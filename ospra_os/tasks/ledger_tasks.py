"""F1 — outcome aggregation and weekly calibration.

Two scheduled jobs close the prediction→outcome loop:

  aggregate_product_outcomes  — roll a week of reality up per product_key
  run_weekly_calibration      — ask whether the grade actually predicted it

REAL vs PROXY outcomes. A deployed product has real commerce data (orders,
revenue, ad spend). An UNDEPLOYED one has none — and if only deployed products
could ever be validated, the engine could only ever be graded on the handful of
things we happened to pick, which is survivorship bias baked into the metric.
So undeployed products get proxy outcomes from the signal timeseries. That is
what makes the pets paper-trade (F8/D6) possible: predict, don't deploy, and
still find out whether the prediction was right.

Proxies are written to `proxy_*` columns and correlated separately from real
orders. They are never mixed into the real-orders correlation — a proxy is
evidence about the market, not a sale, and blending them would produce a
flattering number that means nothing.
"""

import logging
from datetime import datetime, timedelta

from ospra_os.celery_app import celery_app

logger = logging.getLogger(__name__)

# Proxy velocity needs two readings to form a delta. With fewer, the honest
# answer is "unknown" (NULL), not zero.
_MIN_TIMESERIES_POINTS = 2


def _session():
    from ospra_os.database.connection import SessionLocal
    return SessionLocal()


def _period_bounds(period_days: int, end: datetime | None = None):
    """The window, snapped to whole UTC days and covering COMPLETE days only.

    Snapping is load-bearing, not cosmetic. An unsnapped `utcnow()` carries
    microseconds, so every run computes a slightly different period_start — the
    upsert then never matches the existing row and outcomes duplicate silently,
    week over week, with the (product_key, period_start) unique constraint
    powerless to notice. Snapping also excludes today's partial day, so a
    rollup is never a fraction of a day pretending to be a whole one; today's
    data is picked up by the next run's window.
    """
    end = end or datetime.utcnow()
    end = end.replace(hour=0, minute=0, second=0, microsecond=0)
    return end - timedelta(days=period_days), end


def _upsert_outcome(session, product_key: str, period_start, period_end, values: dict):
    """Write or update one outcome row.

    product_outcomes is NOT append-only (unlike grade_snapshots): reality gets
    restated — refunds land late, ad spend reconciles — and an outcome is a
    measurement, not a prediction. Only the PREDICTION side must be immutable.
    """
    from ospra_os.database.ledger_models import ProductOutcome

    row = (
        session.query(ProductOutcome)
        .filter(
            ProductOutcome.product_key == product_key,
            ProductOutcome.period_start == period_start,
        )
        .first()
    )
    if row is None:
        row = ProductOutcome(
            product_key=product_key,
            period_start=period_start,
            period_end=period_end,
        )
        session.add(row)
    for k, v in values.items():
        if v is not None:
            setattr(row, k, v)
    row.period_end = period_end
    return row


def _real_outcomes(session, period_start, period_end) -> int:
    """Aggregate ProductPerformance (real Shopify sales) per product_key."""
    from ospra_os.database.performance_models import ProductPerformance
    from ospra_os.database.product_models import Product

    # Only products that carry a discovery key can be attributed to a
    # prediction. Products deployed before migration 014 have NULL keys — they
    # are genuinely un-attributable and are skipped rather than guessed at.
    keyed = (
        session.query(Product.id, Product.product_key)
        .filter(Product.product_key.isnot(None))
        .all()
    )
    if not keyed:
        return 0
    key_by_id = {pid: pkey for pid, pkey in keyed}

    rows = (
        session.query(ProductPerformance)
        .filter(
            ProductPerformance.product_id.in_(list(key_by_id.keys())),
            ProductPerformance.date >= period_start.date(),
            ProductPerformance.date < period_end.date(),
        )
        .all()
    )

    agg: dict = {}
    for r in rows:
        pkey = key_by_id.get(r.product_id)
        if not pkey:
            continue
        a = agg.setdefault(pkey, {
            "orders": 0, "units": 0, "revenue": 0.0,
            "ad_spend": 0.0, "refunds": 0.0, "sessions": 0,
            "cost": 0.0,
        })
        a["orders"] += r.orders or 0
        a["units"] += r.units_sold or 0
        a["revenue"] += r.gross_revenue or 0.0
        a["ad_spend"] += r.ad_spend or 0.0
        a["refunds"] += r.refunds or 0.0
        a["sessions"] += r.views or 0
        a["cost"] += r.total_cost or 0.0

    written = 0
    for pkey, a in agg.items():
        revenue = a["revenue"]
        # margin_actual only when there was revenue to take a margin ON.
        # A margin of 0.0 on zero revenue is a fabricated data point.
        #
        # ad_spend is ALREADY inside `cost` (ProductPerformance.total_cost
        # includes it — see analytics_tasks._attribute_spend_to_products and
        # sales_sync_service). It is also stored separately on the outcome for
        # visibility. Do NOT subtract a["ad_spend"] here as well; that would
        # double-count ad cost and understate every margin.
        margin_actual = (
            ((revenue - a["cost"] - a["refunds"]) / revenue) * 100.0
            if revenue > 0 else None
        )
        _upsert_outcome(session, pkey, period_start, period_end, {
            "orders": a["orders"],
            "units": a["units"],
            "revenue": revenue,
            "ad_spend": a["ad_spend"],
            "refunds": a["refunds"],
            "sessions": a["sessions"] or None,
            "margin_actual": margin_actual,
        })
        written += 1
    return written


def _proxy_outcomes(session, period_start, period_end) -> int:
    """Proxy outcomes for products we graded but did NOT deploy.

    Uses the signal timeseries the catalog cron already writes, so this costs
    no API calls. Two proxies, both deltas over the period rather than levels —
    a level says how big a market is, a delta says whether our call was timed
    right, which is what the grade actually claims.
    """
    from ospra_os.database.ledger_models import GradeSnapshot
    from ospra_os.database.product_timeseries import ProductTimeseries

    graded_keys = {
        k for (k,) in session.query(GradeSnapshot.product_key)
        .filter(GradeSnapshot.ts >= period_start - timedelta(days=60))
        .distinct()
        .all()
    }
    if not graded_keys:
        return 0

    series = (
        session.query(ProductTimeseries)
        .filter(
            ProductTimeseries.product_key.in_(list(graded_keys)),
            ProductTimeseries.snapshot_date >= period_start.date(),
            ProductTimeseries.snapshot_date < period_end.date(),
        )
        .order_by(ProductTimeseries.snapshot_date.asc())
        .all()
    )

    by_key: dict = {}
    for row in series:
        by_key.setdefault(row.product_key, []).append(row)

    written = 0
    for pkey, points in by_key.items():
        if len(points) < _MIN_TIMESERIES_POINTS:
            continue

        def _delta(attr):
            vals = [(p.snapshot_date, getattr(p, attr)) for p in points]
            vals = [(d, v) for d, v in vals if v is not None]
            if len(vals) < _MIN_TIMESERIES_POINTS:
                return None
            span_days = max((vals[-1][0] - vals[0][0]).days, 1)
            return round((vals[-1][1] - vals[0][1]) / span_days, 4)

        ae_velocity = _delta("aliexpress_orders")
        trend_delta = _delta("google_trends_interest")
        if ae_velocity is None and trend_delta is None:
            continue

        _upsert_outcome(session, pkey, period_start, period_end, {
            "proxy_ae_velocity": ae_velocity,
            "proxy_trend_delta": trend_delta,
        })
        written += 1
    return written


@celery_app.task(name="ospra_os.tasks.ledger_tasks.aggregate_product_outcomes")
def aggregate_product_outcomes(period_days: int = 7) -> dict:
    """Weekly: roll reality up per product_key, real and proxy."""
    period_start, period_end = _period_bounds(period_days)
    session = _session()
    try:
        real = _real_outcomes(session, period_start, period_end)
        proxy = _proxy_outcomes(session, period_start, period_end)
        session.commit()
        logger.info(
            "[LEDGER] outcomes aggregated: %d real, %d proxy (%s → %s)",
            real, proxy, period_start.date(), period_end.date(),
        )
        return {
            "success": True,
            "real_outcomes": real,
            "proxy_outcomes": proxy,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }
    except Exception as exc:
        session.rollback()
        logger.error("[LEDGER] outcome aggregation FAILED: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}
    finally:
        session.close()


@celery_app.task(name="ospra_os.tasks.ledger_tasks.run_weekly_calibration")
def run_weekly_calibration(window_days: int = 28) -> dict:
    """Weekly: does the grade predict the outcome? Logged either way.

    Runs AFTER aggregation in the beat schedule so it reads the week just
    closed rather than correlating against stale outcomes.
    """
    from ospra_os.intelligence.ledger import compute_calibration

    try:
        report = compute_calibration(window_days=window_days, persist=True)
        return {
            "success": True,
            "spearman_grade_vs_orders": report["spearman_grade_vs_orders"],
            "spearman_grade_vs_proxy": report["spearman_grade_vs_proxy"],
            "n_products": report["n_products"],
            "verdict": report["notes"]["verdict"],
        }
    except Exception as exc:
        logger.error("[LEDGER] calibration FAILED: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}
