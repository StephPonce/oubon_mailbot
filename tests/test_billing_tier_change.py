"""
Unit tests for the billing tier-change core + hybrid dispatch
(``ospra_os.tasks.billing_tasks``).

The route-level tests in ``test_lemonsqueezy_webhooks.py`` mock the dispatch
seam, so they never exercise the actual DB write or the hybrid worker/inline
decision. These tests cover that real logic:

  * ``apply_tier_change`` updates the user and raises on bad input.
  * ``dispatch_tier_change`` applies inline when no Celery worker is reachable
    (the current Render deployment), and dead-letters a genuinely bad event.

We drive the DB through the same global ``SessionLocal`` the production code
uses, and depend on the ``engine`` fixture so the test tables exist.
"""

from __future__ import annotations

import pytest

from ospra_os.database import SessionLocal, SubscriptionTier, User
from ospra_os.tasks import billing_tasks

_EMAIL = "billing_tier_test@example.com"


def _make_user(tier: SubscriptionTier = SubscriptionTier.NEST) -> int:
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == _EMAIL).delete()
        db.commit()
        u = User(email=_EMAIL, name="Billing Test", subscription_tier=tier)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def _tier_of(user_id: int) -> SubscriptionTier:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first().subscription_tier
    finally:
        db.close()


def test_apply_tier_change_updates_user(engine):
    uid = _make_user(SubscriptionTier.NEST)
    billing_tasks.apply_tier_change(uid, "soar")
    assert _tier_of(uid) == SubscriptionTier.SOAR


def test_apply_tier_change_unknown_tier_raises(engine):
    uid = _make_user()
    with pytest.raises(ValueError):
        billing_tasks.apply_tier_change(uid, "totally-not-a-tier")


def test_apply_tier_change_missing_user_raises(engine):
    with pytest.raises(ValueError):
        billing_tasks.apply_tier_change(999_999_999, "soar")


def test_dispatch_applies_inline_when_no_worker(engine, monkeypatch):
    # Simulate the current Render reality: no Celery worker reachable.
    monkeypatch.setattr(billing_tasks, "_celery_worker_available", lambda ttl=30: False)
    uid = _make_user(SubscriptionTier.NEST)
    outcome = billing_tasks.dispatch_tier_change(uid, "flight", "subscription_created", {})
    assert outcome == "applied"
    assert _tier_of(uid) == SubscriptionTier.FLIGHT


def test_dispatch_dead_letters_unknown_tier_when_no_worker(engine, monkeypatch):
    monkeypatch.setattr(billing_tasks, "_celery_worker_available", lambda ttl=30: False)
    uid = _make_user()
    outcome = billing_tasks.dispatch_tier_change(uid, "bogus-tier", "subscription_created", {})
    assert outcome == "dead_letter"
