"""
Billing / entitlement safety regression tests (Section B band 3: T27/T31/T28).

T27: payment webhooks had no replay protection (a retried delivery applied the
tier change twice) and a failed tier change still returned HTTP 200 (customer
paid, never upgraded, provider never retried).
T31: template purchase trusted a client-supplied payment_token without reading
it — POSTing any string bought any paid template for free.
T28: the email-automation refund path called lookup_order / get_order_status /
format_tracking_response / process_refund on ShopifyClient — none of which
existed, so the first real refund email raised AttributeError and the refund
guardrails never ran.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-billing")

from ospra_os.security import webhook_verification as wv


def _ls_sig(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def ls_secret(monkeypatch):
    secret = "ls-test-secret"
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(wv, "_webhook_verifier", None, raising=False)
    return secret


@pytest.fixture
def dispatch_capture(monkeypatch):
    """Capture tier-change dispatches; individual tests flip the outcome."""
    from ospra_os.api import webhook_routes

    # The dedup table is created by init_db()'s create_all in prod; the test
    # DB skips that path, so ensure it exists on the engine get_session uses.
    from ospra_os.database.base import Base
    from ospra_os.database.connection import get_engine
    from ospra_os.database.webhook_event_models import ProcessedWebhookEvent

    Base.metadata.create_all(get_engine(), tables=[ProcessedWebhookEvent.__table__])

    state = {"calls": [], "outcome": True}

    def fake_enqueue(user_id, tier, event_name=None, payload=None):
        state["calls"].append((user_id, tier, event_name))
        return state["outcome"]

    monkeypatch.setattr(webhook_routes, "_enqueue_tier_change", fake_enqueue)
    return state


def sub_created_body(user_id="42", tier="soar", nonce="a"):
    return json.dumps({
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {"user_id": user_id, "tier": tier, "nonce": nonce},
        },
        "data": {
            "attributes": {
                "user_email": "shopper@example.com",
                "status": "active",
                "variant_name": "Soar (monthly)",
            },
        },
    }).encode()


def post_sub(client, body, secret):
    return client.post(
        "/api/webhooks/lemonsqueezy/subscription",
        content=body,
        headers={"X-Signature": _ls_sig(body, secret), "Content-Type": "application/json"},
    )


# ---------------------------------------------------------------------------
# T27 — webhook idempotency + honest failure signaling
# ---------------------------------------------------------------------------

class TestT27WebhookIdempotency:
    def test_replayed_delivery_is_not_applied_twice(self, client, ls_secret, dispatch_capture):
        body = sub_created_body(nonce="replay-test")

        first = post_sub(client, body, ls_secret)
        second = post_sub(client, body, ls_secret)  # exact replay

        assert first.status_code == 200
        assert second.status_code == 200  # acked, but…
        assert second.json().get("duplicate") is True
        assert len(dispatch_capture["calls"]) == 1  # …applied exactly once

    def test_failed_tier_change_returns_5xx_for_provider_retry(self, client, ls_secret, dispatch_capture):
        """DB failure must NOT be acked with 200 — LemonSqueezy only retries
        on failure statuses."""
        dispatch_capture["outcome"] = False
        body = sub_created_body(nonce="failure-test")

        response = post_sub(client, body, ls_secret)

        assert response.status_code == 500

    def test_provider_retry_after_failure_is_processed(self, client, ls_secret, dispatch_capture):
        """A failure releases the idempotency claim: the provider's retry of
        the SAME body must be applied (not treated as a duplicate)."""
        dispatch_capture["outcome"] = False
        body = sub_created_body(nonce="retry-after-failure")
        assert post_sub(client, body, ls_secret).status_code == 500

        dispatch_capture["outcome"] = True  # DB healthy again
        response = post_sub(client, body, ls_secret)

        assert response.status_code == 200
        assert response.json().get("duplicate") is not True
        assert len(dispatch_capture["calls"]) == 2

    def test_order_webhook_replay_protected_too(self, client, ls_secret, dispatch_capture):
        body = json.dumps({
            "meta": {
                "event_name": "order_created",
                "custom_data": {"user_id": "42", "tier": "flight"},
            },
            "data": {"attributes": {
                "user_email": "shopper@example.com",
                "status": "paid",
                "total_formatted": "$29.00",
            }},
        }).encode()

        def post(b):
            return client.post(
                "/api/webhooks/lemonsqueezy/order",
                content=b,
                headers={"X-Signature": _ls_sig(b, ls_secret), "Content-Type": "application/json"},
            )

        assert post(body).status_code == 200
        replay = post(body)
        assert replay.status_code == 200
        assert replay.json().get("duplicate") is True
        assert len(dispatch_capture["calls"]) == 1


# ---------------------------------------------------------------------------
# T31 — template purchase verifies payment server-side
# ---------------------------------------------------------------------------

@pytest.fixture
def template_env(monkeypatch):
    """sqlite DB with a paid template + a user; LS API key configured."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from ospra_os.database.base import Base
    from ospra_os.database import User
    from ospra_os.database.template_models import ActionTemplate, TemplatePurchase

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[
        User.__table__, ActionTemplate.__table__, TemplatePurchase.__table__
    ])
    session = sessionmaker(bind=engine)()

    user = User(email="buyer@example.com", name="Buyer", password_hash="x")
    session.add(user)
    session.flush()

    template = ActionTemplate(
        creator_id=user.id, name="Paid Template", slug="paid-template",
        description="d", actions=[], category="ops", status="published",
        is_free=False, price=25.0, revenue_share=0.7,
    )
    session.add(template)
    session.commit()

    monkeypatch.setenv("LEMONSQUEEZY_API_KEY", "ls-api-key")
    return session, user, template


def ls_order_response(status="paid", total_cents=2500, email="buyer@example.com"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {"attributes": {"status": status, "total": total_cents, "user_email": email}}
    }
    return resp


class TestT31PurchaseVerification:
    def _service(self, session, user):
        from ospra_os.services.template_service import TemplateService
        return TemplateService(session, user.id)

    def test_junk_token_no_longer_buys_a_template(self, template_env):
        session, user, template = template_env
        from ospra_os.database.template_models import TemplatePurchase

        with pytest.raises(ValueError):
            self._service(session, user).purchase_template(template.id, "i-am-not-a-payment")

        assert session.query(TemplatePurchase).count() == 0

    def test_no_api_key_fails_closed(self, template_env, monkeypatch):
        session, user, template = template_env
        monkeypatch.delenv("LEMONSQUEEZY_API_KEY")

        with pytest.raises(ValueError, match="not configured"):
            self._service(session, user).purchase_template(template.id, "12345")

    def test_unpaid_order_rejected(self, template_env, monkeypatch):
        session, user, template = template_env
        monkeypatch.setattr("httpx.get", lambda *a, **k: ls_order_response(status="pending"))

        with pytest.raises(ValueError, match="not completed"):
            self._service(session, user).purchase_template(template.id, "12345")

    def test_underpaid_order_rejected(self, template_env, monkeypatch):
        session, user, template = template_env
        monkeypatch.setattr("httpx.get", lambda *a, **k: ls_order_response(total_cents=100))

        with pytest.raises(ValueError, match="amount"):
            self._service(session, user).purchase_template(template.id, "12345")

    def test_other_users_payment_rejected(self, template_env, monkeypatch):
        session, user, template = template_env
        monkeypatch.setattr(
            "httpx.get", lambda *a, **k: ls_order_response(email="attacker@example.com")
        )

        with pytest.raises(ValueError, match="different account"):
            self._service(session, user).purchase_template(template.id, "12345")

    def test_verified_payment_grants_purchase(self, template_env, monkeypatch):
        session, user, template = template_env
        monkeypatch.setattr("httpx.get", lambda *a, **k: ls_order_response())

        purchase = self._service(session, user).purchase_template(template.id, "12345")

        assert purchase.status == "completed"
        assert purchase.transaction_id == "ls_order_12345"
        assert purchase.price_paid == 25.0

    def test_payment_cannot_be_reused(self, template_env, monkeypatch):
        session, user, template = template_env
        from ospra_os.database.template_models import ActionTemplate
        monkeypatch.setattr("httpx.get", lambda *a, **k: ls_order_response())

        self._service(session, user).purchase_template(template.id, "12345")

        second = ActionTemplate(
            creator_id=user.id, name="Another", slug="another", description="d",
            actions=[], category="ops", status="published", is_free=False,
            price=25.0, revenue_share=0.7,
        )
        session.add(second)
        session.commit()

        with pytest.raises(ValueError, match="already used"):
            self._service(session, user).purchase_template(second.id, "12345")


# ---------------------------------------------------------------------------
# T28 — refund path works end-to-end against the REAL ShopifyClient
# ---------------------------------------------------------------------------

@pytest.fixture
def shopify_client(monkeypatch):
    from ospra_os.integrations.shopify.client import ShopifyClient
    return ShopifyClient(store_name="test-store", access_token="tok")


def order_payload(total="49.99", email="jane@example.com", days_old=3):
    created = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    return {
        "id": 555, "name": "#1001", "created_at": created,
        "total_price": total, "financial_status": "paid",
        "fulfillment_status": None, "email": email,
        "customer": {"email": email},
        "fulfillments": [],
    }


def fake_responses(client, monkeypatch, mapping):
    """Stub _sync_request; mapping keys are (method, path-prefix)."""
    calls = []

    def fake(method, path, json_body=None, params=None):
        calls.append((method, path, json_body, params))
        for (m, prefix), resp in mapping.items():
            if m == method and path.startswith(prefix):
                return resp
        raise AssertionError(f"Unexpected request {method} {path}")

    monkeypatch.setattr(client, "_sync_request", fake)
    return calls


def resp(status_code=200, body=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = body or {}
    r.text = text
    return r


class TestT28ShopifyRefundPath:
    def test_methods_exist_on_canonical_client(self, shopify_client):
        """The AttributeError class of bug: these four are what the email
        automation calls."""
        for method in ("lookup_order", "get_order_status",
                       "format_tracking_response", "process_refund"):
            assert callable(getattr(shopify_client, method))

    def test_lookup_order_by_customer_number(self, shopify_client, monkeypatch):
        calls = fake_responses(shopify_client, monkeypatch, {
            ("GET", "/orders.json"): resp(body={"orders": [order_payload()]}),
        })

        order = shopify_client.lookup_order("1001")

        assert order["name"] == "#1001"
        assert calls[0][3] == {"name": "#1001", "status": "any"}

    def test_process_refund_caps_at_shopify_refundable(self, shopify_client, monkeypatch):
        """Even if asked for more, never refund past what Shopify says is
        refundable on the parent transaction."""
        calls = fake_responses(shopify_client, monkeypatch, {
            ("POST", "/orders/555/refunds/calculate.json"): resp(body={
                "refund": {"transactions": [{
                    "parent_id": 777, "amount": "30.00",
                    "maximum_refundable": "30.00", "gateway": "shopify_payments",
                }]},
            }),
            ("POST", "/orders/555/refunds.json"): resp(status_code=201, body={
                "refund": {"id": 9001},
            }),
        })

        result = shopify_client.process_refund(order_id=555, amount=100.0, reason="damaged")

        assert result["success"] is True
        assert result["refund_id"] == 9001
        assert result["amount"] == 30.0
        refund_call = [c for c in calls if c[1] == "/orders/555/refunds.json"][0]
        assert refund_call[2]["refund"]["transactions"][0]["amount"] == "30.00"

    def test_process_refund_fails_safely_when_calculate_fails(self, shopify_client, monkeypatch):
        fake_responses(shopify_client, monkeypatch, {
            ("POST", "/orders/555/refunds/calculate.json"): resp(status_code=422),
        })

        result = shopify_client.process_refund(order_id=555, amount=10.0)

        assert result["success"] is False

    def test_refund_guardrails_run_end_to_end(self, shopify_client, monkeypatch):
        """The full email → decision → refund chain with the REAL
        RefundProcessor and REAL ShopifyClient (stubbed HTTP): guardrails
        execute and the refund is placed."""
        from ospra_os.email_automation.smart_reply import SmartReplySystem
        from ospra_os.email_automation.refund_processor import RefundProcessor

        fake_responses(shopify_client, monkeypatch, {
            ("GET", "/orders.json"): resp(body={"orders": [order_payload(total="49.99")]}),
            ("POST", "/orders/555/refunds/calculate.json"): resp(body={
                "refund": {"transactions": [{
                    "parent_id": 777, "amount": "49.99",
                    "maximum_refundable": "49.99", "gateway": "shopify_payments",
                }]},
            }),
            ("POST", "/orders/555/refunds.json"): resp(status_code=201, body={
                "refund": {"id": 9002},
            }),
        })

        sr = SmartReplySystem.__new__(SmartReplySystem)
        sr.shopify = shopify_client
        sr.brand_name = "Test Brand"
        sr.refund_processor = RefundProcessor(
            max_auto_refund_amount=100.0, auto_refund_days_limit=15,
            require_reason_keywords=True, require_shipped_back=True,
        )

        reply = sr._handle_refund_request(
            subject="Refund for order #1001",
            body="My order #1001 arrived broken. I will ship it back for a refund.",
            customer_name="Jane",
            customer_email="jane@example.com",
            templates={},
            metadata={},
        )

        assert reply["metadata"]["refund_attempted"] is True
        assert reply["metadata"]["refund_success"] is True
        assert reply["metadata"]["refund_id"] == 9002

    def test_refund_guardrails_block_over_limit_orders(self, shopify_client, monkeypatch):
        """A $250 order must NOT be auto-refunded (the $100 cap) — and with
        T28 the check actually executes instead of AttributeError-ing."""
        from ospra_os.email_automation.smart_reply import SmartReplySystem
        from ospra_os.email_automation.refund_processor import RefundProcessor

        calls = fake_responses(shopify_client, monkeypatch, {
            ("GET", "/orders.json"): resp(body={"orders": [order_payload(total="250.00")]}),
        })

        sr = SmartReplySystem.__new__(SmartReplySystem)
        sr.shopify = shopify_client
        sr.brand_name = "Test Brand"
        sr.refund_processor = RefundProcessor(
            max_auto_refund_amount=100.0, auto_refund_days_limit=15,
            require_reason_keywords=True, require_shipped_back=True,
        )

        reply = sr._handle_refund_request(
            subject="Refund for order #1001",
            body="My order #1001 arrived broken. I will ship it back for a refund.",
            customer_name="Jane",
            customer_email="jane@example.com",
            templates={},
            metadata={},
        )

        assert reply["metadata"].get("refund_success") is None  # never placed
        refund_calls = [c for c in calls if "refunds" in c[1]]
        assert refund_calls == []

    def test_stranger_cannot_refund_someone_elses_order(self, shopify_client, monkeypatch):
        from ospra_os.email_automation.smart_reply import SmartReplySystem
        from ospra_os.email_automation.refund_processor import RefundProcessor

        calls = fake_responses(shopify_client, monkeypatch, {
            ("GET", "/orders.json"): resp(body={"orders": [order_payload(email="victim@example.com")]}),
        })

        sr = SmartReplySystem.__new__(SmartReplySystem)
        sr.shopify = shopify_client
        sr.brand_name = "Test Brand"
        sr.refund_processor = RefundProcessor()

        reply = sr._handle_refund_request(
            subject="Refund for order #1001",
            body="Order #1001 arrived broken. I will ship it back.",
            customer_name="Mallory",
            customer_email="attacker@example.com",
            templates={"refund_request": {"subject": "Your refund request", "body": "Hi {{name}}"}},
            metadata={},
        )

        assert reply["metadata"].get("ownership_check_failed") is True
        assert [c for c in calls if "refunds" in c[1]] == []
