"""
Social media platform connectors.

RECOMMENDED (2025-12-07):
- Use XAITwitterDiscovery for sentiment analysis (real-time Twitter/X data via Grok)
- Replaces Reddit sentiment (deprecated)

AVAILABLE CONNECTORS:
- XAITwitterDiscovery: PRIMARY sentiment source (via xAI Grok)
- TwitterConnector: Basic Twitter API v2 wrapper (requires separate API key)
- RedditConnector: DEPRECATED - use XAITwitterDiscovery instead
- MetaConnector: Facebook/Instagram (requires separate setup)
"""

from .meta import MetaConnector
from .twitter import TwitterConnector
from .reddit import RedditConnector

# xAI-powered Twitter discovery (REAL Twitter data access)
# This is the PRIMARY sentiment analysis source
try:
    from .xai_twitter import XAITwitterDiscovery, TwitterProduct, discover_twitter_products
    HAS_XAI_TWITTER = True
except ImportError:
    XAITwitterDiscovery = None
    TwitterProduct = None
    discover_twitter_products = None
    HAS_XAI_TWITTER = False

__all__ = [
    "MetaConnector",
    "TwitterConnector",
    "RedditConnector",  # DEPRECATED - use XAITwitterDiscovery
    "XAITwitterDiscovery",  # PRIMARY sentiment source
    "TwitterProduct",
    "discover_twitter_products",
    "HAS_XAI_TWITTER"
]
