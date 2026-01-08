"""
SMART SENTIMENT CACHE
=====================

Caches social sentiment data intelligently:
- Normal: Cache for 6 hours
- Velocity spike (>20%): Immediate refresh
- Sales change (>15%): Immediate refresh
- Manual refresh: Only if 30+ min since last

Reduces API costs while keeping data fresh when it matters.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class CacheRefreshReason(str, Enum):
    """Reasons for cache refresh."""
    EXPIRED = "expired"
    VELOCITY_SPIKE = "velocity_spike"
    SALES_CHANGE = "sales_change"
    MANUAL = "manual"
    FORCED = "forced"
    FIRST_FETCH = "first_fetch"


@dataclass
class CachedSentiment:
    """Cached sentiment data for a product."""
    product_id: str
    sentiment_score: float  # -1 to 1
    positive_count: int
    negative_count: int
    neutral_count: int
    total_mentions: int
    trending_topics: List[str]
    sources: Dict[str, int]  # {"tiktok": 500, "twitter": 200}
    
    # Cache metadata
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=6))
    fetch_count: int = 1
    last_velocity: float = 0.0
    last_sales_velocity: float = 0.0
    
    def is_expired(self) -> bool:
        """Check if cache has expired."""
        return datetime.utcnow() > self.expires_at
    
    def age_seconds(self) -> int:
        """Get age of cache in seconds."""
        return int((datetime.utcnow() - self.fetched_at).total_seconds())
    
    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "sentiment_score": self.sentiment_score,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "neutral_count": self.neutral_count,
            "total_mentions": self.total_mentions,
            "trending_topics": self.trending_topics,
            "sources": self.sources,
            "fetched_at": self.fetched_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "age_seconds": self.age_seconds(),
            "fetch_count": self.fetch_count,
            "is_stale": self.is_expired()
        }


class SmartSentimentCache:
    """
    Intelligent caching for social sentiment data.
    
    Features:
    - 6-hour default TTL
    - Velocity-triggered refresh
    - Sales-triggered refresh
    - Cooldown on manual refresh
    - Stats tracking
    """
    
    DEFAULT_TTL_HOURS = 6
    VELOCITY_THRESHOLD = 20.0  # % change triggers refresh
    SALES_THRESHOLD = 15.0  # % change triggers refresh
    MANUAL_COOLDOWN_MINUTES = 30
    
    def __init__(self):
        self._cache: Dict[str, CachedSentiment] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "velocity_refreshes": 0,
            "sales_refreshes": 0,
            "manual_refreshes": 0,
            "expired_refreshes": 0
        }
    
    def _generate_key(self, product_id: str, sources: Optional[List[str]] = None) -> str:
        """Generate cache key."""
        key_parts = [product_id]
        if sources:
            key_parts.extend(sorted(sources))
        return hashlib.md5(":".join(key_parts).encode()).hexdigest()
    
    def get(
        self,
        product_id: str,
        sources: Optional[List[str]] = None
    ) -> Optional[CachedSentiment]:
        """
        Get cached sentiment if valid.
        
        Returns None if:
        - Not in cache
        - Cache expired
        """
        key = self._generate_key(product_id, sources)
        cached = self._cache.get(key)
        
        if cached is None:
            self._stats["misses"] += 1
            return None
        
        if cached.is_expired():
            self._stats["misses"] += 1
            return None
        
        self._stats["hits"] += 1
        return cached
    
    def set(
        self,
        product_id: str,
        sentiment_data: Dict[str, Any],
        sources: Optional[List[str]] = None,
        ttl_hours: Optional[float] = None
    ) -> CachedSentiment:
        """
        Cache sentiment data.
        
        Args:
            product_id: Product identifier
            sentiment_data: Raw sentiment data dict
            sources: List of sources queried
            ttl_hours: Custom TTL (default: 6 hours)
        """
        key = self._generate_key(product_id, sources)
        ttl = ttl_hours or self.DEFAULT_TTL_HOURS
        
        # Check if updating existing
        existing = self._cache.get(key)
        fetch_count = (existing.fetch_count + 1) if existing else 1
        
        cached = CachedSentiment(
            product_id=product_id,
            sentiment_score=sentiment_data.get("score", 0.0),
            positive_count=sentiment_data.get("positive", 0),
            negative_count=sentiment_data.get("negative", 0),
            neutral_count=sentiment_data.get("neutral", 0),
            total_mentions=sentiment_data.get("total_mentions", 0),
            trending_topics=sentiment_data.get("trending_topics", []),
            sources=sentiment_data.get("sources", {}),
            fetched_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=ttl),
            fetch_count=fetch_count,
            last_velocity=sentiment_data.get("velocity", 0.0),
            last_sales_velocity=sentiment_data.get("sales_velocity", 0.0)
        )
        
        self._cache[key] = cached
        logger.info(f"[PACKAGE] Cached sentiment for {product_id} (TTL: {ttl}h, fetch #{fetch_count})")
        
        return cached
    
    def should_refresh(
        self,
        product_id: str,
        current_velocity: Optional[float] = None,
        current_sales_velocity: Optional[float] = None,
        manual: bool = False,
        sources: Optional[List[str]] = None
    ) -> tuple[bool, CacheRefreshReason]:
        """
        Determine if cache should be refreshed.
        
        Args:
            product_id: Product identifier
            current_velocity: Current trend velocity (% change)
            current_sales_velocity: Current sales velocity (% change)
            manual: Whether this is a manual refresh request
            sources: Sources to check
        
        Returns:
            (should_refresh, reason)
        """
        key = self._generate_key(product_id, sources)
        cached = self._cache.get(key)
        
        # No cache = first fetch
        if cached is None:
            return True, CacheRefreshReason.FIRST_FETCH
        
        # Expired = refresh
        if cached.is_expired():
            self._stats["expired_refreshes"] += 1
            return True, CacheRefreshReason.EXPIRED
        
        # Velocity spike check
        if current_velocity is not None:
            velocity_change = abs(current_velocity - cached.last_velocity)
            if velocity_change > self.VELOCITY_THRESHOLD:
                self._stats["velocity_refreshes"] += 1
                logger.info(f"[START] Velocity spike for {product_id}: {cached.last_velocity:.1f}% → {current_velocity:.1f}%")
                return True, CacheRefreshReason.VELOCITY_SPIKE
        
        # Sales velocity check
        if current_sales_velocity is not None:
            sales_change = abs(current_sales_velocity - cached.last_sales_velocity)
            if sales_change > self.SALES_THRESHOLD:
                self._stats["sales_refreshes"] += 1
                logger.info(f"[PRICE] Sales change for {product_id}: {cached.last_sales_velocity:.1f}% → {current_sales_velocity:.1f}%")
                return True, CacheRefreshReason.SALES_CHANGE
        
        # Manual refresh with cooldown
        if manual:
            age_minutes = cached.age_seconds() / 60
            if age_minutes >= self.MANUAL_COOLDOWN_MINUTES:
                self._stats["manual_refreshes"] += 1
                return True, CacheRefreshReason.MANUAL
            else:
                remaining = self.MANUAL_COOLDOWN_MINUTES - age_minutes
                logger.info(f"⏳ Manual refresh cooldown: {remaining:.0f}m remaining for {product_id}")
                return False, CacheRefreshReason.MANUAL
        
        # No refresh needed
        return False, CacheRefreshReason.EXPIRED
    
    def invalidate(self, product_id: str, sources: Optional[List[str]] = None):
        """Invalidate cache for a product."""
        key = self._generate_key(product_id, sources)
        if key in self._cache:
            del self._cache[key]
            logger.info(f" Invalidated cache for {product_id}")
    
    def invalidate_all(self):
        """Clear entire cache."""
        count = len(self._cache)
        self._cache = {}
        logger.info(f" Cleared {count} cached sentiments")
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self._stats,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 1),
            "cached_products": len(self._cache),
            "cache_size_estimate_kb": self._estimate_size_kb()
        }
    
    def _estimate_size_kb(self) -> float:
        """Estimate cache size in KB."""
        try:
            size_bytes = len(json.dumps([c.to_dict() for c in self._cache.values()]))
            return round(size_bytes / 1024, 2)
        except:
            return 0.0
    
    def get_all_cached(self) -> List[dict]:
        """Get all cached items (for debugging)."""
        return [
            {
                "key": key,
                **cached.to_dict()
            }
            for key, cached in self._cache.items()
        ]


# Singleton instance
_sentiment_cache: Optional[SmartSentimentCache] = None


def get_sentiment_cache() -> SmartSentimentCache:
    """Get or create singleton cache."""
    global _sentiment_cache
    if _sentiment_cache is None:
        _sentiment_cache = SmartSentimentCache()
    return _sentiment_cache


# === Integration Helper ===

async def get_cached_or_fetch_sentiment(
    product_id: str,
    fetch_func,
    current_velocity: Optional[float] = None,
    current_sales_velocity: Optional[float] = None,
    manual: bool = False,
    sources: Optional[List[str]] = None
) -> tuple[dict, bool]:
    """
    Get sentiment from cache or fetch if needed.
    
    Args:
        product_id: Product identifier
        fetch_func: Async function to fetch fresh data
        current_velocity: Current trend velocity
        current_sales_velocity: Current sales velocity
        manual: Whether this is a manual refresh
        sources: Sources to query
    
    Returns:
        (sentiment_data, was_cached)
    """
    cache = get_sentiment_cache()
    
    # Check if refresh needed
    should_refresh, reason = cache.should_refresh(
        product_id,
        current_velocity=current_velocity,
        current_sales_velocity=current_sales_velocity,
        manual=manual,
        sources=sources
    )
    
    if not should_refresh:
        # Return cached data
        cached = cache.get(product_id, sources)
        if cached:
            return cached.to_dict(), True
    
    # Fetch fresh data
    logger.info(f"[REFRESH] Fetching fresh sentiment for {product_id} (reason: {reason.value})")
    
    try:
        fresh_data = await fetch_func(product_id, sources)
        
        # Add velocity info if provided
        if current_velocity is not None:
            fresh_data["velocity"] = current_velocity
        if current_sales_velocity is not None:
            fresh_data["sales_velocity"] = current_sales_velocity
        
        # Cache it
        cached = cache.set(product_id, fresh_data, sources)
        
        return cached.to_dict(), False
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to fetch sentiment for {product_id}: {e}")
        
        # Try to return stale cache if available
        key = cache._generate_key(product_id, sources)
        stale = cache._cache.get(key)
        if stale:
            logger.warning(f"[WARNING] Returning stale cache for {product_id}")
            return stale.to_dict(), True
        
        raise
