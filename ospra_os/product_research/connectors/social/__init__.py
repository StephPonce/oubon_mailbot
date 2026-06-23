"""
Social media platform connectors.

#57: twitter.py (empty stub) deleted and meta.py sunset (organic Graph API is
dead; Meta signal now comes from the Ad Library actor in the main pipeline).

ACTIVE CONNECTORS:
- RedditConnector: SECONDARY / off by default (DISCOVERY_DISABLE_REDDIT)
- XAITwitterDiscovery: SECONDARY / off by default (DISCOVERY_DISABLE_X) — weak
  corroboration only; Grok sentiment is paraphrase-prone.
"""

from .reddit import RedditConnector

# xAI-powered Twitter discovery — opt-in, off by default (see DISCOVERY_DISABLE_X).
try:
    from .xai_twitter import XAITwitterDiscovery, TwitterProduct, discover_twitter_products
    HAS_XAI_TWITTER = True
except ImportError:
    XAITwitterDiscovery = None
    TwitterProduct = None
    discover_twitter_products = None
    HAS_XAI_TWITTER = False

__all__ = [
    "RedditConnector",
    "XAITwitterDiscovery",
    "TwitterProduct",
    "discover_twitter_products",
    "HAS_XAI_TWITTER",
]
