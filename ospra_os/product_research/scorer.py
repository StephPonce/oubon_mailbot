"""Product scoring algorithm to rank product candidates."""

from typing import List, Dict
from .connectors.base import ProductCandidate


class ProductScorer:
    """
    Score and rank product candidates based on multiple signals.

    NEW SCORING MODEL (matches user requirements):
    - Demand (40%): Reddit mentions + Google search volume
    - Sentiment (30%): Social engagement + community reaction
    - Trend Direction (30%): Google Trends trajectory + momentum
    """

    def __init__(self, weights: Dict[str, float] = None):
        """
        Initialize scorer with custom weights.

        Args:
            weights: Custom scoring weights (0-1)
        """
        self.weights = weights or {
            "demand": 0.40,      # 40% - Market demand signals
            "sentiment": 0.30,   # 30% - Community sentiment
            "trend": 0.30,       # 30% - Trend direction
        }

    def score(self, candidate: ProductCandidate, target_margin: float = 0.50) -> float:
        """
        Calculate score for a product candidate.

        NEW SCORING MODEL:
        - Demand (40%): Reddit mentions + search volume
        - Sentiment (30%): Engagement quality + community reaction
        - Trend (30%): Google Trends direction + momentum

        Args:
            candidate: Product to score

        Returns:
            Score from 0-10
        """
        scores = {}

        # 1. DEMAND SCORE (0-10) - 40% weight
        # Combines Reddit mentions and search volume
        demand_score = 0.0

        # Reddit mentions (upvotes) - max 5 points
        if candidate.social_mentions and candidate.social_mentions > 0:
            if candidate.social_mentions >= 1000:
                demand_score += 5.0
            elif candidate.social_mentions >= 500:
                demand_score += 4.0
            elif candidate.social_mentions >= 100:
                demand_score += 3.0
            elif candidate.social_mentions >= 50:
                demand_score += 2.0
            else:
                demand_score += 1.0

        # Search volume (Google Trends) - max 5 points
        if candidate.search_volume and candidate.search_volume > 0:
            if candidate.search_volume >= 80:
                demand_score += 5.0
            elif candidate.search_volume >= 60:
                demand_score += 4.0
            elif candidate.search_volume >= 40:
                demand_score += 3.0
            elif candidate.search_volume >= 20:
                demand_score += 2.0
            else:
                demand_score += 1.0

        # If no data, use conservative score
        if demand_score == 0:
            demand_score = 3.0  # Conservative default

        scores["demand"] = min(10, demand_score)

        # 2. SENTIMENT SCORE (0-10) - 30% weight
        # Measures community engagement quality
        sentiment_score = 0.0

        # Comments/engagement - max 5 points
        if candidate.social_engagement and candidate.social_engagement > 0:
            if candidate.social_engagement >= 200:
                sentiment_score += 5.0
            elif candidate.social_engagement >= 100:
                sentiment_score += 4.0
            elif candidate.social_engagement >= 50:
                sentiment_score += 3.0
            elif candidate.social_engagement >= 20:
                sentiment_score += 2.0
            else:
                sentiment_score += 1.0

        # Engagement ratio (engagement score from Reddit) - max 5 points
        # Reddit connector calculates this as weighted score
        if candidate.trend_score and candidate.source == "reddit":
            # Reddit trend_score is engagement score (0-1000+)
            if candidate.trend_score >= 500:
                sentiment_score += 5.0
            elif candidate.trend_score >= 250:
                sentiment_score += 4.0
            elif candidate.trend_score >= 100:
                sentiment_score += 3.0
            elif candidate.trend_score >= 50:
                sentiment_score += 2.0
            else:
                sentiment_score += 1.0

        # If no data, use conservative score
        if sentiment_score == 0:
            sentiment_score = 4.0  # Slightly below neutral

        scores["sentiment"] = min(10, sentiment_score)

        # 3. TREND DIRECTION SCORE (0-10) - 30% weight
        # Google Trends trajectory
        trend_score = 0.0

        if candidate.trend_score and candidate.source == "google_trends":
            # Google Trends returns 0-100 trend score
            if candidate.trend_score >= 80:
                trend_score = 10.0
            elif candidate.trend_score >= 60:
                trend_score = 8.0
            elif candidate.trend_score >= 40:
                trend_score = 6.0
            elif candidate.trend_score >= 20:
                trend_score = 4.0
            else:
                trend_score = 2.0
        elif candidate.search_volume:
            # Use search volume as proxy if trend_score not available
            trend_score = min(10, candidate.search_volume / 10)
        else:
            # No trend data - conservative score
            trend_score = 3.0

        scores["trend"] = trend_score

        # Calculate weighted average
        weighted_score = sum(
            scores[factor] * self.weights[factor]
            for factor in scores
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
            Ranked list of products with scores and priority labels
        """
        scored = []

        for candidate in candidates:
            score = self.score(candidate)
            scored.append({
                "product": candidate.to_dict(),
                "score": score,
                "priority": self.get_priority_label(score),
                "recommendation": self._get_recommendation(score),
            })

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)

        return scored[:limit]

    def _get_recommendation(self, score: float) -> str:
        """Get recommendation text based on score with priority labels."""
        if score >= 7.0:
            return "🔥 HIGH PRIORITY - Strong demand and trending"
        elif score >= 5.0:
            return "✅ MEDIUM PRIORITY - Worth testing with small budget"
        else:
            return "⚠️ LOW PRIORITY - Weak signals, high risk"

    def get_priority_label(self, score: float) -> str:
        """Get priority label (HIGH/MEDIUM/LOW) based on score."""
        if score >= 7.0:
            return "HIGH"
        elif score >= 5.0:
            return "MEDIUM"
        else:
            return "LOW"

    def explain_score(self, candidate: ProductCandidate) -> Dict:
        """
        Get detailed scoring breakdown.

        Returns:
            {
                "total_score": float,
                "priority": str,
                "factors": {
                    "demand": {"score": float, "weight": float, "details": str},
                    "sentiment": {"score": float, "weight": float, "details": str},
                    "trend": {"score": float, "weight": float, "details": str}
                }
            }
        """
        # Calculate scores manually for breakdown
        scores = {}

        # Demand
        demand = 0.0
        if candidate.social_mentions and candidate.social_mentions > 0:
            demand += min(5, candidate.social_mentions / 200)  # Scale mentions
        if candidate.search_volume and candidate.search_volume > 0:
            demand += min(5, candidate.search_volume / 16)  # Scale volume
        demand = max(3.0, demand) if demand == 0 else min(10, demand)
        scores["demand"] = demand

        # Sentiment
        sentiment = 0.0
        if candidate.social_engagement:
            sentiment += min(5, candidate.social_engagement / 40)
        if candidate.trend_score and candidate.source == "reddit":
            sentiment += min(5, candidate.trend_score / 100)
        sentiment = max(4.0, sentiment) if sentiment == 0 else min(10, sentiment)
        scores["sentiment"] = sentiment

        # Trend
        if candidate.trend_score and candidate.source == "google_trends":
            trend = min(10, candidate.trend_score / 10)
        elif candidate.search_volume:
            trend = min(10, candidate.search_volume / 10)
        else:
            trend = 3.0
        scores["trend"] = trend

        total = sum(scores[k] * self.weights[k] for k in scores)

        return {
            "total_score": round(total, 2),
            "priority": self.get_priority_label(total),
            "recommendation": self._get_recommendation(total),
            "factors": {
                "demand": {
                    "score": round(scores["demand"], 2),
                    "weight": self.weights["demand"],
                    "details": f"Reddit mentions: {candidate.social_mentions or 0}, Search volume: {candidate.search_volume or 0}",
                },
                "sentiment": {
                    "score": round(scores["sentiment"], 2),
                    "weight": self.weights["sentiment"],
                    "details": f"Engagement: {candidate.social_engagement or 0} comments",
                },
                "trend": {
                    "score": round(scores["trend"], 2),
                    "weight": self.weights["trend"],
                    "details": f"Trend score: {candidate.trend_score or 'N/A'}, Source: {candidate.source}",
                },
            },
        }
