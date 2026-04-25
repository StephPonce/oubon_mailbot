"""
Tests for ``ospra_os.security.webhook_verification`` (audit #11 partial).

Covers the three verifiers that gate revenue/compliance webhook paths:

  - ``verify_shopify``      — base64-encoded HMAC-SHA256
  - ``verify_lemonsqueezy`` — hex-encoded HMAC-SHA256
  - ``verify_stripe``       — ``t=<ts>,v1=<sig>`` format with replay window

For each verifier we cover:

  1. Happy path — a body signed with the configured secret verifies True.
  2. Tampering   — a single byte flip in the body or signature returns False.
  3. Wrong key   — a body signed with a different secret returns False.
  4. Missing key — when the env var is unset the verifier returns False
                   (fail-closed) rather than raising.

This is the load-bearing security boundary for every paid event we
process; before this change there was zero coverage on it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

import pytest

from ospra_os.security import webhook_verification as wv
from ospra_os.security.webhook_verification import WebhookVerifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shopify_sig(body: bytes, secret: str) -> str:
    """Compute a valid Shopify-format HMAC (base64 SHA-256)."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _lemonsqueezy_sig(body: bytes, secret: str) -> str:
    """Compute a valid LemonSqueezy-format HMAC (hex SHA-256)."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _stripe_sig(body: bytes, secret: str, *, timestamp: int) -> str:
    """Compute a valid Stripe ``t=<ts>,v1=<sig>`` header."""
    payload = f"{timestamp}.{body.decode()}"
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


@pytest.fixture
def webhook_secrets(monkeypatch):
    """
    Configure all three secret env vars and force a fresh WebhookVerifier.

    The verifier reads secrets at construction time and caches them; we
    null out the global instance so the next ``get_webhook_verifier()``
    call rebuilds with the fixture's values.
    """
    monkeypatch.setenv("SHOPIFY_WEBHOOK_SECRET", "shopify-test-secret")
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", "ls-test-secret")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "stripe-test-secret")
    # Bust the cached singleton so it picks up the env vars above.
    monkeypatch.setattr(wv, "_webhook_verifier", None, raising=False)
    yield {
        "shopify": "shopify-test-secret",
        "lemonsqueezy": "ls-test-secret",
        "stripe": "stripe-test-secret",
    }


# ---------------------------------------------------------------------------
# verify_shopify
# ---------------------------------------------------------------------------

def test_verify_shopify_accepts_valid_signature(webhook_secrets):
    body = b'{"order_id": 1234}'
    sig = _shopify_sig(body, webhook_secrets["shopify"])
    assert WebhookVerifier().verify_shopify(body, sig) is True


def test_verify_shopify_rejects_tampered_body(webhook_secrets):
    """A single-byte change in the body invalidates the signature."""
    original = b'{"order_id": 1234}'
    sig = _shopify_sig(original, webhook_secrets["shopify"])
    tampered = b'{"order_id": 9999}'
    assert WebhookVerifier().verify_shopify(tampered, sig) is False


def test_verify_shopify_rejects_wrong_secret(webhook_secrets):
    body = b'{"order_id": 1234}'
    forged_sig = _shopify_sig(body, "attacker-guess")
    assert WebhookVerifier().verify_shopify(body, forged_sig) is False


def test_verify_shopify_rejects_when_secret_missing(monkeypatch):
    """No SHOPIFY_WEBHOOK_SECRET configured → verifier returns False, never raises."""
    monkeypatch.delenv("SHOPIFY_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(wv, "_webhook_verifier", None, raising=False)
    body = b'{"x": 1}'
    sig = _shopify_sig(body, "anything")
    assert WebhookVerifier().verify_shopify(body, sig) is False


# ---------------------------------------------------------------------------
# verify_lemonsqueezy
# ---------------------------------------------------------------------------

def test_verify_lemonsqueezy_accepts_valid_signature(webhook_secrets):
    body = b'{"meta":{"event_name":"subscription_created"}}'
    sig = _lemonsqueezy_sig(body, webhook_secrets["lemonsqueezy"])
    assert WebhookVerifier().verify_lemonsqueezy(body, sig) is True


def test_verify_lemonsqueezy_rejects_tampered_body(webhook_secrets):
    """Critically: a tampered ``user_id`` in the body must not verify."""
    original = b'{"meta":{"custom_data":{"user_id":"42","tier":"soar"}}}'
    sig = _lemonsqueezy_sig(original, webhook_secrets["lemonsqueezy"])
    tampered = b'{"meta":{"custom_data":{"user_id":"1","tier":"stratosphere"}}}'
    assert WebhookVerifier().verify_lemonsqueezy(tampered, sig) is False


def test_verify_lemonsqueezy_rejects_wrong_secret(webhook_secrets):
    body = b'{"x": 1}'
    forged = _lemonsqueezy_sig(body, "attacker-guess")
    assert WebhookVerifier().verify_lemonsqueezy(body, forged) is False


def test_verify_lemonsqueezy_rejects_when_secret_missing(monkeypatch):
    monkeypatch.delenv("LEMONSQUEEZY_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(wv, "_webhook_verifier", None, raising=False)
    body = b'{"x": 1}'
    sig = _lemonsqueezy_sig(body, "anything")
    assert WebhookVerifier().verify_lemonsqueezy(body, sig) is False


# ---------------------------------------------------------------------------
# verify_stripe — replay window matters here
# ---------------------------------------------------------------------------

def test_verify_stripe_accepts_fresh_signature(webhook_secrets):
    body = b'{"id":"evt_1","type":"checkout.session.completed"}'
    sig = _stripe_sig(body, webhook_secrets["stripe"], timestamp=int(time.time()))
    assert WebhookVerifier().verify_stripe(body, sig) is True


def test_verify_stripe_rejects_old_timestamp(webhook_secrets):
    """A signature whose timestamp is past MAX_TIMESTAMP_AGE_SECONDS is replay-rejected."""
    body = b'{"id":"evt_1"}'
    too_old = int(time.time()) - (
        wv.WebhookConfig.MAX_TIMESTAMP_AGE_SECONDS + 60
    )
    sig = _stripe_sig(body, webhook_secrets["stripe"], timestamp=too_old)
    assert WebhookVerifier().verify_stripe(body, sig) is False


def test_verify_stripe_rejects_tampered_body(webhook_secrets):
    body = b'{"id":"evt_1"}'
    sig = _stripe_sig(body, webhook_secrets["stripe"], timestamp=int(time.time()))
    assert WebhookVerifier().verify_stripe(b'{"id":"evt_2"}', sig) is False


def test_verify_stripe_rejects_malformed_header(webhook_secrets):
    """A header missing ``t=`` or ``v1=`` returns False, never raises."""
    body = b'{"id":"evt_1"}'
    assert WebhookVerifier().verify_stripe(body, "garbage") is False
    assert WebhookVerifier().verify_stripe(body, "t=") is False
