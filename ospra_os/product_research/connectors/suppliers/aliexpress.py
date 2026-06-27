"""
AliExpress connector for product sourcing.

FIXED: Uses correct API endpoints for keyword search.
- Affiliate API (aliexpress.affiliate.product.query) for keyword search
- Dropshipping API (aliexpress.ds.recommend.feed.get) for hot products feed

IMPROVED: Added relevance filtering to prevent off-topic products.
- Category ID mapping for precise filtering
- Keyword relevance scoring
- Exclude irrelevant products (e.g., CarPlay for "smart home")

Author: OspraOS
Updated: February 2025
"""

from typing import List, Optional
import hashlib
import hmac
import time
import requests
import asyncio
import os
import re
from ..base import BaseConnector, ProductCandidate


# ============================================================================
# CATEGORY ID MAPPING - For more precise product filtering
# ============================================================================
ALIEXPRESS_CATEGORY_MAP = {
    "smart_home": "200003498",      # Smart Home category
    "smart home": "200003498",
    "home automation": "200003498",
    "kitchen": "100003070",         # Kitchen & Dining
    "kitchen gadgets": "100003070",
    "fitness": "200001557",         # Sports & Fitness
    "sports": "200001557",
    "beauty": "66",                 # Beauty & Health
    "electronics": "44",            # Consumer Electronics
    "tech": "44",
    "pet": "200001886",             # Pet Supplies
    "pet supplies": "200001886",
    "automotive": "34",             # Automobiles & Motorcycles
    "car": "34",
    "phone": "509",                 # Phones & Telecommunications
    "phone accessories": "509",
}

# ============================================================================
# RELEVANCE KEYWORDS - Include/Exclude for filtering off-topic products
# ============================================================================
RELEVANCE_FILTERS = {
    "smart_home": {
        "include": ["smart", "wifi", "wireless", "alexa", "home", "automation", "sensor",
                   "plug", "bulb", "light", "switch", "thermostat", "camera", "doorbell",
                   "lock", "security", "motion", "zigbee", "z-wave"],
        "exclude": ["carplay", "car play", "android auto", "car stereo", "car radio",
                   "car screen", "car display", "car dvd", "car navigation", "car gps",
                   "car holder", "car mount", "phone holder car", "windshield"],
    },
    "smart home": {
        "include": ["smart", "wifi", "wireless", "alexa", "home", "automation", "sensor",
                   "plug", "bulb", "light", "switch", "thermostat", "camera", "doorbell",
                   "lock", "security", "motion", "zigbee", "z-wave"],
        "exclude": ["carplay", "car play", "android auto", "car stereo", "car radio",
                   "car screen", "car display", "car dvd", "car navigation", "car gps",
                   "car holder", "car mount", "phone holder car", "windshield"],
    },
    "kitchen": {
        "include": ["kitchen", "cooking", "chef", "food", "blender", "mixer", "knife",
                   "pot", "pan", "utensil", "container", "storage", "gadget", "appliance"],
        "exclude": ["car", "automotive", "phone case", "laptop", "computer"],
    },
    "fitness": {
        "include": ["fitness", "gym", "workout", "exercise", "yoga", "sport", "training",
                   "resistance", "band", "weight", "dumbbell", "mat", "tracker"],
        "exclude": ["car", "carplay", "phone case", "laptop"],
    },
    "beauty": {
        "include": ["beauty", "skin", "face", "hair", "makeup", "cosmetic", "nail",
                   "brush", "cream", "serum", "mask"],
        "exclude": ["car", "carplay", "laptop", "phone case"],
    },
}


class AliExpressConnector(BaseConnector):
    """
    AliExpress integration for dropshipping product sourcing.

    APIs Used:
    - Affiliate API: For keyword product search (better for discovery)
    - Dropshipping API: For hot products feeds and order management

    Setup:
    1. Register at https://portals.aliexpress.com/
    2. Get API credentials for both Affiliate and Dropshipping APIs
    3. Set environment variables in .env
    """

    def __init__(
        self, 
        api_key: Optional[str] = None, 
        app_secret: Optional[str] = None, 
        access_token: Optional[str] = None,
        affiliate_app_key: Optional[str] = None,
        affiliate_app_secret: Optional[str] = None
    ):
        # Primary: Dropshipping API credentials
        self.api_key = api_key or os.getenv('ALIEXPRESS_APP_KEY')
        self.app_secret = app_secret or os.getenv('ALIEXPRESS_APP_SECRET')
        self.access_token = access_token or os.getenv('ALIEXPRESS_ACCESS_TOKEN')
        
        # Secondary: Affiliate API credentials (better for search)
        self.affiliate_app_key = affiliate_app_key or os.getenv('ALIEXPRESS_AFFILIATE_APP_KEY') or self.api_key
        self.affiliate_app_secret = affiliate_app_secret or os.getenv('ALIEXPRESS_AFFILIATE_APP_SECRET') or self.app_secret
        
        self.api_url = "https://api-sg.aliexpress.com/sync"
        
        super().__init__(self.api_key)

    @property
    def name(self) -> str:
        return "AliExpress"

    @property
    def source_id(self) -> str:
        return "aliexpress"

    def is_available(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.api_key and self.app_secret)

    def _generate_signature(self, params: dict, secret: str = None) -> str:
        """Generate HMAC-SHA256 signature for API request."""
        secret = secret or self.app_secret
        
        # Sort parameters alphabetically
        sorted_params = sorted(params.items())

        # Build string to sign
        sign_string = "".join([f"{k}{v}" for k, v in sorted_params])

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()

        return signature

    async def search(self, query: str, **kwargs) -> List[ProductCandidate]:
        """
        Search AliExpress products by keyword.

        Uses Affiliate API for keyword search (most reliable for discovery).
        Falls back to Dropshipping feed if Affiliate fails.

        IMPROVED: Filters results for relevance to prevent off-topic products.

        Args:
            query: Product keyword or category
            min_price: Min price filter (USD)
            max_price: Max price filter (USD)
            min_rating: Min seller rating (0-5)
            sort: 'price_asc', 'price_desc', 'orders', 'rating'
            filter_relevance: Enable relevance filtering (default: True)
            niche: Niche for relevance filtering (auto-detected if not provided)

        Returns:
            Product candidates with pricing and supplier info
        """
        if not self.is_available():
            print("[WARNING]  AliExpress API credentials not configured")
            return []

        # Get category ID if available for more precise results
        category_id = ALIEXPRESS_CATEGORY_MAP.get(query.lower())
        if category_id:
            kwargs['category_ids'] = category_id
            print(f"[FILTER] Using category ID {category_id} for '{query}'")

        # Try Affiliate API first (supports keyword search)
        products = await self._search_affiliate(query, **kwargs)

        if not products:
            # Fallback to Dropshipping feed (doesn't support keyword, but gets products)
            print("[WARNING]  Affiliate search returned 0, trying Dropshipping feed...")
            products = await self._get_feed_products(**kwargs)

        # Apply relevance filtering
        filter_relevance = kwargs.get('filter_relevance', True)
        if filter_relevance and products:
            niche = kwargs.get('niche', query.lower())
            original_count = len(products)
            products = self._filter_relevance(products, query, niche)
            filtered_count = original_count - len(products)
            if filtered_count > 0:
                print(f"[FILTER] Removed {filtered_count} off-topic products from '{query}' results")

        return products

    def _filter_relevance(self, products: List[ProductCandidate], query: str, niche: str) -> List[ProductCandidate]:
        """
        Filter products for relevance to the search query.

        Removes off-topic products (e.g., CarPlay adapters for "smart home" search).

        Args:
            products: List of products to filter
            query: Original search query
            niche: Niche category for filtering rules

        Returns:
            Filtered list of relevant products
        """
        # Get filter rules for this niche
        filters = RELEVANCE_FILTERS.get(niche.lower(), RELEVANCE_FILTERS.get(query.lower(), {}))

        if not filters:
            # No specific filters - do basic keyword matching
            return self._basic_relevance_filter(products, query)

        include_keywords = [kw.lower() for kw in filters.get('include', [])]
        exclude_keywords = [kw.lower() for kw in filters.get('exclude', [])]

        filtered = []
        for product in products:
            name_lower = product.name.lower()
            category_lower = (product.category or '').lower()

            # Check for exclusion keywords (instant reject)
            is_excluded = any(excl in name_lower for excl in exclude_keywords)
            if is_excluded:
                print(f"   [SKIP] Off-topic: {product.name[:50]}...")
                continue

            # Check for inclusion keywords (at least one must match)
            if include_keywords:
                has_include = any(incl in name_lower or incl in category_lower for incl in include_keywords)
                if not has_include:
                    # Give benefit of doubt to generic matches
                    query_words = query.lower().split()
                    has_query_match = any(word in name_lower for word in query_words if len(word) > 3)
                    if not has_query_match:
                        print(f"   [SKIP] Low relevance: {product.name[:50]}...")
                        continue

            filtered.append(product)

        return filtered

    def _basic_relevance_filter(self, products: List[ProductCandidate], query: str) -> List[ProductCandidate]:
        """
        Basic relevance filter when no specific rules exist.

        Checks if product name contains any word from the query (>3 chars).
        """
        query_words = [w.lower() for w in query.split() if len(w) > 3]

        if not query_words:
            return products

        filtered = []
        for product in products:
            name_lower = product.name.lower()

            # Check if ANY query word appears in product name
            has_match = any(word in name_lower for word in query_words)

            if has_match:
                filtered.append(product)
            else:
                print(f"   [SKIP] No query match: {product.name[:50]}...")

        return filtered

    async def _search_affiliate(self, query: str, **kwargs) -> List[ProductCandidate]:
        """
        Search using Affiliate API - supports keyword queries.
        
        API Method: aliexpress.affiliate.product.query
        """
        min_price = kwargs.get("min_price")
        max_price = kwargs.get("max_price")
        sort = kwargs.get("sort", "SALE_PRICE_ASC")
        page_size = kwargs.get("page_size", 20)
        
        # Map sort options
        sort_map = {
            "orders": "LAST_VOLUME_DESC",
            "price_asc": "SALE_PRICE_ASC", 
            "price_desc": "SALE_PRICE_DESC",
            "rating": "EVALUATE_RATE_DESC",
            "commission": "COMMISSION_RATE_DESC",
        }
        sort_param = sort_map.get(sort, sort)

        # Build API parameters for AFFILIATE PRODUCT QUERY
        params = {
            "app_key": self.affiliate_app_key,
            "method": "aliexpress.affiliate.product.query",
            "timestamp": str(int(time.time() * 1000)),
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            # tracking_id is MANDATORY for affiliate.product.query (#AE).
            "tracking_id": os.getenv("ALIEXPRESS_TRACKING_ID", ""),
            # Search parameters
            "keywords": query,
            "target_currency": "USD",
            "target_language": "EN",
            "ship_to_country": "US",
            "sort": sort_param,
            "page_size": str(page_size),
            "page_no": "1",
        }

        # Add optional filters
        if min_price is not None:
            params["min_sale_price"] = str(min_price)
        if max_price is not None:
            params["max_sale_price"] = str(max_price)

        # Add category filter if provided (improves relevance)
        category_ids = kwargs.get("category_ids")
        if category_ids:
            params["category_ids"] = str(category_ids)
            print(f"[FILTER] AliExpress API: category_ids={category_ids}")

        # Generate signature with affiliate secret
        params["sign"] = self._generate_signature(params, self.affiliate_app_secret)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(self.api_url, params=params, timeout=15)
            )

            if response.status_code != 200:
                print(f"[ERROR] AliExpress Affiliate API error: {response.status_code}")
                return []

            data = response.json()

            # Check for API errors
            if "error_response" in data:
                error = data["error_response"]
                error_code = error.get('code', 'unknown')
                error_msg = error.get('msg', 'Unknown error')
                print(f"[ERROR] AliExpress Affiliate API error {error_code}: {error_msg}")
                
                # Log sub-errors if present
                if 'sub_code' in error:
                    print(f"   Sub-code: {error.get('sub_code')} - {error.get('sub_msg', '')}")
                return []

            # Parse Affiliate API response
            products = []
            resp = data.get("aliexpress_affiliate_product_query_response", {})
            resp_result = resp.get("resp_result", {})
            result = resp_result.get("result", {})
            
            # Get products list
            product_list = result.get("products", {}).get("product", [])
            
            # Handle single product (API returns dict instead of list)
            if isinstance(product_list, dict):
                product_list = [product_list]
            
            print(f"[SEARCH] AliExpress Affiliate: Found {len(product_list)} products for '{query}'")

            for item in product_list:
                try:
                    # Extract price (handle both string and number)
                    price_str = item.get("target_sale_price", "0")
                    price = float(str(price_str).replace(",", ""))
                    
                    # Extract original price
                    orig_price_str = item.get("target_original_price", price_str)
                    orig_price = float(str(orig_price_str).replace(",", ""))
                    
                    product = ProductCandidate(
                        name=item.get("product_title", "Unknown"),
                        source=self.source_id,
                        price=price,
                        url=item.get("promotion_link", item.get("product_detail_url", "")),
                        image_url=item.get("product_main_image_url", ""),
                        supplier_rating=float(item.get("evaluate_rate", "0").replace("%", "")) / 100 * 5 if item.get("evaluate_rate") else 4.0,
                        search_volume=int(item.get("lastest_volume", 0)),  # Recent sales
                        category=item.get("second_level_category_name", item.get("first_level_category_name", "")),
                    )
                    
                    # Add extra metadata
                    product.original_price = orig_price
                    product.commission_rate = item.get("commission_rate", "0%")
                    product.product_id = item.get("product_id", "")
                    
                    products.append(product)
                except Exception as e:
                    print(f"   [WARNING] Error parsing product: {e}")
                    continue

            print(f"[SUCCESS] AliExpress Affiliate search: Parsed {len(products)} products")
            return products

        except Exception as e:
            print(f"[ERROR] AliExpress Affiliate search error: {e}")
            return []

    async def _get_feed_products(self, **kwargs) -> List[ProductCandidate]:
        """
        Get products from Dropshipping feed.
        
        API Method: aliexpress.ds.recommend.feed.get
        Note: This doesn't support keyword search, just returns feed products.
        """
        page_size = kwargs.get("page_size", 20)
        feed_name = kwargs.get("feed_name", "DS hot product")

        # Build API parameters for DROPSHIPPING FEED
        params = {
            "app_key": self.api_key,
            "method": "aliexpress.ds.recommend.feed.get",
            "timestamp": str(int(time.time() * 1000)),
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "session": self.access_token,
            "feed_name": feed_name,
            "country": "US",
            "target_currency": "USD",
            "target_language": "EN",
            "page_size": str(page_size),
            "page_no": "1",
        }

        # Generate signature
        params["sign"] = self._generate_signature(params)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(self.api_url, params=params, timeout=15)
            )

            if response.status_code != 200:
                print(f"[ERROR] AliExpress DS Feed API error: {response.status_code}")
                return []

            data = response.json()

            # Check for API errors
            if "error_response" in data:
                error = data["error_response"]
                print(f"[ERROR] AliExpress DS Feed error: {error.get('code')} - {error.get('msg')}")
                return []

            # Parse Dropshipping API response
            products = []
            resp_result = data.get("aliexpress_ds_recommend_feed_get_response", {})
            result = resp_result.get("resp_result", {}).get("result", {})

            # Handle nested product list
            product_list = result.get("products", {})
            if isinstance(product_list, dict):
                product_list = product_list.get("product", [])
            if isinstance(product_list, dict):
                product_list = [product_list]

            print(f"[SEARCH] AliExpress DS Feed: Found {len(product_list)} products")

            for item in product_list:
                try:
                    price = float(item.get("target_sale_price", 0))
                    
                    product = ProductCandidate(
                        name=item.get("product_title", "Unknown"),
                        source=self.source_id,
                        price=price,
                        url=item.get("promotion_link", item.get("product_detail_url", "")),
                        image_url=item.get("product_main_image_url", ""),
                        supplier_rating=float(item.get("evaluate_rate", 0)) / 20.0,
                        search_volume=int(item.get("volume", 0)),
                        category=item.get("second_level_category_name", item.get("first_level_category_name", "")),
                    )
                    products.append(product)
                except Exception as e:
                    print(f"   [WARNING] Error parsing product: {e}")
                    continue

            print(f"[SUCCESS] AliExpress DS Feed: Parsed {len(products)} products")
            return products

        except Exception as e:
            print(f"[ERROR] AliExpress DS Feed error: {e}")
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
        # Try bestseller feed
        products = await self._get_feed_products(
            page_size=limit,
            feed_name="DS bestseller"
        )
        
        if not products:
            # Fallback to hot products
            products = await self._get_feed_products(
                page_size=limit,
                feed_name="DS hot product"
            )
        
        return products

    async def search_by_category(self, category_id: str, **kwargs) -> List[ProductCandidate]:
        """
        Search products by category ID.
        
        Uses Affiliate API with category filter.
        """
        page_size = kwargs.get("page_size", 20)
        
        params = {
            "app_key": self.affiliate_app_key,
            "method": "aliexpress.affiliate.product.query",
            "timestamp": str(int(time.time() * 1000)),
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "tracking_id": os.getenv("ALIEXPRESS_TRACKING_ID", ""),  # mandatory (#AE)
            "category_ids": category_id,
            "target_currency": "USD",
            "target_language": "EN",
            "ship_to_country": "US",
            "sort": "LAST_VOLUME_DESC",
            "page_size": str(page_size),
            "page_no": "1",
        }
        
        params["sign"] = self._generate_signature(params, self.affiliate_app_secret)
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(self.api_url, params=params, timeout=15)
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            
            if "error_response" in data:
                return []
            
            # Parse response
            products = []
            resp = data.get("aliexpress_affiliate_product_query_response", {})
            resp_result = resp.get("resp_result", {})
            result = resp_result.get("result", {})
            product_list = result.get("products", {}).get("product", [])
            
            if isinstance(product_list, dict):
                product_list = [product_list]
            
            for item in product_list:
                try:
                    price = float(str(item.get("target_sale_price", "0")).replace(",", ""))
                    product = ProductCandidate(
                        name=item.get("product_title", "Unknown"),
                        source=self.source_id,
                        price=price,
                        url=item.get("promotion_link", ""),
                        image_url=item.get("product_main_image_url", ""),
                        supplier_rating=4.0,
                        search_volume=int(item.get("lastest_volume", 0)),
                        category=item.get("second_level_category_name", ""),
                    )
                    products.append(product)
                except (ValueError, TypeError, KeyError):
                    continue  # Invalid product data - skip this item
            
            return products
            
        except Exception as e:
            print(f"[ERROR] Category search error: {e}")
            return []

    async def get_product_details(self, product_id: str) -> dict:
        """
        Get detailed product information.

        Args:
            product_id: AliExpress product ID

        Returns:
            Product details dict
        """
        if not self.api_key:
            return {}

        params = {
            "app_key": self.affiliate_app_key,
            "method": "aliexpress.affiliate.productdetail.get",
            "timestamp": str(int(time.time() * 1000)),
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "product_ids": product_id,
            "target_currency": "USD",
            "target_language": "EN",
            "ship_to_country": "US",
        }
        
        params["sign"] = self._generate_signature(params, self.affiliate_app_secret)
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(self.api_url, params=params, timeout=15)
            )
            
            if response.status_code != 200:
                return {}
            
            data = response.json()
            
            if "error_response" in data:
                return {}
            
            resp = data.get("aliexpress_affiliate_productdetail_get_response", {})
            resp_result = resp.get("resp_result", {})
            result = resp_result.get("result", {})
            products = result.get("products", {}).get("product", [])
            
            if products:
                return products[0] if isinstance(products, list) else products
            
            return {}
            
        except Exception as e:
            print(f"[ERROR] Product details error: {e}")
            return {}

    async def calculate_margin(self, product_price: float, sale_price: float, shipping_cost: float = 0) -> dict:
        """
        Calculate profit margin for a product.

        Returns:
            Margin calculation dict
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


# Quick test function
async def test_aliexpress():
    """Test AliExpress connector."""
    print("\n" + "="*60)
    print("[TEST] TESTING ALIEXPRESS CONNECTOR")
    print("="*60)
    
    connector = AliExpressConnector()
    
    if not connector.is_available():
        print("[ERROR] AliExpress not configured")
        return
    
    print(f"[SUCCESS] API Key: {connector.api_key[:8]}...")
    print(f"[SUCCESS] Affiliate Key: {connector.affiliate_app_key[:8]}...")
    
    # Test keyword search
    print("\n Testing keyword search: 'smart plug wifi'")
    products = await connector.search("smart plug wifi", page_size=5)
    
    print(f"\n[SEARCH] Results: {len(products)} products")
    for p in products[:3]:
        print(f"   [PACKAGE] {p.name[:50]}...")
        print(f"      Price: ${p.price:.2f} | Orders: {p.search_volume}")
    
    # Test trending
    print("\n Testing trending products...")
    trending = await connector.get_trending(limit=5)
    
    print(f"\n[HOT] Trending: {len(trending)} products")
    for p in trending[:3]:
        print(f"   [HOT] {p.name[:50]}...")
        print(f"      Price: ${p.price:.2f}")
    
    print("\n[SUCCESS] Test complete!")


if __name__ == "__main__":
    asyncio.run(test_aliexpress())
