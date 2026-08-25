"""Qualitative read cache — a hit must cost zero LLM calls.

assess_product() ran on the top 10 products of every discovery run with no
cache: ~3,000 grok-3 calls/month from the crons alone, re-deriving identical
answers from identical evidence.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from ospra_os.database.base import Base
from ospra_os.database.qualitative_cache_models import QualitativeReadCache
from ospra_os.intelligence import qualitative_cache as qc

EVIDENCE = {"data_sources_available": ["aliexpress_buyer"], "rating": 4.6}
ASSESSMENT = {
    "polarity": "positive", "themes": ["fast shipping"], "top_wins": ["cheap"],
    "top_objections": [], "data_gaps": [], "recommendation": "BUY",
    "confidence": 72, "provider": "xai", "error": None,
}


@pytest.fixture()
def cache(engine, monkeypatch):
    Base.metadata.create_all(bind=engine, tables=[QualitativeReadCache.__table__])
    monkeypatch.setattr(qc, "_session", lambda: Session(engine))
    with Session(engine) as s:
        s.query(QualitativeReadCache).delete()
        s.commit()
    qc.reset_stats()
    return qc


def test_put_then_get_is_a_hit(cache):
    cache.put("xai:grok-3", "prod-1", EVIDENCE, ASSESSMENT, "xai")
    got = cache.get("xai:grok-3", "prod-1", EVIDENCE)
    assert got is not None and got["recommendation"] == "BUY"
    assert cache.get_stats()["hits"] == 1


def test_changed_evidence_is_a_miss(cache):
    """The key IS the invalidation: new evidence must re-read, automatically."""
    cache.put("xai:grok-3", "prod-1", EVIDENCE, ASSESSMENT, "xai")
    newer = dict(EVIDENCE, rating=3.1)
    assert cache.get("xai:grok-3", "prod-1", newer) is None


def test_different_model_is_a_miss(cache):
    """A grok-3 read must not be served as a grok-4 read."""
    cache.put("xai:grok-3", "prod-1", EVIDENCE, ASSESSMENT, "xai")
    assert cache.get("xai:grok-4", "prod-1", EVIDENCE) is None


def test_failures_are_never_cached(cache):
    """Caching a 401 or a parse failure would freeze an outage for the TTL."""
    cache.put("xai:grok-3", "prod-2", EVIDENCE,
              dict(ASSESSMENT, error="401 Unauthorized"), "xai")
    assert cache.get("xai:grok-3", "prod-2", EVIDENCE) is None


def test_expired_entry_is_a_miss(cache, monkeypatch):
    monkeypatch.setenv("QUAL_CACHE_TTL_HOURS", "168")
    cache.put("xai:grok-3", "prod-3", EVIDENCE, ASSESSMENT, "xai")
    key = cache.cache_key("xai:grok-3", "prod-3", EVIDENCE)
    with Session(engine_of(cache)) as s:
        row = s.query(QualitativeReadCache).filter_by(cache_key=key).one()
        row.fetched_at = datetime.utcnow() - timedelta(hours=200)
        s.commit()
    assert cache.get("xai:grok-3", "prod-3", EVIDENCE) is None


def engine_of(cache):
    """The fixture patched _session to a Session bound to the test engine."""
    return cache._session().get_bind()


def test_eval_bypass_disables_the_cache(cache, monkeypatch):
    """evals/qualitative_source_value.py measures marginal source value by
    ablation — served cached reads would make it silently measure nothing."""
    cache.put("xai:grok-3", "prod-4", EVIDENCE, ASSESSMENT, "xai")
    monkeypatch.setenv("OSPRA_QUAL_CACHE_BYPASS", "1")
    assert cache.get("xai:grok-3", "prod-4", EVIDENCE) is None


def test_db_failure_degrades_to_miss(cache, monkeypatch):
    def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(qc, "_session", boom)
    assert qc.get("xai:grok-3", "prod-1", EVIDENCE) is None  # no exception
    qc.put("xai:grok-3", "prod-1", EVIDENCE, ASSESSMENT, "xai")  # no exception


def test_prune_removes_only_old_rows(cache):
    with Session(engine_of(cache)) as s:
        s.add(QualitativeReadCache(
            cache_key="old", product_key="p", assessment={},
            fetched_at=datetime.utcnow() - timedelta(days=90)))
        s.add(QualitativeReadCache(
            cache_key="new", product_key="p", assessment={},
            fetched_at=datetime.utcnow()))
        s.commit()
    assert cache.prune(older_than_days=30) == 1


@pytest.mark.asyncio
async def test_cache_hit_prevents_the_llm_call(cache, monkeypatch):
    """The whole point: a second identical assess_product must cost 0 API calls."""
    from ospra_os.intelligence import sentiment_qualitative as sq

    calls = []

    class _FakeProvider:
        model_name = "grok-3"

        async def chat(self, message):
            calls.append(1)
            return (
                '{"polarity":"positive","themes":["fast shipping"],'
                '"top_wins":["cheap"],"top_objections":[],"data_gaps":[],'
                '"recommendation":"BUY","confidence":72}'
            )

    monkeypatch.setattr(sq, "_select_provider", lambda: ("xai", _FakeProvider()))
    # aliexpress_signals lives UNDER data_sources — _collect_evidence reads
    # (product["data_sources"] or {}).get("aliexpress_signals"). A top-level
    # key yields no evidence and short-circuits before the cache is reached.
    product = {
        "product_id": "abc-123",
        "title": "Smart Plug",
        "data_sources": {
            "aliexpress_signals": {
                "found_real_rating": True,
                "rating_stars": 4.6,
                "rating_pct": 96,
                "recent_sales": 900,
            }
        },
    }

    first = await sq.assess_product(product)
    second = await sq.assess_product(product)

    assert first.recommendation == second.recommendation == "BUY"
    assert len(calls) == 1, (
        f"expected the second read to be served from cache, got {len(calls)} LLM calls"
    )
