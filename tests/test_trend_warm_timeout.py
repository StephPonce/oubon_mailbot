"""
Trend-warm Apify timeout threading (#54 follow-up).

The actor takes ~12 min but the connector hardcoded a 120s run timeout, so
the off-request warm cron abandoned every run at ~2 min (credits still spent)
and fell back to pytrends. These pin that timeout_secs threads from
get_interest -> _fetch_trends_batch -> run_actor, with the request-path
default (120) and the cron's long timeout (1200).
"""

import pytest

from ospra_os.product_research.connectors.apify.google_trends_apify import ApifyGoogleTrends


class _RecordingClient:
    def __init__(self):
        self.calls = []

    async def run_actor(self, **kwargs):
        self.calls.append(kwargs)
        return []  # no items — we only care about the timeout passed in


@pytest.fixture()
def connector():
    c = ApifyGoogleTrends.__new__(ApifyGoogleTrends)
    c.client = _RecordingClient()
    c._cache = {}
    # _get_cached / _set_cache read self._cache via the real helpers; provide
    # a no-op cache so every term is treated as uncached.
    c._get_cached = lambda key: None
    c._set_cache = lambda key, val: None
    c._get_cache_key = lambda term, tf, geo: f"{term}:{tf}:{geo}"
    return c


@pytest.mark.asyncio
async def test_default_timeout_is_request_path_120(connector):
    await connector.get_interest(["smart plug"])
    assert connector.client.calls[0]["timeout_secs"] == 120


@pytest.mark.asyncio
async def test_timeout_threads_through_to_run_actor(connector):
    await connector.get_interest(["smart plug", "video doorbell"], timeout_secs=1200)
    assert connector.client.calls, "run_actor should have been called"
    for call in connector.client.calls:
        assert call["timeout_secs"] == 1200


@pytest.mark.asyncio
async def test_warm_via_apify_uses_long_timeout(monkeypatch):
    """The cron path must request the 20-minute timeout, not the 120s default."""
    import ospra_os.tasks.trend_warm as tw

    recorded = {}

    class _FakeClient:
        async def get_interest(self, **kwargs):
            recorded.update(kwargs)
            return []

    monkeypatch.setattr(
        "ospra_os.product_research.connectors.apify.google_trends_apify.ApifyGoogleTrends",
        lambda *a, **k: _FakeClient(),
    )
    await tw.warm_via_apify(["smart plug"])
    assert recorded.get("timeout_secs") == 1200
