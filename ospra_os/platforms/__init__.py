"""
Platform Adapters Package

This package provides adapters for integrating with various e-commerce platforms.
All adapters implement the PlatformAdapter abstract base class.

Available Platforms:
    - Shopify [SUCCESS] (Admin API 2024-01+)
    - Amazon [SUCCESS] (SP-API 2021-06-30, MVP: Orders & Sync)
    - WooCommerce [SUCCESS] (REST API wc/v3)

Author: OspraOS
Date: November 2025
"""

from ospra_os.platforms.base import (
    PlatformAdapter,
    PlatformAPIError,
    RateLimitError,
    AuthenticationError,
    ProductNotFoundError,
    InvalidRequestError,
    get_available_platforms,
    validate_platform_name
)

from ospra_os.platforms.shopify import ShopifyAdapter
from ospra_os.platforms.amazon import AmazonAdapter
from ospra_os.platforms.woocommerce import WooCommerceAdapter
from ospra_os.platforms.factory import PlatformFactory

__all__ = [
    # Base
    "PlatformAdapter",
    "PlatformAPIError",
    "RateLimitError",
    "AuthenticationError",
    "ProductNotFoundError",
    "InvalidRequestError",
    "get_available_platforms",
    "validate_platform_name",
    # Adapters
    "ShopifyAdapter",
    "AmazonAdapter",
    "WooCommerceAdapter",
    # Factory
    "PlatformFactory"
]
