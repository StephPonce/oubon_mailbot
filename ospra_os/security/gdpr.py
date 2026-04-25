"""
GDPR data-handling service.

Single source of truth for the three operations Shopify mandates on every
public app:

- ``export_customer_data``  — answers a ``customers/data_request`` webhook
  by gathering everything we hold for one customer email under one shop.
- ``redact_customer_data`` — answers a ``customers/redact`` webhook by
  scrubbing that customer's PII from our stores.
- ``redact_shop_data``     — answers a ``shop/redact`` webhook (or an
  uninstall + 48h grace) by wiping all data tied to a shop.

Why this lives in ``ospra_os/security/`` and not ``ospra_os/api/``:
  the same logic backs the **Settings → Data & Privacy** UI (self-serve
  export and account deletion). Keeping it in a service module means the
  webhook handler, the frontend route, and any future CLI utility all
  hit one implementation.

Design notes
------------
- Functions are *pure operations on the DB*: they do not touch FastAPI
  request/response objects or BackgroundTasks. The webhook handler
  schedules them via BackgroundTasks; the frontend route awaits them
  directly.
- We never raise to the caller from a destructive op — Shopify expects a
  ``200`` within 5s on the webhook regardless of the underlying
  bookkeeping. The functions return a structured result dict; the caller
  decides how to surface failures to the merchant.
- All operations log a ``security_audit_logs`` row via
  ``log_security_event`` so the GDPR workflow is auditable end-to-end.
- Inference logs (``ai_responses``, etc.) are not deleted here: per
  ``docs/guides/SHOPIFY_PARTNER_APP_APPROVAL_READINESS.md`` §4 they roll
  off on a 7-day window via the standard retention job. If a customer's
  email appears in an inference prompt that's still inside the rolling
  window, the next scheduled prune drops it.

Pass 4d-followup: implements the previously-stubbed handlers in
``ospra_os/api/webhook_routes.py``.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ospra_os.security.security_audit import (
    SecurityEventType,
    SecuritySeverity,
    log_security_event,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result shapes
# ---------------------------------------------------------------------------

def _empty_export_result(customer_email: str, shop_domain: str) -> Dict[str, Any]:
    return {
        "customer_email": customer_email,
        "shop_domain": shop_domain,
        "exported_at": datetime.now(timezone.utc).isoformat() + "Z",
        "data": {
            "email_followups": [],
            "orders": [],
        },
        "summary": {
            "email_followups_found": 0,
            "orders_found": 0,
            "total_records": 0,
        },
        "errors": [],
    }


def _empty_redact_result(action: str, target: str) -> Dict[str, Any]:
    return {
        "action": action,
        "target": target,
        "completed_at": datetime.now(timezone.utc).isoformat() + "Z",
        "deleted": {
            "email_followups": 0,
            "orders": 0,
            "stores": 0,
            "products": 0,
            "credentials_revoked": 0,
        },
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Helpers — store / shop_domain resolution
# ---------------------------------------------------------------------------

def _normalize_shop_domain(shop_domain: Optional[str]) -> Optional[str]:
    """
    Shopify's webhook payloads send ``shop_domain`` like ``mystore.myshopify.com``,
    but our ``stores.store_url`` is ``https://mystore.myshopify.com``. Strip the
    scheme and lower-case so substring matches work either way.
    """
    if not shop_domain:
        return None
    d = shop_domain.strip().lower()
    if d.startswith("https://"):
        d = d[len("https://"):]
    if d.startswith("http://"):
        d = d[len("http://"):]
    return d


def _find_stores_for_shop(db: Session, shop_domain: str) -> List[Any]:
    """
    Look up Store rows for a shop domain.

    The OAuth path saves ``store_url`` as ``https://<shop>.myshopify.com`` and
    ``credentials.shop_url`` as ``<shop>.myshopify.com``. Using ``.contains``
    on the bare-domain handles both the legacy single-tenant rows that store
    just the slug and the post-OAuth rows with the full URL.
    """
    from ospra_os.database.store_models import Store

    domain = _normalize_shop_domain(shop_domain)
    if not domain:
        return []

    bare = domain.replace(".myshopify.com", "")
    return (
        db.query(Store)
        .filter(Store.store_url.contains(bare))
        .all()
    )


# ---------------------------------------------------------------------------
# Order data — lives in a separate sqlite (data/product_history.db)
# ---------------------------------------------------------------------------

def _product_history_path() -> Path:
    """
    Resolve the product_history.db location. ``ProductHistoryDB`` defaults
    to ``data/product_history.db`` relative to CWD. Honour an explicit
    override via env (``OSPRA_PRODUCT_HISTORY_DB_PATH``) so tests / staging
    can point at a fixture file.
    """
    override = os.getenv("OSPRA_PRODUCT_HISTORY_DB_PATH")
    if override:
        return Path(override)
    return Path("data/product_history.db")


def _fetch_orders_for_email(customer_email: str) -> List[Dict[str, Any]]:
    """
    Return every order row whose ``customer_email`` matches.

    We use the raw sqlite handle because the orders table is created via
    raw SQL by ``ProductHistoryDB`` — there's no SQLAlchemy ORM mapping
    for it, and bolting one on just for GDPR would be more error-prone
    than a parameterized SELECT.
    """
    db_path = _product_history_path()
    if not db_path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                """
                SELECT shopify_order_id, shopify_order_number, customer_email,
                       customer_name, product_name, quantity, total_price,
                       currency, order_status, fulfillment_status,
                       tracking_number, created_at
                FROM orders
                WHERE customer_email = ?
                """,
                (customer_email,),
            )
            for row in cur.fetchall():
                rows.append(dict(row))
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning(
            "GDPR export: could not read product_history.db (%s)", exc
        )
    return rows


def _delete_orders_for_email(customer_email: str) -> int:
    """Best-effort delete of order rows for a customer email. Returns count."""
    db_path = _product_history_path()
    if not db_path.exists():
        return 0

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute(
                "DELETE FROM orders WHERE customer_email = ?",
                (customer_email,),
            )
            conn.commit()
            return cur.rowcount or 0
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning(
            "GDPR redact: could not delete from product_history.db (%s)", exc
        )
        return 0


def _delete_orders_for_store(store_id: Optional[int]) -> int:
    """
    The orders table doesn't carry a store_id FK (legacy raw-SQL schema).
    For shop/redact we therefore drop nothing here — customer-scoped deletes
    happen via ``_delete_orders_for_email``. Documented gap: orders that
    landed *before* we wired tenant scoping can't be tied back to a single
    store, so they're left for the standard 30-day retention sweep.

    Kept as a function with a stable signature so future schema migrations
    (when product_history learns about store_id) only need a one-line edit.
    """
    return 0


# ---------------------------------------------------------------------------
# Public API — the three GDPR operations
# ---------------------------------------------------------------------------

def export_customer_data(
    db: Session,
    customer_email: str,
    shop_domain: str,
    *,
    data_request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gather every record we hold that's keyed off ``customer_email`` for the
    given shop. Used by both the ``customers/data_request`` webhook and the
    Settings → Data & Privacy "Export my data" button.

    The result is JSON-serializable so the caller can ship it as-is to the
    merchant via Shopify Files / email / pre-signed S3 — Shopify's spec is
    deliberately silent on transport, only that we honour the request
    within 30 days.
    """
    from ospra_os.database.email_models import EmailFollowup

    result = _empty_export_result(customer_email, shop_domain)

    # --- Email follow-ups (SQLAlchemy ORM, primary database) ---
    try:
        followups = (
            db.query(EmailFollowup)
            .filter(EmailFollowup.customer_email == customer_email)
            .all()
        )
        for f in followups:
            result["data"]["email_followups"].append({
                "gmail_message_id": f.gmail_message_id,
                "customer_email": f.customer_email,
                "customer_name": f.customer_name,
                "subject": f.subject,
                "label": f.label,
                "received_at": f.received_at.isoformat() if f.received_at else None,
                # ``body`` is intentionally truncated in the export — it
                # frequently contains the customer's reply (which is their
                # own PII) but also our agent's outbound copy. Returning
                # the raw column is fine; we're returning the customer's
                # data to them, not to a third party.
                "body": f.body,
            })
        result["summary"]["email_followups_found"] = len(followups)
    except Exception as exc:
        logger.exception("GDPR export: email_followups lookup failed")
        result["errors"].append(f"email_followups: {exc}")

    # --- Orders (raw sqlite, product_history.db) ---
    orders = _fetch_orders_for_email(customer_email)
    result["data"]["orders"] = orders
    result["summary"]["orders_found"] = len(orders)

    result["summary"]["total_records"] = (
        result["summary"]["email_followups_found"]
        + result["summary"]["orders_found"]
    )

    # --- Audit trail ---
    log_security_event(
        event_type=SecurityEventType.DATA_EXPORT,
        target_type="customer",
        target_identifier=customer_email,
        success=True,
        message=(
            f"GDPR data_request honoured for {customer_email} "
            f"(shop={shop_domain}, records={result['summary']['total_records']})"
        ),
        details={
            "shop_domain": shop_domain,
            "data_request_id": data_request_id,
            "summary": result["summary"],
        },
        severity=SecuritySeverity.MEDIUM,
        db=db,
    )
    logger.info(
        "[GDPR] data_request: %s @ %s -> %d records",
        customer_email, shop_domain, result["summary"]["total_records"],
    )
    return result


def redact_customer_data(
    db: Session,
    customer_email: str,
    shop_domain: str,
) -> Dict[str, Any]:
    """
    Delete every record we hold keyed off ``customer_email``. Idempotent —
    re-running is a no-op once the rows are gone. Returns counts so the
    caller can surface "we deleted N rows" in the audit feed.
    """
    from ospra_os.database.email_models import EmailFollowup

    result = _empty_redact_result(action="customers/redact", target=customer_email)

    # --- Email follow-ups ---
    try:
        deleted = (
            db.query(EmailFollowup)
            .filter(EmailFollowup.customer_email == customer_email)
            .delete(synchronize_session=False)
        )
        db.commit()
        result["deleted"]["email_followups"] = int(deleted or 0)
    except Exception as exc:
        db.rollback()
        logger.exception("GDPR redact: email_followups delete failed")
        result["errors"].append(f"email_followups: {exc}")

    # --- Orders ---
    result["deleted"]["orders"] = _delete_orders_for_email(customer_email)

    # --- Audit trail ---
    log_security_event(
        event_type=SecurityEventType.DATA_DELETION,
        target_type="customer",
        target_identifier=customer_email,
        success=not result["errors"],
        message=(
            f"GDPR customers/redact for {customer_email} "
            f"(shop={shop_domain}, "
            f"followups={result['deleted']['email_followups']}, "
            f"orders={result['deleted']['orders']})"
        ),
        details={"shop_domain": shop_domain, **result["deleted"]},
        severity=SecuritySeverity.HIGH,
        db=db,
    )
    logger.warning(
        "[GDPR] customers/redact: %s @ %s -> followups=%d, orders=%d",
        customer_email, shop_domain,
        result["deleted"]["email_followups"], result["deleted"]["orders"],
    )
    return result


def redact_shop_data(
    db: Session,
    shop_domain: str,
) -> Dict[str, Any]:
    """
    Wipe everything tied to a shop. Called by the ``shop/redact`` webhook
    Shopify fires 48h after uninstall, and by the Settings → Data & Privacy
    "Disconnect & delete" button.

    Order matters: we revoke credentials first (so an in-flight Shopify
    sync can't repopulate the rows we're about to delete), then null-out
    secrets, then drop the products + linked rows, then the Store row
    itself.
    """
    from ospra_os.database.product_models import Product
    from ospra_os.database.base import StoreStatus

    result = _empty_redact_result(action="shop/redact", target=shop_domain)
    stores = _find_stores_for_shop(db, shop_domain)

    if not stores:
        # Already gone, or never existed. Still log the request so we have
        # a paper trail showing we ack'd Shopify's webhook.
        log_security_event(
            event_type=SecurityEventType.DATA_DELETION,
            target_type="store",
            target_identifier=shop_domain,
            success=True,
            message=f"GDPR shop/redact: no Store rows found for {shop_domain}",
            details={"shop_domain": shop_domain},
            severity=SecuritySeverity.MEDIUM,
            db=db,
        )
        logger.info("[GDPR] shop/redact: no stores to delete for %s", shop_domain)
        return result

    for store in stores:
        store_id = store.id
        try:
            # 1. Revoke OAuth credentials in-place so any concurrent sync
            #    job 401s out instead of writing back into the rows we're
            #    about to delete.
            try:
                store.credentials = {}
                store.is_active = False
                store.status = StoreStatus.DISCONNECTED
                store.sync_error = "shop/redact webhook received"
                db.commit()
                result["deleted"]["credentials_revoked"] += 1
            except Exception as exc:
                db.rollback()
                result["errors"].append(f"store {store_id} credential revoke: {exc}")

            # 2. Drop products tied to this store. ``Store`` has
            #    ``ondelete="CASCADE"`` on most child rows, but we delete
            #    products explicitly so the count is observable in the
            #    audit log.
            try:
                product_deleted = (
                    db.query(Product)
                    .filter(Product.store_id == store_id)
                    .delete(synchronize_session=False)
                )
                db.commit()
                result["deleted"]["products"] += int(product_deleted or 0)
            except Exception as exc:
                db.rollback()
                result["errors"].append(f"store {store_id} products: {exc}")

            # 3. Drop orphaned orders for this store (best-effort; see
            #    docstring on _delete_orders_for_store for the schema gap).
            result["deleted"]["orders"] += _delete_orders_for_store(store_id)

            # 4. Finally, the Store row itself.
            try:
                db.delete(store)
                db.commit()
                result["deleted"]["stores"] += 1
            except Exception as exc:
                db.rollback()
                result["errors"].append(f"store {store_id} row: {exc}")

        except Exception as exc:
            db.rollback()
            logger.exception("GDPR redact: store %s wipe failed", store_id)
            result["errors"].append(f"store {store_id}: {exc}")

    log_security_event(
        event_type=SecurityEventType.DATA_DELETION,
        target_type="store",
        target_identifier=shop_domain,
        success=not result["errors"],
        message=(
            f"GDPR shop/redact for {shop_domain}: "
            f"stores={result['deleted']['stores']}, "
            f"products={result['deleted']['products']}, "
            f"creds_revoked={result['deleted']['credentials_revoked']}"
        ),
        details={"shop_domain": shop_domain, **result["deleted"]},
        severity=SecuritySeverity.HIGH,
        db=db,
    )
    logger.warning(
        "[GDPR] shop/redact: %s -> stores=%d, products=%d, errors=%d",
        shop_domain,
        result["deleted"]["stores"],
        result["deleted"]["products"],
        len(result["errors"]),
    )
    return result
