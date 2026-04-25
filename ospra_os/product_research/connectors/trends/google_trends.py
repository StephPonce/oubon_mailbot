"""
Google Trends connector with PROXY SUPPORT
==========================================

Uses ScraperAPI/proxy rotation to bypass rate limits.
"""

from typing import List, Optional
from datetime import datetime, timedelta, timezone
from ..base import BaseConnector, ProductCandidate
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class GoogleTrendsConnector(BaseConnector):
    """
    Google Trends integration with proxy support.

    Uses pytrends library with rotating proxies to avoid rate limits.
    """

    def __init__(self):
        super().__init__()
        self._cache = {}
        self._cache_ttl = 3600  # 1 hour cache
        
    @property
    def name(self) -> str:
        return "Google Trends"

    @property
    def source_id(self) -> str:
        return "google_trends"

    def _get_proxy_config(self) -> dict:
        """Get proxy configuration for pytrends."""
        scraper_api_key = os.getenv('SCRAPERAPI_KEY')
        
        if scraper_api_key:
            # ScraperAPI proxy format
            return {
                'https': f'http://scraperapi:{scraper_api_key}@proxy-server.scraperapi.com:8001'
            }
        
        # Fallback: Try free proxy
        try:
            from ospra_os.scraping.proxy_manager import proxy_manager
            if proxy_manager.free_proxies:
                proxy = proxy_manager._get_next_proxy()
                if proxy:
                    return {'https': proxy, 'http': proxy}
        except Exception as e:
            logger.warning(f"Could not get proxy: {e}")
        
        return {}

    def _get_cache_key(self, query: str, timeframe: str, geo: str) -> str:
        """Generate cache key."""
        return f"{query}:{timeframe}:{geo}"

    def _is_cached(self, key: str) -> bool:
        """Check if data is cached and not expired."""
        if key not in self._cache:
            return False
        cached_time, _ = self._cache[key]
        return (datetime.now(timezone.utc) - cached_time).seconds < self._cache_ttl

    def _get_cached(self, key: str):
        """Get cached data."""
        if self._is_cached(key):
            _, data = self._cache[key]
            return data
        return None

    def _set_cache(self, key: str, data):
        """Cache data."""
        self._cache[key] = (datetime.now(timezone.utc), data)

    async def search(self, query: str, **kwargs) -> List[ProductCandidate]:
        """
        Search for trend data on a specific query.

        Args:
            query: Search term
            timeframe: Optional timeframe (default: 'today 3-m')
            geo: Optional geographic region (default: 'US')

        Returns:
            List with single ProductCandidate showing trend data
        """
        timeframe = kwargs.get("timeframe", "today 3-m")
        geo = kwargs.get("geo", "US")
        
        # Check cache first
        cache_key = self._get_cache_key(query, timeframe, geo)
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.info(f"[PACKAGE] Google Trends cache hit: {query}")
            return cached

        try:
            from pytrends.request import TrendReq

            loop = asyncio.get_event_loop()
            
            # Get proxy configuration
            proxies = self._get_proxy_config()
            
            # Create TrendReq with proxy and timeout
            def create_pytrend():
                return TrendReq(
                    hl='en-US',
                    tz=360,
                    timeout=(10, 25),
                    proxies=proxies if proxies else None,
                    retries=3,
                    backoff_factor=0.5
                )
            
            pytrend = await loop.run_in_executor(None, create_pytrend)
            logger.info(f"[SEARCH] Google Trends search: {query} (proxy: {'yes' if proxies else 'no'})")

            # Build payload with retry logic
            async def build_with_retry(retries=3):
                for attempt in range(retries):
                    try:
                        await loop.run_in_executor(
                            None,
                            lambda: pytrend.build_payload([query], timeframe=timeframe, geo=geo)
                        )
                        return True
                    except Exception as e:
                        if attempt < retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            logger.warning(f"Retry {attempt + 1} for {query}: {e}")
                        else:
                            raise
                return False

            await build_with_retry()

            # Get interest over time
            interest_df = await loop.run_in_executor(None, lambda: pytrend.interest_over_time())

            if interest_df.empty or query not in interest_df.columns:
                result = []
                self._set_cache(cache_key, result)
                return result

            # Calculate trend score (0-100)
            interest_values = interest_df[query].dropna()
            if len(interest_values) == 0:
                result = []
                self._set_cache(cache_key, result)
                return result

            current_value = int(interest_values.iloc[-1])
            max_value = int(interest_values.max())
            avg_value = int(interest_values.mean())

            # Calculate trend direction
            recent = interest_values.tail(7).mean() if len(interest_values) >= 7 else current_value
            older = interest_values.head(7).mean() if len(interest_values) >= 7 else avg_value
            
            if older > 0:
                velocity = ((recent - older) / older) * 100
            else:
                velocity = 0

            # Trend score: higher if currently trending up
            trend_score = min(100, (current_value / max(avg_value, 1)) * 50)
            
            # Boost score if velocity is positive
            if velocity > 20:
                trend_score = min(100, trend_score * 1.3)

            result = [
                ProductCandidate(
                    name=query,
                    source=self.source_id,
                    trend_score=trend_score,
                    search_volume=current_value,
                    category=kwargs.get("category"),
                    tags=self._get_trend_tags(velocity, current_value, avg_value),
                    metadata={
                        "velocity": velocity,
                        "current_interest": current_value,
                        "max_interest": max_value,
                        "avg_interest": avg_value,
                        "timeframe": timeframe,
                        "geo": geo,
                        "fetched_at": datetime.now(timezone.utc).isoformat()
                    }
                )
            ]
            
            self._set_cache(cache_key, result)
            logger.info(f"[SUCCESS] Google Trends: {query} = {trend_score:.1f} score, {velocity:+.1f}% velocity")
            
            return result

        except ImportError:
            logger.error("[WARNING]  pytrends not installed. Run: pip install pytrends")
            return []
        except Exception as e:
            logger.error(f"[WARNING]  Google Trends error for '{query}': {e}")
            # Return empty but don't cache errors
            return []

    def _get_trend_tags(self, velocity: float, current: int, avg: int) -> List[str]:
        """Generate tags based on trend data."""
        tags = []
        
        if velocity > 50:
            tags.append("exploding")
        elif velocity > 20:
            tags.append("trending_up")
        elif velocity > 0:
            tags.append("growing")
        elif velocity > -20:
            tags.append("stable")
        else:
            tags.append("declining")
        
        if current > avg * 1.5:
            tags.append("high_interest")
        elif current < avg * 0.5:
            tags.append("low_interest")
        
        return tags

    async def get_trending(self, category: Optional[str] = None, limit: int = 10) -> List[ProductCandidate]:
        """
        Get currently trending searches.

        Args:
            category: Optional category filter
            limit: Max results

        Returns:
            List of trending product candidates
        """
        cache_key = f"trending:{category or 'all'}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.info(f"[PACKAGE] Google Trends trending cache hit")
            return cached
        
        try:
            from pytrends.request import TrendReq

            loop = asyncio.get_event_loop()
            proxies = self._get_proxy_config()
            
            def create_pytrend():
                return TrendReq(
                    hl='en-US',
                    tz=360,
                    timeout=(10, 25),
                    proxies=proxies if proxies else None,
                    retries=3,
                    backoff_factor=0.5
                )
            
            pytrend = await loop.run_in_executor(None, create_pytrend)

            # Get trending searches (US by default)
            trending_df = await loop.run_in_executor(
                None,
                lambda: pytrend.trending_searches(pn="united_states")
            )

            if trending_df.empty:
                return []

            # Convert to ProductCandidates
            candidates = []
            for idx, row in trending_df.head(limit).iterrows():
                search_term = str(row[0])

                # Get detailed trend data for this term
                detailed = await self.search(search_term, category=category)

                if detailed:
                    candidates.append(detailed[0])
                else:
                    # Fallback: create basic candidate
                    candidates.append(
                        ProductCandidate(
                            name=search_term,
                            source=self.source_id,
                            trend_score=80.0,  # Trending by definition
                            category=category,
                            tags=["trending_now"],
                        )
                    )
                
                # Rate limit between requests
                await asyncio.sleep(0.5)

            self._set_cache(cache_key, candidates)
            return candidates[:limit]

        except ImportError:
            logger.error("[WARNING]  pytrends not installed. Run: pip install pytrends")
            return []
        except Exception as e:
            logger.error(f"[WARNING]  Google Trends trending error: {e}")
            return []

    async def get_related_queries(self, query: str, limit: int = 10) -> List[str]:
        """
        Get related/rising queries for a search term.

        Args:
            query: Main search term
            limit: Max related queries

        Returns:
            List of related search terms
        """
        cache_key = f"related:{query}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            from pytrends.request import TrendReq

            loop = asyncio.get_event_loop()
            proxies = self._get_proxy_config()
            
            def create_pytrend():
                return TrendReq(
                    hl='en-US',
                    tz=360,
                    timeout=(10, 25),
                    proxies=proxies if proxies else None,
                    retries=3,
                    backoff_factor=0.5
                )
            
            pytrend = await loop.run_in_executor(None, create_pytrend)

            await loop.run_in_executor(
                None,
                lambda: pytrend.build_payload([query], timeframe="today 3-m", geo="US")
            )

            # Get related queries
            related_dict = await loop.run_in_executor(None, lambda: pytrend.related_queries())

            if not related_dict or query not in related_dict:
                return []

            # Extract rising queries
            rising_df = related_dict[query].get("rising")
            if rising_df is None or rising_df.empty:
                return []

            # Return top N queries
            result = rising_df["query"].head(limit).tolist()
            self._set_cache(cache_key, result)
            
            return result

        except Exception as e:
            logger.error(f"[WARNING]  Error getting related queries: {e}")
            return []
    
    def clear_cache(self):
        """Clear the cache."""
        self._cache = {}
        logger.info(" Google Trends cache cleared")
