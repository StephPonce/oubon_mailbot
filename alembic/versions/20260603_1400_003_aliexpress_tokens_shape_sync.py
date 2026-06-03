"""Sync aliexpress_tokens to the active SQLAlchemy model.

Revision ID: 003
Revises: 002
Create Date: 2026-06-03 14:00:00.000000

Two competing class definitions point at the ``aliexpress_tokens`` table:

  * ``ospra_os/aliexpress/oauth.py`` — legacy. Columns: id, access_token,
    refresh_token, expires_at, created_at, updated_at, is_valid.
  * ``ospra_os/database/aliexpress_tokens.py`` — the ACTIVE model used
    by every running code path (``ds_client.py``, ``routes.py``). Columns:
    id, api_type, access_token, refresh_token, obtained_at, expires_in.

Whichever module imports first at boot is whichever model
``Base.metadata.create_all`` materializes. On the Render production DB
that race went the active model's way and the table already has the
right columns. On a local Neon dev DB the race went the LEGACY way, so
every ``load_token('dropship')`` fires:

    column aliexpress_tokens.api_type does not exist

This migration brings the legacy-shape DBs in line with the active
model. It does NOT drop the legacy columns — they are unused but
harmless, and leaving them avoids any risk to a hypothetical instance
that still references them.

Idempotent: every column add is guarded by ``information_schema`` /
inspector checks (matches the defensive style of migrations 001/002).
Safe to re-run.

Nullability: model declares ``api_type``, ``obtained_at``, ``expires_in``
as ``nullable=False``. We add them as nullable at the DB level so this
migration is safe to apply on any DB regardless of whether existing
rows already have these values. The ORM still enforces NOT NULL on new
writes. Prod's columns were created NOT NULL by ``create_all`` long ago
and remain so — this migration is a no-op there.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


TABLE = 'aliexpress_tokens'
NEW_COLUMNS = (
    ('api_type', sa.String(length=50)),
    ('obtained_at', sa.DateTime()),
    ('expires_in', sa.Integer()),
)
UNIQUE_IX = 'ix_aliexpress_tokens_api_type'


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(c['name'] == column for c in inspector.get_columns(table))


def _has_index(inspector, table: str, index: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(ix['name'] == index for ix in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    is_sqlite = bind.dialect.name == 'sqlite'

    if TABLE not in inspector.get_table_names():
        # Fresh DB: the table will be created by Base.metadata.create_all at
        # app boot with the correct shape (the active model's). Nothing for
        # this migration to do.
        print(f"[MIGRATION 003] Skipped: {TABLE} table not found")
        return

    adds = [
        sa.Column(name, type_, nullable=True)
        for name, type_ in NEW_COLUMNS
        if not _has_column(inspector, TABLE, name)
    ]

    if adds:
        if is_sqlite:
            with op.batch_alter_table(TABLE) as batch_op:
                for col in adds:
                    batch_op.add_column(col)
        else:
            for col in adds:
                op.add_column(TABLE, col)
        print(
            f"[MIGRATION 003] Added {len(adds)} column(s) to {TABLE}: "
            f"{[c.name for c in adds]}"
        )
    else:
        print(f"[MIGRATION 003] {TABLE} already has the active-model columns")

    # Active model declares ``api_type`` as unique. Add a unique index if it
    # isn't there yet. Use a named index rather than a UniqueConstraint so it
    # is droppable on SQLite via batch_alter_table without recreating the
    # table.
    inspector = inspect(bind)
    if _has_column(inspector, TABLE, 'api_type') and not _has_index(inspector, TABLE, UNIQUE_IX):
        op.create_index(UNIQUE_IX, TABLE, ['api_type'], unique=True)
        print(f"[MIGRATION 003] Created unique index {UNIQUE_IX}")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    is_sqlite = bind.dialect.name == 'sqlite'

    if TABLE not in inspector.get_table_names():
        return

    if _has_index(inspector, TABLE, UNIQUE_IX):
        op.drop_index(UNIQUE_IX, table_name=TABLE)

    to_drop = [name for name, _ in NEW_COLUMNS if _has_column(inspector, TABLE, name)]
    if not to_drop:
        return

    if is_sqlite:
        with op.batch_alter_table(TABLE) as batch_op:
            for name in to_drop:
                batch_op.drop_column(name)
    else:
        for name in to_drop:
            op.drop_column(TABLE, name)
