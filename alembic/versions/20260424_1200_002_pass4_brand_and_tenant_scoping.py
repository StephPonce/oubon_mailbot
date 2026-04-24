"""Pass 4 SaaS refactor: brand columns on users + tenant-scope email_followups

Revision ID: 002
Revises: 001
Create Date: 2026-04-24 12:00:00.000000

Adds three nullable columns needed for the multi-tenant rollout of
email automation:

  users.brand_name           VARCHAR(255) NULL
  users.brand_descriptor     VARCHAR(500) NULL
  email_followups.user_id    INTEGER      NULL  FK -> users.id  INDEX

And one composite index on email_followups to keep the follow-up
lookup fast once user_id is in the where-clause:

  idx_email_followup_user_needs (user_id, needs_followup, followup_sent)

All columns are nullable so there is no backfill required. Oubon's
existing rows keep user_id = NULL; application code treats NULL as
"single-tenant mode" and falls through to the old global query path,
so production behavior is unchanged until a tenant is explicitly
assigned.

Implementation notes:
- Every operation is guarded by an introspection check so this
  migration is idempotent / safe to re-run (matches the defensive
  style of revision 001).
- Uses batch_alter_table for the users column additions so this works
  on SQLite (dev) as well as PostgreSQL (prod). email_followups
  add_column + FK is issued directly on Postgres to preserve the FK;
  on SQLite we fall back to a plain column add (SQLite doesn't
  enforce added FKs anyway).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


USERS_TABLE = 'users'
FOLLOWUPS_TABLE = 'email_followups'
FOLLOWUPS_INDEX = 'idx_email_followup_user_needs'
FOLLOWUPS_USER_IX = 'ix_email_followups_user_id'
FOLLOWUPS_FK = 'fk_email_followups_user_id_users'


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
    dialect = bind.dialect.name
    is_sqlite = dialect == 'sqlite'

    # ------------------------------------------------------------------
    # 1. users.brand_name + users.brand_descriptor
    # ------------------------------------------------------------------
    if USERS_TABLE in inspector.get_table_names():
        adds = []
        if not _has_column(inspector, USERS_TABLE, 'brand_name'):
            adds.append(sa.Column('brand_name', sa.String(length=255), nullable=True))
        if not _has_column(inspector, USERS_TABLE, 'brand_descriptor'):
            adds.append(sa.Column('brand_descriptor', sa.String(length=500), nullable=True))

        if adds:
            with op.batch_alter_table(USERS_TABLE) as batch_op:
                for col in adds:
                    batch_op.add_column(col)
            print(f"[MIGRATION 002] Added {len(adds)} brand column(s) to {USERS_TABLE}")
        else:
            print(f"[MIGRATION 002] Brand columns already present on {USERS_TABLE}")
    else:
        print(f"[MIGRATION 002] Skipped: {USERS_TABLE} table not found")

    # ------------------------------------------------------------------
    # 2. email_followups.user_id (+ FK + single-column index)
    # ------------------------------------------------------------------
    if FOLLOWUPS_TABLE in inspector.get_table_names():
        if not _has_column(inspector, FOLLOWUPS_TABLE, 'user_id'):
            if is_sqlite:
                # SQLite: add column without FK (SQLite cannot add FKs via ALTER TABLE;
                # the constraint is not enforced anyway).
                with op.batch_alter_table(FOLLOWUPS_TABLE) as batch_op:
                    batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
            else:
                op.add_column(
                    FOLLOWUPS_TABLE,
                    sa.Column('user_id', sa.Integer(), nullable=True),
                )
                op.create_foreign_key(
                    FOLLOWUPS_FK,
                    FOLLOWUPS_TABLE, USERS_TABLE,
                    ['user_id'], ['id'],
                )
            print(f"[MIGRATION 002] Added user_id to {FOLLOWUPS_TABLE}")
        else:
            print(f"[MIGRATION 002] user_id already present on {FOLLOWUPS_TABLE}")

        # Single-column index on user_id (matches `index=True` on the model).
        # Refresh inspector so we see the column we just added.
        inspector = inspect(bind)
        if not _has_index(inspector, FOLLOWUPS_TABLE, FOLLOWUPS_USER_IX):
            op.create_index(FOLLOWUPS_USER_IX, FOLLOWUPS_TABLE, ['user_id'])
            print(f"[MIGRATION 002] Created index {FOLLOWUPS_USER_IX}")

        # Composite index to keep the follow-up lookup fast under tenant filter.
        if not _has_index(inspector, FOLLOWUPS_TABLE, FOLLOWUPS_INDEX):
            op.create_index(
                FOLLOWUPS_INDEX,
                FOLLOWUPS_TABLE,
                ['user_id', 'needs_followup', 'followup_sent'],
            )
            print(f"[MIGRATION 002] Created index {FOLLOWUPS_INDEX}")
        else:
            print(f"[MIGRATION 002] Composite index already present")
    else:
        print(f"[MIGRATION 002] Skipped: {FOLLOWUPS_TABLE} table not found")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name
    is_sqlite = dialect == 'sqlite'

    # ------------------------------------------------------------------
    # Reverse order: indexes -> FK -> column -> user brand columns
    # ------------------------------------------------------------------
    if FOLLOWUPS_TABLE in inspector.get_table_names():
        if _has_index(inspector, FOLLOWUPS_TABLE, FOLLOWUPS_INDEX):
            op.drop_index(FOLLOWUPS_INDEX, table_name=FOLLOWUPS_TABLE)
        if _has_index(inspector, FOLLOWUPS_TABLE, FOLLOWUPS_USER_IX):
            op.drop_index(FOLLOWUPS_USER_IX, table_name=FOLLOWUPS_TABLE)

        if _has_column(inspector, FOLLOWUPS_TABLE, 'user_id'):
            if is_sqlite:
                with op.batch_alter_table(FOLLOWUPS_TABLE) as batch_op:
                    batch_op.drop_column('user_id')
            else:
                # Drop the FK first on Postgres if it exists; tolerate absence.
                try:
                    op.drop_constraint(FOLLOWUPS_FK, FOLLOWUPS_TABLE, type_='foreignkey')
                except Exception:
                    pass
                op.drop_column(FOLLOWUPS_TABLE, 'user_id')

    if USERS_TABLE in inspector.get_table_names():
        drops = []
        if _has_column(inspector, USERS_TABLE, 'brand_descriptor'):
            drops.append('brand_descriptor')
        if _has_column(inspector, USERS_TABLE, 'brand_name'):
            drops.append('brand_name')
        if drops:
            with op.batch_alter_table(USERS_TABLE) as batch_op:
                for name in drops:
                    batch_op.drop_column(name)
