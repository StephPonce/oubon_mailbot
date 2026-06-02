"""
Tests for the demand-authenticity / divergence scorer.

Covers the four regimes: manufactured (heavy demote), corroborated organic,
single-source organic, and unproven — plus the demote-only invariant.
"""

from __future__ import annotations

from ospra_os.intelligence.demand_authenticity import (
    DIVERGENCE_DEMOTE_MULTIPLIER,
    compute_authenticity,
    signals_from_product,
)


def test_manufactured_hype_is_heavily_demoted():
    # We MEASURED organic demand (1 source), it's low, yet promoted buzz is high
    # → confirmed manufactured.
    r = compute_authenticity(organic_strength=0.1, promoted_strength=0.9, n_organic_sources=1)
    assert r.divergence_flag is True
    assert r.label == "manufactured"
    assert r.multiplier == DIVERGENCE_DEMOTE_MULTIPLIER  # heavy demote (0.4 default)
    assert r.reasons


def test_unmeasured_organic_is_unverified_not_manufactured():
    # GOVEE case: high promoted buzz but organic demand NOT gathered (n=0).
    # Must NOT be branded manufactured — that false-positive nuked real winners.
    r = compute_authenticity(organic_strength=0.0, promoted_strength=0.8, n_organic_sources=0)
    assert r.divergence_flag is False
    assert r.label == "unverified_hype"
    assert 0.7 <= r.multiplier <= 0.8  # moderate demote, not the heavy 0.4


def test_corroborated_organic_not_demoted():
    # Strong organic demand across multiple independent hard-to-fake sources.
    r = compute_authenticity(organic_strength=0.9, promoted_strength=0.5, n_organic_sources=3)
    assert r.divergence_flag is False
    assert r.label == "corroborated"
    assert r.multiplier >= 0.95  # essentially no penalty
    assert r.multiplier <= 1.0   # demote-only invariant


def test_single_source_organic():
    r = compute_authenticity(organic_strength=0.7, promoted_strength=0.2, n_organic_sources=1)
    assert r.divergence_flag is False
    assert r.label == "organic"
    assert 0.9 <= r.multiplier <= 1.0


def test_unproven_is_only_slightly_demoted_not_flagged():
    # Weak everything → unproven, NOT manufactured (no divergence flag).
    r = compute_authenticity(organic_strength=0.1, promoted_strength=0.15, n_organic_sources=0)
    assert r.divergence_flag is False
    assert r.label == "unproven"
    assert 0.8 <= r.multiplier <= 0.92


def test_multiplier_never_inflates():
    # Demote-only invariant across the whole grid.
    for org in (0.0, 0.3, 0.6, 1.0):
        for promo in (0.0, 0.3, 0.6, 1.0):
            r = compute_authenticity(organic_strength=org, promoted_strength=promo)
            assert r.multiplier <= 1.0


def test_real_brand_with_organic_demand_is_not_flagged_manufactured():
    # GOVEE-like: heavy ads (promoted high) BUT real organic demand too → NOT
    # manufactured. (Its problem is saturation, handled elsewhere — not here.)
    r = compute_authenticity(organic_strength=0.8, promoted_strength=0.9, n_organic_sources=2)
    assert r.divergence_flag is False
    assert r.label in ("corroborated", "organic")


def test_signals_from_product_separates_organic_and_promoted():
    product = {
        "google_trend_score": 80,            # organic
        "amazon_review_count": 1000,         # organic
        "winner_source": "meta_ads",         # promoted
        "data_sources": {"tiktok": {"views": 5_000_000}},  # promoted
    }
    organic, promoted, n_org = signals_from_product(product)
    assert organic > 0.5 and n_org == 2
    assert promoted > 0.5


def test_signals_from_product_pump_profile_is_unverified_without_organic():
    # Huge TikTok views + meta ad, but no organic data gathered → UNVERIFIED hype
    # (not "manufactured" — we can't confirm fakeness without measuring organic).
    # Confirmed-pump detection over time is trend_trajectory's job.
    product = {
        "winner_source": "meta_ads",
        "data_sources": {"tiktok": {"views": 8_000_000}},
    }
    organic, promoted, n_org = signals_from_product(product)
    assert organic == 0.0 and n_org == 0
    assert promoted > 0.6
    r = compute_authenticity(organic_strength=organic, promoted_strength=promoted, n_organic_sources=n_org)
    assert r.divergence_flag is False and r.label == "unverified_hype"


def test_aliexpress_orders_count_as_weak_organic():
    # A dropshipping item with real AE order volume gets organic backing even
    # without Google Trends / Amazon (so winner-sourced AE products aren't nuked).
    product = {
        "winner_source": "meta_ads",
        "data_sources": {"aliexpress": {"orders": 50_000}, "tiktok": {"views": 8_000_000}},
    }
    organic, promoted, n_org = signals_from_product(product)
    assert organic > 0 and n_org >= 1
    assert promoted > 0.6
