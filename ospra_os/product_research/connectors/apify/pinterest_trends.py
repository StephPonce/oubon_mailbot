"""
Apify Pinterest Trends Scraper
==============================

Pinterest is a leading early-signal platform for product discovery.
Repins, saves, and growing search volume on Pinterest precede Amazon
bestseller status by 4–8 weeks for visual/lifestyle product categories
(home, kitchen, beauty, fashion, fitness).

This connector adds Pinterest as a *trend signal source* (not a product
catalog). It returns aggregated repin/search/click metrics per keyword,
which the OpportunityScorer blends with Google Trends as part of the
demand calculation.

Actor: epctex/pinterest-search-scraper (or equivalent) — switchable via
PINTEREST_APIFY_ACTOR env var.

Cost: ~$0.0005 per keyword (well within $39 monthly Apify budget).

Returns same shape as google_trends_apify (TrendData) so
opportunity_scorer can treat it uniformly.
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field

from .base_apify import ApifyClient

logger = logging.getLogger(__name__)


# Default Pinterest actor. The previous default
# (``epctex/pinterest-search-scraper``) was removed from the Apify store
# (404) and the alive successor (``epctex/pinterest-scraper``) requires a
# FLAT_PRICE_PER_MONTH rental ($35/mo). To match the no-rental-defaults
# stance, this connector is disabled by default and must be opted in via
# ``PINTEREST_APIFY_ACTOR``. When unset, the trend-fetch path falls
# through cleanly (UNKNOWN, +0 keywords) without burning credits.
DEFAULT_ACTOR_ID = ""

# Pinterest's repin counts span many orders of magnitude. We log-compress
# at 50,000 repins (≈ "very popular pin" ceiling for a single query) so
# that one viral pin doesn't dominate the score.
REPIN_LOG_CEILING = 50_000

# Save count is a stronger purchase-intent signal than view count. Pinterest
# users save pins to boards specifically because they intend to act on them.
SAVE_LOG_CEILING = 10_000


@dataclass
class PinterestTrendData:
    """Pinterest trend signal for a keyword."""
    search_term: str
    pin_count: int = 0           # Number of pins matching the search
    total_repins: int = 0        # Sum of repins across top results
    total_saves: int = 0         # Sum of save counts
    avg_engagement: float = 0.0  # Average engagement per pin
    rising_keywords: List[str] = field(default_factory=list)  # Related rising terms

    # Normalized 0-100 scores (parallel to google_trends_apify.TrendData)
    current_interest: int = 0    # 0-100 normalized current popularity
    velocity: float = 0.0        # % change estimate (from rising/related signal)
    trend_score: float = 0.0     # 0-100 final blended score
    fetched_at: str = ""


class PinterestTrendsApify:
    """
    Pinterest Trends connector via Apify.

    Returns trend signals comparable in shape to Google Trends data so
    OpportunityScorer can mix them without source-specific branching.
    """

    def __init__(self, api_token: Optional[str] = None, actor_id: Optional[str] = None):
        """
        Initialize Pinterest Trends client.

        Args:
            api_token: Apify API token. If None, reads from APIFY_API_TOKEN env var.
            actor_id: Override the default Pinterest actor.
        """
        try:
            self.client = ApifyClient(api_token=api_token)
            self._available = True
        except ValueError as e:
            # No APIFY_API_TOKEN — connector remains unavailable but importable
            logger.warning(f"[PINTEREST] Apify client init failed: {e}")
            self.client = None
            self._available = False

        self.actor_id = actor_id or os.getenv("PINTEREST_APIFY_ACTOR", DEFAULT_ACTOR_ID)
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl = 3600  # 1 hour cache (Pinterest trends move slower than TikTok)
        logger.info(f"[PINTEREST] Pinterest Trends initialized (actor={self.actor_id})")

    @property
    def name(self) -> str:
        return "Pinterest Trends"

    @property
    def source_id(self) -> str:
        return "pinterest_trends"

    def is_available(self) -> bool:
        # Both the Apify client AND a configured actor are required — the
        # default actor is empty so we don't auto-spend on a rental.
        return self._available and bool(self.actor_id)

    def _cache_key(self, keyword: str, geo: str) -> str:
        return f"pinterest:{keyword.lower()}:{geo}"

    def _cache_get(self, key: str) -> Optional[PinterestTrendData]:
        entry = self._cache.get(key)
        if not entry:
            return None
        cached_at, data = entry
        if (datetime.now(timezone.utc) - cached_at).total_seconds() > self._cache_ttl:
            return None
        return data

    def _cache_set(self, key: str, data: PinterestTrendData) -> None:
        self._cache[key] = (datetime.now(timezone.utc), data)

    @staticmethod
    def _normalize_repins(repins: int) -> float:
        """Log-compress repin counts to 0..1."""
        import math
        if repins <= 0:
            return 0.0
        return min(1.0, math.log1p(repins) / math.log1p(REPIN_LOG_CEILING))

    @staticmethod
    def _normalize_saves(saves: int) -> float:
        """Log-compress save counts to 0..1. Saves weight more than repins."""
        import math
        if saves <= 0:
            return 0.0
        return min(1.0, math.log1p(saves) / math.log1p(SAVE_LOG_CEILING))

    @classmethod
    def _compute_trend_score(cls, repins: int, saves: int, pin_count: int,
                             rising_keyword_count: int) -> float:
        """
        Blend Pinterest signals into a 0-100 trend score.

        Weights:
        - Saves (purchase intent): 0.40
        - Repins (viral spread):   0.30
        - Pin count (volume):      0.15
        - Rising keywords (lift):  0.15
        """
        save_norm = cls._normalize_saves(saves)
        repin_norm = cls._normalize_repins(repins)
        # Pin count: cap at 5000 pins for a search term
        pin_norm = min(1.0, pin_count / 5000) if pin_count > 0 else 0.0
        # Rising keywords: up to 10 are very meaningful
        rising_norm = min(1.0, rising_keyword_count / 10) if rising_keyword_count > 0 else 0.0

        blended = (0.40 * save_norm
                   + 0.30 * repin_norm
                   + 0.15 * pin_norm
                   + 0.15 * rising_norm)
        return round(blended * 100, 1)

    @staticmethod
    def _estimate_velocity(rising_keyword_count: int, save_to_repin_ratio: float) -> float:
        """
        Estimate growth velocity from rising-keyword volume and save/repin ratio.

        High save ratio relative to repins indicates fresh purchase intent
        (rather than just nostalgic re-sharing).

        Returns: % change estimate (-50 to +50).
        """
        # Each rising keyword contributes ~3% velocity, capped at +30%
        rising_lift = min(30.0, rising_keyword_count * 3.0)
        # Save/repin ratio: 1.0 = neutral, >1 = accelerating intent
        if save_to_repin_ratio > 1.5:
            ratio_lift = 15.0
        elif save_to_repin_ratio > 1.0:
            ratio_lift = 5.0
        elif save_to_repin_ratio > 0.5:
            ratio_lift = 0.0
        else:
            ratio_lift = -10.0
        return round(rising_lift + ratio_lift, 1)

    async def get_interest(
        self,
        search_terms: List[str],
        geo: str = "US",
        max_pins_per_term: int = 50,
    ) -> List[PinterestTrendData]:
        """
        Fetch Pinterest trend signals for one or more keywords.

        Args:
            search_terms: Up to 10 keywords per call.
            geo: Country code (US, GB, DE, etc.). Pinterest geo-filters loosely.
            max_pins_per_term: Pin sample size per keyword (default 50).

        Returns:
            List of PinterestTrendData, one per term.
        """
        if not self.is_available() or not search_terms:
            return [self._empty_trend(t) for t in (search_terms or [])]

        results: List[PinterestTrendData] = []
        uncached_terms: List[str] = []

        for term in search_terms:
            cached = self._cache_get(self._cache_key(term, geo))
            if cached:
                results.append(cached)
                logger.info(f"[PINTEREST] Cache hit: {term}")
            else:
                uncached_terms.append(term)

        if not uncached_terms:
            return results

        # Batch the Apify call across all uncached terms
        try:
            raw = await self.client.run_actor(
                actor_id=self.actor_id,
                run_input={
                    "search": uncached_terms,
                    "maxItems": max_pins_per_term * len(uncached_terms),
                    "country": geo,
                    "proxy": {"useApifyProxy": True},
                },
                timeout_secs=180,
                memory_mbytes=512,
            )

            # Group raw pins by their search term
            pins_by_term: Dict[str, List[Dict]] = {t: [] for t in uncached_terms}
            for item in raw:
                # Pinterest scrapers tag pins with a `searchKeyword` or `query` field
                term = (
                    item.get("searchKeyword")
                    or item.get("query")
                    or item.get("search_term")
                    or ""
                ).lower()
                # Fallback: match by description if no explicit tag
                if not term:
                    desc = (item.get("description") or "").lower()
                    for candidate in uncached_terms:
                        if candidate.lower() in desc:
                            term = candidate.lower()
                            break
                if term in pins_by_term:
                    pins_by_term[term].append(item)
                else:
                    # Unmatched pin — distribute round-robin to first term
                    if uncached_terms:
                        pins_by_term[uncached_terms[0].lower()].append(item)

            for term in uncached_terms:
                pins = pins_by_term.get(term.lower(), [])
                trend = self._aggregate_pins(term, pins)
                results.append(trend)
                self._cache_set(self._cache_key(term, geo), trend)

            logger.info(f"[PINTEREST] Fetched {len(uncached_terms)} terms, {len(raw)} pins")

        except Exception as e:
            logger.error(f"[PINTEREST] Apify call failed: {e}")
            for term in uncached_terms:
                results.append(self._empty_trend(term))

        return results

    def _aggregate_pins(self, search_term: str, pins: List[Dict]) -> PinterestTrendData:
        """Aggregate raw pin records into a single trend signal."""
        if not pins:
            return self._empty_trend(search_term)

        total_repins = 0
        total_saves = 0
        rising_keywords_set = set()

        for pin in pins:
            # Different Pinterest scrapers use different field names — we accept all
            repins = (pin.get("repinCount") or pin.get("repins")
                      or pin.get("aggregatedPinData", {}).get("aggregatedStats", {}).get("saves", 0)
                      or 0)
            saves = (pin.get("saveCount") or pin.get("saves")
                     or pin.get("aggregatedPinData", {}).get("aggregatedStats", {}).get("done", 0)
                     or 0)
            try:
                total_repins += int(repins or 0)
            except (TypeError, ValueError):
                pass
            try:
                total_saves += int(saves or 0)
            except (TypeError, ValueError):
                pass

            # Collect related/rising keywords from each pin
            related = pin.get("relatedKeywords") or pin.get("rising_keywords") or []
            if isinstance(related, list):
                for kw in related[:5]:  # cap per-pin contribution
                    if isinstance(kw, str) and kw and kw.lower() != search_term.lower():
                        rising_keywords_set.add(kw)

        pin_count = len(pins)
        avg_engagement = (total_repins + total_saves) / max(pin_count, 1)

        save_to_repin_ratio = (total_saves / total_repins) if total_repins > 0 else 0.0
        rising_keywords = list(rising_keywords_set)[:20]
        rising_kw_count = len(rising_keywords)

        trend_score = self._compute_trend_score(
            repins=total_repins,
            saves=total_saves,
            pin_count=pin_count,
            rising_keyword_count=rising_kw_count,
        )
        velocity = self._estimate_velocity(
            rising_keyword_count=rising_kw_count,
            save_to_repin_ratio=save_to_repin_ratio,
        )
        # current_interest is just the trend_score rounded to int (0-100 scale)
        current_interest = int(round(trend_score))

        return PinterestTrendData(
            search_term=search_term,
            pin_count=pin_count,
            total_repins=total_repins,
            total_saves=total_saves,
            avg_engagement=round(avg_engagement, 1),
            rising_keywords=rising_keywords,
            current_interest=current_interest,
            velocity=velocity,
            trend_score=trend_score,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _empty_trend(term: str) -> PinterestTrendData:
        return PinterestTrendData(
            search_term=term,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def clear_cache(self) -> None:
        self._cache = {}


# Compatibility aliases
PinterestTrends = PinterestTrendsApify


def get_pinterest_trends(api_token: Optional[str] = None) -> PinterestTrendsApify:
    return PinterestTrendsApify(api_token=api_token)


# Quick test
async def _smoke_test():
    print("\n" + "=" * 70)
    print("[TEST] PINTEREST TRENDS APIFY CONNECTOR")
    print("=" * 70 + "\n")

    pin = PinterestTrendsApify()
    if not pin.is_available():
        print("[ERROR] APIFY_API_TOKEN not set — cannot run smoke test")
        return

    terms = ["minimalist desk setup", "led strip lights", "air fryer recipes"]
    print(f"Searching Pinterest for: {terms}\n")

    results = await pin.get_interest(terms)
    for r in results:
        print(f"\n[SEARCH] {r.search_term}")
        print(f"   Pins: {r.pin_count}")
        print(f"   Repins: {r.total_repins:,}")
        print(f"   Saves: {r.total_saves:,}")
        print(f"   Trend score: {r.trend_score}/100")
        print(f"   Velocity: {r.velocity:+.1f}%")
        if r.rising_keywords:
            print(f"   Rising: {', '.join(r.rising_keywords[:5])}")

    print("\n[SUCCESS] Pinterest Trends working!")


if __name__ == "__main__":
    asyncio.run(_smoke_test())
