"""
Phase 1 step 1 — Apify client request contract (fail-if-reverted).

Two long-standing bugs in base_apify.run_actor:
  1. ``memory`` was merged INTO the actor input JSON. Apify reads run options
     from QUERY PARAMS; inside the input it's ignored for provisioning and
     rejects runs on actors with strict input schemas.
  2. Dataset items were fetched with a single ``limit=100`` request — any run
     producing more than 100 items silently lost the rest.

These tests pin the fixed contract using httpx.MockTransport (no live Apify
call, no credits). Live-run verification is tracked separately (account is
over its monthly cap until 2026-08-07).
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

os.environ.setdefault("APIFY_API_TOKEN", "test-token-apify-contract")

from ospra_os.product_research.connectors.apify import base_apify


@pytest.fixture
def apify_env(monkeypatch):
    """MockTransport-backed ApifyClient + captured requests. Serves a run
    that SUCCEEDS with a 1,150-item dataset (2 pages: 1000 + 150)."""
    captured = {"start": None, "dataset_requests": []}
    TOTAL_ITEMS = 1150

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/runs") and request.method == "POST":
            captured["start"] = request
            return httpx.Response(201, json={"data": {"id": "run-1"}})
        if path.endswith("/actor-runs/run-1"):
            return httpx.Response(200, json={
                "data": {"status": "SUCCEEDED", "defaultDatasetId": "ds-1"}
            })
        if path.endswith("/datasets/ds-1/items"):
            captured["dataset_requests"].append(request)
            offset = int(request.url.params.get("offset", 0))
            limit = int(request.url.params.get("limit", 1000))
            end = min(offset + limit, TOTAL_ITEMS)
            page = [{"i": n} for n in range(offset, end)]
            return httpx.Response(200, json=page)
        return httpx.Response(404, json={"error": f"unexpected {path}"})

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_async_client(transport=transport, **{
            k: v for k, v in kwargs.items() if k in ("timeout",)
        })

    monkeypatch.setattr(base_apify.httpx, "AsyncClient", client_factory)

    async def instant_sleep(_secs):
        return None

    monkeypatch.setattr(base_apify.asyncio, "sleep", instant_sleep)

    return base_apify.ApifyClient(api_token="test-token-apify-contract"), captured


class TestMemoryAsRunOption:
    @pytest.mark.asyncio
    async def test_memory_is_a_query_param_not_input(self, apify_env):
        client, captured = apify_env
        run_input = {"hashtags": ["x"], "resultsPerPage": 5}

        await client.run_actor("someone/actor", run_input, memory_mbytes=256)

        start = captured["start"]
        assert start is not None
        # Run options ride as query params...
        assert start.url.params.get("memory") == "256"
        assert start.url.params.get("timeout") is not None
        # ...and the body is EXACTLY the actor input — no injected keys.
        body = json.loads(start.content.decode())
        assert body == run_input
        assert "memory" not in body

    @pytest.mark.asyncio
    async def test_breaker_and_input_survive(self, apify_env):
        """The input passes through unmodified for arbitrary shapes."""
        client, captured = apify_env
        run_input = {"nested": {"a": 1}, "list": [1, 2, 3]}

        await client.run_actor("someone/actor", run_input)

        assert json.loads(captured["start"].content.decode()) == run_input


class TestDatasetPagination:
    @pytest.mark.asyncio
    async def test_returns_more_than_100_items(self, apify_env):
        """The old single limit=100 request lost items 101+. All 1,150 must
        come back via pagination."""
        client, captured = apify_env

        results = await client.run_actor("someone/actor", {"q": "x"})

        assert len(results) == 1150
        assert results[0] == {"i": 0}
        assert results[-1] == {"i": 1149}
        # Two pages: offset 0 (1000) + offset 1000 (150; short page stops loop).
        offsets = [int(r.url.params.get("offset", 0)) for r in captured["dataset_requests"]]
        assert offsets == [0, 1000]

    @pytest.mark.asyncio
    async def test_max_items_caps_fetch(self, apify_env):
        """Dev credit hygiene: max_items stops fetching early."""
        client, captured = apify_env

        results = await client.run_actor("someone/actor", {"q": "x"}, max_items=20)

        assert len(results) == 20
        # One request, limited to exactly what was asked.
        assert len(captured["dataset_requests"]) == 1
        assert captured["dataset_requests"][0].url.params.get("limit") == "20"
