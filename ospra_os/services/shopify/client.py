"""
Shopify API Client
==================

Handles all Shopify API interactions:
- Store info
- Products
- Orders
- Customers
- Inventory
- Analytics

Uses both REST Admin API and GraphQL Admin API.
"""

import os
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


class ShopifyClient:
    """
    Shopify API Client for store operations.
    
    Supports both direct API key access and OAuth token access.
    """
    
    def __init__(
        self,
        store_domain: str,
        access_token: str,
        api_version: str = "2025-01"
    ):
        """
        Initialize Shopify client.
        
        Args:
            store_domain: Store domain (e.g., 'mystore.myshopify.com')
            access_token: Shopify Admin API access token
            api_version: API version (default: 2025-01)
        """
        # Normalize domain
        self.store_domain = store_domain.replace("https://", "").replace("http://", "")
        if not self.store_domain.endswith(".myshopify.com"):
            self.store_domain = f"{self.store_domain}.myshopify.com"
        
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = f"https://{self.store_domain}/admin/api/{api_version}"
        self.graphql_url = f"https://{self.store_domain}/admin/api/{api_version}/graphql.json"
        
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }
    
    # =========================================================================
    # STORE INFO
    # =========================================================================
    
    async def get_shop(self) -> Dict[str, Any]:
        """Get store information."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/shop.json",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("shop", {})
    
    # =========================================================================
    # PRODUCTS
    # =========================================================================
    
    async def get_products(
        self,
        limit: int = 50,
        since_id: Optional[int] = None,
        status: str = "active",
        fields: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get products from the store.
        
        Args:
            limit: Number of products to fetch (max 250)
            since_id: Fetch products after this ID (pagination)
            status: Filter by status (active, archived, draft)
            fields: Comma-separated list of fields to include
        
        Returns:
            List of product dictionaries
        """
        params = {"limit": min(limit, 250), "status": status}
        if since_id:
            params["since_id"] = since_id
        if fields:
            params["fields"] = fields
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/products.json",
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("products", [])
    
    async def get_products_count(self, status: str = "active") -> int:
        """Get total count of products."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/products/count.json",
                headers=self.headers,
                params={"status": status},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("count", 0)
    
    async def get_product(self, product_id: int) -> Dict[str, Any]:
        """Get a single product by ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/products/{product_id}.json",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("product", {})
    
    async def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new product."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/products.json",
                headers=self.headers,
                json={"product": product_data},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("product", {})
    
    async def update_product(self, product_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing product."""
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/products/{product_id}.json",
                headers=self.headers,
                json={"product": product_data},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("product", {})
    
    async def delete_product(self, product_id: int) -> bool:
        """Delete a product."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/products/{product_id}.json",
                headers=self.headers,
                timeout=30.0
            )
            return response.status_code == 200
    
    # =========================================================================
    # ORDERS
    # =========================================================================
    
    async def get_orders(
        self,
        limit: int = 50,
        status: str = "any",
        financial_status: Optional[str] = None,
        fulfillment_status: Optional[str] = None,
        created_at_min: Optional[datetime] = None,
        created_at_max: Optional[datetime] = None,
        since_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get orders from the store.
        
        Args:
            limit: Number of orders to fetch (max 250)
            status: Order status (open, closed, cancelled, any)
            financial_status: Financial status filter
            fulfillment_status: Fulfillment status filter
            created_at_min: Orders created after this date
            created_at_max: Orders created before this date
            since_id: Fetch orders after this ID
        
        Returns:
            List of order dictionaries
        """
        params = {"limit": min(limit, 250), "status": status}
        if financial_status:
            params["financial_status"] = financial_status
        if fulfillment_status:
            params["fulfillment_status"] = fulfillment_status
        if created_at_min:
            params["created_at_min"] = created_at_min.isoformat()
        if created_at_max:
            params["created_at_max"] = created_at_max.isoformat()
        if since_id:
            params["since_id"] = since_id
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/orders.json",
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("orders", [])
    
    async def get_orders_count(
        self,
        status: str = "any",
        created_at_min: Optional[datetime] = None
    ) -> int:
        """Get total count of orders."""
        params = {"status": status}
        if created_at_min:
            params["created_at_min"] = created_at_min.isoformat()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/orders/count.json",
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("count", 0)
    
    async def get_order(self, order_id: int) -> Dict[str, Any]:
        """Get a single order by ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/orders/{order_id}.json",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("order", {})
    
    # =========================================================================
    # CUSTOMERS
    # =========================================================================
    
    async def get_customers(
        self,
        limit: int = 50,
        since_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get customers from the store."""
        params = {"limit": min(limit, 250)}
        if since_id:
            params["since_id"] = since_id
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/customers.json",
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("customers", [])
    
    async def get_customers_count(self) -> int:
        """Get total count of customers."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/customers/count.json",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("count", 0)
    
    # =========================================================================
    # INVENTORY
    # =========================================================================
    
    async def get_inventory_levels(
        self,
        inventory_item_ids: Optional[List[int]] = None,
        location_ids: Optional[List[int]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get inventory levels."""
        params = {"limit": min(limit, 250)}
        if inventory_item_ids:
            params["inventory_item_ids"] = ",".join(map(str, inventory_item_ids))
        if location_ids:
            params["location_ids"] = ",".join(map(str, location_ids))
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/inventory_levels.json",
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("inventory_levels", [])
    
    async def get_locations(self) -> List[Dict[str, Any]]:
        """Get store locations."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/locations.json",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("locations", [])
    
    # =========================================================================
    # ANALYTICS / REPORTS
    # =========================================================================
    
    async def get_sales_by_date(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate sales metrics over a period.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Dictionary with sales metrics
        """
        since = datetime.utcnow() - timedelta(days=days)
        orders = await self.get_orders(
            limit=250,
            status="any",
            created_at_min=since
        )
        
        total_revenue = 0.0
        total_orders = len(orders)
        total_items = 0
        
        for order in orders:
            total_revenue += float(order.get("total_price", 0))
            for item in order.get("line_items", []):
                total_items += item.get("quantity", 0)
        
        return {
            "period_days": days,
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "total_items": total_items,
            "average_order_value": round(total_revenue / total_orders, 2) if total_orders > 0 else 0,
            "orders_per_day": round(total_orders / days, 2) if days > 0 else 0,
            "revenue_per_day": round(total_revenue / days, 2) if days > 0 else 0,
        }
    
    # =========================================================================
    # GRAPHQL
    # =========================================================================
    
    async def graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query.
        
        Args:
            query: GraphQL query string
            variables: Query variables
        
        Returns:
            GraphQL response data
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.graphql_url,
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    # =========================================================================
    # FULFILLMENT
    # =========================================================================
    
    async def get_fulfillment_orders(
        self,
        order_id: int
    ) -> List[Dict[str, Any]]:
        """Get fulfillment orders for an order."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/orders/{order_id}/fulfillment_orders.json",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("fulfillment_orders", [])
    
    # =========================================================================
    # COLLECTIONS
    # =========================================================================
    
    async def get_collections(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get custom collections."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/custom_collections.json",
                headers=self.headers,
                params={"limit": min(limit, 250)},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("custom_collections", [])
    
    async def get_smart_collections(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get smart collections."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/smart_collections.json",
                headers=self.headers,
                params={"limit": min(limit, 250)},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("smart_collections", [])
    
    # =========================================================================
    # THEMES
    # =========================================================================
    
    async def get_themes(self) -> List[Dict[str, Any]]:
        """Get store themes."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/themes.json",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("themes", [])
    
    # =========================================================================
    # HEALTH CHECK
    # =========================================================================
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the API connection.
        
        Returns:
            Dictionary with connection status and store info
        """
        try:
            shop = await self.get_shop()
            return {
                "success": True,
                "store_name": shop.get("name"),
                "store_domain": shop.get("domain"),
                "myshopify_domain": shop.get("myshopify_domain"),
                "email": shop.get("email"),
                "currency": shop.get("currency"),
                "timezone": shop.get("iana_timezone"),
                "plan_name": shop.get("plan_name"),
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


def get_shopify_client_from_env() -> ShopifyClient:
    """
    Create a Shopify client from environment variables.
    
    Uses:
        SHOPIFY_STORE_DOMAIN
        SHOPIFY_ACCESS_TOKEN
        SHOPIFY_API_VERSION
    """
    return ShopifyClient(
        store_domain=os.getenv("SHOPIFY_STORE_DOMAIN", ""),
        access_token=os.getenv("SHOPIFY_ACCESS_TOKEN", ""),
        api_version=os.getenv("SHOPIFY_API_VERSION", "2025-01"),
    )
