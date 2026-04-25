"""
Tier clamp + feature_summary coverage (Pass 6)
===============================================

Unit tests for the two surfaces added in Pass 4c / Task #6:

1. `ospra_os.core.tiers.clamp_request_count` and
   `get_products_per_request_ceiling` — enforces per-request ceilings on the
   discovery API orthogonally to the weekly quota. A Nest user that asks for
   100 products should get 10 back + `was_clamped=True`, so the frontend can
   render an upgrade-nudge banner (see `ProductDiscovery.jsx::tierNudge`).

2. `ospra_os.core.settings.Settings.feature_summary` — returns a dict of
   booleans describing which integrations are usable given the current env.
   Powers `GET /health/features` (see `ospra_os/routers/health.py`). The
   values ARE state-dependent (real env vars) — we just assert shape +
   boolean types here, to avoid flake on dev machines with partial keys.

These tests are deliberately hermetic: no DB, no HTTP, no third-party deps.
They can run under `uv run pytest tests/test_tier_clamp_and_features.py` with
only `pytest` + `pydantic` + the ospra_os package available.
"""

from __future__ import annotations

import pytest

from ospra_os.core.tiers import (
    SubscriptionTier,
    clamp_request_count,
    get_products_per_request_ceiling,
)


# ---------------------------------------------------------------------------
# get_products_per_request_ceiling
# ---------------------------------------------------------------------------


class TestPerRequestCeiling:
    def test_nest_ceiling_is_ten(self):
        assert get_products_per_request_ceiling(SubscriptionTier.NEST) == 10

    def test_flight_ceiling_is_twenty_five(self):
        assert get_products_per_request_ceiling(SubscriptionTier.FLIGHT) == 25

    def test_soar_ceiling_is_fifty(self):
        assert get_products_per_request_ceiling(SubscriptionTier.SOAR) == 50

    def test_stratosphere_ceiling_is_hundred(self):
        assert get_products_per_request_ceiling(SubscriptionTier.STRATOSPHERE) == 100

    def test_ceilings_are_monotonic_by_tier_value(self):
        """Ceilings must never decrease as tier goes up — invariant for pricing."""
        values = [
            get_products_per_request_ceiling(SubscriptionTier.NEST),
            get_products_per_request_ceiling(SubscriptionTier.FLIGHT),
            get_products_per_request_ceiling(SubscriptionTier.SOAR),
            get_products_per_request_ceiling(SubscriptionTier.STRATOSPHERE),
        ]
        assert values == sorted(values)


# ---------------------------------------------------------------------------
# clamp_request_count
# ---------------------------------------------------------------------------


class TestClampRequestCount:
    def test_under_ceiling_is_passthrough(self):
        """Asking for fewer than the ceiling returns the request verbatim, unclamped."""
        effective, was_clamped = clamp_request_count(5, SubscriptionTier.NEST)
        assert effective == 5
        assert was_clamped is False

    def test_at_ceiling_is_not_clamped(self):
        effective, was_clamped = clamp_request_count(10, SubscriptionTier.NEST)
        assert effective == 10
        assert was_clamped is False

    def test_over_ceiling_is_clamped(self):
        effective, was_clamped = clamp_request_count(100, SubscriptionTier.NEST)
        assert effective == 10
        assert was_clamped is True

    def test_zero_floored_to_one(self):
        """Never return 0 — the frontend would render empty state for no reason."""
        effective, was_clamped = clamp_request_count(0, SubscriptionTier.NEST)
        assert effective == 1
        assert was_clamped is False

    def test_negative_floored_to_one(self):
        effective, was_clamped = clamp_request_count(-5, SubscriptionTier.NEST)
        assert effective == 1
        assert was_clamped is False

    def test_stratosphere_clamps_at_hundred(self):
        effective, was_clamped = clamp_request_count(200, SubscriptionTier.STRATOSPHERE)
        assert effective == 100
        assert was_clamped is True

    def test_soar_fifty_is_not_clamped(self):
        """Regression: the /api/discovery/quick caller asks for its tier ceiling."""
        effective, was_clamped = clamp_request_count(50, SubscriptionTier.SOAR)
        assert effective == 50
        assert was_clamped is False

    def test_flight_boundary(self):
        """Flight clamps a 30-product request (> 25) but not 25 or below."""
        at_cap, clamped_at = clamp_request_count(25, SubscriptionTier.FLIGHT)
        over, clamped_over = clamp_request_count(30, SubscriptionTier.FLIGHT)
        assert (at_cap, clamped_at) == (25, False)
        assert (over, clamped_over) == (25, True)


# ---------------------------------------------------------------------------
# feature_summary()
# ---------------------------------------------------------------------------


class TestFeatureSummary:
    def test_returns_a_dict_of_booleans(self):
        from ospra_os.core.settings import get_settings

        settings = get_settings()
        summary = settings.feature_summary()

        assert isinstance(summary, dict)
        assert len(summary) > 0
        for flag_name, flag_value in summary.items():
            assert isinstance(flag_name, str), f"flag name {flag_name!r} not a string"
            assert isinstance(flag_value, bool), (
                f"flag {flag_name!r} is {type(flag_value).__name__}, expected bool "
                "— /health/features must never leak raw secrets"
            )

    def test_known_flags_present(self):
        """Core flags added in Pass 4c must stay stable — they're documented in .env.example."""
        from ospra_os.core.settings import get_settings

        summary = get_settings().feature_summary()
        required_flags = {
            "ai",
            "email_automation",
            "shopify_oauth",
            "shopify_single_store",
            "aliexpress",
            "cj_dropshipping",
            "amazon_reviews",
            "apify",
            "billing",
            "meta_ads",
            "tiktok_ads",
            "google_ads",
            "observability",
            "alerts",
        }
        missing = required_flags - set(summary.keys())
        assert not missing, (
            f"feature_summary() is missing required Pass 4c flags: {missing}"
        )
