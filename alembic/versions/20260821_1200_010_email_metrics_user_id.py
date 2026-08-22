"""Add user_id to email_metrics so the table can be tenant-scoped at all.

Revision ID: 010
Revises: 009
Create Date: 2026-08-21 12:00:00.000000

Why: GET /api/emails/recent returned customer_email + subject for EVERY tenant,
because email_metrics had no owner column — there was nothing to filter on. Auth
was added first (a router-level dependency), but auth alone only narrows the
audience from "the whole internet" to "any logged-in user"; without this column
one tenant still reads another tenant's customer PII.

Rows written before this migration have no known owner. They are left NULL and
the read path treats NULL as UNOWNED — never served to a tenant. That is
deliberately lossy for old rows rather than guessing an owner and attributing
one tenant's customers to another.
"""

import sqlalchemy as sa
from alembic import op

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_metrics",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_email_metrics_user_id", "email_metrics", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_email_metrics_user_id", table_name="email_metrics")
    op.drop_column("email_metrics", "user_id")
