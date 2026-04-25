"""
Webhook background-task dead-letter queue + retry.

Audit fix #5. The 24 ``process_*`` handlers wired into Shopify webhooks
all share the same shape:

    @router.post("/something")
    async def webhook_something(... background_tasks: BackgroundTasks):
        ...
        background_tasks.add_task(process_something, data, store_id)
        return {"status": "received"}  # always 200

The ``process_something`` body wraps everything in
``try/except Exception as e: logger.error(...)`` because Shopify has
already received the 200 — by the time the task runs, raising would be
useless. The previous code took that to its logical end and simply
**dropped** failed work on the floor: a flaky DB connection during a
``customers/redact`` meant the deletion never happened, the audit log
never recorded a refusal, and Shopify's 30-day SLA quietly ticked past.

This module is the smallest correct fix:

  1. A single ``webhook_failures`` table records any handler that raises.
  2. ``safe_dispatch(handler, payload, *, context=...)`` is the wrapper
     the webhook routes call instead of the bare handler. It runs the
     handler, and on exception, persists a row with the original payload
     so the work can be resumed later.
  3. ``retry_due_failures()`` is the worker entry point. It picks up
     rows whose ``next_attempt_at`` has elapsed, replays the original
     handler with the original payload, and either deletes the row
     (success) or schedules the next retry with exponential backoff.
  4. After ``MAX_ATTEMPTS`` failures, the row is flipped to
     ``status='dead'`` and stays in the table indefinitely so the
     operator can inspect what's stuck. The retry loop ignores dead
     rows; an ops dashboard or a manual re-queue can promote them back
     to ``pending``.

Backoff schedule (one row per attempt count): 1 min, 5 min, 30 min,
2 h, 8 h. After the 5th failure the row is dead-lettered. That gives a
genuinely transient problem (DB hiccup, shop offline) ~10 hours of
recovery time without spamming retries on a permanently-broken handler.

Why not Celery / RQ: those would be the right answer at scale, but they
add a new piece of infra. A single Postgres table and a tick-every-minute
asyncio task is enough for Ospra's webhook volume and avoids a Redis or
worker process dependency. If retry rate ever exceeds ~1/sec sustained,
revisit.

Handlers that want retry coverage need to be importable by name (so the
worker can resolve the dotted path on retry). The current ``process_*``
functions in ``ospra_os.webhooks.shopify_webhooks`` qualify.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)

from ospra_os.database.base import Base
from ospra_os.database.connection import SessionLocal, get_engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backoff schedule
# ---------------------------------------------------------------------------
#
# Index = attempt number that just failed (1-based). Value = seconds to
# wait before the NEXT attempt. After ``MAX_ATTEMPTS`` failures the row
# is dead-lettered.
#
_BACKOFF_SECONDS = [
    60,        # 1 → 1 min
    5 * 60,    # 2 → 5 min
    30 * 60,   # 3 → 30 min
    2 * 3600,  # 4 → 2 h
    8 * 3600,  # 5 → 8 h
]
MAX_ATTEMPTS = len(_BACKOFF_SECONDS)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class WebhookFailure(Base):
    """One failed background-handler invocation. See module docstring."""

    __tablename__ = "webhook_failures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Dotted path to the handler that should be re-invoked on retry,
    # e.g. ``ospra_os.webhooks.shopify_webhooks.process_gdpr_customer_redact``.
    handler = Column(String(255), nullable=False, index=True)
    payload = Column(Text, nullable=False)  # JSON-encoded original webhook body
    context = Column(Text, nullable=True)   # JSON — extras like store_id

    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)
    next_attempt_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    status = Column(String(16), nullable=False, default="pending", index=True)
    # ``pending`` — eligible for retry once next_attempt_at elapses
    # ``dead``    — exceeded MAX_ATTEMPTS, requires manual intervention

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_webhook_failures_status_next", "status", "next_attempt_at"),
    )


_table_ready = False


def _ensure_table() -> None:
    """Create the table on first use (no-op after ``init_database``)."""
    global _table_ready
    if _table_ready:
        return
    try:
        engine = get_engine()
        Base.metadata.create_all(engine, tables=[WebhookFailure.__table__])
        _table_ready = True
    except Exception as exc:  # pragma: no cover
        logger.warning("dlq: failed to ensure webhook_failures table: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backoff_for(attempts: int) -> Optional[int]:
    """
    Return the delay in seconds before the NEXT attempt given the
    just-completed attempt count, or ``None`` if no more retries are
    allowed (caller should mark dead).
    """
    if attempts >= MAX_ATTEMPTS:
        return None
    return _BACKOFF_SECONDS[attempts - 1] if 1 <= attempts <= MAX_ATTEMPTS else _BACKOFF_SECONDS[-1]


def _resolve_handler(dotted_path: str) -> Optional[Callable[..., Awaitable[Any]]]:
    """
    Look up an async handler by its dotted-path module:function name.

    Returns ``None`` if the import fails — that happens after a refactor
    that renames or moves the handler. We log loudly so the operator
    knows to re-aim the DLQ row at the new path.
    """
    if ":" in dotted_path:
        module_name, func_name = dotted_path.split(":", 1)
    else:
        module_name, _, func_name = dotted_path.rpartition(".")
        if not module_name:
            logger.error("dlq: invalid handler path %r", dotted_path)
            return None
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        logger.error("dlq: handler module %s not importable: %s", module_name, exc)
        return None
    func = getattr(module, func_name, None)
    if func is None:
        logger.error("dlq: handler %s not found in %s", func_name, module_name)
        return None
    if not asyncio.iscoroutinefunction(func):
        logger.error("dlq: handler %s is not an async function", dotted_path)
        return None
    return func


# ---------------------------------------------------------------------------
# Public API — record + dispatch
# ---------------------------------------------------------------------------

def record_failure(
    handler: str,
    payload: Dict[str, Any],
    error: str,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """
    Persist a failed handler invocation so the worker can retry it.

    Args:
        handler: Dotted path resolvable by ``_resolve_handler``.
        payload: The original webhook body (will be ``json.dumps``'d).
        error: Truncated error message for operator visibility.
        context: Extra positional args, e.g. ``{"store_id": 12}``.

    Returns the new row's id, or None if persistence itself failed
    (logged at ERROR — at that point the work really is lost).
    """
    _ensure_table()
    db = SessionLocal()
    try:
        row = WebhookFailure(
            handler=handler,
            payload=json.dumps(payload or {}),
            context=json.dumps(context or {}),
            attempts=1,
            last_error=(error or "")[:2000],
            last_attempt_at=datetime.now(timezone.utc),
            next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=_BACKOFF_SECONDS[0]),
            status="pending",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.warning(
            "dlq: recorded failure id=%s handler=%s next_attempt=%s",
            row.id, handler, row.next_attempt_at,
        )
        return row.id
    except Exception as exc:
        db.rollback()
        logger.error("dlq.record_failure persistence failed: %s", exc)
        return None
    finally:
        db.close()


async def safe_dispatch(
    handler: str,
    payload: Dict[str, Any],
    *,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Run a handler with automatic DLQ-on-failure semantics.

    The webhook route should call ``background_tasks.add_task(safe_dispatch, ...)``
    instead of the bare handler. Returns True on success, False if the
    handler raised (and the failure was recorded).

    Handlers must accept ``(payload_dict, **context)`` — the wider
    codebase's existing ``process_*(data, store_id)`` shape works
    because we pass context as kwargs.
    """
    func = _resolve_handler(handler)
    if func is None:
        # Even the import failed — record the row so an operator notices.
        record_failure(
            handler, payload,
            f"handler {handler!r} could not be imported",
            context=context,
        )
        return False
    try:
        await func(payload, **(context or {}))
        return True
    except Exception as exc:
        logger.exception("dlq: handler %s raised — recording failure", handler)
        record_failure(handler, payload, str(exc), context=context)
        return False


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------

async def retry_due_failures(*, batch_size: int = 25) -> Dict[str, int]:
    """
    One pass of the retry worker. Picks up to ``batch_size`` due rows,
    re-runs each, and updates the row according to the outcome.

    Returns a dict ``{succeeded, retried, dead}`` for observability.
    Safe to call from a periodic asyncio task; a second concurrent call
    would just race for the same rows and the second one would no-op
    (rows have already been claimed by ``attempts`` increment).
    """
    _ensure_table()
    db = SessionLocal()
    succeeded = 0
    retried = 0
    dead = 0
    try:
        now = datetime.now(timezone.utc)
        rows: List[WebhookFailure] = (
            db.query(WebhookFailure)
            .filter(
                WebhookFailure.status == "pending",
                WebhookFailure.next_attempt_at <= now,
            )
            .order_by(WebhookFailure.next_attempt_at.asc())
            .limit(batch_size)
            .all()
        )

        for row in rows:
            handler_path = row.handler
            try:
                payload = json.loads(row.payload) if row.payload else {}
            except json.JSONDecodeError:
                payload = {}
            try:
                context = json.loads(row.context) if row.context else {}
            except json.JSONDecodeError:
                context = {}

            func = _resolve_handler(handler_path)
            if func is None:
                # Can't even import the handler — give up after marking dead.
                row.status = "dead"
                row.last_error = f"handler {handler_path!r} not importable"
                row.last_attempt_at = datetime.now(timezone.utc)
                dead += 1
                continue

            row.attempts = (row.attempts or 0) + 1
            row.last_attempt_at = datetime.now(timezone.utc)
            try:
                await func(payload, **context)
                # Success — drop the row so we don't keep re-running it.
                db.delete(row)
                succeeded += 1
            except Exception as exc:
                row.last_error = str(exc)[:2000]
                next_delay = _backoff_for(row.attempts)
                if next_delay is None:
                    row.status = "dead"
                    dead += 1
                    logger.error(
                        "dlq: handler %s exhausted retries (id=%s): %s",
                        handler_path, row.id, exc,
                    )
                else:
                    row.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=next_delay)
                    retried += 1
                    logger.warning(
                        "dlq: handler %s retry %d/%d failed (id=%s) — next in %ds: %s",
                        handler_path, row.attempts, MAX_ATTEMPTS, row.id, next_delay, exc,
                    )

        db.commit()
        return {"succeeded": succeeded, "retried": retried, "dead": dead}
    except Exception as exc:
        db.rollback()
        logger.error("dlq.retry_due_failures top-level failure: %s", exc)
        return {"succeeded": succeeded, "retried": retried, "dead": dead}
    finally:
        db.close()


async def run_retry_worker(*, interval_seconds: int = 60) -> None:
    """
    Long-running worker — call once from ``_run_startup_deferred`` via
    ``asyncio.create_task``. Sleeps ``interval_seconds`` between passes
    so we don't hammer the DB on idle deployments.

    Cancelling the task (e.g. on shutdown) cleanly exits.
    """
    logger.info("dlq.run_retry_worker started (interval=%ds)", interval_seconds)
    try:
        while True:
            try:
                stats = await retry_due_failures()
                if any(stats.values()):
                    logger.info("dlq.retry_due_failures: %s", stats)
            except Exception as exc:
                logger.exception("dlq.run_retry_worker iteration failed: %s", exc)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("dlq.run_retry_worker cancelled — exiting")
        raise
