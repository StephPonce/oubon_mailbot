"""
Cached AliExpress Products Database Model

Stores product metadata (cached 24hrs) separate from pricing (fetched live).
Implements hybrid caching strategy for optimal performance and accuracy.
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
import json

Base = declarative_base()


class CachedAliExpressProduct(Base):
    """
    Store AliExpress product metadata with hybrid caching.

    Cached (24 hours):
    - Product metadata: title, images, category, ratings, orders
    - Affiliate URLs and commission rates

    Live-fetched (on-demand):
    - Current pricing, discounts, stock status
    """
    __tablename__ = "cached_aliexpress_products"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(100), unique=True, nullable=False, index=True)

    # CACHED METADATA (Static, 24hr TTL)
    title = Column(Text, nullable=False)
    image_url = Column(Text)
    category = Column(String(255))
    second_level_category = Column(String(255))

    # CACHED SOCIAL PROOF (Updates slowly)
    orders = Column(Integer, default=0)
    rating = Column(Float, default=0.0)  # 0-5 scale
    evaluate_rate = Column(String(20))   # Original percentage from API

    # CACHED AFFILIATE DATA (Static)
    affiliate_url = Column(Text)
    commission_rate = Column(String(20))
    sale_price = Column(String(50))  # Original from API (may be percentage string)

    # LAST KNOWN PRICING (Cached, used as fallback)
    last_known_price = Column(Float)
    last_known_original_price = Column(Float)
    last_known_discount = Column(String(20))

    # SEARCH METADATA (For cache invalidation)
    search_keywords = Column(Text)  # Comma-separated
    search_category_ids = Column(String(255))

    # TIER CLASSIFICATION (Computed from last_known_price)
    price_tier = Column(String(20))  # "starter", "pro", "premium"

    # CACHE MANAGEMENT
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    metadata_cached_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_price_check = Column(DateTime)  # When price was last fetched live

    # AVAILABILITY
    is_available = Column(Boolean, default=True)

    def __repr__(self):
        return f"<CachedProduct(id={self.product_id}, title={self.title[:30]}..., tier={self.price_tier})>"

    def is_metadata_fresh(self, ttl_hours: int = 24) -> bool:
        """Check if metadata cache is still fresh"""
        if not self.metadata_cached_at:
            return False
        age = datetime.now(timezone.utc) - self.metadata_cached_at
        return age < timedelta(hours=ttl_hours)

    def needs_price_refresh(self, ttl_minutes: int = 60) -> bool:
        """Check if price should be refreshed"""
        if not self.last_price_check:
            return True
        age = datetime.now(timezone.utc) - self.last_price_check
        return age > timedelta(minutes=ttl_minutes)

    def update_tier(self):
        """Classify product into price tier based on last_known_price"""
        if not self.last_known_price:
            self.price_tier = None
            return

        if self.last_known_price < 25:
            self.price_tier = "starter"
        elif self.last_known_price < 100:
            self.price_tier = "pro"
        else:
            self.price_tier = "premium"

    def to_dict(self, include_live_price: bool = False) -> Dict:
        """
        Convert to dictionary for API response.

        Args:
            include_live_price: If True, indicates live price should be fetched
        """
        return {
            "product_id": self.product_id,
            "title": self.title,
            "image_url": self.image_url,
            "category": self.category,
            "orders": self.orders,
            "rating": self.rating,
            "affiliate_url": self.affiliate_url,
            "commission_rate": self.commission_rate,

            # Pricing (cached or live)
            "price": self.last_known_price,
            "original_price": self.last_known_original_price,
            "discount": self.last_known_discount,
            "price_is_live": False,  # Frontend can request live price

            # Tier
            "tier": self.price_tier,

            # Cache metadata
            "cached_at": self.metadata_cached_at.isoformat() if self.metadata_cached_at else None,
            "cache_age_minutes": int((datetime.now(timezone.utc) - self.metadata_cached_at).total_seconds() / 60) if self.metadata_cached_at else None,
        }


# Create indexes for common queries
Index('idx_price_tier', CachedAliExpressProduct.price_tier)
Index('idx_category', CachedAliExpressProduct.category)
Index('idx_cached_at', CachedAliExpressProduct.metadata_cached_at)
Index('idx_keywords', CachedAliExpressProduct.search_keywords)


class ProductSearchCache(Base):
    """
    Cache search query results to avoid duplicate API calls.
    Maps search params → product IDs.
    """
    __tablename__ = "product_search_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Search parameters (cache key)
    keywords = Column(String(500))
    category_ids = Column(String(255))
    sort_type = Column(String(50))
    price_tier = Column(String(20))

    # Cache key hash (for quick lookup)
    cache_key = Column(String(64), unique=True, nullable=False, index=True)

    # Results
    product_ids = Column(Text)  # JSON array of product IDs
    total_results = Column(Integer)

    # Cache management
    cached_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    hits = Column(Integer, default=0)  # Track cache hit count

    def __repr__(self):
        return f"<SearchCache(keywords={self.keywords}, results={self.total_results}, age={(datetime.now(timezone.utc) - self.cached_at).seconds}s)>"

    def is_fresh(self, ttl_hours: int = 2) -> bool:
        """Check if search cache is still fresh"""
        age = datetime.now(timezone.utc) - self.cached_at
        return age < timedelta(hours=ttl_hours)

    def get_product_ids(self) -> List[str]:
        """Parse product IDs from JSON"""
        if not self.product_ids:
            return []
        return json.loads(self.product_ids)

    def set_product_ids(self, ids: List[str]):
        """Store product IDs as JSON"""
        self.product_ids = json.dumps(ids)

    @staticmethod
    def generate_cache_key(keywords: Optional[str], category_ids: Optional[str],
                          sort_type: str, price_tier: Optional[str]) -> str:
        """Generate consistent cache key from search params"""
        import hashlib
        key_parts = [
            keywords or "",
            category_ids or "",
            sort_type,
            price_tier or ""
        ]
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()


# Create index for cache key lookups
Index('idx_cache_key', ProductSearchCache.cache_key)
Index('idx_search_cached_at', ProductSearchCache.cached_at)
