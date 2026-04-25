"""
Platform Adapter Base Class

This module provides the abstract base class for e-commerce platform integrations.
All platform adapters (Shopify, Amazon, WooCommerce, etc.) must implement this interface.

Author: OspraOS
Date: November 2025
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTION HIERARCHY
# ============================================================================

class PlatformAPIError(Exception):
    """Base exception for platform API errors"""

    def __init__(self, message: str, platform: str = "unknown", details: Optional[dict] = None):
        self.message = message
        self.platform = platform
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        return f"[{self.platform}] {self.message}"


class RateLimitError(PlatformAPIError):
    """Raised when API rate limit is exceeded"""

    def __init__(self, message: str = "Rate limit exceeded", platform: str = "unknown", retry_after: Optional[int] = None):
        super().__init__(message, platform, {"retry_after": retry_after})
        self.retry_after = retry_after


class AuthenticationError(PlatformAPIError):
    """Raised when authentication fails"""

    def __init__(self, message: str = "Authentication failed", platform: str = "unknown"):
        super().__init__(message, platform)


class ProductNotFoundError(PlatformAPIError):
    """Raised when product is not found on platform"""

    def __init__(self, product_id: str, platform: str = "unknown"):
        message = f"Product not found: {product_id}"
        super().__init__(message, platform, {"product_id": product_id})
        self.product_id = product_id


class InvalidRequestError(PlatformAPIError):
    """Raised when request validation fails"""

    def __init__(self, message: str, platform: str = "unknown", field: Optional[str] = None):
        super().__init__(message, platform, {"field": field})
        self.field = field


# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================

class PlatformAdapter(ABC):
    """
    Abstract base class for e-commerce platform adapters.

    This class defines the interface that all platform adapters must implement
    to ensure consistent integration across different e-commerce platforms.

    Attributes:
        platform_name (str): Name of the platform (e.g., "shopify", "amazon")
        api_version (str): Version of the platform API being used
        credentials (dict): Platform-specific authentication credentials
        base_url (str): Base URL for API requests

    Example:
        class ShopifyAdapter(PlatformAdapter):
            def __init__(self, credentials: dict):
                super().__init__(credentials)
                self.platform_name = "shopify"
                self.api_version = "2025-01"
                # ... implement abstract methods
    """

    def __init__(self, credentials: dict):
        """
        Initialize the platform adapter.

        Args:
            credentials: Dictionary containing platform-specific authentication credentials
                For Shopify: {"shop_url": str, "access_token": str}
                For Amazon: {"seller_id": str, "mws_auth_token": str, "access_key": str, "secret_key": str}
                For WooCommerce: {"url": str, "consumer_key": str, "consumer_secret": str}
        """
        self.credentials = credentials
        self.platform_name = "base"
        self.api_version = "unknown"
        self.base_url = ""

        # Request tracking
        self._request_count = 0
        self._last_request_time: Optional[datetime] = None

        logger.info(f"Initialized {self.platform_name} adapter")

    # ========================================================================
    # ABSTRACT METHODS - Must be implemented by all adapters
    # ========================================================================

    @abstractmethod
    async def test_connection(self) -> dict:
        """
        Test platform API credentials and connectivity.

        This method should verify that the provided credentials are valid
        and that the API is accessible.

        Returns:
            Dictionary with connection test results:
            {
                "success": bool,
                "store_name": str,
                "store_url": str,
                "platform_version": str,
                "error": str (only if failed)
            }

        Raises:
            AuthenticationError: If credentials are invalid
            PlatformAPIError: If connection test fails

        Example:
            >>> result = await adapter.test_connection()
            >>> if result["success"]:
            ...     print(f"Connected to {result['store_name']}")
        """
        pass

    @abstractmethod
    async def deploy_product(self, product: dict) -> dict:
        """
        Deploy/create a new product on the platform.

        Args:
            product: Dictionary containing product information:
                {
                    "title": str,              # Product title
                    "description": str,        # Product description (HTML)
                    "price": float,            # Selling price
                    "compare_at_price": float, # Original/compare price (optional)
                    "sku": str,                # Stock Keeping Unit
                    "inventory": int,          # Stock quantity
                    "images": list[str],       # List of image URLs
                    "tags": list[str],         # Product tags/categories
                    "vendor": str,             # Vendor/supplier name (optional)
                    "product_type": str,       # Product type/category (optional)
                    "weight": float,           # Weight in kg (optional)
                    "weight_unit": str         # Weight unit (optional)
                }

        Returns:
            Dictionary with deployment result:
            {
                "success": bool,
                "platform_product_id": str,  # Platform's internal ID
                "platform_url": str,         # Direct URL to product
                "admin_url": str,            # Admin panel URL (optional)
                "error": str (only if failed)
            }

        Raises:
            InvalidRequestError: If product data is invalid
            PlatformAPIError: If deployment fails

        Example:
            >>> result = await adapter.deploy_product({
            ...     "title": "Smart Watch Pro",
            ...     "price": 99.99,
            ...     "sku": "SW-PRO-001",
            ...     "inventory": 100
            ... })
            >>> print(result["platform_product_id"])
        """
        pass

    @abstractmethod
    async def update_product(self, platform_product_id: str, updates: dict) -> dict:
        """
        Update an existing product on the platform.

        Args:
            platform_product_id: Platform's internal product ID
            updates: Dictionary of fields to update:
                {
                    "title": str (optional),
                    "description": str (optional),
                    "price": float (optional),
                    "inventory": int (optional),
                    "images": list[str] (optional),
                    "tags": list[str] (optional),
                    ...
                }

        Returns:
            Dictionary with update result:
            {
                "success": bool,
                "updated_fields": list[str],  # List of fields that were updated
                "error": str (only if failed)
            }

        Raises:
            ProductNotFoundError: If product doesn't exist
            InvalidRequestError: If update data is invalid
            PlatformAPIError: If update fails

        Example:
            >>> result = await adapter.update_product(
            ...     "prod_123",
            ...     {"price": 89.99, "inventory": 150}
            ... )
        """
        pass

    @abstractmethod
    async def delete_product(self, platform_product_id: str) -> dict:
        """
        Delete or archive a product from the platform.

        Note: Some platforms archive products instead of permanently deleting them.

        Args:
            platform_product_id: Platform's internal product ID

        Returns:
            Dictionary with deletion result:
            {
                "success": bool,
                "archived": bool,  # True if archived instead of deleted
                "error": str (only if failed)
            }

        Raises:
            ProductNotFoundError: If product doesn't exist
            PlatformAPIError: If deletion fails

        Example:
            >>> result = await adapter.delete_product("prod_123")
            >>> if result["archived"]:
            ...     print("Product archived (not permanently deleted)")
        """
        pass

    @abstractmethod
    async def get_orders(
        self,
        limit: int = 50,
        status: str = "any",
        since: Optional[datetime] = None
    ) -> dict:
        """
        Fetch orders from the platform.

        Args:
            limit: Maximum number of orders to fetch (default: 50)
            status: Order status filter:
                - "any": All orders
                - "pending": Pending/unfulfilled orders
                - "fulfilled": Completed orders
                - "cancelled": Cancelled orders
                - "refunded": Refunded orders
            since: Only fetch orders created after this datetime (optional)

        Returns:
            Dictionary with orders:
            {
                "success": bool,
                "orders": list[dict],  # List of normalized order objects
                "total_count": int,    # Total number of orders matching filter
                "has_more": bool,      # True if more orders available
                "error": str (only if failed)
            }

            Each order in "orders" list:
            {
                "platform_order_id": str,
                "order_number": str,
                "customer_email": str,
                "total_price": float,
                "currency": str,
                "status": str,
                "created_at": str (ISO 8601),
                "line_items": list[dict],
                "shipping_address": dict,
                "tracking_number": str (optional)
            }

        Raises:
            PlatformAPIError: If fetching orders fails

        Example:
            >>> result = await adapter.get_orders(limit=10, status="pending")
            >>> for order in result["orders"]:
            ...     print(f"Order {order['order_number']}: ${order['total_price']}")
        """
        pass

    @abstractmethod
    async def get_products(
        self,
        limit: int = 50,
        published_status: str = "published"
    ) -> dict:
        """
        Fetch products from the platform.

        Args:
            limit: Maximum number of products to fetch (default: 50)
            published_status: Publication status filter:
                - "published": Published/active products only
                - "unpublished": Unpublished/draft products only
                - "any": All products

        Returns:
            Dictionary with products:
            {
                "success": bool,
                "products": list[dict],  # List of normalized product objects
                "total_count": int,      # Total number of products
                "has_more": bool,        # True if more products available
                "error": str (only if failed)
            }

            Each product in "products" list:
            {
                "platform_product_id": str,
                "title": str,
                "description": str,
                "price": float,
                "sku": str,
                "inventory": int,
                "images": list[str],
                "status": str,
                "created_at": str (ISO 8601)
            }

        Raises:
            PlatformAPIError: If fetching products fails

        Example:
            >>> result = await adapter.get_products(limit=20)
            >>> print(f"Found {result['total_count']} products")
        """
        pass

    @abstractmethod
    async def update_inventory(
        self,
        platform_product_id: str,
        quantity: int,
        location_id: Optional[str] = None
    ) -> dict:
        """
        Update product inventory/stock quantity.

        Args:
            platform_product_id: Platform's internal product ID
            quantity: New inventory quantity
            location_id: Inventory location ID (for multi-location platforms)

        Returns:
            Dictionary with update result:
            {
                "success": bool,
                "new_quantity": int,
                "previous_quantity": int (optional),
                "location_id": str (optional),
                "error": str (only if failed)
            }

        Raises:
            ProductNotFoundError: If product doesn't exist
            InvalidRequestError: If quantity is invalid
            PlatformAPIError: If update fails

        Example:
            >>> result = await adapter.update_inventory("prod_123", 75)
            >>> print(f"Inventory updated to {result['new_quantity']}")
        """
        pass

    @abstractmethod
    async def sync_orders(
        self,
        since: Optional[datetime] = None
    ) -> dict:
        """
        Sync recent orders and update local database.

        This method fetches recent orders from the platform and updates
        the local database with new or modified orders.

        Args:
            since: Only sync orders created/updated after this datetime
                   If None, uses last sync time or defaults to last 24 hours

        Returns:
            Dictionary with sync results:
            {
                "success": bool,
                "orders_synced": int,      # New orders added
                "orders_updated": int,     # Existing orders updated
                "last_sync_time": str,     # ISO 8601 timestamp
                "error": str (only if failed)
            }

        Raises:
            PlatformAPIError: If sync fails

        Example:
            >>> result = await adapter.sync_orders()
            >>> print(f"Synced {result['orders_synced']} new orders")
        """
        pass

    @abstractmethod
    async def get_store_info(self) -> dict:
        """
        Get store/account information from the platform.

        Returns:
            Dictionary with store information:
            {
                "success": bool,
                "store_name": str,
                "store_url": str,
                "email": str,
                "currency": str,          # Default currency code (USD, EUR, etc.)
                "domain": str,            # Store domain
                "plan": str,              # Subscription plan name
                "country": str,           # Store country code
                "timezone": str,          # Store timezone
                "enabled": bool,          # Store is active/enabled
                "error": str (only if failed)
            }

        Raises:
            AuthenticationError: If credentials are invalid
            PlatformAPIError: If fetching store info fails

        Example:
            >>> info = await adapter.get_store_info()
            >>> print(f"Store: {info['store_name']} ({info['plan']})")
        """
        pass

    # ========================================================================
    # HELPER METHODS - Concrete implementations
    # ========================================================================

    def get_platform_info(self) -> dict:
        """
        Get information about this platform adapter.

        Returns:
            Dictionary with platform information:
            {
                "platform": str,        # Platform name
                "api_version": str,     # API version
                "adapter_version": str, # Adapter version
                "base_url": str,        # API base URL
                "requests_made": int    # Number of API requests made
            }

        Example:
            >>> info = adapter.get_platform_info()
            >>> print(f"Platform: {info['platform']} v{info['api_version']}")
        """
        return {
            "platform": self.platform_name,
            "api_version": self.api_version,
            "adapter_version": "1.0.0",
            "base_url": self.base_url,
            "requests_made": self._request_count
        }

    def track_request(self) -> None:
        """
        Track API request for rate limiting and analytics.

        This method should be called by adapters after each API request.
        """
        self._request_count += 1
        self._last_request_time = datetime.now(timezone.utc)

    def get_request_stats(self) -> dict:
        """
        Get API request statistics.

        Returns:
            Dictionary with request statistics:
            {
                "total_requests": int,
                "last_request_time": str (ISO 8601) or None
            }
        """
        return {
            "total_requests": self._request_count,
            "last_request_time": self._last_request_time.isoformat() if self._last_request_time else None
        }

    def validate_product_data(self, product: dict) -> None:
        """
        Validate product data before deployment.

        Args:
            product: Product dictionary to validate

        Raises:
            InvalidRequestError: If product data is invalid

        Example:
            >>> adapter.validate_product_data(product)  # Raises if invalid
        """
        required_fields = ["title", "price"]
        missing_fields = [field for field in required_fields if field not in product]

        if missing_fields:
            raise InvalidRequestError(
                f"Missing required fields: {', '.join(missing_fields)}",
                platform=self.platform_name
            )

        # Validate price
        if not isinstance(product.get("price"), (int, float)) or product["price"] < 0:
            raise InvalidRequestError(
                "Price must be a positive number",
                platform=self.platform_name,
                field="price"
            )

        # Validate title
        if not product.get("title") or not isinstance(product["title"], str):
            raise InvalidRequestError(
                "Title must be a non-empty string",
                platform=self.platform_name,
                field="title"
            )

        # Validate inventory if provided
        if "inventory" in product:
            if not isinstance(product["inventory"], int) or product["inventory"] < 0:
                raise InvalidRequestError(
                    "Inventory must be a non-negative integer",
                    platform=self.platform_name,
                    field="inventory"
                )

    def normalize_product(self, platform_product: dict) -> dict:
        """
        Convert platform-specific product format to standard format.

        This method should be overridden by each adapter to handle
        platform-specific field names and structures.

        Args:
            platform_product: Product in platform-specific format

        Returns:
            Product in standardized format:
            {
                "platform_product_id": str,
                "title": str,
                "description": str,
                "price": float,
                "compare_at_price": float (optional),
                "sku": str,
                "inventory": int,
                "images": list[str],
                "tags": list[str],
                "vendor": str (optional),
                "product_type": str (optional),
                "status": str,
                "created_at": str (ISO 8601),
                "updated_at": str (ISO 8601)
            }

        Example:
            >>> normalized = adapter.normalize_product(shopify_product)
        """
        # Default implementation - override in subclasses
        return platform_product

    def normalize_order(self, platform_order: dict) -> dict:
        """
        Convert platform-specific order format to standard format.

        This method should be overridden by each adapter to handle
        platform-specific field names and structures.

        Args:
            platform_order: Order in platform-specific format

        Returns:
            Order in standardized format:
            {
                "platform_order_id": str,
                "order_number": str,
                "customer_email": str,
                "customer_name": str,
                "total_price": float,
                "subtotal_price": float,
                "tax_price": float,
                "shipping_price": float,
                "currency": str,
                "status": str,
                "financial_status": str,
                "fulfillment_status": str,
                "created_at": str (ISO 8601),
                "updated_at": str (ISO 8601),
                "line_items": list[dict],
                "shipping_address": dict,
                "billing_address": dict,
                "tracking_number": str (optional),
                "tracking_url": str (optional)
            }

        Example:
            >>> normalized = adapter.normalize_order(shopify_order)
        """
        # Default implementation - override in subclasses
        return platform_order

    def build_error_response(
        self,
        error: Exception,
        context: Optional[str] = None
    ) -> dict:
        """
        Build a standardized error response.

        Args:
            error: Exception that occurred
            context: Additional context about the error

        Returns:
            Standardized error response:
            {
                "success": False,
                "error": str,
                "error_type": str,
                "context": str (optional)
            }

        Example:
            >>> try:
            ...     result = await some_operation()
            ... except Exception as e:
            ...     return adapter.build_error_response(e, "deploy_product")
        """
        error_type = type(error).__name__

        response = {
            "success": False,
            "error": str(error),
            "error_type": error_type
        }

        if context:
            response["context"] = context

        if isinstance(error, PlatformAPIError) and error.details:
            response["details"] = error.details

        return response


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_available_platforms() -> List[str]:
    """
    Get list of available platform adapter names.

    Returns:
        List of platform names

    Example:
        >>> platforms = get_available_platforms()
        >>> print(platforms)  # ["shopify", "amazon", "woocommerce"]
    """
    # This will be populated as adapters are implemented
    return ["shopify", "amazon", "woocommerce"]


def validate_platform_name(platform_name: str) -> bool:
    """
    Check if a platform name is valid and supported.

    Args:
        platform_name: Platform name to validate

    Returns:
        True if platform is supported, False otherwise

    Example:
        >>> if validate_platform_name("shopify"):
        ...     print("Shopify is supported")
    """
    available = get_available_platforms()
    return platform_name.lower() in available
