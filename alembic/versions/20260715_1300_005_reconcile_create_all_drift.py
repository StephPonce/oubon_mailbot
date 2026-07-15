"""Reconcile create_all drift: add 34 columns missing from 4 prod tables.

Revision ID: 005
Revises: 004
Create Date: 2026-07-15 13:00:00.000000

Production tables were materialized by ``Base.metadata.create_all`` with
whatever the models looked like at first boot, and create_all never ALTERs.
An ``inspect()`` sweep found 34 model columns absent from 4 tables
(auto_pilot_logs, ai_learning_events, global_learning_weights,
personal_learning_weights) — each one a latent 500 for its feature the
first time a query SELECTs it. The DB is not cleanly "at" any revision, so
this migration reconciles by inspection: every ADD is guarded by a live
column check and skipped when already present, making it safe on prod, on
fresh DBs, and on dev SQLite alike.

Type/default notes:
- Columns that are NOT NULL in the model but have no server default are
  added NULLABLE here (only auto_pilot_logs.action_type) so the ADD cannot
  fail on populated tables; the ORM still populates them on new writes.
- Counter/flag columns get a server_default matching the ORM default so
  existing rows backfill to sane values (0 / false / 0.5).
- timestamp/created_at columns get server_default now() so existing rows
  aren't NULL under queries that ORDER BY them.
- JSON payload columns are added nullable with no server default; the ORM
  ``default=dict/list`` governs new rows, and readers already tolerate
  missing payloads (the features never worked against these tables).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def _dt():
    return sa.DateTime()


# table -> [(column_name, type, kwargs)]
MISSING = {
    'auto_pilot_logs': [
        # NOT NULL in the model, but added nullable so populated tables accept it.
        ('action_type', sa.String(50), {'nullable': True}),
        ('was_executed', sa.Boolean(), {'nullable': True, 'server_default': sa.false()}),
        ('threshold', sa.Float(), {'nullable': True}),
        ('success', sa.Boolean(), {'nullable': True}),
        ('error_message', sa.Text(), {'nullable': True}),
        ('execution_time_ms', sa.Integer(), {'nullable': True}),
    ],
    'ai_learning_events': [
        ('product_id', sa.String(100), {'nullable': True}),
        ('details', sa.JSON(), {'nullable': True}),
        ('timestamp', sa.DateTime(), {'nullable': True, 'server_default': sa.func.now()}),
    ],
    'global_learning_weights': [
        ('learning_cycles', sa.Integer(), {'nullable': True, 'server_default': '0'}),
        ('scoring_weights', sa.JSON(), {'nullable': True}),
        ('niche_confidence', sa.JSON(), {'nullable': True}),
        ('price_confidence', sa.JSON(), {'nullable': True}),
        ('trend_velocity', sa.JSON(), {'nullable': True}),
        ('accuracy', sa.JSON(), {'nullable': True}),
        ('total_users_contributing', sa.Integer(), {'nullable': True, 'server_default': '0'}),
        ('total_sales_analyzed', sa.Integer(), {'nullable': True, 'server_default': '0'}),
        ('total_revenue_analyzed', sa.Float(), {'nullable': True, 'server_default': '0'}),
        ('created_at', sa.DateTime(), {'nullable': True, 'server_default': sa.func.now()}),
    ],
    'personal_learning_weights': [
        ('learning_cycles', sa.Integer(), {'nullable': True, 'server_default': '0'}),
        ('scoring_adjustments', sa.JSON(), {'nullable': True}),
        ('niche_adjustments', sa.JSON(), {'nullable': True}),
        ('price_adjustments', sa.JSON(), {'nullable': True}),
        ('best_performing_niches', sa.JSON(), {'nullable': True}),
        ('optimal_price_range', sa.JSON(), {'nullable': True}),
        ('peak_selling_days', sa.JSON(), {'nullable': True}),
        ('predictions_made', sa.Integer(), {'nullable': True, 'server_default': '0'}),
        ('predictions_correct', sa.Integer(), {'nullable': True, 'server_default': '0'}),
        ('accuracy_rate', sa.Float(), {'nullable': True, 'server_default': '0.5'}),
        ('sales_analyzed', sa.Integer(), {'nullable': True, 'server_default': '0'}),
        ('revenue_analyzed', sa.Float(), {'nullable': True, 'server_default': '0'}),
        ('custom_weights_enabled', sa.Boolean(), {'nullable': True, 'server_default': sa.false()}),
        ('custom_weights', sa.JSON(), {'nullable': True}),
        ('created_at', sa.DateTime(), {'nullable': True, 'server_default': sa.func.now()}),
    ],
}

# Model-declared indexes on newly added columns; created only if the column
# was just added and the index name is absent.
INDEXES = [
    ('idx_learning_product', 'ai_learning_events', ['product_id']),
    ('idx_learning_timestamp', 'ai_learning_events', ['timestamp']),
]


def _existing_columns(inspector, table):
    try:
        return {c['name'] for c in inspector.get_columns(table)}
    except Exception:
        return set()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    is_sqlite = bind.dialect.name == 'sqlite'
    tables = set(inspector.get_table_names())

    added_total = 0
    for table, columns in MISSING.items():
        if table not in tables:
            # Fresh DB: create_all materializes the full table at boot.
            print(f"[MIGRATION 005] Skipped {table}: table not found")
            continue
        present = _existing_columns(inspector, table)
        to_add = [
            sa.Column(name, type_, **kwargs)
            for name, type_, kwargs in columns
            if name not in present
        ]
        if not to_add:
            print(f"[MIGRATION 005] {table}: all columns already present")
            continue
        if is_sqlite:
            with op.batch_alter_table(table) as batch_op:
                for col in to_add:
                    batch_op.add_column(col)
        else:
            for col in to_add:
                op.add_column(table, col)
        added_total += len(to_add)
        print(f"[MIGRATION 005] {table}: added {[c.name for c in to_add]}")

    # Refresh inspector after DDL, then backfill model-declared indexes.
    inspector = inspect(bind)
    for index_name, table, cols in INDEXES:
        if table not in tables:
            continue
        try:
            existing_indexes = {ix['name'] for ix in inspector.get_indexes(table)}
        except Exception:
            existing_indexes = set()
        if index_name in existing_indexes:
            continue
        if not set(cols) <= _existing_columns(inspector, table):
            continue
        op.create_index(index_name, table, cols)
        print(f"[MIGRATION 005] {table}: created index {index_name}")

    print(f"[MIGRATION 005] Done — {added_total} column(s) added")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    is_sqlite = bind.dialect.name == 'sqlite'
    tables = set(inspector.get_table_names())

    for index_name, table, _cols in INDEXES:
        if table not in tables:
            continue
        try:
            existing_indexes = {ix['name'] for ix in inspector.get_indexes(table)}
        except Exception:
            existing_indexes = set()
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=table)

    for table, columns in MISSING.items():
        if table not in tables:
            continue
        present = _existing_columns(inspector, table)
        names = [name for name, _t, _k in columns if name in present]
        if not names:
            continue
        if is_sqlite:
            with op.batch_alter_table(table) as batch_op:
                for name in names:
                    batch_op.drop_column(name)
        else:
            for name in names:
                op.drop_column(table, name)
