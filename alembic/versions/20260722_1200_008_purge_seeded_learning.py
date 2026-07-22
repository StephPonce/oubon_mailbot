"""Purge seeded learning data — the learning system becomes organic-only.

Revision ID: 008
Revises: 007
Create Date: 2026-07-22 12:00:00.000000

What gets deleted (the December-2025 seed batch):
- product_performance rows dated 2025-12-09 — the one-shot snapshot batch
  written when the learning DB was seeded from Shopify history.
- ai_learning_events with event_type='historical_sale' — ONLY the seeder
  (scripts/seed_learning_from_shopify.py) ever wrote that type; every live
  path writes 'sale'/'first_sale'/'ad_performance'/etc.
- global_learning_weights, all rows — the seeder-derived baseline. The
  analysis job lazily recreates the row from organic events on its next
  run; the 2026-07-15 prod drift audit showed every query against this
  table had been 500ing regardless, so nothing live depends on it.

Companion read-path guard: ORGANIC_SALE_EVENT_TYPES in
ospra_os/database/performance_models.py — even a re-run of the seeder can
no longer feed the learning aggregations.

This is a DATA migration and irreversible by design: downgrade is a no-op
(the seeded rows are reproducible by re-running the seeder; the organic
rows it preserves are not). Deletion counts are printed so the deploy log
records exactly what was removed.

The purge logic lives in plain functions taking a connection so
tests/test_seed_purge.py can exercise the exact predicates against sqlite.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None

SEED_SNAPSHOT_DATE = "2025-12-09"
SEEDED_EVENT_TYPE = "historical_sale"


def purge_seeded_product_performance(bind) -> int:
    res = bind.execute(
        sa.text("DELETE FROM product_performance WHERE date = :d"),
        {"d": SEED_SNAPSHOT_DATE},
    )
    return res.rowcount


def purge_seeded_learning_events(bind) -> int:
    res = bind.execute(
        sa.text("DELETE FROM ai_learning_events WHERE event_type = :t"),
        {"t": SEEDED_EVENT_TYPE},
    )
    return res.rowcount


def purge_global_learning_weights(bind) -> int:
    res = bind.execute(sa.text("DELETE FROM global_learning_weights"))
    return res.rowcount


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    for table, purge in (
        ("product_performance", purge_seeded_product_performance),
        ("ai_learning_events", purge_seeded_learning_events),
        ("global_learning_weights", purge_global_learning_weights),
    ):
        if table not in tables:
            print(f"[MIGRATION 008] Skipped: {table} not found")
            continue
        deleted = purge(bind)
        print(f"[MIGRATION 008] {table}: {deleted} seeded row(s) purged")


def downgrade() -> None:
    # Irreversible data migration — see module docstring.
    print("[MIGRATION 008] downgrade is a no-op (purged seed data is not restored)")
