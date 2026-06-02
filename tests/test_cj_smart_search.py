"""
Tests for CJ smart_search being KEYWORD-FIRST.

Mirrors what scripts/diagnose_cj.py proved against the live API: CJ's category
endpoint returns an empty list (category search → 0 products) while keyword
search works. Discovery's primary CJ path (smart_search) must therefore return
keyword results even when every category call yields nothing.
"""

from __future__ import annotations

import pytest

from ospra_os.integrations.cj_dropshipping.client import CJDropshippingClient


def _make_client(monkeypatch) -> CJDropshippingClient:
    monkeypatch.setenv("CJ_ACCESS_TOKEN", "test-token-12345")
    client = CJDropshippingClient()
    assert client.is_available()
    return client


@pytest.mark.asyncio
async def test_smart_search_returns_keyword_results_when_category_empty(monkeypatch):
    client = _make_client(monkeypatch)
    calls = []

    async def fake_search_products(keyword="", page=1, page_size=20, category_id=None):
        calls.append({"keyword": keyword, "category_id": category_id})
        if category_id and not keyword:
            return []  # category path is broken (mirrors live behaviour)
        # keyword path works
        return [
            {"product_id": f"cj_{keyword}_{i}", "cj_pid": f"{keyword}{i}", "title": f"{keyword} item {i}"}
            for i in range(5)
        ]

    monkeypatch.setattr(client, "search_products", fake_search_products)

    results = await client.smart_search("smart plug", page_size=10)

    assert len(results) >= 5, "keyword search should yield products even when category is empty"
    assert all(r["product_id"].startswith("cj_") for r in results)
    # A keyword search must have actually been attempted.
    assert any(c["keyword"] for c in calls), "smart_search should call keyword search"


@pytest.mark.asyncio
async def test_smart_search_uses_mapped_specific_keywords(monkeypatch):
    """For a mapped query, it should search the SPECIFIC mapped phrases."""
    client = _make_client(monkeypatch)
    keyword_calls = []

    async def fake_search_products(keyword="", page=1, page_size=20, category_id=None):
        if keyword:
            keyword_calls.append(keyword)
            return [{"product_id": f"cj_{keyword}", "title": keyword}]
        return []

    monkeypatch.setattr(client, "search_products", fake_search_products)

    # "smart home" maps to specific keywords like "smart plug"/"wifi switch".
    await client.smart_search("smart home", page_size=10)
    assert keyword_calls, "should issue keyword searches"
    # None of the searched keywords should be the bare ambiguous word "smart".
    assert "smart" not in keyword_calls


@pytest.mark.asyncio
async def test_smart_search_dedupes_and_caps(monkeypatch):
    client = _make_client(monkeypatch)

    async def fake_search_products(keyword="", page=1, page_size=20, category_id=None):
        if keyword:
            # Same product id every call → must dedupe to 1.
            return [{"product_id": "cj_dupe", "title": "dupe"}]
        return []

    monkeypatch.setattr(client, "search_products", fake_search_products)
    results = await client.smart_search("led strip lights rgb", page_size=10)
    assert len(results) == 1
