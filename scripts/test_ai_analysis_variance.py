"""
Task #11: Regression test for AI analysis variance.

Bug we're locking down:
   User opens a product, Claude returns {verdict: 'BUY', confidence: 85}.
   User hits refresh 30 seconds later, Claude returns {verdict: 'CONSIDER',
   confidence: 62}. Same product, same data. The user loses trust.

Two variance sources we fix:
  1. temperature=1.0 default → swap to 0.2 (low-but-nonzero)
  2. Prompt built from unsorted dict iteration → make it byte-stable
  3. No server cache → add a 15-minute TTL cache keyed on the product's
     actual signals so repeated refreshes within the window skip the API.

This test mocks httpx so it runs offline. It asserts:
  A) The prompt for the same product is byte-for-byte identical across two
     calls (regardless of dict insertion order).
  B) The JSON body POSTed to Claude includes temperature=0.2.
  C) Two sequential calls with identical inputs call the API EXACTLY ONCE
     (cache hit on the second call).
  D) Calls with DIFFERENT inputs do NOT collide in the cache.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Make sure env var is set before the module parses it.
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-offline-run")

from ospra_os.api import product_analysis_routes as par


# ----- Fake Claude response --------------------------------------------

FAKE_ANALYSIS_JSON = """
{
  "summary": "Strong dropshipping candidate with solid margins.",
  "verdict": "BUY",
  "confidence": 82,
  "strengths": ["margin", "trend", "sentiment"],
  "risks": ["shipping time"],
  "target_audience": "Smart home enthusiasts, 25-45",
  "marketing_angles": ["convenience", "ambient lighting", "voice control"],
  "ad_spend_recommendation": "$10/day, scale at ROAS 2.5",
  "price_strategy": "Test $24.99 for perceived premium",
  "competition_assessment": "Moderate, differentiate on shipping",
  "seasonal_factors": "Q4 spike likely"
}
"""


def _build_mock_client():
    """Mock httpx.AsyncClient so we never call the real API."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"content": [{"text": FAKE_ANALYSIS_JSON}]}
    client.post = AsyncMock(return_value=response)
    return client


# ----- Tests ------------------------------------------------------------

async def run_tests():
    # Clean cache before running
    par._clear_analysis_cache()

    title = "Smart LED Strip Light"

    # Build the same product dict in two different key orders to prove
    # the prompt is deterministic regardless of insertion order.
    product_a = {
        "niche": "smart_home",
        "cost_price": 8.0,
        "suggested_price": 24.99,
        "profit": 16.99,
        "oi_score": 73.5,
        "demand_score": 62.0,
        "trend_score": 68.0,
        "sentiment_score": 71.0,
        "sales_count": 1250,
        "rating": 4.6,
        "source": "aliexpress",
        "data_sources": {
            "aliexpress": {"available": True},
            "amazon_reviews": {"available": True},
            "google_trends": {"available": True},
        },
    }
    # Same signals, different key order.
    product_b = {
        "data_sources": {
            "google_trends": {"available": True},
            "aliexpress": {"available": True},
            "amazon_reviews": {"available": True},
        },
        "source": "aliexpress",
        "rating": 4.6,
        "sales_count": 1250,
        "sentiment_score": 71.0,
        "trend_score": 68.0,
        "demand_score": 62.0,
        "oi_score": 73.5,
        "profit": 16.99,
        "suggested_price": 24.99,
        "cost_price": 8.0,
        "niche": "smart_home",
    }

    # ---- ASSERTION A: deterministic prompt construction ---------------
    prompt_a = par._build_analysis_prompt(title, product_a)
    prompt_b = par._build_analysis_prompt(title, product_b)
    assert prompt_a == prompt_b, (
        "Prompt must be byte-identical regardless of dict key order.\n"
        f"A:\n{prompt_a}\nB:\n{prompt_b}"
    )
    print("[A PASS] Prompts are byte-identical across dict orderings.")

    # ---- ASSERTION B + C: temperature sent + cache dedupes ------------
    mock_client = _build_mock_client()
    with patch.object(par.httpx, "AsyncClient", return_value=mock_client):
        r1 = await par._analyze_with_claude(title, product_a)
        r2 = await par._analyze_with_claude(title, product_b)  # should cache-hit

    assert r1 is not None, "First call should have returned a parsed analysis"
    assert r2 is not None, "Second call should have returned a parsed analysis"
    assert r1 == r2, "Cached result must equal the original result"

    # B: verify temperature was sent
    assert mock_client.post.call_count == 1, (
        f"Cache should have prevented a 2nd API call. Got {mock_client.post.call_count} calls."
    )
    posted_body = mock_client.post.call_args.kwargs["json"]
    assert posted_body.get("temperature") == par.ANALYSIS_TEMPERATURE, (
        f"Expected temperature={par.ANALYSIS_TEMPERATURE} in POST body. Got: {posted_body.get('temperature')}"
    )
    print(f"[B PASS] POST body includes temperature={par.ANALYSIS_TEMPERATURE}.")
    print("[C PASS] Two identical-input calls → API called exactly once (cache hit on 2nd).")

    # ---- ASSERTION D: different inputs don't collide ------------------
    product_different = dict(product_a)
    product_different["oi_score"] = 50.0  # a meaningful signal change

    mock_client2 = _build_mock_client()
    with patch.object(par.httpx, "AsyncClient", return_value=mock_client2):
        r3 = await par._analyze_with_claude(title, product_different)

    assert r3 is not None
    # This is a DIFFERENT cache key → must call API (not the old one)
    assert mock_client2.post.call_count == 1, (
        "Different product data must produce its own API call, not reuse cache"
    )
    print("[D PASS] Different input → new API call (no stale cache reuse).")

    # ---- ASSERTION E: cache key is sensitive to meaningful fields but
    #                   stable under cosmetic differences (whitespace, float noise)
    product_cosmetic = dict(product_a)
    product_cosmetic["cost_price"] = 8.00000001  # float noise
    product_cosmetic["suggested_price"] = 24.989999  # rounds to 24.99

    key_original = par._analysis_cache_key(title, product_a)
    key_cosmetic = par._analysis_cache_key(title, product_cosmetic)
    assert key_original == key_cosmetic, (
        "Cache key should be stable under float rounding noise. "
        f"original={key_original} cosmetic={key_cosmetic}"
    )
    print("[E PASS] Cache key stable under float noise (rounded before hashing).")

    print("\n[PASS] AI analysis variance locked down.")
    return 0


if __name__ == "__main__":
    rc = asyncio.run(run_tests())
    sys.exit(rc)
