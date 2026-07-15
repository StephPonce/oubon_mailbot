"""Add product_timeseries.store_carry_count (Moat Phase 3 — timing signal).

Revision ID: 006
Revises: 005
Create Date: 2026-07-15 15:00:00.000000

Daily count of distinct public Shopify catalogs ({store}/products.json)
carrying the product — the store-carry half of the early-adopter signal.
Nullable: NULL = not measured that day (never a fabricated zero), matching
the table's signal-column convention. Inspector-guarded like 004/005.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None

TABLE = 'product_timeseries'
COLUMN = 'store_carry_count'


def _has_column(inspector, table, column) -> bool:
    try:
        return any(c['name'] == column for c in inspector.get_columns(table))
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if TABLE not in inspector.get_table_names():
        print(f"[MIGRATION 006] Skipped: {TABLE} table not found")
        return
    if _has_column(inspector, TABLE, COLUMN):
        print(f"[MIGRATION 006] {TABLE}.{COLUMN} already present")
        return

    col = sa.Column(COLUMN, sa.Integer(), nullable=True)
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(TABLE, col)
    print(f"[MIGRATION 006] Added {TABLE}.{COLUMN}")


def downgrade() -> None:
    if op.get_bind().dialect.name == 'sqlite':
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.drop_column(COLUMN)
    else:
        op.drop_column(TABLE, COLUMN)
