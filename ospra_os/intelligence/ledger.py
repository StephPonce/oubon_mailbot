"""
F1 — prediction→outcome ledger write path and receipts query.

The discovery/grading run calls `record_run()` once per run with every product
it EVALUATED — including fit-gate rejects and products that were never
deployed. What we did not pick is signal too, and a ledger of only our winners
is a highlight reel, not evidence.

Loud failures only (spec rule): a snapshot insert failure raises. Silently
skipping a snapshot is how the ledger becomes quietly incomplete, and an
incomplete ledger produces a calibration number nobody can trust — which is
worse than no number.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# The sources the grade is meant to draw on. These names are NOT invented here —
# they are exactly the keys `product_discovery` writes into
# `data_coverage['by_source']` (see the `coverage['...'] = ` block in
# product_discovery.py). A name that does not match that dict silently reports
# "absent" for a source that actually ran, which would understate coverage on
# every snapshot and quietly poison the very audit this manifest exists for.
#
# reddit/twitter remain because discovery still emits those keys; both now
# always resolve to "n/a" (retired per D15 — do not resurrect).
KNOWN_SOURCES = (
    "aliexpress",
    "cj_dropshipping",
    "cj_supplier_proxy",
    "amazon_reviews",
    "google_trends",
    "tiktok",
    "reddit",
    "twitter",
)

# States discovery reports per source, and what each one MEANS. Keeping these
# distinct is the whole point: a dead API and a genuinely quiet market look
# identical once they are collapsed together.
#   real    — queried, returned usable data
#   empty   — queried, honestly had nothing
#   n/a     — not applicable to this product (e.g. CJ proxy on an AE-only item)
#   absent  — never ran: disabled, unconfigured, or it failed
_LIVE_STATE = "real"


# ---------------------------------------------------------------------------
# GRADE VERSIONING
#
# A grade is only comparable to another grade produced by the same scoring
# logic. F7 changes the weights; without a version marker, calibration would
# silently pool pre-change and post-change scores and report one correlation
# for two different engines — a confident number about nothing.
#
# BUMP `WEIGHTS_VERSION` WHENEVER YOU CHANGE HOW oi_score IS COMPUTED
# (the multiplier chain in product_discovery.py, ~line 6229-6437). Bump
# `PROMPT_VERSION` when the grading prompt changes. Deliberately explicit
# constants rather than a source hash: a hash would also fire on comment edits
# and reformatting, fragmenting calibration cohorts for no reason.
#
# Not derived from the deploy SHA for the same reason — that changes on every
# deploy and would shatter a 28-day window into unusable slivers.
WEIGHTS_VERSION = "v1"
PROMPT_VERSION = "v1"
MODEL_VERSION = "multiplier-chain-v1"


def grade_versions() -> Dict[str, str]:
    """The (model, prompt, weights) triple stamped onto every snapshot.

    Env overrides exist so an experiment can mark its runs as a separate
    cohort without a deploy; unset is the normal case.
    """
    return {
        "model_version": os.getenv("OSPRA_MODEL_VERSION") or MODEL_VERSION,
        "prompt_version": os.getenv("OSPRA_PROMPT_VERSION") or PROMPT_VERSION,
        "weights_version": os.getenv("OSPRA_WEIGHTS_VERSION") or WEIGHTS_VERSION,
    }


def new_run_id() -> str:
    """Opaque id grouping every snapshot from one pipeline execution."""
    return uuid.uuid4().hex[:16]


def ledger_enabled() -> bool:
    return os.getenv("LEDGER_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


def _session():
    from ospra_os.database.connection import SessionLocal
    return SessionLocal()


def build_source_manifest(product: Dict[str, Any]) -> Dict[str, Any]:
    """Record which sources actually returned data for THIS product.

    Distinguishes four states, because they mean different things:
      "real"    — the source returned usable data
      "empty"   — the source was queried and honestly had nothing
      "n/a"     — not applicable to this product (CJ proxy on an AE-only item)
      "absent"  — the source never ran (disabled, unconfigured, or failed)

    Collapsing empty and absent is exactly the mistake that lets a dead API
    look like a quiet market.
    """
    data_sources = product.get("data_sources") or {}
    coverage = (product.get("data_coverage") or {}).get("by_source") or {}

    manifest: Dict[str, str] = {}

    # Discovery's own coverage verdict wins — it is computed at the point the
    # source was queried and knows things we cannot reconstruct here.
    for name, state in coverage.items():
        manifest[str(name)] = str(state)

    # Anything expected but not reported by coverage: fall back to whether a
    # data_sources block exists. A source discovery never mentioned at all is
    # "absent" — it did not run.
    for name in KNOWN_SOURCES:
        if name in manifest:
            continue
        block = data_sources.get(name)
        if block is None:
            manifest[name] = "absent"
        elif isinstance(block, dict) and (
            not block or block.get("available") is False
        ):
            manifest[name] = "empty"
        else:
            manifest[name] = _LIVE_STATE

    live = sum(1 for v in manifest.values() if v == _LIVE_STATE)
    # "total" counts sources that were APPLICABLE to this product — n/a ones
    # were never in play, so including them would make a well-covered product
    # look starved. Matches discovery's own `queried` denominator.
    applicable = sum(1 for v in manifest.values() if v != "n/a")
    return {
        "sources": manifest,
        "live": live,
        "total": applicable,
        # Kept separately so "we know of 8 sources" and "6 applied to this
        # product" stay distinguishable in hindsight.
        "known": len(KNOWN_SOURCES),
    }


def _grade_of(product: Dict[str, Any]) -> Optional[float]:
    for key in ("oi_score", "final_score", "score", "opportunity_score"):
        v = product.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def _factor_breakdown(product: Dict[str, Any]) -> Dict[str, Any]:
    """The per-factor detail behind the grade. Kept as-is rather than
    re-derived, so the snapshot reflects what the run actually computed."""
    return {
        "demand_score": product.get("demand_score"),
        "trend_score": product.get("trend_score"),
        "sentiment_score": product.get("sentiment_score"),
        "profit_score": product.get("profit_score"),
        "saturation_score": product.get("saturation_score"),
        "opportunity_score": product.get("opportunity_score"),
        "velocity_phase": product.get("velocity_phase"),
        "meta_advertiser_count": product.get("meta_niche_advertiser_count"),
        "score_breakdown": product.get("score_breakdown"),
        "data_confidence": (product.get("data_coverage") or {}).get("confidence"),
    }


def record_run(
    products: Iterable[Dict[str, Any]],
    *,
    niche: str,
    pipeline_run_id: str,
    model_version: Optional[str] = None,
    prompt_version: Optional[str] = None,
    weights_version: Optional[str] = None,
) -> int:
    """Write one immutable snapshot per evaluated product. Returns rows written.

    Raises on insert failure — a partially-written ledger must be loud.
    """
    if not ledger_enabled():
        return 0

    from ospra_os.database.ledger_models import GradeSnapshot
    from ospra_os.database.product_timeseries import product_identity_key

    # Unset means "the current engine", not "unknown". A NULL here would make
    # the snapshot uncomparable to every other snapshot, which is the exact
    # failure the version columns exist to prevent.
    _v = grade_versions()
    model_version = model_version or _v["model_version"]
    prompt_version = prompt_version or _v["prompt_version"]
    weights_version = weights_version or _v["weights_version"]

    rows: List[GradeSnapshot] = []
    now = datetime.utcnow()
    for product in products:
        if not isinstance(product, dict):
            continue
        try:
            key = product_identity_key(product)
        except Exception:
            key = str(product.get("product_id") or product.get("title") or "")[:255]
        if not key:
            continue

        manifest = build_source_manifest(product)
        rows.append(GradeSnapshot(
            product_key=key,
            product_title=(product.get("title") or product.get("clean_title") or "")[:512] or None,
            niche=niche,
            ts=now,
            pipeline_run_id=pipeline_run_id,
            grade=_grade_of(product),
            factor_breakdown=_factor_breakdown(product),
            model_version=model_version,
            prompt_version=prompt_version,
            weights_version=weights_version,
            source_manifest=manifest,
            sources_live=manifest["live"],
            sources_total=manifest["total"],
            fit_pass=product.get("fit_pass"),
            fit_reasons=product.get("fit_reasons"),
            deployed=bool(product.get("deployed")),
            created_at=now,
        ))

    if not rows:
        return 0

    # Read these BEFORE the commit: attributes expire on commit, so touching
    # them afterwards would fire one refresh SELECT per row just to log a line.
    avg_live = sum(r.sources_live or 0 for r in rows) / len(rows)
    total_sources = rows[0].sources_total

    session = _session()
    try:
        session.add_all(rows)
        session.commit()
        logger.info(
            "[LEDGER] wrote %d snapshots for niche=%s run=%s (avg sources live: %.1f/%d)",
            len(rows), niche, pipeline_run_id, avg_live, total_sources,
        )
        return len(rows)
    except Exception:
        session.rollback()
        # Deliberately re-raised. A silently skipped snapshot yields a ledger
        # that is quietly incomplete, and calibration computed over an
        # incomplete ledger is a confident wrong answer.
        logger.error(
            "[LEDGER] FAILED to write %d snapshots for niche=%s run=%s — "
            "the ledger is the moat; this is a pipeline failure, not a warning",
            len(rows), niche, pipeline_run_id,
        )
        raise
    finally:
        session.close()


def receipts(
    window_start: datetime,
    window_end: datetime,
    *,
    niche: Optional[str] = None,
    min_grade: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Date range → (snapshot, outcome) pairs.

    This is the query file 03's public receipts page is built on: "here is
    everything we graded 8+ in September, and here is what happened." It
    returns misses as well as hits — a receipts page that only shows wins is
    marketing, not evidence.
    """
    from ospra_os.database.ledger_models import GradeSnapshot, ProductOutcome

    session = _session()
    try:
        q = session.query(GradeSnapshot).filter(
            GradeSnapshot.ts >= window_start,
            GradeSnapshot.ts <= window_end,
        )
        if niche:
            q = q.filter(GradeSnapshot.niche == niche)
        if min_grade is not None:
            q = q.filter(GradeSnapshot.grade >= min_grade)
        snapshots = q.order_by(GradeSnapshot.ts.desc()).all()

        keys = {s.product_key for s in snapshots}
        outcomes: Dict[str, List[ProductOutcome]] = {}
        if keys:
            for o in (
                session.query(ProductOutcome)
                .filter(ProductOutcome.product_key.in_(keys))
                .filter(ProductOutcome.period_end >= window_start)
                .all()
            ):
                outcomes.setdefault(o.product_key, []).append(o)

        results: List[Dict[str, Any]] = []
        for s in snapshots:
            matched = [
                o for o in outcomes.get(s.product_key, [])
                # Only outcomes measured AFTER the prediction count. An outcome
                # from before the snapshot cannot validate it.
                if o.period_start >= s.ts
            ]
            results.append({
                "product_key": s.product_key,
                "title": s.product_title,
                "niche": s.niche,
                "graded_at": s.ts.isoformat(),
                "grade": s.grade,
                "sources_live": s.sources_live,
                "sources_total": s.sources_total,
                "deployed": s.deployed,
                "fit_pass": s.fit_pass,
                "outcomes": [
                    {
                        "period_start": o.period_start.isoformat(),
                        "period_end": o.period_end.isoformat(),
                        "orders": o.orders,
                        "revenue": o.revenue,
                        "units": o.units,
                        "margin_projected": o.margin_projected,
                        "margin_actual": o.margin_actual,
                        "proxy_ae_velocity": o.proxy_ae_velocity,
                        "proxy_trend_delta": o.proxy_trend_delta,
                    }
                    for o in sorted(matched, key=lambda x: x.period_start)
                ],
            })
        return results
    finally:
        session.close()


def spearman(xs: List[float], ys: List[float]) -> Optional[float]:
    """Spearman rank correlation, with average ranks for ties.

    Implemented here rather than pulled from scipy: this is ~20 lines, and the
    dependency is not worth carrying for it. Returns None when there is not
    enough data or either series has no variance — an honest None beats a
    fabricated 0.0, which would read as "no relationship" rather than
    "not enough evidence".
    """
    if len(xs) != len(ys) or len(xs) < 3:
        return None

    def ranks(vals: List[float]) -> List[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx)
    dy = sum((b - my) ** 2 for b in ry)
    if dx == 0 or dy == 0:
        return None
    return round(num / ((dx * dy) ** 0.5), 4)


def compute_calibration(
    window_days: int = 28,
    *,
    persist: bool = True,
) -> Dict[str, Any]:
    """Does the grade actually predict the outcome? Logged either way.

    Pairs each snapshot with outcomes measured strictly AFTER it, so the
    correlation only ever looks forward.
    """
    from ospra_os.database.ledger_models import CalibrationReport

    window_end = datetime.utcnow()
    window_start = window_end - timedelta(days=window_days)
    pairs = receipts(window_start, window_end)

    # ONE POINT PER PRODUCT — not one per snapshot.
    #
    # receipts() returns a row per SNAPSHOT, and the catalog cron grades every
    # product twice a day. Over a 28-day window one product yields up to 56
    # snapshots, all matching the same weekly outcome. Feeding those in
    # individually is pseudo-replication: it inflates n ~50x, makes a noisy
    # correlation look highly confident, and silently over-weights whichever
    # products happen to appear in more runs.
    #
    # The EARLIEST grade in the window is the one used. That is the genuine
    # prediction — later re-grades of the same product are increasingly
    # informed by the very period being scored, so preferring them would leak
    # hindsight into a number whose only job is to measure foresight.
    earliest: Dict[str, Dict[str, Any]] = {}
    for row in pairs:
        if row.get("grade") is None:
            continue
        key = row["product_key"]
        prev = earliest.get(key)
        if prev is None or row["graded_at"] < prev["graded_at"]:
            earliest[key] = row

    graded_orders: List[Tuple[float, float]] = []
    graded_proxy: List[Tuple[float, float]] = []
    n_deployed = 0

    for row in earliest.values():
        grade = row["grade"]
        if row.get("deployed"):
            n_deployed += 1
        for o in row["outcomes"]:
            if o.get("orders") is not None:
                graded_orders.append((grade, float(o["orders"])))
                break
        for o in row["outcomes"]:
            if o.get("proxy_ae_velocity") is not None:
                graded_proxy.append((grade, float(o["proxy_ae_velocity"])))
                break

    rho_orders = spearman([g for g, _ in graded_orders], [v for _, v in graded_orders])
    rho_proxy = spearman([g for g, _ in graded_proxy], [v for _, v in graded_proxy])

    report = {
        "window_start": window_start,
        "window_end": window_end,
        "spearman_grade_vs_orders": rho_orders,
        "spearman_grade_vs_proxy": rho_proxy,
        # DISTINCT products, not snapshots. Reporting snapshot count here would
        # advertise a ~50x larger sample than actually exists.
        "n_products": len(earliest),
        "n_deployed": n_deployed,
        "notes": {
            "n_with_orders": len(graded_orders),
            "n_with_proxy": len(graded_proxy),
            "n_snapshots_in_window": len(pairs),
            # The launch gate in file 03 requires Spearman >= 0.4. State
            # plainly when there is not yet enough data to say — "insufficient
            # data" is a valid, honest verdict and must not read as a failure.
            "verdict": (
                "insufficient_data" if rho_orders is None and rho_proxy is None
                else "meets_gate" if (rho_orders or 0) >= 0.4 or (rho_proxy or 0) >= 0.4
                else "below_gate"
            ),
        },
    }

    if persist:
        session = _session()
        try:
            session.add(CalibrationReport(
                run_ts=datetime.utcnow(),
                window_start=window_start,
                window_end=window_end,
                spearman_grade_vs_orders=rho_orders,
                spearman_grade_vs_proxy=rho_proxy,
                n_products=report["n_products"],
                n_deployed=n_deployed,
                notes=report["notes"],
            ))
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.warning("[LEDGER] calibration persist failed: %s", exc)
        finally:
            session.close()

    logger.info(
        "[LEDGER] calibration: rho_orders=%s rho_proxy=%s n=%d verdict=%s",
        rho_orders, rho_proxy, report["n_products"], report["notes"]["verdict"],
    )
    return report
