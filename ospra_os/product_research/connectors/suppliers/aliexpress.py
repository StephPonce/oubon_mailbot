"""AliExpress connector for product sourcing."""

from typing import List, Optional
import hashlib
import hmac
import time
import requests
import asyncio
from ..base import BaseConnector, ProductCandidate


class AliExpressConnector(BaseConnector):
    """
    AliExpress integration for dropshipping product sourcing.

    Use AliExpress Open Platform API to:
    - Search products by keyword/category
    - Get product details (price, rating, shipping)
    - Find trending/hot products
    - Track supplier performance

    Setup:
    1. Register at https://portals.aliexpress.com/
    2. Get API key and App Secret
    3. Set ALIEXPRESS_API_KEY, ALIEXPRESS_APP_SECRET in .env

    Note: Can also use unofficial scraping as fallback (slower, less reliable)
    """

    def __init__(self, api_key: Optional[str] = None, app_secret: Optional[str] = None):
        super().__init__(api_key)
        self.app_secret = app_secret
        self.api_url = "https://api-sg.aliexpress.com/sync"

    @property
    def name(self) -> str:
        return "AliExpress"

    @property
    def source_id(self) -> str:
        return "aliexpress"

    def is_available(self) -> bool:
        """Check if both API key and secret are configured."""
        return bool(self.api_key and self.app_secret)

    def _generate_signature(self, params: dict) -> str:
        """Generate HMAC-SHA256 signature for API request."""
        # Sort parameters alphabetically
        sorted_params = sorted(params.items())

        # Build string to sign
        sign_string = "".join([f"{k}{v}" for k, v in sorted_params])

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()

        return signature

    async def search(self, query: str, **kwargs) -> List[ProductCandidate]:
        """
        Search AliExpress products.

        Args:
            query: Product keyword or category
            min_price: Min price filter (USD)
            max_price: Max price filter (USD)
            min_rating: Min seller rating (0-5)
            ship_from: Shipping location (default: 'CN')
            sort: 'price_asc', 'price_desc', 'orders', 'rating'

        Returns:
            Product candidates with pricing and supplier info
        """
        if not self.is_available():
            print("⚠️  AliExpress API credentials not configured")
            return []

        min_price = kwargs.get("min_price", 0)
        max_price = kwargs.get("max_price", 1000)
        min_rating = kwargs.get("min_rating", 4.0)
        sort = kwargs.get("sort", "orders")

        # Build API parameters
        params = {
            "app_key": self.api_key,
            "method": "aliexpress.affiliate.product.query",
            "timestamp": str(int(time.time() * 1000)),
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "keywords": query,
            "target_currency": "USD",
            "target_language": "EN",
            "page_size": "20",
        }

        # Add optional filters
        if min_price > 0:
            params["min_price"] = str(min_price)
        if max_price < 1000:
            params["max_price"] = str(max_price)

        # Generate signature
        params["sign"] = self._generate_signature(params)

        try:
            # Make async request
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(self.api_url, params=params, timeout=10)
            )

            if response.status_code != 200:
                print(f"❌ AliExpress API error: {response.status_code} - {response.text}")
                return []

            data = response.json()

            # Debug: Print response structure
            print(f"🔍 AliExpress API response keys: {list(data.keys())}")

            # Check for API errors
            if "error_response" in data:
                error = data["error_response"]
                print(f"❌ AliExpress API error: {error.get('code')} - {error.get('msg')}")
                return []

            # Parse response and convert to ProductCandidates
            products = []
            resp_result = data.get("aliexpress_affiliate_product_query_response", {})
            result = resp_result.get("resp_result", {})

            # Handle both nested and flat product list structures
            if isinstance(result.get("products"), dict):
                product_list = result.get("products", {}).get("product", [])
            else:
                product_list = result.get("products", [])

            for item in product_list:
                product = ProductCandidate(
                    name=item.get("product_title", "Unknown"),
                    source=self.source_id,
                    price=float(item.get("target_sale_price", 0)),
                    url=item.get("promotion_link", item.get("product_detail_url", "")),
                    image_url=item.get("product_main_image_url", ""),
                    supplier_rating=float(item.get("evaluate_rate", 0)) / 20.0,  # Convert 0-100 to 0-5
                    search_volume=int(item.get("volume", 0)),  # Use orders as search volume proxy
                    category=item.get("second_level_category_name", item.get("first_level_category_name")),
                )
                products.append(product)

            print(f"✅ AliExpress search: Found {len(products)} products for '{query}'")
            return products

        except Exception as e:
            print(f"❌ AliExpress search error: {e}")
            return []

    async def get_trending(self, category: Optional[str] = None, limit: int = 10) -> List[ProductCandidate]:
        """
        Get trending/hot products on AliExpress.

        Args:
            category: Product category ID or name
            limit: Max results

        Returns:
            Trending products with high order volume
        """
        if not self.is_available():
            print("⚠️  AliExpress API credentials not configured")
            return []

        # Build API parameters for hot products
        params = {
            "app_key": self.api_key,
            "method": "aliexpress.affiliate.hotproduct.query",
            "timestamp": str(int(time.time() * 1000)),
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "target_currency": "USD",
            "target_language": "EN",
            "page_size": str(limit),
            "sort": "SALE_PRICE_ASC",  # Sort by sales volume
        }

        # Add category filter if provided
        if category:
            params["category_ids"] = category

        # Generate signature
        params["sign"] = self._generate_signature(params)

        try:
            # Make async request
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(self.api_url, params=params, timeout=10)
            )

            if response.status_code != 200:
                print(f"❌ AliExpress API error: {response.status_code} - {response.text}")
                return []

            data = response.json()

            # Debug: Print response structure
            print(f"🔍 AliExpress Hot Products API response keys: {list(data.keys())}")

            # Check for API errors
            if "error_response" in data:
                error = data["error_response"]
                print(f"❌ AliExpress API error: {error.get('code')} - {error.get('msg')}")
                return []

            # Parse response
            products = []
            resp_result = data.get("aliexpress_affiliate_hotproduct_query_response", {})
            result = resp_result.get("resp_result", {})

            # Handle both nested and flat product list structures
            if isinstance(result.get("products"), dict):
                product_list = result.get("products", {}).get("product", [])
            else:
                product_list = result.get("products", [])

            for item in product_list:
                product = ProductCandidate(
                    name=item.get("product_title", "Unknown"),
                    source=self.source_id,
                    price=float(item.get("target_sale_price", 0)),
                    url=item.get("promotion_link", item.get("product_detail_url", "")),
                    image_url=item.get("product_main_image_url", ""),
                    supplier_rating=float(item.get("evaluate_rate", 0)) / 20.0,  # Convert 0-100 to 0-5
                    search_volume=int(item.get("volume", 0)),  # Use orders as search volume proxy
                    category=item.get("second_level_category_name", item.get("first_level_category_name")),
                )
                products.append(product)

            print(f"✅ AliExpress trending: Found {len(products)} hot products")
            return products

        except Exception as e:
            print(f"❌ AliExpress trending error: {e}")
            return []

    async def get_product_details(self, product_id: str) -> dict:
        """
        Get detailed product information.

        Args:
            product_id: AliExpress product ID

        Returns:
            {
                "title": str,
                "price": float,
                "original_price": float,
                "discount": float,
                "rating": float,
                "orders": int,
                "shipping_cost": float,
                "shipping_time": str,
                "supplier_rating": float,
                "images": List[str],
                "variants": List[dict]
            }
        """
        if not self.api_key:
            return {}

        # TODO: Implement product details fetch
        # API endpoint: aliexpress.affiliate.productdetail.get
        # - Get complete product info
        # - Calculate potential margins
        # - Check shipping options

        return {}

    async def calculate_margin(self, product_price: float, sale_price: float, shipping_cost: float = 0) -> dict:
        """
        Calculate profit margin for a product.

        Returns:
            {
                "cost": float,
                "revenue": float,
                "profit": float,
                "margin_percent": float
            }
        """
        cost = product_price + shipping_cost
        revenue = sale_price
        profit = revenue - cost
        margin_percent = (profit / revenue * 100) if revenue > 0 else 0

        return {
            "cost": round(cost, 2),
            "revenue": round(revenue, 2),
            "profit": round(profit, 2),
            "margin_percent": round(margin_percent, 2),
        }
