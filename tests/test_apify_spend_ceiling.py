"""Per-actor start ceiling — the backstop the circuit breaker cannot provide.

The existing breaker trips on quota/403 FAILURES. It is blind to an actor that
keeps SUCCEEDING while billing per result, which is exactly how
trakk/tiktok-shop-search-scraper spent $8.42 across 18 successful runs: nothing
ever failed, so nothing ever tripped.
"""

import asyncio

import pytest

from ospra_os.product_research.connectors.apify import base_apify as b


@pytest.fixture(autouse=True)
def _clean_state():
    b.reset_apify_budget()
    yield
    b.reset_apify_budget()


def _client_with_fake_live(calls):
    client = b.ApifyClient(api_token="test-token")

    async def fake_live(actor_id, run_input, timeout_secs, memory_mbytes, max_items):
        calls.append(actor_id)
        # Mirror what the real live path does so the ceiling sees the starts.
        sba = b._apify_run_state["starts_by_actor"]
        sba[actor_id] = sba.get(actor_id, 0) + 1
        return [{"ok": 1}], True

    client._run_actor_live = fake_live
    return client


def test_ceiling_stops_runaway_starts(monkeypatch):
    monkeypatch.setattr(b, "_APIFY_MAX_STARTS_PER_ACTOR", 5)
    calls = []
    client = _client_with_fake_live(calls)

    async def run():
        # Distinct inputs, so the response cache never hides the problem.
        for i in range(20):
            await client.run_actor("acme/expensive", {"q": i})

    asyncio.run(run())
    assert len(calls) == 5, "the ceiling must stop further metered starts"


def test_ceiling_is_per_actor_not_global(monkeypatch):
    monkeypatch.setattr(b, "_APIFY_MAX_STARTS_PER_ACTOR", 3)
    calls = []
    client = _client_with_fake_live(calls)

    async def run():
        for i in range(6):
            await client.run_actor("acme/one", {"q": i})
        for i in range(6):
            await client.run_actor("acme/two", {"q": i})

    asyncio.run(run())
    assert calls.count("acme/one") == 3
    assert calls.count("acme/two") == 3, "one actor's ceiling must not gate another"


def test_report_exposes_per_actor_starts(monkeypatch):
    monkeypatch.setattr(b, "_APIFY_MAX_STARTS_PER_ACTOR", 10)
    calls = []
    client = _client_with_fake_live(calls)

    asyncio.run(client.run_actor("acme/tracked", {"q": 1}))
    report = b.get_apify_budget_report()

    assert report["starts_by_actor"].get("acme/tracked") == 1, (
        "per-actor starts must be visible in the spend report — a single "
        "aggregate count hid which actor was burning the budget"
    )
