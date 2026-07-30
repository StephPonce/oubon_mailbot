"""
Apify response cache — persist actor responses across processes.

Why this exists: catalog_warm re-asked ~25 DISTINCT Meta sub-queries ~60x/month
(5 niches x 5 sub-queries x 2 runs/day) because nothing survived the cron
process. That burned the $45 Apify cap three weeks into a four-week cycle, and
the cap blackout then blanked the winner-proof signal entirely.

Design rules:
  * Cache is keyed on the QUESTION (actor + canonical input + max_items), not on
    run options (memory/timeout), which do not change the answer.
  * The cache must NEVER cause the outage it prevents: every failure logs and
    returns as if the cache were empty.
  * Google Trends is BYPASSED (TTL 0). trend_warm's whole job is to fetch fresh
    trends; caching that actor would feed the warm job its own previous answer
    forever. Term-level caching already lives in `cached_google_trends`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_MARKER = "_ospra_cache"

# Per-run counters, surfaced through get_apify_budget_report().
_stats = {"cache_hits": 0, "cache_misses": 0, "stale_served": 0}


@dataclass(frozen=True)
class CacheHit:
    items: List[Dict]
    fetched_at: datetime
    is_stale: bool


def reset_cache_stats() -> None:
    _stats.update({"cache_hits": 0, "cache_misses": 0, "stale_served": 0})


def get_cache_stats() -> Dict[str, int]:
    return dict(_stats)


def _env_flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes"}


def cache_enabled() -> bool:
    return _env_flag("APIFY_CACHE_ENABLED", "true")


def _session():
    """Indirection so tests can patch the session factory."""
    from ospra_os.database.connection import SessionLocal
    return SessionLocal()


def cache_key(actor_id: str, run_input: Dict, max_items: Optional[int]) -> str:
    """SHA-256 over the QUESTION.

    sort_keys so dict ordering can't produce two keys for one question;
    max_items included because a 25-item answer is not interchangeable with a
    100-item one. timeout/memory deliberately excluded — provisioning knobs
    don't change the answer, and including them would fragment the cache.
    """
    payload = json.dumps(
        {"actor": actor_id, "input": run_input, "max_items": max_items},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_cache_key(
    actor_id: str, run_input: Dict, max_items: Optional[int]
) -> Optional[str]:
    """cache_key() but never raises. A run_input that can't be serialised (a
    circular reference, say) must degrade to "no cache", not take down the
    actor call that the cache exists to protect."""
    try:
        return cache_key(actor_id, run_input, max_items)
    except Exception as exc:
        logger.warning("[APIFY CACHE] un-keyable run_input (%s) — bypassing cache", exc)
        return None


def ttl_for(actor_id: str, *, empty: bool = False) -> Optional[timedelta]:
    """Per-actor TTL, env-overridable. None means bypass (never cache)."""
    trends_actor = os.getenv("APIFY_GOOGLE_TRENDS_ACTOR", "apify/google-trends-scraper")
    if actor_id == trends_actor:
        # BYPASS ON PURPOSE — see module docstring. trend_warm exists to fetch
        # fresh trends; caching here would freeze it on its own last answer.
        return None

    if empty:
        return timedelta(hours=float(os.getenv("APIFY_CACHE_TTL_HOURS_EMPTY", "6")))

    meta_actor = os.getenv(
        "APIFY_META_ADS_LIBRARY_ACTOR", "curious_coder/facebook-ads-library-scraper"
    )
    if actor_id == meta_actor:
        return timedelta(hours=float(os.getenv("APIFY_CACHE_TTL_HOURS_META", "72")))

    return timedelta(hours=float(os.getenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")))


def get(
    actor_id: str,
    run_input: Dict,
    max_items: Optional[int],
    *,
    allow_stale: bool = False,
) -> Optional[CacheHit]:
    """Fresh read by default; allow_stale=True ignores age (the outage path)."""
    if not cache_enabled() or ttl_for(actor_id) is None:
        return None

    key = _safe_cache_key(actor_id, run_input, max_items)
    if key is None:
        return None
    try:
        session = _session()
    except Exception as exc:
        logger.warning("[APIFY CACHE] session unavailable (%s) — treating as miss", exc)
        return None

    try:
        from ospra_os.database.apify_cache_models import ApifyResponseCache

        row = session.query(ApifyResponseCache).filter_by(cache_key=key).first()
        if row is None:
            _stats["cache_misses"] += 1
            return None

        items = row.items if isinstance(row.items, list) else []
        ttl = ttl_for(actor_id, empty=(row.item_count == 0))
        age = datetime.utcnow() - row.fetched_at
        fresh = ttl is not None and age < ttl

        if fresh:
            row.hit_count = (row.hit_count or 0) + 1
            row.last_hit_at = datetime.utcnow()
            fetched_at = row.fetched_at
            session.commit()
            _stats["cache_hits"] += 1
            return CacheHit(items=items, fetched_at=fetched_at, is_stale=False)

        if allow_stale:
            _stats["stale_served"] += 1
            logger.warning(
                "[APIFY CACHE] serving STALE %s (age %.1fh) — live call unavailable",
                actor_id, age.total_seconds() / 3600.0,
            )
            return CacheHit(items=items, fetched_at=row.fetched_at, is_stale=True)

        _stats["cache_misses"] += 1
        return None
    except Exception as exc:
        logger.warning("[APIFY CACHE] read failed (%s) — treating as miss", exc)
        return None
    finally:
        try:
            session.close()
        except Exception:
            pass


def put(
    actor_id: str, run_input: Dict, max_items: Optional[int], items: List[Dict]
) -> None:
    """Upsert a response. Never raises."""
    if not cache_enabled() or ttl_for(actor_id) is None:
        return

    payload = items if isinstance(items, list) else []
    try:
        encoded_len = len(json.dumps(payload, default=str))
    except Exception as exc:
        logger.warning("[APIFY CACHE] response not serialisable (%s) — not cached", exc)
        return

    max_bytes = int(os.getenv("APIFY_CACHE_MAX_BYTES", "2000000"))
    if encoded_len > max_bytes:
        logger.warning(
            "[APIFY CACHE] response %d bytes > %d cap — not cached (%s)",
            encoded_len, max_bytes, actor_id,
        )
        return

    key = _safe_cache_key(actor_id, run_input, max_items)
    if key is None:
        return
    try:
        summary = json.dumps(run_input, sort_keys=True, default=str)[:512]
    except Exception:
        summary = f"<unserialisable input for {actor_id}>"[:512]

    try:
        session = _session()
    except Exception as exc:
        logger.warning("[APIFY CACHE] session unavailable (%s) — not cached", exc)
        return

    try:
        from ospra_os.database.apify_cache_models import ApifyResponseCache

        row = session.query(ApifyResponseCache).filter_by(cache_key=key).first()
        now = datetime.utcnow()
        if row is None:
            session.add(ApifyResponseCache(
                cache_key=key, actor_id=actor_id, run_input_summary=summary,
                items=payload, item_count=len(payload), fetched_at=now, created_at=now,
            ))
        else:
            row.items = payload
            row.item_count = len(payload)
            row.fetched_at = now
            row.run_input_summary = summary
        session.commit()
    except Exception as exc:
        # Includes the benign concurrent-insert race: two parallel sub-queries
        # with the same key both miss, both run, both write. Worst case is one
        # duplicate actor run — never an exception reaching the caller.
        try:
            session.rollback()
        except Exception:
            pass
        logger.warning("[APIFY CACHE] write failed (%s) — continuing", exc)
    finally:
        try:
            session.close()
        except Exception:
            pass


def stamp_stale(items: List[Dict], fetched_at: datetime) -> List[Dict]:
    """Copy items and mark them stale so downstream scoring can downgrade
    confidence instead of treating the signal as absent."""
    marker = {"stale": True, "fetched_at": fetched_at.isoformat()}
    stamped: List[Dict] = []
    for item in items or []:
        if isinstance(item, dict):
            copy = dict(item)
            copy[CACHE_MARKER] = marker
            stamped.append(copy)
        else:
            stamped.append(item)
    return stamped


def is_stale_payload(items: Any) -> bool:
    """True when any item carries the stale marker."""
    return any(
        isinstance(i, dict) and (i.get(CACHE_MARKER) or {}).get("stale")
        for i in (items or [])
    )


def prune(older_than_days: Optional[int] = None) -> int:
    """Delete rows older than the retention window. Returns rows deleted."""
    days = older_than_days if older_than_days is not None else int(
        os.getenv("APIFY_CACHE_PRUNE_DAYS", "30")
    )
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        session = _session()
    except Exception as exc:
        logger.warning("[APIFY CACHE] prune skipped (%s)", exc)
        return 0
    try:
        from ospra_os.database.apify_cache_models import ApifyResponseCache

        deleted = (
            session.query(ApifyResponseCache)
            .filter(ApifyResponseCache.fetched_at < cutoff)
            .delete(synchronize_session=False)
        )
        session.commit()
        return int(deleted or 0)
    except Exception as exc:
        try:
            session.rollback()
        except Exception:
            pass
        logger.warning("[APIFY CACHE] prune failed (%s)", exc)
        return 0
    finally:
        try:
            session.close()
        except Exception:
            pass
