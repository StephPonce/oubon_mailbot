"""AliExpress DS detail cache — persistence across processes, and stale-serve.

ds_client's in-process dict is empty on every cron run (fresh process), so the
place with all the volume never had a cache. Beyond the wasted calls, a slow
call cancels the whole serial enrich_pricing loop and every product silently
falls back to the inflated heuristic cost basis.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from ospra_os.aliexpress import ds_detail_cache as dc
from ospra_os.database.ae_ds_cache_models import AEDSDetailCache
from ospra_os.database.base import Base

DETAIL = {"product_id": "1005001", "sku_price": 7.42, "commission_rate": 8.0}


@pytest.fixture()
def cache(engine, monkeypatch):
    Base.metadata.create_all(bind=engine, tables=[AEDSDetailCache.__table__])
    monkeypatch.setattr(dc, "_session", lambda: Session(engine))
    with Session(engine) as s:
        s.query(AEDSDetailCache).delete()
        s.commit()
    return dc


def _age(engine, key, hours):
    with Session(engine) as s:
        row = s.query(AEDSDetailCache).filter_by(cache_key=key).one()
        row.fetched_at = datetime.utcnow() - timedelta(hours=hours)
        s.commit()


def test_put_then_get(cache):
    cache.put("1005001", "US", "USD", "EN", DETAIL)
    assert cache.get("1005001", "US", "USD", "EN") == DETAIL


def test_key_includes_country_and_currency(cache):
    """Merchant price is ship-to- and currency-dependent — a US/USD answer
    must not be served for a DE/EUR question."""
    cache.put("1005001", "US", "USD", "EN", DETAIL)
    assert cache.get("1005001", "DE", "EUR", "EN") is None


def test_expired_is_a_miss_but_stale_serves(cache, engine, monkeypatch):
    monkeypatch.setenv("AE_DS_DETAIL_TTL_HOURS", "24")
    cache.put("1005001", "US", "USD", "EN", DETAIL)
    _age(engine, cache.cache_key("1005001", "US", "USD", "EN"), hours=48)

    assert cache.get("1005001", "US", "USD", "EN") is None
    stale = cache.get("1005001", "US", "USD", "EN", allow_stale=True)
    assert stale == DETAIL, (
        "an expired real merchant price beats reverting to the heuristic "
        "cost basis the code itself calls 'too generous'"
    )


def test_db_failure_degrades_to_miss(cache, monkeypatch):
    def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(dc, "_session", boom)
    assert dc.get("1005001", "US", "USD", "EN") is None   # no exception
    dc.put("1005001", "US", "USD", "EN", DETAIL)          # no exception


def test_disabled_by_env(cache, monkeypatch):
    monkeypatch.setenv("AE_DS_CACHE_ENABLED", "false")
    cache.put("2", "US", "USD", "EN", DETAIL)
    assert cache.get("2", "US", "USD", "EN") is None


def test_prune_removes_only_old_rows(cache, engine):
    with Session(engine) as s:
        s.add(AEDSDetailCache(cache_key="old", product_id="p", detail={},
                              fetched_at=datetime.utcnow() - timedelta(days=90)))
        s.add(AEDSDetailCache(cache_key="new", product_id="p", detail={},
                              fetched_at=datetime.utcnow()))
        s.commit()
    assert cache.prune(older_than_days=14) == 1
