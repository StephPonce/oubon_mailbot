"""
Apify-based product research connectors.

CLEANUP (2025-12-07):
- Removed AliExpressScraper (use official AliExpress Affiliate API instead)
- Removed RedditSentimentScraper (covered by X/Twitter via xAI API + TikTok API)
- Removed ShopifyCompetitorScraper (not priority, use Shopify API for our own store)

KEPT:
- TikTokShopScraper (supplements TikTok API with shop-specific data)
- AmazonBestsellersScraper (no official Amazon Product API exists)
"""

from .base_apify import ApifyConnector
from .tiktok_shop import TikTokShopScraper
from .amazon_bestsellers import AmazonBestsellersScraper

__all__ = [
    'ApifyConnector',
    'TikTokShopScraper',
    'AmazonBestsellersScraper'
]
