"""
TIER-BASED PRODUCT CACHE
=========================

Provides instant product loading using tier-appropriate cache TTLs.

Cache TTL Philosophy:
- Cache TTL matches rate limit cooldown
- Users get instant loads while in cooldown anyway
- Fresh discovery only when cooldown allows
- Higher tiers = fresher data

Performance Impact:
- NEST (4h cache): Instant load for 4 hours, then fresh
- FLIGHT (2h cache): Instant load for 2 hours, then fresh
- SOAR (30m cache): Instant load for 30 min, then fresh
- STRATOSPHERE (5m cache): Near real-time with minimal caching
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import logging
import hashlib
import json

logger = logging.getLogger(__name__)

# ============================================================================
# SUBSCRIPTION TIER (Local definition to avoid circular imports)
# ============================================================================
# This duplicates ospra_os.core.tiers.SubscriptionTier but avoids the heavy
# import chain that includes SQLAlchemy-dependent modules.
# Values MUST match the canonical definition in ospra_os/core/tiers.py

class SubscriptionTier(str, Enum):
    """
    Subscription tiers for caching purposes.
    Mirrors ospra_os.core.tiers.SubscriptionTier
    """
    NEST = "nest"
    FLIGHT = "flight"
    SOAR = "soar"
    STRATOSPHERE = "stratosphere"


# Cache TTL configuration - matches rate limit cooldowns for consistency
TIER_CACHE_TTL: Dict[SubscriptionTier, int] = {
    SubscriptionTier.NEST: 240,           # 4 hours (matches cooldown)
    SubscriptionTier.FLIGHT: 120,         # 2 hours (matches cooldown)
    SubscriptionTier.SOAR: 30,            # 30 minutes (matches cooldown)
    SubscriptionTier.STRATOSPHERE: 5,     # 5 minutes (matches cooldown)
}


class CacheEntry:
    """A cached product discovery result."""

    def __init__(
        self,
        products: List[Dict],
        niche: str,
        tier: SubscriptionTier,
        ttl_minutes: int,
        metadata: Optional[Dict] = None
    ):
        self.products = products
        self.niche = niche
        self.tier = tier
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(minutes=ttl_minutes)
        self.metadata = metadata or {}
        self.hit_count = 0

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def age_seconds(self) -> int:
        """Get age of cache entry in seconds."""
        return int((datetime.utcnow() - self.created_at).total_seconds())

    @property
    def ttl_remaining_seconds(self) -> int:
        """Get remaining TTL in seconds."""
        if self.is_expired:
            return 0
        return int((self.expires_at - datetime.utcnow()).total_seconds())

    def touch(self):
        """Record a cache hit."""
        self.hit_count += 1

    def to_dict(self) -> dict:
        """Serialize for API response."""
        return {
            "products": self.products,
            "niche": self.niche,
            "tier": self.tier.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "age_seconds": self.age_seconds,
            "ttl_remaining_seconds": self.ttl_remaining_seconds,
            "is_cached": True,
            "hit_count": self.hit_count,
            "metadata": self.metadata
        }


class ProductDiscoveryCache:
    """
    Tier-aware product discovery cache.

    Provides instant loading for users based on their subscription tier.
    Higher tiers get fresher data, lower tiers get longer cache (matching cooldowns).
    """

    def __init__(self):
        # In-memory cache: {cache_key: CacheEntry}
        # In production, replace with Redis for persistence across restarts
        self._cache: Dict[str, CacheEntry] = {}

        # Stats
        self._hits = 0
        self._misses = 0

    def _make_cache_key(self, niche: str, tier: SubscriptionTier) -> str:
        """
        Generate cache key from niche + tier.

        Different tiers have different cache entries because they have
        different refresh rates and may have different data freshness.
        """
        return f"{niche}:{tier.value}"

    def get(
        self,
        niche: str,
        tier: SubscriptionTier,
        allow_expired: bool = False
    ) -> Optional[CacheEntry]:
        """
        Get cached products for niche + tier.

        Args:
            niche: Product niche (e.g., "smart_home")
            tier: User's subscription tier
            allow_expired: If True, return expired entries (for background refresh)

        Returns:
            CacheEntry if found and valid, None otherwise
        """
        key = self._make_cache_key(niche, tier)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            logger.debug(f"[CACHE MISS] {key}")
            return None

        if entry.is_expired and not allow_expired:
            self._misses += 1
            logger.debug(f"[CACHE EXPIRED] {key} (age: {entry.age_seconds}s)")
            return None

        # Cache hit!
        entry.touch()
        self._hits += 1
        logger.info(f"[CACHE HIT] {key} (age: {entry.age_seconds}s, ttl: {entry.ttl_remaining_seconds}s)")

        return entry

    def set(
        self,
        niche: str,
        tier: SubscriptionTier,
        products: List[Dict],
        metadata: Optional[Dict] = None
    ) -> CacheEntry:
        """
        Cache products for niche + tier.

        TTL is automatically determined by tier configuration.

        Args:
            niche: Product niche
            tier: User's subscription tier
            products: List of discovered products
            metadata: Optional metadata (source info, timing, etc.)

        Returns:
            The created CacheEntry
        """
        key = self._make_cache_key(niche, tier)
        ttl_minutes = TIER_CACHE_TTL.get(tier, 60)  # Default 1 hour

        entry = CacheEntry(
            products=products,
            niche=niche,
            tier=tier,
            ttl_minutes=ttl_minutes,
            metadata=metadata
        )

        self._cache[key] = entry
        logger.info(f"[CACHE SET] {key} ({len(products)} products, TTL: {ttl_minutes}m)")

        return entry

    def invalidate(self, niche: str, tier: Optional[SubscriptionTier] = None):
        """
        Invalidate cache entries.

        Args:
            niche: Product niche to invalidate
            tier: If provided, only invalidate for this tier. Otherwise, all tiers.
        """
        if tier:
            key = self._make_cache_key(niche, tier)
            if key in self._cache:
                del self._cache[key]
                logger.info(f"[CACHE INVALIDATE] {key}")
        else:
            # Invalidate all tiers for this niche
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{niche}:")]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"[CACHE INVALIDATE] {niche}:* ({len(keys_to_remove)} entries)")

    def invalidate_all(self):
        """Clear entire cache."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"[CACHE CLEAR] Removed {count} entries")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        entries_by_tier = {}
        for key, entry in self._cache.items():
            tier = entry.tier.value
            if tier not in entries_by_tier:
                entries_by_tier[tier] = {"count": 0, "products": 0, "expired": 0}
            entries_by_tier[tier]["count"] += 1
            entries_by_tier[tier]["products"] += len(entry.products)
            if entry.is_expired:
                entries_by_tier[tier]["expired"] += 1

        return {
            "total_entries": len(self._cache),
            "total_hits": self._hits,
            "total_misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2),
            "entries_by_tier": entries_by_tier,
            "ttl_config": {tier.value: ttl for tier, ttl in TIER_CACHE_TTL.items()}
        }

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"[CACHE CLEANUP] Removed {len(expired_keys)} expired entries")

        return len(expired_keys)

    def warm_cache(
        self,
        niches: List[str],
        tier: SubscriptionTier,
        discovery_func
    ):
        """
        Pre-warm cache for specified niches.

        This can be called during startup or on a schedule to ensure
        popular niches are always cached.

        Args:
            niches: List of niches to pre-fetch
            tier: Tier to cache for (typically NEST for broadest coverage)
            discovery_func: Async function that takes (niche, count) and returns products
        """
        import asyncio

        async def _warm():
            for niche in niches:
                try:
                    existing = self.get(niche, tier)
                    if existing:
                        logger.debug(f"[WARM] {niche} already cached")
                        continue

                    products = await discovery_func(niche=niche, count=20)
                    if products:
                        self.set(niche, tier, products, {"source": "cache_warmup"})
                        logger.info(f"[WARM] Pre-cached {len(products)} products for {niche}")
                except Exception as e:
                    logger.warning(f"[WARM] Failed to warm {niche}: {e}")

        asyncio.create_task(_warm())


# Singleton instance
_product_cache: Optional[ProductDiscoveryCache] = None


def get_product_cache() -> ProductDiscoveryCache:
    """Get or create the singleton product cache."""
    global _product_cache
    if _product_cache is None:
        _product_cache = ProductDiscoveryCache()
    return _product_cache


# =============================================================================
# HELPER: Get cached or fresh products
# =============================================================================

async def get_products_with_cache(
    niche: str,
    tier: SubscriptionTier,
    discovery_func,
    count: int = 20,
    force_refresh: bool = False
) -> dict:
    """
    Get products with tier-based caching.

    This is the main entry point for product loading with caching.

    Args:
        niche: Product niche to fetch
        tier: User's subscription tier (determines cache TTL)
        discovery_func: Async function to call for fresh discovery
        count: Number of products to fetch (will fetch more for pagination)
        force_refresh: If True, bypass cache (Stratosphere on-demand)

    Returns:
        Dict with products, cache info, and metadata
    """
    cache = get_product_cache()

    # Check cache first (unless force refresh)
    if not force_refresh:
        cached = cache.get(niche, tier)
        if cached:
            return {
                "products": cached.products,  # Return ALL for pagination
                "total": len(cached.products),
                "from_cache": True,
                "cache_age_seconds": cached.age_seconds,
                "cache_ttl_remaining": cached.ttl_remaining_seconds,
                "tier": tier.value,
                "niche": niche
            }

    # Cache miss or force refresh - fetch fresh products
    # Fetch more than requested for pagination (at least 50 or 3x requested)
    fetch_count = max(50, count * 3)

    try:
        products = await discovery_func(niche=niche, count=fetch_count)

        if products:
            # Cache the results
            entry = cache.set(
                niche=niche,
                tier=tier,
                products=products,
                metadata={
                    "requested_count": count,
                    "fetched_count": len(products),
                    "source": "fresh_discovery",
                    "forced": force_refresh
                }
            )

            return {
                "products": products,  # Return ALL for pagination
                "total": len(products),
                "from_cache": False,
                "cache_age_seconds": 0,
                "cache_ttl_remaining": entry.ttl_remaining_seconds,
                "tier": tier.value,
                "niche": niche
            }

    except Exception as e:
        logger.error(f"Discovery failed for {niche}: {e}")

        # On failure, try to return stale cache if available
        stale = cache.get(niche, tier, allow_expired=True)
        if stale:
            logger.info(f"[FALLBACK] Returning stale cache for {niche}")
            return {
                "products": stale.products,  # Return ALL for pagination
                "total": len(stale.products),
                "from_cache": True,
                "cache_age_seconds": stale.age_seconds,
                "cache_ttl_remaining": 0,
                "stale": True,
                "tier": tier.value,
                "niche": niche,
                "error": str(e)
            }

    # Total failure - return empty
    return {
        "products": [],
        "total": 0,
        "from_cache": False,
        "tier": tier.value,
        "niche": niche,
        "error": "Discovery failed and no cache available"
    }


logger.info("[SUCCESS] Product cache module loaded")
