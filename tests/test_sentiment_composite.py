"""
Tests for ``ospra_os.intelligence.sentiment_composite``.

Locks down the diversity × volume math the user signed off on. The
critical regressions to prevent:
  - "1 Reddit post = full credit" (single weak signal inflating score)
  - "Single-source = max-with-floor" (collapse to one source's tier)
  - Composite that DOESN'T move when more diverse sources confirm
"""

from __future__ import annotations

import pytest

from ospra_os.intelligence.sentiment_composite import (
    CompositeResult,
    SentimentInput,
    amazon_weight,
    compose,
    diversity_multiplier,
    reddit_weight,
    score_from_amazon_buzz,
    score_from_reddit_mentions,
    score_from_tiktok_engagement,
    score_from_twitter_polarity,
    tiktok_weight,
    twitter_weight,
    twitter_weight_v2,
)


# ---------------------------------------------------------------------------
# Per-source weight curves
# ---------------------------------------------------------------------------

def test_amazon_weight_log_saturated():
    """1 review, 100, 10000 should produce meaningfully different weights."""
    w_1 = amazon_weight(1)
    w_100 = amazon_weight(100)
    w_10k = amazon_weight(10_000)
    assert 0 < w_1 < w_100 < w_10k <= 1.0
    # Single review should not dominate
    assert w_1 < 0.10
    # 100 reviews ≈ 0.5 (mid)
    assert 0.45 <= w_100 <= 0.55
    # 10k reviews → cap
    assert w_10k >= 0.95


def test_reddit_weight_one_post_low():
    """A single Reddit post should NOT get full credit. This is the user's
       complaint that drove the rewrite."""
    w_1 = reddit_weight(1)
    w_50 = reddit_weight(50)
    assert w_1 < 0.20, f"single Reddit post should be low confidence, got {w_1}"
    assert w_50 > w_1 * 4, f"50 posts should be much higher than 1, got {w_50}"


def test_twitter_weight_volume_ladder():
    assert twitter_weight(0) == 0
    assert 0 < twitter_weight(1) < twitter_weight(50) < twitter_weight(1000) <= 1.0


def test_twitter_weight_v2_paraphrase_contributes_zero():
    # #6 Option A: Grok paraphrase (no real citations) is NOT proof — it must
    # contribute ZERO confidence regardless of claimed tweet count / engagement.
    assert twitter_weight_v2(50, 9999, has_citations=False) == 0.0
    assert twitter_weight_v2(0, 0, has_citations=False) == 0.0
    assert twitter_weight_v2(1000, 100000, has_citations=False) == 0.0


def test_twitter_weight_v2_citations_weighted_by_real_engagement():
    # With real citations, weight is driven by real engagement (log-scaled
    # likes+RT+replies) blended with volume. A handful of low-engagement posts
    # barely registers; a high-engagement cluster carries real weight.
    low = twitter_weight_v2(3, 0, has_citations=True)
    mid = twitter_weight_v2(50, 1000, has_citations=True)
    high = twitter_weight_v2(200, 10000, has_citations=True)
    assert low < 0.15, "citations but ~0 engagement should be near-zero"
    assert 0.4 < mid < 0.8, "1k engagement = moderate weight"
    assert high > 0.85, "10k+ engagement = strong weight"
    assert low < mid < high <= 1.0


def test_twitter_weight_v2_engagement_dominates_volume():
    # Engagement is the real proof; raw volume only supports it. High volume but
    # zero engagement must stay below modest volume WITH real engagement.
    volume_no_engagement = twitter_weight_v2(1000, 0, has_citations=True)
    modest_with_engagement = twitter_weight_v2(20, 5000, has_citations=True)
    assert modest_with_engagement > volume_no_engagement


def test_tiktok_weight_combines_comments_and_views():
    only_comments = tiktok_weight(comment_count=100)
    with_views = tiktok_weight(comment_count=100, view_count=10_000)
    assert with_views >= only_comments
    assert tiktok_weight(0, 0) == 0


# ---------------------------------------------------------------------------
# Per-source score normalizers
# ---------------------------------------------------------------------------

def test_amazon_score_clamps_to_0_100():
    assert score_from_amazon_buzz(120) == 100
    assert score_from_amazon_buzz(-5) == 0
    assert score_from_amazon_buzz(63.5) == 63.5


def test_twitter_polarity_maps_minus1_to_plus1():
    assert score_from_twitter_polarity(-1.0) == 20.0
    assert score_from_twitter_polarity(0.0) == 55.0
    assert score_from_twitter_polarity(1.0) == 90.0


def test_reddit_score_tiered():
    assert score_from_reddit_mentions(0) == 0
    assert score_from_reddit_mentions(1) == 58.0
    assert score_from_reddit_mentions(60) == 92.0


def test_tiktok_score_tiered():
    assert score_from_tiktok_engagement(0) == 0
    assert 55 <= score_from_tiktok_engagement(10) <= 65
    assert score_from_tiktok_engagement(2000) == 85.0


# ---------------------------------------------------------------------------
# Diversity multiplier
# ---------------------------------------------------------------------------

def test_diversity_climbs_with_source_count():
    """Use pytest.approx for float equality — 0.20 + 0.20 + 0.20 != 0.60 exactly in IEEE 754."""
    assert diversity_multiplier(0) == 0
    assert diversity_multiplier(1) == pytest.approx(0.40)
    assert diversity_multiplier(2) == pytest.approx(0.60)
    assert diversity_multiplier(3) == pytest.approx(0.80)
    assert diversity_multiplier(4) == pytest.approx(1.00)
    assert diversity_multiplier(10) == pytest.approx(1.00)


# ---------------------------------------------------------------------------
# Compose — the load-bearing function
# ---------------------------------------------------------------------------

def test_compose_no_sources_returns_none():
    """Zero sources with weight > 0 → sentiment_score is None, no fallback."""
    result = compose([])
    assert result.sentiment_score is None
    assert result.sentiment_confidence == 0
    assert result.n_sources == 0


def test_compose_single_low_weight_source_is_low_confidence():
    """One Reddit post: returns SOMETHING, but confidence should be low.
       This is the regression the user demanded we fix."""
    sources = [
        SentimentInput(name="reddit", score=58.0, weight=reddit_weight(1)),  # 1 post
    ]
    result = compose(sources)
    assert result.sentiment_score is not None
    assert result.n_sources == 1
    assert result.diversity == 0.40
    # With one Reddit post (weight ~0.15) and diversity 0.40, confidence should be very low.
    assert result.sentiment_confidence < 0.30, (
        f"single weak source confidence too high: {result.sentiment_confidence}"
    )


def test_compose_three_strong_sources_high_confidence():
    """Amazon (100 reviews) + Twitter (200 tweets) + Reddit (10 posts) → high."""
    sources = [
        SentimentInput("amazon_reviews", 80.0, amazon_weight(100)),
        SentimentInput("twitter", 75.0, twitter_weight(200)),
        SentimentInput("reddit", 72.0, reddit_weight(10)),
    ]
    result = compose(sources)
    assert result.n_sources == 3
    assert result.diversity == 0.80
    assert result.sentiment_confidence >= 0.60
    # Score should be a real weighted average somewhere in the 70s
    assert 70 <= result.sentiment_score <= 82


def test_compose_weighted_average_respects_volume():
    """A high-weight source should dominate a low-weight one."""
    # Amazon with 10k reviews (weight ≈ 1.0) saying 30; Reddit with 1 post (weight ~0.15) saying 90.
    # Weighted avg should pull toward 30, NOT toward 60 (simple average).
    sources = [
        SentimentInput("amazon_reviews", 30.0, amazon_weight(10_000)),
        SentimentInput("reddit", 90.0, reddit_weight(1)),
    ]
    result = compose(sources)
    assert result.sentiment_score is not None
    assert result.sentiment_score < 50, (
        f"high-weight Amazon source should dominate, got {result.sentiment_score}"
    )


def test_compose_excludes_zero_weight_sources():
    """A SentimentInput with weight=0 is filtered out (don't pollute)."""
    sources = [
        SentimentInput("amazon_reviews", 80.0, amazon_weight(100)),
        SentimentInput("twitter", 75.0, 0.0),  # zero weight → filtered
    ]
    result = compose(sources)
    assert result.n_sources == 1
    assert result.diversity == 0.40
    assert result.primary_source == "amazon_reviews"


def test_compose_primary_source_is_highest_weight():
    sources = [
        SentimentInput("twitter", 60.0, 0.30),
        SentimentInput("amazon_reviews", 70.0, 0.85),
        SentimentInput("reddit", 50.0, 0.20),
    ]
    result = compose(sources)
    assert result.primary_source == "amazon_reviews"


def test_compose_diversity_dampens_single_source_high_volume():
    """Even Amazon at 10k reviews alone shouldn't max sentiment_confidence —
       single-source = diversity 0.40 ceiling. The user's frustration: a
       product fully validated on one platform is still less validated than
       one validated on three."""
    sources = [
        SentimentInput("amazon_reviews", 90.0, amazon_weight(10_000)),
    ]
    result = compose(sources)
    assert result.sentiment_confidence <= 0.40
