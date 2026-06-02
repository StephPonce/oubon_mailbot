"""
Tests for the pure trend-trajectory analyzer — especially the pump_crash
signature, which is the defense against bought-engagement hype.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ospra_os.intelligence.trend_trajectory import (
    analyze_trajectory,
    is_organic_trajectory,
)


def _series(values):
    """Build a daily (timestamp, value) series, one point per day."""
    base = datetime(2026, 1, 1)
    return [(base + timedelta(days=i), v) for i, v in enumerate(values)]


def test_insufficient_data():
    r = analyze_trajectory(_series([10, 20]))
    assert r.shape == "insufficient_data"
    assert r.confidence == 0.0


def test_pump_crash_detected():
    # Sharp rise to a peak, then crash — the bought-hype signature.
    r = analyze_trajectory(_series([10, 40, 85, 95, 50, 18]))
    assert r.shape == "pump_crash"
    assert r.peak_ratio < 0.6
    assert not is_organic_trajectory(r.shape)


def test_emerging_caught():
    # Fast rise from a low base, still under the saturation ceiling.
    r = analyze_trajectory(_series([8, 18, 32, 50]))
    assert r.shape == "emerging"
    assert is_organic_trajectory(r.shape)


def test_sustained_growth():
    # Steady ~+2/day (below the fast-rise threshold of 3) → sustained, not emerging.
    r = analyze_trajectory(_series([40, 42, 44, 46, 48]))
    assert r.shape in ("sustained", "accelerating")
    assert is_organic_trajectory(r.shape)


def test_declining_is_not_pump():
    # Steady fade with the peak at the START → declining, NOT pump_crash.
    r = analyze_trajectory(_series([70, 60, 50, 42, 35]))
    assert r.shape == "declining"
    assert r.peak_ratio < 1.0


def test_plateau():
    r = analyze_trajectory(_series([70, 71, 70, 69, 70]))
    assert r.shape == "plateauing"


def test_velocity_and_acceleration_signs():
    r = analyze_trajectory(_series([10, 15, 30, 60]))  # rising and speeding up
    assert r.velocity > 0
    assert r.acceleration > 0
