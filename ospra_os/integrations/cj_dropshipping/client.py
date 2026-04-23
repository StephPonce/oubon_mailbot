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
import json
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
        "car": "1500",             # Car Accessories
        "baby": "1501",            # Baby Products
        "jewelry": "36",           # Jewelry
        "bags": "1524",            # Bags & Luggage
        "watches": "1511",         # Watches
    }

    # Map search keywords to CJ-specific search terms AND categories
    # CJ API needs simpler, more specific keywords
    KEYWORD_MAP = {
        # Smart Home keywords (matching new NICHE_KEYWORDS)
        "wifi smart plug": {"keywords": ["smart plug", "wifi plug"], "category": "1489"},
        "led strip lights rgb": {"keywords": ["led strip", "rgb light"], "category": "39"},
        "smart light bulb wifi": {"keywords": ["smart bulb", "wifi bulb"], "category": "39"},
        "motion sensor alarm": {"keywords": ["motion sensor", "pir sensor"], "category": "1489"},
        "smart door lock": {"keywords": ["door lock", "smart lock"], "category": "1489"},
        # Legacy mappings
        "smart home": {"keywords": ["smart plug", "wifi switch"], "category": "1489"},
        "smart home gadgets": {"keywords": ["smart plug", "led strip"], "category": "1489"},
        "led lights": {"keywords": ["led strip", "led bulb"], "category": "39"},
        "smart plug": {"keywords": ["smart plug", "wifi plug"], "category": "1489"},
        "smart bulb": {"keywords": ["smart bulb", "wifi bulb"], "category": "39"},
        # Kitchen
        "kitchen gadgets": {"keywords": ["kitchen", "cooking", "utensil"], "category": "4"},
        "cooking": {"keywords": ["cooking", "kitchen", "chef"], "category": "4"},
        # Fitness
        "fitness": {"keywords": ["fitness", "gym", "exercise", "sport"], "category": "18"},
        "workout": {"keywords": ["workout", "fitness", "gym"], "category": "18"},
        "yoga": {"keywords": ["yoga", "mat", "fitness"], "category": "18"},
        # Tech/Electronics
        "phone accessories": {"keywords": ["phone", "case", "charger", "cable"], "category": "509"},
        "wireless charger": {"keywords": ["wireless charger", "charging"], "category": "509"},
        "earbuds": {"keywords": ["earbuds", "headphone", "bluetooth"], "category": "509"},
        # Beauty
        "skincare": {"keywords": ["skincare", "face", "cream", "serum"], "category": "66"},
        "makeup": {"keywords": ["makeup", "cosmetic", "beauty"], "category": "66"},
        # Pet
        "pet supplies": {"keywords": ["pet", "dog", "cat"], "category": "1478"},
        "dog": {"keywords": ["dog", "pet", "puppy"], "category": "1478"},
        "cat": {"keywords": ["cat", "pet", "kitten"], "category": "1478"},
        # Car
        "car accessories": {"keywords": ["car", "auto", "vehicle"], "category": "1500"},
        "carplay": {"keywords": ["carplay", "car screen", "car display"], "category": "1500"},
    }
    
    def __init__(self):
        self.access_token = os.getenv('CJ_ACCESS_TOKEN') or os.getenv('OUBONSHOP_CJ_ACCESS_TOKEN')
        self._available = bool(self.access_token)
        self._last_request_time = 0
        self._rate_limit_delay = 3.0  # 3 seconds between requests (CJ very strict limit)
        self._consecutive_429s = 0
        # Step C: reduced from 2 → 1. With our per-source timeout (12s) and
        # a bounded 5s max backoff, one retry is all we can afford.
        self._max_retries = 1
        self._max_backoff_seconds = 5
        # Step A: serialize concurrent CJ calls. Without this lock, multiple
        # parallel callers race past `_rate_limit_wait()` simultaneously and
        # trigger a 429 cascade. Lock is async and created lazily so __init__
        # works outside an event loop.
        self._request_lock: Optional[asyncio.Lock] = None

        if self._available:
            logger.info("[SUCCESS] CJ Dropshipping client initialized (serialized, rate limit: 0.33 req/sec)")
        else:
            logger.warning("[WARNING] CJ Dropshipping: CJ_ACCESS_TOKEN not configured")

    def _get_lock(self) -> asyncio.Lock:
        """Lazily create the async lock on first use (inside a running loop)."""
        if self._request_lock is None:
            self._request_lock = asyncio.Lock()
        return self._request_lock
    
    def is_available(self) -> bool:
        return self._available
    
    async def _rate_limit_wait(self):
        """Ensure we don't exceed rate limit with exponential backoff for 429s.

        NOTE: Must be called while holding `_request_lock` (step A) so that
        concurrent callers queue rather than race past the timestamp check.
        """
        now = time.time()
        time_since_last = now - self._last_request_time

        # Base delay
        delay = self._rate_limit_delay

        # Step C: bounded backoff. Previously used 2^n capped at 30s, which
        # could burn 30s on a single call. Now capped at `_max_backoff_seconds`
        # (5s) so we fail fast instead of hanging the whole request.
        if self._consecutive_429s > 0:
            delay = delay * (2 ** self._consecutive_429s)
            delay = min(delay, self._max_backoff_seconds)
            logger.debug(f"[RATE_LIMIT] Backoff delay: {delay:.1f}s (consecutive 429s: {self._consecutive_429s})")

        if time_since_last < delay:
            wait_time = delay - time_since_last
            logger.debug(f"[RATE_LIMIT] Waiting {wait_time:.2f}s before CJ request")
            await asyncio.sleep(wait_time)

        self._last_request_time = time.time()
    
    async def _request(self, endpoint: str, params: dict = None) -> Optional[Dict]:
        """
        Make authenticated GET request to CJ API.

        NOTE: CJ API v2.0 uses GET for all read operations.

        Serialized via `_request_lock` (step A) so concurrent discovery tasks
        don't race through the rate limiter.
        """
        if not self._available:
            logger.warning("[WARNING] CJ client not available - no token")
            return None

        # Step A: serialize CJ calls. Only one request in-flight at a time.
        async with self._get_lock():
            return await self._request_locked(endpoint, params)

    async def _request_locked(self, endpoint: str, params: dict = None) -> Optional[Dict]:
        """Inner request implementation. Assumes `_request_lock` is held."""
        # Rate limiting
        await self._rate_limit_wait()

        url = f"{CJ_API_BASE}/{endpoint}"
        headers = {
            "CJ-Access-Token": self.access_token,
        }

        # Shorter HTTP timeout (was 30s — too long given our 12s per-source cap)
        http_timeout = 10

        try:
            async with aiohttp.ClientSession() as session:
                logger.debug(f"[DEBUG] CJ API GET {endpoint}")
                logger.debug(f"[DEBUG] Params: {params}")

                async with session.get(url, headers=headers, params=params, timeout=http_timeout) as response:
                    response_text = await response.text()

                    if response.status == 429:
                        self._consecutive_429s += 1
                        # Step C: backoff capped at `_max_backoff_seconds` (5s)
                        # so a single 429 can't stall us for 30s anymore.
                        backoff = min(2 ** self._consecutive_429s, self._max_backoff_seconds)
                        logger.warning(
                            f"[WARNING] CJ rate limit hit (429) - backing off {backoff}s "
                            f"(attempt {self._consecutive_429s}/{self._max_retries})"
                        )
                        await asyncio.sleep(backoff)

                        # Step C: max_retries=1, so one retry at most
                        if self._consecutive_429s <= self._max_retries:
                            return await self._request_locked(endpoint, params)  # retry (lock still held)
                        else:
                            logger.error("[ERROR] CJ max retries exceeded - giving up")
                            return None

                    if response.status == 200:
                        # Reset backoff counter on success
                        self._consecutive_429s = 0

                        try:
                            result = await response.json()
                        except (json.JSONDecodeError, aiohttp.ContentTypeError):
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
            logger.error(f"[ERROR] CJ API HTTP timeout ({http_timeout}s)")
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

    async def smart_search(self, query: str, page_size: int = 20) -> List[Dict]:
        """
        Smart search that uses keyword mappings for better CJ API results.

        CJ's productNameEn search needs simple, specific keywords.
        This method:
        1. Maps user queries to CJ-friendly search terms
        2. Searches by category when available
        3. Tries multiple keywords and combines results

        Args:
            query: User's search query (e.g., "smart home gadgets")
            page_size: Max products to return

        Returns:
            List of normalized products (deduplicated)
        """
        if not self._available:
            return []

        query_lower = query.lower().strip()
        all_products = []
        seen_pids = set()

        # 1. Check if we have a direct keyword mapping
        mapping = self.KEYWORD_MAP.get(query_lower)

        if mapping:
            logger.info(f"[INFO] CJ smart search: '{query}' -> mapped keywords + category")

            # Search by category first (most reliable)
            if mapping.get('category'):
                cat_products = await self.search_products(
                    keyword="",
                    category_id=mapping['category'],
                    page_size=page_size
                )
                for p in cat_products:
                    # Normalized CJ products expose `product_id` (prefix "cj_") and `cj_pid`.
                    # The old keys `source_id`/`name` never exist, so every product
                    # deduped to '' and 10 results collapsed to 1 unique product.
                    pid = p.get('product_id') or p.get('cj_pid') or p.get('title') or ''
                    if pid not in seen_pids:
                        seen_pids.add(pid)
                        all_products.append(p)

            # Then try first mapped keyword only (to avoid rate limiting)
            for kw in mapping.get('keywords', [])[:1]:
                if len(all_products) >= page_size:
                    break
                kw_products = await self.search_products(
                    keyword=kw,
                    page_size=min(10, page_size - len(all_products))
                )
                for p in kw_products:
                    # Normalized CJ products expose `product_id` (prefix "cj_") and `cj_pid`.
                    # The old keys `source_id`/`name` never exist, so every product
                    # deduped to '' and 10 results collapsed to 1 unique product.
                    pid = p.get('product_id') or p.get('cj_pid') or p.get('title') or ''
                    if pid not in seen_pids:
                        seen_pids.add(pid)
                        all_products.append(p)

        else:
            # 2. No mapping - try to infer category from query words
            for word in query_lower.split():
                # Check if any word matches a niche category
                if word in self.CATEGORY_MAP:
                    logger.info(f"[INFO] CJ: Found category '{word}' in query")
                    cat_products = await self.search_products(
                        keyword="",
                        category_id=self.CATEGORY_MAP[word],
                        page_size=page_size
                    )
                    for p in cat_products:
                        # Normalized CJ products expose `product_id` (prefix "cj_") and `cj_pid`.
                        # The old keys `source_id`/`name` never exist, so every product
                        # deduped to '' and 10 results collapsed to 1 unique product.
                        pid = p.get('product_id') or p.get('cj_pid') or p.get('title') or ''
                        if pid not in seen_pids:
                            seen_pids.add(pid)
                            all_products.append(p)
                    break

            # 3. Try first significant word as keyword (limit to 1 to avoid rate limits)
            if len(all_products) < page_size:
                words = [w for w in query_lower.split() if len(w) > 3]  # Longer words only
                for word in words[:1]:  # Only try 1 word to avoid rate limits
                    if len(all_products) >= page_size:
                        break
                    kw_products = await self.search_products(
                        keyword=word,
                        page_size=min(10, page_size - len(all_products))
                    )
                    for p in kw_products:
                        # Normalized CJ products expose `product_id` (prefix "cj_") and `cj_pid`.
                        # The old keys `source_id`/`name` never exist, so every product
                        # deduped to '' and 10 results collapsed to 1 unique product.
                        pid = p.get('product_id') or p.get('cj_pid') or p.get('title') or ''
                        if pid not in seen_pids:
                            seen_pids.add(pid)
                            all_products.append(p)

        logger.info(f"[SUCCESS] CJ smart search '{query}': {len(all_products)} unique products")
        return all_products[:page_size]
    
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
    
    def _parse_price(self, price_value) -> float:
        """
        Parse price, handling various formats from CJ API:
        - Simple numbers: 50.00, 320
        - Double dash ranges: '8.28 -- 13.25'
        - Single dash ranges: '50.00-320.00', '400.00 - 520.00'
        - Multiple dash ranges: '50.00-250.00-320.00'
        - Currency symbols: '$50.00', '€30.00'

        Always returns the LOWEST price from a range.
        """
        import re

        try:
            # If already a number, return it
            if isinstance(price_value, (int, float)):
                return float(price_value)

            # Convert to string and clean
            price_str = str(price_value).strip()

            # Handle empty strings
            if not price_str:
                return 0.0

            # Remove currency symbols and whitespace
            price_str = re.sub(r'[£$€¥₹]', '', price_str).strip()

            # Strategy 1: Extract ALL numbers from the string using regex
            # This handles ANY format including '50.00-320.00', '50.00 -- 320.00', etc.
            numbers = re.findall(r'\d+\.?\d*', price_str)

            if numbers:
                # Convert all found numbers to floats
                prices = []
                for num_str in numbers:
                    try:
                        price = float(num_str)
                        if price > 0:  # Only include positive prices
                            prices.append(price)
                    except ValueError:
                        continue

                if prices:
                    # Return the LOWEST price (best deal for comparison)
                    return min(prices)

            # Strategy 2: Try direct conversion as fallback
            try:
                return float(price_str)
            except ValueError:
                pass

            # No valid price found
            logger.debug(f"[DEBUG] Could not parse price: '{price_value}'")
            return 0.0

        except Exception as e:
            logger.debug(f"[DEBUG] Price parsing error for '{price_value}': {e}")
            return 0.0

    def _normalize_product(self, item: dict) -> Optional[Dict]:
        """Normalize CJ product data to standard format with ALL images"""
        try:
            # Get price - CJ uses sellPrice for our cost (handles price ranges)
            cost_price = self._parse_price(item.get('sellPrice') or item.get('productPrice') or 0)
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
                "weight": self._parse_price(item.get('productWeight', 0)),  # Reuse price parser for weight ranges

                # Task #22: CJ doesn't expose reviews/ratings publicly, but
                # defensively capture any popularity-adjacent fields the
                # `/product/list` response *might* include across API
                # versions. These feed into the CJ supplier-quality proxy
                # signal used for CJ-only products with no Amazon match.
                "listed_num": (
                    item.get('listedNum')
                    or item.get('listedNumber')
                    or item.get('sellerNumber')
                    or None
                ),
                "recommended_level": (
                    item.get('recommendedLevel')
                    or item.get('recommendedGrade')
                    or None
                ),
                "hot_product_flag": bool(
                    item.get('hotProduct')
                    or item.get('isHot')
                    or False
                ),
                
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
