"""
Velocity-based saturation tests (#57 Phase 1 scaffolding, OFF by default).

Pins the trajectory-aware saturation behavior on SYNTHETIC series so it's ready
to flip on once real product_timeseries data accumulates:
  - sweet spot (5–15 advertisers, rising demand) → LOW saturation (good)
  - crowded / fast-filling / dying-demand → HIGH saturation (demoted)
  - confidence scales with how many daily snapshots back the slope
"""

from ospra_os.intelligence.velocity_saturation import (
    linear_slope,
    advertiser_density_penalty,
    velocity_saturation_from_series,
)


# --- linear_slope ---------------------------------------------------------

def test_linear_slope_rising_flat_falling():
    assert linear_slope([1, 2, 3, 4]) == 1.0
    assert linear_slope([5, 5, 5, 5]) == 0.0
    assert linear_slope([4, 3, 2, 1]) == -1.0

def test_linear_slope_too_few_points():
    assert linear_slope([]) == 0.0
    assert linear_slope([7]) == 0.0


# --- advertiser_density_penalty ------------------------------------------

def test_density_sweet_spot_is_lowest():
    sweet = advertiser_density_penalty(8)      # 5–15 sweet spot
    crowded = advertiser_density_penalty(40)   # saturated
    unproven = advertiser_density_penalty(0)   # no validation
    early = advertiser_density_penalty(1)
    assert sweet < early
    assert sweet < unproven
    assert sweet < crowded
    assert crowded >= 0.8

def test_density_none_when_unmeasured():
    assert advertiser_density_penalty(None) is None


# --- velocity_saturation_from_series (the real entry point) --------------

def _week(vals):
    return list(vals)

def test_sweet_spot_rising_demand_is_low_saturation():
    # 8 advertisers steady, demand climbing → the early-winner profile.
    adv = _week([8, 8, 8, 8, 8, 8, 8])
    demand = _week([100, 120, 140, 165, 190, 220, 250])
    r = velocity_saturation_from_series(adv, demand)
    assert r is not None
    assert r["score"] <= 0.15, r          # low saturation = good opportunity
    assert r["confidence"] >= 0.9         # a full week of data

def test_crowded_market_is_high_saturation():
    adv = _week([35, 36, 38, 39, 40, 41, 42])
    demand = _week([500, 500, 500, 500, 500, 500, 500])
    r = velocity_saturation_from_series(adv, demand)
    assert r["score"] >= 0.8

def test_fast_filling_is_demoted():
    # advertisers exploding 5 → 26 in a week (≈ +21/wk) = crowding ahead.
    adv = _week([5, 8, 12, 16, 20, 23, 26])
    demand = _week([200, 205, 210, 212, 215, 216, 218])
    fast = velocity_saturation_from_series(adv, demand)
    # vs a steady 12-advertiser market at the same density end-point
    steady = velocity_saturation_from_series([12] * 7, [200] * 7)
    assert fast["score"] > steady["score"]

def test_dying_demand_is_demoted():
    falling = velocity_saturation_from_series([8] * 7, [250, 220, 190, 160, 130, 100, 70])
    rising = velocity_saturation_from_series([8] * 7, [70, 100, 130, 160, 190, 220, 250])
    assert falling["score"] > rising["score"]

def test_thin_data_low_confidence():
    r = velocity_saturation_from_series([8], [100])   # 1 day only
    assert r is not None
    assert r["confidence"] <= 0.3                      # density-only, slope untrusted

def test_empty_series_returns_none():
    assert velocity_saturation_from_series([], []) is None
    assert velocity_saturation_from_series([None, None], [None]) is None

def test_confidence_grows_with_points():
    three = velocity_saturation_from_series([8, 8, 8], [100, 110, 120])
    seven = velocity_saturation_from_series([8] * 7, [100, 110, 120, 130, 140, 150, 160])
    assert seven["confidence"] > three["confidence"]


# --- loader safety (no history / no table → None, never raises) ----------

def test_loader_returns_none_without_history():
    from ospra_os.intelligence.product_discovery import _load_velocity_saturation
    # A product with no snapshots (and/or no table) must degrade to None, never
    # raise — so the gated grade path falls back to snapshot saturation.
    out = _load_velocity_saturation({"title": "nonexistent zzz product", "image_url": "http://x/none.jpg"})
    assert out is None

def test_timeseries_key_matches_catalog_warm():
    from ospra_os.intelligence.product_discovery import _velocity_timeseries_key
    from ospra_os.tasks.catalog_warm import _product_key
    p = {"title": "WiFi Smart Plug", "image_url": "http://img/1.jpg"}
    assert _velocity_timeseries_key(p) == _product_key(p)  # must join the same rows
