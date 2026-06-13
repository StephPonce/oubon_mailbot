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
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

from ospra_os.intelligence.demand_authenticity import (
    AUTHENTICITY_ENABLED,
    compute_authenticity,
    signals_from_product,
)

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
# products finish in the time of the slowest single call. Raised 15s → 30s
# (2026-06): the xAI Agent Tools migration moved sentiment to grok-4.3's
# server-side ``x_search``, which runs a multi-step search loop on xAI's
# infra and genuinely takes 20-30s — at 15s it timed out and reported no
# sentiment even when the call would have succeeded. Override via
# DISCOVERY_SENTIMENT_TIMEOUT.
SENTIMENT_SOURCE_TIMEOUT = float(os.getenv("DISCOVERY_SENTIMENT_TIMEOUT", "30"))

# Per-source trend-timeout overrides — Apify actors cold-start at 15-60s,
# which the global TREND_SOURCE_TIMEOUT (default 10s) starves entirely.
# The retired Winners-tab flow worked because /winners had its own 90s
# middleware override; the new winner-first /quick flow needs the same
# headroom AT THE PER-SOURCE LEVEL so fast sources (Google Trends) aren't
# punished by giving slow sources their headroom globally.
#
# Empirically:
#   - TikTok scraper (clockworks/free-tiktok-scraper): 30-60s cold
#   - Meta Ad Library actor:                            20-45s cold
#   - Amazon Movers / New Releases (Apify junglee):     15-30s cold
#   - Pinterest / Etsy / TikTok Shop:                   ~15-25s cold
#   - Google Trends (pytrends, in-process):             1-3s, never cold
#
# All env-overridable so we can re-tune from .env without a code change.
TREND_SOURCE_TIMEOUT_OVERRIDES: Dict[str, float] = {
    "tiktok_viral":              float(os.getenv("DISCOVERY_TIMEOUT_TIKTOK", "60")),
    "meta_ads_library":          float(os.getenv("DISCOVERY_TIMEOUT_META", "45")),
    "amazon_movers_rss":         float(os.getenv("DISCOVERY_TIMEOUT_AMAZON_MOVERS", "30")),
    "amazon_new_releases_rss":   float(os.getenv("DISCOVERY_TIMEOUT_AMAZON_NEW_RELEASES", "30")),
    "amazon_bsr":                float(os.getenv("DISCOVERY_TIMEOUT_AMAZON_BSR", "30")),
    "etsy_trending":             float(os.getenv("DISCOVERY_TIMEOUT_ETSY", "25")),
    "pinterest_trends":          float(os.getenv("DISCOVERY_TIMEOUT_PINTEREST", "20")),
    "tiktok_shop":               float(os.getenv("DISCOVERY_TIMEOUT_TIKTOK_SHOP", "30")),
}


def _trend_timeout_for(label: str) -> float:
    """Return the per-source trend timeout for a given task label.

    Labels are emitted by `_get_trending_keywords` when it builds the
    parallel task list (e.g. "tiktok_viral", "meta_ads_library",
    "google_trends:smart"). google_trends:* hits the in-process pytrends
    path which is fast — keep it on the tight global budget. Everything
    else (Apify-backed) gets its per-source headroom from the override
    table above; unknown labels fall back to the global cap.
    """
    if label.startswith("google_trends"):
        return TREND_SOURCE_TIMEOUT
    return TREND_SOURCE_TIMEOUT_OVERRIDES.get(label, TREND_SOURCE_TIMEOUT)


def _with_timeout(coro, timeout: float):
    """Wrap a coroutine so it raises asyncio.TimeoutError after `timeout` seconds.

    Used with asyncio.gather(..., return_exceptions=True) so timed-out sources
    are skipped gracefully and we still return results from fast sources.
    """
    return asyncio.wait_for(coro, timeout=timeout)


def _should_skip_keyword_search(winner_count: int, max_products: int, strict: bool) -> bool:
    """
    Decide whether STEP 2b (keyword-based supplier-CANDIDATE search) runs.

    This is the lever for the "suppliers are sourcing, not discovery" model.

    strict=True  (env DISCOVERY_WINNER_FIRST_STRICT=true): suppliers are
        sourcing-only. STEP 2b never runs, so the ONLY candidates are the
        trend/sentiment-validated winners from STEP 2a (and the AE/CJ products
        those winners sourced). No standalone supplier products with zero
        demand signal can enter — which is exactly what keeps the honest
        scorer from being fed signal-less items. Trades quantity for quality;
        pair with strong winner sources (Meta Ad Library, TikTok Shop, Amazon
        Movers).
    strict=False (default — unchanged behaviour): STEP 2b is skipped only when
        winner-first already produced at least half a page, otherwise it
        supplements so the user always sees a reasonable number of products.
    """
    if strict:
        return True
    threshold = max(int(max_products * 0.5), 5)
    return winner_count >= threshold


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

# ─────────────────────────────────────────────────────────────────────────────
# ANTI-SATURATION SCORING — the differentiator
# ─────────────────────────────────────────────────────────────────────────────
# Sell-The-Trend, Minea, Dropispy, EcomHunt all surface "winners" — products
# that already have many advertisers, many Shopify clones, many Amazon
# listings competing for the same customer. By the time those tools flag a
# product, the field is crowded and ad costs are bid up.
#
# Ospra's differentiator is supposed to be: find the WINNERS BEFORE the
# field crowds. That requires a saturation score — measuring HOW CROWDED
# the market is for a given product — and using it to discount the OI score.
#
# Higher saturation → bigger OI discount. A product with strong sentiment
# AND low saturation rises to the top. A product with strong sentiment but
# heavy saturation (200 advertisers, 100 Amazon clones, declining Trends)
# drops below.
#
# Phase 1 (this file): proxies built from data we ALREADY collect:
#   - AE order count (very high = late-stage saturated)
#   - Amazon match count (many matching listings = crowded)
#   - AE discount % (heavy discounts = price war = saturated)
#   - Google Trends direction (rising = early, falling = late)
#   - Twitter chatter volume (high = mainstream = saturated)
#
# Phase 2 (next session): when Meta Ad Library wires up, replace these
# proxies with direct measures (advertiser_count, ad_age_distribution).
# The function signature stays — only the inputs upgrade.

def _compute_saturation(product: Dict) -> Dict:
    """Compute market saturation for a product. Returns a dict so callers
    can use both the scalar and the breakdown for explainability.

    Returns:
        {
          'score': float,          # 0.0 (uncrowded) to 1.0 (saturated)
          'confidence': float,     # 0.0 to 1.0 — how much input data we had
          'signals': dict,         # per-signal contribution for UI/debug
        }

    When confidence is low (< 0.3), score defaults to 0.5 (unknown). We
    can't penalize products for missing data — that would just hide
    products with sparse signals.
    """
    signals: Dict[str, float] = {}
    weighted_sum = 0.0
    weight_total = 0.0

    # 1. Amazon listing density — many matching Amazon listings = crowded.
    # 0 matches → 0 sat, 50+ matches → 0.9 sat. (We only get match_count
    # when amazon_evidence found real matches; absence is "unknown" not
    # "uncrowded", so we don't penalize the missing case.)
    amazon = product.get('amazon_evidence') or {}
    if amazon.get('found_matches'):
        match_count = int(amazon.get('match_count') or 0)
        sat = min(0.9, match_count / 50.0)
        signals['amazon_listing_density'] = round(sat, 3)
        weighted_sum += sat * 0.30
        weight_total += 0.30

    # 2. AE total order volume — very high = late-stage saturated.
    # Sweet spot is 200-2000 orders (early growth, not yet flooded).
    # >50k orders typically means the product peaked 6+ months ago and
    # the market is now race-to-bottom.
    ali_orders = int(product.get('lastest_volume') or product.get('sales_count') or 0)
    if ali_orders > 0:
        if ali_orders >= 50000:
            sat = 0.85
        elif ali_orders >= 10000:
            sat = 0.55
        elif ali_orders >= 2000:
            sat = 0.25  # ← sweet spot, growing but not crowded
        elif ali_orders >= 200:
            sat = 0.15  # ← very early, opportunity zone
        else:
            sat = 0.10  # too early, may not have proven demand yet
        signals['ali_order_volume'] = round(sat, 3)
        weighted_sum += sat * 0.25
        weight_total += 0.25

    # 3. AE discount % — heavy discounting suggests price war / supplier
    # competition, which only emerges when many sellers chase the same
    # product. 0% discount = no price pressure; 70%+ discount = deep
    # commodity competition.
    discount = float(product.get('discount_pct') or 0)
    if discount > 0:
        sat = min(0.9, discount / 80.0)
        signals['ae_discount_pressure'] = round(sat, 3)
        weighted_sum += sat * 0.15
        weight_total += 0.15

    # 4. Google Trends direction — rising = early-stage opportunity,
    # plateau = mature, falling = past peak. We treat 'unknown' as
    # missing rather than neutral so we don't dilute confidence with
    # null inputs.
    data_sources = product.get('data_sources') or {}
    gt = data_sources.get('google_trends') or {}
    trend_dir = (gt.get('direction') or product.get('trend_direction') or '').lower()
    if trend_dir == 'rising':
        sat = 0.15  # Early — saturation low
        signals['trend_phase'] = round(sat, 3)
        weighted_sum += sat * 0.20
        weight_total += 0.20
    elif trend_dir == 'falling':
        sat = 0.85  # Past peak — saturation high
        signals['trend_phase'] = round(sat, 3)
        weighted_sum += sat * 0.20
        weight_total += 0.20
    elif trend_dir == 'stable':
        sat = 0.55  # Plateau — moderate
        signals['trend_phase'] = round(sat, 3)
        weighted_sum += sat * 0.20
        weight_total += 0.20

    # 5. Twitter chatter volume — high tweet count = mainstream awareness
    # = field is already paying attention. <20 tweets = niche, >200 = mass
    # market discussion (likely already saturated).
    twitter = product.get('twitter_evidence') or {}
    if twitter.get('found_real_tweets'):
        tweet_count = int(twitter.get('tweet_count') or 0)
        sat = min(0.85, tweet_count / 200.0)
        signals['twitter_chatter'] = round(sat, 3)
        weighted_sum += sat * 0.10
        weight_total += 0.10

    # 6. Meta advertiser density — Task #9 Phase 2 direct measure.
    # Until now, ali_order_volume was a proxy for "is this product crowded?"
    # — high sales count was assumed to mean "lots of dropshippers selling
    # it." But that's a noisy proxy: a product can have 50k orders from
    # one super-seller and zero competition, or 200 orders spread across
    # 30 dropshippers. The DIRECT measure is "how many distinct
    # advertisers are running ads for this niche right now" — populated
    # on the product by the scoring loop from
    # engine._meta_winners_cache['advertisers'].
    #
    # Weight: 0.25 (same as the AE order proxy it complements). Over
    # time we may zero out the AE proxy if this direct signal proves
    # more predictive.
    meta_advertiser_count = int(product.get('meta_niche_advertiser_count') or 0)
    if meta_advertiser_count > 0:
        # Translate advertiser count to saturation:
        #   1-2   → 0.10 (blue ocean — almost no competition)
        #   3-7   → 0.30 (validated, early — sweet spot for entry)
        #   8-15  → 0.55 (established niche, multiple players)
        #   16-30 → 0.75 (crowded, late entrant)
        #   30+   → 0.90 (race to bottom)
        if meta_advertiser_count >= 30:
            sat = 0.90
        elif meta_advertiser_count >= 16:
            sat = 0.75
        elif meta_advertiser_count >= 8:
            sat = 0.55
        elif meta_advertiser_count >= 3:
            sat = 0.30
        else:
            sat = 0.10
        signals['meta_advertiser_density'] = round(sat, 3)
        weighted_sum += sat * 0.25
        weight_total += 0.25

    if weight_total == 0:
        # No saturation data at all — return unknown / neutral.
        return {
            'score': 0.5,
            'confidence': 0.0,
            'signals': {},
            'note': 'no_saturation_data_available',
        }

    score = weighted_sum / weight_total
    # Confidence = fraction of the ideal 1.0 weight we actually filled.
    # Helps the UI show "saturation: HIGH (high confidence)" vs
    # "saturation: HIGH (low confidence — only 1 signal)".
    confidence = min(1.0, weight_total)

    return {
        'score': round(score, 3),
        'confidence': round(confidence, 3),
        'signals': signals,
    }


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
                        "painting", "vase", "cushion", "pillow", "blanket", "living room set",
                        # Word-collision excludes (2026-06-13 smart_home probe): these
                        # off-niche items slipped through on a single generic include
                        # token — "plug" (sink plug), "light" (camping lantern),
                        # "bluetooth"/"camera" (wearables). Their distinctive category
                        # words are excluded so the gate drops them while genuine smart
                        # plugs / bulbs / wifi cameras (no exclude token) still pass.
                        # Plumbing:
                        "basin", "sink", "faucet", "drain",
                        # Camping / non-smart lighting:
                        "lantern", "kerosene", "tent", "camping",
                        # Wearables (smartwatches, smart glasses, earbuds are not smart_home):
                        "watch", "earphones", "earbuds", "eyewear", "glasses", "sunglasses",
                        "pedometer", "wristband"]
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

        # Meta Ad Library scraper — Task #10 / winner-proof source #1.
        # Initialized in the Apify block below so it shares the token.
        self.meta_ads_scraper = None

        # Task #12 — Amazon Movers & Shakers RSS. Public feed, no token,
        # no rate limit. Initialized eagerly because it's always
        # available; gracefully no-ops if Amazon temporarily blocks us
        # (handled inside the connector).
        self.amazon_movers_rss = None
        try:
            from ospra_os.product_research.connectors.amazon_movers_rss import (
                get_amazon_movers_rss,
            )
            self.amazon_movers_rss = get_amazon_movers_rss()
            self.sources_status['amazon_movers'] = '[SUCCESS] Connected (public RSS)'
            logger.info("[SUCCESS] Amazon Movers RSS loaded (free, no auth)")
        except Exception as exc:
            self.sources_status['amazon_movers'] = f'[ERROR] {exc}'
            logger.warning(f"[WARNING] Amazon Movers RSS init failed: {exc}")

        if self.apify_token:
            try:
                from ospra_os.product_research.connectors.apify import TikTokShopScraper, AmazonBestsellersScraper
                self.tiktok_scraper = TikTokShopScraper()
                self.amazon_scraper = AmazonBestsellersScraper()
                self.apify_available = True
                self.sources_status['tiktok'] = '[SUCCESS] Connected (Apify)'
                self.sources_status['amazon'] = '[SUCCESS] Connected (Apify)'
                logger.info("[SUCCESS] TikTok + Amazon scrapers loaded")

                # Meta Ad Library — proven-winner signal (advertisers
                # actively spending = product is paying for itself).
                # Best-effort like Pinterest: log + skip on ImportError.
                try:
                    from ospra_os.product_research.connectors.apify.meta_ads_library import (
                        get_meta_ads_library,
                    )
                    self.meta_ads_scraper = get_meta_ads_library()
                    if self.meta_ads_scraper.is_available():
                        self.sources_status['meta_ads'] = '[SUCCESS] Connected (Apify)'
                        logger.info("[SUCCESS] Meta Ad Library scraper loaded")
                    else:
                        self.sources_status['meta_ads'] = '[WARNING] Token check failed'
                        self.meta_ads_scraper = None
                except ImportError as exc:
                    self.sources_status['meta_ads'] = f'[INFO] Connector not installed: {exc}'
                    logger.info(f"[INFO] Meta Ad Library: connector not available ({exc})")
                except Exception as exc:
                    self.sources_status['meta_ads'] = f'[ERROR] {exc}'
                    logger.warning(f"[WARNING] Meta Ad Library init failed: {exc}")

                # Option B: Etsy trending — supplementary signal for
                # handmade/lifestyle niches (decor, jewelry, beauty)
                # where Amazon's data is weak. Niches Etsy doesn't
                # cover well (tech, fitness) are skipped at fetch time.
                self.etsy_trending = None
                try:
                    from ospra_os.product_research.connectors.apify.etsy_trending import (
                        get_etsy_trending,
                    )
                    self.etsy_trending = get_etsy_trending()
                    if self.etsy_trending.is_available():
                        self.sources_status['etsy'] = '[SUCCESS] Connected (Apify)'
                        logger.info("[SUCCESS] Etsy trending scraper loaded")
                    else:
                        self.sources_status['etsy'] = '[WARNING] Token check failed'
                        self.etsy_trending = None
                except ImportError as exc:
                    self.sources_status['etsy'] = f'[INFO] Connector not installed: {exc}'
                except Exception as exc:
                    self.sources_status['etsy'] = f'[ERROR] {exc}'
                    logger.warning(f"[WARNING] Etsy trending init failed: {exc}")

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
            self.sources_status['meta_ads'] = '[ERROR] No APIFY_API_TOKEN'
    
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
        
        # Reddit — RE-ENABLED 2026-06-03. The May-2026 deprecation was
        # premature: the dashboard was reporting "Est." on every product
        # because no FREE sentiment source was firing reliably. Reddit's
        # public JSON API is genuinely free (no auth, no rentals, no Apify
        # actor cost) and the connector below already produces honest
        # sentiment evidence — turning it back on is the fastest way to put
        # a real (not estimated) sentiment number on more products.
        #
        # If a future architectural review wants Reddit back off, set
        # ``DISCOVERY_DISABLE_REDDIT=1``. The qualitative case for the May
        # pivot (Reddit is a LAGGING indicator) still holds for early-winner
        # surfacing — but Meta Ad Library + TikTok Shop are mostly paid
        # right now, so Reddit is the only free-and-running sentiment
        # source until those come back on rentals.
        self.reddit = None
        self.reddit_available = False
        if os.getenv("DISCOVERY_DISABLE_REDDIT", "").strip() in {"1", "true", "yes"}:
            self.sources_status['reddit'] = '[DISABLED] DISCOVERY_DISABLE_REDDIT set'
        else:
            try:
                from ospra_os.product_research.connectors.social.reddit import RedditConnector
                self.reddit = RedditConnector(
                    client_id=os.getenv("REDDIT_CLIENT_ID"),
                    client_secret=os.getenv("REDDIT_SECRET"),
                )
                self.reddit_available = self.reddit.is_available()
                if self.reddit_available:
                    self.sources_status['reddit'] = '[SUCCESS] Connected (public JSON API)'
                    logger.info("[SUCCESS] Reddit connector loaded (public JSON API)")
                else:
                    self.sources_status['reddit'] = '[ERROR] Init failed'
            except Exception as e:
                self.sources_status['reddit'] = f'[ERROR] {e}'

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
        include_sentiment: bool = True,
        include_captions: bool = True,
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
        # STEP 2a: WINNER-FIRST SOURCING (CLAUDE.md social-sentiment-first rule)
        # =====================================================================
        # Read the winner caches that Step 1 already populated as side
        # effects (Meta Ad Library, TikTok Shop, Amazon Movers, Etsy) and
        # fan out to AE + CJ to source supplier matches PER WINNER. This
        # replaces the old "throw the keywords at AE" flow that lost all
        # the structured winner data.
        #
        # If no winners surfaced (small / unmapped niche), we fall through
        # to the legacy keyword-based supplier search below as a safety net.
        step2a_start = time.time()
        logger.info("\n[WINNERS] STEP 2a: Winner-first sourcing (sentiment FIRST, sourcing per-winner)...")

        winner_candidates = self._collect_winner_candidates(niche, max_per_source=5)
        winner_products: List[Dict] = []
        if winner_candidates:
            # Per-winner AE/CJ budget — keep total parallel calls reasonable.
            # 10 winners × 2 suppliers × 3 results = 60 candidates ideally.
            winner_products = await self._source_winners_to_products(
                winner_candidates,
                niche=niche,
                ae_per_winner=3,
                cj_per_winner=3,
            )
            if winner_products:
                data_sources_used.append('winner_first_sourcing')
                logger.info(
                    f"   ✓ Winner-first path sourced {len(winner_products)} products "
                    f"in {time.time() - step2a_start:.2f}s"
                )
            else:
                logger.warning(
                    "   ⚠️ Winner candidates returned 0 AE/CJ matches — "
                    "falling through to keyword-based search"
                )
        else:
            logger.info(
                "   ℹ️ No winner candidates surfaced — using keyword-based search "
                "(legacy path)"
            )

        # =====================================================================
        # STEP 2b: KEYWORD-BASED SUPPLIER SEARCH (fallback + supplement)
        # =====================================================================
        # Runs when winner-first produced fewer than max_products * 0.5
        # results (so we always have at least a half-page to show). When
        # winner-first nailed it, this is skipped entirely to save time.
        winner_threshold = max(int(max_products * 0.5), 5)
        _winner_first_strict = os.getenv("DISCOVERY_WINNER_FIRST_STRICT", "false").lower() == "true"
        skip_keyword_search = _should_skip_keyword_search(
            len(winner_products), max_products, _winner_first_strict
        )
        if skip_keyword_search and _winner_first_strict:
            logger.info(
                "   [WINNER-FIRST STRICT] suppliers are sourcing-only — skipping keyword "
                f"candidate search (winner path produced {len(winner_products)} products)"
            )
        elif skip_keyword_search:
            logger.info(
                f"   ⚡ Skipping keyword-based search — winner path already produced "
                f"{len(winner_products)} products (threshold: {winner_threshold})"
            )

        step2_start = time.time()
        logger.info("\n[SUPPLIER] STEP 2b: Searching suppliers IN PARALLEL...")

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

        # Always start with whatever Step 2a's winner-first path produced.
        # We split the flat winner_products list by source so the
        # cross-reference step sees AE and CJ separately like it expects.
        #
        # `source` is now a routing key (always 'aliexpress' /
        # 'cj_dropshipping') — winner attribution lives on
        # `winner_source` + `winner_provenance` and doesn't affect
        # routing decisions. See the comment in _source_winners_to_products
        # for the bug this avoids.
        #
        # Dedup-by-product-id on BOTH sides — without this, when the keyword
        # fallback below returns the same AE product that winner-first
        # already sourced, the keyword version (no winner_provenance) gets
        # appended alongside the tagged version. Then `_dedupe_by_title`
        # later picks one based on oi_score, and the keyword version
        # usually wins because the broader query produced richer signals —
        # silently dropping our attribution.
        aliexpress_products: List[Dict] = []
        cj_products: List[Dict] = []
        ae_seen_ids: set = set()
        cj_seen_ids: set = set()

        for p in winner_products:
            src = str(p.get('source') or '')
            if src == 'aliexpress':
                pid = p.get('product_id')
                if pid and pid not in ae_seen_ids:
                    aliexpress_products.append(p)
                    ae_seen_ids.add(pid)
                elif not pid:
                    # No product_id (rare) — keep it; dedup later via title.
                    aliexpress_products.append(p)
            elif src == 'cj_dropshipping':
                pid = p.get('product_id')
                if pid and pid not in cj_seen_ids:
                    cj_products.append(p)
                    cj_seen_ids.add(pid)

        # Keyword-based supplier search runs ONLY when winner-first didn't
        # produce enough to fill the page. Saves ~10s on hot niches where
        # Meta/TikTok-Shop/etc. already nailed it.
        if not skip_keyword_search:
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
                    # Dedupe AE products against winner-path picks — without
                    # this the keyword version of an already-tagged product
                    # collides and downstream title-dedup may keep the
                    # untagged copy, dropping winner_provenance attribution.
                    added = 0
                    skipped = 0
                    for p in result:
                        pid = p.get('product_id')
                        if pid and pid in ae_seen_ids:
                            skipped += 1
                            continue
                        aliexpress_products.append(p)
                        if pid:
                            ae_seen_ids.add(pid)
                        added += 1
                    if skipped:
                        logger.debug(
                            f"   ✓ {label}: +{added} new / {skipped} already had "
                            "winner-first attribution"
                        )
                    else:
                        logger.debug(f"   ✓ {label}: {added} products")
                elif label.startswith("cj"):
                    # Dedupe CJ products against winner-path picks too
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
        if skip_keyword_search:
            logger.info("   ⏱️ Step 2b skipped (winner path satisfied page)")
        else:
            logger.info(f"   ⏱️ Step 2b (parallel) took {time.time() - step2_start:.2f}s")

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

        # =====================================================================
        # STEP 3b: NICHE RELEVANCE GATE (#54)
        # =====================================================================
        # Drop candidates that don't belong in the requested niche BEFORE we
        # spend sentiment/trend API calls on them. Catches both meta-ads
        # winners and supplier matches whose product type drifted off-niche
        # (e.g. plush slippers / holiday flags attaching to a smart_home
        # winner via loose keyword overlap).
        _pre_gate = len(all_products)
        all_products = self._apply_niche_gate(all_products, niche)
        if len(all_products) != _pre_gate:
            logger.info(
                f"   -> {len(all_products)} products after relevance gate "
                f"(removed {_pre_gate - len(all_products)})"
            )

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

        # ── Wire per-winner Google Trends into per-product scores (2026-06-04) ──
        # The trend fetch was otherwise niche-level and never reached the
        # per-product scorer — data_sources['google_trends'] had no writer, so
        # google_trends was always null in every score_breakdown. Here we fetch
        # pytrends interest for each WINNER's phrase (batched ≤5/call) and stamp
        # it on every product that winner sourced, giving the scorer a real,
        # cross-product-comparable trend signal at winner granularity. Wrapped
        # so a trend hiccup can never break discovery.
        if self.trend_analyzer and getattr(self, 'trends_available', False) and all_products:
            try:
                phrase_by_winner: Dict[str, str] = {}
                for p in all_products:
                    wname = ((p.get('winner_provenance') or {}).get('source_winner_name') or '').strip()
                    if wname and wname not in phrase_by_winner:
                        phrases = self.trend_analyzer._extract_keywords(wname, niche)
                        if phrases:
                            phrase_by_winner[wname] = phrases[0]
                if phrase_by_winner:
                    trend_map = await self.trend_analyzer.get_trend_interest(
                        list(dict.fromkeys(phrase_by_winner.values()))
                    )
                    attached = 0
                    for p in all_products:
                        wname = ((p.get('winner_provenance') or {}).get('source_winner_name') or '').strip()
                        phrase = phrase_by_winner.get(wname)
                        td = trend_map.get((phrase or '').lower()) if phrase else None
                        if td and td.get('available') and td.get('interest', 0) > 0:
                            ds = p.setdefault('data_sources', {})
                            ds['google_trends'] = {
                                'interest': td['interest'],
                                'direction': td['direction'],
                                'momentum': td.get('momentum', 0),
                                'available': True,
                                'source': 'pytrends',
                                'matched_phrase': phrase,
                            }
                            p['google_trend_score'] = td['interest']
                            p['trend_direction'] = td['direction']
                            attached += 1
                    logger.info(
                        f"   [trend-wire] attached per-winner Google Trends to "
                        f"{attached}/{len(all_products)} products "
                        f"({len(trend_map)} winner phrases resolved)"
                    )
            except Exception as e:
                logger.warning(f"   [trend-wire] per-winner trend attach failed: {e}")

        # Task #24: pass the user-facing category niche down so per-product
        # relevance can fall back to it. Otherwise each product carries the
        # specific search keyword that found it ("LED strip lights RGB",
        # "wifi smart plug") which doesn't match any RELEVANCE_KEYWORDS
        # entry, so every product silently scores 70 via the generic
        # word-overlap path.
        scored_products = self._calculate_scores(all_products, category_niche=niche)

        # Per-source min_score (Task #31 — confirmed CJ killer May 11).
        # CJ-only products have no AE buyer signals (no AliExpress velocity,
        # no Amazon fuzzy-match, no AE buyer rating). Their OI ceiling is
        # mathematically just profit (15%) + sourcing (20%) = 35 max,
        # which collapses below min_score=30 after the anti-saturation and
        # relevance multipliers. Result: 100% of CJ products silently
        # filtered out, even when they're legit US-warehouse early-stage
        # products that should be visible in discovery.
        #
        # Fix: CJ-only products use 50% of the min_score floor (default
        # 15 vs 30 for AE). They're not lower-quality products — they're
        # measured by a different yardstick. Cross-referenced products
        # (AE+CJ both) use the full AE floor since they have AE signals.
        def _is_cj_only(p):
            available = p.get('available_on') or []
            return (
                p.get('source') == 'cj_dropshipping'
                or (available == ['cj_dropshipping'])
            )

        def _cj_count_in(plist):
            return sum(1 for p in plist if _is_cj_only(p))

        cj_min_score = min_score * 0.5  # 15 when min_score is 30

        cj_before_filter = _cj_count_in(scored_products)

        def _passes_filter(p):
            threshold = cj_min_score if _is_cj_only(p) else min_score
            return (p.get('oi_score', 0) or 0) >= threshold

        # ── winner_source pre-clamp instrumentation (2026-06-04) ──────────
        # Surface, BEFORE the min_score filter and the route's tier clamp,
        # how each winner source fares: how many of its sourced products
        # were scored and how many clear the floor. Answers "do meta_ads
        # winners survive scoring into the ranked output, or get scored
        # out?" — and for a dropped meta_ads winner, prints the breakdown so
        # we can see which component kills it.
        try:
            from collections import Counter as _Counter
            _ws_total: _Counter = _Counter()
            _ws_pass: _Counter = _Counter()
            for _p in scored_products:
                _ws = _p.get('winner_source') or 'keyword'
                _ws_total[_ws] += 1
                if _passes_filter(_p):
                    _ws_pass[_ws] += 1
            logger.info(
                "   [winner_source] pre-clamp scored set (passing min_score / total): "
                + ", ".join(f"{s}={_ws_pass[s]}/{_ws_total[s]}" for s in sorted(_ws_total))
            )
            _meta_dropped = [
                _p for _p in scored_products
                if _p.get('winner_source') == 'meta_ads' and not _passes_filter(_p)
            ]
            if _meta_dropped:
                _w = min(_meta_dropped, key=lambda p: p.get('oi_score', 0) or 0)
                logger.info(
                    "   [winner_source] dropped meta_ads winner "
                    f"{(_w.get('title') or _w.get('name') or '?')[:60]!r}: "
                    f"oi_score={_w.get('oi_score')} final_score={_w.get('final_score')} "
                    f"floor={min_score} | demand={_w.get('demand_score')} "
                    f"profit={_w.get('profit_score')} sourcing={_w.get('sourcing_score')} "
                    f"saturation={_w.get('saturation_score')} authenticity={_w.get('authenticity_score')} "
                    f"breakdown={_w.get('score_breakdown')}"
                )
        except Exception as _e:
            logger.warning(f"   [winner_source] instrumentation failed: {_e}")

        filtered = [p for p in scored_products if _passes_filter(p)]
        ranked = sorted(filtered, key=lambda x: x.get('oi_score', 0), reverse=True)
        cj_after_filter = _cj_count_in(filtered)
        logger.info(
            f"   [CJ FUNNEL] before filter (AE floor={min_score}, CJ floor={cj_min_score}): "
            f"{cj_before_filter} CJ → after: {cj_after_filter} "
            f"(dropped: {cj_before_filter - cj_after_filter})"
        )

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
        # STEP 5b: ALIEXPRESS DS API — REAL MERCHANT PRICES (Task #24)
        # =====================================================================
        # Up to this point every AE product was priced off the affiliate API's
        # `target_sale_price × 1.65` heuristic — empirically wrong by $2-10.
        # AE's Dropshipping Solution API exposes the real merchant cost
        # (`sku_price`) per SKU plus a per-product variable commission rate.
        # We only enrich the top 10 ranked products because each DS detail
        # call is one rate-limited round-trip (~250ms) and the user only
        # ever looks at top-of-list anyway. Lower-ranked products keep the
        # heuristic estimate.
        try:
            from ospra_os.aliexpress.ds_client import get_ds_client
            ds_client = get_ds_client()
        except Exception as exc:
            logger.debug(f"   AE DS client import failed (non-fatal): {exc}")
            ds_client = None

        if ds_client and ds_client.is_available() and ranked:
            ds_start = time.time()
            # Only AE-sourced products; CJ-only items don't have AE IDs.
            ds_top = [
                p for p in ranked[:10]
                if p.get("product_id") and (
                    p.get("source") == "aliexpress"
                    or "aliexpress" in (p.get("available_on") or [])
                )
            ]
            logger.info(
                f"\n[AE-DS] STEP 5b: Real merchant prices for top "
                f"{len(ds_top)} AE products..."
            )
            if ds_top:
                try:
                    enriched = await _with_timeout(
                        ds_client.enrich_pricing(ds_top, limit=len(ds_top)),
                        SENTIMENT_SOURCE_TIMEOUT,
                    )
                    # `enrich_pricing` overwrites `cost_price` in place but
                    # downstream fields (`suggested_price`, `profit`,
                    # `discount_pct`, `original_price`) were computed from
                    # the old heuristic. Recompute them so the UI's price
                    # card stays internally consistent. Only touch products
                    # the DS API actually had data for.
                    for product in ds_top:
                        if product.get("cost_basis") != "ae_ds_merchant_price":
                            continue
                        new_cost = float(product.get("cost_price") or 0)
                        if new_cost <= 0:
                            continue
                        new_suggested = _suggested_price_for_cost(new_cost)
                        product["suggested_price"] = new_suggested
                        product["profit"] = round(new_suggested - new_cost, 2)
                        msrp = float(product.get("msrp") or 0)
                        product["original_price"] = msrp if msrp > new_cost else new_cost
                        if msrp > new_cost and msrp > 0:
                            product["discount_pct"] = min(
                                90,
                                round(((msrp - new_cost) / msrp) * 100, 0),
                            )
                        else:
                            product["discount_pct"] = 0
                    logger.info(
                        f"   ✓ AE DS pricing: {enriched}/{len(ds_top)} enriched "
                        f"(took {time.time() - ds_start:.2f}s)"
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"   ⏱️ AE DS enrichment timed out — keeping heuristic prices"
                    )
                except Exception as exc:
                    logger.warning(f"   AE DS enrichment failed: {exc}")

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

        # CJ-survival accounting at each downstream step (Task #31).
        # Track how many CJ products go in vs come out of each stage so we
        # can see exactly where they vanish.
        def _cj_count(plist):
            return sum(
                1 for p in plist
                if p.get('source') == 'cj_dropshipping'
                or 'cj_dropshipping' in (p.get('available_on') or [])
            )

        cj_entering_url_validation = _cj_count(ranked)

        # URL VALIDATION: drop products with no usable outbound source URL so
        # the frontend never receives an unclickable product card.
        url_valid: List[Dict] = []
        url_dropped = 0
        cj_url_dropped = 0
        for product in ranked:
            resolved = _resolve_product_url(product)
            if resolved:
                # Normalize: guarantee a top-level supplier_url for the frontend
                product['supplier_url'] = resolved
                url_valid.append(product)
            else:
                url_dropped += 1
                is_cj = (
                    product.get('source') == 'cj_dropshipping'
                    or 'cj_dropshipping' in (product.get('available_on') or [])
                )
                if is_cj:
                    cj_url_dropped += 1
                logger.warning(
                    f"   ⚠️ Dropping product with no usable URL: "
                    f"{'CJ' if is_cj else 'AE'} "
                    f"{product.get('product_id') or product.get('title', '?')[:60]}"
                )

        if url_dropped:
            logger.info(
                f"   🔗 URL validation: kept {len(url_valid)} / dropped {url_dropped} "
                f"(of which CJ: {cj_url_dropped})"
            )

        cj_after_url_validation = _cj_count(url_valid)
        logger.info(
            f"   [CJ FUNNEL] entering URL validation: {cj_entering_url_validation} → "
            f"surviving: {cj_after_url_validation}"
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

        cj_entering_dedup = _cj_count(url_valid)

        # Fuzzy-title dedup BEFORE the max_products slice — drop near-
        # duplicates so we don't waste tier budget on multiple SKUs of
        # the same product. Sorted by oi_score in the dedup helper, so
        # the higher-OI variant wins each cluster.
        url_valid = _dedupe_by_title(url_valid, threshold=0.7)

        cj_after_dedup = _cj_count(url_valid)
        logger.info(
            f"   [CJ FUNNEL] entering dedup: {cj_entering_dedup} → "
            f"surviving dedup: {cj_after_dedup}"
        )

        # Task #26: Source-quota split for the top-N slice.
        # Previous behaviour was a naive `url_valid[:max_products]` — when
        # AE products consistently outscored CJ products (which they do
        # in most niches because AE has richer signals), the final result
        # ended up 100% AliExpress. That kills Task #15 (sourcing UI shows
        # AE + CJ side-by-side per product) — there are no CJ products to
        # show.
        #
        # Fix: allocate a guaranteed CJ quota (default 30%) and fill the
        # rest from AE. If either side has fewer candidates than its quota,
        # the unused slots go back to the other pool so total count is
        # preserved. Final list is re-sorted by oi_score so the highest-
        # scoring picks appear first regardless of source.
        def _is_cj_product(p):
            return (
                p.get('source') == 'cj_dropshipping'
                or 'cj_dropshipping' in (p.get('available_on') or [])
            )

        ae_pool = [p for p in url_valid if not _is_cj_product(p)]
        cj_pool = [p for p in url_valid if _is_cj_product(p)]

        cj_quota_ratio = float(os.getenv("DISCOVERY_CJ_QUOTA_RATIO", "0.3"))
        cj_quota = max(1, int(round(max_products * cj_quota_ratio)))
        ae_quota = max(1, max_products - cj_quota)

        ae_picked = ae_pool[:ae_quota]
        cj_picked = cj_pool[:cj_quota]

        # Backfill: top up the under-filled side from the other pool so
        # the total still hits max_products.
        ae_short = ae_quota - len(ae_picked)
        cj_short = cj_quota - len(cj_picked)
        if cj_short > 0:
            ae_picked = ae_pool[:ae_quota + cj_short]
        if ae_short > 0:
            cj_picked = cj_pool[:cj_quota + ae_short]

        combined = ae_picked + cj_picked
        # Re-sort by oi_score so ranking still reflects quality. Final
        # list will be a mix of AE and CJ in score order — Task #15
        # sourcing UI then groups them per product for side-by-side
        # comparison.
        combined.sort(key=lambda p: (p.get('oi_score') or 0), reverse=True)
        final = combined[:max_products]

        cj_in_final = _cj_count(final)
        ae_in_final = len(final) - cj_in_final
        logger.info(
            f"   [CJ FUNNEL] quota split: target {ae_quota}AE + {cj_quota}CJ → "
            f"actual {ae_in_final}AE + {cj_in_final}CJ"
        )

        # Caption generation (Task #16). Generates a per-product Shopify
        # caption via Claude on the top N products only.
        #
        # Cost cap: top_n=10 (was 20) × ~$0.01 = ~$0.10/discovery.
        # Latency cap: even with parallel asyncio.gather, Claude haiku
        # rate limits queue calls in practice — 10 captions land in
        # ~6-12s, 20 captions land in ~15-25s. The drop from 20 → 10
        # is the biggest single latency win available without further
        # caching.
        #
        # Gated on include_captions so callers can disable for fast
        # internal probes (audit scripts, smoke tests, prefetch warmers).
        # Frontend defaults this to True so the UX still gets captions.
        if final and include_captions:
            await self._generate_captions_for_top(final, top_n=10)

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

        # Meta Ad Library task — Task #10 / winner-proof source #1.
        # Surfaces keywords from advertisers actively spending against
        # this niche. Different from Pinterest/Google in that "active
        # advertising" is a money-backed signal, not just attention.
        if self.apify_available and getattr(self, "meta_ads_scraper", None):
            trend_tasks.append(self._fetch_meta_ads_trends(niche))
            trend_labels.append("meta_ads_library")

        # Amazon Movers & Shakers RSS — Task #12 / winner-proof source #3.
        # Public feed of products with the biggest 24h sales-rank gains.
        # Free, fast, no quota. Niche → category mapping in the connector;
        # niches without a clean mapping skip this source.
        if getattr(self, "amazon_movers_rss", None):
            trend_tasks.append(self._fetch_amazon_movers_rss(niche))
            trend_labels.append("amazon_movers_rss")

            # Option A: Amazon New Releases RSS — products launched in
            # the last 30 days. Catches products even earlier in their
            # lifecycle than Movers (before they've had time to rank).
            # Same connector, different feed_type — free, public.
            trend_tasks.append(self._fetch_amazon_new_releases_rss(niche))
            trend_labels.append("amazon_new_releases_rss")

        # Option B: Etsy trending — supplementary signal for handmade /
        # lifestyle niches (decor, jewelry, beauty). The connector
        # internally skips niches it doesn't have an Etsy category
        # mapping for (tech, fitness, gaming), so we can register the
        # task unconditionally and let it no-op cleanly.
        if self.apify_available and getattr(self, "etsy_trending", None):
            trend_tasks.append(self._fetch_etsy_trending(niche))
            trend_labels.append("etsy_trending")

        # TikTok Shop Partner API task — first-party data with real
        # units_sold_7d. Most user shops won't have this OAuth-configured,
        # so guarded behind ``self.tiktok_shop_connector``.
        if getattr(self, "tiktok_shop_connector", None):
            trend_tasks.append(self._fetch_tiktok_shop_trends(niche))
            trend_labels.append("tiktok_shop")

        # Execute ALL trend queries in parallel — each capped at its
        # per-source timeout (see TREND_SOURCE_TIMEOUT_OVERRIDES). Fast
        # sources (Google Trends) use the 10s global default; slow
        # Apify actors (TikTok, Meta) get 45-60s.
        if trend_tasks:
            per_source_timeouts = [_trend_timeout_for(lbl) for lbl in trend_labels]
            timeout_summary = ", ".join(
                f"{lbl}={t:g}s" for lbl, t in zip(trend_labels, per_source_timeouts)
            )
            logger.info(
                f"   🚀 Launching {len(trend_tasks)} parallel trend queries "
                f"(per-source timeouts: {timeout_summary})..."
            )
            trend_tasks_timed = [
                _with_timeout(t, to)
                for t, to in zip(trend_tasks, per_source_timeouts)
            ]
            trend_results = await asyncio.gather(*trend_tasks_timed, return_exceptions=True)

            # Process results
            for i, result in enumerate(trend_results):
                label = trend_labels[i] if i < len(trend_labels) else f"trend_{i}"
                # Pull the per-source timeout that ACTUALLY fired for this
                # task, not the global default — without this the log lies
                # ("TIMED OUT after 10.0s") when slow Apify sources get
                # their 45-60s budget but still don't finish.
                effective_timeout = (
                    per_source_timeouts[i]
                    if i < len(per_source_timeouts) else TREND_SOURCE_TIMEOUT
                )

                if isinstance(result, asyncio.TimeoutError):
                    logger.warning(
                        f"   ⏱️ {label} TIMED OUT after {effective_timeout:g}s - skipped"
                    )
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

                # Option C: also surface the "rising" subset of related
                # queries as additional trending keywords. The connector
                # already extracts them (with type="rising" tag) but the
                # discovery layer was only using the momentum dict —
                # leaving the strongest "growing fast right now" signal
                # unused. Now we merge them into the keyword pool so the
                # AE/CJ supplier-search funnel picks them up downstream.
                #
                # Cap at 5 rising terms per base keyword to avoid one
                # noisy base topic dominating the pool.
                rising_related: list[str] = []
                for _, qs in rqs.items():
                    if not qs:
                        continue
                    # `qs` is the list of {query, value, type} dicts the
                    # connector produced. Each entry tagged type='rising'
                    # is one Google flagged as gaining momentum.
                    for q in qs:
                        if isinstance(q, dict) and q.get("type") == "rising":
                            term = (q.get("query") or "").strip()
                            if term and term not in rising_related:
                                rising_related.append(term)
                                if len(rising_related) >= 5:
                                    break
                    if len(rising_related) >= 5:
                        break

                # Merge into the returned keyword list. Dedupe happens
                # naturally in the merge loop in `_get_trending_keywords`.
                combined = list(rising_keywords) + rising_related

                return {
                    'keywords': combined,
                    'trend_direction': trend_data.get('trend_direction', 'STABLE'),
                    'source': 'google_trends',
                    'momentum': momentum,
                    'related_queries': rqs,
                    'rising_related_count': len(rising_related),
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

    # Task #4: sub-niche expansion for Meta Ad Library queries.
    # Research from 6+ dropshipping product-discovery sources unanimously
    # says: search SUB-NICHES and angle keywords, not broad category names.
    # Querying Meta for "smart home" returns brands that USE the phrase in
    # marketing copy (GlowRight, Houdini Holster) — not the actual product
    # winners. Real winners run ads on specific sub-categories ("smart plug",
    # "video doorbell") or angle/outcome keywords ("control with phone").
    # This dict expands each top-level niche into 5-8 sub-queries that get
    # run in parallel; results aggregate and dedupe by advertiser page_id.
    # Falls back to [niche] if no expansion defined.
    NICHE_SUBQUERIES: Dict[str, List[str]] = {
        "smart_home": [
            "smart plug", "video doorbell", "smart bulb", "motion sensor",
            "smart lock", "smart camera", "smart switch", "robot vacuum",
        ],
        "kitchen": [
            "kitchen gadget", "knife sharpener", "vegetable chopper",
            "spice rack", "electric grinder", "silicone utensil",
            "coffee maker", "air fryer accessory",
        ],
        "fitness": [
            "resistance band", "foam roller", "massage gun",
            "posture corrector", "yoga mat", "ab roller",
            "compression sleeve", "jump rope",
        ],
        "beauty": [
            "led face mask", "facial cleansing brush", "jade roller",
            "hair straightener", "lash serum", "derma roller",
            "scalp massager", "eyebrow tool",
        ],
        "pet": [
            "self-cleaning brush", "pet water fountain", "interactive cat toy",
            "no-pull harness", "dog dental chew", "pet hair remover",
            "automatic feeder", "pet camera",
        ],
        "tech": [
            "wireless charger", "magsafe accessory", "phone stand",
            "carplay adapter", "usb-c hub", "portable monitor",
            "wireless earbuds", "screen protector",
        ],
        "home_decor": [
            "led wall light", "sunset projector", "smart led strip",
            "wall art print", "ambient lamp", "decorative shelf",
            "macrame hanging", "rug pad",
        ],
        "office": [
            "standing desk", "monitor arm", "ergonomic chair",
            "desk organizer", "cable management", "laptop stand",
            "footrest", "wrist rest",
        ],
        "outdoor": [
            "camping lantern", "portable grill", "hammock chair",
            "solar light", "garden tool", "outdoor projector",
            "patio heater", "cooler bag",
        ],
        "car": [
            "magsafe car mount", "wireless carplay", "dash camera",
            "car vacuum", "led headlight bulb", "tire inflator",
            "car organizer", "obd2 scanner",
        ],
        "baby": [
            "baby monitor", "white noise machine", "diaper organizer",
            "teething toy", "baby carrier", "swaddle blanket",
            "bottle warmer", "nursery night light",
        ],
    }

    async def _fetch_meta_ads_trends(self, niche: str) -> dict:
        """
        Task #10 + Task #4: Meta Ad Library as a winner-proof source,
        with sub-niche expansion.

        Pulls active ads matching multiple sub-niche queries (not just the
        broad niche name) and surfaces three derived signals:

        1. `keywords` — common phrases from creative titles / bodies of
           proven-winner advertisers across all sub-queries.
        2. `winners` — list of unique advertiser pages (deduped by
           page_id) that pass the 14d × 3-variants × Shopify heuristic
           in ANY sub-query.
        3. `ad_count` — total active ads across all sub-queries.

        Why sub-niche expansion: querying Meta for "smart home" returns
        brands that USE the phrase in marketing copy (GlowRight, Houdini
        Holster) — not the actual product winners. Real smart-home
        winners run ads on specific sub-niches ("smart plug",
        "video doorbell"). Multi-query aggregation surfaces 5-10× more
        relevant winners per niche.

        Cost: each Apify call is ~$0.0008/ad. For smart_home with 8
        sub-queries × 25 ads each = 200 ads × $0.0008 = ~$0.16/discovery.
        Acceptable.
        """
        if not getattr(self, "meta_ads_scraper", None):
            return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'meta_ads'}

        # Expand the niche into sub-queries. Falls back to a single-element
        # list containing the niche itself if no expansion is defined
        # (preserves backward compatibility for niches not yet mapped).
        broad_query = niche.replace("_", " ").strip() or "trending"
        sub_queries = self.NICHE_SUBQUERIES.get(niche.lower()) or [broad_query]
        # Always include the broad query as a fallback, deduped at the end.
        if broad_query not in sub_queries:
            sub_queries = list(sub_queries) + [broad_query]

        # Cap the fan-out. Each sub-query is a separate Apify actor run, so
        # the old 8-9 sub-query expansion fired 8-9 facebook-ads actors in
        # parallel per discovery — the single biggest Apify-credit sink and a
        # memory-burst that 402'd on smaller plans. NICHE_SUBQUERIES is
        # ordered most-relevant-first, so the top few keep the strongest
        # winner coverage at a fraction of the cost. Override via
        # META_ADS_MAX_SUBQUERIES.
        # Default 5 (was 3): the 3-cap visibly cost branded-winner coverage in
        # prod probes (obscure keyword products instead of TP-Link/Wyze-class).
        # 9→5 still captures ~most of the credit saving; quality > marginal cut.
        max_sub_queries = max(1, int(os.getenv("META_ADS_MAX_SUBQUERIES", "5")))
        sub_queries = sub_queries[:max_sub_queries]

        logger.info(
            f"[meta-ads] expanding niche '{niche}' to "
            f"{len(sub_queries)} sub-queries (cap={max_sub_queries}): {sub_queries}"
        )

        # Per-query cap. Lower than the old single-query cap of 50 to
        # keep total Apify spend roughly equivalent across both modes.
        per_query_cap = 25

        # Run all sub-queries in parallel via asyncio.gather. Apify calls
        # are I/O bound, so this parallelism is essentially free.
        async def _one(q: str) -> dict:
            try:
                return await self.meta_ads_scraper.search_active_ads(
                    keyword=q,
                    country="US",
                    max_ads=per_query_cap,
                    active_only=True,
                )
            except Exception as e:
                logger.debug(f"Meta Ad Library sub-query '{q}' failed: {e}")
                return {'available': False, 'error': str(e), 'keyword': q}

        results = await asyncio.gather(*[_one(q) for q in sub_queries])

        # Aggregate across sub-query results. Dedup by page_id so the
        # same advertiser appearing in multiple sub-queries only counts
        # once. Track which sub-query first surfaced each advertiser so
        # downstream code can see the discovery path.
        all_winners_by_page: Dict[str, dict] = {}
        all_advertisers_by_page: Dict[str, dict] = {}
        total_ad_count = 0
        per_query_stats: List[dict] = []

        for q, r in zip(sub_queries, results):
            if not isinstance(r, dict):
                per_query_stats.append({'query': q, 'available': False, 'error': 'invalid_response'})
                continue
            if not r.get('available'):
                per_query_stats.append({
                    'query': q,
                    'available': False,
                    'error': r.get('error'),
                })
                continue

            ad_count = int(r.get('ad_count', 0))
            total_ad_count += ad_count

            for w in r.get('winners') or []:
                pid = str(w.get('page_id') or w.get('page_name') or '')
                if pid and pid not in all_winners_by_page:
                    w = dict(w)
                    w['surfaced_by_query'] = q
                    all_winners_by_page[pid] = w

            for adv in r.get('advertisers') or []:
                pid = str(adv.get('page_id') or adv.get('page_name') or '')
                if pid and pid not in all_advertisers_by_page:
                    adv = dict(adv)
                    adv['surfaced_by_query'] = q
                    all_advertisers_by_page[pid] = adv

            per_query_stats.append({
                'query': q,
                'available': True,
                'ad_count': ad_count,
                'winners': len(r.get('winners') or []),
            })

        winners = list(all_winners_by_page.values())
        advertisers = list(all_advertisers_by_page.values())

        # Task #9: niche-relevance filter at Meta layer. Sub-query Meta
        # search returns winners that match ANY single token in the
        # sub-query (e.g. WYBOT matched "robot vacuum" because their
        # pool-cleaning robots contain "robot"). Without this filter,
        # Pat Kay (photography), Over 40 & Fabulous (beauty), WYBOT
        # (pool robotics) all surface as smart_home winners.
        #
        # Heuristic: a winner is niche-relevant if at least 2 distinct
        # niche-token strings appear as substrings in its page_name +
        # sample_landing_urls. The 2-token requirement filters out
        # single-keyword false positives — a truly on-niche brand will
        # mention multiple category words across its name and URLs,
        # whereas off-niche brands only happen to hit the one keyword
        # that surfaced them.
        # Build the niche keyword set from sub-queries, then ALSO add
        # common 3-char prefix forms so URL slug abbreviations match.
        # URL slugs frequently shorten: "wyze-cam-v3" not "wyze-camera-v3",
        # "smart-vac" not "smart-vacuum". Without prefix expansion the
        # filter rejects legitimately-on-niche brands like Wyze.
        niche_keyword_set: set = set()
        ABBREVIATIONS = {
            'camera': ['cam'],
            'vacuum': ['vac'],
            'video':  ['vid'],
            'doorbell': ['bell', 'door'],
            'sensor': ['sens'],
            'monitor': ['mon'],
        }
        for sq in sub_queries:
            for tok in sq.lower().split():
                if len(tok) >= 3:
                    niche_keyword_set.add(tok)
                    for abbr in ABBREVIATIONS.get(tok, []):
                        niche_keyword_set.add(abbr)

        def _is_niche_relevant(entry: dict) -> tuple[bool, set]:
            """Return (kept, matched_tokens) for this winner/advertiser.

            Substring match handles abbreviations like "cam" vs "camera"
            and URL slugs like "wyze-cam-v3" where hyphens would split
            tokens. Requires 2 distinct matches so single-keyword false
            positives (e.g. WYBOT matching only "robot" because they sell
            pool robots) get filtered.
            """
            content_parts = [str(entry.get('page_name') or '')]
            for url in entry.get('sample_landing_urls') or []:
                if isinstance(url, str):
                    content_parts.append(url)
            content = ' '.join(content_parts).lower()
            matched = {tok for tok in niche_keyword_set if tok in content}
            return (len(matched) >= 2, matched)

        winners_pre_filter = len(winners)
        advertisers_pre_filter = len(advertisers)
        winners = [
            {**w, 'niche_relevance_matched': sorted(matched)}
            for w in winners
            for kept, matched in [_is_niche_relevant(w)]
            if kept
        ]
        advertisers = [
            {**a, 'niche_relevance_matched': sorted(matched)}
            for a in advertisers
            for kept, matched in [_is_niche_relevant(a)]
            if kept
        ]
        winners_dropped = winners_pre_filter - len(winners)
        advertisers_dropped = advertisers_pre_filter - len(advertisers)
        if winners_dropped or advertisers_dropped:
            logger.info(
                f"[meta-ads] niche-relevance filter dropped {winners_dropped} "
                f"winners and {advertisers_dropped} advertisers as off-niche "
                f"(requires 2+ niche keywords in page_name/URLs)"
            )

        # Extract keyword candidates from winners (preferred) or all
        # advertisers if no winners cleared the heuristic.
        seed_pool = winners or advertisers[:10]
        keywords: list[str] = []
        for adv in seed_pool[:10]:
            name = (adv.get('page_name') or '').strip()
            if name:
                tokens = [
                    t for t in name.split()
                    if len(t) > 2 and t.lower() not in {
                        'the', 'and', 'shop', 'store', 'co', 'inc',
                        'llc', 'ltd',
                    }
                ]
                if tokens:
                    keywords.append(' '.join(tokens[:3]))

        # Direction from aggregate ad count.
        if total_ad_count == 0:
            direction = 'UNKNOWN'
        elif total_ad_count >= 25:
            direction = 'RISING'
        elif total_ad_count >= 5:
            direction = 'STABLE'
        else:
            direction = 'FALLING'

        # Stash structured data on the engine for the scoring pass.
        self._meta_winners_cache = {
            'niche': niche,
            'sub_queries_run': sub_queries,
            'per_query_stats': per_query_stats,
            'winners': winners,
            'advertisers': advertisers,
            'ad_count': total_ad_count,
            'fetched_at': datetime.now().isoformat(),
            # Task #9: niche-filter transparency
            'niche_filter': {
                'keyword_set': sorted(niche_keyword_set),
                'winners_dropped': winners_dropped,
                'advertisers_dropped': advertisers_dropped,
                'winners_kept': len(winners),
            },
        }

        logger.info(
            f"[meta-ads] aggregated {len(winners)} unique winners, "
            f"{len(advertisers)} unique advertisers, {total_ad_count} total ads "
            f"across {len(sub_queries)} sub-queries"
        )

        return {
            'keywords': keywords,
            'trend_direction': direction,
            'source': 'meta_ads',
            'ad_count': total_ad_count,
            'winner_count': len(winners),
            'sub_query_count': len(sub_queries),
        }

    async def _fetch_amazon_movers_rss(self, niche: str) -> dict:
        """
        Task #12: Amazon Movers & Shakers RSS as a winner-proof source.

        Amazon's public RSS feed lists the products with the biggest
        24-hour sales-rank gains per category. Velocity leaders =
        actively gaining momentum NOW. Free, no auth, no quota.

        Strategy: pull the top 20 movers for the niche's Amazon
        category, extract the head noun-phrase from each title as a
        trending-keyword candidate, and stash the raw items on the
        engine so the scoring pass can fuzzy-match products against
        the rising rank list (Phase 2 — Task #15).

        Returns the same {keywords, trend_direction, source} shape as
        `_fetch_google_trends` so the merge loop in
        `_get_trending_keywords` treats it identically.

        Trend direction interpretation:
          - Items found  → RISING (movers feed is, by definition,
            ranked by upward velocity)
          - No items     → UNKNOWN (niche has no clean Amazon mapping
            or the feed temporarily failed)
        """
        scraper = getattr(self, "amazon_movers_rss", None)
        if scraper is None:
            return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'amazon_movers'}

        try:
            payload = await scraper.fetch(niche, max_items=20)
        except Exception as e:
            logger.debug(f"Amazon Movers RSS fetch failed: {e}")
            return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'amazon_movers'}

        if not payload.get("available"):
            return {
                'keywords': [],
                'trend_direction': 'UNKNOWN',
                'source': 'amazon_movers',
                'error': payload.get("error"),
            }

        keywords = scraper.extract_keywords(payload, top_n=8)

        # Stash the structured movers list on the engine so the scoring
        # pass can read it. Same pattern as `_meta_winners_cache`.
        self._amazon_movers_cache = {
            'niche': niche,
            'category': payload.get("category"),
            'items': payload.get("items") or [],
            'item_count': payload.get("item_count", 0),
            'fetched_at': payload.get("fetched_at"),
        }

        return {
            'keywords': keywords,
            'trend_direction': 'RISING' if keywords else 'UNKNOWN',
            'source': 'amazon_movers',
            'item_count': payload.get("item_count", 0),
        }

    async def _fetch_amazon_new_releases_rss(self, niche: str) -> dict:
        """
        Option A: Amazon New Releases RSS — products launched in the
        last 30 days for the niche category.

        Different from Movers in *what* it surfaces:
          - Movers: products gaining sales rank (could be old products
            spiking due to a viral moment)
          - New Releases: products that didn't exist a month ago
            (genuine first-mover opportunities, by definition
            un-saturated since competitors haven't even seen them yet)

        Same connector and same parse path as the movers fetcher; just
        a different feed_type. Returns the standard (keywords,
        trend_direction, source) shape.
        """
        scraper = getattr(self, "amazon_movers_rss", None)
        if scraper is None:
            return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'amazon_new_releases'}

        try:
            payload = await scraper.fetch(niche, feed_type="new_releases", max_items=20)
        except Exception as e:
            logger.debug(f"Amazon New Releases RSS fetch failed: {e}")
            return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'amazon_new_releases'}

        if not payload.get("available"):
            return {
                'keywords': [],
                'trend_direction': 'UNKNOWN',
                'source': 'amazon_new_releases',
                'error': payload.get("error"),
            }

        keywords = scraper.extract_keywords(payload, top_n=8)

        # Stash items so the scoring pass can read them later
        self._amazon_new_releases_cache = {
            'niche': niche,
            'category': payload.get("category"),
            'items': payload.get("items") or [],
            'item_count': payload.get("item_count", 0),
            'fetched_at': payload.get("fetched_at"),
        }

        # New releases are by definition early-stage = RISING
        return {
            'keywords': keywords,
            'trend_direction': 'RISING' if keywords else 'UNKNOWN',
            'source': 'amazon_new_releases',
            'item_count': payload.get("item_count", 0),
        }

    async def _fetch_etsy_trending(self, niche: str) -> dict:
        """
        Option B: Etsy trending products as a supplementary signal.

        Etsy is strong for handmade / lifestyle niches (home decor,
        jewelry, beauty accessories) where Amazon's bestseller signal
        is weak. The connector maps Ospra niches → Etsy categories and
        returns trending product titles as keyword seeds.

        Niches without a clean Etsy mapping (tech, fitness, gaming)
        return UNKNOWN with no error — they just skip Etsy quietly.
        Same {keywords, trend_direction, source} shape as the other
        trend tasks so the merge loop treats it identically.
        """
        scraper = getattr(self, "etsy_trending", None)
        if scraper is None:
            return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'etsy'}

        try:
            payload = await scraper.fetch_trending(niche, max_items=20)
        except Exception as e:
            logger.debug(f"Etsy trending fetch failed: {e}")
            return {'keywords': [], 'trend_direction': 'UNKNOWN', 'source': 'etsy'}

        if not payload.get("available"):
            # `no_etsy_category_for_niche` is expected for many niches —
            # log it at debug, not warning.
            err = payload.get("error")
            if err == "no_etsy_category_for_niche":
                logger.debug(f"Etsy skipped for niche '{niche}' (no mapping)")
            return {
                'keywords': [],
                'trend_direction': 'UNKNOWN',
                'source': 'etsy',
                'error': err,
            }

        keywords = scraper.extract_keywords(payload, top_n=8)

        # Stash items so the scoring pass can read them later
        self._etsy_trending_cache = {
            'niche': niche,
            'category': payload.get("category"),
            'items': payload.get("items") or [],
            'item_count': payload.get("item_count", 0),
        }

        return {
            'keywords': keywords,
            'trend_direction': 'RISING' if keywords else 'UNKNOWN',
            'source': 'etsy',
            'item_count': payload.get("item_count", 0),
        }

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
                # PRICE FIELDS — empirically verified from AE affiliate API
                # debug output (May 2026). What each field actually means:
                #
                #   target_sale_price       — AFFILIATE-PROMOTED PRICE.
                #                             What customers pay if they
                #                             arrive via an affiliate link.
                #                             ~35-45% off the AE retail.
                #                             NOT what the dropshipper pays
                #                             when fulfilling, because AE
                #                             ToS forbids self-referral.
                #   target_original_price   — INFLATED MSRP / marketing
                #                             baseline. Almost always
                #                             higher than the actual
                #                             consumer-facing retail.
                #   target_app_sale_price   — Same as target_sale_price in
                #                             observed data.
                #
                # The CONSUMER-FACING RETAIL PRICE (what AE shows visitors
                # at AE.com without an affiliate link) IS NOT EXPOSED in
                # any field of the affiliate API response. It's calculated
                # dynamically by AE based on user state.
                #
                # Heuristic: estimated_retail = affiliate_price × 1.65,
                # capped at MSRP. Empirically AE's affiliate discount is
                # 35-45% off retail. For the Tuya bulb sample:
                #   $5.33 × 1.65 = $8.79 ≈ AE-shown retail of $8.98 ✓
                #
                # This is a SHORT-TERM heuristic. The real fix is wiring
                # the AE DS API (Task #24, get_hot_products in
                # api/aliexpress_product_routes.py) which returns explicit
                # merchant prices. Until that lands, the heuristic gives
                # us numbers that are approximately right for product
                # economics decisions.
                affiliate_price_str = item.get('target_sale_price', '0')
                msrp_str = item.get('target_original_price', '0')

                affiliate_price = float(affiliate_price_str) if affiliate_price_str else 0
                msrp_price = float(msrp_str) if msrp_str else 0
                if affiliate_price == 0:
                    continue

                # Estimated retail = the customer-facing price the user's
                # buyers would pay if they bought direct on AE. Used as
                # the cost basis until AE DS API gives us the real merchant
                # price. Capped at MSRP so we never overshoot the inflated
                # marketing baseline. Floored at affiliate_price so we
                # don't undershoot known data.
                _retail_estimate = min(msrp_price or affiliate_price * 2.0, affiliate_price * 1.65)
                cost_price = max(affiliate_price, round(_retail_estimate, 2))

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
                
                # original_price = the AE strikethrough MSRP. Used only for
                # showing the "Save $X" badge in the product card, NOT as
                # the cost basis. AE marketing inflates this number, so the
                # discount % computed from it is mostly theatrical — but
                # users still expect to see it.
                original_price = msrp_price if msrp_price > cost_price else cost_price

                # discount_pct displays AE's marketing % off. Capped at 90%
                # to avoid 100% artifacts when MSRP is suspiciously high.
                discount_pct = 0
                if msrp_price > cost_price and msrp_price > 0:
                    discount_pct = min(90, round(((msrp_price - cost_price) / msrp_price) * 100, 0))

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
                    # PRICING
                    # cost_price = HEURISTIC estimate of consumer-facing
                    # AE retail (affiliate_price × 1.65, capped at MSRP).
                    # The real fulfillment cost depends on the merchant's
                    # AE Choice membership tier. Will be replaced with
                    # explicit merchant price from AE DS API (Task #24).
                    "cost_price": cost_price,
                    "supplier_cost": cost_price,
                    # affiliate_price = what customers pay via affiliate
                    # link. Surfaced for transparency but NOT used as cost.
                    "affiliate_price": affiliate_price,
                    "msrp": msrp_price,            # AE strikethrough/MSRP
                    "cost_basis": "heuristic_retail_estimate",  # vs "ae_ds_merchant" later
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

        # Intake relevance (#55): reject results that don't match the keyword
        # that found them (AE sometimes returns promoted/loosely-related items).
        return self._filter_supplier_results(products, query=keyword)

    async def _fetch_cj(self, keyword: str, count: int, niche: str = None) -> List[Dict]:
        """Fetch from CJ Dropshipping using smart search with keyword mappings.

        Strategy (May 2026 — Task #31 stopgap):

        After the May 11 diagnostic showed CJ category 1489 ("smart_home")
        returns 0 products (CJ rotated the ID without notice), we no longer
        rely on the CATEGORY_MAP. We go straight to keyword search using
        the FIRST entry from NICHE_KEYWORDS — which the live test confirmed
        returns 5 products for "wifi smart plug" and similar.

        Order of operations:
        1. If an explicit keyword is passed, use it (legacy callers).
        2. Otherwise pull NICHE_KEYWORDS[niche][0] as the search term.
        3. Fall back to category search as a LAST resort when no keyword
           and no niche keyword list.

        All CJ calls share a serialized lock (client.py step A), so this
        is bounded to ~6s per CJ source.

        Future fix (Task #31 phase 2): query CJ's /category endpoint live
        to refresh CATEGORY_MAP, then re-enable category-first lookups.
        """
        products = []

        try:
            results = []

            # Pick a search term. Caller's explicit keyword wins; otherwise
            # use the first niche keyword which we know returns products.
            search_keyword = keyword
            if not search_keyword and niche:
                niche_keywords = self.NICHE_KEYWORDS.get(niche, [])
                if niche_keywords:
                    search_keyword = niche_keywords[0]

            # Step 1: Keyword search (now the primary path).
            if search_keyword:
                logger.info(
                    f"   [INFO] CJ: keyword search for '{search_keyword}' "
                    f"(niche={niche}, page_size={count})"
                )
                results = await self.cj_client.smart_search(search_keyword, page_size=count)
                logger.info(f"   [INFO] CJ: keyword search returned {len(results)} products")

            # Step 2: Category fallback (last resort — usually empty due to
            # stale CATEGORY_MAP, but kept for niches with no NICHE_KEYWORDS).
            if not results and niche:
                logger.info(f"   [INFO] CJ: keyword empty, trying category for '{niche}'")
                results = await self.cj_client.search_by_niche(niche, page_size=count)
                logger.info(f"   [INFO] CJ: category search returned {len(results)} products")

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
                # [CJ_DIAGNOSTIC] Improved logging — when CJ returns nothing,
                # surface enough context to distinguish "token broken" from
                # "no inventory for this niche". Helps debug when discovery
                # silently drops CJ from the result mix.
                client_available = bool(getattr(self, 'cj_available', False))
                token_present = bool(
                    os.getenv('CJ_ACCESS_TOKEN') or os.getenv('OUBONSHOP_CJ_ACCESS_TOKEN')
                )
                category_mapped = bool(niche and getattr(self, 'cj_client', None)
                                       and niche in getattr(self.cj_client, 'CATEGORY_MAP', {}))
                logger.warning(
                    f"   [WARNING] CJ: 0 products. "
                    f"keyword={keyword!r} niche={niche!r} | "
                    f"client_available={client_available} token_present={token_present} "
                    f"category_mapped={category_mapped}"
                )

        except Exception as e:
            logger.error(f"[ERROR] CJ fetch error: {e}", exc_info=True)

        # Intake relevance (#55): CJ is a category-only search (no keyword),
        # so filter by niche relevance to drop products the broad category
        # pulled in that don't belong (e.g. basin waste under a "home" tree).
        return self._filter_supplier_results(products, query=keyword or "", niche=niche or "")

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

        # CJ visibility logging — surface what happened to CJ products
        # at INFO level. Was DEBUG, which was invisible in default uvicorn
        # logs and made the "where did the CJ products go" mystery hard
        # to debug. Task #31.
        cj_matched_count = len(matched_cj_ids)
        cj_unmatched_count = len(cj_products) - cj_matched_count
        if cj_products:
            logger.info(
                f"   [CJ MERGE] {len(cj_products)} CJ products → "
                f"{cj_matched_count} merged into AE products, "
                f"{cj_unmatched_count} kept as CJ-only"
            )

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

    # =========================================================================
    # CROSS-SOURCE MATCHING (Task #30)
    # =========================================================================
    # Meta Ad Library tells us *which products are paying for their ad spend
    # right now* (the winner-heuristic: 14+ days active × 3+ creative variants
    # × Shopify landing). That's the strongest market signal Ospra has.
    #
    # But the AE search returns products by keyword query — there's no
    # automatic link between "Scentify is winning on Meta" and "this AE
    # aromatherapy diffuser is the same product type." Without that link,
    # the AE product gets ranked purely on AE-internal signals (velocity,
    # rating, buzz) and the Meta winner data sits unused.
    #
    # This module bridges that gap. It builds a keyword index from the
    # cached Meta winners' landing URLs (Shopify slug paths almost always
    # contain product-type tokens — "aroma-diffuser", "portable-charger",
    # "magnetic-wallet"). Then each AE product's title is tokenised and
    # matched against the index. A match boosts the product's trend_score
    # and sets trend_source = 'meta_winner_match'.
    #
    # This is the minimum-viable cross-source matcher. Future work
    # (embedding similarity, supplier-side image matching) is in Task #14.
    # =========================================================================

    # Stopword set for keyword extraction — strip generic e-commerce noise
    # so the matcher operates on product-type tokens. Expanded May 2026
    # (Task #34) after the GlowRight matcher mistakenly hit car halo-ring
    # AE products via overlap on {halo, lights}: "lights" is too generic
    # to anchor a match. Added product-category generics, WH-question
    # words from URL slugs ("why-halo-lux" → drop "why"), and pronouns.
    _MATCH_STOPWORDS = frozenset({
        # standard English stopwords
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'have', 'in', 'is', 'it', 'of', 'on', 'or', 'that', 'the',
        'to', 'was', 'were', 'with', 'we', 'you', 'they', 'this', 'these',
        'those', 'our', 'their', 'your', 'all', 'any', 'one', 'two',
        # WH-words (common in marketing-page slugs like /why-product-x)
        'why', 'how', 'what', 'when', 'where', 'who', 'which',
        # e-commerce noise
        'shop', 'store', 'official', 'best', 'new', 'buy', 'get', 'sale',
        'free', 'shipping', 'usa', 'us', 'co', 'inc', 'llc', 'ltd',
        # product modifiers (too generic to anchor a match)
        'pro', 'plus', 'mini', 'max', 'set', 'pcs', 'pack', 'inch', 'cm',
        'mm', 'kit', 'app', 'wifi', 'led', 'usb', 'rgb', 'smart',
        'wireless', 'rechargeable', 'portable', 'compact', 'premium',
        # product-category generics — these caused the GlowRight false
        # positive. They appear in titles for many unrelated categories
        # (car halo lights ≠ smart-home halo lights). Removing them
        # forces the matcher to anchor on more specific product nouns.
        'light', 'lights', 'lamp', 'lamps', 'device', 'gear', 'item',
        'product', 'products', 'page', 'pages', 'home', 'collection',
        # Task #2 (round 3): marketing/quality words that appear in
        # Shopify URL slugs without contributing product-type info.
        # Houdini Holster yielded [breakout, built, concealment, copy,
        # holster, maximum] — "built/maximum/breakout/copy" come from
        # slugs like /products/copy-of-foo, /pages/built-for-X, etc.
        'copy', 'built', 'build', 'breakout', 'maximum', 'ultimate', 'ultra',
        'mega', 'super', 'best', 'top', 'original', 'classic',
        'signature', 'essential', 'elite', 'advanced', 'professional',
        'standard', 'basic', 'deluxe', 'supreme', 'designed', 'crafted',
        'made', 'perfect', 'amazing', 'great', 'special', 'unique',
        'genuine', 'real', 'true', 'pure', 'fine', 'high', 'low',
        # Caught in the Scentify/WYBOT/GlowRight slugs — marketing
        # filler that surfaces as keywords but never matches AE titles
        'bundle', 'full', 'different', 'dif', 'experience', 'introducing',
        'meet', 'love', 'must', 'have', 'need', 'want',
        # action / decision words (common in Shopify CTAs and pages)
        'buy', 'order', 'learn', 'explore', 'discover', 'try',
        'about', 'contact', 'support', 'help', 'guide', 'reviews',
    })

    def _extract_meta_winner_index(self) -> Dict[str, Dict[str, Any]]:
        """Build a {page_id: {keywords, max_days, variants, page_name}} index
        from the engine's cached Meta winners.

        Pulls keywords from each advertiser's sample landing URL slugs —
        Shopify product URLs (`/products/<slug>`, `/pages/<slug>`,
        `/collections/<slug>`) almost always carry the product type in
        the slug. Falls back to page_name tokens if no slug keywords
        are extractable.

        Returns an empty dict when no winner cache exists — caller treats
        that as "no Meta signal" and skips the boost.
        """
        cache = getattr(self, '_meta_winners_cache', None) or {}
        winners = cache.get('winners') or []
        advertisers = cache.get('advertisers') or []

        # Prefer explicit winners (passed the proven-winner heuristic).
        # If none yet, fall back to the top advertisers by ad_count — still
        # better signal than nothing, with the understanding that the
        # match score below will be moderated by max_days_active / variants
        # so weak advertisers don't get the same boost as winners.
        seed = winners or advertisers[:5]

        index: Dict[str, Dict[str, Any]] = {}
        for adv in seed:
            page_id = (
                adv.get('page_id')
                or adv.get('page_name')
                or adv.get('pageId')
                or ''
            )
            if not page_id:
                continue

            # Primary source: Shopify-style slugs in sample_landing_urls.
            # These are the most product-specific keywords we have — a
            # URL slug like "/products/aroma-diffuser-pro" reliably
            # describes the product type, not the brand.
            #
            # Task #6: track keywords PER SLUG, not as a flat union.
            # Multi-product brands (Wyze, Anker) ship multiple SKUs from
            # different product slugs (/wyze-bulb, /wyze-cam-v3). Unioning
            # the keywords makes the matcher require BOTH "bulb" AND "cam"
            # in one AE title — impossible because no single AE clone is
            # both a bulb AND a camera. Tracking per-slug lets the matcher
            # check overlap against ONE slug at a time.
            slug_keyword_groups: list[set] = []
            slug_keywords_union: set = set()  # for legacy callers
            for url in adv.get('sample_landing_urls') or []:
                if not isinstance(url, str):
                    continue
                u = url.lower()
                slug_tokens: set = set()
                for marker in ('/products/', '/product/', '/pages/', '/collections/'):
                    if marker in u:
                        tail = u.split(marker, 1)[1]
                        slug = tail.split('?', 1)[0].split('#', 1)[0].split('/', 1)[0]
                        for tok in slug.replace('-', ' ').replace('_', ' ').split():
                            tok = ''.join(c for c in tok if c.isalnum())
                            if (
                                len(tok) >= 3
                                and tok not in self._MATCH_STOPWORDS
                                and not tok.isdigit()
                            ):
                                slug_tokens.add(tok)
                        break
                if slug_tokens:
                    slug_keyword_groups.append(slug_tokens)
                    slug_keywords_union |= slug_tokens

            # Task #34: don't seed brand names from page_name unless
            # they also appear in a slug — gates brand contamination
            # for matcher use. But we ALSO collect the page_name's
            # distinctive token separately as a "brand fast-path" hint —
            # if an AE title contains the brand name verbatim, that's
            # a 1-token but highly specific match (Task #6 fast-path).
            confirmed_page_tokens: set = set()
            brand_tokens: set = set()
            for tok in (adv.get('page_name') or '').lower().split():
                tok = ''.join(c for c in tok if c.isalnum())
                if (
                    len(tok) >= 4
                    and tok not in self._MATCH_STOPWORDS
                    and not tok.isdigit()
                ):
                    if tok in slug_keywords_union:
                        confirmed_page_tokens.add(tok)
                    # Always collect for the brand fast-path, even if
                    # the slug didn't confirm it.
                    brand_tokens.add(tok)

            if not slug_keywords_union and not brand_tokens:
                continue

            # The legacy `keywords` field stays the flat union for any
            # callers that still iterate it (e.g. the keyword-extraction
            # path in _fetch_meta_ads_trends).
            keywords = slug_keywords_union | confirmed_page_tokens

            index[str(page_id)] = {
                'keywords': keywords,
                'slug_keyword_groups': slug_keyword_groups,
                'brand_tokens': brand_tokens,
                'max_days': int(adv.get('max_days_active') or 0),
                'variants': int(adv.get('variant_count') or 0),
                'page_name': adv.get('page_name') or '',
                'has_shopify': bool(adv.get('has_shopify_landing')),
                'sample_url': (adv.get('sample_landing_urls') or [None])[0],
            }

        return index

    def _collect_winner_candidates(
        self,
        niche: str,
        max_per_source: int = 5,
    ) -> List[Dict[str, Any]]:
        """Winner-first restructure (per CLAUDE.md "social sentiment FIRST" rule).

        Reads the four winner-proof caches that _get_trending_keywords already
        populated as a side effect, and produces a normalized list of winner
        candidates that discover_products() can fan out to AE+CJ for sourcing.

        Each cache is a side-effect of an existing _fetch_* method:
          - self._meta_winners_cache       <- _fetch_meta_ads_trends
          - self._tiktok_shop_cache        <- _fetch_tiktok_shop_trends
          - self._amazon_movers_cache      <- _fetch_amazon_movers_rss
          - self._etsy_trending_cache      <- _fetch_etsy_trending

        We never refetch — Step 1 already paid the I/O cost in parallel.
        This is pure cache aggregation in-process.

        Returns at most max_per_source winners per source, normalized to:
            {
                'source': 'meta_ads' | 'tiktok_shop' | 'amazon_movers' | 'etsy',
                'name':   <human-readable winner name>,
                'brand_tokens':       [str, ...],   # for AE brand-pass query
                'slug_keyword_groups':[[str, ...], ...],  # for AE slug-pass query
                'signal_strength':    float,         # 0-1, source-normalized
                'metadata':           {<source-specific extras>},
            }

        Empty list = no winners surfaced; discover_products() falls back to
        the legacy keyword-based search path.
        """
        candidates: List[Dict[str, Any]] = []

        # ── 1. Meta Ad Library winners ──────────────────────────────────
        # Use the existing index extractor — it's the same logic the old
        # /winners route consumed, so behavior is identical between the
        # retired endpoint and the new winner-first /quick flow.
        try:
            meta_index = self._extract_meta_winner_index()
            # Prefer the strict-winners list, fall back to advertisers
            # (mirrors the old /winners endpoint's soft-winners fallback).
            meta_cache = getattr(self, '_meta_winners_cache', None) or {}
            strict_winners = meta_cache.get('winners') or []
            # Strength: strict-winner = 1.0 (passed the 14d × 3-variants ×
            # Shopify-landing heuristic), advertiser-fallback = 0.6.
            strict_page_ids = {
                str(w.get('page_id') or w.get('page_name') or '')
                for w in strict_winners
            }
            for page_id, entry in list(meta_index.items())[:max_per_source]:
                slug_groups = entry.get('slug_keyword_groups') or []
                brand_tokens = sorted(entry.get('brand_tokens') or set())
                if not slug_groups and not brand_tokens:
                    continue
                candidates.append({
                    'source': 'meta_ads',
                    'name': entry.get('page_name') or page_id,
                    'page_id': page_id,
                    'brand_tokens': brand_tokens,
                    'slug_keyword_groups': [sorted(g) for g in slug_groups],
                    'signal_strength': 1.0 if page_id in strict_page_ids else 0.6,
                    'metadata': {
                        'max_days_active': entry.get('max_days', 0),
                        'variant_count': entry.get('variants', 0),
                        'has_shopify': entry.get('has_shopify', False),
                        'sample_url': entry.get('sample_url'),
                    },
                })
        except Exception as e:
            logger.warning(f"[winners] meta candidate extraction failed: {e}")

        # ── 2. TikTok Shop winners ──────────────────────────────────────
        # Cache shape: {normalized_name: {units_sold_7d, views_7d, ...}}.
        # Rank by units_sold_7d (first-party purchase signal). Names are
        # already lowercased and whitespace-normalized — fine for AE search
        # which is case-insensitive.
        try:
            ts_cache = getattr(self, '_tiktok_shop_cache', None) or {}
            if ts_cache:
                ranked = sorted(
                    ts_cache.items(),
                    key=lambda kv: int(kv[1].get('units_sold_7d') or 0),
                    reverse=True,
                )[:max_per_source]
                # Normalize signal_strength by max units in this batch so
                # we get a 0-1 range. Single-product batches collapse to 1.0.
                max_units = max(
                    (int(v.get('units_sold_7d') or 0) for _, v in ranked),
                    default=1,
                ) or 1
                for name, data in ranked:
                    units = int(data.get('units_sold_7d') or 0)
                    if units <= 0:
                        continue
                    tokens = [
                        t for t in name.split()
                        if len(t) >= 3
                        and t not in self._MATCH_STOPWORDS
                        and t.isalpha()
                    ]
                    if not tokens:
                        continue
                    candidates.append({
                        'source': 'tiktok_shop',
                        'name': name,
                        'brand_tokens': [],  # TikTok Shop products are mostly genericized
                        'slug_keyword_groups': [tokens[:4]],
                        'signal_strength': round(units / max_units, 3),
                        'metadata': {
                            'units_sold_7d': units,
                            'views_7d': int(data.get('views_7d') or 0),
                            'velocity_score': data.get('velocity_score', 0),
                            'product_url': data.get('product_url'),
                        },
                    })
        except Exception as e:
            logger.warning(f"[winners] tiktok_shop candidate extraction failed: {e}")

        # ── 3. Amazon Movers winners ────────────────────────────────────
        # Cache shape: {items: [{title, asin, product_url, bestseller_rank, ...}]}.
        # Lower bestseller_rank = higher signal (rank 1 is the top mover).
        try:
            mv_cache = getattr(self, '_amazon_movers_cache', None) or {}
            items = mv_cache.get('items') or []
            # Sort by rank ascending (1, 2, 3...). Items without rank go last.
            ranked = sorted(
                items,
                key=lambda it: int(it.get('bestseller_rank') or 9999),
            )[:max_per_source]
            for idx, item in enumerate(ranked):
                title = (item.get('title') or '').strip()
                if not title:
                    continue
                tokens = [
                    t.lower() for t in title.split()
                    if len(t) >= 3
                    and t.lower() not in self._MATCH_STOPWORDS
                    and t.isalpha()
                ]
                if not tokens:
                    continue
                # Strength decays with position in the movers list.
                strength = round(max(0.4, 1.0 - (idx * 0.15)), 3)
                candidates.append({
                    'source': 'amazon_movers',
                    'name': title[:120],
                    'brand_tokens': [],
                    'slug_keyword_groups': [tokens[:4]],
                    'signal_strength': strength,
                    'metadata': {
                        'asin': item.get('asin'),
                        'product_url': item.get('product_url'),
                        'bestseller_rank': item.get('bestseller_rank'),
                        'rating': item.get('rating'),
                        'reviews_count': item.get('reviews_count'),
                    },
                })
        except Exception as e:
            logger.warning(f"[winners] amazon_movers candidate extraction failed: {e}")

        # ── 4. Etsy trending winners ────────────────────────────────────
        # Cache shape: {items: [{title, url, category, ...}]}.
        # Etsy doesn't expose rank-delta consistently — use list position
        # as the relative-strength proxy (top items > tail items).
        try:
            etsy_cache = getattr(self, '_etsy_trending_cache', None) or {}
            items = etsy_cache.get('items') or []
            for idx, item in enumerate(items[:max_per_source]):
                title = (item.get('title') or '').strip()
                if not title:
                    continue
                tokens = [
                    t.lower() for t in title.split()
                    if len(t) >= 3
                    and t.lower() not in self._MATCH_STOPWORDS
                    and t.isalpha()
                ]
                if not tokens:
                    continue
                strength = round(max(0.3, 0.8 - (idx * 0.1)), 3)
                candidates.append({
                    'source': 'etsy',
                    'name': title[:120],
                    'brand_tokens': [],
                    'slug_keyword_groups': [tokens[:4]],
                    'signal_strength': strength,
                    'metadata': {
                        'product_url': item.get('url'),
                        'category': item.get('category'),
                    },
                })
        except Exception as e:
            logger.warning(f"[winners] etsy candidate extraction failed: {e}")

        # ── 5. Amazon New Releases winners ──────────────────────────────
        # Cache shape: {items: [{title, asin, product_url, bestseller_rank, ...}]}.
        # Same shape as _amazon_movers_cache. New Releases = products
        # launched in last 30d — by definition early-stage / un-saturated,
        # so signal_strength stays high across the head of the list.
        try:
            nr_cache = getattr(self, '_amazon_new_releases_cache', None) or {}
            items = nr_cache.get('items') or []
            ranked = sorted(
                items,
                key=lambda it: int(it.get('bestseller_rank') or 9999),
            )[:max_per_source]
            for idx, item in enumerate(ranked):
                title = (item.get('title') or '').strip()
                if not title:
                    continue
                tokens = [
                    t.lower() for t in title.split()
                    if len(t) >= 3
                    and t.lower() not in self._MATCH_STOPWORDS
                    and t.isalpha()
                ]
                if not tokens:
                    continue
                # Decay slower than movers (new releases stay high-signal
                # deeper into the list since each is genuinely new).
                strength = round(max(0.5, 1.0 - (idx * 0.10)), 3)
                candidates.append({
                    'source': 'amazon_new_releases',
                    'name': title[:120],
                    'brand_tokens': [],
                    'slug_keyword_groups': [tokens[:4]],
                    'signal_strength': strength,
                    'metadata': {
                        'asin': item.get('asin'),
                        'product_url': item.get('product_url'),
                        'bestseller_rank': item.get('bestseller_rank'),
                        'rating': item.get('rating'),
                        'reviews_count': item.get('reviews_count'),
                    },
                })
        except Exception as e:
            logger.warning(f"[winners] amazon_new_releases candidate extraction failed: {e}")

        if candidates:
            by_source: Dict[str, int] = {}
            for c in candidates:
                by_source[c['source']] = by_source.get(c['source'], 0) + 1
            logger.info(
                f"[winners] collected {len(candidates)} candidates "
                f"across {len(by_source)} sources: {by_source}"
            )
        else:
            logger.info(
                "[winners] no winner candidates surfaced — discover_products "
                "will fall back to keyword-based AE/CJ search"
            )

        return candidates

    async def _source_winners_to_products(
        self,
        winners: List[Dict[str, Any]],
        niche: str,
        ae_per_winner: int = 3,
        cj_per_winner: int = 3,
    ) -> List[Dict]:
        """Fan out N winners to AE + CJ supplier searches IN PARALLEL.

        For each winner, runs the same two-pass (brand → slug-keyword) AE
        search the retired /winners route used, plus a CJ keyword search.
        Returns a flat list of supplier products, each tagged with the
        winner that surfaced it (so the self-learning loop sees better
        attribution than "came from keyword").

        Caller is discover_products() — this replaces the legacy Step 2
        keyword-based supplier loop when winner candidates are available.
        """
        if not winners:
            return []

        import time as _time
        sourcing_start = _time.time()

        niche_context = niche.replace('_', ' ').strip() if niche else ''
        # Cap how many supplier tasks fly in parallel. N winners × 2 suppliers
        # = 2N tasks; with 10 winners that's 20 concurrent Apify/AE/CJ calls.
        # The per-source timeout cap keeps the wall-clock bounded regardless.
        max_winners = min(len(winners), 10)
        winners = winners[:max_winners]

        async def _source_one(winner: Dict[str, Any]) -> List[Dict]:
            """AE (brand→slug fallback) + CJ for one winner, in parallel."""
            local_products: List[Dict] = []
            brand_tokens = winner.get('brand_tokens') or []
            slug_groups = winner.get('slug_keyword_groups') or []

            # Build candidate queries. Brand first (specific), slug second
            # (catches generic alternatives when the brand isn't on AE).
            candidate_queries: List[tuple[str, str]] = []  # (label, query)
            if brand_tokens:
                brand_q = (
                    f"{niche_context} {brand_tokens[0]}".strip()
                    if niche_context else brand_tokens[0]
                )
                candidate_queries.append(('brand', brand_q))
            if slug_groups:
                # First slug group — usually the primary product type.
                # Strip brand tokens so we don't repeat the brand search.
                first_slug = slug_groups[0]
                non_brand = [t for t in first_slug if t not in brand_tokens]
                if non_brand:
                    slug_q = (
                        f"{niche_context} {' '.join(non_brand[:3])}".strip()
                        if niche_context else ' '.join(non_brand[:3])
                    )
                    candidate_queries.append(('slug', slug_q))

            if not candidate_queries:
                return []

            # AE: try brand pass first, only fall through to slug if brand
            # came back empty. CJ: single query against the slug (or brand
            # if no slug) — CJ doesn't benefit from the brand-pass split.
            ae_query = candidate_queries[0][1]
            cj_query = candidate_queries[-1][1]  # prefer slug for CJ

            ae_task = self._fetch_aliexpress(
                ae_query,
                count=max(ae_per_winner * 3, 10),
            ) if (self.aliexpress_available and ae_per_winner > 0) else None

            cj_task = self._fetch_cj(
                keyword=cj_query,
                count=max(cj_per_winner * 3, 10),
                niche=niche,
            ) if (self.cj_available and cj_per_winner > 0) else None

            ae_results: List = []
            cj_results: List = []
            tasks = []
            task_labels = []
            if ae_task is not None:
                tasks.append(_with_timeout(ae_task, SUPPLIER_SOURCE_TIMEOUT))
                task_labels.append('ae')
            if cj_task is not None:
                tasks.append(_with_timeout(cj_task, SUPPLIER_SOURCE_TIMEOUT))
                task_labels.append('cj')

            if not tasks:
                return []

            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.warning(
                    f"[winners] sourcing failed for '{winner.get('name')}': {e}"
                )
                return []

            for label, result in zip(task_labels, results):
                if isinstance(result, (Exception, asyncio.TimeoutError)):
                    continue
                if not result:
                    continue
                if label == 'ae':
                    ae_results = result[:ae_per_winner]
                else:
                    cj_results = result[:cj_per_winner]

            # AE brand-pass fallback: if brand returned nothing AND we
            # have a slug query queued, run it now.
            if not ae_results and len(candidate_queries) > 1 and self.aliexpress_available:
                slug_q = candidate_queries[1][1]
                try:
                    fallback = await asyncio.wait_for(
                        self._fetch_aliexpress(slug_q, count=max(ae_per_winner * 3, 10)),
                        timeout=SUPPLIER_SOURCE_TIMEOUT,
                    )
                    ae_results = (fallback or [])[:ae_per_winner]
                except Exception:
                    pass

            # Tag each supplier product with the winner that surfaced it.
            # This is what gives the self-learning loop better attribution
            # than the old keyword-based path.
            #
            # IMPORTANT: do NOT overwrite p['source']. That field is a
            # routing key used by ~6 downstream filters
            # (`source == 'aliexpress'` / `'cj_dropshipping'`) — overwriting
            # it caused winner-tagged products to silently fail price
            # enrichment, hit the wrong score floor, and get culled at
            # the quota-split step. Attribution lives on `winner_source`
            # (the surfacing winner-source name) and `winner_provenance`
            # (the rich metadata blob). The literal `source` stays as
            # whatever _fetch_aliexpress / _fetch_cj set it to.
            winner_meta = {
                'source_winner': winner.get('source'),
                'source_winner_name': winner.get('name'),
                'source_winner_strength': winner.get('signal_strength'),
            }
            for p in ae_results:
                p = dict(p)
                p['winner_source'] = winner.get('source')
                p['winner_provenance'] = winner_meta
                local_products.append(p)
            for p in cj_results:
                p = dict(p)
                p['winner_source'] = winner.get('source')
                p['winner_provenance'] = winner_meta
                local_products.append(p)

            return local_products

        # Fan out all winners in parallel — sourcing N winners is N×2
        # independent supplier calls, which gather() runs concurrently.
        logger.info(
            f"[winners] sourcing {len(winners)} winners "
            f"({len(winners) * 2} parallel supplier calls max)..."
        )
        per_winner_results = await asyncio.gather(
            *[_source_one(w) for w in winners],
            return_exceptions=True,
        )

        # Flatten + drop exceptions.
        all_products: List[Dict] = []
        for r in per_winner_results:
            if isinstance(r, Exception):
                logger.debug(f"[winners] one winner sourcing raised: {r}")
                continue
            if r:
                all_products.extend(r)

        logger.info(
            f"[winners] sourced {len(all_products)} products from "
            f"{len(winners)} winners in {_time.time() - sourcing_start:.2f}s"
        )
        return all_products

    def _match_product_to_meta_winners(
        self,
        product_title: str,
    ) -> tuple[int, Optional[Dict[str, Any]]]:
        """Score one product's title against the cached Meta winner index.

        Returns (best_match_score, best_winner_meta) — score is 0-100 and
        winner_meta is None when no match cleared the threshold. The
        scoring loop uses both: the score becomes the new trend_score
        when it beats the current value, the winner_meta is stamped on
        the product as `meta_winner_match` for UI/debug.

        Threshold: at least 2 shared product-type tokens. Single-token
        overlaps would match too aggressively (a "diffuser" hit on the
        word "smart" alone would boost every AE smart-anything product).

        Score formula:
          base       = 50 + (shared_tokens * 15)   # 2 shared → 80, 3 → 95
          age_bonus  = min(20, max_days_active / 2) # 14d → +7, 40d → +20
          var_bonus  = min(15, variants * 2)        # 3 variants → +6, 8+ → +15
          total      = min(100, base + age_bonus + var_bonus)

        Cached on the instance so the index isn't rebuilt for every
        product in the loop.
        """
        if not product_title:
            return 0, None

        # Lazy cache the winner index — built once per _calculate_scores call.
        # We clear it at the start of every _calculate_scores so each fresh
        # discovery run rebuilds against current cache.
        index = getattr(self, '_winner_index_cached', None)
        if index is None:
            return 0, None
        if not index:
            return 0, None

        # Tokenise the title
        title_tokens: set = set()
        for tok in product_title.lower().split():
            tok = ''.join(c for c in tok if c.isalnum())
            if (
                len(tok) >= 3
                and tok not in self._MATCH_STOPWORDS
                and not tok.isdigit()
            ):
                title_tokens.add(tok)

        if not title_tokens:
            return 0, None

        best_score = 0
        best_winner: Optional[Dict[str, Any]] = None
        for page_id, winner in index.items():
            # Task #6: try matches in three tiers, strongest first.
            # 1. Per-slug overlap (best signal — title actually
            #    matches a specific product the winner sells)
            # 2. Brand-name fast-path (title contains brand verbatim,
            #    1-token match but high specificity)
            # 3. Legacy union overlap fallback (kept for backward compat
            #    with pre-#6 keyword sets that lack slug grouping)

            best_match_type = None
            best_match_tokens: set = set()

            # Tier 1: per-slug overlap. ALWAYS require 2-token overlap
            # — the per-slug grouping (vs the legacy union) is what
            # makes this safe for multi-product brands like Wyze, NOT
            # a loosened threshold. Wyze slugs are e.g. [bulb, wyze] /
            # [cam, wyze]; a generic Tuya bulb only overlaps `bulb`
            # (not a Wyze knockoff), but "Wyze Cam Knockoff Security
            # Camera" overlaps {wyze, cam} from the second slug → match.
            #
            # The brand fast-path (tier 2 below) is the dedicated path
            # for "title contains brand name only" — that's a 1-token
            # but highly specific match, gated by length+specificity
            # of the brand token itself.
            for slug_keywords in winner.get('slug_keyword_groups') or []:
                if not slug_keywords or len(slug_keywords) < 2:
                    continue
                slug_overlap = title_tokens & slug_keywords
                if len(slug_overlap) >= 2:
                    if len(slug_overlap) > len(best_match_tokens):
                        best_match_tokens = slug_overlap
                        best_match_type = 'slug'

            # Tier 2: brand-name fast-path. If the AE title contains
            # one of the winner's brand tokens (e.g. "wyze"), that's
            # a single-token but highly specific signal — brand names
            # are typically not generic dictionary words.
            if not best_match_tokens:
                brand_overlap = title_tokens & winner.get('brand_tokens', set())
                if brand_overlap:
                    best_match_tokens = brand_overlap
                    best_match_type = 'brand'

            # Tier 3: legacy union overlap (only if Tier 1+2 missed
            # AND the winner has the legacy `keywords` set populated).
            if not best_match_tokens:
                union_overlap = title_tokens & winner.get('keywords', set())
                if len(union_overlap) >= 2:
                    best_match_tokens = union_overlap
                    best_match_type = 'union'

            if not best_match_tokens:
                continue

            # Score: base from match strength, bonuses from winner quality
            base = 50 + len(best_match_tokens) * 15
            age_bonus = min(20, winner['max_days'] // 2)
            var_bonus = min(15, winner['variants'] * 2)
            total = min(100, base + age_bonus + var_bonus)

            if total > best_score:
                best_score = total
                best_winner = {
                    'page_id': page_id,
                    'page_name': winner['page_name'],
                    'matched_keywords': sorted(best_match_tokens),
                    'match_type': best_match_type,  # slug | brand | union
                    'max_days_active': winner['max_days'],
                    'variant_count': winner['variants'],
                    'sample_url': winner.get('sample_url'),
                    'match_score': total,
                }

        return best_score, best_winner

    # =========================================================================
    # SEMANTIC WINNER MATCHING (Task #3) — Haiku-based
    # =========================================================================
    # The keyword-overlap matcher (above) was the right MVP — fast, cheap,
    # explainable — but it's whack-a-mole. Polysemous tokens like "halo"
    # match car headlight rings; "lights" matches everything; brand names
    # like "Wyze" require manual stopword tuning. The architectural fix is
    # semantic matching: ask an LLM "is this AE product a credible
    # alternative to this Meta winner?".
    #
    # Implementation: batched Haiku call PER WINNER (1 call scores all
    # N AE candidates for that winner). ~200ms per call × 6 winners = ~1.2s
    # added latency; ~$0.0001 per call. Caches per (winner_page_id,
    # title_hash) so re-runs within the cache TTL are free.
    #
    # Falls back to (0, 'unavailable') when ANTHROPIC_API_KEY isn't set or
    # the call fails — caller should detect this and use the keyword
    # matcher as fallback.
    # =========================================================================

    _semantic_match_cache: Dict[str, tuple] = {}  # key -> (score, reason)

    async def _semantic_match_winner_to_candidates(
        self,
        winner: Dict[str, Any],
        ae_titles: List[str],
    ) -> List[Tuple[int, str]]:
        """Score each AE title's relevance to the winner via Claude Haiku.

        Returns a list of (score 0-100, reason) tuples in the same order
        as `ae_titles`. Empty input → empty output. Returns all-zero
        scores with reason='unavailable' if the AI client isn't set up.
        """
        if not ae_titles:
            return []

        # Cache lookup for already-evaluated (winner, title) pairs
        import hashlib as _hashlib
        winner_key = str(winner.get('page_id') or winner.get('page_name') or '')

        def _cache_key(title: str) -> str:
            return f"{winner_key}::" + _hashlib.md5(title.encode()).hexdigest()[:16]

        # Compute uncached entries
        results: list[Optional[Tuple[int, str]]] = [None] * len(ae_titles)
        uncached_indices: list[int] = []
        uncached_titles: list[str] = []
        for i, title in enumerate(ae_titles):
            cached = self._semantic_match_cache.get(_cache_key(title))
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_titles.append(title)

        # If everything was cached, return early
        if not uncached_titles:
            return [r for r in results if r is not None]

        # Build prompt and call Haiku
        try:
            page_name = winner.get('page_name') or '(unnamed)'
            sample_url = (
                winner.get('sample_landing_urls') or [None]
            )[0] if isinstance(winner.get('sample_landing_urls'), list) else None
            keywords_str = ', '.join(sorted(winner.get('extracted_keywords') or winner.get('keywords') or [])[:8])

            numbered_candidates = '\n'.join(
                f"{i+1}. {t[:200]}" for i, t in enumerate(uncached_titles)
            )

            system_prompt = (
                "You evaluate AliExpress product candidates against a Meta Ad Library "
                "winner brand to determine if the AE product is a credible alternative, "
                "knockoff, or generic equivalent of what the winner sells. Reply with a "
                "JSON array — one entry per candidate — and no other prose."
            )

            user_prompt = (
                f"WINNER BRAND: {page_name}\n"
                f"LANDING URL: {sample_url or '(none)'}\n"
                f"PRODUCT KEYWORDS: {keywords_str or '(none)'}\n\n"
                f"ALIEXPRESS CANDIDATES:\n{numbered_candidates}\n\n"
                "For each candidate, score 0-100 how likely it is a credible alternative "
                "or knockoff of the winner's product:\n"
                "- 80-100: Clear alternative or knockoff (same product type and use case)\n"
                "- 50-79: Same broad category but different positioning\n"
                "- 0-49:  Different category or wrong product type\n\n"
                "Reply with a JSON array exactly like this, no other text:\n"
                '[{"i": 1, "s": 95, "r": "Direct Wyze cam clone"}, '
                '{"i": 2, "s": 25, "r": "Off-category"}]'
            )

            from ospra_os.ml.ai_client import UnifiedAIClient
            from ospra_os.ml.model_router import ModelTier
            client = UnifiedAIClient()
            ai_resp = await asyncio.to_thread(
                client.generate,
                prompt=user_prompt,
                task_type='general',
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=1200,
                force_tier=ModelTier.LOCAL_FREE,  # prefer cheap; falls back if unavailable
            )

            content = (ai_resp.content or '').strip()
            # Strip code fences if present
            if content.startswith('```'):
                content = content.strip('`')
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()

            import json
            parsed = json.loads(content)
            if not isinstance(parsed, list):
                raise ValueError(f"expected JSON array, got {type(parsed).__name__}")

            # Map parsed results back to uncached indices
            by_i = {int(e.get('i', 0)): e for e in parsed if isinstance(e, dict)}
            for offset, orig_idx in enumerate(uncached_indices):
                e = by_i.get(offset + 1)  # 1-indexed in prompt
                if e:
                    score = max(0, min(100, int(e.get('s', 0))))
                    reason = str(e.get('r', ''))[:120]
                else:
                    score, reason = 0, 'no_response'
                pair = (score, reason)
                results[orig_idx] = pair
                # Cache for next call
                self._semantic_match_cache[_cache_key(uncached_titles[offset])] = pair

        except Exception as exc:
            logger.warning(f"[semantic-match] Haiku call failed: {exc}")
            # Fill remaining unresolved with zeros so the caller knows
            # to fall back to keyword matcher
            for orig_idx in uncached_indices:
                if results[orig_idx] is None:
                    results[orig_idx] = (0, 'unavailable')

        # Convert Optional list to concrete
        return [r if r is not None else (0, 'error') for r in results]

    # =========================================================================
    # SELF-LEARNING PHASE 2 (Task #12) — load learned weights at scoring time
    # =========================================================================
    # The LearningProcessor + daily_feedback_loop write to NicheLearning and
    # GlobalLearningWeights based on actual outcome data (predicted vs real
    # success). Discovery had been ignoring those updates — engine hardcoded
    # ranking weights, so learnings were effectively dropped on the floor.
    # This adds a lightweight read-back: per discovery run, look up the
    # learned multiplier for the niche and apply it in scoring.
    #
    # Cached for 10 min so we don't hit the DB per-product. Gracefully
    # returns 0 (no adjustment) when no learning data exists yet — keeps
    # behavior identical to pre-Phase-2 on cold installs.
    # =========================================================================

    _learned_adjustment_cache: Dict[str, Tuple[float, float]] = {}  # key -> (expires_at, adjustment)
    _LEARNED_ADJUSTMENT_TTL_SECONDS = 600

    # =========================================================================
    # SELF-LEARNING PHASE 5C — per-signal weight multipliers
    # =========================================================================
    # NicheLearning gives us per-niche multiplier. GlobalLearningWeights
    # has per-SIGNAL weights (e.g. "meta_winner_match" might learn it's a
    # better predictor than "amazon_buzz" → its score contribution gets
    # weighted higher in oi_score). This reads them and exposes a lookup.
    # =========================================================================
    _signal_weights_cache: Tuple[float, Dict[str, float]] = (0.0, {})  # (expires_at, weights)

    def _get_learned_signal_weights(self) -> Dict[str, float]:
        """Return a dict of {signal_name: weight_multiplier} from the most
        recent GlobalLearningWeights row. Cached 10 min. Empty dict = no
        learning data yet → caller uses default uniform weights (1.0 each).

        Multiplier semantics: 1.0 = no change; 1.20 = boost signal 20%;
        0.80 = suppress 20%. Bounded ±50% to prevent any single signal
        from dominating after one bad data window.
        """
        import time as _time
        expires_at, cached_weights = self._signal_weights_cache
        if expires_at > _time.time():
            return cached_weights

        try:
            from ospra_os.database import get_session
            from ospra_os.database.performance_models import GlobalLearningWeights
            with next(get_session()) as db:
                row = (
                    db.query(GlobalLearningWeights)
                    .order_by(GlobalLearningWeights.updated_at.desc())
                    .first()
                )
                if row and row.scoring_weights:
                    raw = row.scoring_weights or {}
                    # Sanitize: only keep numeric values, clip to [0.5, 1.5]
                    weights = {}
                    for k, v in raw.items():
                        try:
                            w = float(v)
                            if w > 0:
                                weights[str(k)] = max(0.5, min(1.5, w))
                        except (TypeError, ValueError):
                            continue
                else:
                    weights = {}
        except Exception as exc:
            logger.debug(f"[learning-read] signal weights fetch failed: {exc}")
            weights = {}

        self._signal_weights_cache = (
            _time.time() + 600,  # 10 min TTL
            weights,
        )
        return weights

    def _apply_signal_weight(self, signal_name: str, contribution: float) -> float:
        """Convenience: apply learned multiplier to a signal contribution.
        Returns contribution unchanged if no learning data for this signal."""
        weights = self._get_learned_signal_weights()
        mult = weights.get(signal_name, 1.0)
        return contribution * mult

    def _get_learned_niche_adjustment(self, niche: Optional[str]) -> float:
        """Return the learned score multiplier delta for `niche`, e.g.
        +10 means apply a 1.10× multiplier; -5 means 0.95×. Returns 0.0
        when no learning data exists for the niche yet.

        Reads from NicheLearning (global row, user_id NULL) — personalized
        per-user adjustments are a future enhancement.
        """
        if not niche:
            return 0.0
        import time as _time
        cache_key = niche.lower()
        cached = self._learned_adjustment_cache.get(cache_key)
        if cached and cached[0] > _time.time():
            return cached[1]

        try:
            from ospra_os.database import get_session
            from ospra_os.database.performance_models import NicheLearning
            with next(get_session()) as db:
                row = (
                    db.query(NicheLearning)
                    .filter(NicheLearning.niche == niche.lower())
                    .filter(NicheLearning.user_id.is_(None))  # global only for now
                    .first()
                )
                adjustment = float(row.niche_score_adjustment) if row else 0.0
        except Exception as exc:
            logger.debug(f"[learning-read] failed to fetch niche adjustment for {niche}: {exc}")
            adjustment = 0.0

        self._learned_adjustment_cache[cache_key] = (
            _time.time() + self._LEARNED_ADJUSTMENT_TTL_SECONDS,
            adjustment,
        )
        return adjustment

    def _calculate_scores(
        self,
        products: List[Dict],
        *,
        category_niche: Optional[str] = None,
    ) -> List[Dict]:
        """
        Calculate OI Score with cross-reference bonus.

        Components:
        - Demand (25%): Sales, BSR, views
        - Trend (25%): Google Trends, virality
        - Sentiment (15%): Twitter + Reddit
        - Profit (15%): Margin percentage
        - Sourcing (20%): Cross-reference bonus, warehouse advantage

        Args:
          products: list of product dicts to score in-place.
          category_niche: the user-facing niche (e.g. "smart_home") from
            the discovery API call. Used as a fallback in
            `_calculate_relevance` when a product's per-product `niche`
            field (set to the specific search keyword that found it,
            e.g. "LED strip lights RGB") doesn't have a RELEVANCE_KEYWORDS
            entry. Without this, every product silently scores 70 via
            the generic word-overlap path.

        IMPORTANT: This builds score_breakdown dict for AI analyzer compatibility
        """
        # Task #30: build the Meta winner keyword index once per scoring pass.
        # _match_product_to_meta_winners reads `_winner_index_cached` so each
        # product in the loop does a cheap set-intersect rather than rebuilding
        # the index N times. Cache is invalidated on every call.
        self._winner_index_cached = self._extract_meta_winner_index()
        if self._winner_index_cached:
            logger.info(
                f"[meta-match] indexed {len(self._winner_index_cached)} Meta "
                f"winner(s) for cross-source matching"
            )

        # Task #9 Phase 2: direct saturation measure. Read the Meta
        # advertiser count from the cache so _compute_saturation can use
        # it without taking a self reference. Stamped on every product
        # below so the (module-level) saturation function can read it
        # via product.get(...). Falls back to 0 when Meta data wasn't
        # collected — _compute_saturation then skips this signal.
        meta_cache = getattr(self, "_meta_winners_cache", None) or {}
        meta_niche_advertiser_count = len(meta_cache.get("advertisers") or [])
        if meta_niche_advertiser_count > 0:
            logger.info(
                f"[meta-saturation] niche has {meta_niche_advertiser_count} "
                f"active advertisers — feeding into saturation scoring"
            )
        for product in products:
            data_sources = product.get('data_sources', {})

            # Stamp the niche-level Meta advertiser count so the
            # (module-level) _compute_saturation can read it.
            # Task #9 Phase 2 — direct market-crowding measure.
            if meta_niche_advertiser_count > 0:
                product['meta_niche_advertiser_count'] = meta_niche_advertiser_count

            # ================================================================
            # RELEVANCE CHECK - Filter off-topic products
            # ================================================================
            niche = product.get('niche', '').lower()
            title = product.get('title', '').lower()
            relevance_score = self._calculate_relevance(
                title, niche, category_niche=category_niche,
            )
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

            # Task #30: Cross-source matching — Meta Ad Library winners.
            # If this AE product looks like a product someone is paying real
            # money to scale on Meta right now, that's a stronger signal
            # than any AE-internal heuristic. We replace trend_score with
            # the match score when it's higher than what we have so far,
            # and stamp trend_source so downstream consumers know the
            # signal came from cross-source matching (not Google / TikTok
            # / AE velocity).
            meta_match_score, meta_match_meta = self._match_product_to_meta_winners(
                product.get('title', '')
            )
            if meta_match_score > 0:
                if meta_match_score > trend_score:
                    trend_score = meta_match_score
                has_trend_signal = True
                product['trend_source'] = 'meta_winner_match'
                product['meta_winner_match'] = meta_match_meta

            # AliExpress velocity — Western-trend fallback. Mirror of the
            # AE-buyer sentiment fallback: when no Western trend signal
            # (Google Trends / TikTok / Twitter buzz) fires, fall back to
            # AE buzz_score / recent_sales as a velocity proxy.
            #
            # Two-tier gating after audit Apr 2026 showed only 3/67
            # products cleared the original "buzz>50 AND recent>1000"
            # threshold. Most AE products have buzz in the 30-60 range
            # because the buzz_score is a composite — a product with 200
            # recent sales but no buzz_score still shouldn't score null.
            #
            # STRONG gate: buzz>50 AND recent>1000 → score 30 + buzz*0.5
            #              (premium velocity — this is genuine momentum)
            # WEAK gate:   recent>200 OR (buzz>30 AND recent>50)
            #              → score capped at 60, scaled with sales
            #              (sub-1k recent or modest buzz — we have a
            #              velocity signal but not a strong one)
            #
            # Cap at 80 STRONG / 60 WEAK: we have velocity but no
            # direction. Western signals remain the only path to 90+.
            if not has_trend_signal:
                ae_buzz_for_trend = float(ae_signals.get('buzz_score') or 0)
                ae_recent_for_trend = int(ae_signals.get('recent_sales') or 0)
                if ae_buzz_for_trend > 50 and ae_recent_for_trend > 1000:
                    trend_score = min(80, 30 + ae_buzz_for_trend * 0.5)
                    has_trend_signal = True
                    product['trend_source'] = 'aliexpress_velocity_strong'
                elif ae_recent_for_trend > 200 or (ae_buzz_for_trend > 30 and ae_recent_for_trend > 50):
                    # Map sales count to a 0-30 lift, capped at 60 total.
                    # 50 sales → +10, 200 → +18, 500 → +22, 2k+ → +30.
                    import math as _m
                    sales_lift = min(30, _m.log10(1 + ae_recent_for_trend) * 8)
                    trend_score = min(60, 30 + sales_lift)
                    has_trend_signal = True
                    product['trend_source'] = 'aliexpress_velocity_weak'

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

            # Supplier rating bonus (IMPROVED thresholds).
            # Task #23 (May 2026): also fall back to top-level
            # aliexpress_rating which is set by the AE normalizer (line
            # 2497ish) but wasn't being read here. That's why every
            # product showed supplier_rating=50 in score_breakdown —
            # both product.rating and ali_data.rating were 0 because the
            # rating lives on `aliexpress_rating`. ae_signals.rating_stars
            # is the same value from the data_sources path.
            supplier_rating = (
                product.get('rating', 0)
                or ali_data.get('rating', 0)
                or product.get('aliexpress_rating', 0)
                or ae_signals.get('rating_stars', 0)
                or 0
            )
            try:
                supplier_rating = float(supplier_rating)
            except (TypeError, ValueError):
                supplier_rating = 0.0
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
            # Task #25 (May 2026): google_trends and tiktok_viral now ONLY carry
            # values when the underlying source actually returned data. The old
            # behaviour wrote a composite `trend_score` (which could be derived
            # from AE velocity, Twitter buzz, etc.) into the google_trends slot
            # AND defaulted to 55 when no signal was available. Both behaviours
            # made it look like Google Trends or TikTok contributed to the score
            # when they hadn't. The composite `trend_score` is still reported at
            # the product level with `trend_source` indicating provenance — the
            # breakdown should reflect raw per-source contribution, not the
            # composite.
            # ================================================================
            product['score_breakdown'] = {
                'google_trends': (
                    min(100, 15 + google_trend_score * 0.85)
                    if google_trend_score > 0 else None
                ),
                'tiktok_viral': (
                    min(100, tiktok_views // 10000) if tiktok_views > 0 else None
                ),
                'twitter_sentiment': sentiment_score if has_twitter_signal else None,
                'aliexpress_orders': demand_score,
                # Task #18: Real Amazon data (rating × reviews) when we have it
                'amazon_buzz': int(amazon_buzz_raw) if has_amazon_signal else None,
                'amazon_rating': amazon_rating_raw,
                'amazon_reviews': amazon_review_count_raw if has_amazon_signal else None,
                'reddit_sentiment': min(100, 40 + reddit_mentions * 3) if reddit_mentions > 0 else None,
                # Task #25/#23: surfacing this as None when no real signal so the
                # caller can tell "no data" from "50/100 — confidently mediocre".
                # The hardcoded 50 default went out the door silently — every
                # product looked like it had a known-mediocre supplier when in
                # fact we'd never measured them. Replacing real per-supplier
                # scoring is Task #23 and lives in a follow-up commit.
                'supplier_rating': (
                    min(100, int(supplier_rating * 20)) if supplier_rating > 0 else None
                ),
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
                # Task #30: cross-source signal. Score reflects how well this
                # product matched a Meta winner (>=2 shared product-type tokens
                # required; bonus for advertiser age + variant count). None
                # when no match — caller distinguishes that from a 0 score.
                'meta_winner_match': (
                    meta_match_score if meta_match_score > 0 else None
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
            # Task #30: Meta winner match counts as a validated cross-source
            # signal — this product looks like something actively winning on
            # Meta ads right now.
            if meta_match_score > 0:
                sources_validated.append('meta_winner_match')

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
            # Phase 5C: apply learned per-signal weight multipliers to
            # the design weights. GlobalLearningWeights.scoring_weights is
            # a dict like {"demand": 1.10, "trend": 0.95, ...}. Defaults
            # to 1.0 (no change) when no learning data exists. This makes
            # the engine LEARN that some signals predict outcomes better
            # than others over time, instead of trusting hardcoded weights
            # forever.
            learned_signal_mults = self._get_learned_signal_weights()
            design_weights = {
                'demand': 0.25,
                'trend': 0.25,
                'sentiment': 0.15,
                'profit': 0.15,
                'sourcing': 0.20,
            }
            component_values = {
                'demand':    (design_weights['demand']    * learned_signal_mults.get('demand', 1.0),    demand_score    if has_demand_signal              else None),
                'trend':     (design_weights['trend']     * learned_signal_mults.get('trend', 1.0),     trend_score     if has_trend_signal               else None),
                'sentiment': (design_weights['sentiment'] * learned_signal_mults.get('sentiment', 1.0), sentiment_score if sentiment_score is not None    else None),
                'profit':    (design_weights['profit']    * learned_signal_mults.get('profit', 1.0),    profit_score),
                'sourcing':  (design_weights['sourcing']  * learned_signal_mults.get('sourcing', 1.0),  product['sourcing_score']),
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

            # ──────────────────────────────────────────────────────────────
            # ANTI-SATURATION DISCOUNT — the differentiator
            # ──────────────────────────────────────────────────────────────
            # Two products with identical demand+trend+sentiment can have
            # very different opportunity values. The one in an uncrowded
            # market (few competitors, rising trend, low ad density) is
            # worth chasing; the one in a saturated market is a money pit.
            #
            # Multiplier curve: oi *= (1 - saturation)^0.5
            #   sat 0.0 (uncrowded) → 1.00× (full credit)
            #   sat 0.3            → 0.84× (16% haircut)
            #   sat 0.5 (unknown)  → 0.71× (29% haircut — neutral default)
            #   sat 0.7 (crowded)  → 0.55× (45% haircut)
            #   sat 0.9 (saturated)→ 0.32× (68% haircut — push to bottom)
            #
            # The square-root softens the penalty so we don't over-punish
            # mid-saturation products while still meaningfully demoting
            # the truly crowded ones.
            #
            # Confidence-aware: if we don't have enough saturation data
            # (confidence < 0.3) we apply a NEUTRAL 1.0× multiplier — no
            # haircut for unknown saturation. Haircuts only fire on
            # MEASURED saturation.
            #
            # CALIBRATION (anti-double-counting, matches the authenticity
            # layer fix): the base score already penalizes missing signals
            # ONCE (absent components contribute zero weight). The previous
            # 0.85× low-confidence path was a second uncertainty haircut on
            # the same evidence gap, compressing thin-data products
            # unfairly. Absence of data is penalized at the base, not here.
            saturation_result = _compute_saturation(product)
            sat_score = saturation_result['score']
            sat_conf = saturation_result['confidence']

            if sat_conf >= 0.3:
                saturation_multiplier = (1.0 - sat_score) ** 0.5
            else:
                # Low-confidence path — NEUTRAL. Only measured saturation
                # earns a haircut.
                saturation_multiplier = 1.0

            oi_score = oi_score * saturation_multiplier

            # Persist on the product so the UI can show "saturation: HIGH
            # (12 Amazon clones, plateau trend)" alongside the score.
            product['saturation_score'] = sat_score
            product['saturation_confidence'] = sat_conf
            product['saturation_signals'] = saturation_result.get('signals', {})
            product['saturation_note'] = saturation_result.get('note')

            # ──────────────────────────────────────────────────────────────
            # DEMAND AUTHENTICITY — paid/promoted vs organic divergence check
            # ──────────────────────────────────────────────────────────────
            # Gated A/B toggle (DISCOVERY_AUTHENTICITY_ENABLED). Demote-only
            # (multiplier <= 1.0). Catches products with heavy promoted signal
            # (Meta ad winners, TikTok hype) but no corroborating organic
            # demand (Google Trends intent, Amazon reviews). See
            # ospra_os/intelligence/demand_authenticity.py docstring.
            if AUTHENTICITY_ENABLED:
                org, promo, n_org = signals_from_product(product)
                auth = compute_authenticity(
                    organic_strength=org,
                    promoted_strength=promo,
                    n_organic_sources=n_org,
                )
                oi_score = oi_score * auth.multiplier
                product['authenticity_score'] = auth.score
                product['authenticity_label'] = auth.label
                product['authenticity_divergence'] = auth.divergence_flag
                product['authenticity_reasons'] = auth.reasons

            # ──────────────────────────────────────────────────────────────
            # WINNER-STRENGTH BOOST
            # ──────────────────────────────────────────────────────────────
            # Compensates for missing sentiment signal on winner-sourced
            # products (especially CJ-only, which lack Amazon-reviews /
            # Twitter / AE-velocity signals that AE products accumulate).
            # The winner provenance IS the signal — a product matched to a
            # strict Meta winner (strength=1.0) deserves a real boost; a
            # loose match (0.6) gets a smaller one. Range 1.00 → 1.20×.
            wp = product.get('winner_provenance') or {}
            winner_strength = float(wp.get('source_winner_strength') or 0)
            if winner_strength > 0:
                winner_boost = 1.0 + 0.20 * winner_strength
                oi_score = oi_score * winner_boost
                product['winner_strength_boost'] = round(winner_boost, 3)

            # If product is clearly irrelevant, cap score at 45 (POOR tier)
            if relevance < 25:
                oi_score = min(oi_score, 45)
                product['relevance_note'] = f'Off-topic: Low relevance ({relevance}%) to niche'

            # Self-learning Phase 2: apply learned niche-level adjustment.
            # NicheLearning rows are updated by daily_feedback_loop based on
            # actual outcome data (predicted vs real success per niche). +10
            # means this niche has historically outperformed predictions →
            # boost. -10 means underperformed → suppress. Capped to ±25 so a
            # single bad week doesn't tank a niche.
            niche_adjustment = self._get_learned_niche_adjustment(category_niche)
            if niche_adjustment != 0:
                clipped_adj = max(-25.0, min(25.0, niche_adjustment))
                multiplier = 1.0 + (clipped_adj / 100.0)
                pre_adjustment = oi_score
                oi_score = oi_score * multiplier
                product['learned_niche_adjustment'] = round(clipped_adj, 2)
                product['oi_score_pre_learning'] = round(pre_adjustment, 1)

            product['oi_score'] = round(oi_score, 1)
            product['final_score'] = product['oi_score']
            product['base_score'] = round(base_score, 1)

            # Discovery-stage confidence (kept for backward-compat; counts
            # number of validated source connectors that ran).
            # Task #30: added meta_winner_match as a cross-source validation
            # signal, so the denominator is now 7 (was 6).
            max_sources = 7  # aliexpress, cj, twitter, reddit, google_trends, tiktok, meta_winner_match
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

    def _calculate_relevance(
        self,
        title: str,
        niche: str,
        *,
        category_niche: Optional[str] = None,
    ) -> float:
        """
        Calculate relevance score (0-100) for a product to its niche.

        Uses keyword matching to determine if a product is on-topic.
        Products that match 'exclude' keywords are penalized.
        Products that match 'include' keywords are rewarded.

        Resolution order for which RELEVANCE_KEYWORDS entry to use:
          1. The per-product `niche` field (e.g. "smart_home", "kitchen")
          2. If that doesn't have an entry, the `category_niche` fallback
             (the user-facing niche from the discovery API call). Most
             products carry the specific search keyword that found them
             as their niche — that keyword almost never has a config
             entry, so without the fallback every product hit the
             generic 70 default. Task #24.
          3. If neither has an entry, fall back to the generic
             word-overlap path (returns 50 or 70).

        Returns:
            0-100 relevance score
        """
        if not title:
            return 50  # Neutral if we can't determine
        if not niche and not category_niche:
            return 50

        title_lower = title.lower()

        # Try the per-product niche first (specific match), then the
        # category fallback. First entry to actually carry keywords wins.
        relevance_config: dict = {}
        for candidate in (niche, category_niche):
            if not candidate:
                continue
            cand_norm = candidate.lower().replace(' ', '_')
            cfg = self.RELEVANCE_KEYWORDS.get(cand_norm, {})
            if cfg.get('include'):
                relevance_config = cfg
                break

        include_keywords = relevance_config.get('include', [])
        exclude_keywords = relevance_config.get('exclude', [])

        # If neither niche nor category_niche had a config, use generic matching
        if not include_keywords:
            niche_words = set(
                (niche or category_niche or '').lower().replace('_', ' ').split()
            )
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
        # Base score of 30, +15 for each include match, -25 for each exclude match
        score = 30 + (include_matches * 15) - (exclude_matches * 25)

        # Clamp to 0-100
        return max(0, min(100, score))

    # =========================================================================
    # NICHE RELEVANCE GATE (Task #54)
    # =========================================================================
    # Words too generic to signal niche membership — present in many niches'
    # vocabularies, so matching on them alone lets off-topic products through.
    _GATE_STOPWORDS = frozenset({
        "the", "a", "an", "set", "with", "for", "and", "of", "to", "kit",
        "pack", "pcs", "pc", "new", "mini", "pro", "max", "plus", "smart",
        "wireless", "electric", "portable", "usb", "led",
        # location/descriptor words that appear in multi-word vocab entries
        # ("google home", "home decor") but are far too generic to signal
        # niche membership on their own.
        "home", "google", "fast", "thick", "large", "small",
    })

    # Generic, collision-prone niche-vocabulary tokens (#55). These words DO
    # belong to a niche's include set, but they appear on so many unrelated
    # products that a SINGLE one of them is not enough to claim niche
    # membership — e.g. "Universal Sink Plug" shares only "plug" with
    # smart_home, "Camping Lantern ... LED Tent Light" shares only "light".
    # A title matching ONLY one of these (and nothing stronger) must earn a
    # second signal (another matched token or a category match) to pass the
    # gate. Niche-specific tokens (thermostat/doorbell/vacuum/zigbee/…) are
    # NOT here, so a single strong token still passes on its own.
    # Kept deliberately narrow: only tokens that genuinely ride on unrelated
    # products. wifi/bulb/switch/sensor/remote/strip are NOT here — they are
    # specific enough that a single one (e.g. "Smart Bulb", "Smart Switch")
    # should still pass.
    _WEAK_NICHE_TOKENS = frozenset({
        "plug", "light", "lights", "lamp", "camera", "bluetooth", "speaker",
        "charger", "cable", "adapter", "holder", "mount", "screen", "display",
        "band",
    })

    def _niche_vocabulary(self, niche: str):
        """(include_tokens, exclude_tokens) for a niche, built once and cached.

        include tokens are the union of RELEVANCE_KEYWORDS['include'],
        NICHE_SUBQUERIES, and NICHE_KEYWORDS for the niche — the same
        vocabularies discovery already searches against — minus generic
        stopwords. exclude tokens come from RELEVANCE_KEYWORDS['exclude'].
        """
        norm = (niche or "").lower().replace(" ", "_")
        cache = getattr(self, "_niche_vocab_cache", None)
        if cache is None:
            cache = {}
            self._niche_vocab_cache = cache
        if norm in cache:
            return cache[norm]

        include = set()
        rel = self.RELEVANCE_KEYWORDS.get(norm, {})
        for kw in rel.get("include", []):
            include.update(kw.lower().split())
        for kw in self.NICHE_SUBQUERIES.get(norm, []):
            include.update(kw.lower().split())
        for kw in self.NICHE_KEYWORDS.get(norm, []):
            include.update(kw.lower().split())
        include -= self._GATE_STOPWORDS

        exclude = set()
        for kw in rel.get("exclude", []):
            exclude.update(kw.lower().split())

        result = (include, exclude)
        cache[norm] = result
        return result

    def _passes_niche_gate(self, product: Dict, requested_niche: str):
        """Decide whether a candidate belongs in the requested niche.

        Returns (passed: bool, reason: str). A candidate passes when its
        title (or category) shares meaningful vocabulary with the niche and
        doesn't hit an exclude term. Unknown niches (no vocabulary) are not
        gated. Toggle with DISCOVERY_RELEVANCE_GATE=false.
        """
        if os.getenv("DISCOVERY_RELEVANCE_GATE", "true").lower() != "true":
            return True, "gate_disabled"

        include_tokens, exclude_tokens = self._niche_vocabulary(requested_niche)
        if not include_tokens:
            return True, "no_vocab"  # unknown niche — don't gate blindly

        title = (product.get("title") or product.get("product_name") or "").lower()
        title_tokens = set(re.findall(r"[a-z0-9]+", title))

        # 1. Hard exclude (e.g. "pillow"/"blanket" in smart_home)
        if title_tokens & exclude_tokens:
            return False, "exclude_match"
        # 2. Title shares niche vocabulary. A niche-specific (strong) token,
        #    or two-plus matched tokens, is enough. A SINGLE generic/
        #    collision-prone token (plug/light/camera/…) is NOT — it must
        #    earn a category match below ("Universal Sink Plug" shares only
        #    "plug" with smart_home and should not pass on that alone).
        matched = title_tokens & include_tokens
        strong = matched - self._WEAK_NICHE_TOKENS
        if strong or len(matched) >= 2:
            return True, "vocab_match"
        # 3. Category shares niche vocabulary (titles are noisy; category helps)
        cat = (product.get("category_name") or product.get("category") or "").lower()
        if set(re.findall(r"[a-z0-9]+", cat)) & include_tokens:
            return True, "category_match"
        # 4. A lone generic token is enough IF the category corroborates that
        #    same token (substring catches singular/plural, e.g. title "Smart
        #    Plug" + category "Smart Plugs"). "Sink Plug" in "Bathroom
        #    Fittings" finds no corroboration and stays rejected.
        if matched and any(tok in cat for tok in matched):
            return True, "category_corroborated"
        # Nothing, or only a lone generic token with no supporting category.
        return False, "weak_or_no_overlap"

    def _apply_niche_gate(self, products: List[Dict], requested_niche: str) -> List[Dict]:
        """Filter a candidate pool to niche-relevant products, logging rejects.

        Safety valve: if the gate would remove EVERY candidate (likely an
        incomplete vocabulary for this niche, not 100% junk), it keeps the
        pool unfiltered and logs loudly — an empty discovery result is worse
        than a slightly-noisy one, and product discovery is priority #1.
        """
        kept, rejected = [], []
        for p in products:
            passed, reason = self._passes_niche_gate(p, requested_niche)
            (kept if passed else rejected).append((p, reason))

        if rejected:
            logger.info(
                f"   [RELEVANCE GATE] dropped {len(rejected)}/{len(products)} "
                f"off-niche candidates for '{requested_niche}'"
            )
            for p, reason in rejected[:15]:
                logger.info(f"      ✗ {(p.get('title') or p.get('product_name') or '?')[:60]} ({reason})")

        if not kept and products:
            logger.warning(
                f"   [RELEVANCE GATE] would have removed ALL {len(products)} candidates "
                f"for '{requested_niche}' — keeping pool unfiltered (vocabulary may need "
                f"expansion for this niche)"
            )
            return products

        return [p for p, _ in kept]

    # =========================================================================
    # SUPPLIER INTAKE RELEVANCE (Task #55)
    # =========================================================================
    # The candidate pool was full of off-niche junk (awnings, basin waste,
    # camping lanterns for smart_home) because the trend-keyword expansion
    # (Amazon Movers / Google rising-related / etc.) leaks off-niche terms
    # into the supplier search, and results were accepted with NO check that
    # they matched the query or niche. These intake filters make the pool
    # majority-relevant BEFORE the STEP-3b gate, so the gate trims edge cases
    # instead of doing demolition.

    def _title_overlaps_query(self, title: str, query: str) -> bool:
        """True if a supplier result title shares a meaningful token with the
        search keyword that found it. Rejects e.g. a "basin waste" result
        returned for the query "wifi smart plug". When the query has no
        meaningful tokens (e.g. a category-only CJ search), returns True —
        there's nothing to match against, so niche relevance is used instead.
        """
        q_tokens = {
            t for t in re.findall(r"[a-z0-9]+", (query or "").lower())
            if len(t) > 2 and t not in self._GATE_STOPWORDS
        }
        if not q_tokens:
            return True
        t_tokens = set(re.findall(r"[a-z0-9]+", (title or "").lower()))
        return bool(q_tokens & t_tokens)

    def _filter_supplier_results(
        self, products: List[Dict], *, query: str = "", niche: str = "",
    ) -> List[Dict]:
        """Reject off-niche/off-query supplier results at intake.

        Keyword searches (query set) require query-term overlap; category
        searches (no query) fall back to the niche relevance gate. Toggle with
        DISCOVERY_INTAKE_FILTER=false. Never empties a non-empty batch to zero
        on the niche-only path (defers to the STEP-3b safety valve), but the
        query-overlap path CAN drop everything — a keyword that returns 100%
        unrelated results SHOULD contribute nothing.
        """
        if os.getenv("DISCOVERY_INTAKE_FILTER", "true").lower() != "true":
            return products
        if not products:
            return products

        has_query = bool({
            t for t in re.findall(r"[a-z0-9]+", (query or "").lower())
            if len(t) > 2 and t not in self._GATE_STOPWORDS
        })

        kept, dropped = [], 0
        for p in products:
            title = p.get("title") or p.get("product_name") or ""
            if has_query:
                ok = self._title_overlaps_query(title, query)
            else:
                ok, _ = self._passes_niche_gate(p, niche)
            if ok:
                kept.append(p)
            else:
                dropped += 1

        if dropped:
            tag = f"query='{query[:24]}'" if has_query else f"niche='{niche}'"
            logger.info(f"   [INTAKE FILTER] dropped {dropped}/{len(products)} off-target results ({tag})")
        return kept

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
