"""
Billing dead-letter table.

When a LemonSqueezy subscription/order webhook arrives, the actual tier
change is performed by a Celery task (``ospra_os.tasks.billing_tasks``)
with exponential backoff. If that task exhausts its retries — or the
broker can't be reached to enqueue it — the full event is parked here so
the subscription can be reconciled by hand instead of silently leaving a
paying customer on the wrong tier.

Self-contained (model + lazy table creation) following the same pattern
as ``ospra_os/webhooks/dlq.py``, so it comes online without an edit to
``database/__init__.py`` or an Alembic migration: the table is created on
first write via ``ensure_table()``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text

from ospra_os.database.base import Base
from ospra_os.database.connection import SessionLocal, get_engine

logger = logging.getLogger(__name__)


class BillingDeadLetter(Base):
    """A billing event whose Celery retry attempts were all exhausted."""

    __tablename__ = "billing_dead_letter"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_name = Column(String(64), nullable=True, index=True)  # subscription_created, order_refunded, ...
    user_id = Column(Integer, nullable=True, index=True)
    tier = Column(String(32), nullable=True)
    payload = Column(Text, nullable=False)  # full JSON webhook body, for manual replay
    last_error = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    # ``dead`` — needs manual intervention; ``resolved`` — an operator fixed it.
    status = Column(String(16), nullable=False, default="dead", index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<BillingDeadLetter(id={self.id}, event={self.event_name!r}, "
            f"user_id={self.user_id}, tier={self.tier!r}, status={self.status!r})>"
        )


_table_ready = False


def ensure_table() -> None:
    """Create the table on first use (no-op once created)."""
    global _table_ready
    if _table_ready:
        return
    try:
        engine = get_engine()
        Base.metadata.create_all(engine, tables=[BillingDeadLetter.__table__])
        _table_ready = True
    except Exception as exc:  # pragma: no cover
        logger.warning("billing dead_letter: failed to ensure table: %s", exc)


def record_dead_letter(
    *,
    event_name: Optional[str],
    user_id: Optional[int],
    tier: Optional[str],
    payload: Optional[Dict[str, Any]],
    last_error: Optional[str],
    attempts: int = 0,
) -> Optional[int]:
    """
    Persist an exhausted (or un-enqueueable) billing event.

    Best-effort: if even this write fails, we log at ERROR — at that point
    the work really is lost and only the provider's own retry can recover
    it. Returns the new row id, or None on failure.
    """
    ensure_table()
    db = SessionLocal()
    try:
        row = BillingDeadLetter(
            event_name=event_name,
            user_id=user_id,
            tier=tier,
            payload=json.dumps(payload or {}),
            last_error=(last_error or "")[:2000],
            attempts=attempts or 0,
            status="dead",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.error(
            "billing dead_letter recorded id=%s event=%s user_id=%s tier=%s",
            row.id, event_name, user_id, tier,
        )
        return row.id
    except Exception as exc:
        db.rollback()
        logger.error("billing dead_letter persistence failed: %s", exc)
        return None
    finally:
        db.close()
