"""
Ospra Intelligence - Product Discovery Engine v2
================================================
TREND-FIRST discovery with supplier cross-referencing.

FLOW:
1. TRENDS → Get what's hot (Google Trends, TikTok viral, Amazon BSR)
2. SUPPLIERS → Search trending keywords on AliExpress + CJ
3. CROSS-REF → Match similar products across suppliers
4. SENTIMENT → Add social validation
5. SCORE → Calculate OI score with all data

10 DATA SOURCES:
1. Google Trends - Search interest validation (TREND SOURCE)
2. TikTok Shop (via Apify) - Viral product detection (TREND SOURCE)
3. Amazon Bestsellers (via Apify) - Demand validation (TREND SOURCE)
4. X/Twitter Sentiment (via xAI Grok) - Social buzz
5. Reddit Sentiment - Community feedback
6. AliExpress Affiliate API (522382) - Commission links (SUPPLIER)
7. AliExpress Dropshipping API (520918) - Direct sourcing (SUPPLIER)
8. CJ Dropshipping - US/EU warehouse suppliers (SUPPLIER)
9. Claude AI - Analysis & captions
10. OpenAI - Image generation
"""

import asyncio
import logging
import os
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# =============================================================================
# PER-SOURCE TIMEOUT CAPS
# =============================================================================
# Each parallel source is wrapped in asyncio.wait_for so one slow source
# (usually Apify queues, or CJ's exponential-backoff on 429s) can't push the
# whole discovery request past the 30s global timeout middleware.
#
# Budget: Step 1 (trends) + Step 2 (suppliers) + Step 4 (sentiment) <= ~28s
# leaving ~2s of fixed overhead (scoring, serialization, etc.)
#
# Env overrides let us tune without a redeploy.
# =============================================================================
TREND_SOURCE_TIMEOUT = float(os.getenv("DISCOVERY_TREND_TIMEOUT", "10"))
SUPPLIER_SOURCE_TIMEOUT = float(os.getenv("DISCOVERY_SUPPLIER_TIMEOUT", "12"))
# SENTIMENT_SOURCE_TIMEOUT was 6s when Grok calls ran sequentially and only
# 1-2 of 10 products would complete before the budget ran out. Post-Fix #15
# Grok calls inside the enrichment are parallelized (asyncio.gather), so 20
# products finish in the time of the slowest single call (~5s). 15s gives
# headroom for cold-start latency on the first request.
SENTIMENT_SOURCE_TIMEOUT = float(os.getenv("DISCOVERY_SENTIMENT_TIMEOUT", "15"))


def _with_timeout(coro, timeout: float):
    """Wrap a coroutine so it raises asyncio.TimeoutError after `timeout` seconds.

    Used with asyncio.gather(..., return_exceptions=True) so timed-out sources
    are skipped gracefully and we still return results from fast sources.
    """
    return asyncio.wait_for(coro, timeout=timeout)


def _resolve_product_url(product: Dict) -> Optional[str]:
    """
    Resolve the outbound source URL for a product across supplier shapes.

    Checks top-level and nested data_sources fields so the frontend link
    never goes to a dead/empty URL. Returns None if no usable URL exists.
    """
    if not isinstance(product, dict):
        return None

    data_sources = product.get('data_sources') or {}
    ali_src = data_sources.get('aliexpress') or {}
    cj_src = data_sources.get('cj_dropshipping') or data_sources.get('cj') or {}

    candidates = [
        product.get('affiliate_url'),
        product.get('affiliateUrl'),
        product.get('affiliate_link'),
        product.get('affiliateLink'),
        product.get('promotion_link'),
        product.get('promotionLink'),
        product.get('supplier_url'),
        product.get('supplierUrl'),
        product.get('product_url'),
        product.get('productUrl'),
        ali_src.get('url'),
        ali_src.get('promotion_link'),
        ali_src.get('affiliate_url'),
        ali_src.get('product_url'),
        cj_src.get('url'),
        cj_src.get('product_url'),
        product.get('url'),
        product.get('source_url'),
    ]

    for candidate in candidates:
        if isinstance(candidate, str):
            stripped = candidate.strip()
            if stripped and stripped.lower() not in {'none', 'null', 'n/a', '#'}:
                if stripped.startswith(('http://', 'https://')):
                    return stripped
    return None


class ProductDiscoveryEngine:
    """
    TREND-FIRST multi-source product discovery.
    
    Key Insight: Find what's TRENDING first, then find where to SOURCE it.
    """
    
    # SPECIFIC product search terms - avoid generic phrases like "gadgets"
    # AliExpress works better with specific product names
    NICHE_KEYWORDS = {
        "smart_home": ["wifi smart plug", "LED strip lights RGB", "smart light bulb wifi", "motion sensor alarm", "smart door lock"],
        "kitchen": ["electric milk frother", "vegetable chopper slicer", "silicone utensil set", "digital kitchen scale", "food storage container"],
        "fitness": ["resistance bands set", "yoga mat thick", "adjustable dumbbell", "jump rope fitness", "foam roller muscle"],
        "beauty": ["LED face mask", "jade roller gua sha", "hair straightener brush", "makeup brush set", "facial steamer"],
        "tech": ["wireless charger fast", "bluetooth earbuds TWS", "phone stand holder", "USB C hub adapter", "portable power bank"],
        "home_decor": ["LED neon sign", "wall art canvas", "floating shelf", "fairy string lights", "decorative throw pillow"],
        "pet": ["automatic pet feeder", "dog chew toy", "cat scratching post", "pet water fountain", "dog leash retractable"],
        "outdoor": ["camping lantern LED", "portable water filter", "hiking backpack", "solar power bank", "survival kit emergency"],
        "office": ["desk organizer wood", "monitor stand riser", "ergonomic mouse pad", "cable management", "desk lamp LED"],
        "gaming": ["RGB mousepad large", "gaming headset 7.1", "controller stand PS5", "cable management gaming", "monitor light bar"],
    }

    # Relevance keywords for filtering off-topic products
    # Products containing ANY of these keywords are considered relevant to the niche
    RELEVANCE_KEYWORDS = {
        "smart_home": {
            "include": ["smart", "wifi", "wireless", "sensor", "led", "light", "bulb", "plug", "switch",
                        "automation", "iot", "zigbee", "bluetooth", "remote", "control", "dimmer",
                        "motion", "detector", "thermostat", "camera", "doorbell", "lock", "alexa", "google home"],
            "exclude": ["furniture", "sofa", "chair", "table", "bed", "mattress", "curtain", "carpet",
                        "painting", "vase", "cushion", "pillow", "blanket", "living room set"]
        },
        "kitchen": {
            "include": ["kitchen", "cooking", "food", "utensil", "knife", "pot", "pan", "cook", "chef",
                        "blender", "mixer", "chopper", "slicer", "scale", "timer", "container", "storage",
                        "gadget", "tool", "silicone", "steel", "electric"],
            "exclude": ["furniture", "sofa", "decoration", "wall art", "painting", "sculpture"]
        },
        "fitness": {
            "include": ["fitness", "gym", "workout", "exercise", "sport", "yoga", "resistance", "band",
                        "weight", "dumbbell", "kettlebell", "mat", "rope", "trainer", "muscle", "cardio"],
            "exclude": ["furniture", "sofa", "decoration", "painting"]
        },
        "beauty": {
            "include": ["beauty", "skin", "face", "hair", "makeup", "cosmetic", "cream", "serum",
                        "brush", "mirror", "led mask", "derma", "roller", "massage", "eye"],
            "exclude": ["furniture", "sofa", "wall", "room"]
        },
        "tech": {
            "include": ["tech", "gadget", "electronic", "phone", "wireless", "bluetooth", "usb", "cable",
                        "charger", "speaker", "headphone", "earbuds", "mouse", "keyboard", "hub", "adapter"],
            "exclude": ["furniture", "sofa", "decoration", "painting", "room style"]
        },
        "pet": {
            "include": ["pet", "dog", "cat", "puppy", "kitten", "animal", "bowl", "feeder", "toy",
                        "leash", "collar", "grooming", "brush", "bed", "carrier", "cage"],
            "exclude": ["human", "furniture set", "living room", "bedroom"]
        },
        "car": {
            "include": ["car", "auto", "vehicle", "carplay", "dashboard", "charger", "mount", "holder",
                        "screen", "display", "adapter", "wireless", "bluetooth", "gps", "dvr", "camera"],
            "exclude": ["furniture", "sofa", "home decor", "living room"]
        }
    }
    
    def __init__(self):
        """Initialize all data source connectors"""
        self.sources_status = {}
        self._init_trend_sources()
        self._init_supplier_sources()
        self._init_sentiment_sources()
        self._log_status()
    
    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    
    def _init_trend_sources(self):
        """Initialize TREND sources (what's hot)"""
        # Google Trends via TrendAnalyzer.
        # Task #8: pytrends is archived (April 2025) and unreliable — we now
        # prefer ApifyGoogleTrends. The old availability check only looked at
        # `trend_analyzer.pytrends`, so even a healthy Apify trends backend
        # was reported as unavailable. Check both attributes.
        self.trends_available = False
        self.trend_analyzer = None
        try:
            from ospra_os.intelligence.trend_analyzer import TrendAnalyzer
            self.trend_analyzer = TrendAnalyzer()
            apify_ok = getattr(self.trend_analyzer, "apify_trends", None) is not None
            pytrends_ok = getattr(self.trend_analyzer, "pytrends", None) is not None
            if apify_ok:
                self.trends_available = True
                self.sources_status['google_trends'] = '[SUCCESS] Connected (Apify)'
                logger.info("[SUCCESS] Google Trends loaded via TrendAnalyzer (Apify)")
            elif pytrends_ok:
                # Deprecated path — still usable but expect 429s.
                self.trends_available = True
                self.sources_status['google_trends'] = '[WARNING] Connected via pytrends (deprecated — expect 429s)'
                logger.warning("[WARNING] Google Trends: using pytrends fallback (deprecated)")
            else:
                self.sources_status['google_trends'] = '[WARNING] Neither Apify trends nor pytrends available — set APIFY_API_TOKEN'
                logger.warning("[WARNING] Google Trends: no backend available (set APIFY_API_TOKEN)")
        except Exception as e:
            self.sources_status['google_trends'] = f'[ERROR] {e}'
            logger.warning(f"[WARNING] Google Trends init failed: {e}")
        
        # TikTok + Amazon via Apify
        self.apify_token = os.getenv('APIFY_API_TOKEN') or os.getenv('OUBONSHOP_APIFY_API_TOKEN')
        self.tiktok_scraper = None
        self.amazon_scraper = None
        self.apify_available = False
        
        if self.apify_token:
            try:
                from ospra_os.product_research.connectors.apify import TikTokShopScraper, AmazonBestsellersScraper
                self.tiktok_scraper = TikTokShopScraper()
                self.amazon_scraper = AmazonBestsellersScraper()
                self.apify_available = True
                self.sources_status['tiktok'] = '[SUCCESS] Connected (Apify)'
                self.sources_status['amazon'] = '[SUCCESS] Connected (Apify)'
                logger.info("[SUCCESS] TikTok + Amazon scrapers loaded")
            except Exception as e:
                self.sources_status['tiktok'] = f'[ERROR] {e}'
                self.sources_status['amazon'] = f'[ERROR] {e}'
        else:
            self.sources_status['tiktok'] = '[ERROR] No APIFY_API_TOKEN'
            self.sources_status['amazon'] = '[ERROR] No APIFY_API_TOKEN'
    
    def _init_supplier_sources(self):
        """Initialize SUPPLIER sources (where to buy)"""
        # AliExpress
        self.aliexpress = None
        self.aliexpress_available = False
        try:
            from ospra_os.integrations.aliexpress.client import AliExpressClient
            self.aliexpress = AliExpressClient(use_affiliate=True)
            self.aliexpress_available = True
            self.sources_status['aliexpress'] = '[SUCCESS] Connected (522382 + 520918)'
            logger.info("[SUCCESS] AliExpress API loaded")
        except Exception as e:
            self.sources_status['aliexpress'] = f'[ERROR] {e}'
        
        # CJ Dropshipping
        self.cj_client = None
        self.cj_available = False
        try:
            from ospra_os.integrations.cj_dropshipping.client import CJDropshippingClient
            self.cj_client = CJDropshippingClient()
            self.cj_available = self.cj_client.is_available()
            self.sources_status['cj_dropshipping'] = '[SUCCESS] Connected (US/EU warehouses)' if self.cj_available else '[ERROR] No token'
            if self.cj_available:
                logger.info("[SUCCESS] CJ Dropshipping API loaded")
        except Exception as e:
            self.sources_status['cj_dropshipping'] = f'[ERROR] {e}'
    
    def _init_sentiment_sources(self):
        """Initialize SENTIMENT sources (social validation)"""
        # X/Twitter via xAI
        self.xai_twitter = None
        self.xai_available = False
        xai_key = os.getenv('XAI_API_KEY')
        if xai_key:
            try:
                from ospra_os.product_research.connectors.social.xai_twitter import XAITwitterDiscovery
                self.xai_twitter = XAITwitterDiscovery(api_key=xai_key)
                self.xai_available = self.xai_twitter.is_available()
                self.sources_status['x_twitter'] = '[SUCCESS] Connected (xAI Grok)' if self.xai_available else '[ERROR] Init failed'
            except Exception as e:
                self.sources_status['x_twitter'] = f'[ERROR] {e}'
        else:
            self.sources_status['x_twitter'] = '[ERROR] No XAI_API_KEY'
        
        # Reddit
        self.reddit = None
        self.reddit_available = False
        reddit_id = os.getenv('OUBONSHOP_REDDIT_CLIENT_ID')
        reddit_secret = os.getenv('OUBONSHOP_REDDIT_SECRET')
        if reddit_id and reddit_secret:
            try:
                from ospra_os.product_research.connectors.social.reddit import RedditConnector
                self.reddit = RedditConnector(client_id=reddit_id, client_secret=reddit_secret)
                self.reddit_available = True
                self.sources_status['reddit'] = '[SUCCESS] Connected'
            except Exception as e:
                self.sources_status['reddit'] = f'[ERROR] {e}'
        else:
            self.sources_status['reddit'] = '[ERROR] No credentials'

        # Amazon reviews (via Apify) - primary social signal (Task #18)
        # Amazon aggregate rating × review count is the strongest purchase-intent
        # signal available. We run ONE niche-level search per discovery and
        # fuzzy-match our supplier products against the pool.
        self.amazon_reviews = None
        self.amazon_reviews_available = False
        if self.apify_token:
            try:
                from ospra_os.product_research.connectors.social.amazon_reviews import AmazonReviewsConnector
                self.amazon_reviews = AmazonReviewsConnector(api_token=self.apify_token)
                self.amazon_reviews_available = self.amazon_reviews.is_available()
                if self.amazon_reviews_available:
                    self.sources_status['amazon_reviews'] = '[SUCCESS] Connected (Apify)'
                    logger.info("[SUCCESS] Amazon reviews connector loaded")
                else:
                    self.sources_status['amazon_reviews'] = '[ERROR] Init failed'
            except Exception as e:
                self.sources_status['amazon_reviews'] = f'[ERROR] {e}'
        else:
            self.sources_status['amazon_reviews'] = '[ERROR] No APIFY_API_TOKEN'
    
    def _log_status(self):
        """Log data source status"""
        logger.info("\n" + "="*60)
        logger.info("[OSPRA] OSPRA INTELLIGENCE - DATA SOURCES")
        logger.info("="*60)
        logger.info("\n[TREND] TREND SOURCES (What's Hot):")
        for source in ['google_trends', 'tiktok', 'amazon']:
            logger.info(f"   {source}: {self.sources_status.get(source, '[ERROR] Not loaded')}")
        logger.info("\n[SUPPLIER] SUPPLIER SOURCES (Where to Buy):")
        for source in ['aliexpress', 'cj_dropshipping']:
            logger.info(f"   {source}: {self.sources_status.get(source, '[ERROR] Not loaded')}")
        logger.info("\n[SENTIMENT] SENTIMENT SOURCES (Social Validation):")
        for source in ['x_twitter', 'reddit', 'amazon_reviews']:
            logger.info(f"   {source}: {self.sources_status.get(source, '[ERROR] Not loaded')}")
        connected = sum(1 for s in self.sources_status.values() if '[SUCCESS]' in s)
        logger.info(f"\n[STATS] {connected}/{len(self.sources_status)} sources connected")
        logger.info("="*60 + "\n")
    
    # =========================================================================
    # MAIN DISCOVERY (TREND-FIRST FLOW)
    # =========================================================================
    
    async def discover_products(
        self,
        niche: str = "smart_home",
        max_products: int = 20,
        min_score: float = 30.0,
        include_sentiment: bool = True
    ) -> List[Dict]:
        """
        TREND-FIRST discovery flow with PARALLEL data source queries.

        1. Get trending keywords/products
        2. Search suppliers for those trends (PARALLEL)
        3. Cross-reference across suppliers
        4. Add sentiment data (PARALLEL)
        5. Score and rank

        Performance: ~40% faster than sequential thanks to parallel I/O
        """
        import time
        start_time = time.time()

        logger.info(f"\n{'='*60}")
        logger.info(f"[SEARCH] TREND-FIRST DISCOVERY (PARALLEL): {niche}")
        logger.info(f"{'='*60}")

        data_sources_used = []

        # =====================================================================
        # STEP 1: GET TRENDING KEYWORDS
        # =====================================================================
        step1_start = time.time()
        logger.info("\n[TREND] STEP 1: Finding trending products/keywords...")

        trending_keywords = await self._get_trending_keywords(niche)
        data_sources_used.extend(['google_trends', 'tiktok', 'amazon'])

        logger.info(f"   Found {len(trending_keywords)} trending keywords: {trending_keywords[:5]}")
        logger.info(f"   ⏱️ Step 1 took {time.time() - step1_start:.2f}s")

        # =====================================================================
        # STEP 2: SEARCH SUPPLIERS FOR TRENDING PRODUCTS (PARALLEL!)
        # =====================================================================
        step2_start = time.time()
        logger.info("\n[SUPPLIER] STEP 2: Searching suppliers IN PARALLEL...")

        # Create all supplier fetch tasks to run concurrently
        supplier_tasks = []
        task_labels = []

        # AliExpress tasks - one per keyword (parallel keyword fetches)
        if self.aliexpress_available:
            for keyword in trending_keywords[:3]:
                supplier_tasks.append(self._fetch_aliexpress(keyword, count=10))
                task_labels.append(f"aliexpress:{keyword[:20]}")

        # CJ Dropshipping tasks
        # Step B: CJ is rate-limited (1 req/sec). Previously we fired 3 tasks
        # (1 category + 2 keyword) concurrently, which caused 429 cascades and
        # burned our 12s per-source timeout. Now: ONE category-only task.
        # If CJ's category search is empty, we'd rather know that cleanly than
        # fall through to keyword spam that triggers rate limits.
        if self.cj_available:
            supplier_tasks.append(self._fetch_cj(keyword="", count=15, niche=niche))
            task_labels.append(f"cj:category:{niche}")

        # Execute ALL supplier fetches in parallel (each capped at SUPPLIER_SOURCE_TIMEOUT)
        logger.info(
            f"   🚀 Launching {len(supplier_tasks)} parallel supplier queries "
            f"(per-source timeout: {SUPPLIER_SOURCE_TIMEOUT}s)..."
        )
        supplier_tasks_timed = [_with_timeout(t, SUPPLIER_SOURCE_TIMEOUT) for t in supplier_tasks]
        results = await asyncio.gather(*supplier_tasks_timed, return_exceptions=True)

        # Process results
        aliexpress_products = []
        cj_products = []
        cj_seen_ids = set()

        for i, result in enumerate(results):
            label = task_labels[i] if i < len(task_labels) else f"task_{i}"

            if isinstance(result, asyncio.TimeoutError):
                logger.warning(f"   ⏱️ {label} TIMED OUT after {SUPPLIER_SOURCE_TIMEOUT}s - skipped")
                continue
            if isinstance(result, Exception):
                logger.warning(f"   ⚠️ {label} failed: {result}")
                continue

            if not result:
                continue

            if label.startswith("aliexpress"):
                aliexpress_products.extend(result)
                logger.debug(f"   ✓ {label}: {len(result)} products")
            elif label.startswith("cj"):
                # Dedupe CJ products
                for p in result:
                    pid = p.get('product_id')
                    if pid and pid not in cj_seen_ids:
                        cj_products.append(p)
                        cj_seen_ids.add(pid)
                logger.debug(f"   ✓ {label}: {len(result)} products")

        if aliexpress_products:
            data_sources_used.append('aliexpress')
        if cj_products:
            data_sources_used.append('cj_dropshipping')

        logger.info(f"   [CART] AliExpress: {len(aliexpress_products)} products")
        logger.info(f"   [PACKAGE] CJ Dropshipping: {len(cj_products)} products")
        logger.info(f"   ⏱️ Step 2 (parallel) took {time.time() - step2_start:.2f}s")

        # =====================================================================
        # STEP 3: CROSS-REFERENCE SUPPLIERS
        # =====================================================================
        step3_start = time.time()
        logger.info("\n[CROSSREF] STEP 3: Cross-referencing suppliers...")

        all_products = await self._cross_reference_suppliers(
            aliexpress_products,
            cj_products,
            niche
        )

        logger.info(f"   -> {len(all_products)} unique products after cross-reference")
        logger.info(f"   ⏱️ Step 3 took {time.time() - step3_start:.2f}s")

        if len(all_products) == 0:
            allow_demo = os.getenv("ALLOW_DEMO_FALLBACK", "0").lower() in ("1", "true", "yes")
            if allow_demo:
                logger.warning("[WARNING] No products found from any source - using demo data (ALLOW_DEMO_FALLBACK=1)")
                return self._get_demo_products(niche, max_products)
            logger.warning("[WARNING] No products found from any source - returning empty list (route will surface diagnostics)")
            return []

        # =====================================================================
        # STEP 4: ENRICH WITH SENTIMENT (PARALLEL!)
        # =====================================================================
        if include_sentiment:
            step4_start = time.time()
            logger.info("\n[SENTIMENT] STEP 4: Adding sentiment data IN PARALLEL...")

            sentiment_tasks = []
            sentiment_labels = []

            if self.xai_available:
                sentiment_tasks.append(self._enrich_with_twitter_sentiment(all_products.copy()))
                sentiment_labels.append('x_twitter')

            if self.reddit_available:
                sentiment_tasks.append(self._enrich_with_reddit_sentiment(all_products.copy(), niche))
                sentiment_labels.append('reddit')

            if self.amazon_reviews_available:
                sentiment_tasks.append(self._enrich_with_amazon_reviews(all_products.copy(), niche))
                sentiment_labels.append('amazon_reviews')

            if sentiment_tasks:
                logger.info(
                    f"   🚀 Launching {len(sentiment_tasks)} parallel sentiment queries "
                    f"(per-source timeout: {SENTIMENT_SOURCE_TIMEOUT}s)..."
                )
                sentiment_tasks_timed = [_with_timeout(t, SENTIMENT_SOURCE_TIMEOUT) for t in sentiment_tasks]
                sentiment_results = await asyncio.gather(*sentiment_tasks_timed, return_exceptions=True)

                # Merge sentiment data back into products
                for i, result in enumerate(sentiment_results):
                    label = sentiment_labels[i] if i < len(sentiment_labels) else f"sentiment_{i}"

                    if isinstance(result, asyncio.TimeoutError):
                        logger.warning(f"   ⏱️ {label} sentiment TIMED OUT after {SENTIMENT_SOURCE_TIMEOUT}s - skipped")
                        continue
                    if isinstance(result, Exception):
                        logger.warning(f"   ⚠️ {label} sentiment failed: {result}")
                        continue

                    if result:
                        data_sources_used.append(label)
                        # Merge sentiment data from result into all_products
                        result_by_id = {p.get('product_id'): p for p in result}
                        for product in all_products:
                            pid = product.get('product_id')
                            if pid in result_by_id:
                                enriched = result_by_id[pid]
                                # Copy sentiment-specific fields
                                if label == 'x_twitter':
                                    product['twitter_sentiment'] = enriched.get('twitter_sentiment')
                                    product['twitter_buzz'] = enriched.get('twitter_buzz')
                                    # POST-FIX #15: propagate evidence trail through the merge.
                                    # Without this line, twitter_evidence populated inside
                                    # _enrich_with_twitter_sentiment gets silently dropped.
                                    product['twitter_evidence'] = enriched.get('twitter_evidence')
                                elif label == 'reddit':
                                    product['reddit_mentions'] = enriched.get('reddit_mentions')
                                    # Also propagate reddit_evidence (populated by Fix #15c)
                                    product['reddit_evidence'] = enriched.get('reddit_evidence')
                                elif label == 'amazon_reviews':
                                    # Task #18: Amazon is the primary social signal.
                                    # amazon_evidence is a dict (not list like reddit_evidence).
                                    # amazon_buzz is a scalar score consumed by _calculate_scores.
                                    product['amazon_evidence'] = enriched.get('amazon_evidence')
                                    product['amazon_buzz'] = enriched.get('amazon_buzz')
                                    product['amazon_rating'] = enriched.get('amazon_rating')
                                    product['amazon_review_count'] = enriched.get('amazon_review_count')
                                # Merge data_sources
                                if 'data_sources' in enriched:
                                    if 'data_sources' not in product:
                                        product['data_sources'] = {}
                                    product['data_sources'].update(enriched.get('data_sources', {}))
                        logger.info(f"   ✓ {label}: sentiment data merged")

                logger.info(f"   ⏱️ Step 4 (parallel) took {time.time() - step4_start:.2f}s")

        # =====================================================================
        # STEP 5: SCORE AND RANK
        # =====================================================================
        step5_start = time.time()
        logger.info("\n[SCORE] STEP 5: Calculating OI scores...")

        scored_products = self._calculate_scores(all_products)

        # Filter and sort
        filtered = [p for p in scored_products if p.get('oi_score', 0) >= min_score]
        ranked = sorted(filtered, key=lambda x: x.get('oi_score', 0), reverse=True)

        # URL VALIDATION: drop products with no usable outbound source URL so
        # the frontend never receives an unclickable product card.
        url_valid: List[Dict] = []
        url_dropped = 0
        for product in ranked:
            resolved = _resolve_product_url(product)
            if resolved:
                # Normalize: guarantee a top-level supplier_url for the frontend
                product['supplier_url'] = resolved
                url_valid.append(product)
            else:
                url_dropped += 1
                logger.warning(
                    f"   ⚠️ Dropping product with no usable URL: "
                    f"{product.get('product_id') or product.get('title', '?')[:60]}"
                )

        if url_dropped:
            logger.info(
                f"   🔗 URL validation: kept {len(url_valid)} / dropped {url_dropped}"
            )

        final = url_valid[:max_products]

        # Add metadata
        total_time = time.time() - start_time
        for product in final:
            product['_discovery_metadata'] = {
                'sources_queried': list(set(data_sources_used)),
                'discovered_at': datetime.now().isoformat(),
                'niche': niche,
                'flow': 'trend_first_v2_parallel',
                'discovery_time_seconds': round(total_time, 2)
            }

        logger.info(f"   ⏱️ Step 5 took {time.time() - step5_start:.2f}s")

        logger.info(f"\n[SUCCESS] Discovery complete!")
        logger.info(f"   Sources: {', '.join(set(data_sources_used))}")
        logger.info(f"   Total: {len(aliexpress_products) + len(cj_products)} -> Unique: {len(all_products)} -> Final: {len(final)}")
        logger.info(f"   ⏱️ TOTAL TIME: {total_time:.2f}s (parallel execution)")

        # Log supplier breakdown
        ali_count = sum(1 for p in final if 'aliexpress' in p.get('available_on', []))
        cj_count = sum(1 for p in final if 'cj_dropshipping' in p.get('available_on', []))
        both_count = sum(1 for p in final if len(p.get('available_on', [])) > 1)
        logger.info(f"   AliExpress: {ali_count} | CJ: {cj_count} | Both: {both_count}")

        # Task #4: Aggregate data coverage audit — answer "of the N products
        # we returned, how many had real data from each source?"
        if final:
            confidence_buckets = {'high': 0, 'medium': 0, 'low': 0, 'bare': 0}
            source_real_counts: Dict[str, int] = {}
            source_empty_counts: Dict[str, int] = {}
            for p in final:
                cov = p.get('data_coverage') or {}
                confidence_buckets[cov.get('confidence', 'bare')] = (
                    confidence_buckets.get(cov.get('confidence', 'bare'), 0) + 1
                )
                for src, state in (cov.get('by_source') or {}).items():
                    if state == 'real':
                        source_real_counts[src] = source_real_counts.get(src, 0) + 1
                    elif state == 'empty':
                        source_empty_counts[src] = source_empty_counts.get(src, 0) + 1
            logger.info("   📊 Data coverage audit:")
            logger.info(
                f"      Confidence: high={confidence_buckets.get('high', 0)} "
                f"medium={confidence_buckets.get('medium', 0)} "
                f"low={confidence_buckets.get('low', 0)} "
                f"bare={confidence_buckets.get('bare', 0)}"
            )
            all_srcs = sorted(set(list(source_real_counts.keys()) + list(source_empty_counts.keys())))
            for src in all_srcs:
                r = source_real_counts.get(src, 0)
                e = source_empty_counts.get(src, 0)
                total = r + e
                pct = (100.0 * r / total) if total else 0
                logger.info(f"      {src:<18} real={r:<3} empty={e:<3} coverage={pct:.0f}%")

        return final
    
    # =========================================================================
    # STEP 1: TRENDING KEYWORDS
    # =========================================================================
    
    async def _get_trending_keywords(self, niche: str) -> List[str]:
        """
        Get trending keywords from multiple sources IN PARALLEL.

        TREND-FIRST FLOW:
        1. Start with base niche keywords
        2. Query trend sources IN PARALLEL (Google Trends + TikTok + Amazon)
        3. Extract rising/viral keywords
        4. Return unified keyword list for supplier searches

        Sources (queried in parallel):
        - Google Trends (rising searches) via TrendAnalyzer
        - TikTok (viral product names) via Apify
        - Amazon (bestseller keywords) via Apify
        """
        import time
        step1_detail_start = time.time()

        keywords = []

        # Start with niche keywords (base - always available)
        base_keywords = self.NICHE_KEYWORDS.get(niche, [niche])
        keywords.extend(base_keywords)
        logger.info(f"   📋 Base keywords: {base_keywords}")

        # =====================================================================
        # PARALLEL TREND SOURCE QUERIES
        # =====================================================================
        trend_tasks = []
        trend_labels = []

        # Google Trends tasks (one per base keyword)
        if self.trends_available and self.trend_analyzer:
            for kw in base_keywords[:2]:
                trend_tasks.append(self._fetch_google_trends(kw, niche))
                trend_labels.append(f"google_trends:{kw[:15]}")

        # TikTok viral products task
        if self.apify_available and self.tiktok_scraper:
            trend_tasks.append(self._fetch_tiktok_trends(niche, base_keywords[0]))
            trend_labels.append("tiktok_viral")

        # Amazon bestsellers task (if available)
        if self.apify_available and self.amazon_scraper:
            trend_tasks.append(self._fetch_amazon_trends(niche))
            trend_labels.append("amazon_bsr")

        # Execute ALL trend queries in parallel (each capped at TREND_SOURCE_TIMEOUT)
        if trend_tasks:
            logger.info(
                f"   🚀 Launching {len(trend_tasks)} parallel trend queries "
                f"(per-source timeout: {TREND_SOURCE_TIMEOUT}s)..."
            )
            trend_tasks_timed = [_with_timeout(t, TREND_SOURCE_TIMEOUT) for t in trend_tasks]
            trend_results = await asyncio.gather(*trend_tasks_timed, return_exceptions=True)

            # Process results
            for i, result in enumerate(trend_results):
                label = trend_labels[i] if i < len(trend_labels) else f"trend_{i}"

                if isinstance(result, asyncio.TimeoutError):
                    logger.warning(f"   ⏱️ {label} TIMED OUT after {TREND_SOURCE_TIMEOUT}s - skipped")
                    continue
                if isinstance(result, Exception):
                    logger.warning(f"   ⚠️ {label} failed: {result}")
                    continue

                if result and isinstance(result, list):
                    keywords.extend(result)
                    logger.info(f"   ✓ {label}: +{len(result)} keywords")
                elif result and isinstance(result, dict):
                    # Google Trends returns dict with momentum
                    extracted = result.get('keywords', [])
                    keywords.extend(extracted)
                    direction = result.get('trend_direction', 'STABLE')
                    logger.info(f"   ✓ {label}: {direction}, +{len(extracted)} keywords")

        # Dedupe and clean
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if not kw:
                continue
            kw_clean = kw.lower().strip()
            if kw_clean and kw_clean not in seen and len(kw_clean) > 2:
                seen.add(kw_clean)
                unique_keywords.append(kw)

        logger.info(f"   ⏱️ Trend queries took {time.time() - step1_detail_start:.2f}s")
        logger.info(f"   📊 Total unique keywords: {len(unique_keywords)}")

        return unique_keywords[:10]  # Top 10 trending keywords

    async def _fetch_google_trends(self, keyword: str, niche: str) -> dict:
        """Fetch trending keywords from Google Trends (wrapper for parallel execution)."""
        try:
            trend_data = await self.trend_analyzer._get_google_trends(keyword, niche)
            if trend_data.get('available'):
                # Extract rising momentum keywords
                momentum = trend_data.get('momentum', {})
                rising_keywords = [kw for kw, score in momentum.items() if score > 10]
                return {
                    'keywords': rising_keywords,
                    'trend_direction': trend_data.get('trend_direction', 'STABLE'),
                    'source': 'google_trends'
                }
        except Exception as e:
            logger.debug(f"Google Trends fetch failed for '{keyword}': {e}")
        return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'google_trends'}

    async def _fetch_tiktok_trends(self, niche: str, keyword: str) -> List[str]:
        """Fetch viral product keywords from TikTok (wrapper for parallel execution)."""
        try:
            tiktok_products = await self.tiktok_scraper.discover_products(
                niche=niche,
                max_products=5,
                keyword=keyword
            )
            keywords = []
            for p in tiktok_products:
                name = p.get('name', '')
                # Extract key product words
                words = [w for w in name.split() if len(w) > 3 and w.isalpha()]
                if words:
                    keywords.append(' '.join(words[:3]))
            return keywords
        except Exception as e:
            logger.debug(f"TikTok trends fetch failed: {e}")
        return []

    async def _fetch_amazon_trends(self, niche: str) -> List[str]:
        """Fetch bestseller keywords from Amazon (wrapper for parallel execution)."""
        try:
            # Map niche to Amazon category
            category_map = {
                "smart_home": "smart-home",
                "kitchen": "kitchen",
                "fitness": "sports-and-fitness",
                "beauty": "beauty",
                "tech": "electronics",
                "pet": "pet-supplies",
                "gaming": "video-games",
            }
            category = category_map.get(niche, "best-sellers")

            amazon_products = await self.amazon_scraper.get_bestsellers(
                category=category,
                max_products=5
            )
            keywords = []
            for p in amazon_products:
                name = p.get('name', p.get('title', ''))
                # Extract key product words
                words = [w for w in name.split() if len(w) > 3 and w.isalpha()]
                if words:
                    keywords.append(' '.join(words[:3]))
            return keywords
        except Exception as e:
            logger.debug(f"Amazon trends fetch failed: {e}")
        return []
    
    # =========================================================================
    # STEP 2: SUPPLIER FETCHING
    # =========================================================================
    
    async def _fetch_aliexpress(self, keyword: str, count: int) -> List[Dict]:
        """Fetch from AliExpress API with ALL product images for AI analysis"""
        products = []
        
        try:
            results = await self.aliexpress.search_products(
                keywords=keyword,
                page_size=count
            )
            
            for item in results:
                price_str = item.get('target_sale_price', '0')
                cost_price = float(price_str) if price_str else 0
                if cost_price == 0:
                    continue
                
                suggested_price = round(cost_price * 2.5, 2)
                profit = round(suggested_price - cost_price, 2)
                
                # === CAPTURE ALL PRODUCT IMAGES FOR AI ===
                main_image = item.get('product_main_image_url', '')
                
                # AliExpress API returns product_small_image_urls in various formats
                small_images_data = item.get('product_small_image_urls', {})
                additional_images = []
                
                # Handle different formats from AliExpress API
                if isinstance(small_images_data, dict):
                    # Format: {"string": ["url1", "url2", ...]}
                    additional_images = small_images_data.get('string', [])
                elif isinstance(small_images_data, list):
                    # Format: ["url1", "url2", ...]
                    additional_images = small_images_data
                elif isinstance(small_images_data, str):
                    # Single URL as string
                    additional_images = [small_images_data]
                
                # Build complete image list (deduplicated)
                all_images = [main_image] if main_image else []
                for img in additional_images:
                    if img and img not in all_images and img.startswith('http'):
                        all_images.append(img)
                
                # Limit to 10 images max (enough for AI analysis)
                all_images = all_images[:10]
                
                logger.debug(f"[IMAGES] {item.get('product_title', '')[:30]}: {len(all_images)} images captured")
                
                # Get original price for discount calculation
                original_price_str = item.get('target_original_price', '0') or item.get('original_price', '0')
                original_price = float(original_price_str) if original_price_str else cost_price

                # Calculate discount percentage
                discount_pct = 0
                if original_price > cost_price and original_price > 0:
                    discount_pct = round(((original_price - cost_price) / original_price) * 100, 0)

                # Task #19: Harvest AE buyer-derived signals we already have
                # in the affiliate response but weren't using for sentiment.
                #   - evaluate_rate: positive-feedback % across buyers (0-100)
                #   - lastest_volume: recent sales count
                # Together these are weaker than Amazon's rating×review-count
                # product-level signal (no verbatim review text, no timestamp
                # cohort), but they ARE real buyer behavior and are cheaper
                # than paying Apify for AE review scraping. We expose them
                # as a tertiary sentiment tier, capped (see _calculate_scores).
                ae_evidence = self._build_aliexpress_evidence(item)

                product = {
                    "product_id": str(item.get('product_id', '')),
                    "title": item.get('product_title', 'AliExpress Product'),
                    "title_normalized": self._normalize_title(item.get('product_title', '')),
                    # PRICING - With transparency indicators
                    "cost_price": cost_price,
                    "supplier_cost": cost_price,
                    "original_price": original_price,
                    "discount_pct": discount_pct,
                    "suggested_price": suggested_price,
                    "profit": profit,
                    "price_currency": item.get('target_sale_price_currency', 'USD'),
                    "price_fetched_at": datetime.now().isoformat(),
                    "price_source": "aliexpress_affiliate_api",
                    # Primary image for display
                    "image_url": main_image,
                    # ALL images for AI analysis (up to 10)
                    "all_images": all_images,
                    "image_count": len(all_images),
                    "affiliate_link": item.get('promotion_link', ''),
                    "supplier_url": item.get('promotion_link', ''),
                    "source": "aliexpress",
                    "available_on": ["aliexpress"],
                    "is_mock": False,
                    "niche": keyword,
                    "sales_count": item.get('lastest_volume', 0),
                    "commission_rate": float(str(item.get('commission_rate', '0')).replace('%', '')),
                    # Task #19: scalar signals consumed by _calculate_scores.
                    "aliexpress_rating": ae_evidence.get('rating_stars'),
                    "aliexpress_buzz": ae_evidence.get('buzz_score'),
                    "data_sources": {
                        "aliexpress": {
                            "available": True,
                            "cost": cost_price,
                            "original_price": original_price,
                            "discount_pct": discount_pct,
                            "orders": item.get('lastest_volume', 0),
                            "commission": item.get('commission_rate', '0'),
                            "url": item.get('promotion_link', ''),
                            "image_count": len(all_images),
                            "price_fetched_at": datetime.now().isoformat(),
                            # Task #19: buyer-derived signals surfaced here
                            # so they flow through the evidence panel like
                            # amazon_reviews and apify_twitter do.
                            "rating_pct": ae_evidence.get('rating_pct'),
                            "rating_stars": ae_evidence.get('rating_stars'),
                            "buzz_score": ae_evidence.get('buzz_score'),
                            "source_type": ae_evidence.get('source_type'),
                            "found_real_rating": ae_evidence.get('found_real_rating'),
                        },
                        # Task #19: separate evidence slot so the OI formula
                        # can distinguish "AE supplier presence" (sourcing)
                        # from "AE buyer rating" (sentiment).
                        "aliexpress_signals": ae_evidence,
                    },
                    "discovered_at": datetime.now().isoformat()
                }
                products.append(product)
                
        except Exception as e:
            logger.error(f"AliExpress fetch error: {e}")
        
        return products
    
    async def _fetch_cj(self, keyword: str, count: int, niche: str = None) -> List[Dict]:
        """Fetch from CJ Dropshipping using smart search with keyword mappings.

        Strategy (Fix #7 / Step D):
        1. If niche provided, try category search (fast, no rate limit risk).
        2. If category returns empty (deprecated category id, empty inventory,
           etc.), fall back to keyword search using the FIRST niche keyword
           from NICHE_KEYWORDS. We verified live that keyword search works even
           when the category map is broken.
        3. If an explicit keyword was passed, use smart_search.

        All CJ calls share a serialized lock (client.py step A), so the
        fallback chain costs at most 2 sequential CJ requests (~6s total).
        """
        products = []

        try:
            results = []

            # Step 1: Category-based search (most reliable when map is correct)
            if niche:
                logger.info(f"   [INFO] CJ: Trying category search for niche '{niche}'")
                results = await self.cj_client.search_by_niche(niche, page_size=count)

            # Step 2: Keyword fallback when category is empty.
            # Triggered when the discovery engine passed niche but no keyword,
            # AND category returned nothing. Use the first NICHE_KEYWORDS entry
            # as a concrete search term (e.g. "wifi smart plug" for smart_home).
            if not results and niche and not keyword:
                niche_keywords = self.NICHE_KEYWORDS.get(niche, [])
                if niche_keywords:
                    fallback_kw = niche_keywords[0]
                    logger.info(
                        f"   [INFO] CJ: Category empty, falling back to keyword '{fallback_kw}' "
                        f"(niche={niche})"
                    )
                    fallback_results = await self.cj_client.smart_search(fallback_kw, page_size=count)
                    # Use normalized keys (product_id / cj_pid), not the legacy
                    # source_id / name which never exist on CJ-normalized products.
                    seen_ids = {p.get('product_id') or p.get('cj_pid') or p.get('title') for p in results}
                    for p in fallback_results:
                        pid = p.get('product_id') or p.get('cj_pid') or p.get('title')
                        if pid not in seen_ids:
                            results.append(p)
                            seen_ids.add(pid)

            # Step 3: Explicit keyword path (legacy — still used when discovery
            # or other callers pass a non-empty keyword directly)
            if keyword and (not results or len(results) < count // 2):
                logger.info(f"   [INFO] CJ: Using smart_search for '{keyword}'")
                smart_results = await self.cj_client.smart_search(keyword, page_size=count)
                seen_ids = {p.get('product_id') or p.get('cj_pid') or p.get('title') for p in results}
                for p in smart_results:
                    pid = p.get('product_id') or p.get('cj_pid') or p.get('title')
                    if pid not in seen_ids:
                        results.append(p)
                        seen_ids.add(pid)

            # Process results - they're already normalized by CJ client
            for item in results:
                product = item.copy()
                product['title_normalized'] = self._normalize_title(item.get('title', ''))
                product['available_on'] = ['cj_dropshipping']
                product['niche'] = niche or keyword
                products.append(product)

            if products:
                logger.info(f"   [SUCCESS] CJ: {len(products)} products found")
            else:
                logger.warning(f"   [WARNING] CJ: No products for '{keyword}' / niche '{niche}'")

        except Exception as e:
            logger.error(f"[ERROR] CJ fetch error: {e}")

        return products
    
    # =========================================================================
    # STEP 3: CROSS-REFERENCE SUPPLIERS
    # =========================================================================
    
    async def _cross_reference_suppliers(
        self,
        aliexpress_products: List[Dict],
        cj_products: List[Dict],
        niche: str
    ) -> List[Dict]:
        """
        Cross-reference products across suppliers using MULTI-SIGNAL MATCHING.

        Previous approach (title similarity only) failed because:
        - Different suppliers name products completely differently
        - "Smart LED Strip RGB WiFi" vs "LED Light Strip WiFi Smart" = low match

        NEW APPROACH - Multi-Signal Matching:
        1. Price similarity (within 30% range)
        2. Keyword overlap (semantic matching, not character matching)
        3. Category/niche alignment
        4. Combined confidence score

        Goals:
        1. Find products available on BOTH suppliers
        2. Compare prices to find best deal
        3. Note warehouse advantages
        4. Merge duplicate products
        """
        merged = []
        matched_cj_ids = set()
        match_details = []  # For debugging

        for ali_product in aliexpress_products:
            best_match = None
            best_score = 0.0
            best_cj_id = None

            ali_price = ali_product.get('cost_price', 0)
            ali_keywords = self._extract_product_keywords(ali_product.get('title', ''))

            # Try to find matching CJ product using multi-signal approach
            for cj_product in cj_products:
                if cj_product['product_id'] in matched_cj_ids:
                    continue

                # Calculate multi-signal match score
                match_score, match_breakdown = self._calculate_match_score(
                    ali_product, cj_product, ali_keywords
                )

                if match_score > best_score:
                    best_score = match_score
                    best_match = cj_product
                    best_cj_id = cj_product['product_id']
                    match_details.append(match_breakdown)

            # Threshold: 0.40 = relaxed match (products often named differently)
            # Previously 0.55 was too strict - AliExpress and CJ name products very differently
            if best_match and best_score >= 0.40:
                merged_product = self._merge_supplier_data(ali_product, best_match)
                merged_product['match_confidence'] = round(best_score * 100, 1)
                merged.append(merged_product)
                matched_cj_ids.add(best_cj_id)
                logger.debug(f"   [MATCH] {ali_product.get('title', '')[:30]}... -> {best_match.get('title', '')[:30]}... ({best_score:.0%})")
            else:
                # No match - add AliExpress only
                ali_product['cross_referenced'] = False
                ali_product['supplier_comparison'] = None
                ali_product['match_confidence'] = 0
                merged.append(ali_product)
                # Debug: log best attempt even if below threshold
                if best_match and best_score > 0.20:
                    logger.debug(f"   [NEAR-MISS] {ali_product.get('title', '')[:25]}... ~ {best_match.get('title', '')[:25]}... ({best_score:.0%})")

        # Add remaining CJ products (not matched)
        for cj_product in cj_products:
            if cj_product['product_id'] not in matched_cj_ids:
                cj_product['cross_referenced'] = False
                cj_product['supplier_comparison'] = None
                cj_product['match_confidence'] = 0
                merged.append(cj_product)

        # Log cross-reference stats
        matched_count = sum(1 for p in merged if p.get('cross_referenced'))
        logger.info(f"   [MATCHED] Cross-referenced: {matched_count} products found on both suppliers")

        return merged

    def _calculate_match_score(
        self,
        product1: Dict,
        product2: Dict,
        keywords1: set = None
    ) -> Tuple[float, Dict]:
        """
        Calculate multi-signal match score between two products.

        Signals:
        1. Price similarity (30% weight) - Products should be similar price
        2. Keyword overlap (40% weight) - Key product terms should match
        3. Title similarity (20% weight) - Basic text similarity
        4. Category bonus (10% weight) - Same category = likely same product

        Returns:
            (score, breakdown_dict) - Score from 0.0 to 1.0
        """
        breakdown = {
            'price_score': 0.0,
            'keyword_score': 0.0,
            'title_score': 0.0,
            'category_score': 0.0,
            'total': 0.0
        }

        # 1. PRICE SIMILARITY (30% weight)
        price1 = product1.get('cost_price', 0) or product1.get('price', 0)
        price2 = product2.get('cost_price', 0) or product2.get('price', 0)

        if price1 > 0 and price2 > 0:
            price_ratio = min(price1, price2) / max(price1, price2)
            # Products within 30% price range get full score
            if price_ratio >= 0.7:
                breakdown['price_score'] = 1.0
            elif price_ratio >= 0.5:
                breakdown['price_score'] = 0.7
            elif price_ratio >= 0.3:
                breakdown['price_score'] = 0.4
            else:
                breakdown['price_score'] = 0.0

        # 2. KEYWORD OVERLAP (40% weight) - Semantic matching
        if keywords1 is None:
            keywords1 = self._extract_product_keywords(product1.get('title', ''))
        keywords2 = self._extract_product_keywords(product2.get('title', ''))

        if keywords1 and keywords2:
            # Enhanced keyword matching with related terms
            # First, expand keywords with synonyms
            expanded1 = self._expand_keywords(keywords1)
            expanded2 = self._expand_keywords(keywords2)

            # Jaccard similarity on expanded sets
            intersection = expanded1 & expanded2
            union = expanded1 | expanded2
            if union:
                # Base Jaccard score
                jaccard = len(intersection) / len(union)

                # Bonus for having ANY overlap (encourages matches)
                if intersection:
                    # At least 1 common keyword = 0.3 minimum
                    breakdown['keyword_score'] = max(0.3, jaccard)
                else:
                    breakdown['keyword_score'] = jaccard

        # 3. TITLE SIMILARITY (20% weight) - Character-level backup
        title1 = self._normalize_title(product1.get('title', ''))
        title2 = self._normalize_title(product2.get('title', ''))
        breakdown['title_score'] = self._title_similarity(title1, title2)

        # 4. CATEGORY BONUS (10% weight)
        cat1 = product1.get('category_name', '') or product1.get('niche', '')
        cat2 = product2.get('category_name', '') or product2.get('niche', '')
        if cat1 and cat2 and (cat1.lower() in cat2.lower() or cat2.lower() in cat1.lower()):
            breakdown['category_score'] = 1.0

        # Calculate weighted total
        breakdown['total'] = (
            breakdown['price_score'] * 0.30 +
            breakdown['keyword_score'] * 0.40 +
            breakdown['title_score'] * 0.20 +
            breakdown['category_score'] * 0.10
        )

        return breakdown['total'], breakdown

    def _extract_product_keywords(self, title: str) -> set:
        """
        Extract meaningful product keywords from title.

        This is SEMANTIC extraction - focuses on product-defining words:
        - Product type (led, strip, light, bulb, speaker, etc.)
        - Features (wifi, smart, rgb, bluetooth, wireless, etc.)
        - Brand terms (if recognizable)

        NOT included:
        - Filler words (the, a, for, with, etc.)
        - Size/color variations (handled separately)
        - Numbers (5m, 10w, etc.)
        """
        if not title:
            return set()

        # Convert to lowercase and split
        words = title.lower().split()

        # Remove very short words and numbers
        words = [w for w in words if len(w) > 2 and not w.isdigit()]

        # Clean punctuation
        words = [re.sub(r'[^\w]', '', w) for w in words]

        # Product-defining keywords (high signal)
        PRODUCT_KEYWORDS = {
            # Product types
            'led', 'light', 'lamp', 'bulb', 'strip', 'neon', 'rgb', 'rgbic',
            'speaker', 'bluetooth', 'wireless', 'wifi', 'smart', 'sensor',
            'camera', 'charger', 'cable', 'hub', 'adapter', 'controller',
            'plug', 'outlet', 'switch', 'dimmer', 'remote', 'timer',
            'thermostat', 'doorbell', 'lock', 'alarm', 'detector',
            'purifier', 'humidifier', 'fan', 'heater', 'cooler',
            'vacuum', 'robot', 'cleaner', 'mop', 'sweeper',
            'blender', 'mixer', 'grinder', 'juicer', 'maker',
            'fryer', 'cooker', 'oven', 'microwave', 'toaster',
            'kettle', 'coffee', 'tea', 'water', 'filter',
            'scale', 'thermometer', 'monitor', 'tracker',
            'watch', 'band', 'earbuds', 'headphones', 'earphones',
            'projector', 'display', 'screen', 'monitor',
            'keyboard', 'mouse', 'pad', 'stand', 'mount', 'holder',
            # Features
            'portable', 'rechargeable', 'foldable', 'adjustable', 'magnetic',
            'waterproof', 'dustproof', 'shockproof', 'fireproof',
            'automatic', 'manual', 'electric', 'solar', 'battery',
            'usb', 'typec', 'hdmi', 'aux', 'micro',
            'mini', 'pro', 'max', 'plus', 'lite', 'ultra',
            # Materials
            'silicone', 'plastic', 'metal', 'aluminum', 'steel', 'wood', 'bamboo',
            'leather', 'fabric', 'nylon', 'cotton', 'glass', 'ceramic',
        }

        # Filler words to exclude
        FILLER_WORDS = {
            'the', 'and', 'for', 'with', 'from', 'this', 'that', 'your',
            'our', 'new', 'hot', 'sale', 'free', 'shipping', 'best', 'top',
            'quality', 'high', 'low', 'good', 'great', 'nice', 'cool',
            'home', 'office', 'kitchen', 'bedroom', 'bathroom', 'outdoor',
            'indoor', 'garden', 'car', 'auto', 'room', 'house', 'apartment',
            'pcs', 'set', 'pack', 'piece', 'lot', 'pair', 'unit',
        }

        # Extract keywords
        keywords = set()
        for word in words:
            if word in FILLER_WORDS:
                continue
            if word in PRODUCT_KEYWORDS:
                keywords.add(word)
            elif len(word) >= 4:  # Include longer words that might be product-specific
                keywords.add(word)

        return keywords

    def _expand_keywords(self, keywords: set) -> set:
        """
        Expand keyword set with synonyms and related terms.

        This helps match products that use different terminology:
        - "wifi" <-> "wireless"
        - "led" <-> "light"
        - "smart" <-> "intelligent"
        """
        SYNONYMS = {
            'wifi': {'wireless', 'wifi', 'wi-fi'},
            'wireless': {'wifi', 'wireless', 'bluetooth'},
            'led': {'led', 'light', 'lamp', 'bulb'},
            'light': {'led', 'light', 'lamp', 'bulb', 'lighting'},
            'lamp': {'led', 'light', 'lamp', 'bulb'},
            'bulb': {'led', 'light', 'lamp', 'bulb'},
            'smart': {'smart', 'intelligent', 'auto', 'wifi'},
            'intelligent': {'smart', 'intelligent'},
            'strip': {'strip', 'tape', 'ribbon'},
            'tape': {'strip', 'tape', 'ribbon'},
            'rgb': {'rgb', 'rgbic', 'color', 'colorful'},
            'rgbic': {'rgb', 'rgbic', 'color'},
            'plug': {'plug', 'socket', 'outlet'},
            'socket': {'plug', 'socket', 'outlet'},
            'outlet': {'plug', 'socket', 'outlet'},
            'charger': {'charger', 'charging'},
            'charging': {'charger', 'charging'},
            'speaker': {'speaker', 'audio', 'sound'},
            'headphones': {'headphones', 'earphones', 'earbuds', 'headset'},
            'earphones': {'headphones', 'earphones', 'earbuds'},
            'earbuds': {'headphones', 'earphones', 'earbuds'},
            'camera': {'camera', 'cam', 'webcam'},
            'sensor': {'sensor', 'detector', 'monitor'},
            'detector': {'sensor', 'detector'},
            'remote': {'remote', 'controller', 'control'},
            'controller': {'remote', 'controller', 'control'},
            'portable': {'portable', 'mini', 'compact'},
            'mini': {'portable', 'mini', 'compact', 'small'},
        }

        expanded = set(keywords)
        for kw in keywords:
            if kw in SYNONYMS:
                expanded.update(SYNONYMS[kw])
        return expanded

    def _build_aliexpress_evidence(self, item: Dict) -> Dict:
        """Build AE buyer-evidence dict from the raw affiliate-API item.

        Task #19 — we already pay for this data via the AE affiliate call
        that discovers the product. These fields are buyer-derived and worth
        keeping:

          - ``evaluate_rate`` — AE's aggregate positive-feedback percentage
            across all buyers who rated the product (0-100). Returned as a
            string like "95.0" or "95%".
          - ``lastest_volume`` — recent sales count (acts as a review-count
            proxy: more sales ≈ more feedback behind the percentage).

        We deliberately DO NOT treat this as equal to Amazon reviews:
          - no verbatim review text, no timestamp cohort, no per-review url
          - the percentage is aggregated across product variants
          - AE ratings skew generous (buyers who leave ratings tend positive)

        So the caller (``_calculate_scores``) caps the sentiment contribution
        of this signal; see the "aliexpress_api" branch there.

        Returns a dict with a uniform shape whether or not real data exists,
        so the evidence panel can render it without null-checks.
        """
        rating_pct_raw = item.get('evaluate_rate')
        rating_pct: Optional[float] = None
        if rating_pct_raw not in (None, '', 0, '0'):
            try:
                rating_pct = float(str(rating_pct_raw).replace('%', '').strip())
            except (TypeError, ValueError):
                rating_pct = None

        # Convert 0-100 positive-feedback to 0-5 stars the UI understands.
        rating_stars: Optional[float] = None
        if rating_pct is not None:
            rating_stars = round(rating_pct / 20.0, 2)

        try:
            recent_sales = int(item.get('lastest_volume') or 0)
        except (TypeError, ValueError):
            recent_sales = 0

        # buzz_score mirrors the Amazon pattern: rating strength weighted by
        # confidence from sample size. We're more conservative than Amazon
        # because AE positive-feedback-% is structurally optimistic.
        #
        # rating_norm:     0..1 (pct / 100)
        # volume_factor:   0..1 (capped at 2k recent sales)
        # buzz_score:      0..100, capped at 85 (never match Amazon's 100)
        buzz_score: Optional[float] = None
        found_real_rating = rating_pct is not None
        if found_real_rating:
            rating_norm = (rating_pct or 0) / 100.0
            volume_factor = min(1.0, recent_sales / 2000.0)
            # 70% of the score comes from rating, 30% from sales confidence.
            # Multiply by 100 and cap at 85 so it can rise above the 55
            # baseline and above CJ's 70 cap, but never reach Amazon's ceiling.
            raw = (0.7 * rating_norm + 0.3 * volume_factor) * 100
            buzz_score = round(min(85.0, raw), 2)

        return {
            'found_real_rating': found_real_rating,
            'rating_pct': rating_pct,
            'rating_stars': rating_stars,
            'recent_sales': recent_sales,
            'buzz_score': buzz_score,
            'supplier_url': item.get('promotion_link') or item.get('product_detail_url') or '',
            'source_type': 'aliexpress_affiliate_api',
            'fetched_at': datetime.now().isoformat(),
        }

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison"""
        if not title:
            return ""
        # Remove common filler words and normalize
        title = title.lower()
        # Remove size/color variations
        title = re.sub(r'\b(small|medium|large|xl|xxl|s|m|l)\b', '', title)
        title = re.sub(r'\b(black|white|red|blue|green|pink|gold|silver)\b', '', title)
        # Remove numbers and special chars
        title = re.sub(r'[0-9]+', '', title)
        title = re.sub(r'[^\w\s]', ' ', title)
        # Remove extra spaces
        title = ' '.join(title.split())
        return title.strip()

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two product titles"""
        if not title1 or not title2:
            return 0.0
        return SequenceMatcher(None, title1, title2).ratio()
    
    def _merge_supplier_data(self, ali_product: Dict, cj_product: Dict) -> Dict:
        """Merge data when same product found on both suppliers"""
        # Start with AliExpress data (usually more complete)
        merged = ali_product.copy()

        # Mark as cross-referenced
        merged['cross_referenced'] = True
        merged['available_on'] = ['aliexpress', 'cj_dropshipping']

        # Add CJ data to data_sources
        if 'data_sources' not in merged:
            merged['data_sources'] = {}
        merged['data_sources']['cj_dropshipping'] = cj_product.get('data_sources', {}).get('cj_dropshipping', {})
        merged['data_sources']['cj_dropshipping']['available'] = True

        # ================================================================
        # MERGE IMAGES FROM BOTH SUPPLIERS (More complete coverage)
        # ================================================================
        ali_images = ali_product.get('all_images', [])
        cj_images = cj_product.get('all_images', [])

        # Combine images, removing duplicates, keeping AliExpress first
        all_images = list(ali_images)  # Start with AliExpress
        for img in cj_images:
            if img and img not in all_images:
                all_images.append(img)

        # Limit to 15 images max (more than before since we have 2 sources)
        merged['all_images'] = all_images[:15]
        merged['image_count'] = len(merged['all_images'])
        logger.debug(f"   [IMAGES] Merged: {len(ali_images)} AliExpress + {len(cj_images)} CJ = {len(merged['all_images'])} total")

        # Compare prices
        ali_cost = ali_product.get('cost_price', 0)
        cj_cost = cj_product.get('cost_price', 0)

        # Supplier comparison
        merged['supplier_comparison'] = {
            'aliexpress_cost': ali_cost,
            'cj_cost': cj_cost,
            'price_diff': abs(ali_cost - cj_cost),
            'cheaper_on': 'cj_dropshipping' if cj_cost < ali_cost else 'aliexpress',
            'cj_warehouse': cj_product.get('warehouse', 'CN'),
            'cj_us_warehouse': cj_product.get('us_warehouse', False),
            'cj_eu_warehouse': cj_product.get('eu_warehouse', False),
        }

        # Recommendation based on comparison
        if cj_product.get('us_warehouse') or cj_product.get('eu_warehouse'):
            merged['sourcing_recommendation'] = f"SOURCE FROM CJ: {cj_product.get('warehouse', 'US/EU')} warehouse = faster shipping"
        elif cj_cost < ali_cost * 0.9:  # CJ is 10%+ cheaper
            merged['sourcing_recommendation'] = f"SOURCE FROM CJ: ${cj_cost:.2f} vs ${ali_cost:.2f} on AliExpress"
        else:
            merged['sourcing_recommendation'] = "SOURCE FROM ALIEXPRESS: Better commission rate"

        # Store CJ product ID for reference
        merged['cj_pid'] = cj_product.get('cj_pid', '')
        merged['cj_supplier_url'] = cj_product.get('supplier_url', '')

        return merged
    
    # =========================================================================
    # STEP 4: SENTIMENT ENRICHMENT
    # =========================================================================
    
    async def _enrich_with_twitter_sentiment(self, products: List[Dict]) -> List[Dict]:
        """
        Add X/Twitter sentiment via xAI Grok with EVIDENCE TRAIL.

        Behavior (post-Fix #15a):
        - Uses hallucination-resistant prompt (see xai_twitter.get_product_sentiment)
        - If found_real_tweets=False, sentiment_score is set to None (no fake 55 default later)
        - Persists full evidence blob (sample_tweets, engagement, praise/complaints) on product['twitter_evidence']
        - Honest about Grok's limitations: Grok-3 is NOT a live Twitter scraper. The "sample_tweets"
          returned are PARAPHRASED from Grok's training data, not verbatim live posts. Treat as
          "qualitative sentiment signal" rather than "verified live tweets."
        """
        if not self.xai_available:
            return products

        from datetime import datetime as _dt

        # Parallelize Grok calls - each call is 3-5s sequentially, 10 products = 30-50s,
        # which blew through the 6s SENTIMENT_SOURCE_TIMEOUT and caused most products
        # to have no twitter_evidence at all. With gather, 10 products complete in the
        # time of the slowest single call (~5s).
        async def _fetch_one(product: Dict) -> tuple:
            """Return (product, sentiment_or_None, error_or_None)."""
            try:
                sentiment = await self.xai_twitter.analyze_product_sentiment(
                    product.get('title', '')[:50]
                )
                return (product, sentiment, None)
            except Exception as e:
                return (product, None, str(e))

        # Enrichment must cover more products than the final output count because
        # products get re-scored and re-ranked after enrichment - the top 10 of the
        # final output can include products that were at positions 10-20 in the
        # pre-scoring list. With parallelization this is cheap (all calls run
        # concurrently, so 20 takes the same wall time as 10).
        target_products = products[:20]
        results = await asyncio.gather(
            *[_fetch_one(p) for p in target_products],
            return_exceptions=False
        )

        for product, sentiment, err in results:
            # Always initialize data_sources
            if 'data_sources' not in product:
                product['data_sources'] = {}

            # Exception during the call
            if err is not None:
                logger.warning(f"Twitter sentiment failed for {product.get('title', '')[:40]}: {err}")
                product['data_sources']['x_twitter'] = {
                    'available': False, 'found_real_tweets': False, 'reason': err[:100]
                }
                product['twitter_sentiment'] = None
                # POST-FIX #15: still set evidence on error path so UI can show
                # "Twitter data unavailable" specifically for this product.
                product['twitter_evidence'] = {
                    'found_real_tweets': False,
                    'tweet_count': 0,
                    'sentiment_score': None,
                    'sample_tweets': [],
                    'common_praise': [],
                    'common_complaints': [],
                    'engagement': {'total_likes': 0, 'total_retweets': 0, 'total_replies': 0},
                    'error': err[:200],
                    'fetched_at': _dt.utcnow().isoformat(),
                    'source_type': 'grok_paraphrase',
                }
                continue

            # API returned error structure
            if not sentiment or sentiment.get('error'):
                err_msg = sentiment.get('error', 'unknown') if sentiment else 'no_response'
                product['data_sources']['x_twitter'] = {
                    'available': False, 'found_real_tweets': False, 'reason': err_msg,
                }
                product['twitter_sentiment'] = None
                product['twitter_evidence'] = {
                    'found_real_tweets': False,
                    'tweet_count': 0,
                    'sentiment_score': None,
                    'sample_tweets': [],
                    'common_praise': [],
                    'common_complaints': [],
                    'engagement': {'total_likes': 0, 'total_retweets': 0, 'total_replies': 0},
                    'error': str(err_msg)[:200],
                    'fetched_at': _dt.utcnow().isoformat(),
                    'source_type': 'grok_paraphrase',
                }
                continue

            found_real = bool(sentiment.get('found_real_tweets', False))
            raw_score = sentiment.get('sentiment_score')  # may be None when found_real=false

            if found_real and raw_score is not None:
                product['twitter_sentiment'] = raw_score
                product['twitter_buzz'] = sentiment.get('buzz_level', 'low')
            else:
                # Honest empty state - no fake default
                product['twitter_sentiment'] = None
                product['twitter_buzz'] = None

            # Persist evidence trail regardless of outcome
            engagement = sentiment.get('engagement') or {}
            # search_level tells the UI whether tweets are about this exact product
            # or the product category. "product" > "category" > "none".
            search_level = sentiment.get('search_level') or ('product' if found_real else 'none')
            product['twitter_evidence'] = {
                'found_real_tweets': found_real,
                'search_level': search_level,  # 'product' | 'category' | 'none'
                'category_searched': sentiment.get('category_searched'),  # category phrase when search_level='category'
                'tweet_count': sentiment.get('tweet_count', 0),
                'sentiment_score': raw_score,
                'sentiment_label': sentiment.get('sentiment'),
                'buzz_level': sentiment.get('buzz_level'),
                'sample_tweets': sentiment.get('sample_tweets', []) or [],
                'common_praise': sentiment.get('common_praise', []) or [],
                'common_complaints': sentiment.get('common_complaints', []) or [],
                'engagement': {
                    'total_likes': engagement.get('total_likes', 0),
                    'total_retweets': engagement.get('total_retweets', 0),
                    'total_replies': engagement.get('total_replies', 0),
                },
                'recommendation': sentiment.get('recommendation'),
                'note': sentiment.get('note'),
                'fetched_at': _dt.utcnow().isoformat(),
                # Transparency: these tweets are paraphrased by the model, not verbatim live posts
                'source_type': 'grok_paraphrase',
            }

            # Update data_sources with the full picture for scoring
            product['data_sources']['x_twitter'] = {
                'available': found_real,
                'found_real_tweets': found_real,
                'sentiment': sentiment.get('sentiment'),
                'sentiment_score': raw_score,
                'buzz': sentiment.get('buzz_level'),
                'tweet_count': sentiment.get('tweet_count', 0),
            }

        return products

    async def _enrich_with_amazon_reviews(self, products: List[Dict], niche: str) -> List[Dict]:
        """
        Add Amazon review data as the primary social signal (Task #18).

        Why this is the strongest sentiment signal we have:
        - Reddit/Twitter measure *conversation*. Amazon measures *purchases*.
        - Aggregate rating × review count reflects real market validation.
        - Works for both AliExpress- and CJ-sourced products (they're often
          listed on Amazon by arbitrage sellers, so fuzzy title match hits).

        Economic design:
        - ONE Apify `search_amazon` call per niche (~$0.02-0.05), not per
          product (which would be ~$0.50+ per discovery).
        - Fuzzy-match each supplier product against the niche pool using
          token-overlap + sequence similarity.
        - Top 3 matches per product persisted as clickable evidence.

        Output per product (top 15 enriched):
        - product['amazon_evidence']: dict with top_matches, aggregate_rating,
          buzz_score, etc. (see amazon_reviews.py for shape)
        - product['amazon_buzz']: scalar 0-100 signal for OI scoring
        - product['amazon_rating']: weighted avg rating
        - product['amazon_review_count']: total reviews across top matches
        - product['data_sources']['amazon_reviews']: availability/metadata

        Products beyond the top 15 get empty evidence (honest, not faked).
        """
        if not self.amazon_reviews_available or not products:
            return products

        # Step 1: ONE Amazon search for the whole niche
        try:
            pool = await self.amazon_reviews.search_niche(
                niche=niche,
                max_items=25,
                min_rating=3.5,
            )
        except Exception as e:
            logger.warning(f"[AMAZON] search_niche failed for '{niche}': {e}")
            return products

        if not pool:
            logger.info(
                f"[AMAZON] No Amazon pool returned for niche '{niche}' "
                f"(last_error: {self.amazon_reviews.last_error})"
            )
            # Mark all products as 'searched but nothing found' so the UI
            # can distinguish "we didn't look" from "we looked, found nothing"
            for product in products:
                if 'data_sources' not in product:
                    product['data_sources'] = {}
                product['data_sources']['amazon_reviews'] = {
                    'available': False,
                    'niche_searched': niche,
                    'reason': 'empty_pool',
                }
                product['amazon_evidence'] = {
                    'found_matches': False,
                    'match_count': 0,
                    'top_matches': [],
                    'aggregate_rating': None,
                    'total_reviews': 0,
                    'buzz_score': 0.0,
                    'niche_searched': niche,
                    'reason': 'empty_pool',
                }
                product['amazon_buzz'] = 0.0
            return products

        logger.info(f"[AMAZON] Pool: {len(pool)} listings for niche '{niche}'")

        # Step 2: Fuzzy-match each of the top 15 products against the pool.
        # Products beyond 15 aren't enriched (same cap as reddit) to keep the
        # payload small — enrichment is about the candidates the user actually sees.
        target_products = products[:15]
        matched_count = 0

        for product in target_products:
            evidence = self.amazon_reviews.match_products(
                our_product=product,
                amazon_pool=pool,
                top_n=3,
                min_similarity=0.20,
                niche=niche,
            )

            product['amazon_evidence'] = evidence
            if 'data_sources' not in product:
                product['data_sources'] = {}

            if evidence.get('found_matches'):
                matched_count += 1
                product['amazon_buzz'] = evidence.get('buzz_score', 0.0)
                product['amazon_rating'] = evidence.get('aggregate_rating')
                product['amazon_review_count'] = evidence.get('total_reviews', 0)
                product['data_sources']['amazon_reviews'] = {
                    'available': True,
                    'niche_searched': niche,
                    'pool_size': len(pool),
                    'match_count': evidence.get('match_count', 0),
                    'aggregate_rating': evidence.get('aggregate_rating'),
                    'total_reviews': evidence.get('total_reviews', 0),
                    'buzz_score': evidence.get('buzz_score', 0.0),
                }
            else:
                product['amazon_buzz'] = 0.0
                product['amazon_rating'] = None
                product['amazon_review_count'] = 0
                product['data_sources']['amazon_reviews'] = {
                    'available': False,
                    'niche_searched': niche,
                    'pool_size': len(pool),
                    'reason': evidence.get('reason', 'no_similar_listings'),
                }

        # Products beyond top 15: mark as not-enriched rather than silently empty
        for product in products[15:]:
            if 'data_sources' not in product:
                product['data_sources'] = {}
            product['data_sources']['amazon_reviews'] = {
                'available': False,
                'niche_searched': niche,
                'reason': 'outside_enrichment_cap',
            }
            product.setdefault('amazon_evidence', None)
            product.setdefault('amazon_buzz', 0.0)

        logger.info(
            f"[AMAZON] Enriched {matched_count}/{len(target_products)} products "
            f"with Amazon evidence from {len(pool)}-listing pool"
        )
        return products

    async def _enrich_with_reddit_sentiment(self, products: List[Dict], niche: str) -> List[Dict]:
        """
        Add Reddit community sentiment via SEARCH (Fix #15c).

        Strategy:
        1. For each product, build a search query from its significant tokens
        2. Search 2-3 subreddits per niche using /r/{sub}/search.json?q=...&restrict_sr=on
        3. Apply ≥2 significant-token overlap as a quality filter on returned results
        4. Persist matched posts (with real clickable URLs) as product['reddit_evidence']

        This replaces the old "browse top posts and hope for keyword overlap" logic
        which returned 0 matches even for popular products. Search-based matching
        actually asks Reddit "show me posts that mention this product".

        Rate limiting: Reddit's public JSON API allows ~10 req/min unauthenticated.
        We cap concurrency at 5 and enrich only the top 15 products to stay well
        below the limit. Products beyond the cap get reddit_evidence=None, which
        is honest.
        """
        if not self.reddit_available:
            return products

        import re
        from datetime import datetime as _dt

        # Generic words that would flood search and produce false matches.
        STOPWORDS = {
            "about", "above", "after", "again", "against", "also", "been", "before",
            "being", "below", "between", "both", "doing", "down", "during", "each",
            "from", "further", "have", "having", "here", "into", "itself", "just",
            "more", "most", "much", "must", "only", "other", "over", "same", "some",
            "such", "than", "that", "their", "them", "then", "there", "these", "they",
            "this", "those", "through", "under", "until", "very", "what", "when",
            "where", "which", "while", "with", "would", "your", "yours",
            "smart", "home", "best", "review", "reviews", "cheap", "good", "great",
            "made", "need", "want", "love", "like", "help", "year", "years", "today",
            "time", "times", "thing", "things", "work", "works", "stuff", "setup",
            "product", "products", "price", "prices", "amazon", "tiktok",
        }

        # 2-3 subreddits per niche. More subreddits = more coverage but more HTTP calls.
        # Keep to 2 per niche to stay comfortably under Reddit's rate limit.
        subreddit_map = {
            "smart_home": ["smarthome", "homeautomation"],
            "kitchen": ["Cooking", "MealPrepSunday"],
            "fitness": ["homegym", "fitness"],
            "beauty": ["SkincareAddiction", "MakeupAddiction"],
            "tech": ["gadgets", "BuyItForLife"],
            "pet": ["dogs", "cats"],
            "gaming": ["gaming", "pcgaming"],
        }
        subreddits = subreddit_map.get(niche, ["BuyItForLife", "shutupandtakemymoney"])

        # Concrete product nouns - the THING being sold. Used to build quoted-phrase
        # queries that prioritize posts about this specific product type over posts
        # that just happen to mention the same capabilities. Grows over time as we
        # see false matches in production.
        PRODUCT_NOUNS = {
            # Electronics / smart home
            "plug", "strip", "bulb", "switch", "adapter", "camera", "speaker", "hub",
            "sensor", "socket", "outlet", "doorbell", "thermostat", "lock", "light",
            "cable", "dongle", "monitor", "display", "controller", "headphones",
            "earbuds", "router", "extender", "charger", "battery", "projector",
            "tablet", "phone", "watch",
            # Kitchen / appliances
            "kettle", "blender", "toaster", "fryer", "cooker", "mop", "vacuum",
            "fan", "heater", "purifier", "humidifier", "pot", "pan", "knife",
            "scale", "mixer", "grinder", "maker", "oven",
            # Fitness / health
            "dumbbell", "bike", "treadmill", "tracker", "massager", "roller",
            # Pet
            "collar", "leash", "feeder", "fountain",
            # Beauty / personal care
            "brush", "razor", "trimmer", "serum", "cream", "mask",
            # Auto / tools
            "carplay",  # "wireless carplay adapter" is a common product type
        }

        # Tokens that indicate CAPABILITIES or FEATURES, not the product itself.
        # If a match overlaps ONLY on these, it's likely category-level discussion
        # (e.g. "people talking about Alexa in general" vs "talking about this plug").
        FEATURE_TOKENS = {
            "alexa", "google", "siri", "homekit", "voice", "assistant", "control",
            "wireless", "bluetooth", "remote", "compatible", "support",
            "wifi", "app", "automation", "connected", "portable", "rechargeable",
            "waterproof", "cordless",
        }

        def _significant_tokens(text: str) -> list:
            """Extract meaningful tokens in order (preserves query ordering)."""
            tokens = re.split(r"[^a-z0-9]+", text.lower())
            return [
                t for t in tokens
                if len(t) >= 5 and t not in STOPWORDS and not t.isdigit()
            ]

        def _build_query(title: str):
            """
            Build a Reddit search query focused on the PRODUCT TYPE, not capabilities.

            Uses a quoted phrase around the product noun + its preceding qualifier
            (e.g., "wifi plug", "led strip") so Reddit's search prioritizes posts
            actually about the product, not posts about Alexa/voice in general.

            Returns (query_string, product_type_tokens) so the caller can tag
            match quality by whether the product_type appeared in the overlap.
            """
            toks = _significant_tokens(title)
            if not toks:
                return ("", [])

            # Look for a product noun anywhere in the sig tokens, preferring later
            # occurrences (title format is usually [brand] [adj] [noun] [features]).
            product_noun_idx = None
            for i in range(len(toks) - 1, -1, -1):
                if toks[i] in PRODUCT_NOUNS:
                    product_noun_idx = i
                    break

            if product_noun_idx is not None:
                # Combine with the preceding qualifier if one exists, to form a
                # more specific phrase ("wifi plug" > "plug", "led strip" > "strip").
                if product_noun_idx > 0:
                    phrase_tokens = [toks[product_noun_idx - 1], toks[product_noun_idx]]
                else:
                    phrase_tokens = [toks[product_noun_idx]]

                quoted = f'"{" ".join(phrase_tokens)}"' if len(phrase_tokens) >= 2 else phrase_tokens[0]
                remaining = [t for t in toks if t not in phrase_tokens][:2]
                query = quoted + (" " + " ".join(remaining) if remaining else "")
                return (query, phrase_tokens)

            # No recognizable product noun - fall back to first 3 tokens unquoted.
            # These products get less-targeted category-level matches.
            return (" ".join(toks[:3]), toks[:1])

        def _determine_match_type(overlap: set, product_type_tokens: list) -> str:
            """
            Classify a Reddit match as 'product' (concrete product discussion)
            or 'category' (general category/capability discussion).

            'product' = the overlap contains at least one product-noun token
            'category' = overlap is only capabilities/features (e.g. alexa, voice)
            """
            ptoks = set(product_type_tokens or [])
            if overlap & ptoks:
                return "product"
            # If overlap has ANY concrete non-feature, non-stopword token, it's
            # product-ish. If it's all FEATURE_TOKENS, it's category chatter.
            concrete = {t for t in overlap if t not in FEATURE_TOKENS}
            return "product" if concrete else "category"

        # Concurrency cap to respect Reddit's rate limits and avoid hammering their API.
        semaphore = asyncio.Semaphore(5)

        async def _search_one(product: Dict, subreddit: str, query: str, product_type_tokens: list) -> tuple:
            """Return (product_id, subreddit, matched_posts list) after quality filter."""
            async with semaphore:
                try:
                    posts = await self.reddit.search_subreddit_for_product(
                        subreddit=subreddit,
                        query=query,
                        time_filter="year",
                        limit=10,
                    )
                except Exception as e:
                    logger.debug(f"Reddit search r/{subreddit} for '{query}' errored: {e}")
                    return (product.get('product_id'), subreddit, [])

                # Apply ≥2 overlap quality filter on returned results.
                # Reddit's search is lenient - we want to be stricter about what
                # counts as a real match so we don't persist misleading evidence.
                product_tok_set = set(_significant_tokens(product.get('title', '')))
                if len(product_tok_set) < 2:
                    return (product.get('product_id'), subreddit, [])

                matches = []
                for post in posts:
                    post_tok_set = set(_significant_tokens(post.get("title", "")))
                    # Also consider selftext excerpt for match signal
                    if post.get("selftext_excerpt"):
                        post_tok_set |= set(_significant_tokens(post["selftext_excerpt"]))

                    overlap = product_tok_set & post_tok_set
                    if len(overlap) >= 2:
                        match_type = _determine_match_type(overlap, product_type_tokens)
                        matches.append({
                            'title': post.get("title", ""),
                            'url': post.get("url", ""),
                            'score': post.get("score", 0),
                            'num_comments': post.get("num_comments", 0),
                            'upvote_ratio': post.get("upvote_ratio", 0.0),
                            'subreddit': subreddit,
                            'author': post.get("author", ""),
                            'created_utc': post.get("created_utc", 0),
                            'matched_on': sorted(overlap),
                            'match_type': match_type,  # 'product' or 'category'
                            'selftext_excerpt': post.get("selftext_excerpt", ""),
                        })
                return (product.get('product_id'), subreddit, matches)

        # Build search tasks: top 15 products × 2 subreddits
        # = max 30 requests, running 5 at a time ≈ 6-10s wall time total
        target_products = products[:15]
        tasks = []
        product_type_by_id = {}  # so merge step can also reference it
        for product in target_products:
            query, product_type_tokens = _build_query(product.get('title', ''))
            if not query or len(query.split()) < 1:
                # Product title has no significant tokens - skip (set empty evidence later)
                continue
            product_type_by_id[product.get('product_id')] = product_type_tokens
            for sub in subreddits:
                tasks.append(_search_one(product, sub, query, product_type_tokens))

        if not tasks:
            return products

        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate matches per product across all subreddits searched
        matches_by_product = {}  # {product_id: [merged post dicts]}
        for result in search_results:
            if isinstance(result, Exception):
                continue
            pid, subreddit, matches = result
            if pid is None:
                continue
            matches_by_product.setdefault(pid, []).extend(matches)

        # Attach evidence to each product + deduplicate by URL
        for product in target_products:
            pid = product.get('product_id')
            all_matches = matches_by_product.get(pid, [])
            # Dedupe by URL (a post can appear in results for multiple subs)
            seen_urls = set()
            unique_matches = []
            for m in all_matches:
                u = m.get('url')
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    unique_matches.append(m)
            # Sort: (a) 'product' matches above 'category', then (b) by upvote score desc.
            # This way, users see concrete product discussion at the top of the
            # evidence list, with category-level chatter below.
            unique_matches.sort(
                key=lambda x: (
                    0 if x.get('match_type') == 'product' else 1,
                    -(x.get('score') or 0),
                )
            )

            if unique_matches:
                product_matches = [m for m in unique_matches if m.get('match_type') == 'product']
                product['reddit_mentions'] = len(unique_matches)
                product['reddit_product_matches'] = len(product_matches)
                product['reddit_category_matches'] = len(unique_matches) - len(product_matches)
                if 'data_sources' not in product:
                    product['data_sources'] = {}
                product['data_sources']['reddit'] = {
                    'available': True,
                    'subreddits_searched': subreddits,
                    'mentions': len(unique_matches),
                    'product_matches': len(product_matches),
                    'category_matches': len(unique_matches) - len(product_matches),
                }
                # Keep top 5 matches for evidence trail (UI will render clickable)
                product['reddit_evidence'] = unique_matches[:5]
            else:
                # Honest empty state - we searched and found nothing
                if 'data_sources' not in product:
                    product['data_sources'] = {}
                product['data_sources']['reddit'] = {
                    'available': False,
                    'subreddits_searched': subreddits,
                    'mentions': 0,
                    'reason': 'no_matching_posts',
                }
                product['reddit_evidence'] = []

        return products
    
    # =========================================================================
    # STEP 5: SCORING (FIXED - Extract real data, build score_breakdown)
    # =========================================================================

    def _calculate_scores(self, products: List[Dict]) -> List[Dict]:
        """
        Calculate OI Score with cross-reference bonus.

        Components:
        - Demand (25%): Sales, BSR, views
        - Trend (25%): Google Trends, virality
        - Sentiment (15%): Twitter + Reddit
        - Profit (15%): Margin percentage
        - Sourcing (20%): Cross-reference bonus, warehouse advantage

        IMPORTANT: This builds score_breakdown dict for AI analyzer compatibility
        """
        for product in products:
            data_sources = product.get('data_sources', {})

            # ================================================================
            # RELEVANCE CHECK - Filter off-topic products
            # ================================================================
            niche = product.get('niche', '').lower()
            title = product.get('title', '').lower()
            relevance_score = self._calculate_relevance(title, niche)
            product['relevance_score'] = relevance_score

            # If product is clearly irrelevant, mark it early
            if relevance_score < 20:
                product['is_relevant'] = False
                product['relevance_note'] = 'Off-topic product - does not match niche keywords'
            else:
                product['is_relevant'] = True
                product['relevance_note'] = None

            # ================================================================
            # EXTRACT REAL DATA FROM data_sources
            # ================================================================

            # AliExpress data
            ali_data = data_sources.get('aliexpress', {})
            ali_orders = ali_data.get('orders', 0) or product.get('sales_count', 0)
            ali_commission = float(str(ali_data.get('commission', '0')).replace('%', '')) if ali_data.get('commission') else 0

            # CJ Dropshipping data
            cj_data = data_sources.get('cj_dropshipping', {})
            cj_available = cj_data.get('available', False)
            cj_warehouse = cj_data.get('warehouse', '')

            # Twitter/X sentiment data
            # IMPORTANT: preserve None (no data) vs 0 (neutral) distinction.
            # Post-Fix #15, enrichment sets twitter_sentiment=None when found_real_tweets=false.
            twitter_data = data_sources.get('x_twitter', {})
            _twitter_from_ds = twitter_data.get('sentiment_score')
            _twitter_from_prod = product.get('twitter_sentiment')
            twitter_sentiment_raw = _twitter_from_ds if _twitter_from_ds is not None else _twitter_from_prod
            # twitter_sentiment_raw is now: float (real signal), 0 (neutral), or None (no data)
            twitter_buzz = twitter_data.get('buzz') or 'low'
            twitter_found_real = bool(twitter_data.get('found_real_tweets', False))

            # Reddit data
            reddit_data = data_sources.get('reddit', {})
            reddit_mentions = reddit_data.get('mentions') or product.get('reddit_mentions') or 0

            # Amazon reviews data (Task #18 - primary social signal)
            amazon_rev_data = data_sources.get('amazon_reviews', {})
            amazon_buzz_raw = amazon_rev_data.get('buzz_score') or product.get('amazon_buzz') or 0.0
            amazon_rating_raw = amazon_rev_data.get('aggregate_rating') or product.get('amazon_rating')
            amazon_review_count_raw = amazon_rev_data.get('total_reviews') or product.get('amazon_review_count') or 0
            amazon_found_real = bool(amazon_rev_data.get('available', False))

            # Task #19: AliExpress buyer-derived signals harvested at normalize
            # time from the affiliate API (not a separate paid call).
            # found_real_rating means evaluate_rate came back non-empty.
            # Strength sits between CJ supplier proxy (structural) and Amazon
            # (review-text-backed): AE gives us a real buyer-derived rating
            # but no verbatim reviews.
            ae_signals = data_sources.get('aliexpress_signals', {})
            aliexpress_buzz_raw = ae_signals.get('buzz_score') or product.get('aliexpress_buzz') or 0.0
            aliexpress_rating_raw = ae_signals.get('rating_stars') or product.get('aliexpress_rating')
            aliexpress_found_real = bool(ae_signals.get('found_real_rating', False))

            # Google Trends (from trend_data if available)
            google_data = data_sources.get('google_trends', {})
            google_trend_score = google_data.get('interest') or product.get('google_trend_score') or 0
            trend_direction = google_data.get('direction', product.get('trend_direction', 'stable'))

            # TikTok data
            tiktok_data = data_sources.get('tiktok', {})
            tiktok_views = tiktok_data.get('views', 0)
            tiktok_engagement = tiktok_data.get('engagement', 0)

            # ================================================================
            # DEMAND SCORE (25%) - Based on REAL sales/orders data
            # IMPROVED: More generous thresholds for dropshipping products
            # Task #12: Track whether we have ANY real demand signal so the
            # OI formula can redistribute this component's weight when we
            # don't. Previously every product in a niche without ali_orders
            # or tiktok views got demand=50, flattening the OI ranking.
            # ================================================================
            demand_score = 50  # Neutral baseline (50 = average)
            has_demand_signal = False

            # Orders from AliExpress (IMPROVED - lower thresholds for dropshipping)
            # 500+ orders is actually good for dropshipping (not mainstream retail)
            if ali_orders > 10000:
                demand_score = 98  # Massive demand - proven winner
                has_demand_signal = True
            elif ali_orders > 5000:
                demand_score = 92  # Very high demand
                has_demand_signal = True
            elif ali_orders > 2000:
                demand_score = 86  # Strong demand
                has_demand_signal = True
            elif ali_orders > 1000:
                demand_score = 80  # Good demand
                has_demand_signal = True
            elif ali_orders > 500:
                demand_score = 75  # Solid demand
                has_demand_signal = True
            elif ali_orders > 200:
                demand_score = 70  # Moderate demand (good for testing)
                has_demand_signal = True
            elif ali_orders > 100:
                demand_score = 65  # Some traction
                has_demand_signal = True
            elif ali_orders > 50:
                demand_score = 58  # Early stage
                has_demand_signal = True
            elif ali_orders > 20:
                demand_score = 52  # New product
                has_demand_signal = True
            elif ali_orders > 0:
                demand_score = 48  # Just launched
                has_demand_signal = True

            # Boost from TikTok views (viral potential) - INCREASED
            if tiktok_views > 1000000:
                demand_score = min(100, demand_score + 20)
                has_demand_signal = True
            elif tiktok_views > 500000:
                demand_score = min(100, demand_score + 15)
                has_demand_signal = True
            elif tiktok_views > 100000:
                demand_score = min(100, demand_score + 12)
                has_demand_signal = True
            elif tiktok_views > 50000:
                demand_score = min(100, demand_score + 8)
                has_demand_signal = True
            elif tiktok_views > 10000:
                demand_score = min(100, demand_score + 5)
                has_demand_signal = True

            # Amazon review_count is a strong demand proxy too (purchase
            # behavior, not just conversation). Use it as a fallback demand
            # signal when AliExpress/TikTok are silent.
            if not has_demand_signal and amazon_found_real and amazon_review_count_raw > 0:
                # Log-saturated review-count → demand score
                import math
                rc = float(amazon_review_count_raw)
                # 50 reviews ≈ 55, 500 ≈ 68, 5000 ≈ 80, 50000 ≈ 92
                demand_score = min(95, 50 + 15 * math.log10(1 + rc))
                has_demand_signal = True

            product['demand_score'] = demand_score
            product['has_demand_signal'] = has_demand_signal

            # ================================================================
            # TREND SCORE (25%) - Based on Google Trends + viral indicators
            # IMPROVED: More generous when trends data isn't available
            # Task #12: Track whether we have ANY real trend signal so we can
            # redistribute this component's weight otherwise. Default
            # `trend_direction='stable'` caused every product to get 60
            # regardless of niche.
            # ================================================================
            trend_score = 55  # Neutral baseline (55 = slightly above average)
            has_trend_signal = False

            # Google Trends score (0-100)
            if google_trend_score > 0:
                # Scale Google Trends to be more generous (their 50 = our 65)
                trend_score = min(100, 15 + google_trend_score * 0.85)
                has_trend_signal = True
            else:
                # Estimate from trend direction only if direction was actually
                # reported by a source (i.e. not the default 'stable'/'').
                # The raw product-level direction (product.get('trend_direction'))
                # is the explicit signal; data_sources.google_trends.direction
                # is also explicit. A default of 'stable' in the DS dict means
                # "we didn't hear anything" — don't treat it as a positive.
                direction_raw = google_data.get('direction') or product.get('trend_direction')
                if direction_raw:
                    direction_norm = str(direction_raw).lower()
                    if direction_norm == 'rising':
                        trend_score = 80
                        has_trend_signal = True
                    elif direction_norm == 'stable':
                        trend_score = 60
                        has_trend_signal = True
                    elif direction_norm == 'falling':
                        trend_score = 40
                        has_trend_signal = True

            # Boost from viral indicators (TikTok viral score)
            viral_score = product.get('viral_score', 0)
            if viral_score > 0:
                # Use higher of the two
                trend_score = max(trend_score, 50 + viral_score * 0.5)
                has_trend_signal = True

            # TikTok engagement boost (INCREASED)
            if tiktok_engagement > 0.1:  # 10%+ engagement is excellent
                trend_score = min(100, trend_score + 20)
                has_trend_signal = True
            elif tiktok_engagement > 0.07:
                trend_score = min(100, trend_score + 15)
                has_trend_signal = True
            elif tiktok_engagement > 0.05:
                trend_score = min(100, trend_score + 10)
                has_trend_signal = True
            elif tiktok_engagement > 0.03:
                trend_score = min(100, trend_score + 5)
                has_trend_signal = True

            # Twitter buzz boost (INCREASED)
            if twitter_buzz == 'high':
                trend_score = min(100, trend_score + 15)
                has_trend_signal = True
            elif twitter_buzz == 'medium':
                trend_score = min(100, trend_score + 8)
                has_trend_signal = True

            product['trend_score'] = trend_score
            product['trend_direction'] = trend_direction
            product['has_trend_signal'] = has_trend_signal

            # ================================================================
            # CJ SUPPLIER-QUALITY PROXY SIGNAL (Task #22)
            # CJ's public API doesn't expose reviews or ratings, so for
            # CJ-only products that didn't fuzzy-match to an Amazon listing
            # we have no purchase-behavior signal at all. Build a proxy
            # score from the intrinsic CJ metadata we do have:
            #   - US/EU warehouse presence (faster shipping → higher quality tier)
            #   - Image count (more angles = CJ-featured listing)
            #   - `listed_num` / `recommended_level` / `hot_product_flag` when present
            # The signal is weaker than Amazon reviews, so it only activates
            # when Amazon data is ABSENT for a CJ-sourced product.
            # ================================================================
            cj_proxy_score = None
            product_source = product.get('source') or ''
            is_cj_product = (
                product_source == 'cj_dropshipping'
                or 'cj_dropshipping' in product.get('available_on', [])
                or cj_available
            )
            if is_cj_product:
                cj_proxy = 55  # baseline for being on CJ at all
                cj_has_signal = False

                # Warehouse signal — US/EU warehouse is CJ's premium tier
                if product.get('us_warehouse') or 'US' in str(cj_warehouse).upper():
                    cj_proxy += 15
                    cj_has_signal = True
                if product.get('eu_warehouse') or any(w in str(cj_warehouse).upper() for w in ['DE', 'GB', 'FR', 'EU', 'UK']):
                    cj_proxy += 10
                    cj_has_signal = True

                # Image-richness signal — many product photos = CJ-vetted listing
                image_count = product.get('image_count') or len(product.get('all_images') or [])
                if image_count >= 8:
                    cj_proxy += 10
                    cj_has_signal = True
                elif image_count >= 5:
                    cj_proxy += 6
                    cj_has_signal = True
                elif image_count >= 3:
                    cj_proxy += 3
                    cj_has_signal = True

                # CJ popularity-adjacent fields (when CJ returns them)
                listed_num = product.get('listed_num')
                if isinstance(listed_num, (int, float)) and listed_num > 0:
                    import math
                    cj_proxy += min(10, int(2 * math.log10(1 + listed_num)))
                    cj_has_signal = True

                if product.get('hot_product_flag'):
                    cj_proxy += 8
                    cj_has_signal = True

                recommended_level = product.get('recommended_level')
                if isinstance(recommended_level, (int, float)) and recommended_level > 0:
                    # CJ recommended level is typically 1-5
                    cj_proxy += min(10, int(recommended_level) * 2)
                    cj_has_signal = True

                if cj_has_signal:
                    cj_proxy_score = min(95, cj_proxy)
                    product['cj_proxy_score'] = cj_proxy_score

            # ================================================================
            # SENTIMENT SCORE (15%) - Amazon (primary) + Twitter + Reddit + CJ proxy
            # POST-FIX #15: Honest null state when no real social data.
            # Task #18: Amazon reviews are the PRIMARY signal because aggregate
            # rating × review count reflects actual purchase behavior, not just
            # conversation. Twitter/Reddit stay as secondary signals.
            # Task #22: CJ supplier-quality proxy is a TERTIARY fallback only
            # used when the primary (Amazon) and secondaries (Twitter/Reddit)
            # are all absent — it's weaker evidence (no real buyer voice) so
            # it caps sentiment score at 70.
            # ================================================================
            has_twitter_signal = twitter_found_real and twitter_sentiment_raw is not None
            has_reddit_signal = reddit_mentions > 0
            has_amazon_signal = amazon_found_real and amazon_buzz_raw > 0
            has_cj_proxy_signal = cj_proxy_score is not None
            # Task #19: AE buyer-rating signal. Weaker than Amazon (no review
            # text, no cohort) but stronger than CJ proxy (real buyer voice,
            # not just supplier structural quality). Free — comes from the
            # affiliate response we already paid for to discover the product.
            has_aliexpress_signal = aliexpress_found_real and aliexpress_buzz_raw > 0

            if (
                not has_twitter_signal
                and not has_reddit_signal
                and not has_amazon_signal
                and not has_cj_proxy_signal
                and not has_aliexpress_signal
            ):
                # No real social data at all. Set to None so the OI formula
                # knows to redistribute sentiment's weight to other components.
                sentiment_score = None
                product['sentiment_score'] = None
                product['sentiment_available'] = False
                product['sentiment_source'] = None
            else:
                # Start from a neutral baseline only when we HAVE data.
                sentiment_score = 55
                sentiment_source_tag = None

                # Amazon buzz is the PRIMARY signal when available
                # buzz_score is already 0-100, so use it directly as the floor
                if has_amazon_signal:
                    sentiment_score = max(sentiment_score, int(amazon_buzz_raw))
                    sentiment_source_tag = 'amazon_reviews'

                # Twitter sentiment (-1 to 1 scale -> 0 to 100)
                if has_twitter_signal:
                    # Convert -1 to +1 scale to 0-100, but more generous
                    # -1 = 20, 0 = 55, +1 = 90 (not 0/50/100)
                    twitter_sentiment_score = int(55 + twitter_sentiment_raw * 35)
                    # Take the max so Twitter can raise but not lower Amazon's floor
                    if twitter_sentiment_score > sentiment_score:
                        sentiment_score = twitter_sentiment_score
                        sentiment_source_tag = sentiment_source_tag or 'twitter'

                # Reddit mentions boost (LOWERED thresholds)
                reddit_floor = 0
                if reddit_mentions > 50:
                    reddit_floor = 92
                elif reddit_mentions > 20:
                    reddit_floor = 82
                elif reddit_mentions > 10:
                    reddit_floor = 72
                elif reddit_mentions > 5:
                    reddit_floor = 65
                elif reddit_mentions > 0:
                    reddit_floor = 58
                if reddit_floor > sentiment_score:
                    sentiment_score = reddit_floor
                    sentiment_source_tag = sentiment_source_tag or 'reddit'

                # Task #19: AliExpress buyer-rating tier. Slots between
                # Amazon (primary) and CJ proxy (tertiary):
                #   - contributes only when Amazon is absent (Amazon
                #     dominates because it has verbatim reviews)
                #   - can lift above Twitter/Reddit scores (real buyer
                #     rating > conversation volume)
                #   - capped at 78 (< Amazon ceiling, > CJ proxy cap of 70)
                if has_aliexpress_signal and not has_amazon_signal:
                    capped_ae = min(78, int(aliexpress_buzz_raw))
                    if capped_ae > sentiment_score:
                        sentiment_score = capped_ae
                        sentiment_source_tag = sentiment_source_tag or 'aliexpress_api'

                # Task #22: CJ proxy is the TERTIARY signal. Only contributes
                # when no stronger (Amazon/AE/Twitter/Reddit) signal has
                # lifted the score above the baseline. Capped at 70 because
                # it's structural quality, not real buyer voice.
                if (
                    has_cj_proxy_signal
                    and not has_amazon_signal
                    and not has_aliexpress_signal
                    and not has_twitter_signal
                    and not has_reddit_signal
                ):
                    capped_cj = min(70, cj_proxy_score)
                    if capped_cj > sentiment_score:
                        sentiment_score = capped_cj
                        sentiment_source_tag = 'cj_supplier_proxy'

                product['sentiment_score'] = sentiment_score
                product['sentiment_available'] = True
                product['sentiment_source'] = sentiment_source_tag

            # ================================================================
            # PROFIT SCORE (15%) - Margin analysis
            # IMPROVED: Higher baseline, more generous thresholds
            # ================================================================
            cost = product.get('cost_price', 0)
            suggested = product.get('suggested_price', 0)
            profit_score = 60  # Neutral baseline (unknown margin = assume decent)

            if cost > 0 and suggested > 0:
                margin_pct = ((suggested - cost) / cost) * 100
                if margin_pct >= 200:
                    profit_score = 98  # Exceptional margin
                elif margin_pct >= 150:
                    profit_score = 92  # Excellent margin
                elif margin_pct >= 100:
                    profit_score = 85  # Great margin (2x markup)
                elif margin_pct >= 75:
                    profit_score = 78  # Good margin
                elif margin_pct >= 50:
                    profit_score = 70  # Decent margin
                elif margin_pct >= 30:
                    profit_score = 60  # Acceptable margin
                else:
                    profit_score = 45  # Low margin
                product['profit_margin_pct'] = round(margin_pct, 1)

            # Commission rate bonus (affiliate earnings) - INCREASED
            if ali_commission >= 10:
                profit_score = min(100, profit_score + 12)
            elif ali_commission >= 8:
                profit_score = min(100, profit_score + 10)
            elif ali_commission >= 5:
                profit_score = min(100, profit_score + 6)
            elif ali_commission >= 3:
                profit_score = min(100, profit_score + 3)

            product['profit_score'] = profit_score

            # ================================================================
            # SOURCING SCORE (20%) - Cross-reference and warehouse bonuses
            # IMPROVED: Higher baseline, recognize single-source products
            # ================================================================
            sourcing_score = 50  # Neutral baseline (on at least one supplier)

            # Bonus for being on AliExpress (most common)
            if ali_data.get('available') or ali_orders > 0:
                sourcing_score += 8

            # Bonus for being on both suppliers (cross-referenced) - BIG bonus
            if product.get('cross_referenced'):
                sourcing_score += 20
                logger.debug(f"   +20 cross-reference bonus: {product.get('title', '')[:30]}")

            # Bonus for US/EU warehouse (faster shipping = better customer experience)
            if product.get('us_warehouse') or product.get('eu_warehouse') or 'US' in cj_warehouse or 'EU' in cj_warehouse:
                sourcing_score += 15  # Increased from 18

            # Bonus for having CJ option (generally better for dropshipping)
            if cj_available or 'cj_dropshipping' in product.get('available_on', []):
                sourcing_score += 10

            # Supplier rating bonus (IMPROVED thresholds)
            supplier_rating = product.get('rating', 0) or ali_data.get('rating', 0)
            if supplier_rating >= 4.9:
                sourcing_score += 12
            elif supplier_rating >= 4.7:
                sourcing_score += 10
            elif supplier_rating >= 4.5:
                sourcing_score += 8
            elif supplier_rating >= 4.3:
                sourcing_score += 5
            elif supplier_rating >= 4.0:
                sourcing_score += 3

            product['sourcing_score'] = min(100, sourcing_score)

            # ================================================================
            # BUILD score_breakdown FOR AI ANALYZER COMPATIBILITY
            # POST-FIX #15: twitter_sentiment / reddit_sentiment reflect real data
            # state - None when no real signal, actual score when we have one.
            # ================================================================
            product['score_breakdown'] = {
                'google_trends': trend_score,
                'tiktok_viral': min(100, tiktok_views // 10000) if tiktok_views > 0 else (trend_score if trend_score > 50 else 40),
                'twitter_sentiment': sentiment_score if has_twitter_signal else None,
                'aliexpress_orders': demand_score,
                # Task #18: Real Amazon data (rating × reviews) when we have it
                'amazon_buzz': int(amazon_buzz_raw) if has_amazon_signal else None,
                'amazon_rating': amazon_rating_raw,
                'amazon_reviews': amazon_review_count_raw if has_amazon_signal else None,
                'reddit_sentiment': min(100, 40 + reddit_mentions * 3) if reddit_mentions > 0 else None,
                'supplier_rating': min(100, int(supplier_rating * 20)) if supplier_rating > 0 else 50,
                # Task #22: CJ supplier-quality proxy (fallback for CJ-only products)
                'cj_supplier_proxy': cj_proxy_score,
                # Task #19: AE buyer-rating signal (evaluate_rate-backed)
                'aliexpress_buzz': int(aliexpress_buzz_raw) if has_aliexpress_signal else None,
                'aliexpress_rating': aliexpress_rating_raw if has_aliexpress_signal else None,
            }

            # Track which sources provided real data
            sources_validated = []
            if ali_orders > 0 or ali_data.get('available'):
                sources_validated.append('aliexpress')
            if cj_available:
                sources_validated.append('cj_dropshipping')
            # Twitter only counts as validated when we actually got real tweet evidence.
            # Prior buggy logic: `twitter_sentiment_raw != 0` was True for None, which
            # falsely inflated confidence scores for products with zero social data.
            if twitter_found_real:
                sources_validated.append('twitter')
            if reddit_mentions > 0 or reddit_data.get('available'):
                sources_validated.append('reddit')
            # Task #18: Amazon counts as validated only when fuzzy-match found listings
            if amazon_found_real and amazon_review_count_raw > 0:
                sources_validated.append('amazon_reviews')
            # Task #19: AE buyer-rating counts as validated when we actually
            # got a non-empty evaluate_rate from the affiliate response.
            if has_aliexpress_signal:
                sources_validated.append('aliexpress_ratings')
            # Task #22: CJ supplier-quality proxy — counts as a (weaker) validated
            # source only when it's actually acting as the sentiment driver.
            if has_cj_proxy_signal and product.get('sentiment_source') == 'cj_supplier_proxy':
                sources_validated.append('cj_supplier_proxy')
            if google_trend_score > 0 or google_data.get('available'):
                sources_validated.append('google_trends')
            if tiktok_views > 0 or tiktok_data.get('available'):
                sources_validated.append('tiktok')

            product['sources_validated'] = sources_validated

            # ================================================================
            # DATA COVERAGE AUDIT (Task #4) - honest reporting of real data
            # vs. gaps. For each source we care about, classify as:
            #   "real"    = source returned actual usable data for this product
            #   "empty"   = source was queried / applicable but returned nothing
            #               (e.g. Amazon enrichment ran but fuzzy match found 0)
            #   "n/a"     = source not configured or not applicable
            # This lets the UI + internal audits distinguish "we looked and
            # found nothing" from "we never looked" — which is the whole
            # point of the task.
            # ================================================================
            coverage: Dict[str, str] = {}

            # AliExpress — the product either has aliexpress data or it came
            # from a different source entirely.
            if ali_data.get('available') or ali_orders > 0 or product.get('source') == 'aliexpress':
                coverage['aliexpress'] = 'real' if (ali_data.get('available') or ali_orders > 0) else 'empty'
            else:
                coverage['aliexpress'] = 'n/a'

            # CJ Dropshipping
            if cj_data:
                coverage['cj_dropshipping'] = 'real' if cj_available else 'empty'
            else:
                coverage['cj_dropshipping'] = 'n/a'

            # Twitter — enrichment sets found_real_tweets explicitly
            if 'x_twitter' in data_sources:
                coverage['twitter'] = 'real' if twitter_found_real else 'empty'
            else:
                coverage['twitter'] = 'n/a'

            # Reddit — evidence trail persisted as reddit_evidence
            reddit_evidence = product.get('reddit_evidence')
            if 'reddit' in data_sources or reddit_evidence is not None:
                coverage['reddit'] = 'real' if reddit_mentions > 0 else 'empty'
            else:
                coverage['reddit'] = 'n/a'

            # Amazon reviews (Task #18) — distinguish outside-cap / empty-pool / matched
            amazon_evidence = product.get('amazon_evidence') or {}
            amazon_state = amazon_evidence.get('state') if isinstance(amazon_evidence, dict) else None
            if 'amazon_reviews' in data_sources or amazon_state:
                if amazon_found_real and amazon_review_count_raw > 0:
                    coverage['amazon_reviews'] = 'real'
                else:
                    coverage['amazon_reviews'] = 'empty'
            else:
                coverage['amazon_reviews'] = 'n/a'

            # Google Trends
            if 'google_trends' in data_sources:
                coverage['google_trends'] = 'real' if google_trend_score > 0 or google_data.get('available') else 'empty'
            else:
                coverage['google_trends'] = 'n/a'

            # TikTok
            if 'tiktok' in data_sources:
                coverage['tiktok'] = 'real' if tiktok_views > 0 or tiktok_data.get('available') else 'empty'
            else:
                coverage['tiktok'] = 'n/a'

            # Task #22: CJ supplier-quality proxy — only counts as a coverage
            # entry for products that came from CJ (not applicable for
            # AliExpress-only products).
            if is_cj_product:
                coverage['cj_supplier_proxy'] = 'real' if has_cj_proxy_signal else 'empty'
            else:
                coverage['cj_supplier_proxy'] = 'n/a'

            # Summarize
            total_sources = len(coverage)
            real_count = sum(1 for v in coverage.values() if v == 'real')
            empty_count = sum(1 for v in coverage.values() if v == 'empty')
            na_count = sum(1 for v in coverage.values() if v == 'n/a')
            # Coverage = real / (real+empty) — excludes n/a from denominator
            # so coverage reflects "of the sources we actually queried, how
            # many gave us real data"
            queried = real_count + empty_count
            coverage_pct = round(100.0 * real_count / queried, 1) if queried > 0 else 0.0

            product['data_coverage'] = {
                'by_source': coverage,
                'real_sources': real_count,
                'empty_sources': empty_count,
                'na_sources': na_count,
                'queried': queried,
                'coverage_pct': coverage_pct,
                # Confidence tier — maps to UI badge (high/medium/low/bare)
                'confidence': (
                    'high'   if real_count >= 3 else
                    'medium' if real_count == 2 else
                    'low'    if real_count == 1 else
                    'bare'
                ),
            }

            # ================================================================
            # FINAL OI SCORE CALCULATION (with relevance adjustment)
            # Task #12 + POST-FIX #15: When a component has no real signal,
            # redistribute its weight across components that DO have real
            # data. Previously only sentiment-null was redistributed, so
            # demand=50 and trend=55 baselines flattened products in niches
            # where AliExpress orders and Google Trends were missing.
            #
            # Profit is always computed (at minimum from a neutral baseline
            # but it uses actual price data when present), and sourcing
            # always varies by intrinsic product attributes, so those two
            # components carry weight unconditionally.
            # ================================================================
            base_weights = {
                'demand':    (0.25, demand_score if has_demand_signal else None),
                'trend':     (0.25, trend_score if has_trend_signal else None),
                'sentiment': (0.15, sentiment_score),  # already None when absent
                'profit':    (0.15, profit_score),
                'sourcing':  (0.20, product['sourcing_score']),
            }
            active = {k: (w, v) for k, (w, v) in base_weights.items() if v is not None}
            total_active_weight = sum(w for w, _ in active.values())
            if total_active_weight <= 0:
                # Extreme edge case: nothing scorable. Fall back to neutral.
                base_score = 50.0
            else:
                base_score = sum((w / total_active_weight) * v for w, v in active.values())

            redistributed = [k for k in base_weights if k not in active]
            product['sentiment_weight_redistributed'] = 'sentiment' in redistributed
            product['weights_redistributed'] = redistributed
            product['active_components'] = list(active.keys())

            # Apply relevance multiplier (IMPROVED - less harsh)
            # Relevance 100 = 1.0x (no change)
            # Relevance 70 = 0.95x (5% penalty)
            # Relevance 50 = 0.90x (10% penalty)
            # Relevance 30 = 0.80x (20% penalty)
            # Relevance 0 = 0.70x (30% penalty, down from 50%)
            relevance = product.get('relevance_score', 70)  # Default to 70 (assume relevant)
            relevance_multiplier = 0.70 + (relevance / 100) * 0.30  # Range: 0.70 to 1.0

            oi_score = base_score * relevance_multiplier

            # If product is clearly irrelevant, cap score at 45 (POOR tier)
            if relevance < 25:
                oi_score = min(oi_score, 45)
                product['relevance_note'] = f'⚠️ Off-topic: Low relevance ({relevance}%) to niche'

            product['oi_score'] = round(oi_score, 1)  # Keep 1 decimal for differentiation
            product['final_score'] = product['oi_score']
            product['base_score'] = round(base_score, 1)  # Store pre-relevance score for debugging

            # Calculate confidence based on data availability
            max_sources = 6  # aliexpress, cj, twitter, reddit, google_trends, tiktok
            product['confidence'] = round((len(sources_validated) / max_sources) * 100, 0)

            # ================================================================
            # TIER CLASSIFICATION (with more granular thresholds)
            # ================================================================
            if oi_score >= 85:
                product['tier'] = 'GOLDEN'
                product['recommendation'] = '🔥 RARE GEM - Deploy immediately, high demand + low competition window'
            elif oi_score >= 75:
                product['tier'] = 'EXCELLENT'
                product['recommendation'] = '✅ Strong buy - trending with great sourcing options'
            elif oi_score >= 65:
                product['tier'] = 'GOOD'
                product['recommendation'] = '👍 Worth testing - solid opportunity with good margins'
            elif oi_score >= 55:
                product['tier'] = 'FAIR'
                product['recommendation'] = '⚠️ Proceed with caution - monitor trends before committing'
            elif oi_score >= 45:
                product['tier'] = 'POOR'
                product['recommendation'] = '❌ Skip - weak signals or high competition'
            else:
                product['tier'] = 'AVOID'
                product['recommendation'] = '🚫 Avoid - insufficient data or poor opportunity'

            logger.debug(f"   Scored: {product.get('title', '')[:30]}... -> {oi_score} ({product['tier']})")

        return products

    def _calculate_relevance(self, title: str, niche: str) -> float:
        """
        Calculate relevance score (0-100) for a product to its niche.

        Uses keyword matching to determine if a product is on-topic.
        Products that match 'exclude' keywords are penalized.
        Products that match 'include' keywords are rewarded.

        Returns:
            0-100 relevance score
        """
        if not title or not niche:
            return 50  # Neutral if we can't determine

        title_lower = title.lower()
        niche_lower = niche.lower().replace('_', ' ')

        # Get relevance keywords for this niche
        relevance_config = self.RELEVANCE_KEYWORDS.get(niche_lower.replace(' ', '_'), {})
        include_keywords = relevance_config.get('include', [])
        exclude_keywords = relevance_config.get('exclude', [])

        # If no config for this niche, use generic matching
        if not include_keywords:
            # Check if niche words appear in title
            niche_words = set(niche_lower.split())
            title_words = set(title_lower.split())
            overlap = niche_words & title_words
            if overlap:
                return 70
            return 50  # Neutral - can't determine

        # Count include matches
        include_matches = sum(1 for kw in include_keywords if kw in title_lower)

        # Count exclude matches (these are penalties)
        exclude_matches = sum(1 for kw in exclude_keywords if kw in title_lower)

        # Calculate score
        # Base score of 30, +10 for each include match, -20 for each exclude match
        score = 30 + (include_matches * 15) - (exclude_matches * 25)

        # Clamp to 0-100
        return max(0, min(100, score))

    # =========================================================================
    # DEMO DATA FOR DEVELOPMENT
    # =========================================================================

    def _get_demo_products(self, niche: str, count: int) -> List[Dict]:
        """
        Return demo products for development/testing when APIs fail.

        These are realistic sample products to help test the dashboard.
        """
        import random

        DEMO_PRODUCTS = {
            "smart_home": [
                {"title": "Smart LED Strip Lights RGB WiFi", "cost_price": 8.50, "image_url": "https://ae01.alicdn.com/kf/S1234567890.jpg"},
                {"title": "WiFi Smart Plug with Energy Monitoring", "cost_price": 6.99, "image_url": "https://ae01.alicdn.com/kf/S1234567891.jpg"},
                {"title": "Smart Motion Sensor PIR Detector", "cost_price": 5.50, "image_url": "https://ae01.alicdn.com/kf/S1234567892.jpg"},
                {"title": "WiFi Smart Bulb RGBW Dimmable", "cost_price": 4.99, "image_url": "https://ae01.alicdn.com/kf/S1234567893.jpg"},
                {"title": "Smart Door Lock Fingerprint Digital", "cost_price": 45.00, "image_url": "https://ae01.alicdn.com/kf/S1234567894.jpg"},
            ],
            "kitchen": [
                {"title": "Electric Milk Frother Handheld", "cost_price": 5.99, "image_url": "https://ae01.alicdn.com/kf/K1234567890.jpg"},
                {"title": "Silicone Kitchen Utensil Set 12pcs", "cost_price": 12.50, "image_url": "https://ae01.alicdn.com/kf/K1234567891.jpg"},
                {"title": "Vegetable Chopper Dicer Slicer", "cost_price": 8.99, "image_url": "https://ae01.alicdn.com/kf/K1234567892.jpg"},
                {"title": "Digital Kitchen Scale 5kg", "cost_price": 7.50, "image_url": "https://ae01.alicdn.com/kf/K1234567893.jpg"},
                {"title": "Vacuum Food Storage Containers", "cost_price": 15.00, "image_url": "https://ae01.alicdn.com/kf/K1234567894.jpg"},
            ],
            "fitness": [
                {"title": "Resistance Bands Set 5 Levels", "cost_price": 6.50, "image_url": "https://ae01.alicdn.com/kf/F1234567890.jpg"},
                {"title": "Foam Roller for Muscle Massage", "cost_price": 9.99, "image_url": "https://ae01.alicdn.com/kf/F1234567891.jpg"},
                {"title": "Jump Rope Speed Skipping Rope", "cost_price": 4.50, "image_url": "https://ae01.alicdn.com/kf/F1234567892.jpg"},
                {"title": "Yoga Mat Non-Slip 6mm Thick", "cost_price": 11.00, "image_url": "https://ae01.alicdn.com/kf/F1234567893.jpg"},
                {"title": "Adjustable Dumbbells Set 20kg", "cost_price": 35.00, "image_url": "https://ae01.alicdn.com/kf/F1234567894.jpg"},
            ],
            "tech": [
                {"title": "Wireless Earbuds Bluetooth 5.0", "cost_price": 12.50, "image_url": "https://ae01.alicdn.com/kf/T1234567890.jpg"},
                {"title": "USB C Hub 7-in-1 Adapter", "cost_price": 15.00, "image_url": "https://ae01.alicdn.com/kf/T1234567891.jpg"},
                {"title": "Portable Phone Stand Adjustable", "cost_price": 3.99, "image_url": "https://ae01.alicdn.com/kf/T1234567892.jpg"},
                {"title": "Wireless Charging Pad 15W Fast", "cost_price": 8.50, "image_url": "https://ae01.alicdn.com/kf/T1234567893.jpg"},
                {"title": "Mini Portable Projector 1080P", "cost_price": 55.00, "image_url": "https://ae01.alicdn.com/kf/T1234567894.jpg"},
            ],
            "beauty": [
                {"title": "LED Face Mask Light Therapy", "cost_price": 25.00, "image_url": "https://ae01.alicdn.com/kf/B1234567890.jpg"},
                {"title": "Electric Facial Cleansing Brush", "cost_price": 12.00, "image_url": "https://ae01.alicdn.com/kf/B1234567891.jpg"},
                {"title": "Jade Roller Face Massager", "cost_price": 4.50, "image_url": "https://ae01.alicdn.com/kf/B1234567892.jpg"},
                {"title": "Hair Straightener Brush Ionic", "cost_price": 18.00, "image_url": "https://ae01.alicdn.com/kf/B1234567893.jpg"},
                {"title": "Makeup Brush Set 15pcs Professional", "cost_price": 9.99, "image_url": "https://ae01.alicdn.com/kf/B1234567894.jpg"},
            ],
            "pet": [
                {"title": "Automatic Pet Water Fountain", "cost_price": 15.00, "image_url": "https://ae01.alicdn.com/kf/P1234567890.jpg"},
                {"title": "Interactive Cat Toy Laser Pointer", "cost_price": 6.50, "image_url": "https://ae01.alicdn.com/kf/P1234567891.jpg"},
                {"title": "Self-Cleaning Dog Brush Slicker", "cost_price": 8.99, "image_url": "https://ae01.alicdn.com/kf/P1234567892.jpg"},
                {"title": "Pet GPS Tracker Collar", "cost_price": 22.00, "image_url": "https://ae01.alicdn.com/kf/P1234567893.jpg"},
                {"title": "Automatic Pet Feeder Smart WiFi", "cost_price": 35.00, "image_url": "https://ae01.alicdn.com/kf/P1234567894.jpg"},
            ],
        }

        # Get products for niche or default to smart_home
        niche_products = DEMO_PRODUCTS.get(niche, DEMO_PRODUCTS.get("smart_home", []))

        # Build full product objects
        demo_list = []
        for i, base in enumerate(niche_products[:count]):
            cost = base["cost_price"]
            suggested = round(cost * 2.5, 2)
            profit = round(suggested - cost, 2)

            product = {
                "product_id": f"demo_{niche}_{i}_{int(datetime.now().timestamp())}",
                "title": base["title"],
                "title_normalized": self._normalize_title(base["title"]),
                "cost_price": cost,
                "supplier_cost": cost,
                "suggested_price": suggested,
                "profit": profit,
                "image_url": base["image_url"],
                "all_images": [base["image_url"]],
                "image_count": 1,
                "source": "demo",
                "available_on": ["demo_supplier"],
                "is_mock": True,
                "niche": niche,
                "sales_count": random.randint(100, 2000),
                "trend_score": random.randint(50, 85),
                "oi_score": random.randint(55, 85),
                "final_score": random.randint(55, 85),
                "tier": random.choice(["GOOD", "EXCELLENT"]),
                "recommendation": "Demo product for testing - connect APIs for real data",
                "data_sources": {
                    "demo": {"available": True, "note": "Demo data - APIs not connected"}
                },
                "_discovery_metadata": {
                    "sources_queried": ["demo"],
                    "discovered_at": datetime.now().isoformat(),
                    "niche": niche,
                    "flow": "demo_fallback",
                    "note": "Demo products - connect CJ/AliExpress APIs for real discovery"
                },
                "discovered_at": datetime.now().isoformat()
            }
            demo_list.append(product)

        logger.info(f"[DEMO] Returning {len(demo_list)} demo products for {niche}")
        return demo_list


# =============================================================================
# PRICE FRESHNESS UTILITIES
# =============================================================================

def check_price_freshness(product: Dict, max_age_hours: float = 2.0) -> Dict:
    """
    Check if a product's price data is fresh or stale.

    Args:
        product: Product dict with price_fetched_at field
        max_age_hours: Maximum age in hours before price is considered stale

    Returns:
        Dict with:
        - is_fresh: bool
        - age_hours: float
        - needs_refresh: bool
        - message: str
    """
    price_fetched_at = product.get('price_fetched_at')
    if not price_fetched_at:
        return {
            "is_fresh": False,
            "age_hours": None,
            "needs_refresh": True,
            "message": "Price timestamp not available"
        }

    try:
        fetched_time = datetime.fromisoformat(price_fetched_at.replace('Z', '+00:00'))
        age = datetime.now() - fetched_time.replace(tzinfo=None)
        age_hours = age.total_seconds() / 3600

        is_fresh = age_hours <= max_age_hours

        return {
            "is_fresh": is_fresh,
            "age_hours": round(age_hours, 1),
            "needs_refresh": not is_fresh,
            "message": f"Price is {round(age_hours, 1)}h old" + ("" if is_fresh else " - may need refresh")
        }
    except Exception as e:
        logger.warning(f"Error checking price freshness: {e}")
        return {
            "is_fresh": False,
            "age_hours": None,
            "needs_refresh": True,
            "message": "Error checking price age"
        }


def add_price_freshness_to_products(products: list, max_age_hours: float = 2.0) -> list:
    """
    Add price freshness indicators to a list of products.

    Args:
        products: List of product dicts
        max_age_hours: Maximum age before price is stale

    Returns:
        Products with 'price_freshness' field added
    """
    for product in products:
        product['price_freshness'] = check_price_freshness(product, max_age_hours)
    return products


# =============================================================================
# SINGLETON & COMPATIBILITY
# =============================================================================

_engine_instance = None

def get_engine() -> ProductDiscoveryEngine:
    """Get singleton instance"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProductDiscoveryEngine()
    return _engine_instance


async def discover_products(niche: str = "smart_home", count: int = 20, limit: int = None) -> List[Dict]:
    """Convenience function - accepts both 'count' and 'limit' for backward compatibility"""
    engine = get_engine()
    max_products = limit if limit is not None else count
    return await engine.discover_products(niche=niche, max_products=max_products)


# Backward compatibility
UnifiedProductDiscoveryV3 = ProductDiscoveryEngine
UnifiedProductDiscovery = ProductDiscoveryEngine
OspraIntelligenceEngine = ProductDiscoveryEngine
ProductIntelligenceEngine = ProductDiscoveryEngine
