"""Google Trends connector for product trend analysis."""

from typing import List, Optional
from datetime import datetime, timedelta
from ..base import BaseConnector, ProductCandidate
import asyncio


class GoogleTrendsConnector(BaseConnector):
    """
    Google Trends integration.

    Uses pytrends library to fetch trending searches and interest over time.
    No API key required.
    """

    @property
    def name(self) -> str:
        return "Google Trends"

    @property
    def source_id(self) -> str:
        return "google_trends"

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

        try:
            from pytrends.request import TrendReq

            # Run pytrends in thread pool (it's blocking)
            loop = asyncio.get_event_loop()
            pytrend = await loop.run_in_executor(None, TrendReq)

            # Build payload
            await loop.run_in_executor(
                None,
                lambda: pytrend.build_payload([query], timeframe=timeframe, geo=geo)
            )

            # Get interest over time
            interest_df = await loop.run_in_executor(None, lambda: pytrend.interest_over_time())

            if interest_df.empty or query not in interest_df.columns:
                return []

            # Calculate trend score (0-100)
            interest_values = interest_df[query].dropna()
            if len(interest_values) == 0:
                return []

            current_value = int(interest_values.iloc[-1])
            max_value = int(interest_values.max())
            avg_value = int(interest_values.mean())

            # Trend score: higher if currently trending up
            trend_score = min(100, (current_value / max(avg_value, 1)) * 50)

            return [
                ProductCandidate(
                    name=query,
                    source=self.source_id,
                    trend_score=trend_score,
                    search_volume=current_value,  # Relative search volume
                    category=kwargs.get("category"),
                    tags=["trending" if current_value > avg_value else "declining"],
                )
            ]

        except ImportError:
            print("⚠️  pytrends not installed. Run: pip install pytrends")
            return []
        except Exception as e:
            print(f"⚠️  Google Trends error: {e}")
            return []

    async def get_trending(self, category: Optional[str] = None, limit: int = 10) -> List[ProductCandidate]:
        """
        Get currently trending searches.

        Args:
            category: Optional category filter
            limit: Max results

        Returns:
            List of trending product candidates
        """
        try:
            from pytrends.request import TrendReq

            loop = asyncio.get_event_loop()
            pytrend = await loop.run_in_executor(None, TrendReq)

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

            return candidates[:limit]

        except ImportError:
            print("⚠️  pytrends not installed. Run: pip install pytrends")
            return []
        except Exception as e:
            print(f"⚠️  Google Trends error: {e}")
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
        try:
            from pytrends.request import TrendReq

            loop = asyncio.get_event_loop()
            pytrend = await loop.run_in_executor(None, TrendReq)

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
            return rising_df["query"].head(limit).tolist()

        except Exception as e:
            print(f"⚠️  Error getting related queries: {e}")
            return []
