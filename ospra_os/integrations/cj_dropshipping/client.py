"""
CJ Dropshipping API Client v3
=============================
US/EU warehouse supplier with faster shipping times than AliExpress.

API Docs: https://developers.cjdropshipping.com/
API Version: 2.0

FIXED ISSUES:
- v2: POST not supported -> Now using GET for product/list
- v3: Added rate limiting (1 req/sec max)

ENDPOINTS (ALL GET):
- GET /product/list - List products (keyword + category)
- GET /product/query - Get product by ID
- GET /product/getCategory - Get all categories
"""

import os
import logging
import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)

CJ_API_BASE = "https://developers.cjdropshipping.com/api2.0/v1"


class CJDropshippingClient:
    """
    CJ Dropshipping API client for product discovery and sourcing.
    
    Key Features:
    - US/EU/CN warehouse products
    - Faster shipping than AliExpress
    - Rate limit: 1 request per second
    """
    
    # CJ Category IDs for common niches
    CATEGORY_MAP = {
        "smart_home": "1489",      # Smart Home
        "kitchen": "4",            # Home & Garden > Kitchen
        "fitness": "18",           # Sports & Entertainment
        "beauty": "66",            # Beauty & Health
        "tech": "509",             # Consumer Electronics
        "electronics": "509",
        "home_decor": "15",        # Home & Garden
        "pet": "1478",             # Pet Products
        "outdoor": "18",           # Sports & Outdoors
        "office": "21",            # Office & School Supplies
        "gaming": "509",           # Consumer Electronics
        "phone": "509",            # Phone accessories
        "led": "39",               # Lights & Lighting
        "toys": "26",              # Toys & Hobbies
    }
    
    def __init__(self):
        self.access_token = os.getenv('CJ_ACCESS_TOKEN') or os.getenv('OUBONSHOP_CJ_ACCESS_TOKEN')
        self._available = bool(self.access_token)
        self._last_request_time = 0
        self._rate_limit_delay = 1.1  # 1.1 seconds between requests (CJ allows 1/sec)
        
        if self._available:
            logger.info("[SUCCESS] CJ Dropshipping client initialized (rate limit: 1 req/sec)")
        else:
            logger.warning("[WARNING] CJ Dropshipping: CJ_ACCESS_TOKEN not configured")
    
    def is_available(self) -> bool:
        return self._available
    
    async def _rate_limit_wait(self):
        """Ensure we don't exceed 1 request per second"""
        now = time.time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._rate_limit_delay:
            wait_time = self._rate_limit_delay - time_since_last
            logger.debug(f"[RATE_LIMIT] Waiting {wait_time:.2f}s before CJ request")
            await asyncio.sleep(wait_time)
        self._last_request_time = time.time()
    
    async def _request(self, endpoint: str, params: dict = None) -> Optional[Dict]:
        """
        Make authenticated GET request to CJ API.
        
        NOTE: CJ API v2.0 uses GET for all read operations.
        """
        if not self._available:
            logger.warning("[WARNING] CJ client not available - no token")
            return None
        
        # Rate limiting
        await self._rate_limit_wait()
        
        url = f"{CJ_API_BASE}/{endpoint}"
        headers = {
            "CJ-Access-Token": self.access_token,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.debug(f"[DEBUG] CJ API GET {endpoint}")
                logger.debug(f"[DEBUG] Params: {params}")
                
                async with session.get(url, headers=headers, params=params, timeout=30) as response:
                    response_text = await response.text()
                    
                    if response.status == 429:
                        logger.warning("[WARNING] CJ rate limit hit (429) - waiting 2 seconds")
                        await asyncio.sleep(2)
                        return None
                    
                    if response.status == 200:
                        try:
                            result = await response.json()
                        except:
                            logger.error(f"[ERROR] CJ invalid JSON response: {response_text[:200]}")
                            return None
                        
                        if result.get('result'):
                            logger.debug(f"[DEBUG] CJ success - got data")
                            return result.get('data')
                        else:
                            error_msg = result.get('message', 'Unknown error')
                            logger.warning(f"[WARNING] CJ API error: {error_msg}")
                            return None
                    else:
                        logger.error(f"[ERROR] CJ API HTTP {response.status}: {response_text[:200]}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("[ERROR] CJ API timeout (30s)")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"[ERROR] CJ API connection error: {e}")
            return None
        except Exception as e:
            logger.error(f"[ERROR] CJ API request failed: {e}")
            return None
    
    async def search_products(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
        category_id: str = None
    ) -> List[Dict]:
        """
        Search CJ Dropshipping products.
        
        Uses GET /product/list with query parameters.
        
        Args:
            keyword: Search term (optional)
            page: Page number (1-indexed)
            page_size: Results per page (max 200)
            category_id: Optional category ID filter
            
        Returns:
            List of normalized product dicts
        """
        if not self._available:
            return []
        
        # Build query params
        params = {
            "pageNum": page,
            "pageSize": min(page_size, 200),
        }
        
        # Add keyword if provided
        if keyword:
            params["productNameEn"] = keyword
        
        # Add category filter if provided
        if category_id:
            params["categoryId"] = category_id
        
        search_desc = f"keyword='{keyword}'" if keyword else f"category={category_id}"
        logger.info(f"[INFO] CJ search: {search_desc}")
        
        result = await self._request("product/list", params)
        
        if not result:
            logger.warning(f"[WARNING] CJ returned no data for {search_desc}")
            return []
        
        # Handle both list and paginated response formats
        items = result.get('list', []) if isinstance(result, dict) else result
        if not items:
            logger.info(f"[INFO] CJ: No products found for {search_desc}")
            return []
        
        products = []
        for item in items:
            product = self._normalize_product(item)
            if product:
                products.append(product)
        
        logger.info(f"[SUCCESS] CJ Dropshipping: Found {len(products)} products")
        return products
    
    async def search_by_niche(self, niche: str, page_size: int = 20) -> List[Dict]:
        """
        Search by niche using category mapping.
        
        This is more reliable than keyword search for CJ.
        """
        category_id = self.CATEGORY_MAP.get(niche.lower())
        
        if category_id:
            logger.info(f"[INFO] CJ niche search: {niche} -> category {category_id}")
            return await self.search_products(
                keyword="",
                category_id=category_id,
                page_size=page_size
            )
        else:
            # Fallback to keyword search
            logger.info(f"[INFO] CJ: No category mapping for '{niche}', using keyword search")
            return await self.search_products(keyword=niche, page_size=page_size)
    
    async def get_product_details(self, pid: str) -> Optional[Dict]:
        """Get detailed product info by CJ product ID"""
        if not self._available:
            return None
        
        result = await self._request("product/query", {"pid": pid})
        if result:
            return self._normalize_product(result)
        return None
    
    async def get_categories(self) -> List[Dict]:
        """Get all CJ product categories"""
        result = await self._request("product/getCategory")
        if result:
            logger.info(f"[SUCCESS] CJ: Retrieved {len(result) if isinstance(result, list) else 'unknown'} categories")
        return result if isinstance(result, list) else []
    
    async def get_variants(self, pid: str) -> List[Dict]:
        """Get product variants (colors, sizes, etc.)"""
        if not self._available:
            return []
        
        result = await self._request("product/variant/query", {"pid": pid})
        return result if isinstance(result, list) else []
    
    def _normalize_product(self, item: dict) -> Optional[Dict]:
        """Normalize CJ product data to standard format with ALL images"""
        try:
            # Get price - CJ uses sellPrice for our cost
            cost_price = float(item.get('sellPrice') or item.get('productPrice') or 0)
            if cost_price == 0:
                logger.debug(f"[DEBUG] CJ product skipped - no price: {item.get('productNameEn', 'Unknown')[:30]}")
                return None
            
            # Calculate suggested retail (2.5x markup)
            suggested_price = round(cost_price * 2.5, 2)
            profit = round(suggested_price - cost_price, 2)
            
            # === CAPTURE ALL PRODUCT IMAGES ===
            all_images = []
            
            # Primary image
            main_image = item.get('productImage', '')
            if main_image and isinstance(main_image, str) and main_image.startswith('http'):
                all_images.append(main_image)
            elif isinstance(main_image, list) and main_image:
                all_images.extend([img for img in main_image if img and img.startswith('http')])
            
            # Product image set (contains ALL angles)
            image_set = item.get('productImageSet', [])
            if isinstance(image_set, str):
                image_set = [image_set]
            if isinstance(image_set, list):
                for img in image_set:
                    if img and isinstance(img, str) and img.startswith('http') and img not in all_images:
                        all_images.append(img)
            
            # Also check for variant images
            variants = item.get('variants', []) or item.get('sku_list', [])
            if isinstance(variants, list):
                for variant in variants:
                    if isinstance(variant, dict):
                        var_img = variant.get('variantImage') or variant.get('image')
                        if var_img and isinstance(var_img, str) and var_img.startswith('http') and var_img not in all_images:
                            all_images.append(var_img)
            
            # Limit to 10 images max
            all_images = all_images[:10]
            
            # Use first image as main display image
            image_url = all_images[0] if all_images else ''
            
            logger.debug(f"[IMAGES] CJ {item.get('productNameEn', '')[:30]}: {len(all_images)} images captured")
            
            # Determine warehouse
            warehouse = item.get('sourceFrom', '') or item.get('countryCode', 'CN')
            us_warehouse = 'US' in str(warehouse).upper()
            eu_warehouse = any(w in str(warehouse).upper() for w in ['DE', 'GB', 'FR', 'EU', 'UK'])
            
            pid = item.get('pid', '') or item.get('productId', '')
            title = item.get('productNameEn', '') or item.get('productName', 'CJ Product')
            
            return {
                "product_id": f"cj_{pid}",
                "cj_pid": pid,
                "title": title,
                "description": item.get('description', '') or title,
                
                # Pricing
                "price": cost_price,
                "cost_price": cost_price,
                "supplier_cost": cost_price,
                "suggested_price": suggested_price,
                "profit": profit,
                
                # Images - PRIMARY + ALL
                "image_url": image_url,
                "main_image": image_url,
                "productMainImageUrl": image_url,
                "all_images": all_images,
                "image_count": len(all_images),
                
                # Metadata
                "source": "cj_dropshipping",
                "is_mock": False,
                "supplier_url": f"https://cjdropshipping.com/product/{pid}.html" if pid else None,
                "affiliate_link": None,
                
                # CJ-specific
                "category_id": item.get('categoryId', ''),
                "category_name": item.get('categoryName', ''),
                "sku_list": item.get('variants', []),
                "weight": float(item.get('productWeight', 0) or 0),
                
                # Warehouse info (CJ's key advantage)
                "warehouse": warehouse,
                "us_warehouse": us_warehouse,
                "eu_warehouse": eu_warehouse,
                
                # Data sources citation
                "data_sources": {
                    "cj_dropshipping": {
                        "available": True,
                        "warehouse": warehouse,
                        "us_warehouse": us_warehouse,
                        "eu_warehouse": eu_warehouse,
                        "url": f"https://cjdropshipping.com/product/{pid}.html" if pid else None,
                        "image_count": len(all_images)
                    }
                },
                
                "discovered_at": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"[ERROR] CJ product normalization failed: {e}")
            return None


# Singleton
_cj_client = None

def get_cj_client() -> CJDropshippingClient:
    global _cj_client
    if _cj_client is None:
        _cj_client = CJDropshippingClient()
    return _cj_client


async def search_cj_products(keyword: str, limit: int = 20) -> List[Dict]:
    """Quick function to search CJ products by keyword"""
    client = get_cj_client()
    return await client.search_products(keyword, page_size=limit)


async def search_cj_by_niche(niche: str, limit: int = 20) -> List[Dict]:
    """Quick function to search CJ products by niche/category"""
    client = get_cj_client()
    return await client.search_by_niche(niche, page_size=limit)
