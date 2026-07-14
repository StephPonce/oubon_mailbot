"""
Phase 1 step 3 — units-sold snapshots + velocity (fail-if-reverted).

Cumulative sold_count snapshots persist to the EXISTING product_timeseries
store (keyed by TikTok product id via product_identity_key) and the 7-day
velocity is the slope of consecutive snapshots — gated so thin data (<3
points) yields None, never a fabricated trend.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-units-velocity")

from ospra_os.intelligence.velocity_saturation import units_velocity_from_series
from ospra_os.product_research.connectors.apify.tiktok_shop_products import TikTokShopProduct


# ---------------------------------------------------------------------------
# The math
# ---------------------------------------------------------------------------

class TestUnitsVelocityMath:
    def test_rising_cumulative_counts_yield_weekly_rate(self):
        # 100 → 150 → 200 over 2 days = 50 units/day = 350/week.
        result = units_velocity_from_series([100, 150, 200], day_offsets=[0, 1, 2])
        assert result["units_weekly"] == pytest.approx(350.0)
        assert result["n_points"] == 3

    def test_flat_series_is_zero_velocity(self):
        result = units_velocity_from_series([500, 500, 500], day_offsets=[0, 1, 2])
        assert result["units_weekly"] == 0.0

    def test_two_points_are_noise_not_a_trend(self):
        """Re-audit M4 posture: below MIN_SLOPE_POINTS → None."""
        assert units_velocity_from_series([100, 200], day_offsets=[0, 1]) is None

    def test_calendar_gaps_do_not_inflate_slope(self):
        """100 units over 10 calendar days ≠ 100 units/day (re-audit M3)."""
        result = units_velocity_from_series([100, 150, 200], day_offsets=[0, 5, 10])
        assert result["units_weekly"] == pytest.approx(70.0)  # 10/day × 7

    def test_none_days_are_skipped_not_zeroed(self):
        result = units_velocity_from_series(
            [100, None, 200, 300], day_offsets=[0, 1, 2, 4]
        )
        assert result["n_points"] == 3
        assert result["units_weekly"] > 0


# ---------------------------------------------------------------------------
# The store round-trip (snapshot → velocity)
# ---------------------------------------------------------------------------

@pytest.fixture
def timeseries_db(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from ospra_os.database.base import Base
    from ospra_os.database.product_timeseries import ProductTimeseries

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[ProductTimeseries.__table__])
    factory = sessionmaker(bind=engine)

    import ospra_os.database.connection as conn
    monkeypatch.setattr(conn, "SessionLocal", factory)
    return factory


def shop_product(pid="777", sold=1000, title="Magnetic Phone Mount"):
    return TikTokShopProduct(tiktok_product_id=pid, title=title, sold_count=sold)


class TestSnapshotStore:
    def test_snapshot_keys_by_tiktok_product_id(self, timeseries_db):
        from ospra_os.intelligence.units_velocity import snapshot_tiktok_products
        from ospra_os.database.product_timeseries import (
            ProductTimeseries, product_identity_key,
        )

        stats = snapshot_tiktok_products([shop_product()], niche="smart_home")
        assert stats["inserted"] == 1

        session = timeseries_db()
        row = session.query(ProductTimeseries).one()
        session.close()
        # Keyed by the SHARED identity function on the TikTok product id —
        # same store, no parallel table.
        assert row.product_key == product_identity_key({"product_id": "777"})
        assert row.tiktok_units_sold == 1000
        assert row.snapshot_date == datetime.utcnow().date()

    def test_same_day_rerun_updates_not_duplicates(self, timeseries_db):
        from ospra_os.intelligence.units_velocity import snapshot_tiktok_products
        from ospra_os.database.product_timeseries import ProductTimeseries

        snapshot_tiktok_products([shop_product(sold=1000)])
        stats = snapshot_tiktok_products([shop_product(sold=1050)])
        assert stats["updated"] == 1

        session = timeseries_db()
        rows = session.query(ProductTimeseries).all()
        session.close()
        assert len(rows) == 1
        assert rows[0].tiktok_units_sold == 1050

    def test_missing_sold_count_is_skipped_never_zeroed(self, timeseries_db):
        from ospra_os.intelligence.units_velocity import snapshot_tiktok_products
        from ospra_os.database.product_timeseries import ProductTimeseries

        bad = TikTokShopProduct(tiktok_product_id="1", title="x", sold_count=None)  # type: ignore
        stats = snapshot_tiktok_products([bad])
        assert stats["skipped"] == 1

        session = timeseries_db()
        assert session.query(ProductTimeseries).count() == 0
        session.close()

    def test_velocity_from_three_daily_snapshots(self, timeseries_db):
        """End-to-end: three days of history → units_sold_7d velocity."""
        from ospra_os.intelligence.units_velocity import (
            load_units_velocity, snapshot_tiktok_products,
        )
        from ospra_os.database.product_timeseries import ProductTimeseries

        # Seed two BACKDATED snapshots directly (snapshot() writes 'today').
        snapshot_tiktok_products([shop_product(sold=1100)])
        session = timeseries_db()
        row = session.query(ProductTimeseries).one()
        key = row.product_key
        today = datetime.utcnow().date()
        for days_ago, sold in ((2, 1000), (1, 1050)):
            session.add(ProductTimeseries(
                product_key=key,
                snapshot_date=today - timedelta(days=days_ago),
                tiktok_units_sold=sold,
                signal_count=1,
            ))
        session.commit()
        session.close()

        velocity = load_units_velocity("777")
        assert velocity is not None
        assert velocity["n_points"] == 3
        # 1000 → 1050 → 1100 = 50/day = 350/week.
        assert velocity["units_weekly"] == pytest.approx(350.0)

    def test_velocity_none_until_three_snapshots(self, timeseries_db):
        from ospra_os.intelligence.units_velocity import (
            load_units_velocity, snapshot_tiktok_products,
        )

        snapshot_tiktok_products([shop_product(sold=1000)])
        assert load_units_velocity("777") is None  # 1 point = no trend

    def test_snapshot_stamps_derived_velocity_column(self, timeseries_db):
        """Once history exists, today's row records tiktok_velocity too."""
        from ospra_os.intelligence.units_velocity import snapshot_tiktok_products
        from ospra_os.database.product_timeseries import ProductTimeseries

        session = timeseries_db()
        from ospra_os.database.product_timeseries import product_identity_key
        key = product_identity_key({"product_id": "777"})
        today = datetime.utcnow().date()
        for days_ago, sold in ((2, 1000), (1, 1050)):
            session.add(ProductTimeseries(
                product_key=key, snapshot_date=today - timedelta(days=days_ago),
                tiktok_units_sold=sold, signal_count=1,
            ))
        session.commit()
        session.close()

        snapshot_tiktok_products([shop_product(sold=1100)])

        session = timeseries_db()
        row = (
            session.query(ProductTimeseries)
            .filter_by(product_key=key, snapshot_date=today)
            .one()
        )
        session.close()
        assert row.tiktok_velocity == pytest.approx(350.0)
