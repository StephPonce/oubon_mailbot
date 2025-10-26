"""Base connector class for all API integrations."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProductCandidate:
    """Product candidate found by a connector."""

    name: str
    source: str  # "aliexpress", "google_trends", "tiktok", etc.

    # Pricing
    price: Optional[float] = None
    currency: str = "USD"

    # URLs
    url: Optional[str] = None
    image_url: Optional[str] = None

    # Trend data
    trend_score: Optional[float] = None  # 0-100
    search_volume: Optional[int] = None

    # Social signals
    social_mentions: Optional[int] = None
    social_engagement: Optional[int] = None

    # Supplier info
    supplier_name: Optional[str] = None
    supplier_rating: Optional[float] = None
    min_order_quantity: Optional[int] = None
    shipping_time: Optional[str] = None

    # Competition
    competition_level: Optional[str] = None  # "low", "medium", "high"

    # Metadata
    category: Optional[str] = None
    tags: List[str] = None
    discovered_at: datetime = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.discovered_at is None:
            self.discovered_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "name": self.name,
            "source": self.source,
            "price": self.price,
            "currency": self.currency,
            "url": self.url,
            "image_url": self.image_url,
            "trend_score": self.trend_score,
            "search_volume": self.search_volume,
            "social_mentions": self.social_mentions,
            "social_engagement": self.social_engagement,
            "supplier_name": self.supplier_name,
            "supplier_rating": self.supplier_rating,
            "min_order_quantity": self.min_order_quantity,
            "shipping_time": self.shipping_time,
            "competition_level": self.competition_level,
            "category": self.category,
            "tags": self.tags,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
        }


class BaseConnector(ABC):
    """Base class for all product research connectors."""

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.enabled = api_key is not None if api_key else True
        self.config = kwargs

    @property
    @abstractmethod
    def name(self) -> str:
        """Connector name (e.g., 'Google Trends', 'AliExpress')."""
        pass

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Short identifier (e.g., 'google_trends', 'aliexpress')."""
        pass

    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[ProductCandidate]:
        """
        Search for products/trends.

        Args:
            query: Search term or category
            **kwargs: Connector-specific parameters

        Returns:
            List of product candidates
        """
        pass

    @abstractmethod
    async def get_trending(self, category: Optional[str] = None, limit: int = 10) -> List[ProductCandidate]:
        """
        Get trending products/searches.

        Args:
            category: Optional category filter
            limit: Max results to return

        Returns:
            List of trending product candidates
        """
        pass

    def is_available(self) -> bool:
        """Check if connector is available/configured."""
        return self.enabled

    async def validate(self) -> bool:
        """
        Validate API credentials.

        Returns:
            True if credentials are valid
        """
        if not self.is_available():
            return False
        try:
            # Try a simple API call
            await self.get_trending(limit=1)
            return True
        except Exception:
            return False
