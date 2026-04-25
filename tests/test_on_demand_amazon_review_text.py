"""
Tests for ProductDiscoveryEngine.fetch_amazon_review_text — on-demand
per-product Amazon review-text fetch with 24h ASIN-level cache (Phase K
revision: bulk-at-discovery → on-demand on-click).
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def fresh_discovery(monkeypatch):
    """Build a ProductDiscoveryEngine instance without touching real env tokens.

    We don't run __init__ (it spins up real connectors); instead we
    construct a bare object and only set the fields fetch_amazon_review_text
    actually reads. Class-level cache is reset between tests.
    """
    from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine

    pd = ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)
    pd.amazon_reviews_text_available = True
    pd.amazon_reviews_text = type("Stub", (), {})()
    # Cache is class-level; reset for isolation.
    ProductDiscoveryEngine._amazon_review_text_cache.clear()
    return pd


@pytest.fixture
def amz_text_payload():
    return {
        "available": True,
        "asin": "B0XYZ56789",
        "review_count_returned": 2,
        "average_rating": 4.5,
        "verified_share": 1.0,
        "reviews": [
            {"text": "Worked great.", "rating": 5, "verified": True},
            {"text": "Pretty good, app is buggy though.", "rating": 4, "verified": True},
        ],
        "error": None,
    }


def _product_with_asin(asin="B0XYZ56789"):
    return {
        "title": "Smart Plug",
        "amazon_evidence": {
            "found_matches": True,
            "top_matches": [
                {
                    "asin": asin,
                    "url": f"https://www.amazon.com/dp/{asin}",
                    "title": "Smart Plug",
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Guard rails: no ASIN, no connector → return None, don't crash
# ---------------------------------------------------------------------------

def test_returns_none_when_connector_unavailable(fresh_discovery):
    fresh_discovery.amazon_reviews_text_available = False
    out = _run(fresh_discovery.fetch_amazon_review_text(_product_with_asin()))
    assert out is None


def test_returns_none_when_no_amazon_match(fresh_discovery):
    product = {"title": "Smart Plug"}
    out = _run(fresh_discovery.fetch_amazon_review_text(product))
    assert out is None


def test_returns_none_when_top_match_has_no_asin_or_url(fresh_discovery):
    product = {
        "title": "Smart Plug",
        "amazon_evidence": {"top_matches": [{"title": "matched but no asin"}]},
    }
    out = _run(fresh_discovery.fetch_amazon_review_text(product))
    assert out is None


# ---------------------------------------------------------------------------
# Happy path + cache behavior
# ---------------------------------------------------------------------------

def test_first_call_fetches_and_attaches_to_product(fresh_discovery, amz_text_payload):
    fresh_discovery.amazon_reviews_text.fetch_reviews = AsyncMock(
        return_value=amz_text_payload
    )

    product = _product_with_asin()
    out = _run(fresh_discovery.fetch_amazon_review_text(product))

    assert out is not None
    assert out["available"] is True
    assert out["cached"] is False
    # Attached on the product so the qualitative agent picks it up
    assert product["amazon_review_text"]["asin"] == "B0XYZ56789"
    fresh_discovery.amazon_reviews_text.fetch_reviews.assert_awaited_once()


def test_second_call_within_ttl_uses_cache(fresh_discovery, amz_text_payload):
    fresh_discovery.amazon_reviews_text.fetch_reviews = AsyncMock(
        return_value=amz_text_payload
    )

    product = _product_with_asin()
    first = _run(fresh_discovery.fetch_amazon_review_text(product))
    second = _run(fresh_discovery.fetch_amazon_review_text(product))

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["asin"] == "B0XYZ56789"
    # Only ONE actor call across both clicks
    fresh_discovery.amazon_reviews_text.fetch_reviews.assert_awaited_once()


def test_stale_cache_refetches(fresh_discovery, amz_text_payload):
    from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine

    fresh_discovery.amazon_reviews_text.fetch_reviews = AsyncMock(
        return_value=amz_text_payload
    )
    product = _product_with_asin()

    # Seed the cache at a fake old timestamp (older than TTL)
    stale_ts = time.time() - (ProductDiscoveryEngine._AMAZON_REVIEW_TEXT_TTL_SECONDS + 60)
    ProductDiscoveryEngine._amazon_review_text_cache["B0XYZ56789"] = (stale_ts, amz_text_payload)

    out = _run(fresh_discovery.fetch_amazon_review_text(product))
    assert out["cached"] is False  # refetched, not served stale
    fresh_discovery.amazon_reviews_text.fetch_reviews.assert_awaited_once()


def test_cache_keyed_by_asin_so_separate_products_share_one_fetch(
    fresh_discovery, amz_text_payload
):
    """Two product dicts that both surface the SAME Amazon match should
    share one Apify call (the bill-once-per-ASIN guarantee)."""
    fresh_discovery.amazon_reviews_text.fetch_reviews = AsyncMock(
        return_value=amz_text_payload
    )

    p1 = _product_with_asin()
    p2 = _product_with_asin()
    p2["title"] = "Different supplier listing for the same Amazon ASIN"

    _run(fresh_discovery.fetch_amazon_review_text(p1))
    out2 = _run(fresh_discovery.fetch_amazon_review_text(p2))

    assert out2["cached"] is True
    fresh_discovery.amazon_reviews_text.fetch_reviews.assert_awaited_once()


# ---------------------------------------------------------------------------
# Failure: actor returns unavailable, or raises
# ---------------------------------------------------------------------------

def test_actor_unavailable_response_returns_none(fresh_discovery):
    fresh_discovery.amazon_reviews_text.fetch_reviews = AsyncMock(
        return_value={"available": False, "error": "no reviews returned"}
    )

    product = _product_with_asin()
    out = _run(fresh_discovery.fetch_amazon_review_text(product))
    assert out is None
    # Critically: a failed call should NOT poison the cache
    from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine
    assert "B0XYZ56789" not in ProductDiscoveryEngine._amazon_review_text_cache


def test_actor_exception_returns_none(fresh_discovery):
    fresh_discovery.amazon_reviews_text.fetch_reviews = AsyncMock(
        side_effect=RuntimeError("captcha")
    )

    product = _product_with_asin()
    out = _run(fresh_discovery.fetch_amazon_review_text(product))
    assert out is None
