"""
Tests for ``ospra_os.intelligence.sentiment_qualitative``.

Lock the contract:
  - Returns INSUFFICIENT_DATA cleanly when no social evidence present
  - Returns INSUFFICIENT_DATA cleanly when no AI provider configured
  - Strict task→provider routing: xAI when XAI_API_KEY set, Claude
    fallback, NEVER OpenAI/Gemini for this task
  - Non-JSON agent output is handled gracefully (no raise)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ospra_os.intelligence import sentiment_qualitative as sq
from ospra_os.intelligence.sentiment_qualitative import (
    QualitativeAssessment,
    _build_prompt,
    _collect_evidence,
    _select_provider,
    assess_product,
)


# ---------------------------------------------------------------------------
# Evidence aggregation
# ---------------------------------------------------------------------------

def test_collect_evidence_empty_product_marks_no_sources():
    """A product with no twitter/reddit/amazon evidence has zero data_sources_available."""
    ev = _collect_evidence({"title": "Test Plug", "niche": "smart_home"})
    assert ev["data_sources_available"] == []


def test_collect_evidence_picks_up_twitter_when_real_tweets_found():
    product = {
        "title": "Smart WiFi Plug",
        "niche": "smart_home",
        "twitter_evidence": {
            "found_real_tweets": True,
            "search_level": "category",
            "sentiment": "positive",
            "sentiment_score": 0.6,
            "tweet_count": 120,
            "sample_tweets": ["These plugs are great for HomeKit", "Wish setup was easier"],
            "common_praise": ["easy setup", "Alexa works"],
            "common_complaints": ["wifi-only, no zigbee"],
        },
    }
    ev = _collect_evidence(product)
    assert "twitter" in ev["data_sources_available"]
    assert len(ev["twitter"]["sample_tweets"]) == 2
    assert ev["twitter"]["common_complaints"] == ["wifi-only, no zigbee"]


def test_collect_evidence_truncates_reddit_excerpts():
    long_text = "x" * 800
    product = {
        "title": "Foo",
        "reddit_evidence": [
            {"title": "post", "selftext_excerpt": long_text, "subreddit": "test"},
        ],
    }
    ev = _collect_evidence(product)
    assert len(ev["reddit"][0]["excerpt"]) == 300


def test_collect_evidence_amazon_review_text_flagged_unavailable():
    product = {
        "title": "Foo",
        "amazon_evidence": {
            "found_matches": True,
            "aggregate_rating": 4.3,
            "total_reviews": 5400,
            "top_matches": [{"title": "Foo Pro 2024"}, {"title": "Foo Plus"}],
        },
    }
    ev = _collect_evidence(product)
    assert ev["amazon"]["review_text_available"] is False
    assert "amazon" in ev["data_sources_available"]


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def test_prompt_returns_insufficient_when_no_sources():
    """Prompt for an empty-evidence product should signal the agent
       to return INSUFFICIENT_DATA rather than fabricate."""
    ev = _collect_evidence({"title": "Test", "niche": "general"})
    p = _build_prompt(ev)
    assert "(none — return INSUFFICIENT_DATA)" in p


def test_prompt_includes_twitter_samples_when_present():
    ev = _collect_evidence({
        "title": "Test",
        "twitter_evidence": {
            "found_real_tweets": True,
            "sample_tweets": ["users are loving this"],
            "common_praise": ["good"],
            "common_complaints": ["bad"],
        },
    })
    p = _build_prompt(ev)
    assert "users are loving this" in p
    assert "PRAISE: good" in p
    assert "COMPLAINTS: bad" in p


# ---------------------------------------------------------------------------
# Provider selection (strict task→provider routing)
# ---------------------------------------------------------------------------

def test_select_provider_prefers_xai_when_key_present(monkeypatch):
    """sentiment_analysis is mapped to xAI in TASK_RECOMMENDATIONS — when
       XAI_API_KEY is set, xAI is selected."""
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")

    fake_provider = MagicMock()
    with patch("ospra_os.ai.factory.AIFactory.get_provider", return_value=fake_provider) as get_p:
        name, prov = _select_provider()
        assert name == "xai"
        get_p.assert_called_with("xai")


def test_select_provider_falls_back_to_claude_when_no_xai(monkeypatch):
    """When XAI_API_KEY isn't set, fall back to Claude (mapped to product_analysis)."""
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")

    fake_provider = MagicMock()
    with patch("ospra_os.ai.factory.AIFactory.get_provider", return_value=fake_provider) as get_p:
        name, prov = _select_provider()
        assert name == "claude"
        get_p.assert_called_with("claude")


def test_select_provider_returns_none_when_neither_configured(monkeypatch):
    """No xAI, no Claude → return None. Do NOT cross-purpose to OpenAI/Gemini."""
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    name, prov = _select_provider()
    assert name is None
    assert prov is None


# ---------------------------------------------------------------------------
# Full agent flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assess_product_returns_insufficient_when_no_evidence():
    result = await assess_product({"title": "Empty", "niche": "general"})
    assert isinstance(result, QualitativeAssessment)
    assert result.polarity == "unknown"
    assert result.recommendation == "INSUFFICIENT_DATA"
    assert result.confidence == 0
    assert any("no social evidence" in g for g in result.data_gaps)


@pytest.mark.asyncio
async def test_assess_product_returns_insufficient_when_no_provider(monkeypatch):
    """Evidence exists but no AI provider keys → clean INSUFFICIENT_DATA."""
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    product = {
        "title": "Test",
        "twitter_evidence": {
            "found_real_tweets": True,
            "sample_tweets": ["something"],
        },
    }
    result = await assess_product(product)
    assert result.recommendation == "INSUFFICIENT_DATA"
    assert result.error == "no provider available"


@pytest.mark.asyncio
async def test_assess_product_parses_valid_json_response(monkeypatch):
    """When the AI returns well-formed JSON, the agent surfaces it."""
    monkeypatch.setenv("XAI_API_KEY", "test")

    fake_response = json.dumps({
        "polarity": "positive",
        "themes": ["easy setup", "voice control works well"],
        "top_wins": ["alexa support"],
        "top_objections": ["wifi only"],
        "data_gaps": ["no amazon review text"],
        "recommendation": "WATCH",
        "confidence": 65,
    })

    fake_provider = MagicMock()
    fake_provider.chat = AsyncMock(return_value=fake_response)

    with patch("ospra_os.ai.factory.AIFactory.get_provider", return_value=fake_provider):
        result = await assess_product({
            "title": "Smart Plug",
            "twitter_evidence": {
                "found_real_tweets": True,
                "sample_tweets": ["love it"],
            },
        })

    assert result.polarity == "positive"
    assert result.recommendation == "WATCH"
    assert result.confidence == 65
    assert "easy setup" in result.themes
    assert result.provider == "xai"
    assert result.error is None


@pytest.mark.asyncio
async def test_assess_product_handles_non_json_response_gracefully(monkeypatch):
    """When the AI returns garbage, agent returns INSUFFICIENT_DATA — never raises."""
    monkeypatch.setenv("XAI_API_KEY", "test")

    fake_provider = MagicMock()
    fake_provider.chat = AsyncMock(return_value="not valid json at all")

    with patch("ospra_os.ai.factory.AIFactory.get_provider", return_value=fake_provider):
        result = await assess_product({
            "title": "Test",
            "twitter_evidence": {"found_real_tweets": True, "sample_tweets": ["x"]},
        })

    assert result.recommendation == "INSUFFICIENT_DATA"
    assert "non-JSON" in (result.error or "")


@pytest.mark.asyncio
async def test_assess_product_handles_provider_exception_gracefully(monkeypatch):
    """Provider raises mid-call → assessment surfaces error, no crash."""
    monkeypatch.setenv("XAI_API_KEY", "test")

    fake_provider = MagicMock()
    fake_provider.chat = AsyncMock(side_effect=RuntimeError("network down"))

    with patch("ospra_os.ai.factory.AIFactory.get_provider", return_value=fake_provider):
        result = await assess_product({
            "title": "Test",
            "twitter_evidence": {"found_real_tweets": True, "sample_tweets": ["x"]},
        })

    assert result.recommendation == "INSUFFICIENT_DATA"
    assert "network down" in (result.error or "")


@pytest.mark.asyncio
async def test_assess_product_strips_markdown_fences(monkeypatch):
    """Claude wraps JSON in ```json fences sometimes — agent strips them."""
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    fenced = "```json\n" + json.dumps({
        "polarity": "neutral",
        "themes": [],
        "top_wins": [],
        "top_objections": [],
        "data_gaps": [],
        "recommendation": "WATCH",
        "confidence": 40,
    }) + "\n```"

    fake_provider = MagicMock()
    fake_provider.chat = AsyncMock(return_value=fenced)

    with patch("ospra_os.ai.factory.AIFactory.get_provider", return_value=fake_provider):
        result = await assess_product({
            "title": "Test",
            "reddit_evidence": [{"title": "post", "selftext_excerpt": "hi"}],
        })

    assert result.polarity == "neutral"
    assert result.provider == "claude"
