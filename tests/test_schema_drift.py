"""
Tests for ``ospra_os.database.schema_drift``.

The detector is the only thing standing between us and another silent
"column added to the model, missed in the DB" failure that takes down
login at 9 AM. Lock its behavior.
"""

from __future__ import annotations

from sqlalchemy import Column, Integer, String, MetaData, Table, create_engine
from sqlalchemy.orm import declarative_base

from ospra_os.database.schema_drift import (
    DriftReport,
    TableDrift,
    detect_drift,
)


def _make_engine_with_tables(*tables: Table):
    """Create a fresh in-memory SQLite with the given Table definitions."""
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    for t in tables:
        # Re-bind to our temp metadata so create_all targets our engine.
        new_t = Table(t.name, metadata, *(c.copy() for c in t.columns))
    metadata.create_all(engine)
    return engine


def test_drift_report_renders_clean_when_no_drift():
    report = DriftReport()
    rendered = report.render()
    assert "clean" in rendered.lower()
    assert report.has_drift is False


def test_drift_report_renders_missing_column_block():
    """A real-world drift block should clearly call out the missing column."""
    report = DriftReport(
        tables=[
            TableDrift(
                table="users",
                missing_in_db=["brand_name", "brand_descriptor"],
            ),
        ]
    )
    out = report.render()
    assert report.has_drift is True
    assert "users" in out
    assert "brand_name" in out
    assert "brand_descriptor" in out
    assert "model defines columns the DB does not have" in out


def test_drift_report_renders_extra_column_block():
    """Extra columns in the DB (left after a model drop) should appear too."""
    report = DriftReport(
        tables=[
            TableDrift(
                table="legacy_table",
                extra_in_db=["dropped_col"],
            ),
        ]
    )
    out = report.render()
    assert report.has_drift is True
    assert "dropped_col" in out
    assert "left for backfill" in out.lower()


def test_drift_report_renders_missing_table_block():
    report = DriftReport(
        tables=[TableDrift(table="ghost_table", table_missing=True)]
    )
    out = report.render()
    assert report.has_drift is True
    assert "ghost_table" in out
    assert "missing entirely" in out


def test_detect_drift_on_real_engine_finds_missing_column(monkeypatch):
    """
    End-to-end: build a Base with a User-like model, create a DB whose
    table is missing one of the model's columns, and assert detect_drift
    catches exactly that column.
    """
    # Local Base — don't touch the real ospra_os Base in tests.
    local_base = declarative_base()

    class FakeUser(local_base):
        __tablename__ = "fake_users"
        id = Column(Integer, primary_key=True)
        email = Column(String(255))
        # ``brand_name`` mimics the real-world drift that kicked off this
        # whole module.
        brand_name = Column(String(255), nullable=True)

    # Build a DB where ``fake_users`` exists but is missing brand_name.
    engine = create_engine("sqlite:///:memory:")
    legacy_metadata = MetaData()
    Table(
        "fake_users",
        legacy_metadata,
        Column("id", Integer, primary_key=True),
        Column("email", String(255)),
        # No brand_name here — that's the drift.
    )
    legacy_metadata.create_all(engine)

    # Patch the helper that reads model tables — ``sorted_tables`` is a
    # property and not directly setattr-able, so we substitute the
    # function that consumes it.
    from ospra_os.database import schema_drift as sd
    monkeypatch.setattr(
        sd, "_model_tables",
        lambda: {
            t.name: {c.name for c in t.columns}
            for t in local_base.metadata.sorted_tables
        },
    )

    report = detect_drift(engine)
    assert report.has_drift
    drift_for_users = next(
        (t for t in report.tables if t.table == "fake_users"), None
    )
    assert drift_for_users is not None
    assert drift_for_users.missing_in_db == ["brand_name"]
    assert drift_for_users.extra_in_db == []


def test_detect_drift_finds_missing_table(monkeypatch):
    """A model with no corresponding DB table is reported as table_missing."""
    local_base = declarative_base()

    class Orphan(local_base):
        __tablename__ = "no_such_table_in_db"
        id = Column(Integer, primary_key=True)

    engine = create_engine("sqlite:///:memory:")
    # Don't create the table.

    from ospra_os.database import schema_drift as sd
    monkeypatch.setattr(
        sd, "_model_tables",
        lambda: {
            t.name: {c.name for c in t.columns}
            for t in local_base.metadata.sorted_tables
        },
    )

    report = detect_drift(engine)
    assert report.has_drift
    drift = next(
        (t for t in report.tables if t.table == "no_such_table_in_db"), None
    )
    assert drift is not None
    assert drift.table_missing is True


def test_detect_drift_clean_on_aligned_schema(monkeypatch):
    """Model and DB perfectly aligned → empty report, has_drift False."""
    local_base = declarative_base()

    class Aligned(local_base):
        __tablename__ = "aligned"
        id = Column(Integer, primary_key=True)
        name = Column(String(255))

    engine = create_engine("sqlite:///:memory:")
    local_base.metadata.create_all(engine)

    from ospra_os.database import schema_drift as sd
    monkeypatch.setattr(
        sd, "_model_tables",
        lambda: {
            t.name: {c.name for c in t.columns}
            for t in local_base.metadata.sorted_tables
        },
    )

    report = detect_drift(engine)
    assert report.has_drift is False
    assert report.tables == []
