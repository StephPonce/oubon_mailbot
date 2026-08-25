"""Qualitative AI read cache — stop re-deriving identical grok reads.

Revision ID: 011
Revises: 010
Create Date: 2026-08-24 12:00:00.000000

assess_product() runs on the top 10 ranked products of every discovery run with
no cache at all: 5 niches x 2 crons/day x 10 = ~3,000 grok-3 calls/month from
the crons alone, plus every user-triggered search. The catalog is ~100-200
products in steady state with high times_seen, so most of those calls re-derive
an identical answer from identical evidence.
"""

import sqlalchemy as sa
from alembic import op

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qualitative_read_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("product_key", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("assessment", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_hit_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_qualitative_read_cache_cache_key", "qualitative_read_cache",
        ["cache_key"], unique=True,
    )
    op.create_index(
        "ix_qualitative_read_cache_product_key", "qualitative_read_cache", ["product_key"],
    )
    op.create_index(
        "ix_qualitative_read_cache_fetched_at", "qualitative_read_cache", ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_qualitative_read_cache_fetched_at", table_name="qualitative_read_cache")
    op.drop_index("ix_qualitative_read_cache_product_key", table_name="qualitative_read_cache")
    op.drop_index("ix_qualitative_read_cache_cache_key", table_name="qualitative_read_cache")
    op.drop_table("qualitative_read_cache")
