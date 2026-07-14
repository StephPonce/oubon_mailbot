"""Add users.is_admin boolean (Section A/C admin flag).

Revision ID: 004
Revises: 003
Create Date: 2026-07-13 20:00:00.000000

Section C's admin gates (require_admin_user, whitelabel/monitoring/token
routers) and Section A's T4/T51 fixes check ``user.is_admin`` — the real,
deny-by-default admin signal that replaced the fake 'stratosphere == admin'
and 'admin-key-placeholder' checks. Until this column exists, getattr on the
ORM object returns False for everyone, so every admin route 403s.

This adds the column with a default of False (nobody is admin until an
operator flips their own row). Idempotent + inspector-guarded, matching the
defensive style of migrations 001-003.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

TABLE = 'users'
COLUMN = 'is_admin'


def _has_column(inspector, table, column) -> bool:
    try:
        return any(c['name'] == column for c in inspector.get_columns(table))
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    is_sqlite = bind.dialect.name == 'sqlite'

    if TABLE not in inspector.get_table_names():
        # Fresh DB: Base.metadata.create_all materializes the column at boot.
        print(f"[MIGRATION 004] Skipped: {TABLE} table not found")
        return

    if _has_column(inspector, TABLE, COLUMN):
        print(f"[MIGRATION 004] {TABLE}.{COLUMN} already present")
        return

    # server_default='0' so existing rows backfill to non-admin without a
    # separate UPDATE; the model's default=False governs new rows.
    col = sa.Column(COLUMN, sa.Boolean(), nullable=False, server_default=sa.false())
    if is_sqlite:
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(TABLE, col)
    print(f"[MIGRATION 004] Added {TABLE}.{COLUMN} (default False)")


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    if is_sqlite:
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.drop_column(COLUMN)
    else:
        op.drop_column(TABLE, COLUMN)
