"""Apify response cache — persist actor responses across processes.

Revision ID: 009
Revises: 008
Create Date: 2026-07-28 15:00:00.000000

Why: catalog_warm re-asked ~25 DISTINCT Meta Ad Library sub-queries ~60x/month
(5 niches x 5 sub-queries x 2 runs/day) because nothing survived the cron
process. That burned the $45/month Apify cap three weeks into the cycle; the
resulting 403 blackout then blanked the winner-proof signal on every product.

This table lets run_actor answer a repeated question from Postgres instead of a
metered actor start, and lets an expired row serve as a degraded (marked-stale)
answer during a quota outage.
"""

import sqlalchemy as sa
from alembic import op

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "apify_response_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("run_input_summary", sa.String(512), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_hit_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_apify_response_cache_cache_key", "apify_response_cache",
        ["cache_key"], unique=True,
    )
    op.create_index(
        "ix_apify_response_cache_actor_id", "apify_response_cache", ["actor_id"],
    )
    op.create_index(
        "ix_apify_response_cache_fetched_at", "apify_response_cache", ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_apify_response_cache_fetched_at", table_name="apify_response_cache")
    op.drop_index("ix_apify_response_cache_actor_id", table_name="apify_response_cache")
    op.drop_index("ix_apify_response_cache_cache_key", table_name="apify_response_cache")
    op.drop_table("apify_response_cache")
