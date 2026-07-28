"""Apify response cache — key stability, TTL policy, stale-serve, failure isolation.

Guards the #57 follow-up: catalog_warm re-asked ~25 DISTINCT Meta sub-queries
~60x/month because nothing survived the cron process, burning the $45 Apify cap
three weeks into a four-week cycle.
"""

from datetime import datetime, timedelta

import pytest


def test_model_roundtrips(engine):
    from sqlalchemy.orm import Session

    from ospra_os.database.apify_cache_models import ApifyResponseCache
    from ospra_os.database.base import Base

    Base.metadata.create_all(bind=engine, tables=[ApifyResponseCache.__table__])
    with Session(engine) as s:
        s.query(ApifyResponseCache).delete()
        s.add(ApifyResponseCache(
            cache_key="k1", actor_id="acme/actor", run_input_summary="{}",
            items=[{"a": 1}], item_count=1, fetched_at=datetime.utcnow(),
        ))
        s.commit()
        row = s.query(ApifyResponseCache).filter_by(cache_key="k1").one()
        assert row.items == [{"a": 1}]
        assert row.item_count == 1
        assert row.hit_count == 0


def _fresh_cache(engine):
    """Create the table, clear it, and hand back the module with counters reset."""
    from sqlalchemy.orm import Session

    from ospra_os.database.apify_cache_models import ApifyResponseCache
    from ospra_os.database.base import Base
    from ospra_os.product_research.connectors.apify import response_cache as rc

    Base.metadata.create_all(bind=engine, tables=[ApifyResponseCache.__table__])
    with Session(engine) as s:
        s.query(ApifyResponseCache).delete()
        s.commit()
    rc.reset_cache_stats()
    return rc


def _age_row(engine, key: str, hours: float) -> None:
    from sqlalchemy.orm import Session

    from ospra_os.database.apify_cache_models import ApifyResponseCache

    with Session(engine) as s:
        row = s.query(ApifyResponseCache).filter_by(cache_key=key).one()
        row.fetched_at = datetime.utcnow() - timedelta(hours=hours)
        s.commit()


def test_key_ignores_dict_ordering(engine):
    rc = _fresh_cache(engine)
    assert rc.cache_key("acme/actor", {"b": 2, "a": 1}, None) == rc.cache_key(
        "acme/actor", {"a": 1, "b": 2}, None
    )


def test_key_separates_max_items(engine):
    rc = _fresh_cache(engine)
    assert rc.cache_key("acme/actor", {"a": 1}, 25) != rc.cache_key("acme/actor", {"a": 1}, 100)


def test_put_then_get_is_a_hit(engine, monkeypatch):
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    rc.put("acme/actor", {"q": "smart plug"}, None, [{"ad": 1}])
    hit = rc.get("acme/actor", {"q": "smart plug"}, None)
    assert hit is not None
    assert hit.items == [{"ad": 1}]
    assert hit.is_stale is False
    assert rc.get_cache_stats()["cache_hits"] == 1


def test_expired_entry_is_a_miss_but_stale_serves(engine, monkeypatch):
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    rc.put("acme/actor", {"q": "old"}, None, [{"ad": 2}])
    _age_row(engine, rc.cache_key("acme/actor", {"q": "old"}, None), hours=48)

    assert rc.get("acme/actor", {"q": "old"}, None) is None
    stale = rc.get("acme/actor", {"q": "old"}, None, allow_stale=True)
    assert stale is not None and stale.is_stale is True
    assert rc.get_cache_stats()["stale_served"] == 1


def test_trends_actor_is_bypassed(engine):
    rc = _fresh_cache(engine)
    trends = "apify/google-trends-scraper"
    assert rc.ttl_for(trends) is None
    rc.put(trends, {"q": "led mask"}, None, [{"t": 1}])
    assert rc.get(trends, {"q": "led mask"}, None) is None


def test_empty_result_uses_short_ttl(engine, monkeypatch):
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_EMPTY", "6")
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    assert rc.ttl_for("acme/actor", empty=True).total_seconds() == 6 * 3600
    assert rc.ttl_for("acme/actor", empty=False).total_seconds() == 24 * 3600


def test_empty_result_expires_on_the_short_ttl(engine, monkeypatch):
    """An empty answer is cached (stop re-asking a dead keyword) but must go
    stale fast, so one bad actor run can't blank a term for days."""
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_EMPTY", "6")
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    rc.put("acme/actor", {"q": "dead"}, None, [])
    key = rc.cache_key("acme/actor", {"q": "dead"}, None)

    _age_row(engine, key, hours=2)
    assert rc.get("acme/actor", {"q": "dead"}, None) is not None, "2h < 6h empty TTL"

    _age_row(engine, key, hours=8)
    assert rc.get("acme/actor", {"q": "dead"}, None) is None, "8h > 6h empty TTL"


def test_oversized_response_not_cached(engine, monkeypatch):
    monkeypatch.setenv("APIFY_CACHE_MAX_BYTES", "100")
    rc = _fresh_cache(engine)
    rc.put("acme/actor", {"q": "big"}, None, [{"blob": "x" * 500}])
    assert rc.get("acme/actor", {"q": "big"}, None) is None


def test_db_failure_is_swallowed(engine, monkeypatch):
    rc = _fresh_cache(engine)

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(rc, "_session", boom)
    assert rc.get("acme/actor", {"q": "x"}, None) is None
    rc.put("acme/actor", {"q": "x"}, None, [{"a": 1}])


def test_disabled_by_env(engine, monkeypatch):
    monkeypatch.setenv("APIFY_CACHE_ENABLED", "false")
    rc = _fresh_cache(engine)
    rc.put("acme/actor", {"q": "off"}, None, [{"a": 1}])
    assert rc.get("acme/actor", {"q": "off"}, None) is None


def test_stamp_stale_marks_copies(engine):
    rc = _fresh_cache(engine)
    original = [{"ad": 1}]
    stamped = rc.stamp_stale(original, datetime(2026, 7, 1, 12, 0, 0))
    assert stamped[0][rc.CACHE_MARKER]["stale"] is True
    assert "2026-07-01" in stamped[0][rc.CACHE_MARKER]["fetched_at"]
    assert rc.CACHE_MARKER not in original[0], "must not mutate the cached list"


def test_prune_deletes_only_old_rows(engine):
    from sqlalchemy.orm import Session

    from ospra_os.database.apify_cache_models import ApifyResponseCache

    rc = _fresh_cache(engine)
    with Session(engine) as s:
        s.add(ApifyResponseCache(
            cache_key="old", actor_id="a", items=[], item_count=0,
            fetched_at=datetime.utcnow() - timedelta(days=90),
        ))
        s.add(ApifyResponseCache(
            cache_key="new", actor_id="a", items=[], item_count=0,
            fetched_at=datetime.utcnow(),
        ))
        s.commit()

    assert rc.prune(older_than_days=30) == 1
    with Session(engine) as s:
        assert [r.cache_key for r in s.query(ApifyResponseCache).all()] == ["new"]
