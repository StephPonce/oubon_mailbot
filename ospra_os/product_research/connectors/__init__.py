"""API Connectors for product research platforms."""

from .base import BaseConnector, ProductCandidate
from .tiktok_shop import TikTokShopConnector

__all__ = ["BaseConnector", "ProductCandidate", "TikTokShopConnector"]
