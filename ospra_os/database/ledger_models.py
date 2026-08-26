"""
F1 — THE PREDICTION→OUTCOME LEDGER (D10: the sacred core).

An append-only record of what the engine predicted, AT THE MOMENT it predicted
it, joined later to what actually happened. Today Ospra makes predictions and
remembers nothing; this is its memory and its accountability.

THE CENTRAL RULE: `grade_snapshots` is APPEND-ONLY. A snapshot is NEVER
updated, regenerated, or backfilled — its entire value is being provably
written BEFORE the outcome was known. A backfilled snapshot is worthless as
evidence and worse than none, because it looks like evidence. Immutability is
enforced twice: in code (`_block_snapshot_mutation` below) and by a DB trigger
(migration 013).

DISTINCT FROM `RecommendationOutcome` (performance_models.py), which is keyed on
(user_id, action_id) and only exists once a USER ACCEPTS a recommendation. F1
records EVERY product the engine evaluated — including fit-gate rejects and
products never deployed. What we did NOT pick is signal too.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, JSON, String, UniqueConstraint,
    event,
)
from sqlalchemy.orm import Session

from ospra_os.database.base import Base


class LedgerImmutabilityError(RuntimeError):
    """Raised when something tries to mutate or delete a grade snapshot."""


class GradeSnapshot(Base):
    """One row per product per grading run. Written, never touched again."""

    __tablename__ = "grade_snapshots"

    id = Column(Integer, primary_key=True)

    # Shared identity key (database/product_timeseries.product_identity_key) so
    # snapshots join to outcomes and timeseries without drift.
    product_key = Column(String(255), nullable=False, index=True)
    product_title = Column(String(512), nullable=True)
    niche = Column(String(64), nullable=True, index=True)

    # When the prediction was made. Indexed — every receipts query is a range
    # over this column.
    ts = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)

    # Groups every snapshot written by one pipeline execution, so a bad run can
    # be excluded from calibration wholesale rather than row by row.
    pipeline_run_id = Column(String(64), nullable=False, index=True)

    # The prediction itself.
    grade = Column(Float, nullable=True)
    factor_breakdown = Column(JSON, nullable=True)

    # Versioning: a grade is only comparable to another grade from the same
    # model + prompt + weights. F7 changes weights; without this, calibration
    # silently mixes incompatible scores.
    model_version = Column(String(64), nullable=True)
    prompt_version = Column(String(64), nullable=True)
    weights_version = Column(String(64), nullable=True)

    # WHICH SOURCES ACTUALLY RETURNED DATA. A grade computed with 3 of 10
    # sources dead must be identifiable or it pollutes calibration — this is
    # the "silent API failure" disease (handoff, known flaw #3) made visible.
    source_manifest = Column(JSON, nullable=False, default=dict)
    sources_live = Column(Integer, nullable=True)
    sources_total = Column(Integer, nullable=True)

    # F2 fit gate. Rejects are logged too — they are training data.
    fit_pass = Column(Boolean, nullable=True)
    fit_reasons = Column(JSON, nullable=True)

    deployed = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        # One snapshot per product per run. A retry cannot silently double-count
        # a product in calibration.
        UniqueConstraint("pipeline_run_id", "product_key",
                         name="uq_grade_snapshot_run_product"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<GradeSnapshot {self.product_key!r} grade={self.grade} "
            f"run={self.pipeline_run_id!r} ts={self.ts}>"
        )


class ProductOutcome(Base):
    """What actually happened, per product per period. Comes from REALITY
    (Shopify webhooks, ad spend), never from the engine's own opinion."""

    __tablename__ = "product_outcomes"

    id = Column(Integer, primary_key=True)

    product_key = Column(String(255), nullable=False, index=True)
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)

    # Real commerce results.
    sessions = Column(Integer, nullable=True)
    orders = Column(Integer, nullable=True)
    units = Column(Integer, nullable=True)
    revenue = Column(Float, nullable=True)
    ad_spend = Column(Float, nullable=True)
    refunds = Column(Float, nullable=True)

    # Projected vs actual — the profit calculator's own report card.
    margin_projected = Column(Float, nullable=True)
    margin_actual = Column(Float, nullable=True)

    # Proxies for UNDEPLOYED products (paper-trading, F8). Without these, only
    # deployed products could ever be validated and the pets test is impossible.
    proxy_ae_velocity = Column(Float, nullable=True)
    proxy_trend_delta = Column(Float, nullable=True)

    # Every metric above is NULLABLE on purpose: a missing measurement must
    # read as unknown, never as a zero that drags a correlation.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("product_key", "period_start",
                         name="uq_product_outcome_period"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ProductOutcome {self.product_key!r} "
            f"{self.period_start:%Y-%m-%d} orders={self.orders}>"
        )


class CalibrationReport(Base):
    """Weekly: does grade actually predict outcome? The honest answer, logged
    whether it flatters us or not."""

    __tablename__ = "calibration_reports"

    id = Column(Integer, primary_key=True)
    run_ts = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)

    # Spearman RANK correlation: grades are ordinal, and rank correlation does
    # not assume the grade→orders relationship is linear.
    spearman_grade_vs_orders = Column(Float, nullable=True)
    spearman_grade_vs_proxy = Column(Float, nullable=True)

    # Sample size is not optional context — a 0.8 correlation on n=4 is noise.
    n_products = Column(Integer, nullable=True)
    n_deployed = Column(Integer, nullable=True)

    notes = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<CalibrationReport {self.run_ts:%Y-%m-%d} "
            f"rho={self.spearman_grade_vs_orders} n={self.n_products}>"
        )


# ---------------------------------------------------------------------------
# Immutability enforcement (layer 1 of 2 — the DB trigger in migration 013 is
# layer 2, because ORM guards do not protect against raw SQL).
# ---------------------------------------------------------------------------

def _block_snapshot_mutation(mapper, connection, target):  # pragma: no cover
    raise LedgerImmutabilityError(
        "grade_snapshots is APPEND-ONLY. A snapshot's value is being provably "
        "written before the outcome was known; updating or deleting one "
        "destroys that guarantee. Write a NEW snapshot with a new "
        "pipeline_run_id instead."
    )


event.listen(GradeSnapshot, "before_update", _block_snapshot_mutation)
event.listen(GradeSnapshot, "before_delete", _block_snapshot_mutation)


def assert_append_only(session: Session) -> None:
    """Raise if the session has pending snapshot mutations. Call before commit
    in code paths that touch the ledger."""
    for obj in session.dirty:
        if isinstance(obj, GradeSnapshot):
            _block_snapshot_mutation(None, None, obj)
    for obj in session.deleted:
        if isinstance(obj, GradeSnapshot):
            _block_snapshot_mutation(None, None, obj)
