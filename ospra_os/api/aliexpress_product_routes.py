"""
AliExpress Product Scraping API Routes

Provides endpoints for product search and scraping using both APIs:
- Dropshipping API (520918): Product feeds, search
- Affiliate API (522382): Product details, affiliate links
"""
import os
import json
import hmac
import hashlib
import time
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import aiohttp


router = APIRouter(prefix="/api/aliexpress/products", tags=["aliexpress-products"])


class AliExpressProductAPI:
    """Handles AliExpress product API requests"""

    def __init__(self):
        # Load credentials from environment
        # Try OUBONSHOP_ prefix first (existing), then standard names
        # Defaults match the OAuth routes
        self.dropship_app_key = os.getenv("ALIEXPRESS_APP_KEY") or os.getenv("OUBONSHOP_ALIEXPRESS_API_KEY", "520918")
        self.dropship_app_secret = os.getenv("ALIEXPRESS_APP_SECRET") or os.getenv("OUBONSHOP_ALIEXPRESS_APP_SECRET", "idjX6tOzHx6urVsSylVzEcHZKwBN4YhN")
        self.affiliate_app_key = os.getenv("ALIEXPRESS_AFFILIATE_APP_KEY", "522382")
        self.affiliate_app_secret = os.getenv("ALIEXPRESS_AFFILIATE_APP_SECRET", "9Kkt2Mn5icXLV7fShLfT38OarpjXqtrL")

        # API endpoint
        self.api_url = "https://api-sg.aliexpress.com/sync"

        # Token files
        self.secrets_dir = Path(".secrets")
        self.dropship_tokens_file = self.secrets_dir / "aliexpress_tokens.json"
        self.affiliate_tokens_file = self.secrets_dir / "aliexpress_affiliate_tokens.json"

    def load_tokens(self, tokens_file: Path) -> Optional[dict]:
        """Load access tokens from database (file path used to determine api_type)"""
        # Determine API type from filename
        api_type = "affiliate" if "affiliate" in str(tokens_file) else "dropship"

        try:
            from ospra_os.database.aliexpress_tokens import load_token
            return load_token(api_type)
        except Exception as e:
            print(f"❌ Error loading {api_type} token from database: {e}")
            return None

    def generate_signature(self, params: dict, app_secret: str, api_path: str = "/sync") -> str:
        """Generate HMAC-SHA256 signature for API request"""
        # Sort parameters (excluding 'sign')
        sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])

        # Concatenate: sorted params ONLY (no API path for product API calls)
        concat_str = ''.join([f"{k}{v}" for k, v in sorted_params])

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            app_secret.encode('utf-8'),
            concat_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()

        return signature

    async def get_hot_products(
        self,
        page_size: int = 20,
        category_id: Optional[str] = None,
        feed_name: str = "DS_Global_topsellers"
    ) -> dict:
        """
        Get hot/trending products from Dropshipping API

        Args:
            page_size: Number of products to return (max 50)
            category_id: Optional category filter

        Returns:
            {
                "success": True,
                "products": [...],
                "count": int
            }
        """
        # Load dropshipping tokens
        tokens = self.load_tokens(self.dropship_tokens_file)
        if not tokens or not tokens.get("access_token"):
            raise HTTPException(status_code=401, detail="Dropshipping API not authorized")

        # Build API request
        timestamp = str(int(time.time() * 1000))
        params = {
            "app_key": self.dropship_app_key,
            "method": "aliexpress.ds.recommend.feed.get",
            "timestamp": timestamp,
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "session": tokens["access_token"],
            "feed_name": feed_name,
            "country": "US",
            "target_currency": "USD",
            "target_language": "EN",
            "page_size": str(min(page_size, 50)),
            "page_no": "1",
        }

        if category_id:
            params["category_ids"] = category_id

        # Generate signature
        params["sign"] = self.generate_signature(params, self.dropship_app_secret)

        # Make API request
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params, timeout=15) as response:
                    data = await response.json()

                    # Check for errors
                    if "error_response" in data:
                        error = data["error_response"]
                        raise HTTPException(
                            status_code=400,
                            detail=f"AliExpress API error: {error.get('msg')} (code: {error.get('code')})"
                        )

                    # Parse response - try both response formats
                    resp_result = data.get("aliexpress_ds_recommend_feed_get_response", {})
                    # Try "result" first (new format), then "resp_result" (old format)
                    result = resp_result.get("result") or resp_result.get("resp_result", {})

                # Extract products
                if isinstance(result.get("products"), dict):
                    product_list = result.get("products", {}).get("product", [])
                else:
                    product_list = result.get("products", [])

                # Format products
                products = []
                for item in product_list:
                    products.append({
                        "product_id": item.get("product_id"),
                        "title": item.get("product_title"),
                        "price": float(item.get("target_sale_price", 0)),
                        "original_price": float(item.get("target_original_price", 0)),
                        "discount": item.get("discount", "0%"),
                        "image_url": item.get("product_main_image_url"),
                        "url": item.get("promotion_link", item.get("product_detail_url")),
                        "orders": int(item.get("volume", 0)),
                        "rating": float(item.get("evaluate_rate", 0)) / 20.0,  # Convert 0-100 to 0-5
                        "category": item.get("second_level_category_name", item.get("first_level_category_name")),
                        "ship_from": item.get("ship_from_country"),
                        "shipping_cost": item.get("shipping_cost"),
                    })

                return {
                    "success": True,
                    "products": products,
                    "count": len(products),
                    "source": "dropshipping_api",
                    "feed": "hot_products"
                }
        except HTTPException:
            raise  # Re-raise HTTP exceptions as-is
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch hot products: {str(e)}"
            )

    async def get_bestsellers(self, page_size: int = 20) -> dict:
        """Get bestselling products from Dropshipping API"""
        tokens = self.load_tokens(self.dropship_tokens_file)
        if not tokens or not tokens.get("access_token"):
            raise HTTPException(status_code=401, detail="Dropshipping API not authorized")

        timestamp = str(int(time.time() * 1000))
        params = {
            "app_key": self.dropship_app_key,
            "method": "aliexpress.ds.recommend.feed.get",
            "timestamp": timestamp,
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "session": tokens["access_token"],
            "feed_name": "DS bestseller",  # Bestseller feed
            "country": "US",
            "target_currency": "USD",
            "target_language": "EN",
            "page_size": str(min(page_size, 50)),
            "page_no": "1",
        }

        params["sign"] = self.generate_signature(params, self.dropship_app_secret)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params, timeout=15) as response:
                    data = await response.json()

                    if "error_response" in data:
                        error = data["error_response"]
                        raise HTTPException(
                            status_code=400,
                            detail=f"AliExpress API error: {error.get('msg')}"
                        )

                    resp_result = data.get("aliexpress_ds_recommend_feed_get_response", {})
                    # Try "result" first (new format), then "resp_result" (old format)
                    result = resp_result.get("result") or resp_result.get("resp_result", {})

                    if isinstance(result.get("products"), dict):
                        product_list = result.get("products", {}).get("product", [])
                    else:
                        product_list = result.get("products", [])

                    products = []
                    for item in product_list:
                        products.append({
                            "product_id": item.get("product_id"),
                            "title": item.get("product_title"),
                            "price": float(item.get("target_sale_price", 0)),
                            "image_url": item.get("product_main_image_url"),
                            "url": item.get("promotion_link"),
                            "orders": int(item.get("volume", 0)),
                            "rating": float(item.get("evaluate_rate", 0)) / 20.0,
                        })

                    return {
                        "success": True,
                        "products": products,
                        "count": len(products),
                        "source": "dropshipping_api",
                        "feed": "bestsellers"
                    }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch bestsellers: {str(e)}"
            )

    async def affiliate_product_query(
        self,
        keywords: Optional[str] = None,
        category_ids: Optional[str] = None,
        page_size: int = 20,
        page_no: int = 1,
        sort: str = "SALE_PRICE_ASC"
    ) -> dict:
        """
        Search for products using Affiliate API

        This is more reliable than Dropshipping feeds and works for all account types.
        """
        # Load affiliate tokens
        tokens = self.load_tokens(self.affiliate_tokens_file)
        if not tokens or not tokens.get("access_token"):
            raise HTTPException(status_code=401, detail="Affiliate API not authorized")

        timestamp = str(int(time.time() * 1000))
        params = {
            "app_key": self.affiliate_app_key,
            "method": "aliexpress.affiliate.product.query",
            "timestamp": timestamp,
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "session": tokens["access_token"],
            "target_currency": "USD",
            "target_language": "EN",
            "ship_to_country": "US",
            "page_size": str(min(page_size, 50)),
            "page_no": str(page_no),
            "sort": sort,
        }

        if keywords:
            params["keywords"] = keywords
        if category_ids:
            params["category_ids"] = category_ids

        params["sign"] = self.generate_signature(params, self.affiliate_app_secret)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params, timeout=15) as response:
                    data = await response.json()

                    if "error_response" in data:
                        error = data["error_response"]
                        raise HTTPException(
                            status_code=400,
                            detail=f"AliExpress API error: {error.get('msg')}"
                        )

                    # Parse response
                    resp = data.get("aliexpress_affiliate_product_query_response", {})
                    resp_result = resp.get("resp_result", {})
                    result = resp_result.get("result", {})

                    # Extract products
                    products_data = result.get("products", {})
                    product_list = products_data.get("product", []) if isinstance(products_data, dict) else products_data

                    # Format products
                    products = []
                    for item in product_list:
                        products.append({
                            "product_id": item.get("product_id"),
                            "title": item.get("product_title"),
                            "price": float(item.get("target_sale_price", 0)) if item.get("target_sale_price") else 0.0,
                            "original_price": float(item.get("target_original_price", 0)) if item.get("target_original_price") else 0.0,
                            "discount": item.get("discount", "0%"),
                            "image_url": item.get("product_main_image_url"),
                            "url": item.get("promotion_link"),
                            "orders": int(item.get("volume", 0)) if item.get("volume") else 0,
                            "rating": float(item.get("evaluate_rate", 0)) / 20.0 if item.get("evaluate_rate") else 0.0,
                            "category": item.get("second_level_category_name"),
                            "commission_rate": item.get("commission_rate"),
                        })

                    return {
                        "success": True,
                        "products": products,
                        "count": len(products),
                        "total": result.get("total_record_count", 0),
                        "source": "affiliate_api"
                    }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to query products: {str(e)}"
            )

    async def hybrid_product_discovery(
        self,
        keywords: Optional[str] = None,
        category_ids: Optional[str] = None,
        page_size: int = 20,
        page_no: int = 1,
        sort: str = "SALE_PRICE_ASC",
        enrich_with_dropship: bool = False
    ) -> dict:
        """
        HYBRID: Use Affiliate API for discovery + optionally enrich with Dropshipping API

        This combines the best of both APIs:
        1. Affiliate API: Broad product search with keywords (WORKS)
        2. Dropshipping API: Detailed product info by ID (WORKS if you have product IDs)

        Args:
            keywords: Search keywords
            category_ids: Category filter
            page_size: Number of products (max 50)
            page_no: Page number
            sort: Sort order
            enrich_with_dropship: If True, fetch detailed info from Dropshipping API

        Returns:
            Products with metadata from both APIs
        """
        # Step 1: Get products from Affiliate API (discovery)
        affiliate_result = await self.affiliate_product_query(
            keywords=keywords,
            category_ids=category_ids,
            page_size=page_size,
            page_no=page_no,
            sort=sort
        )

        if not affiliate_result["success"] or not affiliate_result["products"]:
            return affiliate_result

        products = affiliate_result["products"]

        # Step 2: Optionally enrich with Dropshipping API details
        if enrich_with_dropship:
            # Load dropshipping tokens
            tokens = self.load_tokens(self.dropship_tokens_file)

            # Only enrich if we have dropship authorization
            if tokens and tokens.get("access_token"):
                enriched_products = []

                for product in products:
                    product_id = product.get("product_id")

                    if not product_id:
                        enriched_products.append(product)
                        continue

                    try:
                        # Fetch detailed info from Dropshipping API
                        timestamp = str(int(time.time() * 1000))
                        params = {
                            "app_key": self.dropship_app_key,
                            "method": "aliexpress.ds.product.get",
                            "timestamp": timestamp,
                            "format": "json",
                            "v": "2.0",
                            "sign_method": "sha256",
                            "session": tokens["access_token"],
                            "product_id": str(product_id),
                            "target_currency": "USD",
                            "target_language": "EN",
                        }

                        params["sign"] = self.generate_signature(params, self.dropship_app_secret)

                        async with aiohttp.ClientSession() as session:
                            async with session.get(self.api_url, params=params, timeout=10) as response:
                                data = await response.json()

                                # If we got dropship data, merge it
                                if "error_response" not in data:
                                    resp = data.get("aliexpress_ds_product_get_response", {})
                                    result = resp.get("result") or resp.get("resp_result", {})

                                    if result:
                                        # Enrich product with dropship data
                                        product["detailed_images"] = result.get("ae_multimedia_info_dto", {}).get("image_urls", [])
                                        product["ship_from"] = result.get("ship_from_country")
                                        product["package_type"] = result.get("package_type")
                                        product["delivery_time"] = result.get("delivery_time")
                                        product["source"] = "hybrid_affiliate+dropship"

                        enriched_products.append(product)

                    except Exception as e:
                        # If dropship enrichment fails, just use affiliate data
                        print(f"Failed to enrich product {product_id}: {e}")
                        enriched_products.append(product)

                products = enriched_products

        return {
            "success": True,
            "products": products,
            "count": len(products),
            "total": affiliate_result.get("total", 0),
            "source": "hybrid_affiliate" + ("+dropship" if enrich_with_dropship else ""),
            "method": "affiliate_discovery" + (" + dropship_details" if enrich_with_dropship else "")
        }

    async def get_product_details(self, product_ids: List[str]) -> dict:
        """Get product details from Affiliate API"""
        tokens = self.load_tokens(self.affiliate_tokens_file)
        if not tokens or not tokens.get("access_token"):
            raise HTTPException(status_code=401, detail="Affiliate API not authorized")

        timestamp = str(int(time.time() * 1000))
        params = {
            "app_key": self.affiliate_app_key,
            "method": "aliexpress.affiliate.productdetail.get",
            "timestamp": timestamp,
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "session": tokens["access_token"],
            "product_ids": ",".join(product_ids),
            "target_currency": "USD",
            "target_language": "EN",
            "country": "US",
        }

        params["sign"] = self.generate_signature(params, self.affiliate_app_secret)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params, timeout=15) as response:
                    data = await response.json()

                    if "error_response" in data:
                        error = data["error_response"]
                        raise HTTPException(
                            status_code=400,
                            detail=f"AliExpress API error: {error.get('msg')}"
                        )

                    return {
                        "success": True,
                        "data": data,
                        "source": "affiliate_api"
                    }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch product details: {str(e)}"
            )

    async def get_feed_names(self) -> dict:
        """
        Get available feed names for the Dropshipping API

        Returns list of valid feed names that can be used with aliexpress.ds.recommend.feed.get
        """
        # Load dropshipping tokens
        tokens = self.load_tokens(self.dropship_tokens_file)
        if not tokens or not tokens.get("access_token"):
            raise HTTPException(status_code=401, detail="Dropshipping API not authorized")

        timestamp = str(int(time.time() * 1000))
        params = {
            "app_key": self.dropship_app_key,
            "method": "aliexpress.ds.feedname.get",
            "timestamp": timestamp,
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "session": tokens["access_token"],
        }

        params["sign"] = self.generate_signature(params, self.dropship_app_secret)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params, timeout=15) as response:
                    data = await response.json()

                    if "error_response" in data:
                        error = data["error_response"]
                        raise HTTPException(
                            status_code=400,
                            detail=f"AliExpress API error: {error.get('msg')}"
                        )

                    # Parse response
                    resp = data.get("aliexpress_ds_feedname_get_response", {})
                    resp_result = resp.get("resp_result", {})
                    result = resp_result.get("result", {})

                    # Extract promo names from nested structure
                    promos_data = result.get("promos", {})
                    promo_list = promos_data.get("promo", [])

                    # Format feed names
                    feed_names = [
                        {
                            "name": promo.get("promo_name"),
                            "description": promo.get("promo_desc"),
                            "product_count": promo.get("product_num")
                        }
                        for promo in promo_list
                    ]

                    return {
                        "success": True,
                        "total_feeds": result.get("current_record_count", 0),
                        "feeds": feed_names
                    }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get feed names: {str(e)}"
            )

    async def search_products(
        self,
        keywords: str,
        page_size: int = 20,
        page_no: int = 1
    ) -> dict:
        """
        Get product by ID using Dropshipping API

        Args:
            keywords: Product ID
            page_size: Not used (kept for compatibility)
            page_no: Not used (kept for compatibility)
        """
        # Load dropshipping tokens
        tokens = self.load_tokens(self.dropship_tokens_file)
        if not tokens or not tokens.get("access_token"):
            raise HTTPException(status_code=401, detail="Dropshipping API not authorized")

        timestamp = str(int(time.time() * 1000))
        params = {
            "app_key": self.dropship_app_key,
            "method": "aliexpress.ds.product.get",
            "timestamp": timestamp,
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "session": tokens["access_token"],
            "product_id": keywords,
            "target_currency": "USD",
            "target_language": "EN",
        }

        params["sign"] = self.generate_signature(params, self.dropship_app_secret)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params, timeout=15) as response:
                    data = await response.json()

                    if "error_response" in data:
                        error = data["error_response"]
                        raise HTTPException(
                            status_code=400,
                            detail=f"AliExpress API error: {error.get('msg')}"
                        )

                    # Parse product data
                    resp = data.get("aliexpress_ds_product_get_response", {})
                    result = resp.get("result") or resp.get("resp_result", {})

                    if not result:
                        return {
                            "success": True,
                            "products": [],
                            "count": 0,
                            "source": "dropshipping_search"
                        }

                    # Format single product
                    product = {
                        "product_id": result.get("ae_item_id"),
                        "title": result.get("subject"),
                        "price": float(result.get("target_sale_price", 0)),
                        "original_price": float(result.get("target_original_price", 0)),
                        "image_url": result.get("ae_item_main_image_url"),
                        "images": result.get("ae_multimedia_info_dto", {}).get("image_urls", []),
                        "url": result.get("item_url"),
                        "category": result.get("category_id"),
                        "ship_from": result.get("ship_from_country"),
                    }

                    return {
                        "success": True,
                        "products": [product],
                        "count": 1,
                        "source": "dropshipping_search"
                    }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to search products: {str(e)}"
            )


# Create API instance
api = AliExpressProductAPI()


# Route handlers

@router.get("/feed-names")
async def get_feed_names():
    """
    Get available feed names for the Dropshipping API

    Returns a list of valid feed names that can be used with the /hot and /bestsellers endpoints.
    """
    return await api.get_feed_names()


@router.get("/hot")
async def get_hot_products(
    page_size: int = Query(20, ge=1, le=50, description="Number of products to return"),
    category_id: Optional[str] = Query(None, description="Category ID filter"),
    feed_name: str = Query("DS_Global_topsellers", description="Feed name (use /feed-names to see available feeds)")
):
    """
    Get hot/trending products from AliExpress

    Uses Dropshipping API to fetch products from a specific feed.
    Use the /feed-names endpoint to see all available feeds.

    Popular feeds:
    - DS_Global_topsellers
    - DS_Home&Kitchen_bestsellers
    - AEB_Topseller_PriceRange0~20$
    """
    return await api.get_hot_products(page_size=page_size, category_id=category_id, feed_name=feed_name)


@router.get("/bestsellers")
async def get_bestsellers(
    page_size: int = Query(20, ge=1, le=50, description="Number of products to return")
):
    """
    Get bestselling products from AliExpress

    Uses Dropshipping API to fetch best-selling products by order volume.
    """
    return await api.get_bestsellers(page_size=page_size)


@router.get("/details")
async def get_product_details(
    product_ids: str = Query(..., description="Comma-separated product IDs")
):
    """
    Get detailed product information

    Uses Affiliate API to get product details including commission rates.
    """
    ids = [pid.strip() for pid in product_ids.split(",")]
    return await api.get_product_details(product_ids=ids)


@router.get("/search")
async def search_products_affiliate(
    keywords: Optional[str] = Query(None, description="Search keywords"),
    category_ids: Optional[str] = Query(None, description="Category IDs"),
    page_size: int = Query(20, ge=1, le=50),
    page_no: int = Query(1, ge=1),
    sort: str = Query("SALE_PRICE_ASC", description="Sort order (SALE_PRICE_ASC, SALE_PRICE_DESC, LAST_VOLUME_ASC, LAST_VOLUME_DESC)")
):
    """
    Search for products using Affiliate API

    This endpoint is more reliable than Dropshipping feeds and works for all account types.
    You can search by keywords, category, or both.

    Examples:
    - ?keywords=phone
    - ?keywords=smart+watch&sort=LAST_VOLUME_DESC
    - ?category_ids=509,1511
    """
    return await api.affiliate_product_query(
        keywords=keywords,
        category_ids=category_ids,
        page_size=page_size,
        page_no=page_no,
        sort=sort
    )


@router.get("/product/{product_id}")
async def get_single_product(
    product_id: str,
    page_size: int = Query(20, ge=1, le=50),
    page_no: int = Query(1, ge=1)
):
    """
    Get product details by ID using Dropshipping API
    """
    return await api.search_products(
        keywords=product_id,
        page_size=page_size,
        page_no=page_no
    )


@router.get("/hybrid-discover")
async def hybrid_product_discovery(
    keywords: Optional[str] = Query(None, description="Search keywords"),
    category_ids: Optional[str] = Query(None, description="Category IDs"),
    page_size: int = Query(20, ge=1, le=50),
    page_no: int = Query(1, ge=1),
    sort: str = Query("SALE_PRICE_ASC", description="Sort order"),
    enrich: bool = Query(False, description="Enrich with Dropshipping API details (slower)")
):
    """
    🔥 HYBRID DISCOVERY: Best of both APIs

    Uses Affiliate API for discovery (keyword search) + optionally enriches with Dropshipping API.

    - **Affiliate API**: Fast product search with keywords
    - **Dropshipping API**: Detailed shipping/delivery info (optional, use ?enrich=true)

    This is the RECOMMENDED method for product discovery.

    Examples:
    - ?keywords=smart+watch (fast, affiliate only)
    - ?keywords=smart+watch&enrich=true (slower, includes shipping details)
    - ?keywords=headphones&sort=LAST_VOLUME_DESC&enrich=true
    """
    return await api.hybrid_product_discovery(
        keywords=keywords,
        category_ids=category_ids,
        page_size=page_size,
        page_no=page_no,
        sort=sort,
        enrich_with_dropship=enrich
    )


@router.get("/debug/raw-response")
async def debug_raw_response(page_size: int = Query(3, ge=1, le=10)):
    """
    DEBUG: Get raw AliExpress API response to see structure
    """
    import aiohttp
    import time

    # Load tokens
    tokens = api.load_tokens(api.dropship_tokens_file)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(status_code=401, detail="Dropshipping API not authorized")

    # Build request
    timestamp = str(int(time.time() * 1000))
    params = {
        "app_key": api.dropship_app_key,
        "method": "aliexpress.ds.recommend.feed.get",
        "timestamp": timestamp,
        "format": "json",
        "v": "2.0",
        "sign_method": "sha256",
        "session": tokens["access_token"],
        "feed_name": "DS hot product",
        "country": "US",
        "target_currency": "USD",
        "target_language": "EN",
        "page_size": str(page_size),
        "page_no": "1",
    }

    params["sign"] = api.generate_signature(params, api.dropship_app_secret)

    # Make request
    async with aiohttp.ClientSession() as session:
        async with session.get(api.api_url, params=params, timeout=15) as response:
            data = await response.json()
            return {
                "raw_response": data,
                "token_preview": tokens["access_token"][:20] + "...",
                "signature_preview": params["sign"][:40] + "..."
            }
