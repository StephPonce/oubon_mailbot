"""
Tests for the DB-backed OAuth state store (audit fix #8).

Covers the contract the three OAuth routers depend on:
  - put → pop round-trip preserves the data dict
  - pop is atomic: a second pop of the same nonce returns None
  - expired nonces return None and are cleaned up inline
  - provider scoping: a nonce registered for ``shopify_partner`` cannot
    be redeemed against ``woocommerce``
  - ``purge_expired`` deletes only expired rows
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest

from ospra_os.security import oauth_state
from ospra_os.security.oauth_state import (
    OAuthState,
    pop_state,
    purge_expired,
    put_state,
)


def _row_count(db_session) -> int:
    return db_session.query(OAuthState).count()


def test_put_then_pop_round_trip(db_session):
    """Putting a state and popping it returns the original metadata."""
    put_state(
        "shopify_partner",
        "nonce-abc",
        {"shop": "demo.myshopify.com", "user_id": 7},
    )
    data = pop_state("shopify_partner", "nonce-abc")
    assert data == {"shop": "demo.myshopify.com", "user_id": 7}
    # Row should be gone — pop is consume-not-read.
    assert _row_count(db_session) == 0


def test_pop_is_atomic_no_replay(db_session):
    """A second pop of the same nonce returns None (replay protection)."""
    put_state("shopify_partner", "nonce-abc", {"shop": "x"})
    assert pop_state("shopify_partner", "nonce-abc") is not None
    assert pop_state("shopify_partner", "nonce-abc") is None


def test_unknown_state_returns_none(db_session):
    """Popping a state that was never put returns None, not an exception."""
    assert pop_state("shopify_partner", "nope") is None


def test_provider_scoping_prevents_cross_flow_use(db_session):
    """
    A nonce registered for one OAuth provider can't be used to claim a
    callback for a different provider. The Shopify Partner App nonce
    should not be redeemable as a WooCommerce nonce.
    """
    put_state("shopify_partner", "shared-nonce", {"shop": "demo"})
    assert pop_state("woocommerce", "shared-nonce") is None
    # The original record is still there (cross-provider lookup didn't consume it).
    assert pop_state("shopify_partner", "shared-nonce") == {"shop": "demo"}


def test_expired_state_returns_none_and_is_cleaned(db_session):
    """An expired nonce is treated as unknown and the row is dropped."""
    put_state("shopify_partner", "expiring", {"shop": "demo"}, ttl_seconds=1)
    # Sleep 1.1s so the row is genuinely past expires_at
    time.sleep(1.1)
    assert pop_state("shopify_partner", "expiring") is None
    assert _row_count(db_session) == 0


def test_purge_expired_only_removes_expired(db_session):
    """purge_expired deletes expired rows but leaves valid ones."""
    put_state("shopify_partner", "fresh", {"shop": "f"}, ttl_seconds=600)
    put_state("shopify_partner", "old", {"shop": "o"}, ttl_seconds=1)
    time.sleep(1.1)
    deleted = purge_expired()
    assert deleted >= 1
    # The fresh nonce should still pop successfully
    assert pop_state("shopify_partner", "fresh") == {"shop": "f"}
    # The old one was already wiped
    assert pop_state("shopify_partner", "old") is None


def test_put_state_handles_empty_metadata(db_session):
    """Storing without metadata is fine — the data dict round-trips as {}."""
    put_state("woocommerce", "bare", None)
    data = pop_state("woocommerce", "bare")
    assert data == {}
