"""
Tests for the discovery cache warmer.

Verifies the cost-efficient behaviour (discovery runs ONCE per niche, all tiers
populated from it), resilience (failures never raise), and niche parsing.
Discovery + cache are mocked so nothing hits live APIs.
"""

from __future__ import annotations

import pytest

from ospra_os.intelligence import cache_warmer


class _FakeCache:
    def __init__(self):
        self.sets = []

    def set(self, niche, tier, products, metadata=None):
        self.sets.append((niche, tier, len(products)))


def test_parse_niches_default():
    assert cache_warmer.parse_niches(None) == ["smart_home"]
    assert cache_warmer.parse_niches("   ") == ["smart_home"]


def test_parse_niches_cleans_and_dedupes():
    assert cache_warmer.parse_niches("Smart Home, pet, pet , kitchen") == [
        "smart_home", "pet", "kitchen",
    ]


@pytest.mark.asyncio
async def test_warm_one_runs_discovery_once_and_caches_all_tiers(monkeypatch):
    from ospra_os.product_research.product_cache import SubscriptionTier

    calls = {"n": 0}

    async def fake_discovery(niche, max_products):
        calls["n"] += 1
        return [{"id": i} for i in range(5)]

    fake_cache = _FakeCache()
    monkeypatch.setattr(
        "ospra_os.product_research.product_cache.get_product_cache",
        lambda: fake_cache,
    )

    cached = await cache_warmer.warm_one("smart_home", fake_discovery)

    assert cached == 5
    assert calls["n"] == 1  # discovery ran exactly ONCE (cost-efficient)
    # ...but every tier's cache key was populated from that single run
    assert len(fake_cache.sets) == len(list(SubscriptionTier))


@pytest.mark.asyncio
async def test_warm_one_never_raises_on_discovery_failure():
    async def boom(niche, max_products):
        raise RuntimeError("apify down")

    assert await cache_warmer.warm_one("smart_home", boom) == 0


@pytest.mark.asyncio
async def test_warm_one_empty_products_caches_nothing(monkeypatch):
    fake_cache = _FakeCache()
    monkeypatch.setattr(
        "ospra_os.product_research.product_cache.get_product_cache",
        lambda: fake_cache,
    )

    async def empty(niche, max_products):
        return []

    assert await cache_warmer.warm_one("smart_home", empty) == 0
    assert fake_cache.sets == []


@pytest.mark.asyncio
async def test_warm_all_iterates_all_niches(monkeypatch):
    monkeypatch.setattr(
        "ospra_os.product_research.product_cache.get_product_cache",
        lambda: _FakeCache(),
    )

    async def fake_discovery(niche, max_products):
        return [{"id": 1}]

    res = await cache_warmer.warm_all(fake_discovery, niches=["a", "b", "c"])
    assert set(res.keys()) == {"a", "b", "c"}
    assert all(v == 1 for v in res.values())
