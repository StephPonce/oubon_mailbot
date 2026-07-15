"""
Fail-if-reverted lock on the DEPLOY-TIME schema drift guard.

Prod (b9ec5f1 / PR #7) reds a deploy when a model column is missing from the
live Postgres DB — the exact failure mode that let prod drift 34 columns behind
the models before migration 005 reconciled it. The guard is two facts working
together:

  1. ``fail_on_drift`` raises RuntimeError on *blocking* drift (a model column or
     whole table absent from the DB) and stays silent on *informational* drift
     (``extra_in_db`` — columns the create_all backfill leaves behind after a
     model drops them).
  2. ``init_database``'s PostgreSQL path actually CALLS it (connection.py), after
     migrations + backfill, so the raise propagates out of ``_run_startup_critical``
     and reds the deploy while the previous release keeps serving.

Nothing else in the suite covers either fact, so a future edit could quietly
downgrade the deploy guard to warn-only and ship a latent 500. These tests fail
the moment that happens.
"""

from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-drift-guard")

from ospra_os.database import schema_drift
from ospra_os.database.schema_drift import DriftReport, TableDrift, fail_on_drift


def _patch_report(monkeypatch, report: DriftReport) -> None:
    """Make ``fail_on_drift`` see a crafted drift report (no live DB needed).

    ``fail_on_drift`` looks up ``detect_drift`` in its module globals at call
    time, so patching the module attribute is enough.
    """
    monkeypatch.setattr(schema_drift, "detect_drift", lambda engine=None: report)


class TestFailOnDriftContract:
    def test_missing_column_reds_the_deploy(self, monkeypatch):
        # A model column absent from the DB WILL 500 at request time.
        _patch_report(
            monkeypatch,
            DriftReport(tables=[TableDrift(table="users", missing_in_db=["is_admin"])]),
        )
        with pytest.raises(RuntimeError, match="deploy blocked"):
            fail_on_drift()

    def test_missing_table_reds_the_deploy(self, monkeypatch):
        _patch_report(
            monkeypatch,
            DriftReport(tables=[TableDrift(table="product_comments", table_missing=True)]),
        )
        with pytest.raises(RuntimeError, match="deploy blocked"):
            fail_on_drift()

    def test_extra_db_column_is_informational_not_fatal(self, monkeypatch):
        # ``extra_in_db`` = a column the model dropped but create_all left in the
        # DB for backfill safety. It never 500s a SELECT, so it must NOT red a
        # deploy — otherwise every safe model-column removal would block prod.
        _patch_report(
            monkeypatch,
            DriftReport(tables=[TableDrift(table="users", extra_in_db=["legacy_flag"])]),
        )
        # No exception.
        report = fail_on_drift()
        assert report.has_drift is True
        assert report.blocking is False

    def test_clean_schema_does_not_raise(self, monkeypatch):
        _patch_report(monkeypatch, DriftReport())
        report = fail_on_drift()
        assert report.has_drift is False


class TestGuardIsWiredIntoDeploy:
    def test_init_database_postgres_path_calls_fail_on_drift(self):
        """The drift guard is worthless if nothing invokes it on deploy. Lock the
        wiring: ``init_database`` must still reference ``fail_on_drift``. If this
        reverts to warn-only, prod can ship a latent 500 (the 34-column-drift
        failure mode) — so this fails loudly."""
        from ospra_os.database import connection

        src = inspect.getsource(connection.init_database)
        assert "fail_on_drift" in src, (
            "init_database must call fail_on_drift on the PostgreSQL path — "
            "reverting it to warn-only re-opens the silent-drift 500 bug"
        )
