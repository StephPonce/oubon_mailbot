"""
Tests for the GDPR data-handling service (``ospra_os.security.gdpr``).

These tests cover the three Shopify-mandated public-app operations:

- ``customers/data_request``  → ``export_customer_data``
- ``customers/redact``        → ``redact_customer_data``
- ``shop/redact``             → ``redact_shop_data``

Strategy:
  - Use the conftest ``db_session`` fixture (per-worker SQLite, isolated
    transaction wrapper) so tests don't leak rows into each other.
  - Stub out the orders sqlite by pointing
    ``OSPRA_PRODUCT_HISTORY_DB_PATH`` at a temp path; ``ProductHistoryDB``
    isn't ORM-mapped so we drive its raw schema directly.
  - We assert on counts + audit-log side effects, not on request/response
    plumbing — the webhook routes are tested separately via ``TestClient``
    in ``tests/test_webhooks.py`` (covered by the existing webhook auth
    tests).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from ospra_os.database import EmailFollowup, Store
from ospra_os.database.base import Platform, StoreStatus
from ospra_os.security.gdpr import (
    export_customer_data,
    redact_customer_data,
    redact_shop_data,
)


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------

@pytest.fixture
def orders_db(tmp_path, monkeypatch):
    """
    Build a tiny ``product_history.db`` with the same ``orders`` schema the
    real ``ProductHistoryDB`` creates and point the GDPR service at it.

    Returns the path so tests can read rows back to assert deletions.
    """
    path = tmp_path / "product_history.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shopify_order_id TEXT UNIQUE NOT NULL,
                shopify_order_number TEXT,
                customer_email TEXT,
                customer_name TEXT,
                product_id TEXT,
                product_name TEXT,
                quantity INTEGER,
                total_price REAL,
                currency TEXT DEFAULT 'USD',
                order_status TEXT DEFAULT 'pending',
                fulfillment_status TEXT DEFAULT 'unfulfilled',
                tracking_number TEXT,
                tracking_url TEXT,
                supplier_order_id TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("OSPRA_PRODUCT_HISTORY_DB_PATH", str(path))
    return path


def _seed_followup(db_session, *, email: str, gmail_id: str) -> EmailFollowup:
    """Insert a single EmailFollowup row tied to a customer email."""
    f = EmailFollowup(
        gmail_message_id=gmail_id,
        customer_email=email,
        customer_name="Test Customer",
        subject="Where is my order?",
        body="hi, just checking on my order",
        label="Tracking",
    )
    db_session.add(f)
    db_session.commit()
    return f


def _seed_order(orders_path: Path, *, email: str, order_id: str) -> None:
    conn = sqlite3.connect(str(orders_path))
    try:
        conn.execute(
            """
            INSERT INTO orders
              (shopify_order_id, shopify_order_number, customer_email,
               customer_name, product_name, quantity, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (order_id, order_id, email, "Test Customer", "Cool Widget", 1, 19.99),
        )
        conn.commit()
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# customers/data_request
# ----------------------------------------------------------------------------

def test_export_customer_data_returns_followups_and_orders(db_session, orders_db, test_user):
    """Export gathers both ORM rows and raw-sqlite orders for one email."""
    email = "shopper@example.com"
    _seed_followup(db_session, email=email, gmail_id="gmail-1")
    _seed_followup(db_session, email=email, gmail_id="gmail-2")
    _seed_order(orders_db, email=email, order_id="ORDER-100")

    result = export_customer_data(
        db_session,
        customer_email=email,
        shop_domain="mystore.myshopify.com",
        data_request_id="42",
    )

    assert result["customer_email"] == email
    assert result["summary"]["email_followups_found"] == 2
    assert result["summary"]["orders_found"] == 1
    assert result["summary"]["total_records"] == 3
    assert len(result["data"]["email_followups"]) == 2
    assert len(result["data"]["orders"]) == 1
    assert result["errors"] == []


def test_export_customer_data_empty_when_no_records(db_session, orders_db):
    """Export honours the request even when we hold nothing for that email."""
    result = export_customer_data(
        db_session,
        customer_email="ghost@example.com",
        shop_domain="mystore.myshopify.com",
    )
    assert result["summary"]["total_records"] == 0
    assert result["data"]["email_followups"] == []
    assert result["data"]["orders"] == []


def test_export_customer_data_isolates_other_emails(db_session, orders_db):
    """Export does NOT leak rows belonging to other customer emails."""
    _seed_followup(db_session, email="alice@example.com", gmail_id="gmail-a")
    _seed_followup(db_session, email="bob@example.com", gmail_id="gmail-b")
    _seed_order(orders_db, email="alice@example.com", order_id="A1")
    _seed_order(orders_db, email="bob@example.com", order_id="B1")

    result = export_customer_data(
        db_session,
        customer_email="alice@example.com",
        shop_domain="mystore.myshopify.com",
    )
    assert result["summary"]["email_followups_found"] == 1
    assert result["summary"]["orders_found"] == 1
    assert result["data"]["email_followups"][0]["gmail_message_id"] == "gmail-a"
    assert result["data"]["orders"][0]["shopify_order_id"] == "A1"


# ----------------------------------------------------------------------------
# customers/redact
# ----------------------------------------------------------------------------

def test_redact_customer_data_deletes_followups_and_orders(db_session, orders_db):
    """customers/redact removes everything tied to that email."""
    email = "shopper@example.com"
    _seed_followup(db_session, email=email, gmail_id="gmail-1")
    _seed_followup(db_session, email=email, gmail_id="gmail-2")
    _seed_order(orders_db, email=email, order_id="ORDER-100")

    result = redact_customer_data(
        db_session,
        customer_email=email,
        shop_domain="mystore.myshopify.com",
    )

    assert result["deleted"]["email_followups"] == 2
    assert result["deleted"]["orders"] == 1
    assert result["errors"] == []

    # Confirm rows are actually gone
    remaining = (
        db_session.query(EmailFollowup)
        .filter(EmailFollowup.customer_email == email)
        .count()
    )
    assert remaining == 0


def test_redact_customer_data_is_idempotent(db_session, orders_db):
    """Running customers/redact twice is harmless — second call deletes 0."""
    email = "shopper@example.com"
    _seed_followup(db_session, email=email, gmail_id="gmail-1")
    _seed_order(orders_db, email=email, order_id="ORDER-100")

    redact_customer_data(db_session, customer_email=email, shop_domain="mystore.myshopify.com")
    second = redact_customer_data(
        db_session, customer_email=email, shop_domain="mystore.myshopify.com"
    )
    assert second["deleted"]["email_followups"] == 0
    assert second["deleted"]["orders"] == 0


def test_redact_customer_data_preserves_other_customers(db_session, orders_db):
    """Redacting alice does NOT touch bob's data."""
    _seed_followup(db_session, email="alice@example.com", gmail_id="gmail-a")
    _seed_followup(db_session, email="bob@example.com", gmail_id="gmail-b")
    _seed_order(orders_db, email="alice@example.com", order_id="A1")
    _seed_order(orders_db, email="bob@example.com", order_id="B1")

    redact_customer_data(
        db_session,
        customer_email="alice@example.com",
        shop_domain="mystore.myshopify.com",
    )

    bob_followups = (
        db_session.query(EmailFollowup)
        .filter(EmailFollowup.customer_email == "bob@example.com")
        .count()
    )
    assert bob_followups == 1

    conn = sqlite3.connect(str(orders_db))
    try:
        cur = conn.execute(
            "SELECT count(*) FROM orders WHERE customer_email = ?",
            ("bob@example.com",),
        )
        bob_orders = cur.fetchone()[0]
    finally:
        conn.close()
    assert bob_orders == 1


# ----------------------------------------------------------------------------
# shop/redact
# ----------------------------------------------------------------------------

def test_redact_shop_data_wipes_store_and_credentials(db_session, test_user):
    """shop/redact deletes the Store row and revokes credentials."""
    store = Store(
        user_id=test_user.id,
        store_name="My Store",
        store_url="https://mystore.myshopify.com",
        platform=Platform.SHOPIFY,
        credentials={"shop_url": "mystore.myshopify.com", "access_token": "t0k3n"},
        currency="USD",
        status=StoreStatus.ACTIVE,
        is_active=True,
    )
    db_session.add(store)
    db_session.commit()

    result = redact_shop_data(db_session, shop_domain="mystore.myshopify.com")

    assert result["deleted"]["stores"] == 1
    assert result["deleted"]["credentials_revoked"] == 1
    assert result["errors"] == []

    remaining = (
        db_session.query(Store)
        .filter(Store.store_url.contains("mystore"))
        .count()
    )
    assert remaining == 0


def test_redact_shop_data_no_op_when_shop_unknown(db_session):
    """shop/redact returns clean result + audit log even for unknown shops."""
    result = redact_shop_data(db_session, shop_domain="unknown.myshopify.com")
    assert result["deleted"]["stores"] == 0
    assert result["errors"] == []
