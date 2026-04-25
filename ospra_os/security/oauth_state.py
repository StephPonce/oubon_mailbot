"""
DB-backed OAuth state store (CSRF nonce persistence).

Audit fix #8 — three OAuth routers (Shopify Partner App OAuth, the older
shop-connect flow, WooCommerce) used to keep ``_oauth_states: Dict`` in
process memory. That broke any deployment with more than one worker:
the worker that handled ``/connect`` stored the nonce, and the worker
that handled the callback didn't have it, so the CSRF check failed
randomly. On Render rolling deploys the same effect happened across the
old and new container during the swap.

Design:
  - One table, ``oauth_states``, keyed by ``(provider, state)``.
  - ``data`` is JSON — every router has slightly different metadata
    (``shop``/``store_url``/``user_id``/...) and a generic blob keeps the
    schema stable.
  - ``put_state`` writes; ``pop_state`` atomically reads-and-deletes so a
    state token can never be reused (replay protection).
  - TTL defaults to 10 minutes — Shopify's authorize page typically
    finishes inside a minute; 10 covers a slow user without keeping
    nonces around indefinitely. Expired rows are GC'd inline by
    ``pop_state`` and by ``purge_expired`` for callers that want to
    sweep on a schedule.
  - The state-token PK is global (not scoped to provider); the
    ``provider`` column is just for observability and so a leaked nonce
    from one OAuth flow can't be redeemed against a different one.

This is deliberately the smallest possible API. We don't add Redis here
because we'd be adding a new infra dep for ~200 bytes of state with a
~10-minute lifetime — Postgres handles that fine.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    String,
    Text,
)

from ospra_os.database.base import Base
from ospra_os.database.connection import SessionLocal, get_engine

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 600  # 10 minutes


class OAuthState(Base):
    """OAuth CSRF nonce row. See module docstring for design notes."""

    __tablename__ = "oauth_states"

    state = Column(String(128), primary_key=True)
    provider = Column(String(32), nullable=False, index=True)
    data = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        Index("ix_oauth_states_provider_state", "provider", "state"),
    )


_table_ready = False


def _ensure_table() -> None:
    """
    Create the ``oauth_states`` table on first use.

    The shared ``init_database`` call in ``main._run_startup_critical``
    already creates every Base table, so in production this is usually a
    no-op. The lazy create matters for ad-hoc scripts and tests that
    bypass full startup.
    """
    global _table_ready
    if _table_ready:
        return
    try:
        engine = get_engine()
        Base.metadata.create_all(engine, tables=[OAuthState.__table__])
        _table_ready = True
    except Exception as exc:  # pragma: no cover - logged so an operator notices
        logger.warning(
            "oauth_state: failed to ensure oauth_states table exists: %s", exc
        )


def put_state(
    provider: str,
    state: str,
    data: Optional[Dict[str, Any]] = None,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """
    Persist a freshly-minted OAuth state nonce.

    Safe to call concurrently — a duplicate ``state`` would only
    happen on a true 256-bit collision, which is the same risk profile
    as the in-memory dict had.
    """
    _ensure_table()
    # Naive UTC for DB compatibility — Column(DateTime) without
    # timezone=True drops tzinfo on persistence, and comparing
    # naive-vs-aware datetimes raises TypeError. Stay naive UTC across
    # this module so reads and writes match.
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).replace(tzinfo=None)
    payload = json.dumps(data or {})
    db = SessionLocal()
    try:
        row = OAuthState(
            state=state,
            provider=provider,
            data=payload,
            expires_at=expires_at,
        )
        db.add(row)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("oauth_state.put_state failed: %s", exc)
        raise
    finally:
        db.close()


def pop_state(provider: str, state: str) -> Optional[Dict[str, Any]]:
    """
    Atomically look up + delete a state token.

    Returns the stored ``data`` dict on success. Returns ``None`` if
    the state was unknown, expired, or registered against a different
    provider — the caller should treat all three identically (CSRF
    failure → redirect to error page).
    """
    _ensure_table()
    db = SessionLocal()
    try:
        row = (
            db.query(OAuthState)
            .filter(OAuthState.state == state, OAuthState.provider == provider)
            .first()
        )
        if row is None:
            return None

        # Expired? Drop the row and return None — same UX as "unknown".
        if row.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            db.delete(row)
            db.commit()
            return None

        try:
            data = json.loads(row.data) if row.data else {}
        except json.JSONDecodeError:
            data = {}

        # Atomic consume — pop, never reuse.
        db.delete(row)
        db.commit()
        return data
    except Exception as exc:
        db.rollback()
        logger.error("oauth_state.pop_state failed: %s", exc)
        return None
    finally:
        db.close()


def purge_expired(*, batch_size: int = 500) -> int:
    """
    Delete every expired ``oauth_states`` row. Returns the count.

    Wire this into a periodic job if traffic is high enough that
    expired-but-unused nonces accumulate. Otherwise the inline
    expiry-on-pop path is sufficient.
    """
    _ensure_table()
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = (
            db.query(OAuthState)
            .filter(OAuthState.expires_at < cutoff)
            .limit(batch_size)
            .all()
        )
        count = 0
        for row in rows:
            db.delete(row)
            count += 1
        db.commit()
        return count
    except Exception as exc:
        db.rollback()
        logger.error("oauth_state.purge_expired failed: %s", exc)
        return 0
    finally:
        db.close()
