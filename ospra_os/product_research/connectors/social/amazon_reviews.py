"""
Amazon Reviews as a Social Signal (via Apify)
=============================================

Why Amazon rather than just Reddit/Twitter?
-------------------------------------------
For a dropshipping store, the strongest validation signal is *other people
actually paying for this thing*. That's what Amazon's aggregate rating and
review count captures. Reddit/Twitter tell us about conversation; Amazon
tells us about purchase behavior.

Economic design
---------------
The naive approach would be "call Apify's Amazon search once per product"
(~15 actor runs per discovery @ $0.01-0.05 each = $0.50+). That's wasteful
because a single niche-level query already returns ~25 products that can be
fuzzy-matched against our supplier catalog.

So this connector runs **one** Amazon search per niche and exposes a
fuzzy-matching helper that lines up each of our supplier products with
the closest Amazon listing in the pool. Cost per discovery: ~$0.02-0.05.

Evidence shape
--------------
product['amazon_evidence'] = {
    'found_matches': bool,
    'match_count': int,
    'top_matches': [
        {
            'title': str,
            'rating': float,          # 0-5 Amazon stars
            'reviews_count': int,
            'price': float,
            'url': str,               # clickable Amazon listing
            'image_url': str,
            'asin': str,
            'bestseller_rank': int,
            'match_score': float,     # 0-1 title similarity to our product
        },
        ...
    ],
    'aggregate_rating': float,        # weighted avg across top_matches
    'total_reviews': int,             # sum across top_matches
    'buzz_score': float,              # rating * log(reviews) style score
    'niche_searched': str,
    'fetched_at': ISO8601 timestamp,
}

The frontend panel renders the top matches as clickable Amazon links so the
user can verify the signal is real. `buzz_score` feeds the OI sentiment
bucket alongside Twitter buzz and Reddit mentions.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# COST CONTROLS
# =============================================================================
# Apify's Amazon actor runs at ~$0.02-0.05 per query depending on max_items.
# Two guards keep spend bounded:
#   1. Per-niche in-memory cache with a TTL (default 2h). Niche-level market
#      signals don't shift fast enough to justify re-running every discovery.
#   2. Pre-flight budget check via ApifyClient.get_account_usage(). If the
#      remaining balance is below AMAZON_MIN_BUDGET_USD, we skip silently
#      with a clear log rather than burning down the last dollar.
# Env overrides let us tune or disable without a redeploy.
# =============================================================================
AMAZON_CACHE_TTL_SECONDS = int(os.getenv("AMAZON_CACHE_TTL_SECONDS", "7200"))  # 2h
AMAZON_MIN_BUDGET_USD = float(os.getenv("AMAZON_MIN_BUDGET_USD", "1.0"))
AMAZON_BUDGET_CHECK_ENABLED = os.getenv("AMAZON_BUDGET_CHECK_ENABLED", "1").lower() in (
    "1", "true", "yes",
)


# =============================================================================
# Token hygiene - keep this aligned with the reddit matcher so both signals
# agree on "what counts as a meaningful token from a product title".
# =============================================================================
_STOPWORDS = {
    "about", "above", "after", "again", "against", "also", "been", "before",
    "being", "below", "between", "both", "doing", "down", "during", "each",
    "from", "further", "have", "having", "here", "into", "itself", "just",
    "more", "most", "much", "must", "only", "other", "over", "same", "some",
    "such", "than", "that", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "under", "until", "very", "what", "when",
    "where", "which", "while", "with", "would", "your", "yours",
    # Marketing noise that floods Amazon titles and destroys match quality
    "premium", "quality", "professional", "ultimate", "perfect",
    "amazing", "incredible", "latest", "newest", "brand", "original",
    "authentic", "genuine", "certified", "bestseller", "popular",
    "piece", "pieces", "pack", "pcs", "set", "kit", "bundle", "assorted",
    "inch", "inches", "large", "medium", "small", "size", "sized",
    "black", "white", "silver", "gold", "color", "colors", "colour",
    "for", "the", "and", "with", "free", "new",
}


def _tokens(text: str) -> List[str]:
    """Extract normalized significant tokens from a title."""
    if not text:
        return []
    lowered = text.lower()
    # Keep alnum only, collapse punctuation into word boundaries
    parts = re.split(r"[^a-z0-9]+", lowered)
    return [
        t for t in parts
        if len(t) >= 3 and t not in _STOPWORDS and not t.isdigit()
    ]


def _title_similarity(a: str, b: str) -> float:
    """
    Hybrid similarity between two product titles in [0, 1].

    Blends Jaccard token overlap (robust to word order / extra filler) with
    a capped SequenceMatcher ratio (catches near-identical phrases). Pure
    SequenceMatcher gets fooled by Amazon's long keyword-stuffed titles
    where almost everything differs after the first few tokens; pure
    Jaccard misses when one title is a substring of the other.
    """
    if not a or not b:
        return 0.0

    toks_a = set(_tokens(a))
    toks_b = set(_tokens(b))
    if not toks_a or not toks_b:
        return 0.0

    overlap = toks_a & toks_b
    union = toks_a | toks_b
    jaccard = len(overlap) / len(union) if union else 0.0

    # SequenceMatcher on lowered originals for the phrase-level lift
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()

    # Weighted: token-overlap is the dominant signal, seq is a tiebreaker
    return round(0.75 * jaccard + 0.25 * seq, 4)


class AmazonReviewsConnector:
    """
    Niche-level Amazon review lookups via Apify.

    Usage:
        connector = AmazonReviewsConnector()
        if connector.is_available():
            pool = await connector.search_niche("smart home", max_items=25)
            for our_product in products:
                match = connector.match_products(our_product, pool, top_n=3)
                if match['found_matches']:
                    our_product['amazon_evidence'] = match
    """

    # Mapping from Ospra niche slugs to Amazon-friendly keywords. Without
    # this, searching literally for "smart_home" returns garbage.
    _NICHE_KEYWORD_MAP = {
        "smart_home": "smart home",
        "smart-home": "smart home",
        "smarthome": "smart home",
        "kitchen": "kitchen gadgets",
        "fitness": "fitness equipment",
        "beauty": "beauty gadgets",
        "tech": "tech gadgets",
        "pet": "pet supplies",
        "pets": "pet supplies",
        "gaming": "gaming accessories",
        "office": "office gadgets",
        "auto": "car accessories",
        "car": "car accessories",
        "outdoor": "outdoor gear",
        "baby": "baby products",
    }

    # Class-level cache shared across instances. Keyed by
    # (niche_keyword, max_items, min_rating) -> (timestamp, pool). One
    # discovery run per niche within the TTL window reuses the pool rather
    # than re-running the Apify actor.
    _pool_cache: Dict[Tuple[str, int, float], Tuple[float, List[Dict]]] = {}
    _budget_last_check: float = 0.0
    _budget_last_result: Optional[bool] = None
    _budget_check_lock = asyncio.Lock()

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("APIFY_API_TOKEN") or os.getenv("OUBONSHOP_APIFY_API_TOKEN")
        self._client = None
        self._last_error: Optional[str] = None

        if self.api_token:
            try:
                from ospra_os.product_research.connectors.apify.base_apify import ApifyClient
                self._client = ApifyClient(api_token=self.api_token)
            except Exception as exc:  # pragma: no cover - defensive
                self._last_error = f"ApifyClient init failed: {exc}"
                self._client = None

    # -------------------------------------------------------------------------
    # Availability
    # -------------------------------------------------------------------------
    def is_available(self) -> bool:
        return self._client is not None and self._client.is_available()

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    # -------------------------------------------------------------------------
    # Budget guard
    # -------------------------------------------------------------------------
    async def _check_budget(self) -> bool:
        """
        Return True if Apify has enough budget to safely run an Amazon query.

        Result is cached for 5 minutes to avoid hitting the usage endpoint
        every single discovery. On failure (network error, weird shape) we
        fail-open (return True) because the actor call itself will surface
        any real credential/billing issue.
        """
        if not AMAZON_BUDGET_CHECK_ENABLED:
            return True

        async with self._budget_check_lock:
            # Refresh at most every 5 minutes. Apify usage doesn't change in
            # seconds, so polling it repeatedly is wasteful.
            if (
                type(self)._budget_last_result is not None
                and time.time() - type(self)._budget_last_check < 300
            ):
                return type(self)._budget_last_result

            try:
                usage = await self._client.get_account_usage()
                remaining = float(usage.get("remaining_usd") or 0.0)
                can_run = bool(usage.get("can_run_paid_actors", True))
                ok = can_run and remaining >= AMAZON_MIN_BUDGET_USD
                type(self)._budget_last_check = time.time()
                type(self)._budget_last_result = ok
                if not ok:
                    logger.warning(
                        f"[AMAZON] Budget guard: remaining=${remaining:.2f} "
                        f"(min=${AMAZON_MIN_BUDGET_USD:.2f}, can_run={can_run}) - "
                        f"skipping Amazon enrichment"
                    )
                return ok
            except Exception as exc:
                logger.debug(f"[AMAZON] Budget check failed ({exc}) - failing open")
                return True

    @classmethod
    def clear_cache(cls) -> None:
        """Manual cache bust - used by tests and the /admin/refresh endpoint."""
        cls._pool_cache.clear()
        cls._budget_last_check = 0.0
        cls._budget_last_result = None

    # -------------------------------------------------------------------------
    # Niche-level Amazon search
    # -------------------------------------------------------------------------
    async def search_niche(
        self,
        niche: str,
        max_items: int = 25,
        min_rating: float = 3.5,
    ) -> List[Dict]:
        """
        Run ONE Amazon search for the whole niche. Returns a pool of
        candidate listings that `match_products` will fuzzy-match against.

        Uses a more permissive min_rating than the default (3.5 vs 4.0) so
        products with mixed reviews still appear in the pool - we want the
        evidence trail to be honest, not cherry-picked.
        """
        if not self.is_available():
            self._last_error = "Amazon reviews: APIFY_API_TOKEN not configured"
            return []

        keyword = self._NICHE_KEYWORD_MAP.get(niche.lower(), niche.replace("_", " "))
        cache_key = (keyword, max_items, min_rating)

        # -----------------------------------------------------------------
        # Cache lookup (cost control #1)
        # -----------------------------------------------------------------
        cached = type(self)._pool_cache.get(cache_key)
        if cached:
            cached_at, cached_pool = cached
            age = time.time() - cached_at
            if age < AMAZON_CACHE_TTL_SECONDS:
                logger.info(
                    f"[AMAZON] Cache hit for niche='{niche}' (age={age:.0f}s, "
                    f"TTL={AMAZON_CACHE_TTL_SECONDS}s, size={len(cached_pool)})"
                )
                # Return a shallow copy so per-run mutations can't poison the cache
                return [dict(row) for row in cached_pool]
            # Stale - fall through and re-fetch

        # -----------------------------------------------------------------
        # Budget guard (cost control #2)
        # -----------------------------------------------------------------
        if not await self._check_budget():
            self._last_error = "Amazon reviews: budget guard triggered"
            return []

        try:
            products = await self._client.search_amazon(
                keyword=keyword,
                max_items=max_items,
                min_rating=min_rating,
            )
        except Exception as exc:
            self._last_error = f"Amazon search failed for niche '{niche}': {exc}"
            return []

        # -----------------------------------------------------------------
        # Defensive field parsing - Apify actor outputs vary by version.
        # We accept the ApifyProduct shape (from search_amazon's parser) OR
        # raw dict rows with alternate field names we've seen in practice.
        # -----------------------------------------------------------------
        pool: List[Dict] = []
        rating_zero_count = 0
        for p in products:
            try:
                d = p.to_dict()
            except Exception:
                if isinstance(p, dict):
                    d = p
                else:
                    continue

            title = (
                d.get("name") or d.get("title") or d.get("productTitle") or ""
            ).strip()
            if not title:
                continue

            # Rating can appear as: rating, stars, starsCount, averageRating
            rating = 0.0
            for field in ("rating", "stars", "starsCount", "averageRating"):
                val = d.get(field)
                if val is not None:
                    try:
                        rating = float(val)
                        break
                    except (TypeError, ValueError):
                        continue

            # Review count: reviews_count, reviewsCount, numReviews, totalReviews
            reviews_count = 0
            for field in ("reviews_count", "reviewsCount", "numReviews", "totalReviews"):
                val = d.get(field)
                if val is not None:
                    try:
                        reviews_count = int(val)
                        break
                    except (TypeError, ValueError):
                        continue

            # Image: image_url, thumbnailImage, image, imageUrl
            image_url = ""
            for field in ("image_url", "thumbnailImage", "image", "imageUrl"):
                val = d.get(field)
                if val:
                    image_url = str(val)
                    break

            # Price parsing is forgiving - string with $, comma, or dict {value: X}
            price_raw = d.get("price", 0)
            price = 0.0
            try:
                if isinstance(price_raw, dict):
                    price = float(price_raw.get("value") or 0.0)
                elif isinstance(price_raw, str):
                    price = float(price_raw.replace("$", "").replace(",", "").strip() or 0)
                else:
                    price = float(price_raw or 0.0)
            except (TypeError, ValueError):
                price = 0.0

            if rating <= 0:
                rating_zero_count += 1

            pool.append({
                "title": title,
                "rating": rating,
                "reviews_count": reviews_count,
                "price": price,
                "url": d.get("url") or d.get("productUrl") or "",
                "image_url": image_url,
                "asin": d.get("asin") or "",
                "bestseller_rank": int(d.get("bestseller_rank") or d.get("bsr") or 0),
            })

        # Shape-drift warning: if we fetched a real pool but >50% have zero
        # ratings, the Apify actor likely changed its field names. This is
        # loud so we catch it before users see broken sentiment.
        if pool and rating_zero_count / len(pool) > 0.5:
            logger.warning(
                f"[AMAZON] Shape drift suspected: {rating_zero_count}/{len(pool)} "
                f"pool entries have rating=0 for niche='{niche}'. "
                f"Apify actor field names may have changed. "
                f"Sample keys in first row: {list(products[0].to_dict().keys()) if products else 'empty'}"
            )

        # Populate cache on success
        if pool:
            type(self)._pool_cache[cache_key] = (time.time(), [dict(row) for row in pool])

        return pool

    # -------------------------------------------------------------------------
    # Match a single supplier product against the niche pool
    # -------------------------------------------------------------------------
    def match_products(
        self,
        our_product: Dict,
        amazon_pool: List[Dict],
        top_n: int = 3,
        min_similarity: float = 0.20,
        niche: Optional[str] = None,
    ) -> Dict:
        """
        Fuzzy-match our supplier product against the Amazon pool and return
        an evidence dict suitable for persisting on the product.

        min_similarity=0.20 is intentionally lenient. Amazon listings are
        keyword-stuffed; requiring strict overlap drops too many legitimate
        matches. The `match_score` is exposed on each evidence row so the
        UI can visually indicate confidence.
        """
        our_title = our_product.get("title") or our_product.get("name") or ""
        now_iso = datetime.now(timezone.utc).isoformat()

        # Empty pool or empty title = honest empty evidence
        if not our_title or not amazon_pool:
            return {
                "found_matches": False,
                "match_count": 0,
                "top_matches": [],
                "aggregate_rating": None,
                "total_reviews": 0,
                "buzz_score": 0.0,
                "niche_searched": niche,
                "fetched_at": now_iso,
                "reason": "no_pool" if not amazon_pool else "no_title",
            }

        # Score every pool entry
        scored: List[Dict] = []
        for candidate in amazon_pool:
            sim = _title_similarity(our_title, candidate["title"])
            if sim >= min_similarity:
                scored.append({**candidate, "match_score": sim})

        if not scored:
            return {
                "found_matches": False,
                "match_count": 0,
                "top_matches": [],
                "aggregate_rating": None,
                "total_reviews": 0,
                "buzz_score": 0.0,
                "niche_searched": niche,
                "fetched_at": now_iso,
                "reason": "no_similar_listings",
            }

        # Sort by similarity (primary) then review_count (secondary):
        # popular listings win ties so we preference stronger social proof.
        scored.sort(
            key=lambda x: (-x["match_score"], -x["reviews_count"]),
        )
        top = scored[:top_n]

        # Aggregate signals weighted by review count (so 10k-review listings
        # dominate 50-review listings in the average - that's what we want
        # for a "is the market validating this" signal).
        total_reviews = sum(m["reviews_count"] for m in top)
        if total_reviews > 0:
            weighted_rating = sum(m["rating"] * m["reviews_count"] for m in top) / total_reviews
        else:
            # Fallback: simple avg of ratings when no review counts
            ratings = [m["rating"] for m in top if m["rating"] > 0]
            weighted_rating = sum(ratings) / len(ratings) if ratings else 0.0

        buzz_score = self._buzz_score(weighted_rating, total_reviews)

        return {
            "found_matches": True,
            "match_count": len(scored),
            "top_matches": top,
            "aggregate_rating": round(weighted_rating, 2),
            "total_reviews": total_reviews,
            "buzz_score": round(buzz_score, 2),
            "niche_searched": niche,
            "fetched_at": now_iso,
        }

    # -------------------------------------------------------------------------
    # Buzz score calculation
    # -------------------------------------------------------------------------
    @staticmethod
    def _buzz_score(rating: float, review_count: int) -> float:
        """
        Convert (rating, review_count) into a 0-100 buzz score.

        Design goals:
        - Rating dominates at low review counts (a 4.8-star listing with 20
          reviews should beat a 3.2-star listing with 50 reviews).
        - Review count matters at scale - 10k reviews vs 100 reviews should
          push the score up meaningfully.
        - Saturate smoothly so a 100k-review listing doesn't pin the score
          at 100 and drown out rating differences.

        Formula: normalized_rating * log-saturated_reviews * 100
        """
        if rating <= 0:
            return 0.0

        # rating is 0-5, normalize to 0-1
        rating_norm = min(rating, 5.0) / 5.0

        # Log-saturated review factor: log10(1 + reviews) / log10(1 + 50000)
        # -> 100 reviews => ~0.43, 1000 => ~0.64, 10000 => ~0.85, 50000 => 1.0
        if review_count <= 0:
            review_factor = 0.0
        else:
            review_factor = min(math.log10(1 + review_count) / math.log10(1 + 50000), 1.0)

        # Blend: rating is the floor, reviews are a multiplier that grows it.
        # A 5-star listing with 0 reviews gets 50 (half credit); a 5-star
        # listing with 50k+ reviews gets 100.
        score = rating_norm * (0.5 + 0.5 * review_factor) * 100
        return score


# Convenience factory for parity with other connectors
def get_amazon_reviews_connector(api_token: Optional[str] = None) -> AmazonReviewsConnector:
    return AmazonReviewsConnector(api_token=api_token)
