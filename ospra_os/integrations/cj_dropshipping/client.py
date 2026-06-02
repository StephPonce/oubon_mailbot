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
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

CJ_API_BASE = "https://developers.cjdropshipping.com/api2.0/v1"

# Task #36: live CATEGORY_MAP cache. The hard-coded `CJDropshippingClient.CATEGORY_MAP`
# below was hand-curated against a snapshot of CJ's category IDs that has since
# drifted — half the IDs return zero products. We now also refresh from CJ's
# `/product/getCategory` endpoint at most once per `CJ_CATEGORY_REFRESH_SECONDS`
# and persist the flattened name→id index here so subsequent boots use the
# live snapshot. The hard-coded map stays in place as a fallback.
CJ_CATEGORY_CACHE_DIR = Path(os.getenv("OSPRA_CACHE_DIR", "/tmp/ospra_cache"))
CJ_CATEGORY_CACHE_FILE = CJ_CATEGORY_CACHE_DIR / "cj_categories.json"
CJ_CATEGORY_REFRESH_SECONDS = 7 * 24 * 60 * 60  # 7 days


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

        # Task #36: live category index loaded from disk cache (populated by
        # `refresh_category_map()`). `None` until first lookup; lookups fall
        # back to the hard-coded CATEGORY_MAP / KEYWORD_MAP when this is
        # empty or doesn't contain the niche.
        self._dynamic_category_map: Optional[Dict[str, str]] = None
        self._dynamic_category_loaded_at: Optional[float] = None

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
        # Task #36: use live CJ map first, fall back to hard-coded snapshot
        category_id = self._get_category_id(niche)

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

        def _add(products: List[Dict]) -> None:
            # Normalized CJ products expose `product_id` (prefix "cj_") and `cj_pid`.
            for p in products:
                pid = p.get('product_id') or p.get('cj_pid') or p.get('title') or ''
                if pid and pid not in seen_pids:
                    seen_pids.add(pid)
                    all_products.append(p)

        # ── KEYWORD-FIRST ────────────────────────────────────────────────
        # CJ's /product/getCategory has been returning an EMPTY category list
        # (verified via scripts/diagnose_cj.py: category 1489 → 0 products,
        # keyword "smart plug" → 10). Leading with category therefore wasted
        # the reliable request slot and often returned nothing. Keyword search
        # (productNameEn) is the working path, so we lead with it and use the
        # SPECIFIC mapped phrases (e.g. "smart plug", "wifi plug") rather than
        # splitting into broad single words like "smart" (which match junk).
        mapping = self.KEYWORD_MAP.get(query_lower)
        if mapping and mapping.get('keywords'):
            keywords = list(mapping['keywords'])
        else:
            # Full phrase first (most specific), then longer single words.
            keywords = [query_lower] + [w for w in query_lower.split() if len(w) > 3]

        # De-dupe preserving order; cap at 3 keyword calls to respect rate limits.
        _seen_kw: set = set()
        keywords = [k for k in keywords if k and not (k in _seen_kw or _seen_kw.add(k))][:3]

        logger.info(f"[INFO] CJ smart search: '{query}' -> keyword-first {keywords}")
        for kw in keywords:
            if len(all_products) >= page_size:
                break
            remaining = page_size - len(all_products)
            _add(await self.search_products(keyword=kw, page_size=min(20, remaining)))

        # ── CATEGORY as best-effort SUPPLEMENT ──────────────────────────
        # Usually empty today, but kept so a future CATEGORY_MAP refresh
        # transparently adds coverage without another code change.
        if len(all_products) < page_size:
            cat_id = mapping.get('category') if mapping else None
            if not cat_id:
                for word in query_lower.split():
                    cat_id = self._get_category_id(word)
                    if cat_id:
                        break
            if cat_id:
                remaining = page_size - len(all_products)
                _add(await self.search_products(keyword="", category_id=cat_id, page_size=remaining))

        logger.info(f"[SUCCESS] CJ smart search '{query}': {len(all_products)} unique products (keyword-first)")
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

    # ------------------------------------------------------------------
    # Task #36: dynamic CATEGORY_MAP refresh
    # ------------------------------------------------------------------
    # The hard-coded `CATEGORY_MAP` above was hand-curated and has drifted
    # away from CJ's live category tree (smart_home → 1489 returns 0
    # products as of the 2026-04 audit). The methods below pull the live
    # tree from `/product/getCategory`, flatten it to a name → id index,
    # persist it to `CJ_CATEGORY_CACHE_FILE`, and use it as the primary
    # lookup with the hard-coded map as a fallback for niches the live
    # tree doesn't carry the same name for.

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Lowercase and collapse to alpha+underscore so 'Smart Home' ==
        'smart_home' == 'smart-home' == 'smart  home'."""
        if not name:
            return ""
        n = name.strip().lower()
        # Replace separators with underscore
        for ch in (" ", "-", "/", "&", ",", "."):
            n = n.replace(ch, "_")
        # Collapse repeats
        while "__" in n:
            n = n.replace("__", "_")
        return n.strip("_")

    def _walk_category_tree(self, nodes, out: Dict[str, str]) -> None:
        """Defensively walk CJ's category response and emit (name → id)
        pairs at every depth. Handles several response shapes seen in the
        wild (first/second/third-level keys, generic id/name/children)."""
        if not nodes:
            return
        if isinstance(nodes, dict):
            nodes = [nodes]
        if not isinstance(nodes, list):
            return

        for node in nodes:
            if not isinstance(node, dict):
                continue

            # Try every known key naming for (id, name) at each depth.
            for id_key, name_key, children_key in (
                ("categoryFirstId", "categoryFirstName", "categoryFirstList"),
                ("categorySecondId", "categorySecondName", "categorySecondList"),
                ("categoryThirdId", "categoryThirdName", "categoryThirdList"),
                ("categoryId", "categoryName", "children"),
                ("id", "name", "children"),
            ):
                cid = node.get(id_key)
                cname = node.get(name_key)
                if cid and cname:
                    norm = self._normalize_name(str(cname))
                    if norm and norm not in out:
                        out[norm] = str(cid)
                if children_key in node:
                    self._walk_category_tree(node.get(children_key), out)

    def _load_cached_category_map(self) -> Optional[Dict[str, str]]:
        """Read the persisted name→id index from disk. Returns None if
        missing or unparseable."""
        try:
            if not CJ_CATEGORY_CACHE_FILE.exists():
                return None
            with CJ_CATEGORY_CACHE_FILE.open("r") as fh:
                payload = json.load(fh)
            if not isinstance(payload, dict):
                return None
            mapping = payload.get("map")
            saved_at = payload.get("saved_at")
            if not isinstance(mapping, dict):
                return None
            self._dynamic_category_loaded_at = float(saved_at) if saved_at else None
            return {str(k): str(v) for k, v in mapping.items()}
        except Exception as exc:
            logger.warning(f"[CJ-CAT] Failed to load cached category map: {exc}")
            return None

    def _save_cached_category_map(self, mapping: Dict[str, str]) -> None:
        """Persist the flattened name→id index alongside a timestamp."""
        try:
            CJ_CATEGORY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                "saved_at": time.time(),
                "saved_at_iso": datetime.now(timezone.utc).isoformat(),
                "entry_count": len(mapping),
                "map": mapping,
            }
            with CJ_CATEGORY_CACHE_FILE.open("w") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            logger.info(
                f"[CJ-CAT] Cached {len(mapping)} CJ categories to "
                f"{CJ_CATEGORY_CACHE_FILE}"
            )
        except Exception as exc:
            logger.warning(f"[CJ-CAT] Failed to write category cache: {exc}")

    async def refresh_category_map(self, force: bool = False) -> Dict[str, str]:
        """Pull `/product/getCategory` and rebuild the dynamic name→id
        index. Persists to `CJ_CATEGORY_CACHE_FILE` and updates the
        in-memory `_dynamic_category_map`. Idempotent — repeated calls
        within `CJ_CATEGORY_REFRESH_SECONDS` short-circuit unless
        `force=True`."""
        if not self._available:
            logger.warning("[CJ-CAT] Cannot refresh — CJ token not configured")
            return self._dynamic_category_map or {}

        # Honour the TTL unless caller forces a refresh
        if not force and self._dynamic_category_loaded_at:
            age = time.time() - self._dynamic_category_loaded_at
            if age < CJ_CATEGORY_REFRESH_SECONDS:
                logger.debug(
                    f"[CJ-CAT] Skipping refresh — cache is {age/3600:.1f}h old "
                    f"(refresh interval: {CJ_CATEGORY_REFRESH_SECONDS/3600:.0f}h)"
                )
                return self._dynamic_category_map or {}

        logger.info("[CJ-CAT] Refreshing CJ CATEGORY_MAP from /product/getCategory")
        raw = await self.get_categories()
        if not raw:
            logger.warning("[CJ-CAT] /getCategory returned no data — keeping existing map")
            return self._dynamic_category_map or {}

        mapping: Dict[str, str] = {}
        self._walk_category_tree(raw, mapping)

        if not mapping:
            logger.warning("[CJ-CAT] Could not parse category tree — keeping existing map")
            return self._dynamic_category_map or {}

        self._dynamic_category_map = mapping
        self._dynamic_category_loaded_at = time.time()
        self._save_cached_category_map(mapping)
        logger.info(
            f"[CJ-CAT] Built dynamic CJ category index with {len(mapping)} entries"
        )
        return mapping

    def _get_category_id(self, niche: str) -> Optional[str]:
        """Resolve a niche keyword to a CJ categoryId. Checks the
        dynamic map first (loaded from disk on demand), then falls
        through to the hard-coded `CATEGORY_MAP`. Returns None if no
        match exists in either layer."""
        if not niche:
            return None

        # Lazy-load the disk cache once per process
        if self._dynamic_category_map is None:
            cached = self._load_cached_category_map()
            if cached is not None:
                self._dynamic_category_map = cached
                logger.debug(
                    f"[CJ-CAT] Loaded {len(cached)} cached CJ categories from disk"
                )

        # Try a few normalisations against the dynamic map
        if self._dynamic_category_map:
            for candidate in (
                self._normalize_name(niche),
                self._normalize_name(niche.replace("_", " ")),
                niche.lower(),
            ):
                cid = self._dynamic_category_map.get(candidate)
                if cid:
                    return cid

        # Fallback: hard-coded map (legacy snapshot of CJ IDs)
        return self.CATEGORY_MAP.get(niche.lower())
    
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
