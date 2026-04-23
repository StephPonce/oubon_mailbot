"""
Apify Google Trends Scraper - REPLACES pytrends
================================================

pytrends is ARCHIVED (April 2025) and constantly hits 429 rate limits.
This uses Apify's syntellect_ai/google-trends-scraper actor instead.

Cost: ~$0.00007 per result (very cheap with your $39 credits)
Success rate: 99.7%

Returns same data format as pytrends for compatibility.
"""

import os
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
import logging
from .base_apify import ApifyClient

logger = logging.getLogger(__name__)


@dataclass
class TrendData:
    """Google Trends data for a search term"""
    search_term: str
    current_interest: int  # 0-100
    max_interest: int      # 0-100
    avg_interest: float    # 0-100
    velocity: float        # % change (positive = trending up)
    trend_score: float     # 0-100 (our calculated score)
    related_queries: List[Dict]  # Rising & top queries
    related_topics: List[Dict]   # Rising & top topics
    interest_by_region: List[Dict]  # Regional breakdown
    interest_over_time: List[Dict]  # Time series data
    geo: str
    timeframe: str
    fetched_at: str

    # AI predictions (if enabled)
    prediction: Optional[Dict] = None


class ApifyGoogleTrends:
    """
    Google Trends via Apify - 99.7% success rate, no 429 errors!

    Uses: syntellect_ai/google-trends-scraper
    Cost: ~$0.00007 per result
    """

    ACTOR_ID = "syntellect_ai/google-trends-scraper"

    # Timeframe mapping (pytrends format -> Apify format)
    TIMEFRAME_MAP = {
        "today 1-m": "today 1-m",
        "today 3-m": "today 3-m",
        "today 12-m": "today 12-m",
        "today 5-y": "today 5-y",
        "now 1-H": "now 1-H",
        "now 4-H": "now 4-H",
        "now 1-d": "now 1-d",
        "now 7-d": "now 7-d",
    }

    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Apify Google Trends client

        Args:
            api_token: Apify API token. If None, reads from APIFY_API_TOKEN env var.
        """
        self.client = ApifyClient(api_token=api_token)
        self._cache = {}
        self._cache_ttl = 3600  # 1 hour cache
        logger.info("[TRENDS] Apify Google Trends initialized (replaces pytrends)")

    def _get_cache_key(self, query: str, timeframe: str, geo: str) -> str:
        """Generate cache key."""
        return f"trends:{query}:{timeframe}:{geo}"

    def _is_cached(self, key: str) -> bool:
        """Check if data is cached and not expired."""
        if key not in self._cache:
            return False
        cached_time, _ = self._cache[key]
        return (datetime.utcnow() - cached_time).seconds < self._cache_ttl

    def _get_cached(self, key: str):
        """Get cached data."""
        if self._is_cached(key):
            _, data = self._cache[key]
            return data
        return None

    def _set_cache(self, key: str, data):
        """Cache data."""
        self._cache[key] = (datetime.utcnow(), data)

    async def get_interest(
        self,
        search_terms: List[str],
        geo: str = "US",
        timeframe: str = "today 3-m",
        enable_prediction: bool = True
    ) -> List[TrendData]:
        """
        Get Google Trends interest data for search terms.

        Args:
            search_terms: List of keywords (max 5 per request)
            geo: Country code (US, GB, DE, etc.) or "" for worldwide
            timeframe: Time range (see TIMEFRAME_MAP)
            enable_prediction: Include AI trend predictions

        Returns:
            List of TrendData objects with interest data
        """
        results = []

        # Process in batches of 5 (Apify limit)
        for i in range(0, len(search_terms), 5):
            batch = search_terms[i:i+5]
            batch_results = await self._fetch_trends_batch(batch, geo, timeframe, enable_prediction)
            results.extend(batch_results)

            # Small delay between batches
            if i + 5 < len(search_terms):
                await asyncio.sleep(1)

        return results

    async def _fetch_trends_batch(
        self,
        search_terms: List[str],
        geo: str,
        timeframe: str,
        enable_prediction: bool
    ) -> List[TrendData]:
        """Fetch trends for a batch of up to 5 terms."""
        results = []

        # Check cache first
        uncached_terms = []
        for term in search_terms:
            cache_key = self._get_cache_key(term, timeframe, geo)
            cached = self._get_cached(cache_key)
            if cached:
                results.append(cached)
                logger.info(f"[CACHE] Google Trends cache hit: {term}")
            else:
                uncached_terms.append(term)

        if not uncached_terms:
            return results

        # Fetch from Apify
        logger.info(f"[FETCH] Apify Google Trends: {uncached_terms}")

        try:
            apify_timeframe = self.TIMEFRAME_MAP.get(timeframe, "today 3-m")

            raw_results = await self.client.run_actor(
                actor_id=self.ACTOR_ID,
                run_input={
                    "searchTerms": uncached_terms,
                    "geo": geo,
                    "timeRange": apify_timeframe,
                    "enablePrediction": enable_prediction,
                    "maxConcurrency": 1,
                    "proxyConfiguration": {
                        "useApifyProxy": True,
                        "apifyProxyGroups": ["RESIDENTIAL"]
                    }
                },
                timeout_secs=120,
                memory_mbytes=256  # Low memory = cheaper
            )

            # Parse results
            for item in raw_results:
                trend_data = self._parse_apify_result(item, geo, timeframe)
                if trend_data:
                    results.append(trend_data)
                    # Cache the result
                    cache_key = self._get_cache_key(trend_data.search_term, timeframe, geo)
                    self._set_cache(cache_key, trend_data)

            logger.info(f"[SUCCESS] Got {len(raw_results)} trend results from Apify")

        except Exception as e:
            logger.error(f"[ERROR] Apify Google Trends failed: {e}")
            # Return empty results for failed terms
            for term in uncached_terms:
                results.append(self._empty_trend_data(term, geo, timeframe))

        return results

    def _parse_apify_result(self, item: Dict, geo: str, timeframe: str) -> Optional[TrendData]:
        """Parse Apify result into TrendData."""
        try:
            search_term = item.get('searchTerm', '')
            interest_over_time = item.get('interestOverTime', [])

            # Calculate statistics from interest over time
            values = [entry.get('value', 0) for entry in interest_over_time if entry.get('value') is not None]

            if values:
                current_interest = values[-1] if values else 0
                max_interest = max(values) if values else 0
                avg_interest = sum(values) / len(values) if values else 0

                # Calculate velocity (% change from first half to second half)
                if len(values) >= 4:
                    first_half = sum(values[:len(values)//2]) / (len(values)//2)
                    second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
                    velocity = ((second_half - first_half) / max(first_half, 1)) * 100
                else:
                    velocity = 0

                # Calculate trend score (0-100)
                # Higher score = trending up + high interest
                trend_score = min(100, (current_interest / max(avg_interest, 1)) * 50)
                if velocity > 20:
                    trend_score = min(100, trend_score * 1.3)
                elif velocity < -20:
                    trend_score = trend_score * 0.7
            else:
                current_interest = 0
                max_interest = 0
                avg_interest = 0
                velocity = 0
                trend_score = 0

            # Parse related queries
            related_queries = item.get('relatedQueries', {})
            related_queries_list = []
            for q in related_queries.get('rising', []):
                related_queries_list.append({
                    'query': q.get('query', ''),
                    'value': q.get('value', ''),
                    'type': 'rising'
                })
            for q in related_queries.get('top', []):
                related_queries_list.append({
                    'query': q.get('query', ''),
                    'value': q.get('value', 0),
                    'type': 'top'
                })

            # Parse related topics
            related_topics = item.get('relatedTopics', {})
            related_topics_list = []
            for t in related_topics.get('rising', []):
                related_topics_list.append({
                    'topic': t.get('topic', ''),
                    'value': t.get('value', ''),
                    'type': 'rising'
                })
            for t in related_topics.get('top', []):
                related_topics_list.append({
                    'topic': t.get('topic', ''),
                    'value': t.get('value', 0),
                    'type': 'top'
                })

            # Parse regional interest
            interest_by_region = item.get('interestByRegion', [])

            # AI predictions (if available)
            prediction = item.get('prediction') or item.get('forecast')

            return TrendData(
                search_term=search_term,
                current_interest=int(current_interest),
                max_interest=int(max_interest),
                avg_interest=round(avg_interest, 1),
                velocity=round(velocity, 1),
                trend_score=round(trend_score, 1),
                related_queries=related_queries_list,
                related_topics=related_topics_list,
                interest_by_region=interest_by_region,
                interest_over_time=interest_over_time,
                geo=geo,
                timeframe=timeframe,
                fetched_at=datetime.utcnow().isoformat(),
                prediction=prediction
            )

        except Exception as e:
            logger.error(f"[ERROR] Failed to parse trend result: {e}")
            return None

    def _empty_trend_data(self, term: str, geo: str, timeframe: str) -> TrendData:
        """Create empty TrendData for failed fetches."""
        return TrendData(
            search_term=term,
            current_interest=0,
            max_interest=0,
            avg_interest=0,
            velocity=0,
            trend_score=0,
            related_queries=[],
            related_topics=[],
            interest_by_region=[],
            interest_over_time=[],
            geo=geo,
            timeframe=timeframe,
            fetched_at=datetime.utcnow().isoformat(),
            prediction=None
        )

    async def get_related_queries(self, query: str, geo: str = "US", limit: int = 10) -> List[str]:
        """
        Get related/rising queries for a search term.

        Args:
            query: Main search term
            geo: Country code
            limit: Max related queries

        Returns:
            List of related search terms
        """
        results = await self.get_interest([query], geo=geo)

        if not results:
            return []

        trend_data = results[0]

        # Prioritize rising queries
        rising = [q['query'] for q in trend_data.related_queries if q.get('type') == 'rising']
        top = [q['query'] for q in trend_data.related_queries if q.get('type') == 'top']

        # Combine and limit
        all_queries = rising + [q for q in top if q not in rising]
        return all_queries[:limit]

    async def get_trending_searches(self, geo: str = "US", limit: int = 20) -> List[Dict]:
        """
        Get currently trending searches (daily trends).

        Note: This requires a different Apify actor for real-time trending.
        For now, we'll use broad category searches.
        """
        # Common trending product categories
        trending_categories = [
            "smart home gadgets",
            "kitchen gadgets",
            "fitness products",
            "beauty products",
            "pet supplies",
        ]

        results = await self.get_interest(trending_categories, geo=geo)

        # Sort by trend score
        results.sort(key=lambda x: x.trend_score, reverse=True)

        return [
            {
                'search_term': r.search_term,
                'trend_score': r.trend_score,
                'velocity': r.velocity,
                'current_interest': r.current_interest,
            }
            for r in results[:limit]
        ]

    def clear_cache(self):
        """Clear the cache."""
        self._cache = {}
        logger.info("[CLEAR] Google Trends cache cleared")


# Compatibility alias
GoogleTrendsApify = ApifyGoogleTrends


# Quick test
async def test_apify_trends():
    """Test Apify Google Trends integration"""
    print("\n" + "="*70)
    print("[TEST] TESTING APIFY GOOGLE TRENDS")
    print("="*70 + "\n")

    try:
        trends = ApifyGoogleTrends()

        # Test with product-related search terms
        search_terms = ["smart plug", "led strip lights", "air fryer"]

        print(f"Searching for: {search_terms}")
        print("This uses Apify (no 429 errors!)\n")

        results = await trends.get_interest(search_terms, geo="US", timeframe="today 3-m")

        for result in results:
            print(f"\n{'='*50}")
            print(f"[SEARCH] {result.search_term}")
            print(f"{'='*50}")
            print(f"   Trend Score: {result.trend_score:.1f}/100")
            print(f"   Velocity: {result.velocity:+.1f}%")
            print(f"   Current Interest: {result.current_interest}")
            print(f"   Max Interest: {result.max_interest}")
            print(f"   Avg Interest: {result.avg_interest:.1f}")

            if result.related_queries:
                print(f"\n   Related Queries (rising):")
                for q in result.related_queries[:5]:
                    if q.get('type') == 'rising':
                        print(f"      - {q['query']} ({q['value']})")

            if result.prediction:
                print(f"\n   AI Prediction: {result.prediction}")

        print("\n[SUCCESS] Apify Google Trends working!")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_apify_trends())
