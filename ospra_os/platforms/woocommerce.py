"""
WooCommerce REST API Adapter

This module provides integration with WooCommerce REST API for WordPress stores.
Implements the PlatformAdapter interface for consistent multi-platform support.

WooCommerce is simpler than Amazon but has WordPress-specific considerations.

Author: OspraOS
Date: November 2025
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import logging
import asyncio
import json

from ospra_os.platforms.base import (
    PlatformAdapter,
    PlatformAPIError,
    RateLimitError,
    AuthenticationError,
    ProductNotFoundError,
    InvalidRequestError
)

logger = logging.getLogger(__name__)

# Try to import requests (standard HTTP library)
try:
    import requests
    from requests.auth import HTTPBasicAuth
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests library not installed. WooCommerce adapter will have limited functionality.")


class WooCommerceAdapter(PlatformAdapter):
    """
    WooCommerce REST API adapter for WordPress stores.

    Credentials format:
        {
            "store_url": "https://example.com",
            "consumer_key": "ck_1234567890abcdef1234567890abcdef12345678",
            "consumer_secret": "cs_1234567890abcdef1234567890abcdef12345678",
            "wp_api": True,  # Use WordPress REST API structure
            "version": "wc/v3"  # WooCommerce API version
        }

    Example:
        >>> adapter = WooCommerceAdapter({
        ...     "store_url": "https://mystore.com",
        ...     "consumer_key": "ck_...",
        ...     "consumer_secret": "cs_...",
        ...     "wp_api": True
        ... })
        >>> result = await adapter.test_connection()

    Note:
        WooCommerce uses HTTP Basic Auth over HTTPS with consumer key/secret.
        The REST API follows WordPress conventions with /wp-json/ prefix.
    """

    # WooCommerce rate limiting (conservative - actual limits vary by host)
    RATE_LIMIT_DELAY = 0.25  # 4 requests per second

    def __init__(self, credentials: dict):
        """
        Initialize WooCommerce REST API adapter.

        Args:
            credentials: Dictionary with WooCommerce credentials
        """
        super().__init__(credentials)

        if not REQUESTS_AVAILABLE:
            logger.error(
                "requests library not installed. "
                "Install with: pip install requests"
            )

        self.platform_name = "woocommerce"
        self.api_version = credentials.get("version", "wc/v3")

        # Extract credentials
        self.store_url = credentials.get("store_url", "").rstrip("/")
        self.consumer_key = credentials.get("consumer_key", "")
        self.consumer_secret = credentials.get("consumer_secret", "")
        self.wp_api = credentials.get("wp_api", True)

        # Validate required credentials
        required = ["store_url", "consumer_key", "consumer_secret"]
        missing = [field for field in required if not credentials.get(field)]

        if missing:
            raise AuthenticationError(
                f"Missing WooCommerce credentials: {', '.join(missing)}",
                platform="woocommerce"
            )

        # Validate HTTPS
        if not self.store_url.startswith("https://"):
            logger.warning(
                f"Store URL should use HTTPS for security: {self.store_url}"
            )

        # Set base URL
        if self.wp_api:
            self.base_url = f"{self.store_url}/wp-json/{self.api_version}"
        else:
            # Legacy WooCommerce API
            self.base_url = f"{self.store_url}/wc-api/{self.api_version}"

        # Setup authentication
        if REQUESTS_AVAILABLE:
            self.auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)
        else:
            self.auth = None

        logger.info(f"Initialized WooCommerce adapter for {self.store_url}")

    def _build_headers(self) -> dict:
        """Build HTTP headers for requests"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "OspraOS-WooCommerce-Adapter/1.0"
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None
    ) -> dict:
        """
        Make HTTP request to WooCommerce API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            data: Request body data

        Returns:
            Response data as dictionary
        """
        if not REQUESTS_AVAILABLE:
            raise PlatformAPIError(
                "requests library not installed",
                platform="woocommerce"
            )

        # Enforce rate limiting
        await self._enforce_rate_limit()

        # Build URL
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Build headers
        headers = self._build_headers()

        try:
            # Make request. T106: `requests` is synchronous — calling it directly
            # in this async method blocked the event loop for the full round-trip.
            # Offload to a worker thread so the loop stays responsive.
            if method.upper() == "GET":
                response = await asyncio.to_thread(
                    requests.get, url,
                    auth=self.auth, headers=headers, params=params, timeout=30,
                )
            elif method.upper() == "POST":
                response = await asyncio.to_thread(
                    requests.post, url,
                    auth=self.auth, headers=headers, params=params, json=data, timeout=30,
                )
            elif method.upper() == "PUT":
                response = await asyncio.to_thread(
                    requests.put, url,
                    auth=self.auth, headers=headers, params=params, json=data, timeout=30,
                )
            elif method.upper() == "DELETE":
                response = await asyncio.to_thread(
                    requests.delete, url,
                    auth=self.auth, headers=headers, params=params, timeout=30,
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Track request
            self.track_request()

            # Handle errors
            if response.status_code == 401:
                raise AuthenticationError(
                    "Invalid WooCommerce credentials",
                    platform="woocommerce"
                )
            elif response.status_code == 404:
                raise ProductNotFoundError(
                    "Resource not found",
                    platform="woocommerce"
                )
            elif response.status_code == 429:
                raise RateLimitError(
                    "WooCommerce rate limit exceeded",
                    platform="woocommerce",
                    retry_after=60
                )
            elif response.status_code >= 400:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("message", response.text)
                raise PlatformAPIError(
                    f"WooCommerce API error: {error_msg}",
                    platform="woocommerce",
                    status_code=response.status_code
                )

            # Parse response
            return response.json() if response.text else {}

        except requests.exceptions.RequestException as e:
            logger.error(f"WooCommerce request failed: {e}")
            raise PlatformAPIError(
                f"Request failed: {str(e)}",
                platform="woocommerce"
            )

    async def _enforce_rate_limit(self):
        """Enforce rate limiting between requests"""
        if self._last_request_time:
            elapsed = (datetime.now(timezone.utc) - self._last_request_time).total_seconds()
            if elapsed < self.RATE_LIMIT_DELAY:
                await asyncio.sleep(self.RATE_LIMIT_DELAY - elapsed)

        self._last_request_time = datetime.now(timezone.utc)

    # ========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ========================================================================

    async def test_connection(self) -> dict:
        """
        Test WooCommerce REST API credentials.

        Returns:
            {
                "success": True,
                "store_name": "My WooCommerce Store",
                "store_url": "https://example.com",
                "platform_version": "WooCommerce 8.5.0",
                "wordpress_version": "6.4.2"
            }
        """
        try:
            # Get system status
            response = await self._make_request("GET", "/system_status")

            # Extract info
            environment = response.get("environment", {})
            settings = response.get("settings", {})

            return {
                "success": True,
                "store_name": settings.get("site_title", "WooCommerce Store"),
                "store_url": self.store_url,
                "platform_version": f"WooCommerce {environment.get('version', 'Unknown')}",
                "wordpress_version": environment.get("wp_version", "Unknown"),
                "php_version": environment.get("php_version", "Unknown"),
                "currency": settings.get("currency", "USD")
            }

        except Exception as e:
            return self.build_error_response(e, "test_connection")

    async def deploy_product(self, product: dict) -> dict:
        """
        Deploy product to WooCommerce store.

        Args:
            product: Standard product format with:
                - title (required)
                - description
                - price (required)
                - sku
                - inventory
                - images (list of URLs)
                - tags (list)

        Returns:
            {
                "success": True,
                "platform_product_id": "123",
                "platform_url": "https://example.com/product/smart-watch",
                "sku": "SW-001"
            }
        """
        try:
            # Map to WooCommerce format
            wc_product = {
                "name": product.get("title", ""),
                "type": "simple",  # Default to simple product
                "regular_price": str(product.get("price", 0)),
                "description": product.get("description", ""),
                "short_description": product.get("short_description", ""),
                "sku": product.get("sku", ""),
                "manage_stock": True,
                "stock_quantity": product.get("inventory", 0),
                "status": "publish" if product.get("status") != "draft" else "draft"
            }

            # Add sale price if present
            if product.get("sale_price"):
                wc_product["sale_price"] = str(product["sale_price"])

            # Add images
            if product.get("images"):
                wc_product["images"] = [
                    {"src": img} for img in product["images"]
                ]

            # Add tags
            if product.get("tags"):
                wc_product["tags"] = [
                    {"name": tag} for tag in product["tags"]
                ]

            # Add categories if present
            if product.get("categories"):
                wc_product["categories"] = [
                    {"name": cat} for cat in product["categories"]
                ]

            # Create product
            response = await self._make_request("POST", "/products", data=wc_product)

            product_id = response.get("id")
            permalink = response.get("permalink", "")

            logger.info(f"Created WooCommerce product {product_id}: {wc_product['name']}")

            return {
                "success": True,
                "platform_product_id": str(product_id),
                "platform_url": permalink,
                "sku": response.get("sku", ""),
                "created_at": response.get("date_created", "")
            }

        except Exception as e:
            return self.build_error_response(e, "deploy_product")

    async def update_product(
        self,
        platform_product_id: str,
        updates: dict
    ) -> dict:
        """
        Update existing WooCommerce product.

        Args:
            platform_product_id: WooCommerce product ID
            updates: Fields to update (price, inventory, title, etc.)

        Returns:
            {
                "success": True,
                "updated_fields": ["price", "inventory"]
            }
        """
        try:
            # Map updates to WooCommerce format
            wc_updates = {}
            updated_fields = []

            if "title" in updates:
                wc_updates["name"] = updates["title"]
                updated_fields.append("title")

            if "description" in updates:
                wc_updates["description"] = updates["description"]
                updated_fields.append("description")

            if "price" in updates:
                wc_updates["regular_price"] = str(updates["price"])
                updated_fields.append("price")

            if "sale_price" in updates:
                wc_updates["sale_price"] = str(updates["sale_price"])
                updated_fields.append("sale_price")

            if "inventory" in updates:
                wc_updates["stock_quantity"] = updates["inventory"]
                updated_fields.append("inventory")

            if "sku" in updates:
                wc_updates["sku"] = updates["sku"]
                updated_fields.append("sku")

            if "images" in updates:
                wc_updates["images"] = [
                    {"src": img} for img in updates["images"]
                ]
                updated_fields.append("images")

            if "tags" in updates:
                wc_updates["tags"] = [
                    {"name": tag} for tag in updates["tags"]
                ]
                updated_fields.append("tags")

            # Update product
            response = await self._make_request(
                "PUT",
                f"/products/{platform_product_id}",
                data=wc_updates
            )

            logger.info(f"Updated WooCommerce product {platform_product_id}")

            return {
                "success": True,
                "platform_product_id": str(response.get("id")),
                "updated_fields": updated_fields,
                "updated_at": response.get("date_modified", "")
            }

        except Exception as e:
            return self.build_error_response(e, "update_product")

    async def delete_product(self, platform_product_id: str) -> dict:
        """
        Delete WooCommerce product.

        Args:
            platform_product_id: WooCommerce product ID

        Returns:
            {
                "success": True,
                "deleted": True
            }
        """
        try:
            # Delete product (force=true permanently deletes)
            response = await self._make_request(
                "DELETE",
                f"/products/{platform_product_id}",
                params={"force": "true"}
            )

            logger.info(f"Deleted WooCommerce product {platform_product_id}")

            return {
                "success": True,
                "deleted": True,
                "platform_product_id": platform_product_id
            }

        except Exception as e:
            return self.build_error_response(e, "delete_product")

    async def get_orders(
        self,
        limit: int = 50,
        status: str = "any",
        since: Optional[datetime] = None
    ) -> dict:
        """
        Fetch orders from WooCommerce.

        Args:
            limit: Max orders to fetch (max 100)
            status: "any", "pending", "processing", "completed", "cancelled"
            since: Only orders created after this datetime

        Returns:
            {
                "success": True,
                "orders": [...],
                "total_count": 42,
                "has_more": False
            }
        """
        try:
            # Build parameters
            params = {
                "per_page": min(limit, 100)  # WooCommerce max is 100
            }

            # Add status filter
            if status != "any":
                # Map standard statuses to WooCommerce statuses
                wc_status = status
                if status == "fulfilled":
                    wc_status = "completed"
                params["status"] = wc_status

            # Add date filter
            if since:
                params["after"] = since.isoformat()

            # Fetch orders
            response = await self._make_request("GET", "/orders", params=params)

            # Normalize orders
            normalized_orders = []
            if isinstance(response, list):
                for order in response:
                    normalized = self.normalize_order(order)
                    normalized_orders.append(normalized)

            return {
                "success": True,
                "orders": normalized_orders,
                "total_count": len(normalized_orders),
                "has_more": len(normalized_orders) >= limit
            }

        except Exception as e:
            return self.build_error_response(e, "get_orders")

    async def get_products(
        self,
        limit: int = 50,
        published_status: str = "published"
    ) -> dict:
        """
        Fetch products from WooCommerce.

        Args:
            limit: Max products to fetch
            published_status: "published", "draft", "any"

        Returns:
            {
                "success": True,
                "products": [...],
                "total_count": 42,
                "has_more": False
            }
        """
        try:
            # Build parameters
            params = {
                "per_page": min(limit, 100)
            }

            # Add status filter
            if published_status == "published":
                params["status"] = "publish"
            elif published_status == "draft":
                params["status"] = "draft"
            # "any" - no filter

            # Fetch products
            response = await self._make_request("GET", "/products", params=params)

            # Normalize products
            normalized_products = []
            if isinstance(response, list):
                for product in response:
                    normalized = self.normalize_product(product)
                    normalized_products.append(normalized)

            return {
                "success": True,
                "products": normalized_products,
                "total_count": len(normalized_products),
                "has_more": len(normalized_products) >= limit
            }

        except Exception as e:
            return self.build_error_response(e, "get_products")

    async def update_inventory(
        self,
        platform_product_id: str,
        quantity: int,
        location_id: Optional[str] = None
    ) -> dict:
        """
        Update WooCommerce product inventory.

        Args:
            platform_product_id: WooCommerce product ID
            quantity: New inventory quantity
            location_id: Not used for WooCommerce (single inventory)

        Returns:
            {
                "success": True,
                "new_quantity": 75
            }
        """
        try:
            # Update stock quantity
            response = await self._make_request(
                "PUT",
                f"/products/{platform_product_id}",
                data={
                    "manage_stock": True,
                    "stock_quantity": quantity
                }
            )

            new_quantity = response.get("stock_quantity", quantity)

            logger.info(
                f"Updated inventory for WooCommerce product {platform_product_id}: {new_quantity}"
            )

            return {
                "success": True,
                "platform_product_id": platform_product_id,
                "new_quantity": new_quantity,
                "in_stock": response.get("stock_status") == "instock"
            }

        except Exception as e:
            return self.build_error_response(e, "update_inventory")

    async def sync_orders(
        self,
        since: Optional[datetime] = None
    ) -> dict:
        """
        Sync recent orders from WooCommerce and calculate metrics.

        Args:
            since: Only sync orders after this datetime (defaults to last 30 days)

        Returns:
            {
                "success": True,
                "orders_synced": 42,
                "orders_updated": 0,
                "last_sync_time": "2025-11-14T12:00:00Z",
                "metrics": {
                    "total_revenue": 5234.56,
                    "avg_order_value": 124.63,
                    "total_orders": 42
                }
            }
        """
        try:
            # Default to last 30 days
            if not since:
                since = datetime.now(timezone.utc) - timedelta(days=30)

            # Fetch all orders
            result = await self.get_orders(limit=100, status="any", since=since)

            if not result.get("success"):
                return result

            orders = result.get("orders", [])

            # Calculate metrics
            total_revenue = sum(float(order.get("total_price", 0)) for order in orders)
            avg_order_value = total_revenue / len(orders) if orders else 0

            # Count by status
            status_counts = {}
            for order in orders:
                status = order.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

            sync_time = datetime.now(timezone.utc).isoformat()

            logger.info(
                f"Synced {len(orders)} WooCommerce orders. "
                f"Revenue: ${total_revenue:.2f}, AOV: ${avg_order_value:.2f}"
            )

            return {
                "success": True,
                "orders_synced": len(orders),
                "orders_updated": 0,
                "last_sync_time": sync_time,
                "metrics": {
                    "total_revenue": round(total_revenue, 2),
                    "avg_order_value": round(avg_order_value, 2),
                    "total_orders": len(orders),
                    "status_breakdown": status_counts
                }
            }

        except Exception as e:
            return self.build_error_response(e, "sync_orders")

    async def get_store_info(self) -> dict:
        """
        Get WooCommerce store information.

        Returns:
            {
                "success": True,
                "store_name": "My WooCommerce Store",
                "store_url": "https://example.com",
                "email": "admin@example.com",
                "currency": "USD",
                "domain": "example.com",
                "plan": "Self-Hosted",
                "country": "US",
                "timezone": "America/New_York"
            }
        """
        try:
            # Get system status
            system_response = await self._make_request("GET", "/system_status")

            # Get general settings
            settings_response = await self._make_request("GET", "/settings/general")

            # Extract info
            environment = system_response.get("environment", {})
            settings_data = system_response.get("settings", {})

            # Parse settings
            settings_map = {}
            if isinstance(settings_response, list):
                for setting in settings_response:
                    settings_map[setting.get("id")] = setting.get("value")

            return {
                "success": True,
                "store_name": settings_map.get("woocommerce_store_name", "WooCommerce Store"),
                "store_url": self.store_url,
                "email": settings_map.get("woocommerce_email_from_address", ""),
                "currency": settings_map.get("woocommerce_currency", "USD"),
                "domain": self.store_url.replace("https://", "").replace("http://", ""),
                "plan": "Self-Hosted",  # WooCommerce is self-hosted
                "country": settings_map.get("woocommerce_default_country", "US"),
                "timezone": environment.get("timezone", "UTC"),
                "woocommerce_version": environment.get("version", "Unknown"),
                "wordpress_version": environment.get("wp_version", "Unknown"),
                "php_version": environment.get("php_version", "Unknown")
            }

        except Exception as e:
            return self.build_error_response(e, "get_store_info")

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def normalize_product(self, wc_product: dict) -> dict:
        """
        Convert WooCommerce product format to standard format.

        Args:
            wc_product: Product in WooCommerce format

        Returns:
            Product in standard format
        """
        # Extract images
        images = []
        for img in wc_product.get("images", []):
            images.append(img.get("src", ""))

        # Extract tags
        tags = []
        for tag in wc_product.get("tags", []):
            tags.append(tag.get("name", ""))

        # Extract categories
        categories = []
        for cat in wc_product.get("categories", []):
            categories.append(cat.get("name", ""))

        return {
            "platform_product_id": str(wc_product.get("id", "")),
            "title": wc_product.get("name", ""),
            "description": wc_product.get("description", ""),
            "short_description": wc_product.get("short_description", ""),
            "price": float(wc_product.get("regular_price", 0) or 0),
            "sale_price": float(wc_product.get("sale_price", 0) or 0) if wc_product.get("sale_price") else None,
            "sku": wc_product.get("sku", ""),
            "inventory": wc_product.get("stock_quantity", 0) or 0,
            "images": images,
            "tags": tags,
            "categories": categories,
            "vendor": "",  # WooCommerce doesn't have vendor concept
            "product_type": wc_product.get("type", "simple"),
            "status": "active" if wc_product.get("status") == "publish" else "draft",
            "created_at": wc_product.get("date_created", ""),
            "updated_at": wc_product.get("date_modified", ""),
            "permalink": wc_product.get("permalink", "")
        }

    def normalize_order(self, wc_order: dict) -> dict:
        """
        Convert WooCommerce order format to standard format.

        Args:
            wc_order: Order in WooCommerce format

        Returns:
            Order in standard format
        """
        # Extract line items
        line_items = []
        for item in wc_order.get("line_items", []):
            line_items.append({
                "product_id": str(item.get("product_id", "")),
                "variant_id": str(item.get("variation_id", "")),
                "title": item.get("name", ""),
                "quantity": item.get("quantity", 0),
                "price": float(item.get("price", 0)),
                "sku": item.get("sku", ""),
                "total": float(item.get("total", 0))
            })

        # Extract addresses
        billing = wc_order.get("billing", {})
        shipping = wc_order.get("shipping", {})

        return {
            "platform_order_id": str(wc_order.get("id", "")),
            "order_number": wc_order.get("number", ""),
            "customer_email": billing.get("email", ""),
            "customer_name": f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
            "total_price": float(wc_order.get("total", 0)),
            "subtotal_price": float(wc_order.get("total", 0)) - float(wc_order.get("total_tax", 0)),
            "tax_price": float(wc_order.get("total_tax", 0)),
            "shipping_price": float(wc_order.get("shipping_total", 0)),
            "currency": wc_order.get("currency", "USD"),
            "status": wc_order.get("status", ""),
            "financial_status": wc_order.get("payment_method_title", ""),
            "fulfillment_status": "fulfilled" if wc_order.get("status") == "completed" else "unfulfilled",
            "created_at": wc_order.get("date_created", ""),
            "updated_at": wc_order.get("date_modified", ""),
            "line_items": line_items,
            "shipping_address": {
                "name": f"{shipping.get('first_name', '')} {shipping.get('last_name', '')}".strip(),
                "address1": shipping.get("address_1", ""),
                "address2": shipping.get("address_2", ""),
                "city": shipping.get("city", ""),
                "province": shipping.get("state", ""),
                "country": shipping.get("country", ""),
                "zip": shipping.get("postcode", ""),
                "phone": shipping.get("phone", "")
            },
            "billing_address": {
                "name": f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
                "address1": billing.get("address_1", ""),
                "address2": billing.get("address_2", ""),
                "city": billing.get("city", ""),
                "province": billing.get("state", ""),
                "country": billing.get("country", ""),
                "zip": billing.get("postcode", ""),
                "phone": billing.get("phone", ""),
                "email": billing.get("email", "")
            },
            "tracking_number": "",  # Would need plugin for tracking
            "tracking_url": ""
        }
