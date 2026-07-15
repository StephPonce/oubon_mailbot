"""
Phase 1 step 5 — units-sold velocity reaches the GRADE (fail-if-reverted).

The whole point of Phase 1: real TikTok Shop units_sold velocity is an actual
weighted input to the opportunity score. This proves it end-to-end through the
REAL scoring method (_calculate_scores), the same way the self-learning-loop
test proves an outcome reaches a future score:

  two IDENTICAL products, one whose product_timeseries shows RISING units_sold
  and one FLAT, scored by the real pipeline → the rising product grades higher.

Because the two products are identical in every other field, any scoring quirk
cancels; the score delta isolates the units-velocity boost.
"""

from __future__ import annotations

import copy
import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-units-grade")
os.environ["DISCOVERY_UNITS_VELOCITY_ENABLED"] = "true"

from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine


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

    def seed(product_id, sold_series):
        """Write daily snapshots (oldest→newest ending today) for a product."""
        key = product_identity_key({"product_id": str(product_id)})
        today = datetime.utcnow().date()
        n = len(sold_series)
        session = factory()
        for i, sold in enumerate(sold_series):
            session.add(ProductTimeseries(
                product_key=key,
                snapshot_date=today - timedelta(days=(n - 1 - i)),
                tiktok_units_sold=sold,
                signal_count=1,
            ))
        session.commit()
        session.close()

    return seed


def _engine():
    """A ProductDiscoveryEngine with scoring dependencies stubbed to neutral —
    we exercise the real _calculate_scores body, not the connectors."""
    eng = ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)
    eng._winner_index_cached = None
    eng._get_learned_signal_weights = lambda: {}
    eng._get_learned_niche_adjustment = lambda niche: 0.0
    eng._extract_meta_winner_index = lambda: {}
    eng._match_product_to_meta_winners = lambda *a, **k: (0, None)  # (score, winner_meta)
    eng._calculate_relevance = lambda *a, **k: 100
    return eng


def _product(product_id):
    """A minimal, fully-scoreable product. Both test products are deep copies
    of this — identical except product_id (which selects their timeseries)."""
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


class TestUnitsVelocityReachesGrade:
    def test_rising_units_scores_higher_than_flat(self, timeseries_db):
        timeseries_db("RISING", [1000, 1050, 1100])   # +50/day → +350/week
        timeseries_db("FLAT", [1000, 1000, 1000])     # no growth

        eng = _engine()
        rising = eng._calculate_scores([_product("RISING")], category_niche="tech")[0]
        flat = eng._calculate_scores([_product("FLAT")], category_niche="tech")[0]

        # THE assertion: rising real units-sold measurably lifts the score.
        assert rising["oi_score"] > flat["oi_score"], (
            f"rising {rising['oi_score']} !> flat {flat['oi_score']} — "
            "units velocity did not reach the grade"
        )
        # The boost is present and >1 for rising, absent/neutral for flat.
        assert rising.get("units_velocity_boost", 1.0) > 1.0
        assert rising.get("units_sold_velocity_7d") == pytest.approx(350.0)
        assert flat.get("units_velocity_boost", 1.0) == 1.0

    def test_flat_units_do_not_penalize(self, timeseries_db):
        """A product with flat units must score the SAME as one with no TikTok
        history at all — velocity only lifts, never punishes."""
        timeseries_db("FLAT", [1000, 1000, 1000])

        eng = _engine()
        flat = eng._calculate_scores([_product("FLAT")], category_niche="tech")[0]
        none = eng._calculate_scores([_product("NOHISTORY")], category_niche="tech")[0]

        assert flat["oi_score"] == pytest.approx(none["oi_score"])

    def test_thin_history_does_not_move_grade(self, timeseries_db):
        """Two snapshots are noise (< MIN_SLOPE_POINTS): no boost, same as no
        history — thin data must not move the grade."""
        timeseries_db("THIN", [1000, 2000])  # huge jump but only 2 points

        eng = _engine()
        thin = eng._calculate_scores([_product("THIN")], category_niche="tech")[0]
        none = eng._calculate_scores([_product("NOHISTORY2")], category_niche="tech")[0]

        assert thin.get("units_velocity_boost", 1.0) == 1.0
        assert thin["oi_score"] == pytest.approx(none["oi_score"])
