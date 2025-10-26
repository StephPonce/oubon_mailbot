"""Product scoring algorithm to rank product candidates."""

from typing import List, Dict
from .connectors.base import ProductCandidate


class ProductScorer:
    """
    Score and rank product candidates based on multiple signals.

    Scoring factors:
    - Trend score (Google Trends, social mentions)
    - Pricing & margins
    - Competition level
    - Supplier rating
    - Social engagement
    - Search volume
    """

    def __init__(self, weights: Dict[str, float] = None):
        """
        Initialize scorer with custom weights.

        Args:
            weights: Custom scoring weights (0-1)
        """
        self.weights = weights or {
            "trend": 0.30,  # 30% - Trending up is critical
            "margin": 0.25,  # 25% - Need good profit margins
            "competition": 0.20,  # 20% - Low competition is better
            "social": 0.15,  # 15% - Social proof matters
            "supplier": 0.10,  # 10% - Reliable supplier
        }

    def score(self, candidate: ProductCandidate, target_margin: float = 0.50) -> float:
        """
        Calculate score for a product candidate.

        Args:
            candidate: Product to score
            target_margin: Target profit margin (0-1)

        Returns:
            Score from 0-10
        """
        scores = []

        # 1. Trend Score (0-10)
        if candidate.trend_score is not None:
            trend_score = min(10, candidate.trend_score / 10)
            scores.append(("trend", trend_score))
        else:
            scores.append(("trend", 5.0))  # Neutral if no data

        # 2. Margin Score (0-10)
        if candidate.price:
            # Assume 2x markup as target (50% margin)
            # Better margins = higher score
            # TODO: Get actual sale price from Shopify comparable
            estimated_sale_price = candidate.price * 2.5
            margin = (estimated_sale_price - candidate.price) / estimated_sale_price
            margin_score = min(10, (margin / target_margin) * 10)
            scores.append(("margin", margin_score))
        else:
            scores.append(("margin", 5.0))

        # 3. Competition Score (0-10)
        competition_scores = {
            "low": 10,
            "medium": 5,
            "high": 2,
        }
        competition_score = competition_scores.get(candidate.competition_level, 5)
        scores.append(("competition", competition_score))

        # 4. Social Score (0-10)
        social_score = 5.0  # Default neutral
        if candidate.social_engagement:
            # High engagement = higher score
            # This is relative - adjust thresholds based on data
            if candidate.social_engagement > 10000:
                social_score = 10
            elif candidate.social_engagement > 5000:
                social_score = 8
            elif candidate.social_engagement > 1000:
                social_score = 6
            else:
                social_score = 4
        scores.append(("social", social_score))

        # 5. Supplier Score (0-10)
        if candidate.supplier_rating:
            supplier_score = min(10, candidate.supplier_rating * 2)
        else:
            supplier_score = 5.0
        scores.append(("supplier", supplier_score))

        # Calculate weighted average
        weighted_score = sum(
            score * self.weights.get(factor, 0)
            for factor, score in scores
        )

        # Normalize to 0-10 scale
        final_score = weighted_score / sum(self.weights.values()) if sum(self.weights.values()) > 0 else 0

        return round(final_score, 2)

    def rank(self, candidates: List[ProductCandidate], limit: int = 10) -> List[Dict]:
        """
        Score and rank multiple product candidates.

        Args:
            candidates: List of products to rank
            limit: Max results to return

        Returns:
            Ranked list of products with scores
        """
        scored = []

        for candidate in candidates:
            score = self.score(candidate)
            scored.append({
                "product": candidate.to_dict(),
                "score": score,
                "recommendation": self._get_recommendation(score),
            })

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)

        return scored[:limit]

    def _get_recommendation(self, score: float) -> str:
        """Get recommendation text based on score."""
        if score >= 8.0:
            return "🔥 Strong Buy - High potential winner"
        elif score >= 6.5:
            return "✅ Good - Worth testing"
        elif score >= 5.0:
            return "⚠️ Maybe - Test with small budget"
        else:
            return "❌ Pass - Low potential"

    def explain_score(self, candidate: ProductCandidate) -> Dict:
        """
        Get detailed scoring breakdown.

        Returns:
            {
                "total_score": float,
                "factors": {
                    "trend": {"score": float, "weight": float},
                    "margin": {"score": float, "weight": float},
                    ...
                }
            }
        """
        # Recalculate with breakdown
        score = self.score(candidate)

        return {
            "total_score": score,
            "recommendation": self._get_recommendation(score),
            "factors": {
                "trend": {
                    "score": min(10, (candidate.trend_score or 50) / 10),
                    "weight": self.weights["trend"],
                    "value": candidate.trend_score,
                },
                "margin": {
                    "score": 5.0,  # TODO: Calculate actual margin
                    "weight": self.weights["margin"],
                    "value": None,
                },
                "competition": {
                    "score": {"low": 10, "medium": 5, "high": 2}.get(candidate.competition_level, 5),
                    "weight": self.weights["competition"],
                    "value": candidate.competition_level,
                },
                "social": {
                    "score": 5.0,  # TODO: Calculate from engagement
                    "weight": self.weights["social"],
                    "value": candidate.social_engagement,
                },
                "supplier": {
                    "score": (candidate.supplier_rating or 2.5) * 2,
                    "weight": self.weights["supplier"],
                    "value": candidate.supplier_rating,
                },
            },
        }
