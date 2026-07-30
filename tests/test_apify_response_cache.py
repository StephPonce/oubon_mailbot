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


def test_unserialisable_run_input_degrades_to_no_cache(engine):
    """A run_input json.dumps can't handle must bypass the cache, never raise —
    the cache may not cause the outage it exists to prevent."""
    rc = _fresh_cache(engine)
    circular = {}
    circular["self"] = circular

    assert rc.get("acme/actor", circular, None) is None
    rc.put("acme/actor", circular, None, [{"a": 1}])  # must not raise


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


# ---------------------------------------------------------------------------
# run_actor integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_actor_second_call_hits_cache(engine, monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    from ospra_os.product_research.connectors.apify.base_apify import (
        ApifyClient, reset_apify_budget,
    )

    reset_apify_budget()
    client = ApifyClient(api_token="test-token")
    calls = []

    async def fake_live(actor_id, run_input, timeout_secs, memory_mbytes, max_items):
        calls.append(actor_id)
        return [{"ad": "one"}], True

    monkeypatch.setattr(client, "_run_actor_live", fake_live)

    first = await client.run_actor("acme/actor", {"q": "smart plug"})
    second = await client.run_actor("acme/actor", {"q": "smart plug"})

    assert first == [{"ad": "one"}] and second == [{"ad": "one"}]
    assert len(calls) == 1, "second call must be served from cache"
    assert rc.get_cache_stats()["cache_hits"] == 1


@pytest.mark.asyncio
async def test_run_actor_serves_stale_when_live_fails(engine, monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    from ospra_os.product_research.connectors.apify.base_apify import (
        ApifyClient, reset_apify_budget,
    )

    reset_apify_budget()
    rc.put("acme/actor", {"q": "quota"}, None, [{"ad": "old"}])
    _age_row(engine, rc.cache_key("acme/actor", {"q": "quota"}, None), hours=200)

    client = ApifyClient(api_token="test-token")

    async def failing_live(actor_id, run_input, timeout_secs, memory_mbytes, max_items):
        return [], False  # e.g. quota 403

    monkeypatch.setattr(client, "_run_actor_live", failing_live)

    items = await client.run_actor("acme/actor", {"q": "quota"})
    assert items and items[0]["ad"] == "old"
    assert items[0][rc.CACHE_MARKER]["stale"] is True


@pytest.mark.asyncio
async def test_successful_empty_result_is_not_replaced_by_stale(engine, monkeypatch):
    """An actor that SUCCEEDS with no rows is a real answer, not a failure."""
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    _fresh_cache(engine)
    from ospra_os.product_research.connectors.apify.base_apify import (
        ApifyClient, reset_apify_budget,
    )

    reset_apify_budget()
    client = ApifyClient(api_token="test-token")

    async def empty_ok(actor_id, run_input, timeout_secs, memory_mbytes, max_items):
        return [], True

    monkeypatch.setattr(client, "_run_actor_live", empty_ok)
    assert await client.run_actor("acme/actor", {"q": "nothing"}) == []


@pytest.mark.asyncio
async def test_tripped_breaker_serves_stale_instead_of_empty(engine, monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    rc = _fresh_cache(engine)
    from ospra_os.product_research.connectors.apify import base_apify

    base_apify.reset_apify_budget()
    rc.put("acme/actor", {"q": "tripped"}, None, [{"ad": "cached"}])
    _age_row(engine, rc.cache_key("acme/actor", {"q": "tripped"}, None), hours=500)

    base_apify._record_apify_quota_fail("acme/actor")
    base_apify._record_apify_quota_fail("acme/actor")
    assert base_apify.apify_actor_tripped("acme/actor")

    client = base_apify.ApifyClient(api_token="test-token")
    items = await client.run_actor("acme/actor", {"q": "tripped"})
    assert items and items[0]["ad"] == "cached"
    assert items[0][rc.CACHE_MARKER]["stale"] is True
    base_apify.reset_apify_budget()


def test_saturation_halves_weight_for_stale_meta():
    """A stale Meta reading still describes the market — it just describes last
    week's. Half weight keeps the score and lands confidence between
    fresh-signal and no-signal."""
    from ospra_os.intelligence.product_discovery import _compute_saturation

    fresh = _compute_saturation({"meta_niche_advertiser_count": 10})
    stale = _compute_saturation(
        {"meta_niche_advertiser_count": 10, "meta_niche_stale": True}
    )
    none_ = _compute_saturation({})

    assert stale["score"] == fresh["score"]
    assert none_["confidence"] < stale["confidence"] < fresh["confidence"]
    assert stale["confidence"] == pytest.approx(0.125)
    assert fresh["confidence"] == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_meta_connector_propagates_stale_flag(monkeypatch):
    from ospra_os.product_research.connectors.apify.meta_ads_library import (
        MetaAdsLibraryApify,
    )
    from ospra_os.product_research.connectors.apify.response_cache import CACHE_MARKER

    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    scraper = MetaAdsLibraryApify(api_token="test-token")

    stale_raw = {
        "ad_archive_id": "1", "page_id": "p1", "page_name": "Acme",
        "body": "buy now",
        CACHE_MARKER: {"stale": True, "fetched_at": "2026-07-01T00:00:00"},
    }

    async def fake_run_actor(**kwargs):
        return [stale_raw]

    monkeypatch.setattr(scraper.client, "run_actor", fake_run_actor)
    result = await scraper.search_active_ads(keyword="smart plug")
    assert result["available"] is True
    assert result["stale"] is True


@pytest.mark.asyncio
async def test_meta_connector_fresh_payload_is_not_stale(monkeypatch):
    from ospra_os.product_research.connectors.apify.meta_ads_library import (
        MetaAdsLibraryApify,
    )

    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    scraper = MetaAdsLibraryApify(api_token="test-token")

    async def fake_run_actor(**kwargs):
        return [{
            "ad_archive_id": "2", "page_id": "p2", "page_name": "Beta",
            "body": "shop today",
        }]

    monkeypatch.setattr(scraper.client, "run_actor", fake_run_actor)
    result = await scraper.search_active_ads(keyword="smart plug")
    assert result["available"] is True
    assert result["stale"] is False


def test_budget_report_includes_cache_counters():
    from ospra_os.product_research.connectors.apify.base_apify import (
        get_apify_budget_report, reset_apify_budget,
    )

    reset_apify_budget()
    report = get_apify_budget_report()
    for field in ("cache_hits", "cache_misses", "stale_served"):
        assert field in report
