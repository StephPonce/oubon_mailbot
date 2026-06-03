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


# ── Freshness rotation ──────────────────────────────────────────────────────

def _prods(*ids):
    return [{"product_id": i, "title": f"Product {i}", "oi_score": 50} for i in ids]


def test_apply_freshness_marks_new_and_repeats():
    prev = _prods("a", "b")
    new = _prods("a", "c")
    out = cache_warmer.apply_freshness(new, prev)
    by_id = {p["product_id"]: p for p in out}
    assert by_id["a"]["is_new_discovery"] is False
    assert by_id["a"]["repeat_count"] == 1
    assert by_id["c"]["is_new_discovery"] is True
    assert by_id["c"]["repeat_count"] == 0
    assert all(p.get("first_seen_at") for p in out)


def test_apply_freshness_carries_first_seen_forward():
    prev = cache_warmer.apply_freshness(_prods("a"), None)
    first_seen = prev[0]["first_seen_at"]
    out = cache_warmer.apply_freshness(_prods("a"), prev)
    assert out[0]["first_seen_at"] == first_seen
    assert out[0]["repeat_count"] == 1


def test_apply_freshness_rotates_new_below_top_slots():
    # Top keep_top slots untouched; below them, NEW items surface before repeats.
    prev = _prods("a", "b", "c", "d", "e")
    new = _prods("a", "b", "c", "d", "x")  # x is new, ranked last by discovery
    out = cache_warmer.apply_freshness(new, prev, keep_top=3)
    assert [p["product_id"] for p in out[:3]] == ["a", "b", "c"]  # winners stay
    assert out[3]["product_id"] == "x"  # new item promoted above repeat 'd'


def test_apply_freshness_never_touches_scores():
    prev = _prods("a", "b")
    new = _prods("a", "c")
    out = cache_warmer.apply_freshness(new, prev)
    assert all(p["oi_score"] == 50 for p in out)
