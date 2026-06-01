"""
Billing Tasks — LemonSqueezy subscription / order processing.

The LemonSqueezy webhook handler validates the ``X-Signature`` (unchanged),
then calls ``dispatch_tier_change`` and returns 200 immediately. Dispatch is
a HYBRID:

  * If a Celery worker is reachable, the tier change is enqueued
    (``apply_subscription_change``) so the DB write happens on the worker with
    exponential-backoff retries (30s / 2min / 10min) and dead-lettering.
  * If NO worker/broker is available (e.g. the current single-service Render
    deployment has neither Redis nor a worker), the change is applied
    synchronously in-process so a paying customer is upgraded immediately.
  * Only a genuine failure (DB error, unknown tier) parks the event in
    ``billing_dead_letter`` for manual reconciliation — nothing is silently
    dropped.

This replaces the old ``BackgroundTasks(upgrade_user_tier)`` path, whose
handler swallowed every exception — a transient DB error there left a paying
customer on the wrong tier with no retry and no record.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ospra_os.celery_app import celery_app
from ospra_os.tasks.base import DatabaseTask

logger = logging.getLogger(__name__)

# Seconds to wait before each retry, indexed by retries already taken:
# retry #1 -> 30s, retry #2 -> 120s, retry #3 -> 600s.
_RETRY_BACKOFF = [30, 120, 600]
MAX_RETRIES = len(_RETRY_BACKOFF)


def resolve_tier(tier: str):
    """Map a tier string to the SubscriptionTier enum, or None if unknown."""
    from ospra_os.database import SubscriptionTier

    return {
        "nest": SubscriptionTier.NEST,
        "flight": SubscriptionTier.FLIGHT,
        "soar": SubscriptionTier.SOAR,
        "stratosphere": SubscriptionTier.STRATOSPHERE,
    }.get((tier or "").lower())


# ---------------------------------------------------------------------------
# Synchronous core — the single source of truth for "apply a tier change".
# Used by both the Celery task and the in-process fallback. Raises on failure
# so callers can retry / dead-letter; it never swallows errors.
# ---------------------------------------------------------------------------
def apply_tier_change(user_id: int, tier: str) -> None:
    """
    Apply a subscription tier change for ``user_id``. Raises on unknown tier,
    missing user, or DB error.
    """
    from ospra_os.database import SessionLocal, User

    tier_key = (tier or "").lower()
    tier_enum = resolve_tier(tier_key)
    if tier_enum is None:
        raise ValueError(f"unknown tier {tier!r}")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None:
            # A checkout webhook can arrive before the user row is visible
            # (replication lag / open txn). Treat as retryable upstream.
            raise ValueError(f"user {user_id} not found")
        user.subscription_tier = tier_enum
        if tier_key != "nest":
            user.subscription_started = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("billing: user %s set to tier %s", user_id, tier_key)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="ospra_os.tasks.billing_tasks.apply_subscription_change",
    max_retries=MAX_RETRIES,
)
def apply_subscription_change(
    self,
    user_id: int,
    tier: str,
    event_name: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Worker entry point: apply tier change with retry + dead-letter."""
    # Unknown tier is a payload problem, not transient — park it immediately.
    if resolve_tier(tier) is None:
        logger.error("billing: unknown tier %r for user %s — dead-lettering", tier, user_id)
        _dead_letter(event_name, user_id, tier, payload, f"unknown tier {tier!r}", self.request.retries)
        return {"status": "dead", "reason": "unknown_tier", "user_id": user_id}

    try:
        apply_tier_change(user_id, tier)
        return {"status": "ok", "user_id": user_id, "tier": (tier or "").lower()}
    except Exception as exc:
        retries = self.request.retries
        if retries < MAX_RETRIES:
            countdown = _RETRY_BACKOFF[retries]
            logger.warning(
                "billing: tier change failed for user %s (attempt %d/%d) — retrying in %ds: %s",
                user_id, retries + 1, MAX_RETRIES, countdown, exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.error("billing: tier change exhausted retries for user %s: %s", user_id, exc)
        _dead_letter(event_name, user_id, tier, payload, str(exc), retries)
        return {"status": "dead", "reason": "retries_exhausted", "user_id": user_id}


# ---------------------------------------------------------------------------
# Worker-availability probe (cached) — decides enqueue vs. inline.
# ---------------------------------------------------------------------------
_worker_probe: Dict[str, Any] = {"ts": 0.0, "ok": False}


def _celery_worker_available(ttl: int = 30) -> bool:
    """
    True if a Celery worker answers a ping. Result cached for ``ttl`` seconds
    so we don't add a broker round-trip to every webhook. On the current
    Render deployment (no Redis/worker) the ping fails fast and we return
    False, so dispatch falls back to synchronous in-process application.
    """
    now = time.time()
    if now - _worker_probe["ts"] < ttl:
        return _worker_probe["ok"]
    ok = False
    try:
        replies = celery_app.control.ping(timeout=0.5)
        ok = bool(replies)
    except Exception as exc:  # broker unreachable, etc.
        logger.debug("celery worker probe failed: %s", exc)
        ok = False
    _worker_probe.update(ts=now, ok=ok)
    return ok


def dispatch_tier_change(
    user_id: int,
    tier: str,
    event_name: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Hybrid dispatch. Returns one of: ``"enqueued"``, ``"applied"``, ``"dead_letter"``.
    Never raises — a paying customer's upgrade is never lost.
    """
    # Prefer the worker (gets retry + backoff + DLQ) when one is live.
    if _celery_worker_available():
        try:
            apply_subscription_change.delay(user_id, tier, event_name, payload)
            logger.info("billing: enqueued tier change user=%s tier=%s", user_id, tier)
            return "enqueued"
        except Exception as exc:
            logger.warning("billing: enqueue failed despite worker probe; applying inline: %s", exc)

    # No worker (or enqueue failed): apply right now so the customer is upgraded.
    try:
        apply_tier_change(user_id, tier)
        return "applied"
    except Exception as exc:
        logger.error("billing: inline tier change failed for user %s: %s", user_id, exc)
        _dead_letter(event_name, user_id, tier, payload, str(exc), 0)
        return "dead_letter"


def _dead_letter(
    event_name: Optional[str],
    user_id: Optional[int],
    tier: Optional[str],
    payload: Optional[Dict[str, Any]],
    last_error: str,
    retries: int,
) -> None:
    """Park an unrecoverable billing event; never raises."""
    try:
        from ospra_os.database.dead_letter_models import record_dead_letter

        record_dead_letter(
            event_name=event_name,
            user_id=int(user_id) if user_id is not None else None,
            tier=tier,
            payload=payload,
            last_error=last_error,
            attempts=(retries or 0) + 1,
        )
    except Exception as exc:  # pragma: no cover - last line of defence
        logger.error("billing: failed to record dead letter for user %s: %s", user_id, exc)
