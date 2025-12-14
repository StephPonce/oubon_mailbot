"""Ospra OS Integrations - External service connectors."""

from .shopify.client import ShopifyClient
from .meta.client import MetaAdsClient
from .amazon_client import AmazonSPAPIClient, AmazonCredentials

__all__ = [
    "ShopifyClient",
    "MetaAdsClient",
    "AmazonSPAPIClient",
    "AmazonCredentials",
]
