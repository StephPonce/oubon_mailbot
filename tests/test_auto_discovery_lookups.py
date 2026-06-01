"""
Tests for AutoDiscoveryJob's real DB-backed lookups (replacing the old
``_get_*_mock`` stubs that ran discovery against fictional users).

We only test the data-access helpers — not the full discovery run, which
calls external APIs. A real user + settings + store are created via the same
global ``SessionLocal`` the job uses, then the job (constructed with that
session) is asked to look them up.
"""

from __future__ import annotations

from ospra_os.background_jobs.auto_discovery import AutoDiscoveryJob
from ospra_os.database import SessionLocal, Store, User, UserSettings
from ospra_os.database.base import Platform, StoreStatus

_EMAIL = "autodiscovery_lookup_test@example.com"


def _seed():
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == _EMAIL).delete()
        db.commit()
        u = User(email=_EMAIL, name="AD Test")
        db.add(u)
        db.commit()
        db.refresh(u)
        db.add(UserSettings(user_id=u.id, auto_discover_products=True,
                            min_discovery_score=8.0, preferred_niches=["pet_supplies"]))
        db.add(Store(user_id=u.id, store_name="AD Store",
                     store_url="https://ad-store.myshopify.com",
                     credentials={}, platform=Platform.SHOPIFY, status=StoreStatus.ACTIVE))
        db.commit()
        return u.id
    finally:
        db.close()


def test_lookups_return_real_data(engine):
    uid = _seed()
    job = AutoDiscoveryJob(db_session=SessionLocal())
    try:
        user = job._get_user(uid)
        assert user is not None and user["id"] == uid and user["email"] == _EMAIL

        settings = job._get_user_settings(uid)
        assert settings is not None
        assert settings["auto_discovery_enabled"] is True
        assert settings["min_product_score"] == 8.0
        assert settings["preferred_niches"] == ["pet_supplies"]

        stores = job._get_user_stores(uid)
        assert len(stores) == 1 and stores[0]["store_name"] == "AD Store"

        all_ids = {u["id"] for u in job._get_all_users()}
        assert uid in all_ids
    finally:
        job.db.close()


def test_get_user_missing_returns_none(engine):
    job = AutoDiscoveryJob(db_session=SessionLocal())
    try:
        assert job._get_user(999_999_999) is None
        assert job._get_user_settings(999_999_999) is None
        assert job._get_user_stores(999_999_999) == []
    finally:
        job.db.close()
