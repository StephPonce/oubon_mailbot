"""
Tests for AutoDiscoveryJob's real DB-backed lookups (replacing the old
``_get_*_mock`` stubs that ran discovery against fictional users).

We only test the data-access helpers — not the full discovery run, which calls
external APIs. The job is constructed with the conftest ``db_session`` so the
seed data and the job share exactly one session (robust under pytest-xdist).
"""

from __future__ import annotations

from ospra_os.background_jobs.auto_discovery import AutoDiscoveryJob
from ospra_os.database import Store, User, UserSettings
from ospra_os.database.base import Platform, StoreStatus

_EMAIL = "autodiscovery_lookup_test@example.com"


def _seed(db) -> int:
    # Clear any residue from a prior run sharing this DB file, then seed.
    existing = db.query(User).filter(User.email == _EMAIL).first()
    if existing:
        db.delete(existing)
        db.commit()
    u = User(email=_EMAIL, name="AD Test")
    db.add(u)
    db.commit()
    db.refresh(u)
    db.add(UserSettings(user_id=u.id, auto_discover_products=True,
                        min_discovery_score=8.0, preferred_niches=["pet_supplies"]))
    db.add(Store(user_id=u.id, store_name="AD Store",
                 store_url="https://ad-store.myshopify.com", credentials={},
                 platform=Platform.SHOPIFY, status=StoreStatus.ACTIVE))
    db.commit()
    return u.id


def test_lookups_return_real_data(db_session):
    uid = _seed(db_session)
    job = AutoDiscoveryJob(db_session=db_session)

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


def test_get_user_missing_returns_none(db_session):
    job = AutoDiscoveryJob(db_session=db_session)
    assert job._get_user(999_999_999) is None
    assert job._get_user_settings(999_999_999) is None
    assert job._get_user_stores(999_999_999) == []
