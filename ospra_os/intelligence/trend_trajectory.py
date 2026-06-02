"""
Trend trajectory analysis — the pure time-series primitive.

The defense against being gamed by bought engagement / paid pumps lives in the
SHAPE of a signal over time, not its level at one moment. Real organic demand
rises and SUSTAINS; a bought pump rises sharply then CRASHES (an inverted-V).
A single snapshot can't tell them apart — only the trajectory can.

This module is PURE (no I/O): give it a series of (timestamp, value) points and
it returns velocity, acceleration, how far the latest value is off its peak, and
a SHAPE classification that includes ``pump_crash`` and ``emerging``.

Why a new module rather than extending the existing detectors: the repo has
THREE overlapping velocity implementations — ``VelocityDetector`` (lifecycle
phases, in scoring), ``MomentumTracker`` (trends UI), and the orphaned
``TrendVelocityDetector`` (velocity+acceleration but in-memory, never fed, and
direction-only — it cannot tell a genuine early-spike from a pump mid-spike).
This is the canonical math core they should all delegate to. It is the input
the demand-authenticity engine needs: run it on the HARD-to-fake organic series
(Google Trends, Amazon reviews) and on the EASY-to-fake promoted series (TikTok
views) — when the promoted series is a ``pump_crash`` or surges while the
organic series stays flat, that's manufactured hype.

Thresholds default to a 0–100 score scale (matching the existing detectors'
conventions: velocity > ~3/day = fast). All env-overridable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Sequence, Tuple

# Tunables (0–100 score scale; env-overridable).
FAST_RISE_PER_DAY = float(os.getenv("TRAJECTORY_FAST_RISE", "3.0"))
SLOW_RISE_PER_DAY = float(os.getenv("TRAJECTORY_SLOW_RISE", "0.5"))
EMERGING_LEVEL_CEILING = float(os.getenv("TRAJECTORY_EMERGING_CEILING", "60.0"))
ACCEL_EPSILON = float(os.getenv("TRAJECTORY_ACCEL_EPSILON", "0.3"))
# Pump = rose meaningfully to a peak, then fell below this fraction of it.
PUMP_RISE_FRACTION = float(os.getenv("TRAJECTORY_PUMP_RISE_FRAC", "0.2"))
PUMP_CRASH_FRACTION = float(os.getenv("TRAJECTORY_PUMP_CRASH_FRAC", "0.4"))


@dataclass
class TrajectoryResult:
    velocity: float        # avg change per day across the window
    acceleration: float    # 2nd-half velocity minus 1st-half velocity
    peak_ratio: float      # latest / max  (1.0 = at peak; <1 = fallen off peak)
    shape: str             # see SHAPES below
    confidence: float      # 0..1, grows with number of data points
    reasons: List[str] = field(default_factory=list)


# emerging        — rising fast from a low base, not yet saturated (CATCH THIS)
# accelerating    — rising and speeding up
# sustained       — steady positive growth
# plateauing      — high but flat
# declining       — steady fade (no prior spike)
# pump_crash      — sharp rise to a peak then crash (bought-hype signature)
# insufficient_data — fewer than 3 points
SHAPES = (
    "emerging", "accelerating", "sustained", "plateauing",
    "declining", "pump_crash", "insufficient_data",
)


def analyze_trajectory(points: Sequence[Tuple[datetime, float]]) -> TrajectoryResult:
    """
    Analyze a time-series of (timestamp, value) points.

    Returns a TrajectoryResult. Needs >= 3 points for a shape; fewer yields
    ``insufficient_data`` (which the caller should treat as "unknown", not bad).
    """
    pts = sorted((p for p in points if p and p[1] is not None), key=lambda p: p[0])
    n = len(pts)
    if n < 3:
        return TrajectoryResult(
            velocity=0.0, acceleration=0.0, peak_ratio=1.0,
            shape="insufficient_data", confidence=0.0,
            reasons=[f"Only {n} data point(s) — need >= 3 to read a trajectory."],
        )

    values = [float(v) for _, v in pts]
    t0 = pts[0][0]
    days = [max(0.0, (t - t0).total_seconds() / 86400.0) for t, _ in pts]

    span = days[-1] - days[0]
    span = span if span > 0 else 1.0
    velocity = (values[-1] - values[0]) / span

    mid = n // 2
    fh_span = (days[mid] - days[0]) or 1.0
    sh_span = (days[-1] - days[mid]) or 1.0
    v_first = (values[mid] - values[0]) / fh_span
    v_second = (values[-1] - values[mid]) / sh_span
    acceleration = v_second - v_first

    peak = max(values)
    peak_idx = values.index(peak)
    latest = values[-1]
    peak_ratio = (latest / peak) if peak > 0 else 1.0

    # PUMP: peak happened before the end, rose meaningfully to it, then crashed.
    rose_to_peak = peak - values[0]
    fell_from_peak = peak - latest
    is_pump = (
        peak > 0
        and peak_idx < n - 1
        and rose_to_peak >= PUMP_RISE_FRACTION * peak
        and fell_from_peak >= PUMP_CRASH_FRACTION * peak
    )

    reasons: List[str] = []
    if is_pump:
        shape = "pump_crash"
        reasons.append(
            f"Spiked to {peak:.0f} then fell to {latest:.0f} "
            f"({peak_ratio*100:.0f}% of peak) — pump/crash signature."
        )
    elif velocity >= FAST_RISE_PER_DAY and latest < EMERGING_LEVEL_CEILING:
        shape = "emerging"
        reasons.append(
            f"Rising fast (+{velocity:.1f}/day) from a low base "
            f"(now {latest:.0f}) — emerging, not yet saturated."
        )
    elif velocity > 0 and acceleration > ACCEL_EPSILON:
        shape = "accelerating"
        reasons.append(f"Rising and speeding up (+{velocity:.1f}/day, accel +{acceleration:.1f}).")
    elif velocity >= SLOW_RISE_PER_DAY:
        shape = "sustained"
        reasons.append(f"Steady organic growth (+{velocity:.1f}/day).")
    elif velocity <= -SLOW_RISE_PER_DAY:
        shape = "declining"
        reasons.append(f"Fading ({velocity:.1f}/day).")
    else:
        shape = "plateauing"
        reasons.append(f"Flat ({velocity:+.1f}/day, level {latest:.0f}).")

    confidence = min(1.0, n / 7.0)  # full confidence at ~7 points
    return TrajectoryResult(
        velocity=round(velocity, 2),
        acceleration=round(acceleration, 2),
        peak_ratio=round(peak_ratio, 3),
        shape=shape,
        confidence=round(confidence, 2),
        reasons=reasons,
    )


def is_organic_trajectory(shape: str) -> bool:
    """Convenience: shapes that indicate real, ongoing demand (not a pump/fade)."""
    return shape in ("emerging", "accelerating", "sustained")
