"""
Shopify Platform Adapter

This module provides integration with Shopify's Admin API v2024-01+.
Implements the PlatformAdapter interface for consistent multi-platform support.

Author: OspraOS
Date: November 2025
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import logging
import asyncio
import httpx

from ospra_os.platforms.base import (
    PlatformAdapter,
    PlatformAPIError,
    RateLimitError,
    AuthenticationError,
    ProductNotFoundError,
    InvalidRequestError
)

logger = logging.getLogger(__name__)


class ShopifyAdapter(PlatformAdapter):
    """
    Shopify platform adapter using Admin REST API.

    Credentials format:
        {
            "store_domain": "example.myshopify.com",
            "admin_api_token": "shpat_xxxxx",
            "api_version": "2024-01"  # Optional, defaults to 2024-01
        }

    Example:
        >>> adapter = ShopifyAdapter({
        ...     "store_domain": "mystore.myshopify.com",
        ...     "admin_api_token": "shpat_abc123"
        ... })
        >>> result = await adapter.test_connection()
    """

    # Shopify rate limit: 2 requests/second (bucket algorithm)
    RATE_LIMIT_DELAY = 0.5  # 500ms between requests

    def __init__(self, credentials: dict):
        """
        Initialize Shopify adapter.

        Args:
            credentials: Dictionary with store_domain, admin_api_token, api_version
        """
        super().__init__(credentials)

        self.platform_name = "shopify"
        self.store_domain = credentials.get("store_domain", "")
        self.admin_api_token = credentials.get("admin_api_token", "")
        self.api_version = credentials.get("api_version", "2024-01")

        if not self.store_domain or not self.admin_api_token:
            raise AuthenticationError(
                "Missing Shopify credentials: store_domain and admin_api_token required",
                platform="shopify"
            )

        # Clean store domain (remove https://, trailing slashes)
        self.store_domain = self.store_domain.replace("https://", "").replace("http://", "").rstrip("/")

        self.base_url = f"https://{self.store_domain}/admin/api/{self.api_version}"

        # Track rate limit bucket
        self._last_request_time: Optional[datetime] = None
        self._bucket_count = 0
        self._bucket_max = 40  # Shopify's bucket size

        logger.info(f"Initialized Shopify adapter for {self.store_domain}")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None
    ) -> dict:
        """
        Make authenticated request to Shopify API with rate limiting.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without /admin/api/{version}/)
            data: JSON data for POST/PUT requests
            params: Query parameters

        Returns:
            Response JSON

        Raises:
            AuthenticationError: If credentials are invalid
            RateLimitError: If rate limit exceeded
            PlatformAPIError: For other API errors
        """
        # Rate limiting
        await self._enforce_rate_limit()

        # Build URL
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if not url.endswith(".json"):
            url += ".json"

        # Headers
        headers = {
            "X-Shopify-Access-Token": self.admin_api_token,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    params=params
                )

                # Track request
                self.track_request()
                self._last_request_time = datetime.now(timezone.utc)

                # Check rate limit header
                rate_limit_header = response.headers.get("X-Shopify-Shop-Api-Call-Limit")
                if rate_limit_header:
                    current, maximum = map(int, rate_limit_header.split("/"))
                    self._bucket_count = current
                    self._bucket_max = maximum

                # Handle errors
                if response.status_code == 401:
                    raise AuthenticationError(
                        "Invalid Shopify access token",
                        platform="shopify"
                    )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2))
                    raise RateLimitError(
                        "Shopify rate limit exceeded",
                        platform="shopify",
                        retry_after=retry_after
                    )

                if response.status_code == 404:
                    raise ProductNotFoundError(
                        endpoint.split("/")[-1].replace(".json", ""),
                        platform="shopify"
                    )

                response.raise_for_status()

                # Return JSON if present
                if response.content:
                    return response.json()
                return {}

        except (AuthenticationError, RateLimitError, ProductNotFoundError):
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Shopify API error: {e.response.status_code} - {e.response.text}")
            raise PlatformAPIError(
                f"Shopify API error: {e.response.status_code}",
                platform="shopify",
                details={"status_code": e.response.status_code, "response": e.response.text}
            )
        except Exception as e:
            logger.error(f"Shopify request failed: {e}")
            raise PlatformAPIError(
                f"Shopify request failed: {str(e)}",
                platform="shopify"
            )

    async def _enforce_rate_limit(self):
        """Enforce Shopify's 2 requests/second rate limit"""
        if self._last_request_time:
            elapsed = (datetime.now(timezone.utc) - self._last_request_time).total_seconds()
            if elapsed < self.RATE_LIMIT_DELAY:
                await asyncio.sleep(self.RATE_LIMIT_DELAY - elapsed)

        # If bucket is near full, wait longer
        if self._bucket_count >= self._bucket_max * 0.9:
            logger.warning(f"Shopify bucket nearly full ({self._bucket_count}/{self._bucket_max}), throttling...")
            await asyncio.sleep(2.0)

    # ========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ========================================================================

    async def test_connection(self) -> dict:
        """
        Test Shopify API credentials.

        Returns:
            {
                "success": True,
                "store_name": "My Store",
                "store_url": "https://mystore.myshopify.com",
                "platform_version": "2024-01"
            }
        """
        try:
            response = await self._make_request("GET", "shop")

            shop = response.get("shop", {})

            return {
                "success": True,
                "store_name": shop.get("name", ""),
                "store_url": f"https://{shop.get('domain', self.store_domain)}",
                "platform_version": self.api_version,
                "email": shop.get("email", ""),
                "currency": shop.get("currency", "USD")
            }

        except Exception as e:
            return self.build_error_response(e, "test_connection")

    async def deploy_product(self, product: dict) -> dict:
        """
        Deploy product to Shopify.

        Args:
            product: Standard product format

        Returns:
            {
                "success": True,
                "platform_product_id": "12345678901",
                "platform_url": "https://mystore.com/products/smart-watch",
                "admin_url": "https://mystore.myshopify.com/admin/products/12345678901"
            }
        """
        try:
            # Validate product data
            self.validate_product_data(product)

            # Build Shopify product payload
            shopify_product = {
                "product": {
                    "title": product["title"],
                    "body_html": product.get("description", ""),
                    "vendor": product.get("vendor", "OspraOS"),
                    "product_type": product.get("product_type", ""),
                    "tags": ",".join(product.get("tags", [])),
                    "status": "active",
                    "variants": [
                        {
                            "price": str(product["price"]),
                            "compare_at_price": str(product.get("compare_at_price", "")) if product.get("compare_at_price") else None,
                            "sku": product.get("sku", ""),
                            "inventory_management": "shopify",
                            "inventory_quantity": product.get("inventory", 0),
                            "weight": product.get("weight", 0),
                            "weight_unit": product.get("weight_unit", "kg")
                        }
                    ]
                }
            }

            # Add images if provided
            if product.get("images"):
                shopify_product["product"]["images"] = [
                    {"src": url} for url in product["images"]
                ]

            # Create product
            response = await self._make_request("POST", "products", data=shopify_product)

            created_product = response.get("product", {})
            product_id = str(created_product.get("id", ""))
            handle = created_product.get("handle", "")

            return {
                "success": True,
                "platform_product_id": product_id,
                "platform_url": f"https://{self.store_domain.replace('.myshopify.com', '.com')}/products/{handle}",
                "admin_url": f"https://{self.store_domain}/admin/products/{product_id}"
            }

        except Exception as e:
            return self.build_error_response(e, "deploy_product")

    async def update_product(
        self,
        platform_product_id: str,
        updates: dict
    ) -> dict:
        """
        Update existing Shopify product.

        Args:
            platform_product_id: Shopify product ID
            updates: Fields to update (title, price, inventory, etc.)

        Returns:
            {
                "success": True,
                "updated_fields": ["price", "inventory"]
            }
        """
        try:
            # Build update payload
            product_update = {"product": {}}
            updated_fields = []

            # Map standard fields to Shopify fields
            field_mapping = {
                "title": "title",
                "description": "body_html",
                "vendor": "vendor",
                "product_type": "product_type"
            }

            for std_field, shopify_field in field_mapping.items():
                if std_field in updates:
                    product_update["product"][shopify_field] = updates[std_field]
                    updated_fields.append(std_field)

            # Handle tags
            if "tags" in updates:
                product_update["product"]["tags"] = ",".join(updates["tags"])
                updated_fields.append("tags")

            # Handle variant updates (price, sku, inventory)
            variant_updates = {}
            if "price" in updates:
                variant_updates["price"] = str(updates["price"])
                updated_fields.append("price")

            if "compare_at_price" in updates:
                variant_updates["compare_at_price"] = str(updates["compare_at_price"])
                updated_fields.append("compare_at_price")

            if "sku" in updates:
                variant_updates["sku"] = updates["sku"]
                updated_fields.append("sku")

            # If variant fields need updating, get first variant and update it
            if variant_updates:
                # Get product to find variant ID
                product_data = await self._make_request("GET", f"products/{platform_product_id}")
                variants = product_data.get("product", {}).get("variants", [])

                if variants:
                    variant_id = variants[0]["id"]
                    # Update variant
                    await self._make_request(
                        "PUT",
                        f"variants/{variant_id}",
                        data={"variant": variant_updates}
                    )

            # Update product fields if any
            if product_update["product"]:
                await self._make_request(
                    "PUT",
                    f"products/{platform_product_id}",
                    data=product_update
                )

            # Handle inventory separately if needed
            if "inventory" in updates:
                await self.update_inventory(platform_product_id, updates["inventory"])
                updated_fields.append("inventory")

            return {
                "success": True,
                "updated_fields": updated_fields
            }

        except Exception as e:
            return self.build_error_response(e, "update_product")

    async def delete_product(self, platform_product_id: str) -> dict:
        """
        Delete product from Shopify.

        Note: Shopify permanently deletes products.

        Args:
            platform_product_id: Shopify product ID

        Returns:
            {
                "success": True,
                "archived": False
            }
        """
        try:
            await self._make_request("DELETE", f"products/{platform_product_id}")

            return {
                "success": True,
                "archived": False  # Shopify deletes permanently
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
        Fetch orders from Shopify.

        Args:
            limit: Max orders to fetch (max 250)
            status: "any", "open", "closed", "cancelled"
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
            # Build query params
            params = {
                "limit": min(limit, 250)  # Shopify max is 250
            }

            # Map status
            if status == "pending":
                params["status"] = "open"
                params["fulfillment_status"] = "unfulfilled"
            elif status == "fulfilled":
                params["fulfillment_status"] = "fulfilled"
            elif status == "cancelled":
                params["status"] = "cancelled"
            elif status != "any":
                params["status"] = status

            # Filter by date
            if since:
                params["created_at_min"] = since.isoformat()

            # Fetch orders
            response = await self._make_request("GET", "orders", params=params)

            orders = response.get("orders", [])

            # Normalize orders
            normalized_orders = [self.normalize_order(order) for order in orders]

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
        Fetch products from Shopify.

        Args:
            limit: Max products to fetch (max 250)
            published_status: "published", "unpublished", "any"

        Returns:
            {
                "success": True,
                "products": [...],
                "total_count": 42,
                "has_more": False
            }
        """
        try:
            # Build query params
            params = {
                "limit": min(limit, 250)
            }

            if published_status != "any":
                params["status"] = "active" if published_status == "published" else "draft"

            # Fetch products
            response = await self._make_request("GET", "products", params=params)

            products = response.get("products", [])

            # Normalize products
            normalized_products = [self.normalize_product(product) for product in products]

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
        Update product inventory on Shopify.

        Args:
            platform_product_id: Shopify product ID
            quantity: New inventory quantity
            location_id: Shopify location ID (optional, uses primary if not provided)

        Returns:
            {
                "success": True,
                "new_quantity": 75,
                "previous_quantity": 100,
                "location_id": "12345"
            }
        """
        try:
            # Get product to find variant and inventory item
            product_data = await self._make_request("GET", f"products/{platform_product_id}")

            variants = product_data.get("product", {}).get("variants", [])
            if not variants:
                raise InvalidRequestError(
                    "Product has no variants",
                    platform="shopify",
                    field="variants"
                )

            variant = variants[0]
            inventory_item_id = variant.get("inventory_item_id")

            if not inventory_item_id:
                raise InvalidRequestError(
                    "Variant has no inventory_item_id",
                    platform="shopify"
                )

            # Get location ID if not provided
            if not location_id:
                locations = await self._make_request("GET", "locations")
                location_list = locations.get("locations", [])
                if location_list:
                    location_id = str(location_list[0]["id"])
                else:
                    raise PlatformAPIError(
                        "No locations found for store",
                        platform="shopify"
                    )

            # Get current inventory level
            inventory_levels = await self._make_request(
                "GET",
                "inventory_levels",
                params={"inventory_item_ids": inventory_item_id, "location_ids": location_id}
            )

            previous_quantity = 0
            if inventory_levels.get("inventory_levels"):
                previous_quantity = inventory_levels["inventory_levels"][0].get("available", 0)

            # Set new inventory level
            await self._make_request(
                "POST",
                "inventory_levels/set",
                data={
                    "location_id": int(location_id),
                    "inventory_item_id": int(inventory_item_id),
                    "available": quantity
                }
            )

            return {
                "success": True,
                "new_quantity": quantity,
                "previous_quantity": previous_quantity,
                "location_id": location_id
            }

        except Exception as e:
            return self.build_error_response(e, "update_inventory")

    async def sync_orders(
        self,
        since: Optional[datetime] = None
    ) -> dict:
        """
        Sync recent orders from Shopify and update metrics.

        Args:
            since: Only sync orders after this datetime (defaults to last 30 days)

        Returns:
            {
                "success": True,
                "orders_synced": 42,
                "orders_updated": 5,
                "last_sync_time": "2025-11-14T12:00:00Z"
            }
        """
        try:
            # Default to last 30 days if not specified
            if not since:
                since = datetime.now(timezone.utc) - timedelta(days=30)

            # Fetch orders
            result = await self.get_orders(limit=250, status="any", since=since)

            if not result.get("success"):
                return result

            orders = result.get("orders", [])

            # Calculate metrics
            total_revenue = sum(float(order.get("total_price", 0)) for order in orders)
            avg_order_value = total_revenue / len(orders) if orders else 0

            sync_time = datetime.now(timezone.utc).isoformat()

            logger.info(
                f"Synced {len(orders)} Shopify orders. "
                f"Revenue: ${total_revenue:.2f}, AOV: ${avg_order_value:.2f}"
            )

            return {
                "success": True,
                "orders_synced": len(orders),
                "orders_updated": 0,  # Would track updates in real implementation
                "last_sync_time": sync_time,
                "metrics": {
                    "total_revenue": round(total_revenue, 2),
                    "avg_order_value": round(avg_order_value, 2),
                    "total_orders": len(orders)
                }
            }

        except Exception as e:
            return self.build_error_response(e, "sync_orders")

    async def get_store_info(self) -> dict:
        """
        Get comprehensive Shopify store information.

        Returns:
            {
                "success": True,
                "store_name": "My Store",
                "store_url": "https://mystore.com",
                "email": "owner@mystore.com",
                "currency": "USD",
                "domain": "mystore.com",
                "plan": "shopify_plus",
                "country": "US",
                "timezone": "America/New_York",
                "enabled": True
            }
        """
        try:
            response = await self._make_request("GET", "shop")

            shop = response.get("shop", {})

            return {
                "success": True,
                "store_name": shop.get("name", ""),
                "store_url": f"https://{shop.get('domain', '')}",
                "email": shop.get("email", ""),
                "currency": shop.get("currency", "USD"),
                "domain": shop.get("domain", ""),
                "plan": shop.get("plan_name", ""),
                "country": shop.get("country_code", ""),
                "timezone": shop.get("iana_timezone", ""),
                "enabled": not shop.get("setup_required", True),
                "phone": shop.get("phone", ""),
                "myshopify_domain": shop.get("myshopify_domain", ""),
                "plan_display_name": shop.get("plan_display_name", "")
            }

        except Exception as e:
            return self.build_error_response(e, "get_store_info")

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def normalize_product(self, shopify_product: dict) -> dict:
        """
        Convert Shopify product format to standard format.

        Args:
            shopify_product: Product in Shopify format

        Returns:
            Product in standard format
        """
        variants = shopify_product.get("variants", [])
        first_variant = variants[0] if variants else {}

        images = shopify_product.get("images", [])
        image_urls = [img.get("src", "") for img in images]

        return {
            "platform_product_id": str(shopify_product.get("id", "")),
            "title": shopify_product.get("title", ""),
            "description": shopify_product.get("body_html", ""),
            "price": float(first_variant.get("price", 0)),
            "compare_at_price": float(first_variant.get("compare_at_price", 0)) if first_variant.get("compare_at_price") else None,
            "sku": first_variant.get("sku", ""),
            "inventory": first_variant.get("inventory_quantity", 0),
            "images": image_urls,
            "tags": shopify_product.get("tags", "").split(",") if shopify_product.get("tags") else [],
            "vendor": shopify_product.get("vendor", ""),
            "product_type": shopify_product.get("product_type", ""),
            "status": shopify_product.get("status", "draft"),
            "created_at": shopify_product.get("created_at", ""),
            "updated_at": shopify_product.get("updated_at", ""),
            "handle": shopify_product.get("handle", "")
        }

    def normalize_order(self, shopify_order: dict) -> dict:
        """
        Convert Shopify order format to standard format.

        Args:
            shopify_order: Order in Shopify format

        Returns:
            Order in standard format
        """
        line_items = []
        for item in shopify_order.get("line_items", []):
            line_items.append({
                "product_id": str(item.get("product_id", "")),
                "variant_id": str(item.get("variant_id", "")),
                "title": item.get("title", ""),
                "quantity": item.get("quantity", 0),
                "price": float(item.get("price", 0)),
                "sku": item.get("sku", "")
            })

        shipping_address = shopify_order.get("shipping_address", {})
        billing_address = shopify_order.get("billing_address", {})

        # Get tracking info from fulfillments
        tracking_number = None
        tracking_url = None
        fulfillments = shopify_order.get("fulfillments", [])
        if fulfillments:
            tracking_number = fulfillments[0].get("tracking_number")
            tracking_url = fulfillments[0].get("tracking_url")

        return {
            "platform_order_id": str(shopify_order.get("id", "")),
            "order_number": shopify_order.get("name", ""),
            "customer_email": shopify_order.get("email", ""),
            "customer_name": shopify_order.get("customer", {}).get("first_name", "") + " " + shopify_order.get("customer", {}).get("last_name", ""),
            "total_price": float(shopify_order.get("total_price", 0)),
            "subtotal_price": float(shopify_order.get("subtotal_price", 0)),
            "tax_price": float(shopify_order.get("total_tax", 0)),
            "shipping_price": float(shopify_order.get("total_shipping_price_set", {}).get("shop_money", {}).get("amount", 0)),
            "currency": shopify_order.get("currency", "USD"),
            "status": shopify_order.get("fulfillment_status", "unfulfilled"),
            "financial_status": shopify_order.get("financial_status", ""),
            "fulfillment_status": shopify_order.get("fulfillment_status", ""),
            "created_at": shopify_order.get("created_at", ""),
            "updated_at": shopify_order.get("updated_at", ""),
            "line_items": line_items,
            "shipping_address": shipping_address,
            "billing_address": billing_address,
            "tracking_number": tracking_number,
            "tracking_url": tracking_url
        }
