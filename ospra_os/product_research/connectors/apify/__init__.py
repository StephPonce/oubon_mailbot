"""
Apify Integration - Real Data from Amazon & TikTok
"""

from .base_apify import ApifyClient, ApifyProduct, ApifyConnector, get_apify_client
from .tiktok_shop import TikTokShopScraper
from .amazon_bestsellers import AmazonBestsellersScraper
from .pinterest_trends import (
    PinterestTrendsApify,
    PinterestTrends,
    PinterestTrendData,
    get_pinterest_trends,
)

__all__ = [
    "ApifyClient",
    "ApifyConnector",
    "ApifyProduct",
    "get_apify_client",
    "TikTokShopScraper",
    "AmazonBestsellersScraper",
    "PinterestTrendsApify",
    "PinterestTrends",
    "PinterestTrendData",
    "get_pinterest_trends",
]
