"""
Tests for the qualitative source-value eval harness itself.

We run only in mock mode here so this test never burns AI credits.
The eval's --live mode is exercised manually.
"""

from __future__ import annotations

import asyncio

import pytest

from ospra_os.evals.qualitative_source_value import (
    ABLATABLE_SOURCES,
    _MockProvider,
    _ablate,
    all_fixtures,
    evaluate,
    summarize,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Fixtures load and have the expected shape
# ---------------------------------------------------------------------------

def test_all_fixtures_have_titles_and_niches():
    fixtures = all_fixtures()
    assert len(fixtures) >= 10
    for f in fixtures:
        assert f.get("title"), f"fixture missing title: {f}"
        # niche optional but title is mandatory


def test_ablate_removes_top_level_source():
    p = {"title": "x", "twitter_evidence": {"a": 1}, "reddit_evidence": [{"b": 2}]}
    out = _ablate(p, "twitter_evidence")
    assert "twitter_evidence" not in out
    assert "reddit_evidence" in out  # untouched


def test_ablate_handles_nested_data_sources_for_trends():
    p = {
        "title": "x",
        "data_sources": {
            "google_trends": {"trend_direction": "rising"},
            "shopify": {"foo": "bar"},
        },
    }
    out = _ablate(p, "data_sources")
    # google_trends removed, shopify preserved
    assert "google_trends" not in out["data_sources"]
    assert "shopify" in out["data_sources"]


def test_ablate_drops_data_sources_when_empty():
    p = {"title": "x", "data_sources": {"google_trends": {}}}
    out = _ablate(p, "data_sources")
    assert "data_sources" not in out


# ---------------------------------------------------------------------------
# End-to-end: run the eval in mock mode and verify the report shape
# ---------------------------------------------------------------------------

def test_evaluate_mock_mode_produces_results_for_all_fixtures():
    results = _run(evaluate(mock=True))
    assert len(results) == len(all_fixtures())

    for r in results:
        # Every result has the structural fields we render in the report.
        assert isinstance(r.fixture_title, str)
        assert isinstance(r.full_recommendation, str)
        assert r.full_recommendation in (
            "BUY", "WATCH", "SKIP", "INSUFFICIENT_DATA",
        ), f"unexpected recommendation: {r.full_recommendation}"
        # Each ablation has the required keys
        for source_label, _ in ABLATABLE_SOURCES:
            assert source_label in r.ablations
            ab = r.ablations[source_label]
            assert "rec_flipped" in ab
            assert "polarity_flipped" in ab
            assert "theme_overlap" in ab
            assert "confidence_delta" in ab


def test_evaluate_mock_strong_buy_fixture_recognized():
    """The strong-multi-source-buy fixture should NOT come back as
    INSUFFICIENT_DATA in mock mode — that would mean my mock provider
    isn't matching against the prompt evidence sections."""
    results = _run(evaluate(mock=True, limit=1))
    first = results[0]
    assert first.full_recommendation != "INSUFFICIENT_DATA", (
        f"mock provider failed to read evidence sections in prompt; "
        f"got {first.full_recommendation}"
    )


def test_evaluate_mock_insufficient_data_fixture_returns_insufficient():
    """The empty fixture (last one) should return INSUFFICIENT_DATA."""
    results = _run(evaluate(mock=True))
    last = results[-1]  # _fixture_insufficient_data
    assert last.full_recommendation == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Summary aggregation
# ---------------------------------------------------------------------------

def test_summarize_returns_per_source_metrics():
    results = _run(evaluate(mock=True))
    summary = summarize(results)
    assert summary["n_fixtures"] == len(results)
    for source_label, _ in ABLATABLE_SOURCES:
        assert source_label in summary["per_source"]
        agg = summary["per_source"][source_label]
        assert 0.0 <= agg["rec_flip_rate"] <= 1.0
        assert 0.0 <= agg["polarity_flip_rate"] <= 1.0
        assert 0.0 <= agg["avg_theme_overlap"] <= 1.0


def test_summarize_at_least_one_source_has_nonzero_flip_rate():
    """Sanity check: in mock mode at least one source should move the
    needle on at least one fixture, otherwise the harness can't tell
    sources apart."""
    results = _run(evaluate(mock=True))
    summary = summarize(results)
    flip_rates = [agg["rec_flip_rate"] for agg in summary["per_source"].values()]
    assert max(flip_rates) > 0.0, (
        "No source ablation moved any recommendation in mock mode — "
        "the mock provider's heuristics aren't differentiating sources."
    )


# ---------------------------------------------------------------------------
# Mock provider sanity
# ---------------------------------------------------------------------------

def test_mock_provider_returns_valid_json():
    import json
    mock = _MockProvider()
    raw = _run(mock.chat("--- twitter ---\nworked great\nlove this product\nbest purchase\n--- reddit ---\nworked great"))
    parsed = json.loads(raw)
    assert "recommendation" in parsed
    assert "polarity" in parsed
    assert "confidence" in parsed
