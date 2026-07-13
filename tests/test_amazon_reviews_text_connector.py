"""
Tests for the Apify Amazon per-product review-text connector — Phase K.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ospra_os.product_research.connectors.apify.amazon_reviews_text import (
    AmazonReviewsTextApify,
    _extract_asin,
)


def _run(coro):
    # asyncio.run() is immune to a prior TestClient test leaving the thread
    # with no current event loop (get_event_loop() raised on 3.12) — the
    # ordering-dependent flakiness fixed across the connector test suite.
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# ASIN extraction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.amazon.com/dp/B0ABCD1234", "B0ABCD1234"),
        ("https://www.amazon.com/dp/B0ABCD1234?tag=foo", "B0ABCD1234"),
        ("https://www.amazon.com/Some-Product-Name/dp/B0XYZ56789/ref=sr_1_1", "B0XYZ56789"),
        ("https://www.amazon.com/gp/product/B0AAAA0000/ref=cm_cr", "B0AAAA0000"),
        ("https://www.amazon.com/dp/b0lower123", "B0LOWER123"),  # case-insensitive (10 chars)
        ("https://www.amazon.com/", None),                          # no ASIN
        ("", None),
        (None, None),
    ],
)
def test_extract_asin(url, expected):
    assert _extract_asin(url) == expected


# ---------------------------------------------------------------------------
# Availability + arg validation
# ---------------------------------------------------------------------------

def test_unavailable_when_no_apify_token(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    with pytest.raises(ValueError):
        AmazonReviewsTextApify(api_token=None)


def test_returns_unavailable_when_no_asin_or_url():
    c = AmazonReviewsTextApify(api_token="fake-token")
    result = _run(c.fetch_reviews(asin=None, product_url=None))
    assert result["available"] is False
    assert "asin or product_url" in (result.get("error") or "")


def test_extracts_asin_from_url_when_asin_omitted():
    c = AmazonReviewsTextApify(api_token="fake-token")

    actor_results = [
        {
            "reviewDescription": "Worked perfectly out of the box.",
            "ratingScore": 5,
            "verifiedPurchase": True,
        }
    ]

    captured = {}

    async def _fake_run(actor_id, run_input, **kw):
        captured["asins"] = run_input.get("asins")
        captured["productUrls"] = run_input.get("productUrls")
        return actor_results

    with patch.object(c.client, "run_actor", new=AsyncMock(side_effect=_fake_run)):
        result = _run(c.fetch_reviews(
            product_url="https://www.amazon.com/dp/B0XYZ56789",
        ))

    assert result["available"] is True
    assert result["asin"] == "B0XYZ56789"
    assert captured["asins"] == ["B0XYZ56789"]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_parses_reviews():
    c = AmazonReviewsTextApify(api_token="fake-token")

    actor_results = [
        {
            "reviewDescription": "Best smart plug I've owned. Easy setup.",
            "reviewTitle": "Just works",
            "ratingScore": 5,
            "verifiedPurchase": True,
            "helpfulCount": 23,
            "reviewedIn": "Reviewed in the United States on March 1, 2026",
        },
        {
            "reviewDescription": "App is buggy, kept losing wifi after a week.",
            "reviewTitle": "Disappointed",
            "ratingScore": 2,
            "verifiedPurchase": True,
            "helpfulCount": 8,
            "reviewedIn": "Reviewed in the United States on March 12, 2026",
        },
        {
            "reviewDescription": "Decent for the price.",
            "reviewTitle": "OK",
            "ratingScore": 3,
            "verifiedPurchase": False,
            "helpfulCount": 0,
        },
    ]

    with patch.object(c.client, "run_actor", new=AsyncMock(return_value=actor_results)):
        result = _run(c.fetch_reviews(asin="B0XYZ56789", max_reviews=5))

    assert result["available"] is True
    assert result["asin"] == "B0XYZ56789"
    assert result["review_count_returned"] == 3
    assert result["average_rating"] == round((5 + 2 + 3) / 3, 2)
    # 2 of 3 verified
    assert abs(result["verified_share"] - (2 / 3)) < 0.01
    assert len(result["reviews"]) == 3
    assert result["reviews"][0]["title"] == "Just works"
    assert result["reviews"][0]["helpful_count"] == 23


def test_actor_failure_returns_error_envelope():
    c = AmazonReviewsTextApify(api_token="fake-token")

    with patch.object(
        c.client, "run_actor", new=AsyncMock(side_effect=Exception("captcha"))
    ):
        result = _run(c.fetch_reviews(asin="B0AAAA0000"))

    assert result["available"] is False
    assert "captcha" in (result.get("error") or "")
    assert result.get("asin") == "B0AAAA0000"


def test_no_results_returns_unavailable():
    c = AmazonReviewsTextApify(api_token="fake-token")

    with patch.object(c.client, "run_actor", new=AsyncMock(return_value=[])):
        result = _run(c.fetch_reviews(asin="B0BBBB0000"))

    assert result["available"] is False
    assert result.get("asin") == "B0BBBB0000"


def test_reviews_without_text_are_dropped():
    c = AmazonReviewsTextApify(api_token="fake-token")

    actor_results = [
        {"reviewDescription": "real review", "ratingScore": 4, "verifiedPurchase": True},
        {"reviewDescription": "", "ratingScore": 5},          # empty — drop
        {"reviewTitle": "title only", "ratingScore": 3},      # no body — drop
        {"reviewDescription": None, "ratingScore": 5},        # null — drop
    ]

    with patch.object(c.client, "run_actor", new=AsyncMock(return_value=actor_results)):
        result = _run(c.fetch_reviews(asin="B0CCCC0000"))

    assert result["available"] is True
    assert result["review_count_returned"] == 1
    assert result["reviews"][0]["text"] == "real review"


def test_text_is_capped_for_prompt_budget():
    c = AmazonReviewsTextApify(api_token="fake-token")
    long_text = "X" * 5000
    actor_results = [{"reviewDescription": long_text, "ratingScore": 5}]

    with patch.object(c.client, "run_actor", new=AsyncMock(return_value=actor_results)):
        result = _run(c.fetch_reviews(asin="B0DDDD0000"))

    assert result["available"] is True
    # Each review text capped to 400 chars to keep prompts tight
    assert len(result["reviews"][0]["text"]) == 400
