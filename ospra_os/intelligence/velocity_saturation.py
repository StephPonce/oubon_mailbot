"""
Velocity-based saturation (#57 Phase 1) — SCAFFOLDING, OFF BY DEFAULT.

Turns saturation from a single-snapshot heuristic into a first-class,
TRAJECTORY-aware grade term computed from product_timeseries history:

  advertiser DENSITY (how crowded right now) + advertiser SLOPE (how fast it's
  filling) + demand SLOPE (is interest rising or dying).

The thesis (owner brief): reward rising demand at LOW-BUT-NONZERO competition
(target ~5–15 advertisers); demote crowded markets (30+) and ones filling fast.

Gated behind DISCOVERY_VELOCITY_SATURATION_ENABLED (default OFF) — these numbers
are UNVALIDATED until real snapshots accumulate, so the flag keeps them out of
live grades. Everything here is pure (no DB / no I/O) so it's fully unit-tested
on synthetic series; the DB read + grade wiring live in product_discovery.

`score` is 0..1 where HIGHER = MORE SATURATED (worse opportunity) — same polarity
as _compute_saturation, so the two can blend directly.
"""

from typing import Dict, List, Optional


def linear_slope(values: List[float]) -> float:
    """Least-squares slope per step (per day, given daily snapshots).

    Returns 0.0 for <2 points (no trend). Robust to noise vs (last-first)/n.
    """
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    num = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    return num / denom


def advertiser_density_penalty(count: Optional[int]) -> Optional[float]:
    """0..1 competition penalty by advertiser count (lower = better opportunity).

    Sweet spot 5–15 (validated demand, not yet crowded) → lowest penalty.
    0–2 = unproven/thin; 30+ = saturated. None when not measured.
    """
    if count is None:
        return None
    if count <= 0:
        return 0.55          # unproven — no money-backed validation yet
    if count <= 2:
        return 0.40          # very early, thin validation
    if count <= 4:
        return 0.22          # emerging
    if count <= 15:
        return 0.10          # SWEET SPOT — validated, not crowded
    if count <= 29:
        return 0.45          # getting crowded
    return 0.80              # saturated


def velocity_saturation(
    advertiser_count: Optional[int],
    advertiser_weekly_slope: float,
    demand_weekly_slope: float,
    demand_recent_level: float,
    n_points: int,
) -> Optional[Dict]:
    """Compute a trajectory-aware saturation score.

    Args:
      advertiser_count: latest Meta advertiser count (density).
      advertiser_weekly_slope: change in advertiser count per WEEK (filling speed).
      demand_weekly_slope: change in the demand signal per WEEK (orders/trends).
      demand_recent_level: recent mean of the demand signal (to normalize slope).
      n_points: number of daily snapshots backing the slopes (confidence driver).

    Returns {score, confidence, note, components} or None when there's no signal.
    score 0..1 (higher = more saturated). confidence 0..1 (0 → caller ignores).
    """
    base = advertiser_density_penalty(advertiser_count)
    if base is None and n_points < 2:
        return None  # nothing measured

    score = base if base is not None else 0.5
    components = {"density_penalty": base}

    # Fast-filling: advertisers piling in quickly = crowding ahead → demote.
    if advertiser_weekly_slope >= 5:
        score += 0.25
        components["fast_filling"] = 0.25
    elif advertiser_weekly_slope >= 2:
        score += 0.10
        components["fast_filling"] = 0.10

    # Demand trajectory: normalize weekly slope against recent level so it works
    # for both small (orders=20) and large (orders=5000) magnitudes.
    denom = max(1.0, abs(demand_recent_level))
    rel = demand_weekly_slope / denom
    if rel >= 0.20:           # rising ≥20%/wk — the early-winner signal → reward
        score -= 0.15
        components["demand_rising"] = -0.15
    elif rel <= -0.20:        # demand dying → demote
        score += 0.15
        components["demand_falling"] = 0.15

    score = max(0.0, min(1.0, score))

    # Confidence: a full week of daily snapshots → full trust. Slopes need ≥3
    # points to mean anything; with <3 we trust only density (lower ceiling).
    if n_points >= 3:
        confidence = min(1.0, n_points / 7.0)
    elif advertiser_count is not None:
        confidence = 0.3      # density-only, no trustworthy slope yet
    else:
        confidence = 0.0

    note = None
    if advertiser_count is not None:
        note = (
            f"velocity_sat: {advertiser_count} advertisers, "
            f"adv {advertiser_weekly_slope:+.1f}/wk, demand {rel*100:+.0f}%/wk "
            f"({n_points}d)"
        )
    return {
        "score": round(score, 3),
        "confidence": round(confidence, 3),
        "note": note,
        "components": components,
    }


def velocity_saturation_from_series(
    advertiser_series: List[Optional[float]],
    demand_series: List[Optional[float]],
) -> Optional[Dict]:
    """Convenience: turn raw daily time-series into a velocity-saturation score.

    `advertiser_series` / `demand_series` are oldest→newest daily values (None
    entries are dropped). Computes weekly slopes (per-day slope × 7) and the
    recent demand level, then calls velocity_saturation(). This is the single
    entry point product_discovery calls after loading rows from the DB.
    """
    adv = [float(v) for v in advertiser_series if v is not None]
    dem = [float(v) for v in demand_series if v is not None]
    n_points = max(len(adv), len(dem))
    if n_points == 0:
        return None
    advertiser_count = int(round(adv[-1])) if adv else None
    advertiser_weekly_slope = linear_slope(adv) * 7.0 if len(adv) >= 2 else 0.0
    demand_weekly_slope = linear_slope(dem) * 7.0 if len(dem) >= 2 else 0.0
    demand_recent_level = (sum(dem) / len(dem)) if dem else 0.0
    return velocity_saturation(
        advertiser_count=advertiser_count,
        advertiser_weekly_slope=advertiser_weekly_slope,
        demand_weekly_slope=demand_weekly_slope,
        demand_recent_level=demand_recent_level,
        n_points=n_points,
    )
