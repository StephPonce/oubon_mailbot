"""F1 — the prediction→outcome ledger (D10).

The ledger's entire value is that a snapshot was provably written BEFORE the
outcome was known. If a snapshot can be updated or backfilled it is no longer
evidence, it just looks like evidence — which is worse. These tests pin that
guarantee at both layers (ORM and database), plus the properties calibration
depends on.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from ospra_os.database.base import Base
from ospra_os.database.ledger_models import (
    CalibrationReport,
    GradeSnapshot,
    LedgerImmutabilityError,
    ProductOutcome,
)
from ospra_os.intelligence import ledger


@pytest.fixture()
def led(engine, monkeypatch):
    Base.metadata.create_all(
        bind=engine,
        tables=[GradeSnapshot.__table__, ProductOutcome.__table__,
                CalibrationReport.__table__],
    )
    monkeypatch.setattr(ledger, "_session", lambda: Session(engine))
    with Session(engine) as s:
        s.execute(text("DELETE FROM grade_snapshots"))
        s.execute(text("DELETE FROM product_outcomes"))
        s.execute(text("DELETE FROM calibration_reports"))
        s.commit()
    return ledger


def _product(pid, grade, **extra):
    p = {
        "product_id": pid,
        "title": f"Product {pid}",
        "oi_score": grade,
        "data_sources": {"aliexpress": {"orders": 900}},
        "data_coverage": {"by_source": {"aliexpress": "real", "amazon": "empty"}},
    }
    p.update(extra)
    return p


# ---------------------------------------------------------------------------
# Immutability — the sacred property
# ---------------------------------------------------------------------------

def test_snapshot_cannot_be_updated_via_orm(led, engine):
    led.record_run([_product("p1", 8.2)], niche="lighting", pipeline_run_id="run-a")
    with Session(engine) as s:
        row = s.query(GradeSnapshot).one()
        row.grade = 9.9
        with pytest.raises(LedgerImmutabilityError):
            s.commit()


def test_snapshot_cannot_be_deleted_via_orm(led, engine):
    led.record_run([_product("p1", 8.2)], niche="lighting", pipeline_run_id="run-a")
    with Session(engine) as s:
        row = s.query(GradeSnapshot).one()
        s.delete(row)
        with pytest.raises(LedgerImmutabilityError):
            s.commit()


def test_snapshot_immutability_survives_raw_sql(led, engine):
    """The ORM guard protects the app; raw SQL walks straight past it. The DB
    trigger is what makes immutability a property of the DATABASE.

    Skipped when the trigger is absent, because create_all() builds tables
    without running migration 013 — the assertion below is what matters in
    any environment that HAS the trigger (prod, and any migrated test DB).
    """
    with Session(engine) as s:
        has_trigger = s.execute(text(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' "
            "AND name='trg_grade_snapshots_no_update'"
        )).scalar()
    if not has_trigger:
        pytest.skip("trigger comes from migration 013; create_all() skips it")

    led.record_run([_product("p1", 8.2)], niche="lighting", pipeline_run_id="run-a")
    with Session(engine) as s:
        with pytest.raises(Exception):
            s.execute(text("UPDATE grade_snapshots SET grade = 9.9"))
            s.commit()


def test_rerunning_the_same_product_creates_a_new_row_not_an_edit(led, engine):
    """New run = new rows. This is how the ledger records a CHANGE of opinion
    without destroying the record of the earlier one."""
    led.record_run([_product("p1", 8.2)], niche="lighting", pipeline_run_id="run-a")
    led.record_run([_product("p1", 5.1)], niche="lighting", pipeline_run_id="run-b")
    with Session(engine) as s:
        grades = sorted(g for (g,) in s.query(GradeSnapshot.grade).all())
    assert grades == [5.1, 8.2]


# ---------------------------------------------------------------------------
# Completeness — what we did NOT pick is signal too
# ---------------------------------------------------------------------------

def test_fit_gate_rejects_are_logged(led, engine):
    led.record_run(
        [
            _product("pass1", 7.0, fit_pass=True),
            _product("rej1", 3.0, fit_pass=False, fit_reasons=["G4 app_required"]),
        ],
        niche="lighting", pipeline_run_id="run-a",
    )
    with Session(engine) as s:
        rows = {r.product_key: r for r in s.query(GradeSnapshot).all()}
    assert len(rows) == 2, "rejects must be recorded — they are training data"
    rejected = [r for r in rows.values() if r.fit_pass is False]
    assert rejected and rejected[0].fit_reasons == ["G4 app_required"]


def test_source_manifest_present_on_every_snapshot(led, engine):
    """A grade computed with most sources dead must be identifiable, or it
    silently pollutes calibration."""
    led.record_run([_product("p1", 8.2)], niche="lighting", pipeline_run_id="run-a")
    with Session(engine) as s:
        row = s.query(GradeSnapshot).one()
    assert row.source_manifest and "sources" in row.source_manifest
    assert row.sources_total == len(ledger.KNOWN_SOURCES)
    assert row.source_manifest["sources"]["aliexpress"] == "real"
    # "empty" (asked, nothing there) must not be conflated with "absent"
    # (never ran) — they mean different things about the market.
    assert row.source_manifest["sources"]["amazon"] == "empty"
    assert row.source_manifest["sources"]["cj_dropshipping"] == "absent"


def test_ledger_write_failure_is_loud(led, monkeypatch):
    """A silently skipped snapshot yields a quietly incomplete ledger, and
    calibration over an incomplete ledger is a confident wrong answer."""
    class _BoomSession:
        def add_all(self, _): pass
        def commit(self): raise RuntimeError("db down")
        def rollback(self): pass
        def close(self): pass

    monkeypatch.setattr(ledger, "_session", lambda: _BoomSession())
    with pytest.raises(RuntimeError):
        ledger.record_run([_product("p1", 8.2)], niche="lighting", pipeline_run_id="r")


# ---------------------------------------------------------------------------
# Receipts + calibration
# ---------------------------------------------------------------------------

def test_receipts_pairs_snapshots_with_later_outcomes(led, engine):
    led.record_run([_product("p1", 8.2)], niche="lighting", pipeline_run_id="run-a")
    with Session(engine) as s:
        snap_ts = s.query(GradeSnapshot).one().ts
        s.add(ProductOutcome(
            product_key=s.query(GradeSnapshot).one().product_key,
            period_start=snap_ts + timedelta(days=1),
            period_end=snap_ts + timedelta(days=8),
            orders=12, revenue=430.0,
        ))
        s.commit()

    rows = led.receipts(snap_ts - timedelta(days=1), snap_ts + timedelta(days=30))
    assert len(rows) == 1
    assert rows[0]["outcomes"][0]["orders"] == 12


def test_receipts_ignores_outcomes_that_predate_the_prediction(led, engine):
    """An outcome measured before the grade cannot validate it."""
    led.record_run([_product("p1", 8.2)], niche="lighting", pipeline_run_id="run-a")
    with Session(engine) as s:
        snap = s.query(GradeSnapshot).one()
        s.add(ProductOutcome(
            product_key=snap.product_key,
            period_start=snap.ts - timedelta(days=10),
            period_end=snap.ts - timedelta(days=3),
            orders=99,
        ))
        s.commit()
        ts = snap.ts

    rows = led.receipts(ts - timedelta(days=30), ts + timedelta(days=30))
    assert rows[0]["outcomes"] == [], "backward-looking outcomes must not count"


def test_spearman_ranks_and_handles_ties():
    assert ledger.spearman([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0
    assert ledger.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    # Monotonic but non-linear: rank correlation should still be perfect.
    assert ledger.spearman([1, 2, 3, 4], [1, 10, 100, 1000]) == 1.0


def test_spearman_returns_none_rather_than_a_fake_zero():
    """A fabricated 0.0 reads as 'no relationship'; None reads as 'not enough
    evidence'. Those are very different claims to put on a receipts page."""
    assert ledger.spearman([1, 2], [1, 2]) is None          # too few points
    assert ledger.spearman([5, 5, 5], [1, 2, 3]) is None    # no variance


def test_calibration_reports_insufficient_data_honestly(led):
    report = led.compute_calibration(window_days=28, persist=False)
    assert report["notes"]["verdict"] == "insufficient_data"
    assert report["spearman_grade_vs_orders"] is None
