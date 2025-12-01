"""Social media platform connectors."""

from .meta import MetaConnector
from .twitter import TwitterConnector
from .reddit import RedditConnector

# xAI-powered Twitter discovery (REAL Twitter data access)
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
    "RedditConnector",
    "XAITwitterDiscovery",
    "TwitterProduct",
    "discover_twitter_products",
    "HAS_XAI_TWITTER"
]
