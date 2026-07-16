"""Create discovery_jobs (discovery-reliability spec, step 2).

Revision ID: 007
Revises: 006
Create Date: 2026-07-16 00:00:00.000000

Job+poll state for on-demand discovery — replaces the synchronous 45–95s
HTTP cold path that died in the browser/proxy/middleware timeout chain.
Results live in discovered_catalog; this table only tracks run state.
Inspector-guarded like 004–006.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None

TABLE = 'discovery_jobs'


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE in inspector.get_table_names():
        print(f"[MIGRATION 007] {TABLE} already present")
        return

    op.create_table(
        TABLE,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('niche', sa.String(64), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('status', sa.String(16), nullable=False, server_default='queued'),
        sa.Column('error_text', sa.Text(), nullable=True),
        sa.Column('result_count', sa.Integer(), nullable=True),
        sa.Column('requested_by', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_discovery_jobs_niche', TABLE, ['niche'])
    op.create_index('ix_discovery_jobs_status', TABLE, ['status'])
    print(f"[MIGRATION 007] Created {TABLE}")


def downgrade() -> None:
    op.drop_table(TABLE)
