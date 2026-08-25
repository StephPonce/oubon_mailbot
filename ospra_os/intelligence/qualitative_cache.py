"""
Cache for the qualitative AI read.

Why: assess_product() runs on the top 10 ranked products of every discovery
run with no cache at all — ~3,000 grok-3 calls/month from the crons alone, plus
every user-triggered search. The catalog is ~100-200 products in steady state
with high times_seen, so most of those reads re-derive an identical answer from
identical evidence.

Design rules (same shape as apify/response_cache.py):
  * Key on the QUESTION: model + product identity + the exact evidence fed to
    the prompt. "Evidence changed" and "cache miss" become the same event, so
    there is no separate invalidation to forget.
  * NEVER cache a failure. A 401 or a non-JSON reply must not be frozen for a
    week — only assessments with error=None are stored.
  * The cache must never cause the outage it prevents: every DB failure logs
    and behaves as a miss.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_stats = {"hits": 0, "misses": 0, "writes": 0}


def reset_stats() -> None:
    _stats.update({"hits": 0, "misses": 0, "writes": 0})


def get_stats() -> Dict[str, int]:
    return dict(_stats)


def cache_enabled() -> bool:
    if os.getenv("OSPRA_QUAL_CACHE_BYPASS", "").strip().lower() in {"1", "true", "yes"}:
        # Escape hatch for evals/qualitative_source_value.py, which measures the
        # marginal value of each evidence source by ablation — served cached
        # reads would make it silently measure nothing.
        return False
    return os.getenv("QUAL_CACHE_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


def _ttl() -> timedelta:
    return timedelta(hours=float(os.getenv("QUAL_CACHE_TTL_HOURS", "168")))


def _session():
    """Indirection so tests can patch the session factory."""
    from ospra_os.database.connection import SessionLocal
    return SessionLocal()


def cache_key(model: str, product_key: str, evidence: Dict[str, Any]) -> str:
    """SHA-256 over what actually determines the answer.

    `evidence` is _collect_evidence()'s output — already truncated and capped
    by that function, so the hash input is bounded.
    """
    payload = json.dumps(
        {"v": 1, "model": model, "product_key": product_key, "evidence": evidence},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get(model: str, product_key: str, evidence: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a cached assessment dict, or None. Never raises."""
    if not cache_enabled():
        return None
    try:
        key = cache_key(model, product_key, evidence)
    except Exception as exc:
        logger.warning("[QUAL CACHE] un-keyable evidence (%s) — bypassing", exc)
        return None

    try:
        session = _session()
    except Exception as exc:
        logger.warning("[QUAL CACHE] session unavailable (%s) — treating as miss", exc)
        return None

    try:
        from ospra_os.database.qualitative_cache_models import QualitativeReadCache

        row = session.query(QualitativeReadCache).filter_by(cache_key=key).first()
        if row is None:
            _stats["misses"] += 1
            return None
        if datetime.utcnow() - row.fetched_at >= _ttl():
            _stats["misses"] += 1
            return None

        row.hit_count = (row.hit_count or 0) + 1
        row.last_hit_at = datetime.utcnow()
        assessment = row.assessment
        session.commit()
        _stats["hits"] += 1
        return assessment if isinstance(assessment, dict) else None
    except Exception as exc:
        logger.warning("[QUAL CACHE] read failed (%s) — treating as miss", exc)
        return None
    finally:
        try:
            session.close()
        except Exception:
            pass


def put(
    model: str,
    product_key: str,
    evidence: Dict[str, Any],
    assessment: Dict[str, Any],
    provider: Optional[str] = None,
) -> None:
    """Store a SUCCESSFUL assessment. Never raises, never caches a failure."""
    if not cache_enabled():
        return
    if not isinstance(assessment, dict) or assessment.get("error"):
        # Caching an error would freeze an outage for the whole TTL.
        return

    try:
        key = cache_key(model, product_key, evidence)
    except Exception:
        return

    try:
        session = _session()
    except Exception as exc:
        logger.warning("[QUAL CACHE] session unavailable (%s) — not cached", exc)
        return

    try:
        from ospra_os.database.qualitative_cache_models import QualitativeReadCache

        now = datetime.utcnow()
        row = session.query(QualitativeReadCache).filter_by(cache_key=key).first()
        if row is None:
            session.add(QualitativeReadCache(
                cache_key=key, product_key=str(product_key)[:255],
                provider=provider, model=model, assessment=assessment,
                fetched_at=now, created_at=now,
            ))
        else:
            row.assessment = assessment
            row.fetched_at = now
            row.provider = provider
            row.model = model
        session.commit()
        _stats["writes"] += 1
    except Exception as exc:
        try:
            session.rollback()
        except Exception:
            pass
        logger.warning("[QUAL CACHE] write failed (%s) — continuing", exc)
    finally:
        try:
            session.close()
        except Exception:
            pass


def prune(older_than_days: Optional[int] = None) -> int:
    """Delete rows past the retention window. Returns rows deleted."""
    days = older_than_days if older_than_days is not None else int(
        os.getenv("QUAL_CACHE_PRUNE_DAYS", "30")
    )
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        session = _session()
    except Exception:
        return 0
    try:
        from ospra_os.database.qualitative_cache_models import QualitativeReadCache

        deleted = (
            session.query(QualitativeReadCache)
            .filter(QualitativeReadCache.fetched_at < cutoff)
            .delete(synchronize_session=False)
        )
        session.commit()
        return int(deleted or 0)
    except Exception as exc:
        try:
            session.rollback()
        except Exception:
            pass
        logger.warning("[QUAL CACHE] prune failed (%s)", exc)
        return 0
    finally:
        try:
            session.close()
        except Exception:
            pass
