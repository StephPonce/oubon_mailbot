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
        self.dropship_app_key = os.getenv("ALIEXPRESS_APP_KEY", "520918")
        self.dropship_app_secret = os.getenv("ALIEXPRESS_APP_SECRET")
        self.affiliate_app_key = os.getenv("ALIEXPRESS_AFFILIATE_APP_KEY", "522382")
        self.affiliate_app_secret = os.getenv("ALIEXPRESS_AFFILIATE_APP_SECRET")

        # API endpoint
        self.api_url = "https://api-sg.aliexpress.com/sync"

        # Token files
        self.secrets_dir = Path(".secrets")
        self.dropship_tokens_file = self.secrets_dir / "aliexpress_tokens.json"
        self.affiliate_tokens_file = self.secrets_dir / "aliexpress_affiliate_tokens.json"

    def load_tokens(self, tokens_file: Path) -> Optional[dict]:
        """Load access tokens from file"""
        if not tokens_file.exists():
            return None

        try:
            with open(tokens_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def generate_signature(self, params: dict, app_secret: str, api_path: str = "/sync") -> str:
        """Generate HMAC-SHA256 signature for API request"""
        # Sort parameters (excluding 'sign')
        sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])

        # Concatenate: API_PATH + sorted params
        concat_str = api_path + ''.join([f"{k}{v}" for k, v in sorted_params])

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
        category_id: Optional[str] = None
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
            "feed_name": "DS hot product",
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

                    # Parse response
                    resp_result = data.get("aliexpress_ds_recommend_feed_get_response", {})
                    result = resp_result.get("resp_result", {})

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
                    result = resp_result.get("resp_result", {})

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


# Create API instance
api = AliExpressProductAPI()


# Route handlers

@router.get("/hot")
async def get_hot_products(
    page_size: int = Query(20, ge=1, le=50, description="Number of products to return"),
    category_id: Optional[str] = Query(None, description="Category ID filter")
):
    """
    Get hot/trending products from AliExpress

    Uses Dropshipping API to fetch currently trending products.
    """
    return await api.get_hot_products(page_size=page_size, category_id=category_id)


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
