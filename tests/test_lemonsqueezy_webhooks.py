"""
Tests for LemonSqueezy webhook routes (audit #11 partial).

The two routes (``/api/webhooks/lemonsqueezy/subscription`` and
``/api/webhooks/lemonsqueezy/order``) are the production tier-upgrade
path for direct-web signups. Before this change neither was exercised
by tests; a regression in signature verification or in the
``upgrade_user_tier`` dispatch would silently accept forged payloads or
miss legitimate ones.

Coverage:

  - Valid signature + ``subscription_created`` upgrades the user's tier.
  - Valid signature + ``subscription_cancelled`` downgrades to NEST.
  - Tampered body returns 401, no DB write.
  - Missing ``X-Signature`` returns 422 (FastAPI dependency raises before
    body verification).
  - ``order_created`` paid event upgrades the user.
  - ``order_refunded`` downgrades to NEST.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from ospra_os.database import User
from ospra_os.security import webhook_verification as wv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ls_sig(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def ls_secret(monkeypatch):
    """Configure the LemonSqueezy signing secret + bust the cached verifier."""
    secret = "ls-test-secret"
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(wv, "_webhook_verifier", None, raising=False)
    return secret


@pytest.fixture
def upgrade_capture(monkeypatch):
    """
    Capture every ``upgrade_user_tier`` call instead of mutating the DB.

    The route uses ``BackgroundTasks`` to dispatch the upgrade. With
    Starlette's ``TestClient`` background tasks run synchronously after
    the response is returned, so by the time ``client.post(...)`` returns
    the captured list contains the upgrade arguments. We patch the
    function on the route module (where it's looked up at call time).
    """
    from ospra_os.api import webhook_routes

    captured: list[tuple[int, str]] = []

    async def fake_upgrade(user_id: int, tier: str, db_session=None):
        captured.append((user_id, tier))
        return True

    monkeypatch.setattr(webhook_routes, "upgrade_user_tier", fake_upgrade)
    return captured


# ---------------------------------------------------------------------------
# /lemonsqueezy/subscription
# ---------------------------------------------------------------------------

def test_subscription_created_upgrades_user(client, ls_secret, upgrade_capture):
    """Happy path: valid sig + active subscription → user upgraded to the requested tier."""
    body = json.dumps({
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {"user_id": "42", "tier": "soar"},
        },
        "data": {
            "attributes": {
                "user_email": "shopper@example.com",
                "status": "active",
                "variant_name": "Soar (monthly)",
            },
        },
    }).encode()
    sig = _ls_sig(body, ls_secret)

    response = client.post(
        "/api/webhooks/lemonsqueezy/subscription",
        content=body,
        headers={"X-Signature": sig, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["event"] == "subscription_created"
    # Upgrade dispatched with the values from custom_data
    assert upgrade_capture == [(42, "soar")]


def test_subscription_cancelled_downgrades_to_nest(client, ls_secret, upgrade_capture):
    """A cancellation event downgrades the user, regardless of stored tier."""
    body = json.dumps({
        "meta": {
            "event_name": "subscription_cancelled",
            "custom_data": {"user_id": "42", "tier": "soar"},
        },
        "data": {"attributes": {"status": "cancelled"}},
    }).encode()
    sig = _ls_sig(body, ls_secret)

    response = client.post(
        "/api/webhooks/lemonsqueezy/subscription",
        content=body,
        headers={"X-Signature": sig, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert upgrade_capture == [(42, "nest")]


def test_subscription_tampered_body_rejected(client, ls_secret, upgrade_capture):
    """
    A body signed for tier=soar but delivered as tier=stratosphere fails
    HMAC verification → 401, no upgrade dispatched.
    """
    original = json.dumps({
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {"user_id": "42", "tier": "soar"},
        },
        "data": {"attributes": {"status": "active"}},
    }).encode()
    sig_for_original = _ls_sig(original, ls_secret)

    forged = json.dumps({
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {"user_id": "42", "tier": "stratosphere"},
        },
        "data": {"attributes": {"status": "active"}},
    }).encode()

    response = client.post(
        "/api/webhooks/lemonsqueezy/subscription",
        content=forged,
        headers={"X-Signature": sig_for_original, "Content-Type": "application/json"},
    )
    assert response.status_code == 401
    assert upgrade_capture == []  # tier-upgrade was never queued


def test_subscription_missing_signature_header_rejected(client, ls_secret, upgrade_capture):
    """No X-Signature header → FastAPI dependency raises before body parse."""
    body = b'{"x": 1}'
    response = client.post(
        "/api/webhooks/lemonsqueezy/subscription",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code in (401, 422)
    assert upgrade_capture == []


# ---------------------------------------------------------------------------
# /lemonsqueezy/order
# ---------------------------------------------------------------------------

def test_order_paid_upgrades_user(client, ls_secret, upgrade_capture):
    body = json.dumps({
        "meta": {
            "event_name": "order_created",
            "custom_data": {"user_id": "9", "tier": "flight"},
        },
        "data": {"attributes": {
            "user_email": "shopper@example.com",
            "status": "paid",
            "total_formatted": "$29.00",
        }},
    }).encode()
    sig = _ls_sig(body, ls_secret)

    response = client.post(
        "/api/webhooks/lemonsqueezy/order",
        content=body,
        headers={"X-Signature": sig, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert upgrade_capture == [(9, "flight")]


def test_order_refunded_downgrades_to_nest(client, ls_secret, upgrade_capture):
    body = json.dumps({
        "meta": {
            "event_name": "order_refunded",
            "custom_data": {"user_id": "9", "tier": "flight"},
        },
        "data": {"attributes": {"status": "refunded"}},
    }).encode()
    sig = _ls_sig(body, ls_secret)

    response = client.post(
        "/api/webhooks/lemonsqueezy/order",
        content=body,
        headers={"X-Signature": sig, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert upgrade_capture == [(9, "nest")]
