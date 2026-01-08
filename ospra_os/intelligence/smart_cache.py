"""
SMART SENTIMENT CACHE
=====================

Caches social sentiment data intelligently:
- Default: Cache for 6 hours
- Velocity spike (>20%): Immediate re-fetch
- Sales change (>15%): Immediate re-fetch
- Manual refresh: Only if 30+ min since last fetch

This saves API calls while ensuring data stays fresh when it matters.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import json
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class CachedSentiment:
    """Cached sentiment data with metadata."""
    product_id: str
    data: Dict[str, Any]
    fetched_at: datetime
    velocity_at_fetch: float = 0.0
    sales_at_fetch: int = 0
    fetch_count: int = 1
    
    def age_hours(self) -> float:
        """Get age of cache in hours."""
        return (datetime.utcnow() - self.fetched_at).total_seconds() / 3600
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "product_id": self.product_id,
            "data": self.data,
            "fetched_at": self.fetched_at.isoformat(),
            "age_hours": round(self.age_hours(), 2),
            "velocity_at_fetch": self.velocity_at_fetch,
            "sales_at_fetch": self.sales_at_fetch,
            "fetch_count": self.fetch_count,
        }


class SmartSentimentCache:
    """
    Intelligent caching for social sentiment data.
    
    Refresh triggers:
    1. Time-based: After 6 hours (default TTL)
    2. Velocity change: If velocity changed by >20% since last fetch
    3. Sales change: If sales changed by >15% since last fetch
    4. Manual: Only allowed if 30+ minutes since last fetch
    """
    
    # Configuration
    DEFAULT_TTL_HOURS = 6
    VELOCITY_CHANGE_THRESHOLD = 0.20  # 20%
    SALES_CHANGE_THRESHOLD = 0.15  # 15%
    MIN_MANUAL_REFRESH_MINUTES = 30
    
    def __init__(self):
        self._cache: Dict[str, CachedSentiment] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "velocity_refreshes": 0,
            "sales_refreshes": 0,
            "time_refreshes": 0,
            "manual_refreshes": 0,
            "manual_blocked": 0,
        }
    
    def _cache_key(self, product_id: str, source: str = "all") -> str:
        """Generate cache key."""
        return f"{product_id}:{source}"
    
    def get(
        self,
        product_id: str,
        source: str = "all",
        current_velocity: Optional[float] = None,
        current_sales: Optional[int] = None,
    ) -> Tuple[Optional[Dict], str]:
        """
        Get cached sentiment if valid.
        
        Args:
            product_id: Product to get sentiment for
            source: Sentiment source (tiktok, twitter, etc.)
            current_velocity: Current velocity for comparison
            current_sales: Current sales count for comparison
            
        Returns:
            (cached_data, status) where status is:
            - "hit": Valid cache, use it
            - "expired": Cache too old
            - "velocity_changed": Velocity changed significantly
            - "sales_changed": Sales changed significantly
            - "miss": No cache exists
        """
        key = self._cache_key(product_id, source)
        cached = self._cache.get(key)
        
        if not cached:
            self._stats["misses"] += 1
            return None, "miss"
        
        # Check time-based expiry
        if cached.age_hours() > self.DEFAULT_TTL_HOURS:
            self._stats["time_refreshes"] += 1
            logger.info(f"[ALARM] Cache expired for {product_id} ({cached.age_hours():.1f}h old)")
            return None, "expired"
        
        # Check velocity change
        if current_velocity is not None and cached.velocity_at_fetch > 0:
            velocity_change = abs(current_velocity - cached.velocity_at_fetch) / cached.velocity_at_fetch
            if velocity_change > self.VELOCITY_CHANGE_THRESHOLD:
                self._stats["velocity_refreshes"] += 1
                logger.info(f"[TREND] Velocity spike for {product_id}: {cached.velocity_at_fetch:.1f}% → {current_velocity:.1f}%")
                return None, "velocity_changed"
        
        # Check sales change
        if current_sales is not None and cached.sales_at_fetch > 0:
            sales_change = abs(current_sales - cached.sales_at_fetch) / cached.sales_at_fetch
            if sales_change > self.SALES_CHANGE_THRESHOLD:
                self._stats["sales_refreshes"] += 1
                logger.info(f"[PRICE] Sales change for {product_id}: {cached.sales_at_fetch} → {current_sales}")
                return None, "sales_changed"
        
        # Cache hit!
        self._stats["hits"] += 1
        logger.debug(f"[SUCCESS] Cache hit for {product_id} ({cached.age_hours():.1f}h old)")
        return cached.data, "hit"
    
    def can_manual_refresh(self, product_id: str, source: str = "all") -> Tuple[bool, Optional[int]]:
        """
        Check if manual refresh is allowed.
        
        Returns:
            (allowed, minutes_to_wait)
        """
        key = self._cache_key(product_id, source)
        cached = self._cache.get(key)
        
        if not cached:
            return True, None
        
        minutes_since_fetch = (datetime.utcnow() - cached.fetched_at).total_seconds() / 60
        
        if minutes_since_fetch >= self.MIN_MANUAL_REFRESH_MINUTES:
            return True, None
        
        wait_minutes = int(self.MIN_MANUAL_REFRESH_MINUTES - minutes_since_fetch) + 1
        self._stats["manual_blocked"] += 1
        return False, wait_minutes
    
    def set(
        self,
        product_id: str,
        data: Dict[str, Any],
        source: str = "all",
        velocity: float = 0.0,
        sales: int = 0,
    ):
        """
        Cache sentiment data.
        
        Args:
            product_id: Product ID
            data: Sentiment data to cache
            source: Sentiment source
            velocity: Current velocity (for future comparison)
            sales: Current sales count (for future comparison)
        """
        key = self._cache_key(product_id, source)
        
        # Check if updating existing cache
        existing = self._cache.get(key)
        fetch_count = (existing.fetch_count + 1) if existing else 1
        
        self._cache[key] = CachedSentiment(
            product_id=product_id,
            data=data,
            fetched_at=datetime.utcnow(),
            velocity_at_fetch=velocity,
            sales_at_fetch=sales,
            fetch_count=fetch_count,
        )
        
        logger.info(f" Cached sentiment for {product_id} (fetch #{fetch_count})")
    
    def invalidate(self, product_id: str, source: str = "all"):
        """Invalidate cache for a product."""
        key = self._cache_key(product_id, source)
        if key in self._cache:
            del self._cache[key]
            logger.info(f" Invalidated cache for {product_id}")
    
    def invalidate_all(self):
        """Clear entire cache."""
        count = len(self._cache)
        self._cache = {}
        logger.info(f" Cleared {count} cached entries")
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"] + \
                        self._stats["velocity_refreshes"] + self._stats["sales_refreshes"] + \
                        self._stats["time_refreshes"]
        
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            **self._stats,
            "total_requests": total_requests,
            "hit_rate": round(hit_rate * 100, 1),
            "cached_products": len(self._cache),
            "savings_estimate": f"~{self._stats['hits'] * 0.01:.2f} API calls saved",
        }
    
    def get_cached_products(self) -> list:
        """Get list of all cached products with metadata."""
        return [cached.to_dict() for cached in self._cache.values()]


# Singleton instance
_sentiment_cache: Optional[SmartSentimentCache] = None


def get_sentiment_cache() -> SmartSentimentCache:
    """Get or create the sentiment cache instance."""
    global _sentiment_cache
    if _sentiment_cache is None:
        _sentiment_cache = SmartSentimentCache()
    return _sentiment_cache


async def get_cached_sentiment(
    product_id: str,
    source: str = "all",
    current_velocity: Optional[float] = None,
    current_sales: Optional[int] = None,
    force_refresh: bool = False,
) -> Tuple[Optional[Dict], bool, str]:
    """
    Get sentiment from cache or indicate refresh needed.
    
    Args:
        product_id: Product ID
        source: Sentiment source
        current_velocity: Current velocity for smart invalidation
        current_sales: Current sales for smart invalidation
        force_refresh: Manual refresh request
        
    Returns:
        (data, needs_refresh, reason)
    """
    cache = get_sentiment_cache()
    
    # Manual refresh check
    if force_refresh:
        allowed, wait_minutes = cache.can_manual_refresh(product_id, source)
        if not allowed:
            # Return cached data with message
            data, _ = cache.get(product_id, source)
            return data, False, f"Please wait {wait_minutes} minutes before refreshing"
        return None, True, "manual_refresh"
    
    # Normal cache check with smart invalidation
    data, status = cache.get(
        product_id,
        source,
        current_velocity=current_velocity,
        current_sales=current_sales,
    )
    
    if status == "hit":
        return data, False, "cached"
    
    return None, True, status


def cache_sentiment(
    product_id: str,
    data: Dict[str, Any],
    source: str = "all",
    velocity: float = 0.0,
    sales: int = 0,
):
    """Cache sentiment data."""
    cache = get_sentiment_cache()
    cache.set(product_id, data, source, velocity, sales)
