"""
Google Trends pre-warm job (task #47)
=====================================

Runs the slow (~12 min) Apify Google-Trends actor OFF the request path and
upserts results into ``cached_google_trends``, which the web process reads
inline in microseconds. Designed to run as a Render Cron Job every 12h:

    python -m ospra_os.tasks.trend_warm

Requires only DATABASE_URL + APIFY_API_TOKEN (no Redis, no Celery worker).

Term selection per run (capped at TREND_WARM_MAX_TERMS, default 25):
  1. PENDING terms — recorded by the read path on cache miss
     (fetched_at IS NULL), ordered by miss_count DESC. These are the winner
     phrases discovery actually asked for; warming them converges the cache
     on real demand.
  2. STALE terms — fetched > TREND_CACHE_TTL_HOURS ago (default 24h),
     ordered by last_requested_at DESC.
  3. NICHE BASE KEYWORDS — from TREND_WARM_NICHES (default "smart_home,tech"),
     so day-one cold start still has the core vocabulary warm.

Fallback: if the Apify actor fails or APIFY_API_TOKEN is unset, the job
falls back to pytrends (the cron has time to absorb 429 retries; the
request path no longer does).

Self-bootstrapping: creates the table if it doesn't exist, so the cron can
deploy before any migration runs.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger("trend_warm")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Base keywords per niche — intentionally duplicated from
# product_discovery.NICHE_SUBQUERIES rather than imported: that module is a
# 6.8k-line file with heavy transitive imports the cron doesn't need, and
# the cron must boot fast and never fail because a discovery-side import broke.
NICHE_BASE_KEYWORDS: Dict[str, List[str]] = {
    "smart_home": [
        "smart plug", "video doorbell", "smart bulb", "motion sensor",
        "smart lock", "smart camera", "smart switch", "robot vacuum",
    ],
    "tech": [
        "wireless charger", "magsafe accessory", "phone stand",
        "carplay adapter", "usb-c hub", "portable monitor",
        "wireless earbuds", "screen protector",
    ],
    "kitchen": [
        "kitchen gadget", "knife sharpener", "vegetable chopper",
        "spice rack", "electric grinder", "coffee maker",
    ],
    "fitness": [
        "resistance band", "foam roller", "massage gun",
        "posture corrector", "yoga mat", "jump rope",
    ],
    "pet": [
        "pet water fountain", "interactive cat toy", "no-pull harness",
        "automatic feeder", "pet camera", "pet hair remover",
    ],
    "home_decor": [
        "led wall light", "sunset projector", "smart led strip",
        "ambient lamp", "wall art print",
    ],
    "car": [
        "magsafe car mount", "wireless carplay", "dash camera",
        "car vacuum", "tire inflator",
    ],
}

TREND_CACHE_TTL_HOURS = int(os.getenv("TREND_CACHE_TTL_HOURS", "24"))
MAX_TERMS_PER_RUN = int(os.getenv("TREND_WARM_MAX_TERMS", "25"))


def _get_session():
    from ospra_os.database.connection import SessionLocal
    return SessionLocal()


def _bootstrap_table() -> None:
    """Create cached_google_trends if missing — idempotent."""
    from ospra_os.database.base import Base
    from ospra_os.database.connection import engine
    from ospra_os.database.trend_cache_models import CachedGoogleTrend

    Base.metadata.create_all(bind=engine, tables=[CachedGoogleTrend.__table__])


def collect_terms() -> List[str]:
    """Pick the terms to warm this run (see module docstring for priority)."""
    from ospra_os.database.trend_cache_models import CachedGoogleTrend

    session = _get_session()
    try:
        terms: List[str] = []
        seen: set = set()

        # 1. Pending (requested by read path, never fetched), hottest first.
        pending = (
            session.query(CachedGoogleTrend)
            .filter(CachedGoogleTrend.fetched_at.is_(None))
            .order_by(CachedGoogleTrend.miss_count.desc())
            .limit(MAX_TERMS_PER_RUN)
            .all()
        )
        for row in pending:
            if row.term not in seen:
                seen.add(row.term)
                terms.append(row.term)

        # 2. Stale, most-recently-requested first.
        cutoff = datetime.utcnow() - timedelta(hours=TREND_CACHE_TTL_HOURS)
        stale = (
            session.query(CachedGoogleTrend)
            .filter(CachedGoogleTrend.fetched_at.isnot(None))
            .filter(CachedGoogleTrend.fetched_at < cutoff)
            .order_by(CachedGoogleTrend.last_requested_at.desc().nullslast())
            .limit(MAX_TERMS_PER_RUN)
            .all()
        )
        for row in stale:
            if len(terms) >= MAX_TERMS_PER_RUN:
                break
            if row.term not in seen:
                seen.add(row.term)
                terms.append(row.term)

        # 3. Niche base keywords (cold-start coverage).
        niches = [n.strip() for n in os.getenv("TREND_WARM_NICHES", "smart_home,tech").split(",") if n.strip()]
        for niche in niches:
            for kw in NICHE_BASE_KEYWORDS.get(niche, []):
                if len(terms) >= MAX_TERMS_PER_RUN:
                    break
                kw = kw.lower()
                if kw not in seen:
                    # Only re-warm base keywords when missing or stale.
                    row = session.query(CachedGoogleTrend).filter_by(term=kw).first()
                    if row is None or row.fetched_at is None or row.fetched_at < cutoff:
                        seen.add(kw)
                        terms.append(kw)

        return terms[:MAX_TERMS_PER_RUN]
    finally:
        session.close()


def upsert_result(term: str, interest: int, direction: str, momentum: float,
                  source: str, related_queries: Optional[list] = None) -> None:
    from ospra_os.database.trend_cache_models import CachedGoogleTrend

    session = _get_session()
    try:
        row = session.query(CachedGoogleTrend).filter_by(term=term.lower()).first()
        if row is None:
            row = CachedGoogleTrend(term=term.lower())
            session.add(row)
        row.interest = int(interest)
        row.direction = direction
        row.momentum = float(momentum)
        row.source = source
        row.related_queries = related_queries or None
        row.fetched_at = datetime.utcnow()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def warm_via_apify(terms: List[str]) -> List[str]:
    """Warm terms via the Apify actor. Returns the terms successfully warmed."""
    from ospra_os.product_research.connectors.apify.google_trends_apify import ApifyGoogleTrends

    client = ApifyGoogleTrends()
    results = await client.get_interest(search_terms=terms, geo="US", timeframe="today 3-m")

    warmed: List[str] = []
    for td in results or []:
        direction = "rising" if td.velocity > 10 else "falling" if td.velocity < -10 else "stable"
        rqs = [
            {"query": rq.get("query"), "value": rq.get("value"), "rank": rq.get("rank")}
            for rq in (getattr(td, "related_queries", None) or [])
            if isinstance(rq, dict) and rq.get("query")
        ][:10] or None
        upsert_result(td.search_term, td.current_interest, direction, td.velocity, "apify", rqs)
        warmed.append(td.search_term.lower())
        logger.info(f"warmed (apify): {td.search_term!r} interest={td.current_interest} dir={direction}")
    return warmed


async def warm_via_pytrends(terms: List[str]) -> List[str]:
    """Fallback warm via pytrends — the cron can absorb 429 retries."""
    from ospra_os.intelligence.trend_analyzer import TrendAnalyzer

    analyzer = TrendAnalyzer.__new__(TrendAnalyzer)  # skip full __init__ (AI clients etc.)
    analyzer.apify_trends = None
    analyzer.pytrends = None
    try:
        from ospra_os.intelligence.trend_analyzer import (
            HAS_PYTRENDS, _patch_urllib3_for_pytrends,
        )
        if HAS_PYTRENDS:
            from pytrends.request import TrendReq
            _patch_urllib3_for_pytrends()
            analyzer.pytrends = TrendReq(hl="en-US", tz=360, retries=3, backoff_factor=1.0)
    except Exception as e:
        logger.warning(f"pytrends unavailable for fallback warm: {e}")
        return []

    if not analyzer.pytrends:
        return []

    result = await analyzer.get_trend_interest(terms)
    warmed: List[str] = []
    for term, data in result.items():
        if data.get("available"):
            upsert_result(term, data["interest"], data["direction"], data["momentum"], "pytrends")
            warmed.append(term)
            logger.info(f"warmed (pytrends): {term!r} interest={data['interest']}")
    return warmed


async def run() -> int:
    _bootstrap_table()
    terms = collect_terms()
    if not terms:
        logger.info("Nothing to warm — cache is fresh.")
        return 0
    logger.info(f"Warming {len(terms)} terms: {terms}")

    warmed: List[str] = []
    if os.getenv("APIFY_API_TOKEN"):
        try:
            warmed = await warm_via_apify(terms)
        except Exception as e:
            logger.error(f"Apify warm failed ({e}); falling back to pytrends.")
    else:
        logger.warning("APIFY_API_TOKEN not set — using pytrends fallback only.")

    missed = [t for t in terms if t.lower() not in set(warmed)]
    if missed:
        warmed += await warm_via_pytrends(missed)

    logger.info(f"Warm complete: {len(warmed)}/{len(terms)} terms warmed.")
    # Non-zero exit only if we warmed NOTHING while having terms to warm —
    # lets Render surface a genuinely broken cron without flapping on
    # partial passes.
    return 0 if warmed else 1


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
