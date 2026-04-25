"""
Schema drift detector.

Catches the failure mode that bit us during the SaaS-launch refactor:
``brand_name`` and ``brand_descriptor`` were added to the ``User`` ORM
model but the live Postgres ``users`` table was created before those
columns existed. ``Base.metadata.create_all`` only CREATES missing
tables — it never ALTERs an existing one — so the drift was invisible
until login fired ``SELECT users.brand_name, ...`` and got a 500.

This module compares every Base-mapped table's column list against the
live database and reports the diff. It does NOT auto-apply fixes —
Postgres ALTER TABLE is the kind of operation you want a human
authorizing — but it surfaces the gap so you can catch it at boot
instead of at request time.

Usage at startup (already wired into ``_run_startup_critical``):
    from ospra_os.database.schema_drift import warn_on_drift
    warn_on_drift()

Usage from CLI (``make schema-check``):
    python -m ospra_os.database.schema_drift
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from ospra_os.database.base import Base
from ospra_os.database.connection import get_engine

logger = logging.getLogger(__name__)


@dataclass
class TableDrift:
    """Per-table diff between the ORM model and the live DB."""

    table: str
    missing_in_db: list[str] = field(default_factory=list)   # model has → db doesn't
    extra_in_db: list[str] = field(default_factory=list)     # db has → model doesn't
    table_missing: bool = False                              # whole table absent in DB

    @property
    def has_drift(self) -> bool:
        return bool(
            self.missing_in_db or self.extra_in_db or self.table_missing
        )


@dataclass
class DriftReport:
    """Whole-database drift summary."""

    tables: list[TableDrift] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return any(t.has_drift for t in self.tables)

    def render(self) -> str:
        """Human-readable rendering for logs / CLI / startup banners."""
        if not self.has_drift:
            return "schema_drift: clean — every model column exists in the live DB"

        lines = ["Schema drift detected:"]
        for t in self.tables:
            if t.table_missing:
                lines.append(f"  · table '{t.table}' is missing entirely")
                continue
            if t.missing_in_db:
                lines.append(
                    f"  · table '{t.table}': model defines columns the DB does not have:"
                )
                for col in t.missing_in_db:
                    lines.append(f"      - {col}")
            if t.extra_in_db:
                # ``extra_in_db`` is informational — usually a column dropped from the
                # model but left in the DB for backfill safety. Surface it but don't
                # treat it as urgent.
                lines.append(
                    f"  · table '{t.table}': DB has columns the model no longer "
                    "declares (likely safe — left for backfill):"
                )
                for col in t.extra_in_db:
                    lines.append(f"      - {col}")
        lines.append(
            "\nResolution: run an ALTER TABLE per missing column, OR re-run\n"
            "Alembic migrations, OR (dev only) drop and recreate the offending\n"
            "tables. See docs/LOCAL_DEV.md and ``alembic.ini``."
        )
        return "\n".join(lines)


def _model_tables() -> dict[str, set[str]]:
    """All Base-registered tables → their model-declared column names."""
    return {
        table.name: {col.name for col in table.columns}
        for table in Base.metadata.sorted_tables
    }


def _live_tables(engine: Engine) -> dict[str, set[str]]:
    """All tables that actually exist in the connected DB → their column names."""
    inspector = inspect(engine)
    out: dict[str, set[str]] = {}
    for tname in inspector.get_table_names():
        out[tname] = {col["name"] for col in inspector.get_columns(tname)}
    return out


def detect_drift(engine: Engine | None = None) -> DriftReport:
    """
    Compare every Base table against the live database.

    Returns a ``DriftReport`` — never raises. Connection failures are
    logged at WARNING and produce an empty report (the caller decides
    whether that's acceptable).
    """
    try:
        engine = engine or get_engine()
        live = _live_tables(engine)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("schema_drift: could not inspect live database: %s", exc)
        return DriftReport()

    model = _model_tables()
    report = DriftReport()

    for table_name, model_cols in model.items():
        # SQLite-only tables (e.g. orders kept in product_history.db) live
        # outside the main engine and won't appear in ``live`` — skip.
        if table_name not in live:
            # Distinguish "table never created in this engine" from
            # "table genuinely missing in a DB that should have it."
            # We err on the loud side: report it, let the operator
            # decide. Filtering would mask real drift.
            report.tables.append(TableDrift(table=table_name, table_missing=True))
            continue

        live_cols = live[table_name]
        missing = sorted(model_cols - live_cols)
        extra = sorted(live_cols - model_cols)

        if missing or extra:
            report.tables.append(
                TableDrift(
                    table=table_name,
                    missing_in_db=missing,
                    extra_in_db=extra,
                )
            )

    return report


def warn_on_drift(engine: Engine | None = None) -> DriftReport:
    """
    Run ``detect_drift`` and emit one log message per problematic table.

    Called from ``_run_startup_critical``. Drift is logged at WARNING
    (not ERROR) because it doesn't necessarily mean the app is broken —
    a missing column only matters if a query selects it. But every
    operator should see it.
    """
    report = detect_drift(engine)
    if report.has_drift:
        # One big formatted block — much easier to spot in tail-f than
        # one warning per table.
        logger.warning("\n" + report.render())
    else:
        logger.debug("schema_drift: clean")
    return report


def _main() -> int:
    """CLI entry. Exit code 0 = clean, 1 = drift, 2 = couldn't connect."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        engine = get_engine()
    except Exception as exc:
        print(f"schema_drift: could not connect to DB: {exc}", file=sys.stderr)
        return 2

    report = detect_drift(engine)
    print(report.render())
    return 1 if report.has_drift else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
