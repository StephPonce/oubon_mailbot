"""
Moat Phase 3 step 4 — early-adopter signal reaches the GRADE (fail-if-reverted).

The moat's core question — "is it too late?" — proven end-to-end through the
REAL scoring method (_calculate_scores), same harness as the Phase 1 test:

  two products with IDENTICAL rising units-sold velocity; one carried by
  many stores (saturated), one by ~none (early-adopter). The low-carry one
  must flag early_adopter and grade HIGHER; the saturated one must not.

  And the sacred invariant: missing store-carry is "unknown" — grades
  exactly like a product with no carry data, NEVER silently "low".
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-early-adopter")
os.environ["DISCOVERY_UNITS_VELOCITY_ENABLED"] = "true"
os.environ["DISCOVERY_EARLY_ADOPTER_ENABLED"] = "true"

from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine
from ospra_os.intelligence.store_carry import early_adopter_signal


@pytest.fixture
def timeseries_db(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from ospra_os.database.base import Base
    from ospra_os.database.product_timeseries import ProductTimeseries, product_identity_key

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[ProductTimeseries.__table__])
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        "ospra_os.database.connection.SessionLocal", factory, raising=False
    )

    def seed(product_id, sold_series, store_carry=None):
        """Daily snapshots ending today; store_carry lands on the newest row."""
        key = product_identity_key({"product_id": str(product_id)})
        today = datetime.utcnow().date()
        n = len(sold_series)
        session = factory()
        for i, sold in enumerate(sold_series):
            session.add(ProductTimeseries(
                product_key=key,
                snapshot_date=today - timedelta(days=(n - 1 - i)),
                tiktok_units_sold=sold,
                store_carry_count=store_carry if i == n - 1 else None,
                signal_count=1,
            ))
        session.commit()
        session.close()

    return seed


def _engine():
    eng = ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)
    eng._winner_index_cached = None
    eng._get_learned_signal_weights = lambda: {}
    eng._get_learned_niche_adjustment = lambda niche: 0.0
    eng._extract_meta_winner_index = lambda: {}
    eng._match_product_to_meta_winners = lambda *a, **k: (0, None)
    eng._calculate_relevance = lambda *a, **k: 100
    return eng


def _product(product_id):
    return {
        "title": "Magnetic Phone Mount for Car Vent",
        "product_id": str(product_id),
        "price": 24.99,
        "cost": 6.0,
        "profit_margin": 62.0,
        "sourcing_score": 60,
        "relevance_score": 100,
        "niche": "tech",
        "data_sources": {},
    }


RISING = [1000, 1050, 1100]  # identical demand curve for every product below


class TestEarlyAdopterReachesGrade:
    def test_low_carry_flags_and_outgrades_saturated_at_equal_velocity(self, timeseries_db):
        """THE Phase 3 assertion: same rising velocity, opposite timing."""
        timeseries_db("EARLY", RISING, store_carry=0)     # nobody carries it yet
        timeseries_db("SATURATED", RISING, store_carry=12)  # market moved in

        eng = _engine()
        early = eng._calculate_scores([_product("EARLY")], category_niche="tech")[0]
        saturated = eng._calculate_scores([_product("SATURATED")], category_niche="tech")[0]

        # identical demand — the velocity boost itself must match
        assert early["units_sold_velocity_7d"] == saturated["units_sold_velocity_7d"]

        assert early["early_adopter_flag"] == "early_adopter"
        assert saturated["early_adopter_flag"] == "saturated"
        assert early["oi_score"] > saturated["oi_score"], (
            f"early {early['oi_score']} !> saturated {saturated['oi_score']} — "
            "the pre-saturation window did not reach the grade"
        )
        # bounded: boost above 1, demote below 1, both within the ±15% cap
        assert 1.0 < early["early_adopter_adjustment"] <= 1.15
        assert 0.85 <= saturated["early_adopter_adjustment"] < 1.0

    def test_missing_carry_is_unknown_never_low(self, timeseries_db):
        """A rising product with NO carry measurement must flag 'unknown' and
        grade exactly as if the signal didn't exist — not get the boost a
        genuinely un-carried product earns."""
        timeseries_db("NOCARRY", RISING, store_carry=None)
        timeseries_db("ZEROCARRY", RISING, store_carry=0)

        eng = _engine()
        nocarry = eng._calculate_scores([_product("NOCARRY")], category_niche="tech")[0]
        zerocarry = eng._calculate_scores([_product("ZEROCARRY")], category_niche="tech")[0]

        assert nocarry["early_adopter_flag"] == "unknown"
        assert nocarry.get("early_adopter_adjustment") is None
        assert nocarry["store_carry_count"] is None
        # unknown must NOT be treated as low: the truly-zero-carry product
        # earns the boost, the unknown one does not.
        assert zerocarry["oi_score"] > nocarry["oi_score"]

    def test_no_velocity_means_no_timing_signal(self, timeseries_db):
        """Low carry WITHOUT rising demand is not an early-adopter signal —
        an un-carried product nobody buys is just an un-carried product."""
        timeseries_db("FLATLOW", [1000, 1000, 1000], store_carry=0)

        eng = _engine()
        flat = eng._calculate_scores([_product("FLATLOW")], category_niche="tech")[0]
        assert flat["early_adopter_flag"] == "neutral"
        assert flat.get("early_adopter_adjustment") is None


class TestSignalFunction:
    def test_boost_scales_with_openness_and_demote_with_depth(self):
        full = early_adopter_signal(300, 0)
        partial = early_adopter_signal(300, 2)
        assert full["multiplier"] > partial["multiplier"] > 1.0

        shallow = early_adopter_signal(300, 6)
        deep = early_adopter_signal(300, 20)
        assert deep["multiplier"] < shallow["multiplier"] < 1.0
        assert deep["multiplier"] >= 0.85  # capped

    def test_unknowns(self):
        assert early_adopter_signal(300, None) == {"flag": "unknown", "multiplier": 1.0}
        assert early_adopter_signal(None, 0) == {"flag": "neutral", "multiplier": 1.0}
        assert early_adopter_signal(0, 0)["multiplier"] == 1.0
