"""
Shopify Inventory Sync - Fetch products and sales data from Shopify

Integrates with Shopify Admin API to get:
- Product inventory levels
- Sales order history
- Product costs and pricing
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import os

from ospra_os.platforms.shopify import ShopifyAdapter

logger = logging.getLogger(__name__)


class ShopifyInventorySync:
    """Sync inventory data from Shopify for forecasting"""

    def __init__(self):
        """Initialize Shopify sync with credentials from environment"""
        # Get Shopify credentials from environment
        store_domain = os.getenv("SHOPIFY_STORE_DOMAIN", "")
        access_token = os.getenv("SHOPIFY_ACCESS_TOKEN", "")

        if not store_domain or not access_token:
            logger.warning("Shopify credentials not found in environment")
            self.adapter = None
            return

        # Initialize Shopify adapter
        try:
            self.adapter = ShopifyAdapter({
                "store_domain": store_domain,
                "admin_api_token": access_token,
                "api_version": "2024-01"
            })
            logger.info("[SUCCESS] Shopify inventory sync initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Shopify adapter: {e}")
            self.adapter = None

    def is_available(self) -> bool:
        """Check if Shopify sync is available"""
        return self.adapter is not None

    async def get_products_with_inventory(self, limit: int = 50) -> List[Dict]:
        """
        Fetch products from Shopify with inventory data

        Args:
            limit: Max products to fetch

        Returns:
            List of product dictionaries with inventory data
        """
        if not self.adapter:
            logger.warning("Shopify adapter not available")
            return []

        try:
            # Fetch products from Shopify
            products_response = await self.adapter._make_request(
                "GET",
                "products.json",
                params={"limit": limit, "fields": "id,title,variants,vendor,product_type"}
            )

            products = products_response.get("products", [])
            logger.info(f"Fetched {len(products)} products from Shopify")

            # Transform to inventory format
            inventory_products = []
            for product in products:
                # Get first variant (most products have one variant)
                variant = product.get("variants", [{}])[0]

                inventory_products.append({
                    'product_id': str(product['id']),
                    'product_name': product['title'],
                    'sku': variant.get('sku', f"SHOP-{product['id']}"),
                    'current_stock': variant.get('inventory_quantity', 0),
                    'reserved': 0,  # Shopify doesn't expose this directly
                    'unit_cost': float(variant.get('price', 0)),
                    'unit_price': float(variant.get('price', 0)),
                    'lead_time_days': 14,  # Default lead time
                    'min_order_qty': 10,
                    'incoming_stock': 0,
                    'variant_id': variant.get('id'),
                    'inventory_item_id': variant.get('inventory_item_id')
                })

            return inventory_products

        except Exception as e:
            logger.error(f"Error fetching products from Shopify: {e}")
            return []

    async def get_sales_history(
        self,
        product_id: str,
        days: int = 90
    ) -> List[Dict]:
        """
        Fetch sales history for a product from Shopify orders

        Args:
            product_id: Shopify product ID
            days: Days of history to fetch

        Returns:
            List of sales records with date and quantity
        """
        if not self.adapter:
            logger.warning("Shopify adapter not available")
            return []

        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Fetch orders from Shopify
            orders_response = await self.adapter._make_request(
                "GET",
                "orders.json",
                params={
                    "status": "any",
                    "created_at_min": start_date.isoformat(),
                    "limit": 250,  # Max per page
                    "fields": "id,line_items,created_at"
                }
            )

            orders = orders_response.get("orders", [])
            logger.info(f"Fetched {len(orders)} orders from Shopify")

            # Extract sales for this product
            sales_history = []
            for order in orders:
                for line_item in order.get("line_items", []):
                    if str(line_item.get("product_id")) == str(product_id):
                        sales_history.append({
                            'created_at': order['created_at'],
                            'quantity': line_item.get('quantity', 1)
                        })

            logger.info(f"Found {len(sales_history)} sales records for product {product_id}")
            return sales_history

        except Exception as e:
            logger.error(f"Error fetching sales history from Shopify: {e}")
            return []

    async def get_inventory_levels(self, inventory_item_ids: List[str]) -> Dict[str, int]:
        """
        Get current inventory levels for multiple items

        Args:
            inventory_item_ids: List of Shopify inventory item IDs

        Returns:
            Dictionary mapping inventory_item_id to quantity
        """
        if not self.adapter:
            return {}

        try:
            # Fetch inventory levels
            levels_response = await self.adapter._make_request(
                "GET",
                "inventory_levels.json",
                params={
                    "inventory_item_ids": ",".join(inventory_item_ids),
                    "limit": 250
                }
            )

            levels = levels_response.get("inventory_levels", [])

            # Map to dictionary
            inventory_map = {}
            for level in levels:
                item_id = str(level.get("inventory_item_id"))
                quantity = level.get("available", 0)
                inventory_map[item_id] = quantity

            return inventory_map

        except Exception as e:
            logger.error(f"Error fetching inventory levels: {e}")
            return {}

    async def sync_all_products(self) -> List[Dict]:
        """
        Sync all products with their current inventory and sales history

        Returns:
            List of products ready for forecasting engine
        """
        if not self.adapter:
            logger.warning("Shopify sync not available, using mock data")
            return []

        try:
            # Get all products
            products = await self.get_products_with_inventory(limit=50)

            if not products:
                logger.warning("No products found in Shopify")
                return []

            # For each product, get sales history
            synced_products = []
            for product in products[:10]:  # Limit to 10 for performance
                product_id = product['product_id']

                # Get sales history
                sales_history = await self.get_sales_history(product_id, days=90)

                # Add to synced products
                synced_products.append({
                    'product_data': product,
                    'sales_history': sales_history
                })

            logger.info(f"[SUCCESS] Synced {len(synced_products)} products from Shopify")
            return synced_products

        except Exception as e:
            logger.error(f"Error syncing products: {e}")
            return []

    async def test_connection(self) -> Dict:
        """Test Shopify connection and return store info"""
        if not self.adapter:
            return {
                "success": False,
                "error": "Shopify adapter not available"
            }

        try:
            result = await self.adapter.test_connection()
            return {
                "success": True,
                "store_name": result.get("name", "Unknown"),
                "platform": "Shopify"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Global instance
_shopify_sync = None


def get_shopify_sync() -> ShopifyInventorySync:
    """Get or create global Shopify sync instance"""
    global _shopify_sync
    if _shopify_sync is None:
        _shopify_sync = ShopifyInventorySync()
    return _shopify_sync
