"""AliExpress DS detail cache — persist real merchant prices across processes.

Revision ID: 012
Revises: 011
Create Date: 2026-08-24 14:00:00.000000

ds_client's detail cache is an in-process dict, and catalog_warm is a fresh
process per cron run — so where the volume is, it started empty every time
(~3,000 calls/month at ~100% miss).

The wasted calls matter less than the failure they cause: enrich_pricing is a
serial await loop inside a 30s wrapper, so a couple of slow calls cancel ALL
pricing and every product silently keeps the inflated heuristic cost basis.
"""

import sqlalchemy as sa
from alembic import op

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ae_ds_detail_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("country", sa.String(8), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_hit_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_ae_ds_detail_cache_cache_key", "ae_ds_detail_cache",
        ["cache_key"], unique=True,
    )
    op.create_index(
        "ix_ae_ds_detail_cache_product_id", "ae_ds_detail_cache", ["product_id"],
    )
    op.create_index(
        "ix_ae_ds_detail_cache_fetched_at", "ae_ds_detail_cache", ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ae_ds_detail_cache_fetched_at", table_name="ae_ds_detail_cache")
    op.drop_index("ix_ae_ds_detail_cache_product_id", table_name="ae_ds_detail_cache")
    op.drop_index("ix_ae_ds_detail_cache_cache_key", table_name="ae_ds_detail_cache")
    op.drop_table("ae_ds_detail_cache")
