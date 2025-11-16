"""Advertising automation for Meta, TikTok, Google, and other platforms."""

from .meta.meta_ads import MetaAdsManager
from .tiktok.tiktok_ads import TikTokAdsManager

# Google Ads will be available once google-ads SDK is installed
try:
    from .google.google_ads import GoogleAdsManager
    __all__ = ['MetaAdsManager', 'TikTokAdsManager', 'GoogleAdsManager']
except ImportError:
    __all__ = ['MetaAdsManager', 'TikTokAdsManager']
    print("⚠️  Google Ads not available. Install: uv add google-ads==23.1.0")
