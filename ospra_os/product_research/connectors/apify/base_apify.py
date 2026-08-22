"""
Apify Integration - REAL API Calls for Amazon & TikTok Data
============================================================

Uses your $39/month Apify subscription for:
- Amazon Bestsellers scraping
- Amazon Product search
- TikTok trending products
- TikTok hashtag search

NO MOCK DATA. REAL API CALLS ONLY.
"""
import os
import asyncio
import logging
import httpx
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ===========================================================================
# Per-run Apify circuit breaker + spend tracking (SaaS cost brief)
# ===========================================================================
# Stops the retry storms the logs showed: once an actor returns quota/403
# failures >= threshold in a run, it's "tripped" and skipped for the rest of
# the run (no more actor-starts → no more metered cost / cap hammering).
# State is process-global, which == per-run for the catalog-warm cron (fresh
# process each run); call reset_apify_budget() at run start to be explicit.
_APIFY_BREAKER_THRESHOLD = int(os.getenv("APIFY_BREAKER_THRESHOLD", "2"))
_apify_run_state = {"starts": 0, "fails_by_actor": {}, "tripped": set(),
                    "starts_by_actor": {}}

# HARD PER-RUN START CEILING (2026-08). The circuit breaker only trips on
# quota/403 FAILURES — it cannot stop an actor that keeps SUCCEEDING while
# billing per result. That is exactly how trakk/tiktok-shop-search-scraper
# burned $8.42 in 18 runs: every run succeeded, so nothing tripped.
#
# This caps how many times ONE actor may start within a single process (a cron
# run, or one web-process lifetime). It is a backstop against a loop or a
# caching regression, not a substitute for either.
_APIFY_MAX_STARTS_PER_ACTOR = int(os.getenv("APIFY_MAX_STARTS_PER_ACTOR", "12"))


def reset_apify_budget() -> None:
    """Reset per-run Apify counters (call at the start of a cron run)."""
    _apify_run_state["starts"] = 0
    _apify_run_state["fails_by_actor"] = {}
    _apify_run_state["tripped"] = set()
    _apify_run_state["starts_by_actor"] = {}
    try:
        from ospra_os.product_research.connectors.apify import response_cache
        response_cache.reset_cache_stats()
    except Exception:
        pass


def apify_actor_tripped(actor_id: str) -> bool:
    return actor_id in _apify_run_state["tripped"]


def _record_apify_quota_fail(actor_id: str) -> None:
    c = _apify_run_state["fails_by_actor"].get(actor_id, 0) + 1
    _apify_run_state["fails_by_actor"][actor_id] = c
    if c >= _APIFY_BREAKER_THRESHOLD and actor_id not in _apify_run_state["tripped"]:
        _apify_run_state["tripped"].add(actor_id)
        logger.warning(
            f"[APIFY BREAKER] {actor_id} tripped after {c} quota/403 failures — "
            f"skipping for the rest of this run"
        )


def get_apify_budget_report() -> Dict:
    """Per-run spend proxy: actor-start count drives metered cost. The cache
    counters show how many metered starts the response cache avoided."""
    report = {
        "actor_starts": _apify_run_state["starts"],
        "quota_failures": dict(_apify_run_state["fails_by_actor"]),
        "tripped_actors": sorted(_apify_run_state["tripped"]),
        "starts_by_actor": dict(_apify_run_state["starts_by_actor"]),
    }
    try:
        from ospra_os.product_research.connectors.apify import response_cache
        report.update(response_cache.get_cache_stats())
    except Exception:
        report.update({"cache_hits": 0, "cache_misses": 0, "stale_served": 0})
    return report


@dataclass
class ApifyProduct:
    """Product data from Apify scraper"""
    name: str
    price: float
    source: str
    url: str = ""
    image_url: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    asin: str = ""
    bestseller_rank: int = 0
    category: str = ""
    in_stock: bool = True
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'price': self.price,
            'source': self.source,
            'url': self.url,
            'image_url': self.image_url,
            'rating': self.rating,
            'reviews_count': self.reviews_count,
            'asin': self.asin,
            'bestseller_rank': self.bestseller_rank,
            'category': self.category,
            'in_stock': self.in_stock,
        }


class ApifyClient:
    """
    Production Apify Client - REAL API calls
    
    Your subscription: $39/month
    Actors available:
    - junglee/amazon-bestsellers (Amazon bestsellers by category)
    - apify/amazon-crawler (Full Amazon product search)
    - clockworks/tiktok-scraper (TikTok videos & hashtags)
    """
    
    # Popular Apify actors for e-commerce.
    #
    # Actor IDs are env-overridable. ``amazon_search`` has NO default because
    # every public free Amazon keyword-search actor we vetted requires a
    # FLAT_PRICE_PER_MONTH rental (epctex/amazon-scraper = $40/mo,
    # apify/amazon-crawler = 404 / removed). To keep Ospra free of rental
    # surprises the default is empty — when unset, ``search_amazon`` returns
    # an empty list and the Amazon-reviews matcher reports ``empty_pool``
    # honestly instead of secretly tripping a rental.
    #
    # To re-enable Amazon search, set ``APIFY_AMAZON_SEARCH_ACTOR`` to a
    # PAY_PER_EVENT actor you have access to (e.g. a rented epctex actor).
    ACTORS = {
        'amazon_bestsellers': os.getenv('APIFY_AMAZON_BESTSELLERS_ACTOR', 'junglee/amazon-bestsellers'),
        'amazon_search': os.getenv('APIFY_AMAZON_SEARCH_ACTOR', ''),
        'tiktok_scraper': os.getenv('APIFY_TIKTOK_SCRAPER_ACTOR', 'clockworks/tiktok-scraper'),
        'tiktok_hashtag': os.getenv('APIFY_TIKTOK_HASHTAG_ACTOR', 'clockworks/tiktok-hashtag-scraper'),
    }
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Apify client
        
        Args:
            api_token: Apify API token. If None, reads from APIFY_API_TOKEN env var.
        """
        self.api_token = api_token or os.getenv('APIFY_API_TOKEN')
        self.base_url = "https://api.apify.com/v2"
        
        if not self.api_token:
            raise ValueError("APIFY_API_TOKEN not set. Get yours at https://console.apify.com/account/integrations")
        
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
        
        print(f"[SUCCESS] Apify client initialized (token: {self.api_token[:10]}...)")
    
    def is_available(self) -> bool:
        """Check if Apify is configured"""
        return bool(self.api_token)
    
    async def test_connection(self) -> Dict:
        """Test API connection and get account info"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/users/me",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()['data']
                    return {
                        'connected': True,
                        'username': data.get('username', 'unknown'),
                        'email': data.get('email', 'unknown'),
                        'plan': data.get('plan', {}).get('id', 'unknown'),
                    }
                else:
                    return {
                        'connected': False,
                        'error': f"HTTP {response.status_code}: {response.text}"
                    }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }

    async def get_account_usage(self) -> Dict:
        """
        Get current account usage and remaining budget.

        Apify has TWO types of credits:
        1. Subscription credits (monthlyUsageCreditsUsd) - Monthly allocation
        2. Prepaid credits (prepaidUsd) - One-time purchased credits

        Returns dict with:
        - remaining_usd: Total remaining (subscription + prepaid)
        - used_usd: Amount used this billing period
        - plan: Current plan name
        - can_run_paid_actors: True if enough credits for paid actors
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get user info with plan details
                response = await client.get(
                    f"{self.base_url}/users/me",
                    headers=self.headers
                )

                if response.status_code != 200:
                    return {'error': f"HTTP {response.status_code}"}

                data = response.json().get('data', {})
                plan = data.get('plan', {})

                # Debug: print raw response to see actual fields
                # print(f"[DEBUG] Apify user data keys: {list(data.keys())}")
                # print(f"[DEBUG] Apify plan data: {plan}")

                # Get subscription limit (if on paid plan)
                monthly_limit = plan.get('monthlyUsageCreditsUsd', 0)

                # Get prepaid balance - Apify uses multiple possible field names
                # Check all possible fields for prepaid/available balance
                prepaid_usd = (
                    data.get('prepaidUsd', 0) or
                    data.get('availableUsd', 0) or
                    data.get('prepaidBalance', 0) or
                    data.get('balance', 0) or
                    plan.get('prepaidUsd', 0) or
                    0
                )

                # Also check the proxy field which sometimes contains balance info
                proxy_info = data.get('proxy', {})
                if isinstance(proxy_info, dict):
                    proxy_balance = proxy_info.get('availableUsd', 0)
                    if proxy_balance > prepaid_usd:
                        prepaid_usd = proxy_balance

                # Get current usage
                usage_response = await client.get(
                    f"{self.base_url}/users/me/usage/monthly",
                    headers=self.headers
                )

                used_usd = 0
                if usage_response.status_code == 200:
                    usage_data = usage_response.json().get('data', {})
                    used_usd = usage_data.get('usageCreditsUsedUsd', 0)

                # Calculate remaining from subscription
                subscription_remaining = max(0, monthly_limit - used_usd)

                # Total available = subscription remaining + prepaid
                total_remaining = subscription_remaining + prepaid_usd

                return {
                    'remaining_usd': round(total_remaining, 2),
                    'used_usd': round(used_usd, 2),
                    'monthly_limit_usd': monthly_limit,
                    'subscription_remaining_usd': round(subscription_remaining, 2),
                    'prepaid_usd': round(prepaid_usd, 2),
                    'plan': plan.get('id', 'unknown'),
                    'can_run_paid_actors': total_remaining > 1.0,  # Need at least $1 for paid actors
                }

        except Exception as e:
            print(f"[WARNING] Could not check Apify usage: {e}")
            return {'error': str(e), 'can_run_paid_actors': False}
    
    # Dataset items are fetched in pages of this size (Apify max per request
    # is 1000). Phase-1 fix: the old code did ONE request with limit=100, so
    # any run producing more than 100 items silently lost the rest.
    DATASET_PAGE_SIZE = 1000

    async def run_actor(
        self,
        actor_id: str,
        run_input: Dict,
        timeout_secs: int = 300,
        memory_mbytes: int = 512,
        max_items: Optional[int] = None,
    ) -> List[Dict]:
        """Run an Apify actor, served from the response cache when possible.

        Cache policy lives in ``response_cache`` (per-actor TTL; Google Trends
        deliberately bypassed because trend_warm exists to fetch fresh trends).

        On any live failure we fall back to an EXPIRED entry rather than
        returning nothing — a stale winner-proof signal beats no signal — and
        the items carry a marker so scoring downgrades confidence instead of
        treating the signal as absent.
        """
        from ospra_os.product_research.connectors.apify import response_cache

        hit = response_cache.get(actor_id, run_input, max_items)
        if hit is not None:
            age_h = (datetime.utcnow() - hit.fetched_at).total_seconds() / 3600.0
            print(
                f"[APIFY CACHE] hit {actor_id} "
                f"({len(hit.items)} items, age {age_h:.1f}h)"
            )
            return hit.items

        # Circuit breaker: this actor already hit quota/403 this run. Prefer a
        # stale answer over nothing — this is the exact outage the cache is for.
        if apify_actor_tripped(actor_id):
            stale = response_cache.get(
                actor_id, run_input, max_items, allow_stale=True
            )
            if stale is not None:
                print(f"[APIFY BREAKER] {actor_id} tripped — serving stale cache")
                return response_cache.stamp_stale(stale.items, stale.fetched_at)
            print(f"[APIFY BREAKER] skipping {actor_id} (tripped this run)")
            return []

        _starts = _apify_run_state["starts_by_actor"].get(actor_id, 0)
        if _starts >= _APIFY_MAX_STARTS_PER_ACTOR:
            logger.warning(
                "[APIFY BUDGET] %s hit the per-run start ceiling (%d) — "
                "refusing further starts this run. Raise "
                "APIFY_MAX_STARTS_PER_ACTOR only if this is expected.",
                actor_id, _APIFY_MAX_STARTS_PER_ACTOR,
            )
            stale = response_cache.get(actor_id, run_input, max_items, allow_stale=True)
            if stale is not None:
                return response_cache.stamp_stale(stale.items, stale.fetched_at)
            return []

        items, ok = await self._run_actor_live(
            actor_id, run_input, timeout_secs, memory_mbytes, max_items
        )
        if ok:
            # A SUCCEEDED run with zero rows is a real answer ("no ads for this
            # keyword"), so it is cached too — at the shorter empty TTL.
            response_cache.put(actor_id, run_input, max_items, items)
            return items

        stale = response_cache.get(actor_id, run_input, max_items, allow_stale=True)
        if stale is not None:
            return response_cache.stamp_stale(stale.items, stale.fetched_at)
        return items

    async def _run_actor_live(
        self,
        actor_id: str,
        run_input: Dict,
        timeout_secs: int = 300,
        memory_mbytes: int = 512,
        max_items: Optional[int] = None,
    ) -> tuple:
        """Live actor run. Returns ``(items, ok)``; ok=False means the run did
        not succeed (start rejected, FAILED/ABORTED, timeout, or exception).
        An empty list with ok=True is a legitimate "no results" answer.

        Args:
            actor_id: Actor ID (e.g., "junglee/amazon-bestsellers")
            run_input: Input configuration for the actor
            timeout_secs: Max seconds to wait (default 5 minutes)
            memory_mbytes: Memory allocation (higher = faster but more expensive)
            max_items: Cap on how many dataset items to fetch (None = all).
                Use a LOW cap while developing to conserve Apify credits.

        Returns:
            ``(items, ok)`` — see summary above.

        Phase-1 (TikTok demand spine) fixes:
          * ``memory`` used to be merged INTO the actor input JSON. Apify reads
            run options (memory/timeout) from QUERY PARAMS on the run-start
            request — inside the input it is ignored for provisioning and, on
            actors with strict input schemas, rejects the run outright. It is
            now sent as ``?memory=...&timeout=...``.
          * results were fetched with a single ``limit=100`` request, silently
            dropping everything past 100. Now paginated until exhausted (or
            ``max_items``).
        """
        # NOTE: the circuit-breaker check lives in run_actor (the caller), so a
        # tripped actor can still be answered from stale cache instead of [].

        # Convert actor ID format for API
        actor_id_safe = actor_id.replace('/', '~')

        print(f"[START] Starting Apify actor: {actor_id}")
        print(f"   Input: {run_input}")

        try:
            async with httpx.AsyncClient(timeout=timeout_secs) as client:
                # Start the actor run. Run OPTIONS go in query params; the
                # body is the actor input alone.
                run_url = f"{self.base_url}/acts/{actor_id_safe}/runs"

                _apify_run_state["starts"] += 1
                _sba = _apify_run_state["starts_by_actor"]
                _sba[actor_id] = _sba.get(actor_id, 0) + 1
                response = await client.post(
                    run_url,
                    headers=self.headers,
                    params={
                        "memory": memory_mbytes,
                        "timeout": timeout_secs,
                    },
                    json=run_input,
                )

                if response.status_code not in [200, 201]:
                    # Quota/permission failures feed the breaker so repeated
                    # cap hits trip the actor instead of retrying all run.
                    body = (response.text or "")[:300].lower()
                    if response.status_code in (402, 403, 429) or "quota" in body or "limit" in body or "exceeded" in body:
                        _record_apify_quota_fail(actor_id)
                    print(f"[ERROR] Failed to start actor: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return [], False

                run_data = response.json()['data']
                run_id = run_data['id']

                print(f"   Run ID: {run_id}")
                print(f"   Waiting for completion...")

                # Poll for completion
                status_url = f"{self.base_url}/actor-runs/{run_id}"

                poll_interval = 5
                max_polls = timeout_secs // poll_interval

                for attempt in range(max_polls):
                    await asyncio.sleep(poll_interval)

                    status_response = await client.get(status_url, headers=self.headers)
                    status_data = status_response.json()['data']
                    status = status_data['status']

                    if status == "SUCCEEDED":
                        dataset_id = status_data['defaultDatasetId']
                        results = await self._fetch_dataset_items(
                            client, dataset_id, max_items=max_items
                        )
                        print(f"[SUCCESS] Actor completed! Got {len(results)} results")
                        return results, True

                    elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                        print(f"[ERROR] Actor {status}: {actor_id}")
                        return [], False

                    # Still running
                    elapsed = (attempt + 1) * poll_interval
                    if elapsed % 30 == 0:
                        print(f"   Still running... ({elapsed}s)")

                # Log the run ID so an abandoned-but-still-charging run is
                # traceable in the Apify console (results may finish later).
                print(
                    f"[ALARM] Timeout after {timeout_secs}s waiting for {actor_id} "
                    f"(run_id={run_id}, last status={status} — run continues "
                    f"server-side; check the Apify console for its results)"
                )
                return [], False

        except Exception as e:
            print(f"[ERROR] Error running actor {actor_id}: {e}")
            import traceback
            traceback.print_exc()
            return [], False

    async def _fetch_dataset_items(
        self,
        client: "httpx.AsyncClient",
        dataset_id: str,
        max_items: Optional[int] = None,
    ) -> List[Dict]:
        """Fetch ALL items from a run's dataset, paginating past the old
        100-item ceiling. ``max_items`` caps the total (dev credit hygiene)."""
        results_url = f"{self.base_url}/datasets/{dataset_id}/items"
        items: List[Dict] = []

        while True:
            page_limit = self.DATASET_PAGE_SIZE
            if max_items is not None:
                remaining = max_items - len(items)
                if remaining <= 0:
                    break
                page_limit = min(page_limit, remaining)

            response = await client.get(
                results_url,
                headers=self.headers,
                params={"offset": len(items), "limit": page_limit},
            )
            page = response.json()
            if not isinstance(page, list):
                print(f"   [WARNING] Unexpected dataset response shape: {type(page)}")
                break

            items.extend(page)
            if len(page) < page_limit:
                break  # short page → dataset exhausted

        return items
    
    async def get_amazon_bestsellers(
        self,
        category: str = "Home & Kitchen",
        country: str = "US",
        max_items: int = 20
    ) -> List[ApifyProduct]:
        """
        Get Amazon bestsellers for a category
        
        Popular categories for dropshipping:
        - "Home & Kitchen"
        - "Electronics"
        - "Sports & Outdoors"
        - "Beauty & Personal Care"
        - "Toys & Games"
        - "Pet Supplies"
        """
        print(f"[TOP] Fetching Amazon bestsellers: {category}")
        
        results = await self.run_actor(
            actor_id=self.ACTORS['amazon_bestsellers'],
            run_input={
                "categoryUrls": [
                    f"https://www.amazon.com/Best-Sellers-{category.replace(' ', '-').replace('&', '')}/zgbs"
                ],
                "maxItems": max_items,
                "proxy": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": ["RESIDENTIAL"]
                }
            },
            timeout_secs=180
        )
        
        products = []
        for item in results:
            try:
                product = ApifyProduct(
                    name=item.get('title', item.get('name', 'Unknown')),
                    price=float(item.get('price', {}).get('value', 0) if isinstance(item.get('price'), dict) else item.get('price', 0)),
                    source='apify_amazon',
                    url=item.get('url', item.get('productUrl', '')),
                    image_url=item.get('image', item.get('imageUrl', '')),
                    rating=float(item.get('rating', 0)),
                    reviews_count=int(item.get('reviewsCount', item.get('reviews', 0))),
                    asin=item.get('asin', ''),
                    bestseller_rank=int(item.get('rank', item.get('bestsellersRank', 0))),
                    category=category,
                    in_stock=item.get('inStock', True)
                )
                products.append(product)
            except Exception as e:
                print(f"   [WARNING] Error parsing product: {e}")
                continue
        
        print(f"   Found {len(products)} bestsellers")
        return products
    
    async def search_amazon(
        self,
        keyword: str,
        max_items: int = 20,
        min_rating: float = 4.0
    ) -> List[ApifyProduct]:
        """
        Search Amazon products by keyword
        """
        actor = self.ACTORS.get('amazon_search') or ''
        if not actor:
            # No actor configured — see ACTORS comment. Fail closed so the
            # caller (amazon_reviews matcher) reports ``empty_pool`` cleanly
            # instead of silently spending money on a rental fallback.
            print(
                "[SEARCH] Amazon search disabled: APIFY_AMAZON_SEARCH_ACTOR is "
                "unset (matcher will report empty_pool)."
            )
            return []

        print(f"[SEARCH] Searching Amazon for: {keyword}")

        results = await self.run_actor(
            actor_id=actor,
            run_input={
                "searchTerms": [keyword],
                "maxItems": max_items,
                "filterByMinRating": min_rating,
                "proxy": {
                    "useApifyProxy": True
                }
            },
            timeout_secs=180
        )
        
        products = []
        for item in results:
            try:
                price_str = item.get('price', '0')
                if isinstance(price_str, str):
                    price_str = price_str.replace('$', '').replace(',', '')
                price = float(price_str) if price_str else 0
                
                product = ApifyProduct(
                    name=item.get('title', 'Unknown'),
                    price=price,
                    source='apify_amazon',
                    url=item.get('url', ''),
                    image_url=item.get('thumbnailImage', item.get('image', '')),
                    rating=float(item.get('stars', 0)),
                    reviews_count=int(item.get('reviewsCount', 0)),
                    asin=item.get('asin', ''),
                    bestseller_rank=int(item.get('bsr', 0)),
                    category=keyword,
                    in_stock=item.get('inStock', True)
                )
                products.append(product)
            except Exception as e:
                print(f"   [WARNING] Error parsing product: {e}")
                continue
        
        print(f"   Found {len(products)} products")
        return products
    
    async def get_tiktok_trending(
        self,
        hashtag: str = "tiktokmademebuyit",
        max_videos: int = 20
    ) -> List[Dict]:
        """
        Get trending TikTok videos for product discovery
        
        Popular hashtags:
        - tiktokmademebuyit
        - amazonfinds
        - musthave
        - coolgadgets
        - smarthome
        """
        print(f"[MOBILE] Fetching TikTok trends: #{hashtag}")
        
        results = await self.run_actor(
            actor_id=self.ACTORS['tiktok_hashtag'],
            run_input={
                "hashtags": [hashtag],
                "resultsPerPage": max_videos,
                "shouldDownloadVideos": False,
                "proxy": {
                    "useApifyProxy": True
                }
            },
            timeout_secs=180
        )
        
        videos = []
        for item in results:
            try:
                video = {
                    'id': item.get('id', ''),
                    'description': item.get('text', item.get('desc', '')),
                    'author': item.get('authorMeta', {}).get('name', 'unknown'),
                    'views': int(item.get('playCount', item.get('stats', {}).get('playCount', 0))),
                    'likes': int(item.get('diggCount', item.get('stats', {}).get('diggCount', 0))),
                    'comments': int(item.get('commentCount', item.get('stats', {}).get('commentCount', 0))),
                    'shares': int(item.get('shareCount', item.get('stats', {}).get('shareCount', 0))),
                    'url': item.get('webVideoUrl', f"https://tiktok.com/@{item.get('authorMeta', {}).get('name', '')}/video/{item.get('id', '')}"),
                    'hashtag': hashtag,
                    'source': 'apify_tiktok',
                }
                
                # Calculate viral score (0-100)
                engagement = video['likes'] + video['comments'] * 2 + video['shares'] * 3
                views = max(video['views'], 1)
                engagement_rate = engagement / views
                
                # Score based on views and engagement
                view_score = min(50, video['views'] / 100000 * 50)  # Max 50 from views
                engagement_score = min(50, engagement_rate * 1000)  # Max 50 from engagement
                video['viral_score'] = round(view_score + engagement_score, 1)
                
                videos.append(video)
            except Exception as e:
                print(f"   [WARNING] Error parsing video: {e}")
                continue
        
        # Sort by viral score
        videos.sort(key=lambda x: x['viral_score'], reverse=True)
        
        print(f"   Found {len(videos)} trending videos")
        return videos
    
    async def discover_products_for_ospra(
        self,
        niches: List[str] = None,
        max_products: int = 20
    ) -> List[Dict]:
        """
        Comprehensive product discovery using Apify
        
        Combines:
        1. Amazon bestsellers
        2. Amazon keyword search
        3. TikTok viral products
        """
        if not niches:
            niches = ['smart home', 'kitchen gadgets', 'fitness']
        
        all_products = []
        
        # Amazon categories mapping
        amazon_categories = {
            'smart home': 'Home & Kitchen',
            'kitchen': 'Home & Kitchen',
            'fitness': 'Sports & Outdoors',
            'beauty': 'Beauty & Personal Care',
            'pet': 'Pet Supplies',
            'tech': 'Electronics',
        }
        
        for niche in niches:
            print(f"\n[SEARCH] Discovering products for: {niche}")
            
            # 1. Amazon bestsellers
            category = amazon_categories.get(niche.lower(), 'Home & Kitchen')
            try:
                bestsellers = await self.get_amazon_bestsellers(
                    category=category,
                    max_items=max_products // 2
                )
                for p in bestsellers:
                    product_dict = p.to_dict()
                    product_dict['niche'] = niche
                    product_dict['discovery_method'] = 'amazon_bestseller'
                    all_products.append(product_dict)
            except Exception as e:
                print(f"   [WARNING] Amazon bestsellers failed: {e}")
            
            # 2. Amazon search
            try:
                search_results = await self.search_amazon(
                    keyword=niche,
                    max_items=max_products // 2
                )
                for p in search_results:
                    product_dict = p.to_dict()
                    product_dict['niche'] = niche
                    product_dict['discovery_method'] = 'amazon_search'
                    all_products.append(product_dict)
            except Exception as e:
                print(f"   [WARNING] Amazon search failed: {e}")
        
        # 3. TikTok viral (once for all niches)
        try:
            tiktok_videos = await self.get_tiktok_trending(
                hashtag="tiktokmademebuyit",
                max_videos=max_products
            )
            for video in tiktok_videos:
                # Extract potential product mentions from description
                all_products.append({
                    'name': video['description'][:100],
                    'price': 0,  # Need to cross-reference
                    'source': 'apify_tiktok',
                    'url': video['url'],
                    'viral_score': video['viral_score'],
                    'views': video['views'],
                    'likes': video['likes'],
                    'discovery_method': 'tiktok_viral',
                    'niche': 'tiktok',
                })
        except Exception as e:
            print(f"   [WARNING] TikTok trends failed: {e}")
        
        print(f"\n[SUCCESS] Total products discovered: {len(all_products)}")
        return all_products


# Alias for backward compatibility - TikTokShopScraper and AmazonBestsellersScraper inherit from this
ApifyConnector = ApifyClient


# Factory function for Intelligence Engine
def get_apify_client(api_token: Optional[str] = None) -> ApifyClient:
    """Get configured Apify client"""
    return ApifyClient(api_token=api_token)


# Quick test
async def test_apify():
    """Test Apify connection and basic functionality"""
    print("\n" + "="*70)
    print("[TEST] TESTING APIFY INTEGRATION")
    print("="*70 + "\n")
    
    try:
        client = ApifyClient()
        
        # Test connection
        print("1⃣ Testing connection...")
        connection = await client.test_connection()
        
        if connection['connected']:
            print(f"   [SUCCESS] Connected as: {connection['username']}")
            print(f"   [EMAIL] Email: {connection['email']}")
            print(f"   [PAYMENT] Plan: {connection['plan']}")
        else:
            print(f"   [ERROR] Connection failed: {connection['error']}")
            return
        
        # Test Amazon bestsellers (small test)
        print("\n2⃣ Testing Amazon bestsellers...")
        bestsellers = await client.get_amazon_bestsellers(
            category="Home & Kitchen",
            max_items=5
        )
        
        for p in bestsellers[:3]:
            print(f"   [PACKAGE] {p.name[:50]}...")
            print(f"      ${p.price:.2f} | [STAR]{p.rating} | #{p.bestseller_rank}")
        
        print("\n[SUCCESS] Apify integration working!")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_apify())
