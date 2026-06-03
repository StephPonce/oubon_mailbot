"""
Discovery cache warmer — makes the dashboard load instantly.

The problem: `/api/discovery/quick` already caches results by (niche, tier)
(see ospra_os/product_research/product_cache.py), so WARM hits return in ~10ms.
But nothing pre-warms it — so the first request, and the first after the TTL
expires, runs the full ~80s live discovery synchronously while the user waits
(and the browser often times out first). That's the "stuck loading / Discovery
unavailable" experience.

The fix (this module): a background job runs discovery on a schedule and fills
the cache, so a real user request almost always hits the warm path. This is how
fast product-research tools work — collection happens in the background, the
dashboard just reads precomputed results.

Cost-efficiency: discovery PRODUCTS don't depend on tier (tier only changes the
count cap + cache TTL), so we run discovery ONCE per niche and populate every
tier's cache key from that single run — not once per tier.

Runs in-process via APScheduler (same pattern as the other background jobs in
main.py), so it needs no Celery/Redis and works on the existing single Render
web service. ``discovery_func`` is injected so this module stays decoupled and
unit-testable without hitting live APIs.

Per-user / anti-saturation note (SaaS): this warms a SHARED pool for speed.
Per-user differentiation (exclude already-shown/deployed, demote cross-user
saturated products, rotate, personal ranking) is a SERVE-TIME concern applied
when reading the pool — see UserProductRecommendation / SaturationTracker. The
shared warm cache and the per-user serving layer are complementary.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_WARM_NICHES = ["smart_home"]
DEFAULT_WARM_INTERVAL_HOURS = int(os.getenv("DISCOVERY_WARM_INTERVAL_HOURS", "6"))
# How many products to fetch per warm run (a generous pool the read path
# paginates / per-user-filters down from).
WARM_FETCH_COUNT = int(os.getenv("DISCOVERY_WARM_COUNT", "50"))
# Freshness rotation: keep the top N score-ranked slots untouched (real winners
# stay visible), then surface NEW discoveries ahead of repeats below them.
FRESHNESS_KEEP_TOP = int(os.getenv("DISCOVERY_FRESHNESS_KEEP_TOP", "3"))


def _identity(p: Dict[str, Any]) -> str:
    """Stable identity for batch-over-batch comparison."""
    return str(
        p.get("product_id")
        or p.get("id")
        or (p.get("title") or "").strip().lower()[:80]
    )


def apply_freshness(
    new_batch: List[Dict[str, Any]],
    previous_batch: Optional[List[Dict[str, Any]]],
    keep_top: int = FRESHNESS_KEEP_TOP,
) -> List[Dict[str, Any]]:
    """
    Compare this warm's batch against the previous one and:

      1. Stamp every product with ``is_new_discovery`` (not in last batch),
         ``repeat_count`` (consecutive batches seen) and ``first_seen_at``
         (carried forward), so the UI can badge "NEW" and the user can see
         what changed since yesterday instead of an identical-looking page.
      2. Rotate ORDERING (scores are NOT touched — honest scoring stays
         honest): the top ``keep_top`` score-ranked slots stay as-is (a real
         winner is still a winner today), and below them NEW discoveries are
         surfaced ahead of repeats.

    Without this, deterministic discovery makes every refresh look identical
    even when it found something new buried at rank 14.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    prev_by_id = {_identity(p): p for p in (previous_batch or [])}

    for p in new_batch:
        prev = prev_by_id.get(_identity(p))
        if prev is not None:
            p["is_new_discovery"] = False
            p["repeat_count"] = int(prev.get("repeat_count") or 0) + 1
            p["first_seen_at"] = prev.get("first_seen_at") or now_iso
        else:
            p["is_new_discovery"] = True
            p["repeat_count"] = 0
            p["first_seen_at"] = now_iso

    if len(new_batch) <= keep_top:
        return new_batch

    head = new_batch[:keep_top]
    tail = new_batch[keep_top:]
    tail_new = [p for p in tail if p.get("is_new_discovery")]
    tail_rep = [p for p in tail if not p.get("is_new_discovery")]
    return head + tail_new + tail_rep


def parse_niches(raw: Optional[str]) -> List[str]:
    """Parse the DISCOVERY_WARM_NICHES env value into a clean niche list."""
    if not raw or not raw.strip():
        return list(DEFAULT_WARM_NICHES)
    seen: set = set()
    out: List[str] = []
    for part in raw.split(","):
        n = part.strip().lower().replace(" ", "_")
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out or list(DEFAULT_WARM_NICHES)


def _all_cache_tiers():
    """All tiers to populate from a single discovery run (cache is keyed by tier)."""
    from ospra_os.product_research.product_cache import SubscriptionTier
    return list(SubscriptionTier)


async def warm_one(
    niche: str,
    discovery_func: Callable[..., Awaitable[List[Dict[str, Any]]]],
    tiers=None,
    count: int = WARM_FETCH_COUNT,
) -> int:
    """
    Run discovery ONCE for a niche and populate every tier's cache key.

    Returns the number of products cached (0 on failure). Never raises — a
    warm failure must not take down the scheduler.
    """
    from ospra_os.product_research.product_cache import get_product_cache

    tiers = tiers or _all_cache_tiers()
    try:
        # ProductDiscoveryEngine.discover_products names this `max_products`,
        # not `count` — passing `count=` raises TypeError and the warm fails.
        products = await discovery_func(niche=niche, max_products=count)
    except Exception as exc:
        logger.warning("cache_warmer: discovery failed for niche=%s: %s", niche, exc)
        return 0

    if not products:
        logger.info("cache_warmer: niche=%s returned 0 products (nothing cached)", niche)
        return 0

    cache = get_product_cache()

    # Freshness pass: compare against the previous cached batch so each warm
    # rotates genuinely NEW finds toward the top and stamps is_new_discovery /
    # repeat_count / first_seen_at for the UI. Scores are not modified.
    try:
        prev_entry = cache.get(niche, tiers[0])
        previous = list(prev_entry.products) if prev_entry and getattr(prev_entry, "products", None) else None
    except Exception:
        previous = None
    products = apply_freshness(products, previous)

    for tier in tiers:
        try:
            cache.set(
                niche=niche,
                tier=tier,
                products=products,
                metadata={"source": "cache_warmer", "fetched_count": len(products)},
            )
        except Exception as exc:
            logger.warning("cache_warmer: cache.set failed niche=%s tier=%s: %s", niche, tier, exc)
    logger.info("cache_warmer: warmed niche=%s with %d products across %d tier(s)",
                niche, len(products), len(tiers))
    return len(products)


async def warm_all(
    discovery_func: Callable[..., Awaitable[List[Dict[str, Any]]]],
    niches: Optional[List[str]] = None,
) -> Dict[str, int]:
    """Warm every configured niche. Returns {niche: products_cached}."""
    niches = niches if niches is not None else parse_niches(os.getenv("DISCOVERY_WARM_NICHES"))
    results: Dict[str, int] = {}
    for niche in niches:
        results[niche] = await warm_one(niche, discovery_func)
    logger.info("cache_warmer: warm_all complete: %s", results)
    return results


def start_cache_warmer(
    discovery_func: Callable[..., Awaitable[List[Dict[str, Any]]]],
    interval_hours: int = DEFAULT_WARM_INTERVAL_HOURS,
    run_on_start: bool = True,
):
    """
    Schedule the warmer in-process (APScheduler). Call once from startup with
    the real discovery function. Returns the scheduler (or None if disabled).

    Disabled when DISCOVERY_WARM_ENABLED=false.
    """
    if os.getenv("DISCOVERY_WARM_ENABLED", "true").lower() != "true":
        logger.info("cache_warmer: disabled (DISCOVERY_WARM_ENABLED=false)")
        return None

    import asyncio

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except Exception as exc:  # pragma: no cover
        logger.warning("cache_warmer: APScheduler unavailable, not scheduling: %s", exc)
        return None

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        warm_all,
        "interval",
        hours=max(1, interval_hours),
        args=[discovery_func],
        id="discovery_cache_warmer",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("cache_warmer: scheduled every %dh", interval_hours)

    if run_on_start:
        # Fire one warm shortly after boot so the cache is hot for early users,
        # without blocking startup.
        try:
            asyncio.get_event_loop().create_task(warm_all(discovery_func))
        except Exception as exc:  # pragma: no cover
            logger.warning("cache_warmer: initial warm could not be scheduled: %s", exc)

    return scheduler
