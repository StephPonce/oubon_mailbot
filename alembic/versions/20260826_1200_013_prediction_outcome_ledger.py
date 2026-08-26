"""F1 — the prediction→outcome ledger (D10: the sacred core).

Revision ID: 013
Revises: 012
Create Date: 2026-08-26 12:00:00.000000

Three tables plus an immutability trigger.

The trigger is the point. `grade_snapshots` rows are evidence that a prediction
was made BEFORE its outcome was known — that is their entire value. An ORM
event listener guards the app, but anything issuing raw SQL (a migration, a
psql session, a future service) walks straight past it. The trigger makes the
guarantee a property of the DATABASE rather than a convention.

SQLite gets equivalent triggers so the same rule holds in dev and tests; a
guarantee that only exists in production is one nobody ever exercises.
"""

import sqlalchemy as sa
from alembic import op

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None

_BLOCK_MSG = (
    "grade_snapshots is APPEND-ONLY: write a new snapshot instead of "
    "updating or deleting one"
)


def upgrade() -> None:
    op.create_table(
        "grade_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_key", sa.String(255), nullable=False),
        sa.Column("product_title", sa.String(512), nullable=True),
        sa.Column("niche", sa.String(64), nullable=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("pipeline_run_id", sa.String(64), nullable=False),
        sa.Column("grade", sa.Float(), nullable=True),
        sa.Column("factor_breakdown", sa.JSON(), nullable=True),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(64), nullable=True),
        sa.Column("weights_version", sa.String(64), nullable=True),
        sa.Column("source_manifest", sa.JSON(), nullable=False),
        sa.Column("sources_live", sa.Integer(), nullable=True),
        sa.Column("sources_total", sa.Integer(), nullable=True),
        sa.Column("fit_pass", sa.Boolean(), nullable=True),
        sa.Column("fit_reasons", sa.JSON(), nullable=True),
        sa.Column("deployed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("pipeline_run_id", "product_key",
                            name="uq_grade_snapshot_run_product"),
    )
    op.create_index("ix_grade_snapshots_product_key", "grade_snapshots", ["product_key"])
    op.create_index("ix_grade_snapshots_ts", "grade_snapshots", ["ts"])
    op.create_index("ix_grade_snapshots_pipeline_run_id", "grade_snapshots", ["pipeline_run_id"])
    op.create_index("ix_grade_snapshots_niche", "grade_snapshots", ["niche"])

    op.create_table(
        "product_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_key", sa.String(255), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("sessions", sa.Integer(), nullable=True),
        sa.Column("orders", sa.Integer(), nullable=True),
        sa.Column("units", sa.Integer(), nullable=True),
        sa.Column("revenue", sa.Float(), nullable=True),
        sa.Column("ad_spend", sa.Float(), nullable=True),
        sa.Column("refunds", sa.Float(), nullable=True),
        sa.Column("margin_projected", sa.Float(), nullable=True),
        sa.Column("margin_actual", sa.Float(), nullable=True),
        sa.Column("proxy_ae_velocity", sa.Float(), nullable=True),
        sa.Column("proxy_trend_delta", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("product_key", "period_start",
                            name="uq_product_outcome_period"),
    )
    op.create_index("ix_product_outcomes_product_key", "product_outcomes", ["product_key"])
    op.create_index("ix_product_outcomes_period_start", "product_outcomes", ["period_start"])

    op.create_table(
        "calibration_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_ts", sa.DateTime(), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
        sa.Column("spearman_grade_vs_orders", sa.Float(), nullable=True),
        sa.Column("spearman_grade_vs_proxy", sa.Float(), nullable=True),
        sa.Column("n_products", sa.Integer(), nullable=True),
        sa.Column("n_deployed", sa.Integer(), nullable=True),
        sa.Column("notes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_calibration_reports_run_ts", "calibration_reports", ["run_ts"])

    _create_immutability_guards()


def _create_immutability_guards() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(f"""
            CREATE OR REPLACE FUNCTION ospra_block_grade_snapshot_mutation()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION '{_BLOCK_MSG}';
            END;
            $$ LANGUAGE plpgsql;
        """)
        op.execute("""
            CREATE TRIGGER trg_grade_snapshots_no_update
            BEFORE UPDATE ON grade_snapshots
            FOR EACH ROW EXECUTE FUNCTION ospra_block_grade_snapshot_mutation();
        """)
        op.execute("""
            CREATE TRIGGER trg_grade_snapshots_no_delete
            BEFORE DELETE ON grade_snapshots
            FOR EACH ROW EXECUTE FUNCTION ospra_block_grade_snapshot_mutation();
        """)
    elif dialect == "sqlite":
        op.execute(f"""
            CREATE TRIGGER trg_grade_snapshots_no_update
            BEFORE UPDATE ON grade_snapshots
            BEGIN
                SELECT RAISE(ABORT, '{_BLOCK_MSG}');
            END;
        """)
        op.execute(f"""
            CREATE TRIGGER trg_grade_snapshots_no_delete
            BEFORE DELETE ON grade_snapshots
            BEGIN
                SELECT RAISE(ABORT, '{_BLOCK_MSG}');
            END;
        """)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect in ("postgresql", "sqlite"):
        op.execute("DROP TRIGGER IF EXISTS trg_grade_snapshots_no_update ON grade_snapshots"
                   if dialect == "postgresql"
                   else "DROP TRIGGER IF EXISTS trg_grade_snapshots_no_update")
        op.execute("DROP TRIGGER IF EXISTS trg_grade_snapshots_no_delete ON grade_snapshots"
                   if dialect == "postgresql"
                   else "DROP TRIGGER IF EXISTS trg_grade_snapshots_no_delete")
    if dialect == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS ospra_block_grade_snapshot_mutation()")

    op.drop_index("ix_calibration_reports_run_ts", table_name="calibration_reports")
    op.drop_table("calibration_reports")
    op.drop_index("ix_product_outcomes_period_start", table_name="product_outcomes")
    op.drop_index("ix_product_outcomes_product_key", table_name="product_outcomes")
    op.drop_table("product_outcomes")
    op.drop_index("ix_grade_snapshots_niche", table_name="grade_snapshots")
    op.drop_index("ix_grade_snapshots_pipeline_run_id", table_name="grade_snapshots")
    op.drop_index("ix_grade_snapshots_ts", table_name="grade_snapshots")
    op.drop_index("ix_grade_snapshots_product_key", table_name="grade_snapshots")
    op.drop_table("grade_snapshots")
