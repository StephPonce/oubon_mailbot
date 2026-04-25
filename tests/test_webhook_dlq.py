"""
Tests for the webhook dead-letter / retry queue (audit fix #5).

Covers the contract the GDPR + uninstall handlers depend on:
  - safe_dispatch returns True on success and runs the handler with the
    payload and context kwargs
  - safe_dispatch returns False on failure and persists a webhook_failures row
  - retry_due_failures replays a failed handler and deletes the row on success
  - the row's status flips to 'dead' once MAX_ATTEMPTS is exhausted
  - rows whose next_attempt_at is in the future are skipped
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

# Module under test — and a place to register stub handlers we control.
from ospra_os.webhooks import dlq
from ospra_os.webhooks.dlq import (
    MAX_ATTEMPTS,
    WebhookFailure,
    record_failure,
    retry_due_failures,
    safe_dispatch,
)
from ospra_os.database.connection import SessionLocal


def _open_session():
    """
    Open a session against the same engine ``record_failure`` /
    ``retry_due_failures`` use. The conftest ``db_session`` fixture wraps
    its own session in an outer transaction that we roll back at the end
    of each test, but the DLQ helpers open their own independent sessions
    through ``SessionLocal``. Tests that need to seed or inspect rows
    must do so through the same path so they actually see the helpers'
    writes.
    """
    return SessionLocal()


@pytest.fixture(autouse=True)
def _wipe_failures():
    """
    Clean ``webhook_failures`` before AND after every test.

    The DLQ helpers commit through independent sessions that the
    transactional ``db_session`` fixture doesn't roll back, so leftover
    rows from one test would leak into the next.

    We call ``_ensure_table`` first because the table is only created
    lazily on first use of the helpers, and our cleanup pre-test runs
    before any test has had a chance to trigger that.
    """
    dlq._ensure_table()
    db = _open_session()
    try:
        db.query(WebhookFailure).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = _open_session()
    try:
        db.query(WebhookFailure).delete()
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stub handlers — registered as attributes of ``dlq`` so the resolver
# (which uses dotted paths) can find them.
# ---------------------------------------------------------------------------

_call_log: list[dict] = []


async def _stub_succeeds(payload, *, store_id=None):
    _call_log.append({"payload": payload, "store_id": store_id})


async def _stub_always_fails(payload, *, store_id=None):
    _call_log.append({"payload": payload, "store_id": store_id})
    raise RuntimeError("boom")


# Registered once at module-import time so dotted-path lookup resolves.
dlq._stub_succeeds = _stub_succeeds  # type: ignore[attr-defined]
dlq._stub_always_fails = _stub_always_fails  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _clear_call_log():
    _call_log.clear()
    yield
    _call_log.clear()


# ---------------------------------------------------------------------------
# safe_dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_safe_dispatch_runs_handler_on_success():
    ok = await safe_dispatch(
        "ospra_os.webhooks.dlq._stub_succeeds",
        {"shop": "demo"},
        context={"store_id": 7},
    )
    assert ok is True
    assert _call_log == [{"payload": {"shop": "demo"}, "store_id": 7}]
    # No failure row was written.
    db = _open_session()
    try:
        assert db.query(WebhookFailure).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_safe_dispatch_records_row_on_failure():
    ok = await safe_dispatch(
        "ospra_os.webhooks.dlq._stub_always_fails",
        {"shop": "demo"},
        context={"store_id": 7},
    )
    assert ok is False
    db = _open_session()
    try:
        rows = db.query(WebhookFailure).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.handler == "ospra_os.webhooks.dlq._stub_always_fails"
        assert row.attempts == 1
        assert "boom" in (row.last_error or "")
        assert row.status == "pending"
        # next_attempt_at should be in the future (first backoff = 60s)
        assert row.next_attempt_at > datetime.utcnow()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_safe_dispatch_unknown_handler_records_failure():
    ok = await safe_dispatch(
        "ospra_os.webhooks.dlq.handler_does_not_exist",
        {"x": 1},
    )
    assert ok is False
    db = _open_session()
    try:
        rows = db.query(WebhookFailure).all()
        assert len(rows) == 1
        assert "could not be imported" in (rows[0].last_error or "")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# retry_due_failures
# ---------------------------------------------------------------------------

def _force_row_due(failure_id: int, *, attempts: int | None = None) -> int:
    """Backdate ``next_attempt_at`` (and optionally set ``attempts``) so a row is eligible for retry."""
    db = _open_session()
    try:
        row = db.query(WebhookFailure).filter_by(id=failure_id).first()
        assert row is not None, f"failure {failure_id} not in DB"
        row.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
        if attempts is not None:
            row.attempts = attempts
        db.commit()
        return row.attempts
    finally:
        db.close()


@pytest.mark.asyncio
async def test_retry_due_failures_succeeds_and_drops_row():
    """
    A failure was recorded for a handler. The handler now succeeds (the
    stub does). The retry worker should pick up the due row, re-run the
    handler, and delete the row on success.
    """
    failure_id = record_failure(
        "ospra_os.webhooks.dlq._stub_succeeds",
        {"shop": "demo"},
        "first attempt blew up",
        context={"store_id": 9},
    )
    assert failure_id is not None
    _force_row_due(failure_id)

    stats = await retry_due_failures()
    assert stats["succeeded"] == 1
    assert stats["retried"] == 0
    assert stats["dead"] == 0
    assert _call_log == [{"payload": {"shop": "demo"}, "store_id": 9}]
    db = _open_session()
    try:
        assert db.query(WebhookFailure).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_retry_due_failures_dead_letters_after_max_attempts():
    """
    A handler that always fails should hit ``status='dead'`` once
    MAX_ATTEMPTS is exhausted. We seed a row with ``attempts`` at
    MAX_ATTEMPTS-1 so a single retry pushes it over.
    """
    failure_id = record_failure(
        "ospra_os.webhooks.dlq._stub_always_fails",
        {"x": 1},
        "first failure",
    )
    _force_row_due(failure_id, attempts=MAX_ATTEMPTS - 1)

    stats = await retry_due_failures()
    assert stats["dead"] == 1

    db = _open_session()
    try:
        final = db.query(WebhookFailure).filter_by(id=failure_id).first()
        assert final is not None
        assert final.status == "dead"
        assert final.attempts == MAX_ATTEMPTS
    finally:
        db.close()


@pytest.mark.asyncio
async def test_retry_due_failures_skips_future_rows():
    """A row whose next_attempt_at is in the future is left alone."""
    failure_id = record_failure(
        "ospra_os.webhooks.dlq._stub_succeeds",
        {"x": 1},
        "first failure",
    )
    # Push way into the future.
    db = _open_session()
    try:
        row = db.query(WebhookFailure).filter_by(id=failure_id).first()
        row.next_attempt_at = datetime.utcnow() + timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    stats = await retry_due_failures()
    assert stats == {"succeeded": 0, "retried": 0, "dead": 0}
    db = _open_session()
    try:
        assert db.query(WebhookFailure).count() == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_retry_due_failures_increments_attempt_and_schedules_next():
    """
    Retry of a still-failing handler should increment ``attempts`` and
    push ``next_attempt_at`` forward by the next backoff window.
    """
    failure_id = record_failure(
        "ospra_os.webhooks.dlq._stub_always_fails",
        {"x": 1},
        "first failure",
    )
    initial_attempts = _force_row_due(failure_id)

    stats = await retry_due_failures()
    assert stats["retried"] == 1

    db = _open_session()
    try:
        fresh = db.query(WebhookFailure).filter_by(id=failure_id).first()
        assert fresh.attempts == initial_attempts + 1
        assert fresh.status == "pending"
        assert fresh.next_attempt_at > datetime.utcnow()
    finally:
        db.close()
