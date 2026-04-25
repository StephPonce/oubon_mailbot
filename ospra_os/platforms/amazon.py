"""
Amazon Seller Partner API Adapter

This module provides integration with Amazon's SP-API (Selling Partner API).
Implements the PlatformAdapter interface for consistent multi-platform support.

Note: Amazon SP-API is significantly more complex than other platforms.
MVP focuses on order management and inventory. Product creation is simplified.

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

# Try to import SP-API library
try:
    from sp_api.api import Orders, CatalogItems, Sellers, Inventories
    from sp_api.base import Marketplaces, SellingApiException
    SP_API_AVAILABLE = True
except ImportError:
    SP_API_AVAILABLE = False
    logger.warning("python-amazon-sp-api not installed. Amazon adapter will have limited functionality.")


class AmazonAdapter(PlatformAdapter):
    """
    Amazon Selling Partner API adapter.

    Credentials format:
        {
            "marketplace_id": "ATVPDKIKX0DER",  # US marketplace
            "seller_id": "A1234567890123",
            "refresh_token": "Atzr|...",
            "client_id": "amzn1.application-oa2-client...",
            "client_secret": "...",
            "aws_access_key": "AKIA...",
            "aws_secret_key": "...",
            "region": "us-east-1"  # Optional, defaults based on marketplace
        }

    Example:
        >>> adapter = AmazonAdapter({
        ...     "marketplace_id": "ATVPDKIKX0DER",
        ...     "seller_id": "A1234567890123",
        ...     "refresh_token": "Atzr|...",
        ...     ...
        ... })
        >>> result = await adapter.test_connection()

    Note:
        Amazon SP-API requires both LWA (Login with Amazon) OAuth
        and AWS IAM credentials for Signature V4 authentication.
    """

    # Amazon SP-API rate limits (vary by endpoint)
    ORDERS_RATE_LIMIT = 0.0055  # ~200 requests per hour
    CATALOG_RATE_LIMIT = 0.1    # ~600 requests per hour

    # Marketplace endpoints
    MARKETPLACE_ENDPOINTS = {
        "ATVPDKIKX0DER": "https://sellingpartnerapi-na.amazon.com",  # US
        "A2EUQ1WTGCTBG2": "https://sellingpartnerapi-na.amazon.com",  # CA
        "A1AM78C64UM0Y8": "https://sellingpartnerapi-na.amazon.com",  # MX
        "A1PA6795UKMFR9": "https://sellingpartnerapi-eu.amazon.com",  # DE
        "A1RKKUPIHCS9HS": "https://sellingpartnerapi-eu.amazon.com",  # ES
        "A13V1IB3VIYZZH": "https://sellingpartnerapi-eu.amazon.com",  # FR
        "A1F83G8C2ARO7P": "https://sellingpartnerapi-eu.amazon.com",  # UK
        "APJ6JRA9NG5V4": "https://sellingpartnerapi-eu.amazon.com",   # IT
        "A39IBJ37TRP1C6": "https://sellingpartnerapi-fe.amazon.com",  # AU
        "A1VC38T7YXB528": "https://sellingpartnerapi-fe.amazon.com",  # JP
    }

    def __init__(self, credentials: dict):
        """
        Initialize Amazon SP-API adapter.

        Args:
            credentials: Dictionary with Amazon SP-API credentials
        """
        super().__init__(credentials)

        if not SP_API_AVAILABLE:
            logger.error(
                "python-amazon-sp-api library not installed. "
                "Install with: pip install python-amazon-sp-api"
            )

        self.platform_name = "amazon"
        self.api_version = "2021-06-30"  # Catalog Items API version

        # Extract credentials
        self.marketplace_id = credentials.get("marketplace_id", "")
        self.seller_id = credentials.get("seller_id", "")
        self.refresh_token = credentials.get("refresh_token", "")
        self.client_id = credentials.get("client_id", "")
        self.client_secret = credentials.get("client_secret", "")
        self.aws_access_key = credentials.get("aws_access_key", "")
        self.aws_secret_key = credentials.get("aws_secret_key", "")
        self.region = credentials.get("region", "us-east-1")

        # Validate required credentials
        required = [
            "marketplace_id", "seller_id", "refresh_token",
            "client_id", "client_secret", "aws_access_key", "aws_secret_key"
        ]
        missing = [field for field in required if not credentials.get(field)]

        if missing:
            raise AuthenticationError(
                f"Missing Amazon SP-API credentials: {', '.join(missing)}",
                platform="amazon"
            )

        # Set base URL based on marketplace
        self.base_url = self.MARKETPLACE_ENDPOINTS.get(
            self.marketplace_id,
            "https://sellingpartnerapi-na.amazon.com"
        )

        # Initialize SP-API clients if library is available
        if SP_API_AVAILABLE:
            try:
                self._init_sp_api_clients()
            except Exception as e:
                logger.error(f"Failed to initialize SP-API clients: {e}")
                self._clients_initialized = False
        else:
            self._clients_initialized = False

        logger.info(f"Initialized Amazon adapter for marketplace {self.marketplace_id}")

    def _init_sp_api_clients(self):
        """Initialize SP-API client instances"""
        if not SP_API_AVAILABLE:
            return

        # Common credentials for all clients
        credentials_dict = dict(
            refresh_token=self.refresh_token,
            lwa_app_id=self.client_id,
            lwa_client_secret=self.client_secret,
            aws_access_key=self.aws_access_key,
            aws_secret_key=self.aws_secret_key
        )

        try:
            # Get marketplace enum
            marketplace = self._get_marketplace_enum()

            # Initialize API clients
            self.orders_client = Orders(
                credentials=credentials_dict,
                marketplace=marketplace
            )

            self.catalog_client = CatalogItems(
                credentials=credentials_dict,
                marketplace=marketplace
            )

            self.sellers_client = Sellers(
                credentials=credentials_dict,
                marketplace=marketplace
            )

            # Note: Inventories API might not be available in all versions
            try:
                self.inventory_client = Inventories(
                    credentials=credentials_dict,
                    marketplace=marketplace
                )
            except Exception:
                logger.warning("Inventories API client not available")
                self.inventory_client = None

            self._clients_initialized = True
            logger.info("SP-API clients initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize SP-API clients: {e}")
            self._clients_initialized = False

    def _get_marketplace_enum(self):
        """Get marketplace enum from sp-api library"""
        if not SP_API_AVAILABLE:
            return None

        # Map marketplace IDs to sp-api Marketplaces enum
        marketplace_map = {
            "ATVPDKIKX0DER": Marketplaces.US,
            "A2EUQ1WTGCTBG2": Marketplaces.CA,
            "A1AM78C64UM0Y8": Marketplaces.MX,
            "A1PA6795UKMFR9": Marketplaces.DE,
            "A1RKKUPIHCS9HS": Marketplaces.ES,
            "A13V1IB3VIYZZH": Marketplaces.FR,
            "A1F83G8C2ARO7P": Marketplaces.UK,
            "APJ6JRA9NG5V4": Marketplaces.IT,
            "A39IBJ37TRP1C6": Marketplaces.AU,
            "A1VC38T7YXB528": Marketplaces.JP,
        }

        return marketplace_map.get(self.marketplace_id, Marketplaces.US)

    async def _handle_sp_api_error(self, error: Exception, context: str) -> dict:
        """
        Handle SP-API specific errors.

        Args:
            error: Exception from SP-API
            context: Context string for logging

        Returns:
            Standardized error response
        """
        if not SP_API_AVAILABLE:
            return self.build_error_response(error, context)

        if isinstance(error, SellingApiException):
            # Check for rate limiting
            if error.code == 429 or "QuotaExceeded" in str(error):
                raise RateLimitError(
                    "Amazon SP-API rate limit exceeded",
                    platform="amazon",
                    retry_after=60  # Amazon typically requires 60s wait
                )

            # Check for authentication errors
            if error.code == 401 or error.code == 403:
                raise AuthenticationError(
                    f"Amazon SP-API authentication failed: {error}",
                    platform="amazon"
                )

            # Check for not found
            if error.code == 404:
                raise ProductNotFoundError(
                    "Resource not found",
                    platform="amazon"
                )

        return self.build_error_response(error, context)

    # ========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ========================================================================

    async def test_connection(self) -> dict:
        """
        Test Amazon SP-API credentials.

        Returns:
            {
                "success": True,
                "store_name": "My Amazon Store",
                "store_url": "amazon.com",
                "platform_version": "SP-API"
            }
        """
        if not self._clients_initialized:
            return {
                "success": False,
                "error": "SP-API clients not initialized. Check credentials and library installation."
            }

        try:
            # Get marketplace participations
            response = self.sellers_client.get_marketplace_participations()

            self.track_request()

            # Extract marketplace info
            participations = response.payload.get("payload", [])

            if participations:
                marketplace = participations[0].get("marketplace", {})
                seller = participations[0].get("seller", {})

                return {
                    "success": True,
                    "store_name": seller.get("name", "Amazon Seller"),
                    "store_url": marketplace.get("domainName", "amazon.com"),
                    "platform_version": "SP-API",
                    "marketplace_id": marketplace.get("id", self.marketplace_id),
                    "seller_id": self.seller_id
                }
            else:
                return {
                    "success": False,
                    "error": "No marketplace participations found"
                }

        except Exception as e:
            return await self._handle_sp_api_error(e, "test_connection")

    async def deploy_product(self, product: dict) -> dict:
        """
        Deploy product to Amazon.

        NOTE: Amazon product creation is complex and requires:
        - Product type definition
        - Category-specific attributes
        - Brand approval
        - UPC/EAN codes

        For MVP, this is a simplified implementation.
        Full implementation requires Amazon Brand Registry and product type schemas.

        Args:
            product: Standard product format

        Returns:
            {
                "success": True/False,
                "platform_product_id": "ASIN" (if successful),
                "platform_url": "amazon.com/dp/ASIN",
                "error": "..." (if failed),
                "note": "Amazon product creation requires additional setup"
            }
        """
        # TODO: Implement full product creation with product type definitions
        # This requires:
        # 1. Product type selection (e.g., "PRODUCT", "SHIRT", "SHOES")
        # 2. Category-specific attributes
        # 3. Brand approval through Amazon Brand Registry
        # 4. UPC/EAN/ISBN codes
        # 5. Compliance with Amazon listing policies

        return {
            "success": False,
            "error": "Amazon product creation not yet implemented",
            "note": (
                "Amazon product creation requires:\n"
                "1. Product type definition and attributes\n"
                "2. Brand approval (Amazon Brand Registry)\n"
                "3. UPC/EAN codes\n"
                "4. Category approval\n"
                "\n"
                "For now, use Amazon Seller Central to create listings manually,\n"
                "then use this adapter for inventory and order management."
            ),
            "alternative": "Use update_inventory() to manage existing listings"
        }

    async def update_product(
        self,
        platform_product_id: str,
        updates: dict
    ) -> dict:
        """
        Update existing Amazon listing.

        NOTE: For MVP, this focuses on price and inventory updates.
        Full implementation would use Listings Items API.

        Args:
            platform_product_id: Amazon ASIN
            updates: Fields to update (price, inventory mainly)

        Returns:
            {
                "success": True,
                "updated_fields": ["price", "inventory"]
            }
        """
        try:
            updated_fields = []

            # For MVP, inventory updates go through update_inventory()
            if "inventory" in updates:
                result = await self.update_inventory(
                    platform_product_id,
                    updates["inventory"]
                )
                if result.get("success"):
                    updated_fields.append("inventory")

            # TODO: Implement price updates via Listings Items API
            # This requires:
            # - Listings Items API (PUT /listings/2021-08-01/items/{sellerId}/{sku})
            # - SKU (not just ASIN)
            # - Proper price structure with currency

            if "price" in updates:
                logger.warning(
                    f"Price updates not yet implemented for Amazon. "
                    f"Use Seller Central to update price for ASIN {platform_product_id}"
                )
                # Don't add to updated_fields since we didn't actually update it

            return {
                "success": len(updated_fields) > 0,
                "updated_fields": updated_fields,
                "note": "Full product updates require Listings Items API implementation"
            }

        except Exception as e:
            return await self._handle_sp_api_error(e, "update_product")

    async def delete_product(self, platform_product_id: str) -> dict:
        """
        Delete/archive Amazon listing.

        NOTE: Amazon doesn't allow permanent deletion of listings.
        Instead, we set inventory to 0 to make it unavailable.

        Args:
            platform_product_id: Amazon ASIN

        Returns:
            {
                "success": True,
                "archived": True  # Amazon doesn't delete, only archives
            }
        """
        try:
            # Set inventory to 0 to make unavailable
            result = await self.update_inventory(platform_product_id, 0)

            if result.get("success"):
                return {
                    "success": True,
                    "archived": True,  # Amazon archives, doesn't delete
                    "note": "Amazon listings are archived (inventory set to 0), not permanently deleted"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to archive listing")
                }

        except Exception as e:
            return await self._handle_sp_api_error(e, "delete_product")

    async def get_orders(
        self,
        limit: int = 50,
        status: str = "any",
        since: Optional[datetime] = None
    ) -> dict:
        """
        Fetch orders from Amazon.

        Args:
            limit: Max orders to fetch (max 100 per request)
            status: "any", "pending", "shipped", "cancelled"
            since: Only orders created after this datetime

        Returns:
            {
                "success": True,
                "orders": [...],
                "total_count": 42,
                "has_more": False
            }
        """
        if not self._clients_initialized:
            return {
                "success": False,
                "error": "SP-API clients not initialized"
            }

        try:
            # Default to last 30 days if not specified
            if not since:
                since = datetime.now(timezone.utc) - timedelta(days=30)

            # Map status to Amazon order statuses
            order_statuses = []
            if status == "pending":
                order_statuses = ["Pending", "Unshipped", "PartiallyShipped"]
            elif status == "fulfilled":
                order_statuses = ["Shipped"]
            elif status == "cancelled":
                order_statuses = ["Canceled"]
            else:
                # "any" - don't filter by status
                pass

            # Fetch orders
            params = {
                "CreatedAfter": since.isoformat(),
                "MaxResultsPerPage": min(limit, 100)  # Amazon max is 100
            }

            if order_statuses:
                params["OrderStatuses"] = order_statuses

            response = self.orders_client.get_orders(**params)

            self.track_request()
            await asyncio.sleep(self.ORDERS_RATE_LIMIT)  # Rate limiting

            # Extract orders
            orders_data = response.payload.get("payload", {}).get("Orders", [])

            # Normalize orders
            normalized_orders = []
            for order in orders_data:
                normalized = self.normalize_order(order)
                normalized_orders.append(normalized)

            return {
                "success": True,
                "orders": normalized_orders,
                "total_count": len(normalized_orders),
                "has_more": len(normalized_orders) >= limit
            }

        except Exception as e:
            return await self._handle_sp_api_error(e, "get_orders")

    async def get_products(
        self,
        limit: int = 50,
        published_status: str = "published"
    ) -> dict:
        """
        Fetch products from Amazon.

        NOTE: Amazon doesn't have a simple "list all products" endpoint.
        This would require:
        - Inventory Reports API (generate and download report)
        - Or Listings Items API (requires SKU list)

        For MVP, returning empty list with guidance.

        Args:
            limit: Max products to fetch
            published_status: "published", "unpublished", "any"

        Returns:
            {
                "success": False,
                "error": "Not implemented",
                "note": "Use Amazon Inventory Reports or Listings Items API"
            }
        """
        # TODO: Implement via Inventory Reports API
        # This requires:
        # 1. Request report generation (POST /reports/2021-06-30/reports)
        # 2. Wait for report completion
        # 3. Download and parse report
        # 4. Return normalized products

        return {
            "success": False,
            "error": "Product listing not yet implemented for Amazon",
            "note": (
                "Amazon product listing requires Reports API:\n"
                "1. Generate inventory report\n"
                "2. Wait for processing\n"
                "3. Download and parse CSV\n"
                "\n"
                "For now, use Amazon Seller Central to view products."
            ),
            "products": [],
            "total_count": 0,
            "has_more": False
        }

    async def update_inventory(
        self,
        platform_product_id: str,
        quantity: int,
        location_id: Optional[str] = None
    ) -> dict:
        """
        Update Amazon inventory.

        NOTE: This is simplified for MVP.
        Full implementation depends on fulfillment method (FBA vs FBM).

        Args:
            platform_product_id: Amazon ASIN or SKU
            quantity: New inventory quantity
            location_id: Not used for Amazon (single inventory)

        Returns:
            {
                "success": True,
                "new_quantity": 75,
                "note": "For FBA, inventory is managed by Amazon"
            }
        """
        # TODO: Implement via FBA Inventory API or Listings Items API
        # This requires:
        # - For FBA: Use FBA Inventory API (inventory managed by Amazon)
        # - For FBM: Use Listings Items API to update quantity
        # - Need to know SKU (not just ASIN)

        return {
            "success": False,
            "error": "Inventory updates not yet implemented for Amazon",
            "note": (
                "Amazon inventory updates require:\n"
                "1. For FBA: FBA Inventory API (inventory at Amazon warehouses)\n"
                "2. For FBM: Listings Items API (seller-fulfilled)\n"
                "3. SKU (not just ASIN)\n"
                "\n"
                "For now, use Amazon Seller Central to manage inventory."
            ),
            "new_quantity": quantity,  # Placeholder
            "warning": "Inventory not actually updated - use Seller Central"
        }

    async def sync_orders(
        self,
        since: Optional[datetime] = None
    ) -> dict:
        """
        Sync recent orders from Amazon and calculate metrics.

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

            sync_time = datetime.now(timezone.utc).isoformat()

            logger.info(
                f"Synced {len(orders)} Amazon orders. "
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
                    "total_orders": len(orders)
                }
            }

        except Exception as e:
            return await self._handle_sp_api_error(e, "sync_orders")

    async def get_store_info(self) -> dict:
        """
        Get Amazon seller and marketplace information.

        Returns:
            {
                "success": True,
                "store_name": "My Amazon Store",
                "store_url": "amazon.com",
                "email": "seller@example.com",
                "currency": "USD",
                "domain": "amazon.com",
                "plan": "Professional",
                "country": "US",
                "marketplace_id": "ATVPDKIKX0DER"
            }
        """
        if not self._clients_initialized:
            return {
                "success": False,
                "error": "SP-API clients not initialized"
            }

        try:
            # Get marketplace participations
            response = self.sellers_client.get_marketplace_participations()

            self.track_request()

            participations = response.payload.get("payload", [])

            if participations:
                participation = participations[0]
                marketplace = participation.get("marketplace", {})
                seller = participation.get("seller", {})

                # Map marketplace ID to country
                marketplace_countries = {
                    "ATVPDKIKX0DER": "US",
                    "A2EUQ1WTGCTBG2": "CA",
                    "A1AM78C64UM0Y8": "MX",
                    "A1PA6795UKMFR9": "DE",
                    "A1RKKUPIHCS9HS": "ES",
                    "A13V1IB3VIYZZH": "FR",
                    "A1F83G8C2ARO7P": "UK",
                    "APJ6JRA9NG5V4": "IT",
                    "A39IBJ37TRP1C6": "AU",
                    "A1VC38T7YXB528": "JP",
                }

                marketplace_id = marketplace.get("id", self.marketplace_id)

                return {
                    "success": True,
                    "store_name": seller.get("name", "Amazon Seller"),
                    "store_url": marketplace.get("domainName", "amazon.com"),
                    "email": "",  # Not provided by SP-API
                    "currency": marketplace.get("defaultCurrencyCode", "USD"),
                    "domain": marketplace.get("domainName", "amazon.com"),
                    "plan": "Professional" if participation.get("hasSellerAccount") else "Individual",
                    "country": marketplace_countries.get(marketplace_id, "US"),
                    "timezone": marketplace.get("defaultLanguageCode", "en_US"),
                    "enabled": participation.get("isParticipating", True),
                    "marketplace_id": marketplace_id,
                    "seller_id": self.seller_id
                }
            else:
                return {
                    "success": False,
                    "error": "No marketplace participations found"
                }

        except Exception as e:
            return await self._handle_sp_api_error(e, "get_store_info")

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def normalize_product(self, amazon_product: dict) -> dict:
        """
        Convert Amazon product format to standard format.

        NOTE: Amazon product structure varies by API.
        This is a simplified version.

        Args:
            amazon_product: Product in Amazon format

        Returns:
            Product in standard format
        """
        # Amazon product structure varies significantly
        # This is a placeholder implementation

        return {
            "platform_product_id": amazon_product.get("asin", ""),
            "title": amazon_product.get("itemName", ""),
            "description": amazon_product.get("itemDescription", ""),
            "price": float(amazon_product.get("price", {}).get("amount", 0)),
            "sku": amazon_product.get("sellerSku", ""),
            "inventory": amazon_product.get("quantity", 0),
            "images": amazon_product.get("imageUrl", []) if isinstance(amazon_product.get("imageUrl"), list) else [amazon_product.get("imageUrl", "")],
            "tags": [],  # Amazon doesn't have tags like Shopify
            "vendor": amazon_product.get("brand", ""),
            "product_type": amazon_product.get("productType", ""),
            "status": "active" if amazon_product.get("status") == "Active" else "inactive",
            "created_at": amazon_product.get("openDate", ""),
            "updated_at": ""
        }

    def normalize_order(self, amazon_order: dict) -> dict:
        """
        Convert Amazon order format to standard format.

        Args:
            amazon_order: Order in Amazon SP-API format

        Returns:
            Order in standard format
        """
        # Extract line items (if available)
        line_items = []
        # Note: Line items require separate API call in SP-API
        # For now, leaving empty - would need to fetch via get_order_items()

        # Extract shipping address
        shipping_address = amazon_order.get("ShippingAddress", {})

        # Calculate prices
        total = amazon_order.get("OrderTotal", {})
        total_price = float(total.get("Amount", 0))

        return {
            "platform_order_id": amazon_order.get("AmazonOrderId", ""),
            "order_number": amazon_order.get("AmazonOrderId", ""),
            "customer_email": amazon_order.get("BuyerEmail", ""),
            "customer_name": amazon_order.get("BuyerName", ""),
            "total_price": total_price,
            "subtotal_price": total_price,  # Amazon doesn't break down clearly
            "tax_price": 0.0,  # Would need order items for tax breakdown
            "shipping_price": 0.0,  # Would need order items
            "currency": total.get("CurrencyCode", "USD"),
            "status": amazon_order.get("OrderStatus", ""),
            "financial_status": amazon_order.get("PaymentMethod", ""),
            "fulfillment_status": amazon_order.get("FulfillmentChannel", ""),
            "created_at": amazon_order.get("PurchaseDate", ""),
            "updated_at": amazon_order.get("LastUpdateDate", ""),
            "line_items": line_items,  # Would need separate API call
            "shipping_address": {
                "name": shipping_address.get("Name", ""),
                "address1": shipping_address.get("AddressLine1", ""),
                "address2": shipping_address.get("AddressLine2", ""),
                "city": shipping_address.get("City", ""),
                "province": shipping_address.get("StateOrRegion", ""),
                "country": shipping_address.get("CountryCode", ""),
                "zip": shipping_address.get("PostalCode", "")
            },
            "billing_address": {},  # Amazon doesn't provide billing address via API
            "tracking_number": "",  # Would need shipment info
            "tracking_url": ""
        }
