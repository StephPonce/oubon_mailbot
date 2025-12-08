"""
Product Saturation Scorer
==========================

Analyzes market saturation using Amazon + TikTok data to avoid deploying
products that are already oversaturated.

Uses data from:
- Amazon Bestsellers (seller count, reviews, BSR trends)
- TikTok Shop (viral velocity, engagement trends)
- Cross-reference engine (opportunity scoring)

NO SHOPIFY SCRAPING NEEDED - More reliable using Amazon data.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import asyncio


class SaturationScorer:
    """
    Calculate product saturation scores to avoid oversaturated markets.

    Saturation Score (0-100):
    - 0-30: Blue ocean (low competition) ✅ DEPLOY
    - 31-60: Moderate competition ⚠️ CAUTION
    - 61-100: Saturated (high competition) ❌ SKIP

    Based on Amazon data (more reliable than Shopify scraping):
    - Seller count
    - Review velocity (reviews per day)
    - Best Seller Rank (BSR) trends
    - Price competition
    """

    def __init__(self):
        self.amazon_scraper = None
        self.tiktok_scraper = None

        # Try to load scrapers
        try:
            from ospra_os.product_research.connectors.apify import AmazonBestsellersScraper
            self.amazon_scraper = AmazonBestsellersScraper()
        except ImportError:
            pass

        try:
            from ospra_os.product_research.connectors.apify import TikTokShopScraper
            self.tiktok_scraper = TikTokShopScraper()
        except ImportError:
            pass

    async def calculate_saturation_score(
        self,
        product_name: str,
        amazon_data: Optional[Dict] = None,
        category: str = "All"
    ) -> Dict:
        """
        Check how saturated a product is on Amazon.

        Args:
            product_name: Product to check
            amazon_data: Optional pre-fetched Amazon data (recommended - avoids scraping)
            category: Amazon category to search (if scraping needed)

        Returns:
            {
                "saturation_score": float (0-100),
                "competitor_count": int,
                "review_velocity": float (reviews/day),
                "bsr": int,
                "bsr_trend": "rising" | "stable" | "falling",
                "price_range": {"min": float, "max": float},
                "recommendation": "deploy" | "caution" | "skip",
                "reasons": List[str],
                "opportunity_score": float (0-100)
            }
        """

        # If Amazon data not provided, try to fetch it from bestsellers
        # Note: The Amazon scraper doesn't support keyword search, only category scraping
        # For best results, pass amazon_data from the discovery pipeline
        if not amazon_data and self.amazon_scraper:
            try:
                # Scrape bestsellers and try to find matching product
                bestsellers = await self.amazon_scraper.scrape_bestsellers(
                    category=category,
                    max_products=100
                )

                # Try to find product by name match
                product_name_lower = product_name.lower()
                for item in bestsellers:
                    if product_name_lower in item.get('name', '').lower():
                        amazon_data = item
                        break

                if not amazon_data:
                    print(f"⚠️  Product '{product_name}' not found in Amazon bestsellers")
            except Exception as e:
                print(f"⚠️  Amazon scraper failed: {e}")
                amazon_data = None

        # Calculate saturation components
        seller_count = self._extract_seller_count(amazon_data)
        review_velocity = self._calculate_review_velocity(amazon_data)
        bsr = self._extract_bsr(amazon_data)
        bsr_trend = self._analyze_bsr_trend(amazon_data)
        price_range = self._extract_price_range(amazon_data)

        # Calculate weighted saturation score
        saturation_score = self._calculate_weighted_score(
            seller_count=seller_count,
            review_velocity=review_velocity,
            bsr=bsr,
            bsr_trend=bsr_trend
        )

        # Determine recommendation
        recommendation, reasons = self._get_recommendation(
            saturation_score=saturation_score,
            seller_count=seller_count,
            review_velocity=review_velocity,
            bsr=bsr
        )

        # Calculate opportunity score (inverse of saturation)
        opportunity_score = max(0, 100 - saturation_score)

        return {
            "saturation_score": round(saturation_score, 1),
            "competitor_count": seller_count,
            "review_velocity": round(review_velocity, 2),
            "bsr": bsr,
            "bsr_trend": bsr_trend,
            "price_range": price_range,
            "recommendation": recommendation,
            "reasons": reasons,
            "opportunity_score": round(opportunity_score, 1)
        }

    def _extract_seller_count(self, amazon_data: Optional[Dict]) -> int:
        """
        Estimate number of competing sellers from Amazon data.

        Note: Amazon Bestsellers scraper doesn't provide seller count directly.
        We estimate based on other signals:
        - High review count = more sellers likely
        - Good BSR = more competitive = more sellers
        """
        if not amazon_data:
            return 0

        # Check for explicit seller count (if available from other scrapers)
        seller_count = amazon_data.get("seller_count") or amazon_data.get("sellers")
        if seller_count:
            return int(seller_count)

        # Estimate based on reviews and BSR
        reviews = amazon_data.get("reviews_count", 0)
        bsr = amazon_data.get("bestseller_rank", 999999)

        # Heuristic estimation:
        # High reviews + good BSR = likely many sellers
        if reviews > 5000 and bsr < 1000:
            return 50  # Very competitive
        elif reviews > 1000 and bsr < 10000:
            return 25  # Moderately competitive
        elif reviews > 100 and bsr < 50000:
            return 10  # Some competition
        else:
            return 5   # Low competition

        return 0

    def _calculate_review_velocity(self, amazon_data: Optional[Dict]) -> float:
        """Calculate reviews per day (indicates market maturity)."""
        if not amazon_data:
            return 0.0

        total_reviews = amazon_data.get("review_count", 0) or amazon_data.get("reviews", 0)

        # Estimate reviews per day based on product age
        # If we have first_available date, use it; otherwise estimate
        first_available = amazon_data.get("first_available")
        if first_available:
            try:
                from datetime import datetime
                first_date = datetime.fromisoformat(first_available)
                days_live = (datetime.now() - first_date).days
                if days_live > 0:
                    return total_reviews / days_live
            except:
                pass

        # Fallback: Estimate based on review count
        # Assume product has been live for:
        # - 500+ reviews: ~180 days (6 months)
        # - 100-500 reviews: ~90 days (3 months)
        # - <100 reviews: ~30 days (1 month)
        if total_reviews >= 500:
            estimated_days = 180
        elif total_reviews >= 100:
            estimated_days = 90
        else:
            estimated_days = 30

        return total_reviews / estimated_days if estimated_days > 0 else 0.0

    def _extract_bsr(self, amazon_data: Optional[Dict]) -> int:
        """Extract Best Seller Rank from Amazon data."""
        if not amazon_data:
            return 999999  # Very high = not ranked

        bsr = (
            amazon_data.get("bestseller_rank") or  # Primary field from our scraper
            amazon_data.get("bsr") or
            amazon_data.get("best_seller_rank") or
            amazon_data.get("rank") or
            999999
        )

        return int(bsr) if bsr else 999999

    def _analyze_bsr_trend(self, amazon_data: Optional[Dict]) -> str:
        """Analyze if BSR is rising, stable, or falling."""
        if not amazon_data:
            return "unknown"

        # Check if from movers & shakers (trending up)
        if amazon_data.get("is_trending"):
            return "rising"

        # Check if new release (likely trending)
        if amazon_data.get("is_new_release"):
            return "rising"

        # If we have historical BSR data
        bsr_history = amazon_data.get("bsr_history", [])
        if len(bsr_history) >= 2:
            current_bsr = bsr_history[-1]
            previous_bsr = bsr_history[-2]

            # Lower BSR = better rank (rising)
            if current_bsr < previous_bsr * 0.9:
                return "rising"
            elif current_bsr > previous_bsr * 1.1:
                return "falling"
            else:
                return "stable"

        # Default to stable if no trend data
        return "stable"

    def _extract_price_range(self, amazon_data: Optional[Dict]) -> Dict[str, float]:
        """Extract price range from competing offers."""
        if not amazon_data:
            return {"min": 0.0, "max": 0.0}

        price = amazon_data.get("price", 0) or amazon_data.get("current_price", 0)
        price_min = amazon_data.get("price_min", price)
        price_max = amazon_data.get("price_max", price)

        return {
            "min": float(price_min) if price_min else 0.0,
            "max": float(price_max) if price_max else 0.0
        }

    def _calculate_weighted_score(
        self,
        seller_count: int,
        review_velocity: float,
        bsr: int,
        bsr_trend: str
    ) -> float:
        """
        Calculate weighted saturation score (0-100).

        Formula:
        - Seller count: 40% weight (more sellers = higher saturation)
        - Review velocity: 30% weight (faster reviews = higher saturation)
        - BSR: 20% weight (lower BSR = higher saturation)
        - BSR trend: 10% weight (rising = lower saturation)
        """

        # 1. Seller count score (0-100)
        # 0 sellers = 0, 50+ sellers = 100
        seller_score = min(100, seller_count * 2)

        # 2. Review velocity score (0-100)
        # 0 reviews/day = 0, 20+ reviews/day = 100
        velocity_score = min(100, review_velocity * 5)

        # 3. BSR score (0-100)
        # Top 1000 = 100 (very saturated)
        # 10,000-50,000 = 50 (moderate)
        # 100,000+ = 0 (low saturation)
        if bsr < 1000:
            bsr_score = 100
        elif bsr < 10000:
            bsr_score = 90 - ((bsr - 1000) / 9000 * 40)  # 90 to 50
        elif bsr < 50000:
            bsr_score = 50 - ((bsr - 10000) / 40000 * 50)  # 50 to 0
        else:
            bsr_score = 0

        # 4. Trend modifier (0-100)
        # Rising = lower saturation, Falling = higher saturation
        if bsr_trend == "rising":
            trend_score = 100  # Counterintuitively high because rising = more competition coming
        elif bsr_trend == "falling":
            trend_score = 30   # Falling = opportunity (less interest)
        else:  # stable
            trend_score = 50

        # Weighted average
        saturation = (
            seller_score * 0.40 +
            velocity_score * 0.30 +
            bsr_score * 0.20 +
            trend_score * 0.10
        )

        return min(100, max(0, saturation))

    def _get_recommendation(
        self,
        saturation_score: float,
        seller_count: int,
        review_velocity: float,
        bsr: int
    ) -> Tuple[str, List[str]]:
        """
        Get deployment recommendation based on saturation metrics.

        Returns:
            (recommendation, reasons)
        """
        reasons = []

        # Determine recommendation tier
        if saturation_score <= 30:
            recommendation = "deploy"
            reasons.append("✅ Blue ocean opportunity - low competition detected")

            if seller_count < 10:
                reasons.append(f"✅ Only {seller_count} competing sellers")
            if review_velocity < 2:
                reasons.append("✅ Low review velocity - market not mature")
            if bsr > 50000:
                reasons.append("✅ BSR indicates emerging niche")

        elif saturation_score <= 60:
            recommendation = "caution"
            reasons.append("⚠️  Moderate competition - proceed with caution")

            if seller_count >= 10 and seller_count < 30:
                reasons.append(f"⚠️  {seller_count} competing sellers (moderate)")
            if review_velocity >= 2 and review_velocity < 10:
                reasons.append("⚠️  Moderate review velocity - market developing")

            reasons.append("💡 Recommend: Differentiate with better images/copy/pricing")

        else:  # saturation_score > 60
            recommendation = "skip"
            reasons.append("❌ Market saturated - high risk of failure")

            if seller_count >= 30:
                reasons.append(f"❌ {seller_count} competing sellers (very high)")
            if review_velocity >= 10:
                reasons.append("❌ High review velocity - mature market")
            if bsr < 10000:
                reasons.append("❌ Strong BSR indicates established competition")

            reasons.append("💡 Recommend: Find alternative product in less saturated niche")

        return recommendation, reasons

    async def batch_score_products(
        self,
        product_names: List[str],
        max_concurrent: int = 5
    ) -> Dict[str, Dict]:
        """
        Score multiple products concurrently.

        Args:
            product_names: List of products to score
            max_concurrent: Max concurrent API calls (avoid rate limits)

        Returns:
            {
                "product_name": saturation_result,
                ...
            }
        """
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def score_with_limit(product_name: str):
            async with semaphore:
                return await self.calculate_saturation_score(product_name)

        tasks = [score_with_limit(name) for name in product_names]
        scores = await asyncio.gather(*tasks, return_exceptions=True)

        for product_name, score in zip(product_names, scores):
            if isinstance(score, Exception):
                results[product_name] = {
                    "error": str(score),
                    "saturation_score": None,
                    "recommendation": "unknown"
                }
            else:
                results[product_name] = score

        return results


# Convenience function for quick scoring
async def calculate_saturation_score(product_name: str) -> Dict:
    """
    Quick saturation check for a single product.

    Returns:
        {
            "saturation_score": float (0-100),
            "competitor_count": int,
            "recommendation": "deploy" | "caution" | "skip",
            "reasons": List[str]
        }
    """
    scorer = SaturationScorer()
    return await scorer.calculate_saturation_score(product_name)
