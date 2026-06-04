"""
Unit tests for the Pinterest Trends Apify connector.

Mirrors the test pattern used in test_tiktok_shop_connector.py:
- Identity / availability gating
- Score normalization & blending
- Velocity estimation logic
- Pin aggregation
- Mocked Apify actor results
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def configured_connector():
    """Pinterest connector with a fake Apify token AND an explicit actor."""
    # The connector's default actor was unset (2026-06-03) so it doesn't
    # auto-spend on a rental. Tests that need an "available" connector pass
    # an actor explicitly — production code is expected to do the same via
    # the PINTEREST_APIFY_ACTOR env var.
    env = {"APIFY_API_TOKEN": "fake-token-12345", "PINTEREST_APIFY_ACTOR": "test/fake-actor"}
    with patch.dict(os.environ, env):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
        )
        connector = PinterestTrendsApify()
        # Replace the underlying Apify client so we never make real calls
        connector.client = MagicMock()
        connector.client.run_actor = AsyncMock(return_value=[])
        return connector


@pytest.fixture
def unconfigured_connector():
    """Pinterest connector with no Apify token — should be unavailable."""
    # Force ApifyClient.__init__ to raise ValueError (the same error path it
    # takes when APIFY_API_TOKEN is unset). We patch the class directly because
    # `load_dotenv()` runs at module import and may inject a real token.
    from ospra_os.product_research.connectors.apify import pinterest_trends as pt_mod

    with patch.object(
        pt_mod,
        "ApifyClient",
        side_effect=ValueError("APIFY_API_TOKEN not set"),
    ):
        return pt_mod.PinterestTrendsApify()


# ---------------------------------------------------------------------------
# Identity / availability
# ---------------------------------------------------------------------------

def test_name_and_source_id(configured_connector):
    assert configured_connector.name == "Pinterest Trends"
    assert configured_connector.source_id == "pinterest_trends"


def test_is_available_when_configured(configured_connector):
    assert configured_connector.is_available() is True


def test_is_available_when_unconfigured(unconfigured_connector):
    assert unconfigured_connector.is_available() is False


# ---------------------------------------------------------------------------
# Score normalization
# ---------------------------------------------------------------------------

class TestNormalization:
    def test_normalize_repins_zero(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
        )
        assert PinterestTrendsApify._normalize_repins(0) == 0.0

    def test_normalize_repins_negative(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
        )
        assert PinterestTrendsApify._normalize_repins(-100) == 0.0

    def test_normalize_repins_at_ceiling(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
            REPIN_LOG_CEILING,
        )
        # At ceiling, score should be ≤ 1.0 (but very close to it)
        score = PinterestTrendsApify._normalize_repins(REPIN_LOG_CEILING)
        assert 0.99 <= score <= 1.0

    def test_normalize_repins_above_ceiling_capped(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
            REPIN_LOG_CEILING,
        )
        # Way above ceiling → capped at 1.0
        score = PinterestTrendsApify._normalize_repins(REPIN_LOG_CEILING * 100)
        assert score == 1.0

    def test_normalize_saves_purchase_intent_weight(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
            SAVE_LOG_CEILING,
            REPIN_LOG_CEILING,
        )
        # Same absolute count, saves should normalize HIGHER than repins
        # because save ceiling is lower (10K vs 50K)
        count = 1000
        saves_score = PinterestTrendsApify._normalize_saves(count)
        repins_score = PinterestTrendsApify._normalize_repins(count)
        # Saves should reach ~75% normalized at 1000 vs ~57% for repins
        assert saves_score > repins_score


# ---------------------------------------------------------------------------
# Trend score blending
# ---------------------------------------------------------------------------

class TestTrendScore:
    def test_trend_score_zero_inputs(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
        )
        score = PinterestTrendsApify._compute_trend_score(0, 0, 0, 0)
        assert score == 0.0

    def test_trend_score_high_saves_dominates(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
        )
        # Many saves, no repins — should still produce a meaningful score
        # because saves carry 0.40 weight
        score = PinterestTrendsApify._compute_trend_score(
            repins=0, saves=10_000, pin_count=0, rising_keyword_count=0
        )
        # 0.40 * 1.0 = 0.4 → 40
        assert 35 <= score <= 45

    def test_trend_score_bounds(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
        )
        # Maxed-out signals → near 100
        score = PinterestTrendsApify._compute_trend_score(
            repins=100_000, saves=50_000, pin_count=10_000, rising_keyword_count=20
        )
        assert 95 <= score <= 100

    def test_trend_score_full_blend(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
        )
        # Realistic mid-range: 5K repins, 2K saves, 100 pins, 5 rising keywords
        score = PinterestTrendsApify._compute_trend_score(
            repins=5_000, saves=2_000, pin_count=100, rising_keyword_count=5
        )
        assert 30 <= score <= 70  # Healthy mid-range trend


# ---------------------------------------------------------------------------
# Velocity estimation
# ---------------------------------------------------------------------------

class TestVelocity:
    def test_velocity_no_signals(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
        )
        # No rising keywords, no save activity → mildly negative
        v = PinterestTrendsApify._estimate_velocity(
            rising_keyword_count=0, save_to_repin_ratio=0.0
        )
        assert v == -10.0

    def test_velocity_strong_rising_lift(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
        )
        # 10+ rising keywords cap at +30%, ratio 1.2 = +5%
        v = PinterestTrendsApify._estimate_velocity(
            rising_keyword_count=15, save_to_repin_ratio=1.2
        )
        assert v == 35.0

    def test_velocity_high_save_ratio(self):
        from ospra_os.product_research.connectors.apify.pinterest_trends import (
            PinterestTrendsApify,
        )
        # save/repin ratio > 1.5 = +15% lift
        v = PinterestTrendsApify._estimate_velocity(
            rising_keyword_count=2, save_to_repin_ratio=2.0
        )
        # 2 * 3 + 15 = 21
        assert v == 21.0


# ---------------------------------------------------------------------------
# Pin aggregation
# ---------------------------------------------------------------------------

class TestAggregation:
    def test_aggregate_empty_pins(self, configured_connector):
        trend = configured_connector._aggregate_pins("led strip lights", [])
        assert trend.search_term == "led strip lights"
        assert trend.pin_count == 0
        assert trend.total_repins == 0
        assert trend.total_saves == 0
        assert trend.trend_score == 0.0

    def test_aggregate_with_pins(self, configured_connector):
        pins = [
            {"repinCount": 1000, "saveCount": 500, "relatedKeywords": ["RGB", "smart home"]},
            {"repinCount": 2000, "saveCount": 800, "relatedKeywords": ["bedroom", "RGB"]},
            {"repins": 500, "saves": 200, "rising_keywords": ["gaming setup"]},
        ]
        trend = configured_connector._aggregate_pins("led strip lights", pins)
        assert trend.pin_count == 3
        assert trend.total_repins == 3500  # 1000 + 2000 + 500
        assert trend.total_saves == 1500   # 500 + 800 + 200
        # Rising keywords deduped: {"RGB", "smart home", "bedroom", "gaming setup"}
        assert len(trend.rising_keywords) == 4
        assert "RGB" in trend.rising_keywords
        assert "led strip lights" not in trend.rising_keywords  # search term excluded

    def test_aggregate_handles_garbage_repin_counts(self, configured_connector):
        pins = [
            {"repinCount": "not_a_number", "saveCount": 100},
            {"repinCount": None, "saveCount": "also_garbage"},
            {"repinCount": 50, "saveCount": 25},
        ]
        # Should not crash; only the parseable values count
        trend = configured_connector._aggregate_pins("test", pins)
        assert trend.pin_count == 3
        assert trend.total_repins == 50
        assert trend.total_saves == 125  # 100 + 0 + 25


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_skips_actor(configured_connector):
    from ospra_os.product_research.connectors.apify.pinterest_trends import (
        PinterestTrendData,
    )
    # Pre-populate cache
    cached = PinterestTrendData(
        search_term="cached_term",
        trend_score=42.0,
        fetched_at="2025-01-01T00:00:00",
    )
    configured_connector._cache_set(
        configured_connector._cache_key("cached_term", "US"),
        cached,
    )

    results = await configured_connector.get_interest(["cached_term"])
    assert len(results) == 1
    assert results[0].trend_score == 42.0
    # Apify actor should NOT have been called
    configured_connector.client.run_actor.assert_not_called()


# ---------------------------------------------------------------------------
# get_interest integration (mocked Apify actor)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_interest_unconfigured_returns_empty(unconfigured_connector):
    results = await unconfigured_connector.get_interest(["smart home", "led lights"])
    # Returns empty trend objects (length matches input), not [] — so callers
    # don't have to special-case missing-credentials state
    assert len(results) == 2
    assert all(r.trend_score == 0 for r in results)
    assert all(r.pin_count == 0 for r in results)


@pytest.mark.asyncio
async def test_get_interest_calls_actor_with_correct_input(configured_connector):
    configured_connector.client.run_actor.return_value = [
        {"searchKeyword": "led strip lights", "repinCount": 1000, "saveCount": 500},
    ]
    results = await configured_connector.get_interest(["led strip lights"], geo="US")

    assert configured_connector.client.run_actor.called
    call_kwargs = configured_connector.client.run_actor.call_args.kwargs
    assert call_kwargs["actor_id"] == configured_connector.actor_id
    assert call_kwargs["run_input"]["search"] == ["led strip lights"]
    assert call_kwargs["run_input"]["country"] == "US"
    assert len(results) == 1
    assert results[0].search_term == "led strip lights"
    assert results[0].total_repins == 1000


@pytest.mark.asyncio
async def test_get_interest_groups_pins_by_search_keyword(configured_connector):
    configured_connector.client.run_actor.return_value = [
        {"searchKeyword": "term_a", "repinCount": 100, "saveCount": 50},
        {"searchKeyword": "term_a", "repinCount": 200, "saveCount": 100},
        {"searchKeyword": "term_b", "repinCount": 300, "saveCount": 150},
    ]
    results = await configured_connector.get_interest(["term_a", "term_b"])

    by_term = {r.search_term: r for r in results}
    assert by_term["term_a"].total_repins == 300
    assert by_term["term_a"].total_saves == 150
    assert by_term["term_b"].total_repins == 300
    assert by_term["term_b"].total_saves == 150


@pytest.mark.asyncio
async def test_get_interest_handles_actor_failure(configured_connector):
    configured_connector.client.run_actor.side_effect = RuntimeError("Apify down")
    results = await configured_connector.get_interest(["a", "b"])
    # Returns empty trend objects rather than raising
    assert len(results) == 2
    assert all(r.trend_score == 0 for r in results)


@pytest.mark.asyncio
async def test_get_interest_falls_back_to_description_match(configured_connector):
    # No searchKeyword field — must match by description
    configured_connector.client.run_actor.return_value = [
        {"description": "Beautiful smart home gadgets", "repinCount": 500, "saveCount": 250},
    ]
    results = await configured_connector.get_interest(["smart home"])
    assert results[0].total_repins == 500


# ---------------------------------------------------------------------------
# OpportunityScorer integration (the 0.15 weight)
# ---------------------------------------------------------------------------

class TestOpportunityScorerWiring:
    def test_pinterest_in_trend_source_weights(self):
        from ospra_os.intelligence.opportunity_scorer import OpportunityScorer
        assert "pinterest" in OpportunityScorer.TREND_SOURCE_WEIGHTS
        assert OpportunityScorer.TREND_SOURCE_WEIGHTS["pinterest"] == 0.15

    def test_demand_signal_enum_includes_pinterest(self):
        from ospra_os.intelligence.opportunity_scorer import DemandSignal
        assert DemandSignal.PINTEREST_TREND.value == "pinterest_trend"
        assert DemandSignal.PINTEREST_SAVES.value == "pinterest_saves"

    def test_demand_metrics_has_pinterest_fields(self):
        from ospra_os.intelligence.opportunity_scorer import DemandMetrics
        m = DemandMetrics()
        # New fields exist with defaults of 0
        assert m.pinterest_trend_score == 0.0
        assert m.pinterest_velocity == 0.0
        assert m.pinterest_saves == 0
        assert m.pinterest_repins == 0

    def test_pinterest_velocity_contributes_to_velocity_score(self):
        from ospra_os.intelligence.opportunity_scorer import (
            DemandMetrics,
            OpportunityScorer,
        )
        scorer = OpportunityScorer()
        # Only Pinterest signal present (other sources absent)
        m = DemandMetrics()
        m.pinterest_trend_score = 80.0
        m.pinterest_velocity = 20.0  # +20% growth
        score = scorer._calc_velocity_score(m)
        # With only Pinterest signal: pin_velocity = 50 + 20 = 70
        # weighted average with single weight returns that value
        assert score == 70.0

    def test_pinterest_volume_contributes_to_volume_score(self):
        from ospra_os.intelligence.opportunity_scorer import (
            DemandMetrics,
            OpportunityScorer,
        )
        scorer = OpportunityScorer()
        m = DemandMetrics()
        m.pinterest_trend_score = 75.0
        score = scorer._calc_volume_score(m)
        # Single source → returns that source's score directly
        assert score == 75.0
