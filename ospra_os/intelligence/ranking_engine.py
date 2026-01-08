"""
Product Ranking Engine - Top 20, Movers & Fallers, Historical Tracking

Calculates composite scores and maintains daily rankings for products
based on multiple weighted factors including trends, sales, sentiment,
profit margins, and competition.
"""

from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
import logging

from ospra_os.database.multi_store_models import (
    Product, ProductIntelligence, ProductSaturation, Base
)

logger = logging.getLogger(__name__)


# Tier definitions
class RankingTier:
    ELITE = {"name": "ELITE", "emoji": "[TOP]", "range": (1, 3), "color": "#FFD700"}
    TOP = {"name": "TOP", "emoji": "[FIRST]", "range": (4, 10), "color": "#C0C0C0"}
    RISING = {"name": "RISING", "emoji": "[SECOND]", "range": (11, 20), "color": "#CD7F32"}


class RankingEngine:
    """
    Calculate and maintain product rankings based on composite scores.

    Composite Score Formula:
    - Trend Score (25%): Google Trends, TikTok momentum
    - Sales Velocity (25%): Actual sales rate
    - Social Sentiment (20%): Reddit, TikTok comments
    - Profit Margin (15%): Profitability
    - Competition Score (15%): Inverse of saturation
    """

    # Scoring weights (must sum to 1.0)
    WEIGHTS = {
        "trend_score": 0.25,
        "sales_velocity": 0.25,
        "social_sentiment": 0.20,
        "profit_margin": 0.15,
        "competition_score": 0.15
    }

    def __init__(self, db_session: Session):
        self.db = db_session

    def normalize_score(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize any value to 0-100 scale"""
        if max_val == min_val:
            return 50.0
        normalized = ((value - min_val) / (max_val - min_val)) * 100
        return max(0, min(100, normalized))

    async def calculate_composite_score(self, product: Product) -> Dict:
        """
        Calculate composite score with breakdown for a single product.

        Returns:
            {
                "composite_score": 87.5,
                "breakdown": {
                    "trend_score": 92,
                    "sales_velocity": 85,
                    "social_sentiment": 88,
                    "profit_margin": 78,
                    "competition_score": 82
                }
            }
        """
        # Get product intelligence
        intelligence = self.db.query(ProductIntelligence).filter(
            ProductIntelligence.asin == str(product.id)
        ).first()

        # Get saturation data
        saturation = self.db.query(ProductSaturation).filter(
            ProductSaturation.product_name == product.product_name
        ).first()

        # Component 1: Trend Score (0-100)
        trend_score = product.trend_score if product.trend_score else 50.0
        if intelligence and intelligence.momentum_score:
            trend_score = intelligence.momentum_score

        # Component 2: Sales Velocity (convert to 0-100)
        # Use total_sales as proxy for velocity
        sales_velocity = min(100, (product.total_sales or 0) / 10) if product.total_sales else 0

        # Component 3: Social Sentiment (using opportunity score from intelligence)
        social_sentiment = intelligence.opportunity_score if intelligence else 50.0

        # Component 4: Profit Margin (already percentage, normalize to 0-100)
        profit_margin = min(100, (product.profit_margin or 0) * 2) if product.profit_margin else 50.0

        # Component 5: Competition Score (inverse of saturation)
        if saturation:
            # High saturation = low competition score
            saturation_percent = (saturation.total_users_count / (saturation.saturation_threshold or 100)) * 100
            competition_score = max(0, 100 - saturation_percent)
        else:
            competition_score = 100.0  # No saturation data = good opportunity

        # Calculate weighted composite score
        composite_score = (
            (trend_score * self.WEIGHTS["trend_score"]) +
            (sales_velocity * self.WEIGHTS["sales_velocity"]) +
            (social_sentiment * self.WEIGHTS["social_sentiment"]) +
            (profit_margin * self.WEIGHTS["profit_margin"]) +
            (competition_score * self.WEIGHTS["competition_score"])
        )

        return {
            "composite_score": round(composite_score, 2),
            "breakdown": {
                "trend_score": round(trend_score, 1),
                "sales_velocity": round(sales_velocity, 1),
                "social_sentiment": round(social_sentiment, 1),
                "profit_margin": round(profit_margin, 1),
                "competition_score": round(competition_score, 1)
            }
        }

    async def generate_daily_rankings(self, store_id: Optional[int] = None, niche: Optional[str] = None) -> List[Dict]:
        """
        Generate rankings for all products.

        Args:
            store_id: Filter by store (optional)
            niche: Filter by niche (optional)

        Returns:
            List of products with rankings, sorted by composite score
        """
        # Build query
        query = self.db.query(Product).filter(
            Product.status.in_(["active", "deployed"])
        )

        if store_id:
            query = query.filter(Product.store_id == store_id)

        products = query.all()

        # Calculate scores for all products
        ranked_products = []
        for product in products:
            score_data = await self.calculate_composite_score(product)

            ranked_products.append({
                "product_id": product.id,
                "product_name": product.product_name,
                "composite_score": score_data["composite_score"],
                "score_breakdown": score_data["breakdown"],
                "store_id": product.store_id,
                "source_url": product.source_url,
                "selling_price": product.selling_price,
                "profit_margin": product.profit_margin
            })

        # Sort by composite score (highest first)
        ranked_products.sort(key=lambda x: x["composite_score"], reverse=True)

        # Add rank numbers
        for idx, product in enumerate(ranked_products, start=1):
            product["rank"] = idx
            product["tier"] = self._get_tier(idx)

        return ranked_products

    def _get_tier(self, rank: int) -> Dict:
        """Get tier information for a rank"""
        if RankingTier.ELITE["range"][0] <= rank <= RankingTier.ELITE["range"][1]:
            return RankingTier.ELITE
        elif RankingTier.TOP["range"][0] <= rank <= RankingTier.TOP["range"][1]:
            return RankingTier.TOP
        elif RankingTier.RISING["range"][0] <= rank <= RankingTier.RISING["range"][1]:
            return RankingTier.RISING
        else:
            return {"name": "UNRANKED", "emoji": "[STATS]", "range": (21, 9999), "color": "#808080"}

    async def get_current_rankings(self, limit: int = 20, store_id: Optional[int] = None) -> List[Dict]:
        """Get current top N products"""
        all_rankings = await self.generate_daily_rankings(store_id=store_id)
        return all_rankings[:limit]

    async def get_biggest_gainers(self, limit: int = 10, timeframe: str = "24h") -> List[Dict]:
        """
        Get products with biggest positive rank changes.

        Note: This is a simplified version. Full implementation would
        compare against historical RankingHistory table.
        """
        # For now, return products with highest trend scores
        # In full implementation, this would compare today's rank vs yesterday's

        # Get all products and rank them, then return top movers
        all_rankings = await self.generate_daily_rankings()

        # Filter for products with high trend scores
        gainers = [p for p in all_rankings if p.get("score_breakdown", {}).get("trend_score", 0) > 70]
        gainers.sort(key=lambda x: x.get("score_breakdown", {}).get("trend_score", 0), reverse=True)

        result = []
        for product in gainers[:limit]:
            result.append({
                "product_id": product["product_id"],
                "product_name": product["product_name"],
                "composite_score": product["composite_score"],
                "rank": product["rank"],
                "rank_change": "",  # Placeholder until we have history
                "trend_direction": "up",
                "trend_score": product.get("score_breakdown", {}).get("trend_score", 0)
            })

        return result

    async def get_biggest_losers(self, limit: int = 10, timeframe: str = "24h") -> List[Dict]:
        """
        Get products with biggest negative rank changes.

        Note: Simplified version.
        """
        # Return products with lowest scores
        all_rankings = await self.generate_daily_rankings()
        losers = [p for p in all_rankings if p["composite_score"] < 50]
        losers.sort(key=lambda x: x["composite_score"])

        return losers[:limit]

    async def get_product_rank_details(self, product_id: int) -> Optional[Dict]:
        """Get detailed ranking info for a single product"""
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return None

        score_data = await self.calculate_composite_score(product)
        all_rankings = await self.generate_daily_rankings(store_id=product.store_id)

        # Find product's current rank
        current_rank = None
        for ranked_product in all_rankings:
            if ranked_product["product_id"] == product_id:
                current_rank = ranked_product["rank"]
                break

        return {
            "product_id": product.id,
            "product_name": product.product_name,
            "current_rank": current_rank,
            "composite_score": score_data["composite_score"],
            "score_breakdown": score_data["breakdown"],
            "tier": self._get_tier(current_rank) if current_rank else None,
            "selling_price": product.selling_price,
            "profit_margin": product.profit_margin,
            "total_sales": product.total_sales,
            "total_revenue": product.total_revenue
        }


logger.info("[SUCCESS] RankingEngine initialized")
