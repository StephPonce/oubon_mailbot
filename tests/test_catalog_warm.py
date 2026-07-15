"""
Catalog warm + persistent discovered_catalog tests (#56).

Pins the durable catalog the scheduled discovery cron writes and the API reads:
upsert/dedupe, proof-age accrual (first_seen preserved, times_seen bumped),
saturation→opportunity normalization, and grade/score extraction.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ospra_os.database.base import Base
from ospra_os.database.discovered_catalog import DiscoveredProduct
from ospra_os.database.product_timeseries import ProductTimeseries
from ospra_os.tasks import catalog_warm as cw


@pytest.fixture()
def session():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(
        eng, tables=[DiscoveredProduct.__table__, ProductTimeseries.__table__]
    )
    yield sessionmaker(bind=eng)()


PLUG = {
    "title": "WiFi Smart Plug Energy Monitor", "image_url": "http://img/1.jpg",
    "source": "cj_dropshipping", "tier": "BUY", "final_score": 82.0,
    "saturation_score": 0.28, "sentiment_score": 71, "velocity_phase": "early_spike",
}
SINK = {
    "title": "Basin Sink Plug", "image_url": "http://img/3.jpg",
    "source": "cj_dropshipping", "tier": "AVOID", "final_score": 16.0, "saturation_score": 0.9,
}


def test_insert_then_read(session):
    assert cw.upsert_product(session, PLUG, "smart_home") == "new"
    session.commit()
    row = session.query(DiscoveredProduct).one()
    assert row.title == PLUG["title"]
    assert row.grade == "BUY"
    assert row.score == 82.0
    assert row.times_seen == 1


def test_saturation_normalized_to_opportunity(session):
    # 0.28 (0-1 scale) -> 28.0 saturation, 72.0 opportunity
    cw.upsert_product(session, PLUG, "smart_home")
    session.commit()
    row = session.query(DiscoveredProduct).one()
    assert row.saturation_score == 28.0
    assert row.opportunity_score == 72.0


def test_resurface_preserves_first_seen_and_bumps_proof(session):
    cw.upsert_product(session, PLUG, "smart_home")
    session.commit()
    first_seen = session.query(DiscoveredProduct).one().first_seen_at

    assert cw.upsert_product(session, PLUG, "smart_home") == "seen"
    session.commit()
    row = session.query(DiscoveredProduct).one()
    assert row.times_seen == 2
    assert row.first_seen_at == first_seen  # proof anchor never resets


def test_dedupe_by_identity_not_row_count(session):
    cw.upsert_product(session, PLUG, "smart_home")
    cw.upsert_product(session, PLUG, "smart_home")  # same product
    cw.upsert_product(session, SINK, "smart_home")  # different
    session.commit()
    assert session.query(DiscoveredProduct).count() == 2


def test_score_filter_excludes_avoid_grade(session):
    for p in (PLUG, SINK):
        cw.upsert_product(session, p, "smart_home")
    session.commit()
    buys = session.query(DiscoveredProduct).filter(DiscoveredProduct.score >= 50).all()
    titles = {r.title for r in buys}
    assert titles == {PLUG["title"]}  # AVOID-grade sink plug excluded


def test_product_key_stable_and_title_sensitive():
    assert cw._product_key(PLUG) == cw._product_key(dict(PLUG))
    assert cw._product_key(PLUG) != cw._product_key(SINK)


# ---------------------------------------------------------------------------
# product_timeseries — the moat (#56 Phase 1)
# ---------------------------------------------------------------------------

FULL_SIGNAL = {
    "title": "Smart Doorbell Camera", "image_url": "http://img/9.jpg",
    "source": "cj_dropshipping", "tier": "GOOD", "final_score": 70.0,
    "saturation_score": 0.30, "sentiment_score": 64, "velocity_phase": "growth",
    "meta_niche_advertiser_count": 8,
    "sales_count": 1200,
    "google_trend_score": 55,
    "data_sources": {"tiktok_shop": {"units_sold_7d": 340, "velocity": 22.5}},
}


def test_snapshot_extracts_named_signals(session):
    assert cw.snapshot_timeseries(session, FULL_SIGNAL, "smart_home") == "inserted"
    session.commit()
    row = session.query(ProductTimeseries).one()
    assert row.meta_advertiser_count == 8
    assert row.aliexpress_orders == 1200
    assert row.google_trends_interest == 55.0
    assert row.tiktok_units_sold == 340
    assert row.tiktok_velocity == 22.5
    assert row.signal_count == 5            # all 5 raw signals fresh
    assert row.grade == "GOOD" and row.velocity_phase == "growth"


def test_snapshot_missing_signals_are_null_not_zero(session):
    # PLUG has none of the raw signals → they must be NULL (confidence gate),
    # never fabricated zeros.
    cw.snapshot_timeseries(session, PLUG, "smart_home")
    session.commit()
    row = session.query(ProductTimeseries).one()
    assert row.meta_advertiser_count is None
    assert row.aliexpress_orders is None
    assert row.google_trends_interest is None
    assert row.signal_count == 0           # thin day → low confidence, not bad product


def test_snapshot_one_row_per_product_per_day(session):
    # Same product, same day, run twice → UPDATE not duplicate.
    assert cw.snapshot_timeseries(session, FULL_SIGNAL, "smart_home") == "inserted"
    session.commit()
    assert cw.snapshot_timeseries(session, FULL_SIGNAL, "smart_home") == "updated"
    session.commit()
    assert session.query(ProductTimeseries).count() == 1


def test_snapshot_distinct_products_distinct_rows(session):
    cw.snapshot_timeseries(session, FULL_SIGNAL, "smart_home")
    cw.snapshot_timeseries(session, PLUG, "smart_home")
    session.commit()
    assert session.query(ProductTimeseries).count() == 2


class TestPerNicheFaultIsolation:
    """Step 0 of the discovery-reliability spec (fail-if-reverted): one niche
    crashing at ANY level must never zero out the whole refresh."""

    def test_crashing_niche_does_not_abort_batch(self, monkeypatch):
        import asyncio

        from ospra_os.tasks import catalog_warm

        monkeypatch.setattr(catalog_warm, "_bootstrap_table", lambda: None)
        monkeypatch.setattr(catalog_warm, "_niches", lambda: ["n1", "n2", "n3"])
        warmed = []

        async def fake_warm(niche):
            if niche == "n2":
                # raised OUTSIDE warm_niche's internal try/except — the level
                # that used to abort the entire batch
                raise RuntimeError("boom in niche 2")
            warmed.append(niche)
            return {"niche": niche, "discovered": 5, "new": 5, "seen": 0,
                    "snapshots": 5, "absences": 0}

        monkeypatch.setattr(catalog_warm, "warm_niche", fake_warm)
        result = asyncio.run(catalog_warm.run())

        assert warmed == ["n1", "n3"]                      # survivors both ran
        assert result["discovered"] == 10                   # their output counted
        by_niche = {r["niche"]: r for r in result["by_niche"]}
        assert "boom in niche 2" in by_niche["n2"]["error"]

    def test_all_niches_failing_still_alerts(self, monkeypatch):
        """M6 semantics preserved: every niche dead → discovered=0 (main exits 2)."""
        import asyncio

        from ospra_os.tasks import catalog_warm

        monkeypatch.setattr(catalog_warm, "_bootstrap_table", lambda: None)
        monkeypatch.setattr(catalog_warm, "_niches", lambda: ["n1", "n2"])

        async def fake_warm(niche):
            raise RuntimeError("all dead")

        monkeypatch.setattr(catalog_warm, "warm_niche", fake_warm)
        result = asyncio.run(catalog_warm.run())
        assert result["discovered"] == 0
