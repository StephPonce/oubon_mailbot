"""
CJ Dropshipping Integration
Async client for CJ Dropshipping API v2.0

Provides product discovery, pricing, and inventory management for dropshipping.
"""
import os
import asyncio
from typing import List, Dict, Optional
from dotenv import load_dotenv
import aiohttp

load_dotenv()

API_BASE = "https://developers.cjdropshipping.com/api2.0/v1"


class CJDropshippingClient:
    """Async client for CJ Dropshipping API"""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication"""
        return {
            "Content-Type": "application/json",
            "CJ-Access-Token": self.access_token
        }

    async def _ensure_session(self):
        """Ensure HTTP session exists"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def get_categories(self) -> Dict:
        """Get product categories from CJ - returns raw API response"""
        await self._ensure_session()

        url = f"{API_BASE}/product/getCategory"

        async with self.session.get(url, headers=self._get_headers()) as resp:
            data = await resp.json()
            return data

    async def search_products(
        self,
        query: str = "",
        keyword: str = "",
        page_num: int = 1,
        page_size: int = 20,
        category_id: Optional[str] = None
    ) -> Dict:
        """Search products by keyword or category - returns raw API response

        Args:
            query: Search keyword (alias: keyword)
            keyword: Search keyword (alias: query)
            page_num: Page number (default: 1)
            page_size: Results per page (minimum 10)
            category_id: Optional category filter
        """
        await self._ensure_session()

        url = f"{API_BASE}/product/list"

        # Accept both 'query' and 'keyword' parameters (keyword takes precedence)
        search_term = keyword or query

        params = {
            "pageNum": page_num,
            "pageSize": max(page_size, 10)  # Min pageSize is 10
        }

        if search_term:
            params["productNameEn"] = search_term

        if category_id:
            params["categoryId"] = category_id

        async with self.session.get(url, headers=self._get_headers(), params=params) as resp:
            data = await resp.json()
            return data

    async def get_product_details(self, product_id: str) -> Dict:
        """Get detailed product information"""
        await self._ensure_session()

        url = f"{API_BASE}/product/query"

        params = {"pid": product_id}

        async with self.session.get(url, headers=self._get_headers(), params=params) as resp:
            data = await resp.json()

            if data.get("result"):
                return data.get("data", {})
            else:
                raise Exception(f"CJ API error: {data.get('message')}")

    def _calculate_price(self, cost: float, margin: float = 2.5) -> float:
        """Calculate selling price from cost with margin"""
        return round(cost * margin, 2)

    def _parse_price(self, price_str) -> float:
        """Parse price, handling price ranges like '8.28 -- 13.25'"""
        try:
            # Convert to string first in case it's already a number
            price_str = str(price_str)

            # Check if it's a price range
            if '--' in price_str:
                # Take the lowest price from range
                price_str = price_str.split('--')[0].strip()

            return float(price_str)
        except (ValueError, AttributeError):
            # Return 0 if parsing fails
            return 0.0

    def _format_for_ospra(self, cj_product: Dict) -> Dict:
        """Convert CJ product format to Ospra dashboard format"""

        # Extract basic info
        product_id = cj_product.get("pid", "")
        name = cj_product.get("productNameEn", "Unknown Product")
        cost = self._parse_price(cj_product.get("sellPrice", 0))
        price = self._calculate_price(cost)

        # Get first variant info if available
        variants = cj_product.get("variants", [])
        ship_from = "CN"  # Default to China

        if variants and len(variants) > 0:
            first_variant = variants[0]
            ship_from = first_variant.get("shipFromCountryCode", "CN")

        # Get image
        image_url = cj_product.get("productImage", "")

        # Get shipping info
        shipping_info = cj_product.get("shippingInfo", {})
        estimated_days = shipping_info.get("deliveryTimeMin", 15)

        return {
            "id": product_id,
            "name": name,
            "cost": cost,
            "price": price,
            "margin": round((price - cost) / price * 100, 1),
            "ship_from": ship_from,
            "image": image_url,
            "supplier": "CJ Dropshipping",
            "shipping_days": estimated_days,
            "category": cj_product.get("categoryName", "General"),
            "url": f"https://cjdropshipping.com/product/{product_id}"
        }

    async def discover_products_for_ospra(
        self,
        max_products: int = 10,
        search_query: str = "smart home",
        category: Optional[str] = None
    ) -> List[Dict]:
        """
        Discover trending products formatted for Ospra dashboard

        Args:
            max_products: Maximum number of products to return
            search_query: Keyword to search for
            category: Category ID to filter by (optional)

        Returns:
            List of products formatted for Ospra dashboard
        """

        # Calculate pages needed (max 50 products per page)
        page_size = min(max_products, 50)
        num_pages = (max_products // page_size) + (1 if max_products % page_size else 0)

        all_products = []

        for page in range(1, num_pages + 1):
            try:
                response = await self.search_products(
                    query=search_query,
                    page_num=page,
                    page_size=page_size,
                    category_id=category
                )

                # Check if API call was successful
                if not response.get("result"):
                    print(f"[WARNING] API error on page {page}: {response.get('message')}")
                    continue

                # Extract product list from response
                data = response.get("data", {})
                products = data.get("list", [])

                # Format each product
                for product in products:
                    if len(all_products) >= max_products:
                        break

                    formatted = self._format_for_ospra(product)
                    all_products.append(formatted)

                if len(all_products) >= max_products:
                    break

            except Exception as e:
                print(f"[WARNING] Error fetching page {page}: {e}")
                continue

        return all_products[:max_products]

    async def get_product_variants(self, product_id: str) -> List[Dict]:
        """Get all variants for a product"""
        product = await self.get_product_details(product_id)
        return product.get("variants", [])

    async def check_inventory(self, variant_id: str) -> Dict:
        """Check inventory status for a variant"""
        await self._ensure_session()

        url = f"{API_BASE}/product/variant/queryByVid"

        params = {"vid": variant_id}

        async with self.session.get(url, headers=self._get_headers(), params=params) as resp:
            data = await resp.json()

            if data.get("result"):
                variant = data.get("data", {})
                return {
                    "in_stock": variant.get("vid") is not None,
                    "quantity": variant.get("stockQuantity", 0),
                    "variant_id": variant_id
                }
            else:
                raise Exception(f"CJ API error: {data.get('message')}")


def get_cj_client() -> CJDropshippingClient:
    """
    Factory function to create CJ Dropshipping client

    Loads credentials from environment variables:
    - CJ_ACCESS_TOKEN: Valid access token from CJ API

    Returns:
        Configured CJDropshippingClient instance

    Raises:
        ValueError: If CJ_ACCESS_TOKEN not found in environment
    """
    access_token = os.getenv("CJ_ACCESS_TOKEN")

    if not access_token:
        raise ValueError(
            "CJ_ACCESS_TOKEN not found in environment. "
            "Run: python3 get_cj_token.py --update-env"
        )

    return CJDropshippingClient(access_token)


# Convenience function for quick testing
async def test_connection():
    """Quick test to verify CJ API connection"""
    client = get_cj_client()

    try:
        print("[SEARCH] Testing CJ Dropshipping API connection...")

        # Test categories
        categories = await client.get_categories()
        print(f"[SUCCESS] Found {len(categories)} categories")

        # Test product search
        products = await client.discover_products_for_ospra(max_products=5)
        print(f"[SUCCESS] Found {len(products)} products")

        for p in products:
            print(f"   {p['name'][:40]:40} | ${p['cost']:6.2f} → ${p['price']:6.2f}")

        print("\n[SUCCESS] CJ API connection successful!")

    finally:
        await client.close()


if __name__ == "__main__":
    # Run quick test when executed directly
    asyncio.run(test_connection())
