"""
Cross-Reference Engine - Validate products across multiple sources

Combines data from Amazon, TikTok, and Reddit to validate product opportunities
with high confidence scoring.
"""
from typing import Dict, List, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class CrossReferenceEngine:
    """Cross-reference products across Amazon, TikTok, Reddit"""

    def __init__(self, amazon_scraper, tiktok_scraper, reddit_scraper):
        """
        Initialize cross-reference engine

        Args:
            amazon_scraper: Amazon Bestsellers scraper instance
            tiktok_scraper: TikTok Shop scraper instance
            reddit_scraper: Reddit sentiment scraper instance
        """
        self.amazon_scraper = amazon_scraper
        self.tiktok_scraper = tiktok_scraper
        self.reddit_scraper = reddit_scraper

    async def validate_product(
        self,
        keyword: str,
        niche: str
    ) -> Dict:
        """
        Cross-reference a product keyword across all sources

        Args:
            keyword: Product keyword to validate
            niche: Product niche/category

        Returns:
            Validated product with confidence score and multi-source data
        """
        logger.info(f"🔍 Cross-referencing: {keyword}")

        results = {
            'keyword': keyword,
            'niche': niche,
            'amazon_data': None,
            'tiktok_data': None,
            'reddit_data': None,
            'validation_score': 0.0,
            'recommendation': 'UNKNOWN'
        }

        # Run all scrapers in parallel
        tasks = []

        if self.amazon_scraper:
            tasks.append(self._get_amazon_data(keyword, niche))

        if self.tiktok_scraper:
            tasks.append(self._get_tiktok_data(keyword, niche))

        if self.reddit_scraper:
            tasks.append(self._get_reddit_data(keyword))

        # Wait for all to complete
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Parse responses
        idx = 0
        if self.amazon_scraper:
            results['amazon_data'] = responses[idx] if not isinstance(responses[idx], Exception) else None
            idx += 1

        if self.tiktok_scraper:
            results['tiktok_data'] = responses[idx] if not isinstance(responses[idx], Exception) else None
            idx += 1

        if self.reddit_scraper:
            results['reddit_data'] = responses[idx] if not isinstance(responses[idx], Exception) else None

        # Calculate validation score
        results['validation_score'] = self._calculate_validation_score(results)
        results['recommendation'] = self._get_recommendation(results['validation_score'])

        logger.info(f"✅ Validation Score: {results['validation_score']:.1f}/100")
        logger.info(f"   Recommendation: {results['recommendation']}")

        return results

    async def _get_amazon_data(self, keyword: str, niche: str) -> Optional[Dict]:
        """
        Get Amazon product data

        Args:
            keyword: Product keyword
            niche: Product niche

        Returns:
            Amazon product data or None
        """
        try:
            products = await self.amazon_scraper.discover_products(
                niche=niche,
                max_products=5,
                category='Electronics'
            )

            if products:
                # Return best match
                return products[0]
            return None

        except Exception as e:
            logger.error(f"   ⚠️  Amazon scraping failed: {e}")
            return None

    async def _get_tiktok_data(self, keyword: str, niche: str) -> Optional[Dict]:
        """
        Get TikTok viral data

        Args:
            keyword: Product keyword
            niche: Product niche

        Returns:
            TikTok product data or None
        """
        try:
            products = await self.tiktok_scraper.discover_products(
                niche=niche,
                max_products=5,
                keyword=keyword
            )

            if products:
                return products[0]
            return None

        except Exception as e:
            logger.error(f"   ⚠️  TikTok scraping failed: {e}")
            return None

    async def _get_reddit_data(self, keyword: str) -> Optional[Dict]:
        """
        Get Reddit sentiment

        Args:
            keyword: Product keyword

        Returns:
            Reddit sentiment data or None
        """
        try:
            sentiment = await self.reddit_scraper.get_product_sentiment(
                product_name=keyword,
                max_posts=20
            )
            return sentiment

        except Exception as e:
            logger.error(f"   ⚠️  Reddit scraping failed: {e}")
            return None

    def _calculate_validation_score(self, results: Dict) -> float:
        """
        Calculate overall validation score from all sources

        Scoring breakdown:
        - Amazon data (40 points): Has real product with good rating
        - TikTok viral (30 points): High engagement/views
        - Reddit sentiment (30 points): Positive community feedback

        Args:
            results: Cross-reference results dictionary

        Returns:
            Validation score (0-100)
        """
        score = 0.0

        # Amazon validation (40 points max)
        if results['amazon_data']:
            amazon = results['amazon_data']

            # Has product = 10 points
            score += 10

            # Good rating (4+ stars) = 15 points
            rating = amazon.get('rating', 0)
            if rating >= 4.5:
                score += 15
            elif rating >= 4.0:
                score += 10
            elif rating >= 3.5:
                score += 5

            # Many reviews = 15 points
            reviews = amazon.get('reviews_count', 0)
            if reviews >= 1000:
                score += 15
            elif reviews >= 500:
                score += 10
            elif reviews >= 100:
                score += 5

        # TikTok validation (30 points max)
        if results['tiktok_data']:
            tiktok = results['tiktok_data']

            # Has viral content = 10 points
            score += 10

            # High engagement = 20 points
            viral_score = tiktok.get('viral_score', 0)
            if viral_score >= 80:
                score += 20
            elif viral_score >= 60:
                score += 15
            elif viral_score >= 40:
                score += 10

        # Reddit validation (30 points max)
        if results['reddit_data']:
            reddit = results['reddit_data']

            # Has mentions = 10 points
            if reddit.get('mentions', 0) > 0:
                score += 10

            # Positive sentiment = 20 points
            sentiment = reddit.get('sentiment_score', 50)
            if sentiment >= 70:
                score += 20
            elif sentiment >= 60:
                score += 15
            elif sentiment >= 50:
                score += 10

        return min(score, 100.0)

    def _get_recommendation(self, score: float) -> str:
        """
        Get recommendation based on validation score

        Args:
            score: Validation score (0-100)

        Returns:
            Recommendation string
        """
        if score >= 80:
            return "STRONG BUY - Multiple sources confirm"
        elif score >= 60:
            return "BUY - Good validation"
        elif score >= 40:
            return "MAYBE - Limited validation"
        else:
            return "SKIP - Insufficient validation"
