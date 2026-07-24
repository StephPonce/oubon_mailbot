"""
Discovery-reliability step 1 (fail-if-reverted): /catalog must report when
its data was last written, so the UI can stop presenting June as now.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-freshness")


@pytest.fixture
def catalog_db(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from ospra_os.database.base import Base
    from ospra_os.database.discovered_catalog import DiscoveredProduct

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[DiscoveredProduct.__table__])
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        "ospra_os.database.connection.SessionLocal", factory, raising=False
    )

    def seed(niche, title, last_seen_days_ago):
        s = factory()
        now = datetime.utcnow()
        seen = now - timedelta(days=last_seen_days_ago)
        s.add(DiscoveredProduct(
            product_key=f"k-{niche}-{title}"[:64], niche=niche, title=title,
            score=50.0, first_seen_at=seen, last_seen_at=seen, times_seen=1,
            created_at=seen, payload={"title": title},
        ))
        s.commit()
        s.close()

    return seed


async def _get_catalog(**kw):
    from ospra_os.intelligence.unified_discovery_routes import get_catalog
    return await get_catalog(
        niche=kw.get("niche"), min_score=0, phase=None,
        max_saturation=None, sort="score", limit=60,
    )


class TestCatalogFreshness:
    @pytest.mark.asyncio
    async def test_freshness_is_newest_write_for_the_niche(self, catalog_db):
        catalog_db("smart_home", "Old Product", last_seen_days_ago=16)
        catalog_db("smart_home", "Newer Product", last_seen_days_ago=3)
        catalog_db("kitchen", "Fresh Elsewhere", last_seen_days_ago=0)

        res = await _get_catalog(niche="smart_home")
        assert res["success"] is True
        assert res["catalog_freshness"] is not None
        # niche-scoped: kitchen's fresh write must not mask smart_home's staleness
        assert res["catalog_freshness_hours"] == pytest.approx(3 * 24, abs=1.5)

    @pytest.mark.asyncio
    async def test_stale_catalog_crosses_banner_threshold(self, catalog_db):
        """The June incident fixture: 16-day-old data must read as stale
        (>48h — the frontend banner threshold)."""
        catalog_db("smart_home", "June Product", last_seen_days_ago=16)
        res = await _get_catalog(niche="smart_home")
        assert res["catalog_freshness_hours"] > 48

    @pytest.mark.asyncio
    async def test_fresh_catalog_stays_under_threshold(self, catalog_db):
        catalog_db("smart_home", "Today Product", last_seen_days_ago=0)
        res = await _get_catalog(niche="smart_home")
        assert res["catalog_freshness_hours"] < 48

    @pytest.mark.asyncio
    async def test_empty_catalog_reports_null_freshness(self, catalog_db):
        res = await _get_catalog(niche="ghost_niche")
        assert res["catalog_freshness"] is None
        assert res["catalog_freshness_hours"] is None


class TestCatalogTitleDedupe:
    """AE sellers double-list the same product under different supplier ids —
    distinct identity keys, identical titles (live: 4 dupe titles in tech's
    top 10). The read path must serve each title once, best row first."""

    @pytest.mark.asyncio
    async def test_duplicate_titles_served_once_best_score_wins(self, catalog_db, monkeypatch):
        from ospra_os.database.discovered_catalog import DiscoveredProduct
        import ospra_os.database.connection as conn

        s = conn.SessionLocal()
        for key, title, score in (
            ("k-dupe-1", "TWS Wireless Earphones", 80.0),
            ("k-dupe-2", "TWS Wireless Earphones", 40.0),   # same title, other seller
            ("k-dupe-3", "tws wireless earphones", 30.0),   # case variant
            ("k-uniq-1", "Magnetic Watch Charger", 60.0),
        ):
            s.add(DiscoveredProduct(
                product_key=key, niche="tech", title=title, score=score,
                payload={"title": title},
            ))
        s.commit()
        s.close()

        res = await _get_catalog(niche="tech")
        titles = [(p.get("title") or "").lower() for p in res["products"]]
        assert titles.count("tws wireless earphones") == 1
        assert len(res["products"]) == 2
        # Best-scored copy is the survivor (default sort is score desc).
        kept = next(p for p in res["products"] if (p.get("title") or "").lower() == "tws wireless earphones")
        assert kept["catalog_score"] == 80.0
