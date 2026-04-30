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
import time
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


# ─────────────────────────────────────────────────────────────────────────────
# TITLE CLEANING — convert AliExpress keyword salad into readable product names
# ─────────────────────────────────────────────────────────────────────────────
# AE titles average 120+ chars and look like:
#   "Silicone Suction Phone Holder Mat Multifunctional Suction Cup Wall Stand
#    Square Anti-Slip Single-Sided Case Mount Back Sticker"
#
# These are SEO keyword stuffing for AE's internal search, not human-readable
# product names. The cleaner extracts the head noun phrase and drops trailing
# descriptors, capping at ~60 chars. We persist BOTH the original title (for
# downstream agents that need full keyword context) and `clean_title` (for UI).

import re as _re

# Generic descriptors that show up at the END of AE titles after the real name.
# Dropping these from the trailing portion produces shorter, cleaner labels.
_TITLE_TRAILING_NOISE = {
    'multifunctional', 'multi-functional', 'multi', 'functional',
    'portable', 'durable', 'premium', 'professional',
    'high-quality', 'quality', 'reusable', 'eco-friendly',
    'waterproof', 'wireless', 'mini', 'large', 'small', 'medium',
    'new', 'hot', 'fashion', 'trendy', 'creative',
    'anti-slip', 'antislip', 'non-slip', 'nonslip',
    'single-sided', 'double-sided',
    'with', 'and', 'for', 'the', 'a', 'an', 'or', 'of',
    'square', 'round', 'oval', 'rectangular',
    'home', 'kitchen', 'office', 'outdoor', 'indoor', 'travel',
    'usb', 'plastic', 'silicone', 'metal', 'wooden',
    'black', 'white', 'red', 'blue', 'green', 'yellow', 'pink', 'gray', 'grey',
    'set', 'pack', 'pcs', 'piece', 'pieces', 'kit',
}

# Brand prefixes are real signal — keep them.
_TITLE_KEEP_PREFIX = {
    'apple', 'samsung', 'xiaomi', 'huawei', 'sony', 'lg', 'nintendo',
    'baseus', 'ugreen', 'anker', 'essager', 'rocoren',
}


def _clean_product_title(raw: str, max_chars: int = 60) -> str:
    """Strip AE keyword stuffing and produce a human-readable label.

    Strategy:
      1. Strip leading/trailing whitespace + collapse internal whitespace
      2. Take the first 8 tokens (the head noun phrase usually lives here)
      3. Trim trailing generic descriptors that don't add product identity
      4. Cap at max_chars on a word boundary
      5. Title-case the result for consistency

    This is deterministic and free — no AI call. Good enough for 95% of AE
    titles. The ones it can't help (e.g., titles that lead with brand model
    numbers like "5 in 1 USB C HUB") fall back to a length-only truncation.
    """
    if not raw or not isinstance(raw, str):
        return ''
    # Collapse whitespace and strip
    cleaned = _re.sub(r'\s+', ' ', raw).strip()
    if not cleaned:
        return ''
    # Remove all-caps SKU-like noise: "USB-C 4K HDMI" stays, but
    # standalone codes like "VR-2034" or "M11" get pruned only if they
    # appear after position 4 (head-position SKU is real signal).
    tokens = cleaned.split(' ')
    if len(tokens) <= 8:
        head = tokens
    else:
        head = tokens[:8]
    # Drop trailing noise tokens but never below 3 tokens (avoid "Phone")
    while len(head) > 3 and head[-1].lower().strip(',.;:') in _TITLE_TRAILING_NOISE:
        head.pop()
    label = ' '.join(head)
    # Cap at max_chars on a word boundary
    if len(label) > max_chars:
        truncated = label[:max_chars].rsplit(' ', 1)[0]
        if truncated and len(truncated) >= 20:
            label = truncated
        else:
            label = label[:max_chars]
    # Title-case unless the token is an all-caps acronym (USB, HDMI, 4K, etc.)
    out_tokens = []
    for tok in label.split(' '):
        if not tok:
            continue
        if tok.isupper() and len(tok) <= 5:
            out_tokens.append(tok)  # Preserve acronyms
        elif _re.match(r'^[A-Z]\w*[A-Z]\w*', tok):
            out_tokens.append(tok)  # Preserve mixed-case brand-y tokens
        else:
            out_tokens.append(tok.capitalize())
    return ' '.join(out_tokens).strip(',.;: ')


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY-AWARE PRICING — replaces hardcoded cost × 2.5 markup
# ─────────────────────────────────────────────────────────────────────────────
# AliExpress returns affiliate cost. We need a suggested retail price. The
# old logic was `cost * 2.5` for everything, which produces:
#   - $4 cost → $10 retail (60% margin) — fine for accessories
#   - $40 cost → $100 retail (60% margin) — too expensive vs comp
#   - $100 cost → $250 retail (60% margin) — uncompetitive
#
# Real dropshipping markup curves are reverse-elastic — cheaper items
# tolerate larger multipliers, expensive items need tighter margins to
# stay competitive. The brackets below match common competitor pricing.

def _suggested_price_for_cost(cost_price: float) -> float:
    """Return a category-aware suggested retail price.

    Brackets:
      < $3       → 4.0× (impulse buys, room for margin)
      $3 - $10   → 3.0×
      $10 - $25  → 2.5× (the old default — still right for this band)
      $25 - $75  → 2.0×
      >= $75     → 1.7× (high-ticket, price-sensitive)

    Returns rounded-to-2dp. Returns 0.0 if cost is invalid.
    """
    try:
        c = float(cost_price)
    except (TypeError, ValueError):
        return 0.0
    if c <= 0:
        return 0.0
    if c < 3.0:
        mult = 4.0
    elif c < 10.0:
        mult = 3.0
    elif c < 25.0:
        mult = 2.5
    elif c < 75.0:
        mult = 2.0
    else:
        mult = 1.7
    return round(c * mult, 2)


# ─────────────────────────────────────────────────────────────────────────────
# FUZZY TITLE DEDUPLICATION
# ─────────────────────────────────────────────────────────────────────────────
# AE returns multiple SKUs for the same product (different colors, sizes,
# sellers) with different product_ids but near-identical titles. The current
# dedup is product_id only, so the same item appears 3-5 times in results.
# Fuzzy title dedup drops near-duplicates AFTER scoring (so we keep the
# higher-OI variant of each cluster).

def _dedupe_by_title(products: List[Dict], threshold: float = 0.7) -> List[Dict]:
    """Drop near-duplicate products by title token overlap.

    For each pair, compute the Jaccard-ish ratio of shared 4+-char tokens
    over the smaller token set. If ratio > threshold, drop the lower-scored
    product. Linear in product count after sorting (we only compare each
    product to those we've kept so far, so it's O(n × kept) ≈ O(n²) worst
    case; with ~100 products this is fine).

    Operates on `clean_title` if present, falling back to `title`.
    """
    if not products:
        return products

    def _tokens(p: Dict) -> set:
        title = (p.get('clean_title') or p.get('title') or '').lower()
        return {t.strip(',.;:') for t in title.split() if len(t.strip(',.;:')) > 3}

    # Sort by oi_score desc so kept[] holds winners; drops are losers.
    ordered = sorted(products, key=lambda p: p.get('oi_score', 0) or 0, reverse=True)
    kept: List[Dict] = []
    kept_token_sets: List[set] = []
    dropped = 0

    for p in ordered:
        toks = _tokens(p)
        if not toks:
            kept.append(p)
            kept_token_sets.append(toks)
            continue
        is_dup = False
        for prior_toks in kept_token_sets:
            if not prior_toks:
                continue
            overlap = len(toks & prior_toks)
            min_len = min(len(toks), len(prior_toks))
            if min_len > 0 and (overlap / min_len) > threshold:
                is_dup = True
                break
        if is_dup:
            dropped += 1
        else:
            kept.append(p)
            kept_token_sets.append(toks)

    if dropped:
        logger.info(f"   🔁 Title dedup: kept {len(kept)} / dropped {dropped} near-duplicates")
    return kept


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
        
        # Pinterest scraper — initialized in the same Apify block but as an
        # optional dependency (older deploys may not have the connector
        # installed). Pinterest Trends gives us visual-niche momentum
        # (kitchen, beauty, home decor) that Google/TikTok miss.
        self.pinterest_scraper = None

        # TikTok Shop Partner API connector — first-party data
        # (real units_sold_7d, real view counts). Requires per-seller
        # OAuth, so it's best-effort: if TIKTOK_SHOP_APP_KEY +
        # TIKTOK_SHOP_ACCESS_TOKEN are configured, we wire it as a
        # parallel trend source. Otherwise we silently skip — most users
        # won't have this configured and that's fine.
        self.tiktok_shop_connector = None
        if os.getenv("TIKTOK_SHOP_APP_KEY") and os.getenv("TIKTOK_SHOP_ACCESS_TOKEN"):
            try:
                from ospra_os.product_research.connectors.tiktok_shop import (
                    TikTokShopConnector,
                )
                self.tiktok_shop_connector = TikTokShopConnector()
                self.sources_status['tiktok_shop'] = '[SUCCESS] Connected (Partner API)'
                logger.info("[SUCCESS] TikTok Shop Partner API connected")
            except Exception as exc:
                self.sources_status['tiktok_shop'] = f'[ERROR] {exc}'
                logger.warning(f"[WARNING] TikTok Shop Partner init failed: {exc}")
        else:
            self.sources_status['tiktok_shop'] = '[INFO] Not configured (set TIKTOK_SHOP_APP_KEY/_ACCESS_TOKEN)'

        if self.apify_token:
            try:
                from ospra_os.product_research.connectors.apify import TikTokShopScraper, AmazonBestsellersScraper
                self.tiktok_scraper = TikTokShopScraper()
                self.amazon_scraper = AmazonBestsellersScraper()
                self.apify_available = True
                self.sources_status['tiktok'] = '[SUCCESS] Connected (Apify)'
                self.sources_status['amazon'] = '[SUCCESS] Connected (Apify)'
                logger.info("[SUCCESS] TikTok + Amazon scrapers loaded")

                # Pinterest is best-effort. Older codebases or deploys
                # that don't have the actor configured will hit ImportError
                # — that's fine, we just log + skip.
                try:
                    from ospra_os.product_research.connectors.apify.pinterest_trends import (
                        PinterestTrendsApify,
                    )
                    self.pinterest_scraper = PinterestTrendsApify(api_token=self.apify_token)
                    self.sources_status['pinterest'] = '[SUCCESS] Connected (Apify)'
                    logger.info("[SUCCESS] Pinterest Trends scraper loaded")
                except ImportError as exc:
                    self.sources_status['pinterest'] = f'[INFO] Connector not installed: {exc}'
                    logger.info(f"[INFO] Pinterest Trends: connector not available ({exc})")
                except Exception as exc:
                    self.sources_status['pinterest'] = f'[ERROR] {exc}'
                    logger.warning(f"[WARNING] Pinterest Trends init failed: {exc}")

            except Exception as e:
                self.sources_status['tiktok'] = f'[ERROR] {e}'
                self.sources_status['amazon'] = f'[ERROR] {e}'
        else:
            self.sources_status['tiktok'] = '[ERROR] No APIFY_API_TOKEN'
            self.sources_status['amazon'] = '[ERROR] No APIFY_API_TOKEN'
            self.sources_status['pinterest'] = '[ERROR] No APIFY_API_TOKEN'
    
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

        # Phase H — AliExpress reviews (per-product review TEXT via Apify).
        # Only invoked for top-N AliExpress products by OI in step 4b to
        # control cost. Best-effort: silently disabled if Apify isn't
        # configured.
        self.aliexpress_reviews = None
        self.aliexpress_reviews_available = False
        if self.apify_token:
            try:
                from ospra_os.product_research.connectors.apify.aliexpress_reviews import (
                    AliExpressReviewsApify,
                )
                self.aliexpress_reviews = AliExpressReviewsApify(api_token=self.apify_token)
                self.aliexpress_reviews_available = self.aliexpress_reviews.is_available()
                if self.aliexpress_reviews_available:
                    self.sources_status['aliexpress_reviews'] = '[SUCCESS] Connected (Apify)'
                    logger.info("[SUCCESS] AliExpress reviews connector loaded")
                else:
                    self.sources_status['aliexpress_reviews'] = '[ERROR] Init failed'
            except Exception as e:
                self.sources_status['aliexpress_reviews'] = f'[ERROR] {e}'
        else:
            self.sources_status['aliexpress_reviews'] = '[ERROR] No APIFY_API_TOKEN'

        # Phase I — YouTube Data API v3 (review videos + verbatim viewer
        # comments). Free 10k quota units/day; ~107 units per product, so
        # capped at top 10 ranked products in step 5c. The qualitative
        # agent reads ``top_comments`` as actual viewer feedback prose.
        self.youtube_reviews = None
        self.youtube_reviews_available = False
        youtube_key = os.getenv('YOUTUBE_API_KEY')
        if youtube_key:
            try:
                from ospra_os.product_research.connectors.social.youtube import (
                    YouTubeReviewsConnector,
                )
                self.youtube_reviews = YouTubeReviewsConnector(api_key=youtube_key)
                self.youtube_reviews_available = self.youtube_reviews.is_available()
                if self.youtube_reviews_available:
                    self.sources_status['youtube'] = '[SUCCESS] Connected (Data API v3)'
                    logger.info("[SUCCESS] YouTube reviews connector loaded")
                else:
                    self.sources_status['youtube'] = '[ERROR] Init failed'
            except Exception as e:
                self.sources_status['youtube'] = f'[ERROR] {e}'
        else:
            self.sources_status['youtube'] = '[ERROR] No YOUTUBE_API_KEY'

        # Phase K — Amazon per-product review TEXT (verbatim buyer
        # prose) via a dedicated Apify actor. The niche-level
        # ``amazon_reviews`` connector gives aggregate rating only;
        # this fills the qualitative gap on the top-N ranked products.
        self.amazon_reviews_text = None
        self.amazon_reviews_text_available = False
        if self.apify_token:
            try:
                from ospra_os.product_research.connectors.apify.amazon_reviews_text import (
                    AmazonReviewsTextApify,
                )
                self.amazon_reviews_text = AmazonReviewsTextApify(api_token=self.apify_token)
                self.amazon_reviews_text_available = self.amazon_reviews_text.is_available()
                if self.amazon_reviews_text_available:
                    self.sources_status['amazon_reviews_text'] = '[SUCCESS] Connected (Apify)'
                    logger.info("[SUCCESS] Amazon review-text connector loaded")
                else:
                    self.sources_status['amazon_reviews_text'] = '[ERROR] Init failed'
            except Exception as e:
                self.sources_status['amazon_reviews_text'] = f'[ERROR] {e}'
        else:
            self.sources_status['amazon_reviews_text'] = '[ERROR] No APIFY_API_TOKEN'

        # Phase J (Instagram via Apify) was disabled per cost-cut decision —
        # IG captions are the noisiest verbatim source we tried, and the
        # signal didn't justify ~$50-70/mo. Connector file is kept on disk at
        # ``connectors/apify/instagram_hashtag.py`` (with its tests) in case
        # we want to revisit it; it just isn't wired into discovery.
        self.instagram_hashtag = None
        self.instagram_hashtag_available = False
    
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
        for source in ['x_twitter', 'reddit', 'amazon_reviews', 'amazon_reviews_text', 'aliexpress_reviews', 'youtube']:
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

        # ── Tier-aware supplier budget ────────────────────────────────────
        # Was: hardcoded 3 keywords × 10 AliExpress + 15 CJ = 45 raw → ~23
        # final after dedup/URL-validation/score attrition. Both NEST
        # (max_products=10) and Stratosphere (max_products=300) hit the
        # same 23-product wall — Stratosphere users were paying for nothing.
        #
        # Now: scale the fetch budget with max_products. Targeting raw ≈
        # 2 × max_products so post-attrition (~50%) we can fill the request.
        #
        # Caps:
        #   - AliExpress affiliate page_size hard cap is 50 (we use 40 to
        #     leave headroom for the rare oversized response).
        #   - 8 keywords is our trending-keyword pool ceiling — adding more
        #     means trending_keywords padding kicks in (less relevant).
        #   - CJ /list2 page_size accepts up to 200 but each call is one
        #     request against their 1 req/sec rate limit; capping at 60
        #     keeps us comfortably inside SUPPLIER_SOURCE_TIMEOUT.
        ali_keywords = max(3, min(8, max_products // 25))   # 3 → 8 keywords
        ali_per_kw   = max(10, min(40, max_products // 10)) # 10 → 40 per kw
        cj_count     = max(15, min(60, max_products // 5))  # 15 → 60

        # AliExpress tasks - one per keyword (parallel keyword fetches)
        if self.aliexpress_available:
            for keyword in trending_keywords[:ali_keywords]:
                supplier_tasks.append(self._fetch_aliexpress(keyword, count=ali_per_kw))
                task_labels.append(f"aliexpress:{keyword[:20]}")

        # CJ Dropshipping tasks
        # Step B: CJ is rate-limited (1 req/sec). Previously we fired 3 tasks
        # (1 category + 2 keyword) concurrently, which caused 429 cascades and
        # burned our 12s per-source timeout. Now: ONE category-only task.
        # If CJ's category search is empty, we'd rather know that cleanly than
        # fall through to keyword spam that triggers rate limits.
        if self.cj_available:
            supplier_tasks.append(self._fetch_cj(keyword="", count=cj_count, niche=niche))
            task_labels.append(f"cj:category:{niche}")

        logger.info(
            f"   📦 Supplier budget @ max_products={max_products}: "
            f"AliExpress {ali_keywords}kw × {ali_per_kw} + CJ {cj_count} "
            f"= {ali_keywords * ali_per_kw + cj_count} raw"
        )

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

        # Merge cached TikTok engagement (playCount, commentCount, etc.) onto
        # discovered products so the scoring pass actually has TikTok data
        # to read. Previously this data was fetched in Step 1 and dropped
        # before the merge — sentiment/demand/trend TikTok branches were
        # dead code in practice.
        try:
            self._merge_tiktok_engagement_into_products(all_products)
        except Exception as exc:
            logger.warning(f"   TikTok engagement merge failed (non-fatal): {exc}")

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

                    # When a sentiment task times out or crashes wholesale,
                    # leave a breadcrumb on every product so downstream
                    # debugging can tell "source attempted but failed" apart
                    # from "source never wired". Without this, products
                    # silently lack data_sources[label] and look identical
                    # to products from a backend with the connector disabled.
                    def _stamp_attempt_failure(reason: str) -> None:
                        for product in all_products:
                            if 'data_sources' not in product:
                                product['data_sources'] = {}
                            # Don't clobber a real entry if one was set by
                            # a prior partial completion of this source.
                            product['data_sources'].setdefault(label, {
                                'available': False,
                                'attempted': True,
                                'reason': reason,
                            })

                    if isinstance(result, asyncio.TimeoutError):
                        logger.warning(f"   ⏱️ {label} sentiment TIMED OUT after {SENTIMENT_SOURCE_TIMEOUT}s - skipped")
                        _stamp_attempt_failure(f'timeout_{SENTIMENT_SOURCE_TIMEOUT}s')
                        continue
                    if isinstance(result, Exception):
                        logger.warning(f"   ⚠️ {label} sentiment failed: {result}")
                        _stamp_attempt_failure(f'exception:{type(result).__name__}')
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
                            else:
                                # Product wasn't in this enricher's per-source top-N
                                # cap (e.g. Twitter enricher caps at 20 to bound cost).
                                # Without a breadcrumb here, the product silently lacks
                                # data_sources[label] and looks identical to a product
                                # from a backend where the source is disabled.
                                if 'data_sources' not in product:
                                    product['data_sources'] = {}
                                product['data_sources'].setdefault(label, {
                                    'available': False,
                                    'attempted': False,
                                    'reason': 'out_of_per_source_cap',
                                })
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

        # =====================================================================
        # STEP 5a: ALIEXPRESS REVIEW TEXT (Phase H)
        # =====================================================================
        # The AliExpress affiliate API gives us ``evaluate_rate`` (rolled-up
        # buyer rating) but NO review text. To do real qualitative reads we
        # need verbatim reviews. We pull them per-product via Apify, capped
        # at the top 10 ranked products to keep costs at ~$9/mo. The reviews
        # land on ``product.aliexpress_reviews`` as text the qualitative
        # agent then reads in step 5b.
        if self.aliexpress_reviews_available and ranked:
            ae_review_start = time.time()
            ae_top = [
                p for p in ranked[:10]
                if p.get("supplier_url") and "aliexpress" in (p.get("supplier_url") or "")
            ]
            logger.info(
                f"\n[REVIEWS] STEP 5a: AliExpress review text for top "
                f"{len(ae_top)} ranked products..."
            )
            if ae_top:
                # Fan out per-product Apify calls in parallel; cap each at
                # the same per-source timeout we use elsewhere.
                review_tasks = [
                    _with_timeout(
                        self.aliexpress_reviews.fetch_reviews(
                            product_url=p["supplier_url"],
                            max_reviews=20,
                        ),
                        SENTIMENT_SOURCE_TIMEOUT,
                    )
                    for p in ae_top
                ]
                review_results = await asyncio.gather(*review_tasks, return_exceptions=True)
                attached = 0
                for product, result in zip(ae_top, review_results):
                    if isinstance(result, (asyncio.TimeoutError, Exception)) or not result:
                        product["aliexpress_reviews"] = None
                        continue
                    if not result.get("available"):
                        product["aliexpress_reviews"] = None
                        continue
                    product["aliexpress_reviews"] = result
                    attached += 1
                logger.info(
                    f"   ✓ AliExpress reviews: {attached}/{len(ae_top)} attached "
                    f"(took {time.time() - ae_review_start:.2f}s)"
                )

        # =====================================================================
        # STEP 5c: YOUTUBE REVIEW VIDEOS + VIEWER COMMENTS (Phase I)
        # =====================================================================
        # YouTube is where buyers go to watch a product BEFORE buying. Top
        # comments are real reviewer feedback prose — perfect input for the
        # qualitative agent. Free 10k quota/day; ~107 units per product, so
        # cap at top 10 ranked products to stay safely under quota.
        if self.youtube_reviews_available and ranked:
            yt_start = time.time()
            yt_top = ranked[:10]
            logger.info(
                f"\n[YOUTUBE] STEP 5c: YouTube review videos + comments for top "
                f"{len(yt_top)} ranked products..."
            )
            yt_tasks = [
                _with_timeout(
                    self.youtube_reviews.get_product_reviews(
                        product_name=p.get("title") or p.get("name") or "",
                        max_videos=5,
                        max_comments_per_video=5,
                    ),
                    SENTIMENT_SOURCE_TIMEOUT,
                )
                for p in yt_top
            ]
            yt_results = await asyncio.gather(*yt_tasks, return_exceptions=True)
            yt_attached = 0
            for product, result in zip(yt_top, yt_results):
                if isinstance(result, (asyncio.TimeoutError, Exception)) or not result:
                    product["youtube_evidence"] = None
                    continue
                if not result.get("available"):
                    product["youtube_evidence"] = None
                    continue
                product["youtube_evidence"] = result
                yt_attached += 1
            logger.info(
                f"   ✓ YouTube reviews: {yt_attached}/{len(yt_top)} attached "
                f"(took {time.time() - yt_start:.2f}s)"
            )

        # Step 5d (Instagram) was removed per cost-cut decision — see init
        # block comment above for context.

        # Step 5e (Amazon review text) was moved to ON-DEMAND fetch per
        # cost-cut decision. Discovery no longer fans out the Apify call to
        # top-10 products; instead, ``ProductDiscovery.fetch_amazon_review_text``
        # is called by a frontend route (or the qualitative-refresh action) when
        # a user actually opens a product card. The fetch is cached by ASIN for
        # 24h so repeated clicks don't re-bill. ~$5-15/mo at typical click
        # volumes vs. $45-90/mo for the bulk-at-discovery path.

        # =====================================================================
        # STEP 5b: QUALITATIVE AI AGENT — actual "eyes" on social evidence
        # =====================================================================
        # Numeric composite says HOW STRONG the signal is. The agent says
        # WHAT THE SIGNAL IS SAYING. Capped at the top 10 ranked products so
        # we don't burn tokens on weak candidates the user wouldn't click on
        # anyway. Strict provider routing: xAI Grok (live X integration)
        # primary, Claude as fallback. See sentiment_qualitative.py.
        if include_sentiment and ranked:
            qual_start = time.time()
            logger.info("\n[AGENT] STEP 5b: Qualitative AI read on top 10 ranked products...")

            try:
                from ospra_os.intelligence.sentiment_qualitative import assess_product
            except ImportError as exc:
                logger.warning(f"   qualitative agent unavailable: {exc}")
                assess_product = None  # type: ignore[assignment]

            if assess_product is not None:
                top_for_agent = ranked[:10]
                qual_tasks = [
                    _with_timeout(assess_product(p), SENTIMENT_SOURCE_TIMEOUT)
                    for p in top_for_agent
                ]
                qual_results = await asyncio.gather(*qual_tasks, return_exceptions=True)
                merged = 0
                for product, result in zip(top_for_agent, qual_results):
                    if isinstance(result, (asyncio.TimeoutError, Exception)):
                        # Don't crash discovery on agent failure; surface in logs only.
                        logger.debug(
                            "   qualitative agent failed for %s: %s",
                            product.get('title', '?')[:30], result,
                        )
                        product['qualitative_assessment'] = None
                        continue
                    product['qualitative_assessment'] = result.to_dict()
                    merged += 1
                logger.info(
                    f"   ✓ {merged}/{len(top_for_agent)} qualitative reads landed "
                    f"(took {time.time() - qual_start:.2f}s)"
                )

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

        # Backfill clean_title for any product missing one (CJ products
        # don't get cleaned at supplier-fetch time; AE products already do).
        # Without this, the dedup below uses raw 120-char keyword salad and
        # finds fewer matches.
        for p in url_valid:
            if not p.get('clean_title'):
                p['clean_title'] = _clean_product_title(
                    p.get('title', ''), max_chars=60
                )

        # Fuzzy-title dedup BEFORE the max_products slice — drop near-
        # duplicates so we don't waste tier budget on multiple SKUs of
        # the same product. Sorted by oi_score in the dedup helper, so
        # the higher-OI variant wins each cluster.
        url_valid = _dedupe_by_title(url_valid, threshold=0.7)

        final = url_valid[:max_products]

        # Caption generation (Task #16). Generates a per-product Shopify
        # caption via Claude on the top N products only — capped at 20
        # to keep cost bounded (~$0.01/call × 20 = $0.20/discovery).
        #
        # Why here and not earlier: we want captions only for products
        # the user is actually going to see (post-rank, post-dedup,
        # post-URL-validation). Generating 100+ captions on raw fetch
        # results would burn ~$1/discovery on products that get pruned.
        if final:
            await self._generate_captions_for_top(final, top_n=20)

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

        # Pinterest Trends task — wired here for the first time. The
        # PinterestTrendsApify connector existed but only powered the
        # opportunity_scorer; discovery never saw it. Pinterest is
        # uniquely strong for visual/lifestyle niches (kitchen, beauty,
        # home decor) and complements Google Trends for those categories.
        if self.apify_available and getattr(self, "pinterest_scraper", None):
            trend_tasks.append(self._fetch_pinterest_trends(niche))
            trend_labels.append("pinterest_trends")

        # TikTok Shop Partner API task — first-party data with real
        # units_sold_7d. Most user shops won't have this OAuth-configured,
        # so guarded behind ``self.tiktok_shop_connector``.
        if getattr(self, "tiktok_shop_connector", None):
            trend_tasks.append(self._fetch_tiktok_shop_trends(niche))
            trend_labels.append("tiktok_shop")

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
        """
        Fetch trending keywords from Google Trends.

        Phase G: also stash ``related_queries`` on
        ``self._google_trends_related`` so the qualitative agent can
        consume them as context (NOT as sentiment input — Trends is
        interest, not opinion).
        """
        try:
            trend_data = await self.trend_analyzer._get_google_trends(keyword, niche)
            if trend_data.get('available'):
                momentum = trend_data.get('momentum', {})
                rising_keywords = [kw for kw, score in momentum.items() if score > 10]

                # Stash related queries keyed by lowercased base keyword
                # so we can fuzzy-match per product later.
                if not hasattr(self, "_google_trends_related") or self._google_trends_related is None:
                    self._google_trends_related = {}
                rqs = trend_data.get('related_queries') or {}
                for kw, qs in rqs.items():
                    if kw and qs:
                        self._google_trends_related[kw.lower().strip()] = qs

                return {
                    'keywords': rising_keywords,
                    'trend_direction': trend_data.get('trend_direction', 'STABLE'),
                    'source': 'google_trends',
                    'momentum': momentum,
                    'related_queries': rqs,
                }
        except Exception as e:
            logger.debug(f"Google Trends fetch failed for '{keyword}': {e}")
        return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'google_trends'}

    async def _fetch_tiktok_trends(self, niche: str, keyword: str) -> List[str]:
        """
        Fetch viral product keywords from TikTok.

        Bug fix: previously this method dropped every engagement field
        (playCount, commentCount, etc.) before merging — the catalog called
        this out as "fetched then dropped." Now we ALSO stash the engagement
        data on ``self._tiktok_engagement_cache`` keyed by normalized
        product name, so the scoring pass can fuzzy-match it back onto
        discovered products. This is what unblocks TikTok in the demand,
        trend, and (new) sentiment cascades.
        """
        try:
            tiktok_products = await self.tiktok_scraper.discover_products(
                niche=niche,
                max_products=5,
                keyword=keyword,
            )
            keywords = []
            # Initialize cache lazily so we don't break instances that
            # were constructed before this attribute existed.
            if not hasattr(self, "_tiktok_engagement_cache") or self._tiktok_engagement_cache is None:
                self._tiktok_engagement_cache = {}

            for p in tiktok_products:
                name = (p.get('name') or p.get('title') or '').strip()
                if not name:
                    continue

                # Keyword extraction (existing behaviour)
                words = [w for w in name.split() if len(w) > 3 and w.isalpha()]
                if words:
                    keywords.append(' '.join(words[:3]))

                # Stash engagement under a normalized key for fuzzy match.
                norm = ' '.join(name.lower().split())
                self._tiktok_engagement_cache[norm] = {
                    'play_count': int(p.get('playCount') or p.get('play_count') or 0),
                    'comment_count': int(p.get('commentCount') or p.get('comment_count') or 0),
                    'share_count': int(p.get('shareCount') or p.get('share_count') or 0),
                    'digg_count': int(p.get('diggCount') or p.get('digg_count') or 0),
                    'video_url': p.get('webVideoUrl') or p.get('video_url'),
                    'caption': p.get('text') or p.get('caption') or '',
                    'source_keyword': keyword,
                }
            return keywords
        except Exception as e:
            logger.debug(f"TikTok trends fetch failed: {e}")
        return []

    def _merge_tiktok_engagement_into_products(self, products: List[Dict]) -> None:
        """
        Fuzzy-match cached TikTok engagement onto discovered products.

        Called from the discovery flow AFTER suppliers and trends have been
        fetched. For each product we look at the title and try to find a
        TikTok cache entry whose normalized name shares ≥2 keyword tokens —
        that's enough overlap to call it the same product without inviting
        the cross-niche false positives we saw with the CJ matcher.
        """
        cache = getattr(self, "_tiktok_engagement_cache", None) or {}
        if not cache:
            return
        for product in products:
            title = (product.get('title') or '').lower()
            if not title:
                continue
            title_tokens = {t for t in title.split() if len(t) > 3}
            best_score = 0
            best_data = None
            for norm, engagement in cache.items():
                tt_tokens = {t for t in norm.split() if len(t) > 3}
                if not tt_tokens:
                    continue
                overlap = len(title_tokens & tt_tokens)
                if overlap >= 2 and overlap > best_score:
                    best_score = overlap
                    best_data = engagement
            if best_data:
                # Land on the product object in the shape the scoring pass expects.
                product.setdefault('data_sources', {})
                product['data_sources']['tiktok'] = {
                    'available': True,
                    'views': best_data['play_count'],
                    'comments': best_data['comment_count'],
                    'shares': best_data['share_count'],
                    'likes': best_data['digg_count'],
                    'video_url': best_data['video_url'],
                    'caption': best_data['caption'],
                    'matched_via': 'fuzzy_title',
                }
                product['tiktok_views'] = best_data['play_count']
                product['tiktok_comment_count'] = best_data['comment_count']
                product['tiktok_engagement'] = (
                    (best_data['digg_count'] + best_data['comment_count'])
                    / best_data['play_count']
                    if best_data['play_count'] > 0 else 0.0
                )

    async def _fetch_tiktok_shop_trends(self, niche: str) -> dict:
        """
        Fetch trending TikTok Shop products via the official Partner API.

        Returns dict-shaped output (matching `_fetch_google_trends`) plus
        stashes the raw `units_sold_7d` / `views_7d` per product on
        ``self._tiktok_shop_cache`` so the scoring pass can fuzzy-merge it
        onto discovered products as a real demand signal (first-party
        purchase data, stronger than any social proxy we have).
        """
        try:
            connector = self.tiktok_shop_connector
            candidates = await connector.get_trending(category=None, limit=20)

            if not hasattr(self, "_tiktok_shop_cache") or self._tiktok_shop_cache is None:
                self._tiktok_shop_cache = {}

            keywords = []
            for c in candidates or []:
                name = (c.name or "").strip()
                if not name:
                    continue
                words = [w for w in name.split() if len(w) > 3 and w.isalpha()]
                if words:
                    keywords.append(" ".join(words[:3]))

                norm = " ".join(name.lower().split())
                self._tiktok_shop_cache[norm] = {
                    'units_sold_7d': getattr(c, 'units_sold_7d', 0) or 0,
                    'views_7d': getattr(c, 'views_7d', 0) or 0,
                    'velocity_score': getattr(c, 'velocity_score', 0) or 0,
                    'product_url': getattr(c, 'url', None),
                }

            return {
                'keywords': keywords,
                'trend_direction': 'RISING' if keywords else 'UNKNOWN',
                'source': 'tiktok_shop',
            }
        except Exception as e:
            logger.debug(f"TikTok Shop trends fetch failed: {e}")
            return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'tiktok_shop'}

    async def _fetch_pinterest_trends(self, niche: str) -> dict:
        """
        Fetch Pinterest Trends keywords for the niche.

        Pinterest is uniquely valuable for visual / lifestyle product
        discovery (kitchen, beauty, home decor) — what's "rising on
        Pinterest" usually surfaces 2-4 weeks before Google/TikTok pick
        it up. Returns the same shape as ``_fetch_google_trends`` so the
        merge loop can treat it identically.
        """
        try:
            # Pinterest connectors expose either ``get_trending_pins`` or
            # ``get_trending_keywords`` depending on the actor version.
            # Try whichever is available; fall back to empty cleanly.
            scraper = self.pinterest_scraper
            if hasattr(scraper, "get_trending_keywords"):
                trending = await scraper.get_trending_keywords(niche=niche, limit=10)
            elif hasattr(scraper, "get_trending_pins"):
                pins = await scraper.get_trending_pins(niche=niche, limit=10)
                # Extract title tokens
                trending = []
                for pin in pins or []:
                    title = (pin.get("title") or pin.get("description") or "").strip()
                    if title:
                        words = [w for w in title.split() if len(w) > 3 and w.isalpha()]
                        if words:
                            trending.append(" ".join(words[:3]))
            else:
                logger.debug("Pinterest scraper has no recognized trending method")
                trending = []

            return {
                'keywords': trending or [],
                'trend_direction': 'RISING' if trending else 'UNKNOWN',
                'source': 'pinterest_trends',
            }
        except Exception as e:
            logger.debug(f"Pinterest trends fetch failed: {e}")
            return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'pinterest_trends'}

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
                
                # Category-aware markup (replaces hardcoded cost × 2.5).
                # See _suggested_price_for_cost docstring for the bracket
                # rationale: cheap items tolerate higher markups, expensive
                # ones need tighter margins to stay competitive.
                suggested_price = _suggested_price_for_cost(cost_price)
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

                _raw_title = item.get('product_title', 'AliExpress Product')
                product = {
                    "product_id": str(item.get('product_id', '')),
                    # Original AE title — preserved for the qualitative agent
                    # which wants full keyword context for sentiment matching.
                    "title": _raw_title,
                    # Human-readable label for UI display. AE titles are
                    # 120+ chars of keyword stuffing; clean_title is
                    # ~60 chars of the head noun phrase.
                    "clean_title": _clean_product_title(_raw_title, max_chars=60),
                    "title_normalized": self._normalize_title(_raw_title),
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

            # Threshold: 0.55 = strict-enough to prevent false-positive merges.
            # The previous 0.40 + the 0.3 keyword floor below let unrelated
            # CJ items merge into AliExpress products purely on synonym overlap
            # (wifi↔smart↔wireless), then the supplier-badges UI lit up
            # ``CJ Dropshipping ✓`` on AliExpress-only products. Raised back to
            # 0.55 in tandem with removing the floor — see ``_calculate_match_score``.
            if best_match and best_score >= 0.55:
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

            # Jaccard similarity on expanded sets — raw, no floor.
            # The 0.3 minimum that used to live here ("at least 1 common
            # keyword = 0.3") was the smoking gun behind the false-CJ-badge
            # bug: synonym expansion turns ``wifi``/``smart``/``wireless``
            # into the same cluster, so two unrelated smart-home products
            # always shared at least one expanded keyword and the floor
            # made every pair score ≥0.3 on this 40%-weight axis. Combined
            # with the 0.40 acceptance threshold and a category bonus, that
            # gave a free 0.22 toward acceptance regardless of similarity.
            intersection = expanded1 & expanded2
            union = expanded1 | expanded2
            if union:
                breakdown['keyword_score'] = len(intersection) / len(union)

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

        # ``available=True`` only when the CJ payload actually contains real
        # CJ-side data. Belt-and-braces against the false-CJ-badge bug: even
        # if the matcher mis-pairs an Ali product with an empty/sentinel CJ
        # row, we won't tell the UI "CJ available" without proof.
        cj_has_real_payload = bool(
            cj_product.get('product_id')
            or cj_product.get('cj_pid')
            or cj_product.get('warehouse')
            or cj_product.get('cj_url')
        )

        # Mark as cross-referenced
        merged['cross_referenced'] = bool(cj_has_real_payload)
        merged['available_on'] = (
            ['aliexpress', 'cj_dropshipping'] if cj_has_real_payload else ['aliexpress']
        )

        # Add CJ data to data_sources
        if 'data_sources' not in merged:
            merged['data_sources'] = {}
        merged['data_sources']['cj_dropshipping'] = cj_product.get('data_sources', {}).get('cj_dropshipping', {})
        merged['data_sources']['cj_dropshipping']['available'] = bool(cj_has_real_payload)

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
                # Phase F: real tweet URLs from xAI live search. These are
                # verifiable links (UI can render as clickable). When present,
                # source_type flips from "grok_paraphrase" to "grok_live_search".
                # An empty citations list with sample_tweets present means we
                # fell back to the older paraphrase-only path (xAI live search
                # may have been disabled or returned no real posts).
                'citations': sentiment.get('citations') or [],
                'source_type': (
                    'grok_live_search' if (sentiment.get('citations') or [])
                    else 'grok_paraphrase'
                ),
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

    async def _generate_captions_for_top(self, products: List[Dict], top_n: int = 20) -> None:
        """Generate per-product Shopify captions for the top N products.

        Mutates products in-place: sets product['caption'] when generation
        succeeds, leaves it None on failure. Capped at top_n to bound cost
        (Claude haiku ~$0.01/call → top_n=20 = ~$0.20/discovery).

        Failure modes (all degrade gracefully):
          - Caption module not importable → all captions stay None
          - Per-product Claude call errors out → that product's caption None
          - Per-product Claude call times out → that product's caption None

        Caption text design (anti-template) lives in
        product_analysis_routes._generate_caption_with_claude — see comments
        there for the prompt rationale (Tasks #16 / #63).
        """
        if not products:
            return

        # Lazy import to avoid an api↔intelligence circular import at startup
        try:
            from ospra_os.api.product_analysis_routes import _generate_caption_with_claude
        except Exception as e:
            logger.warning(f"   ⚠️ Caption generator unavailable: {e}")
            return

        cap_start = time.time()
        target = products[:top_n]
        logger.info(f"\n[CAPTIONS] Generating Shopify copy for top {len(target)} products...")

        async def _one(p: Dict) -> tuple:
            try:
                title = p.get('title') or p.get('clean_title') or ''
                niche = p.get('niche') or 'general'
                price = float(p.get('suggested_price') or p.get('cost_price') or 0)
                tags = p.get('tags') or []
                if not isinstance(tags, list):
                    tags = []
                # Per-call timeout — Claude haiku is fast (~2s) but we don't
                # want one stuck call to block the discovery response.
                cap = await asyncio.wait_for(
                    _generate_caption_with_claude(
                        title=title,
                        niche=niche,
                        price=price,
                        tags=tags,
                    ),
                    timeout=8.0,
                )
                return (p, cap, None)
            except (asyncio.TimeoutError, Exception) as e:
                return (p, None, str(e)[:120])

        results = await asyncio.gather(*[_one(p) for p in target], return_exceptions=False)

        ok = 0
        for p, cap, err in results:
            if cap and isinstance(cap, str) and cap.strip():
                p['caption'] = cap.strip()
                ok += 1
            else:
                p['caption'] = None
                if err:
                    logger.debug(f"   caption miss for '{(p.get('title') or '')[:30]}': {err}")

        # Mark products beyond the cap so the UI can disambiguate
        # "no caption yet" from "caption generation failed".
        for p in products[top_n:]:
            p.setdefault('caption', None)

        logger.info(
            f"   ✓ Captions: {ok}/{len(target)} generated "
            f"(took {time.time() - cap_start:.2f}s)"
        )

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

            # Bug fix (regression of #11/#12): never write the 50-baseline as
            # if it were a real score. If we have no signal, the field is
            # ``None`` so the UI can show "no data" instead of "score=50".
            # The redistribution math at the end of this function still uses
            # ``has_demand_signal`` to decide whether to count this in the
            # OI total, so making the field nullable here doesn't break the
            # composite score — it only stops two unrelated products from
            # showing identical 50/55 numbers.
            product['demand_score'] = demand_score if has_demand_signal else None
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

            # AliExpress velocity — Western-trend fallback. Mirror of the
            # AE-buyer sentiment fallback: when no Western trend signal
            # (Google Trends / TikTok / Twitter buzz) fires, fall back to
            # AE buzz_score gated on recent_sales volume. A product with
            # buzz=85 and 11k recent sales is meaningfully trending even
            # if Western public-social ignores it.
            #
            # Why gated: buzz_score alone can be inflated by old reviews,
            # so we require >1k recent sales to confirm the buzz reflects
            # current buyer interest, not historical noise.
            #
            # Cap at 80: we have velocity but no direction (no week-over-
            # week comparison from AE), so this branch can't claim
            # peak-trending. Western signals are the only way to hit 90+.
            if not has_trend_signal:
                ae_buzz_for_trend = float(ae_signals.get('buzz_score') or 0)
                ae_recent_for_trend = int(ae_signals.get('recent_sales') or 0)
                if ae_buzz_for_trend > 50 and ae_recent_for_trend > 1000:
                    trend_score = min(80, 30 + ae_buzz_for_trend * 0.5)
                    has_trend_signal = True
                    product['trend_source'] = 'aliexpress_velocity'

            # Same fix as demand: don't pretend the 55-baseline is a real
            # score when no Google Trends / direction / viral / TikTok /
            # Twitter / AE-velocity signal contributed.
            product['trend_score'] = trend_score if has_trend_signal else None
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
            # ================================================================
            # SENTIMENT — COMPOSITE (diversity × volume) — 2026-04-25 rewrite
            # ================================================================
            # The previous cascade was "first source wins, take max with a
            # tier-floor." Two failure modes:
            #
            #   1. A SINGLE Reddit post got the same baseline floor (58) as
            #      50 posts. Volume was ignored past tier boundaries.
            #   2. A product with only Amazon scored as if Amazon was a
            #      complete view. Diversity wasn't reflected.
            #
            # New model (see ``ospra_os/intelligence/sentiment_composite.py``):
            # each source contributes a polarity score AND a confidence
            # weight (log-saturated by evidence volume). The final sentiment
            # is a weight-weighted average across present sources, plus a
            # ``sentiment_confidence`` that blends per-source weight and
            # source-count diversity. Confidence flows into ``data_confidence``
            # so single-source weakness can drive the product into the
            # INSUFFICIENT_DATA tier even when polarity is high.
            # ================================================================
            from ospra_os.intelligence.sentiment_composite import (
                compose as _compose_sentiment,
                SentimentInput,
                amazon_weight as _amazon_w,
                twitter_weight as _twitter_w,
                reddit_weight as _reddit_w,
                tiktok_weight as _tiktok_w,
                aliexpress_buyer_weight as _ae_buyer_w,
                score_from_amazon_buzz as _amazon_s,
                score_from_twitter_polarity as _twitter_s,
                score_from_reddit_mentions as _reddit_s,
                score_from_tiktok_engagement as _tiktok_s,
                score_from_aliexpress_buyer as _ae_buyer_s,
            )
            # AE review-text helpers exist (aliexpress_review_weight,
            # score_from_aliexpress_reviews) but aren't called from the
            # composite cascade — that runs for ALL products inside
            # _calculate_scores, while AE reviews are only fetched for
            # the top 10 (cost cap). Mixing them in the composite would
            # create a discontinuity where ranks 1-10 have 4-source
            # sentiment and ranks 11+ have 3-source. Instead, AE reviews
            # are passed to the qualitative agent only — same products,
            # same cap, where verbatim text matters most.

            sentiment_inputs = []

            # Amazon — rating-driven polarity, weighted by review count.
            if amazon_found_real and amazon_buzz_raw > 0 and amazon_review_count_raw > 0:
                sentiment_inputs.append(SentimentInput(
                    name='amazon_reviews',
                    score=_amazon_s(amazon_buzz_raw),
                    weight=_amazon_w(int(amazon_review_count_raw)),
                ))

            # Twitter — Grok polarity, weighted by tweet count.
            twitter_tweet_count = (
                (data_sources.get('x_twitter') or {}).get('tweet_count', 0) or 0
            )
            if twitter_found_real and twitter_sentiment_raw is not None:
                sentiment_inputs.append(SentimentInput(
                    name='twitter',
                    score=_twitter_s(twitter_sentiment_raw),
                    weight=_twitter_w(int(twitter_tweet_count)),
                ))

            # Reddit — mention count drives both score and weight.
            if reddit_mentions > 0:
                sentiment_inputs.append(SentimentInput(
                    name='reddit',
                    score=_reddit_s(int(reddit_mentions)),
                    weight=_reddit_w(int(reddit_mentions)),
                ))

            # TikTok — comment count drives score and weight.
            tiktok_comment_count = (
                tiktok_data.get('comment_count', 0)
                or tiktok_data.get('total_comments', 0)
                or 0
            )
            tiktok_view_count = tiktok_views or 0
            if tiktok_comment_count > 0 or tiktok_view_count > 1000:
                sentiment_inputs.append(SentimentInput(
                    name='tiktok',
                    score=_tiktok_s(int(tiktok_comment_count), int(tiktok_view_count)),
                    weight=_tiktok_w(int(tiktok_comment_count), int(tiktok_view_count)),
                ))

            # AliExpress buyer rating — Western-fallback sentiment input.
            #
            # Why this exists: most dropshipping products have NO Western
            # public-social presence (no tweets, no Reddit threads, no
            # Amazon listing). Without this branch they score sentiment=None,
            # which floors OI at the demand+profit+sourcing budget (~35-50)
            # regardless of how good the AE buyer evidence is. A product
            # with 11k orders and 4.5★ on AE is strong buyer-side evidence
            # — treating it as "no signal" is dishonest.
            #
            # Why it's a fallback (not always-on): AE ratings are
            # systemically inflated (4.5+ is the de-facto floor on the
            # platform), so combining them with Twitter/Reddit/Amazon
            # would compress the dynamic range of the composite. By only
            # contributing when Western sources are silent, the calibration
            # of products WITH Western coverage is unchanged. Existing
            # comparative rankings between high-coverage products stay
            # the same.
            #
            # Confidence haircut: weight is multiplied by 0.6 to encode
            # that AE buyer ratings are a weaker per-data-point signal
            # than verified Amazon reviews or Reddit polarity. Even at
            # max volume the AE buyer branch tops out at weight ≈ 0.6,
            # vs amazon_weight which can hit 1.0 at ~500 reviews.
            has_western_sentiment = bool(sentiment_inputs)
            if not has_western_sentiment and aliexpress_found_real:
                ae_rating_pct = float(ae_signals.get('rating_pct') or 0)
                ae_rating_stars = float(aliexpress_rating_raw or 0)
                ae_recent_sales = int(ae_signals.get('recent_sales') or 0)
                if ae_rating_stars > 0:
                    sentiment_inputs.append(SentimentInput(
                        name='aliexpress_buyer',
                        score=_ae_buyer_s(ae_rating_pct, ae_rating_stars),
                        weight=_ae_buyer_w(ae_recent_sales) * 0.6,
                    ))

            sentiment_result = _compose_sentiment(sentiment_inputs)

            # Persist on the product. ``sentiment_score`` is None whenever
            # no source had data — the OI composite treats None as zero
            # (no redistribution) so single-source / low-volume products
            # land in INSUFFICIENT_DATA appropriately.
            product['sentiment_score'] = sentiment_result.sentiment_score
            product['sentiment_confidence'] = sentiment_result.sentiment_confidence
            product['sentiment_diversity'] = sentiment_result.diversity
            product['sentiment_n_sources'] = sentiment_result.n_sources
            product['sentiment_source'] = sentiment_result.primary_source
            product['sentiment_sources'] = sentiment_result.sources  # [(name, score, weight), ...]
            product['sentiment_available'] = sentiment_result.sentiment_score is not None

            # Local boolean used by the report block below (preserved for
            # backward compat with code that checked ``has_*_signal``).
            has_twitter_signal = twitter_found_real and twitter_sentiment_raw is not None
            has_reddit_signal = reddit_mentions > 0
            has_amazon_signal = amazon_found_real and amazon_buzz_raw > 0
            sentiment_score = sentiment_result.sentiment_score

            # AliExpress buyer-rating is exposed on the product for the
            # sourcing-score block AND, as of the AE-fallback branch above,
            # contributes to the sentiment composite when Western public-
            # social is silent. CJ structural metadata stays sourcing-only.
            product['aliexpress_buyer_rating'] = (
                int(aliexpress_buzz_raw) if (aliexpress_found_real and aliexpress_buzz_raw > 0) else None
            )
            product['cj_supplier_quality'] = cj_proxy_score

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
                # AE buyer-rating now exposed as a sourcing signal (not sentiment).
                # The architectural rewrite removed ``has_aliexpress_signal`` from
                # the sentiment cascade — re-derive locally here so this report
                # block doesn't NameError.
                'aliexpress_buzz': (
                    int(aliexpress_buzz_raw) if (aliexpress_found_real and aliexpress_buzz_raw > 0) else None
                ),
                'aliexpress_rating': (
                    aliexpress_rating_raw if (aliexpress_found_real and aliexpress_buzz_raw > 0) else None
                ),
            }
            # Local derivations used by the validated-sources + coverage blocks
            # below. Same predicates as in the report dict above; kept as
            # explicit names so the readers stay readable.
            _ae_signal_present = bool(aliexpress_found_real and aliexpress_buzz_raw > 0)
            _cj_signal_present = cj_proxy_score is not None

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
            # AE buyer-rating: now feeds sourcing, not sentiment. Still
            # counted as a validated DATA source so coverage reports it.
            if _ae_signal_present:
                sources_validated.append('aliexpress_ratings')
            # CJ supplier-quality proxy — coverage signal only when CJ is
            # the product's source (otherwise it doesn't apply).
            if _cj_signal_present and is_cj_product:
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
                coverage['cj_supplier_proxy'] = 'real' if _cj_signal_present else 'empty'
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
            # ================================================================
            # OI COMPOSITE — HONEST SCORING (rewritten 2026-04-25)
            # ================================================================
            # Previous behaviour: missing components had their weight
            # redistributed to whichever components had data, so a product
            # with only profit (15%) + sourcing (20%) data would be scored
            # as if those two represented 100% of the analysis. That
            # inflated weak products into the EXCELLENT tier just because
            # they had a US warehouse and decent margin.
            #
            # New behaviour: missing components are treated as ZERO. The
            # composite naturally compresses when signals are missing.
            # A product with only profit + sourcing tops out at:
            #   0.15 * 100 + 0.20 * 100 = 35
            # — which is correctly in the AVOID/INSUFFICIENT-DATA band.
            #
            # ``data_confidence`` records what fraction of the design
            # weight came from real signals. The tier ladder below
            # requires BOTH a high score AND high confidence to label a
            # product GOLDEN/EXCELLENT — you can't be "Strong buy" on 40%
            # of the data.
            # ================================================================
            component_values = {
                'demand':    (0.25, demand_score    if has_demand_signal              else None),
                'trend':     (0.25, trend_score     if has_trend_signal               else None),
                'sentiment': (0.15, sentiment_score if sentiment_score is not None    else None),
                'profit':    (0.15, profit_score),
                'sourcing':  (0.20, product['sourcing_score']),
            }

            # Treat-missing-as-zero: missing components contribute 0 to the
            # weighted sum, NOT redistributed.
            base_score = sum(
                w * (v if v is not None else 0)
                for w, v in component_values.values()
            )

            # ``data_confidence`` = fraction of design weight backed by real
            # signal. Profit (15%) and sourcing (20%) always count because
            # we always know cost/price and supplier metadata. The other
            # three only count when their respective signal flags are True.
            data_confidence = sum(
                w for w, v in component_values.values() if v is not None
            )  # 0.0–1.0
            present_components = [k for k, (_, v) in component_values.items() if v is not None]
            missing_components = [k for k, (_, v) in component_values.items() if v is None]

            product['active_components'] = present_components
            product['missing_components'] = missing_components
            product['data_confidence'] = round(data_confidence, 2)
            product['data_confidence_pct'] = int(round(data_confidence * 100))

            # Apply relevance multiplier (IMPROVED - less harsh)
            # Relevance 100 = 1.0x (no change)
            # Relevance 70 = 0.95x (5% penalty)
            # Relevance 50 = 0.90x (10% penalty)
            # Relevance 30 = 0.80x (20% penalty)
            # Relevance 0 = 0.70x (30% penalty)
            relevance = product.get('relevance_score', 70)
            relevance_multiplier = 0.70 + (relevance / 100) * 0.30

            oi_score = base_score * relevance_multiplier

            # If product is clearly irrelevant, cap score at 45 (POOR tier)
            if relevance < 25:
                oi_score = min(oi_score, 45)
                product['relevance_note'] = f'Off-topic: Low relevance ({relevance}%) to niche'

            product['oi_score'] = round(oi_score, 1)
            product['final_score'] = product['oi_score']
            product['base_score'] = round(base_score, 1)

            # Discovery-stage confidence (kept for backward-compat; counts
            # number of validated source connectors that ran).
            max_sources = 6  # aliexpress, cj, twitter, reddit, google_trends, tiktok
            product['confidence'] = round((len(sources_validated) / max_sources) * 100, 0)

            # ================================================================
            # TIER CLASSIFICATION — gated on BOTH score and data confidence
            # ================================================================
            # If we don't have enough data to grade with confidence, we
            # don't pretend to grade. Below 50% data coverage the product
            # is INSUFFICIENT_DATA regardless of whether profit + sourcing
            # add up to a high number — those two alone don't justify a
            # buy recommendation.
            if data_confidence < 0.50:
                product['tier'] = 'INSUFFICIENT_DATA'
                product['recommendation'] = (
                    f'Not enough validated signal to grade '
                    f'({product["data_confidence_pct"]}% data coverage — '
                    f'missing: {", ".join(missing_components) or "none"})'
                )
            elif oi_score >= 85 and data_confidence >= 0.85:
                product['tier'] = 'GOLDEN'
                product['recommendation'] = 'RARE GEM - Deploy immediately; strong signals across the board.'
            elif oi_score >= 75 and data_confidence >= 0.70:
                product['tier'] = 'EXCELLENT'
                product['recommendation'] = 'Strong buy - validated demand, trend, and sourcing.'
            elif oi_score >= 65 and data_confidence >= 0.60:
                product['tier'] = 'GOOD'
                product['recommendation'] = 'Worth testing - solid opportunity, monitor weak signals.'
            elif oi_score >= 55:
                product['tier'] = 'FAIR'
                product['recommendation'] = 'Proceed with caution - mixed signals.'
            elif oi_score >= 45:
                product['tier'] = 'POOR'
                product['recommendation'] = 'Skip - weak signals or insufficient validation.'
            else:
                product['tier'] = 'AVOID'
                product['recommendation'] = 'Avoid - insufficient data or poor opportunity.'

            logger.debug(f"   Scored: {product.get('title', '')[:30]}... -> {oi_score} ({product['tier']})")

        return products

    # =========================================================================
    # ON-DEMAND ENRICHMENT (Phase K — lazy fetch, cost-controlled)
    # =========================================================================

    # Class-level ASIN cache for on-demand Amazon review-text fetches.
    # Keyed by ASIN -> (timestamp, result). 24h TTL chosen because review
    # text doesn't shift meaningfully day-to-day, and repeated clicks on
    # the same product within a day shouldn't re-bill the actor.
    _amazon_review_text_cache: Dict[str, Tuple[float, Dict]] = {}
    _AMAZON_REVIEW_TEXT_TTL_SECONDS: int = 86400  # 24h

    async def fetch_amazon_review_text(
        self,
        product: Dict,
        *,
        max_reviews: int = 15,
        timeout_secs: float = 30.0,
    ) -> Optional[Dict]:
        """
        On-demand: pull verbatim Amazon review text for ONE product.

        Intended to be called by a frontend product-detail route or by a
        "refresh AI analysis" action — NOT during bulk discovery. This
        keeps Apify spend at ~$5-15/mo (only products users actually
        click) instead of ~$45-90/mo (top-10 every discovery).

        Caches by ASIN for 24h, so repeated clicks on the same listing
        within a day reuse the same fetched payload.

        Args:
          product: a discovery product dict. Must have either
            ``amazon_evidence.top_matches[0].asin`` or ``...url`` set
            for there to be anything to fetch.
          max_reviews: per-product cap (default 15).
          timeout_secs: hard cap on the actor wait.

        Returns:
          The same shape that ``AmazonReviewsTextApify.fetch_reviews``
          returns, plus a ``"cached"`` boolean. Returns ``None`` if no
          ASIN/URL was present, the connector isn't available, or the
          actor errored. Also writes the result to
          ``product["amazon_review_text"]`` so the qualitative agent
          picks it up on the next ``assess_product`` call.
        """
        if not self.amazon_reviews_text_available or not self.amazon_reviews_text:
            return None

        evidence = product.get("amazon_evidence") or {}
        top_matches = evidence.get("top_matches") or []
        if not top_matches:
            return None
        first = top_matches[0]
        asin = (first.get("asin") or "").strip().upper() or None
        url = first.get("url") or None
        if not asin and not url:
            return None

        # Cache lookup keyed by ASIN (URL can also yield an ASIN inside
        # the connector — we use ASIN once we have it).
        cache_key = asin or url
        cached = type(self)._amazon_review_text_cache.get(cache_key)
        if cached:
            cached_at, cached_result = cached
            if time.time() - cached_at < type(self)._AMAZON_REVIEW_TEXT_TTL_SECONDS:
                # Return a shallow copy with the ``cached`` flag set.
                out = dict(cached_result)
                out["cached"] = True
                product["amazon_review_text"] = out
                return out
            # Stale — fall through and re-fetch.

        try:
            result = await _with_timeout(
                self.amazon_reviews_text.fetch_reviews(
                    asin=asin, product_url=url, max_reviews=max_reviews,
                ),
                timeout_secs,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.debug(
                "fetch_amazon_review_text: actor failed for %s: %s",
                asin or url, exc,
            )
            return None

        if not result or not result.get("available"):
            return None

        # Populate cache + product, mark as fresh.
        type(self)._amazon_review_text_cache[cache_key] = (time.time(), dict(result))
        result_with_flag = dict(result)
        result_with_flag["cached"] = False
        product["amazon_review_text"] = result_with_flag
        return result_with_flag

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
