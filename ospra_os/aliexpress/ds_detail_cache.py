"""
Persistent AliExpress DS product-detail cache.

The in-process dict in ds_client is per-PROCESS, and catalog_warm runs as a
fresh process per cron invocation — so in the place with all the volume it
started empty every time: ~10 detail calls x 300 niche-runs = ~3,000 calls a
month at a ~100% miss rate.

The wasted calls are the smaller problem. `enrich_pricing` is a SERIAL loop of
awaits paced at 0.25s with a 15s per-request timeout, wrapped in a 30s
SENTIMENT_SOURCE_TIMEOUT. Two slow calls and the whole enrichment is cancelled
— every product then keeps the heuristic cost basis that the code itself
describes as "too generous", and no error surfaces. Fewer live calls means the
loop finishes.

Same rules as the other caches here: keyed on the question, failures degrade to
a miss, never raises into the caller.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def cache_enabled() -> bool:
    return os.getenv("AE_DS_CACHE_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


def _ttl() -> timedelta:
    # 24h collapses the two daily cron runs onto one fetch per product before
    # any day-over-day reuse. Merchant prices move, but not within a day.
    return timedelta(hours=float(os.getenv("AE_DS_DETAIL_TTL_HOURS", "24")))


def _session():
    """Indirection so tests can patch the session factory."""
    from ospra_os.database.connection import SessionLocal
    return SessionLocal()


def cache_key(product_id: str, country: str, currency: str, language: str) -> str:
    """All four arguments change the answer: merchant price is ship-to- and
    currency-dependent, so they all belong in the key."""
    payload = json.dumps(
        {"v": 1, "product_id": str(product_id), "country": country,
         "currency": currency, "language": language},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get(
    product_id: str,
    country: str = "US",
    currency: str = "USD",
    language: str = "EN",
    *,
    allow_stale: bool = False,
) -> Optional[Dict[str, Any]]:
    """Fresh read by default; allow_stale ignores age (the outage path)."""
    if not cache_enabled():
        return None
    try:
        session = _session()
    except Exception as exc:
        logger.warning("[AE-DS CACHE] session unavailable (%s) — miss", exc)
        return None

    try:
        from ospra_os.database.ae_ds_cache_models import AEDSDetailCache

        key = cache_key(product_id, country, currency, language)
        row = session.query(AEDSDetailCache).filter_by(cache_key=key).first()
        if row is None:
            return None

        detail = row.detail if isinstance(row.detail, dict) else None
        if detail is None:
            return None

        fresh = (datetime.utcnow() - row.fetched_at) < _ttl()
        if fresh or allow_stale:
            row.hit_count = (row.hit_count or 0) + 1
            row.last_hit_at = datetime.utcnow()
            session.commit()
            return detail
        return None
    except Exception as exc:
        logger.warning("[AE-DS CACHE] read failed (%s) — miss", exc)
        return None
    finally:
        try:
            session.close()
        except Exception:
            pass


def put(
    product_id: str,
    country: str,
    currency: str,
    language: str,
    detail: Dict[str, Any],
) -> None:
    """Upsert a normalised detail dict. Never raises."""
    if not cache_enabled() or not isinstance(detail, dict) or not detail:
        return
    try:
        session = _session()
    except Exception:
        return

    try:
        from ospra_os.database.ae_ds_cache_models import AEDSDetailCache

        key = cache_key(product_id, country, currency, language)
        now = datetime.utcnow()
        row = session.query(AEDSDetailCache).filter_by(cache_key=key).first()
        if row is None:
            session.add(AEDSDetailCache(
                cache_key=key, product_id=str(product_id)[:64],
                country=country, currency=currency,
                detail=detail, fetched_at=now, created_at=now,
            ))
        else:
            row.detail = detail
            row.fetched_at = now
        session.commit()
    except Exception as exc:
        try:
            session.rollback()
        except Exception:
            pass
        logger.warning("[AE-DS CACHE] write failed (%s) — continuing", exc)
    finally:
        try:
            session.close()
        except Exception:
            pass


def prune(older_than_days: Optional[int] = None) -> int:
    days = older_than_days if older_than_days is not None else int(
        os.getenv("AE_DS_CACHE_PRUNE_DAYS", "14")
    )
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        session = _session()
    except Exception:
        return 0
    try:
        from ospra_os.database.ae_ds_cache_models import AEDSDetailCache

        deleted = (
            session.query(AEDSDetailCache)
            .filter(AEDSDetailCache.fetched_at < cutoff)
            .delete(synchronize_session=False)
        )
        session.commit()
        return int(deleted or 0)
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            session.close()
        except Exception:
            pass
