"""
GRADE REASONING ENGINE - TRANSPARENT PRODUCT SCORING

Provides transparent, explainable product grades with detailed breakdowns.

Key features:
- Letter grades (A+, A, B+, B, C+, C, D, F)
- Detailed breakdown showing WHY each score
- Weighted factors (profit potential 30%, trend score 25%, etc.)
- Historical grade tracking
- Comparison to category average
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class GradeReasoningEngine:
    """
    Calculates product grades with full transparency.

    Grade Breakdown (100 points total):
    - Profit Potential: 30 points (margin × expected volume)
    - Trend Score: 25 points (velocity, social signals)
    - Market Saturation: 20 points (lower = better)
    - Quality Indicators: 15 points (rating, reviews, complaints)
    - Competitive Edge: 10 points (vs competitors)
    """

    # Grade thresholds
    GRADE_THRESHOLDS = {
        "A+": 95,
        "A": 90,
        "A-": 85,
        "B+": 80,
        "B": 75,
        "B-": 70,
        "C+": 65,
        "C": 60,
        "C-": 55,
        "D": 50,
        "F": 0
    }

    # Weight for each factor (must sum to 1.0)
    WEIGHTS = {
        "profit_potential": 0.30,
        "trend_score": 0.25,
        "market_saturation": 0.20,
        "quality": 0.15,
        "competitive_edge": 0.10
    }

    def __init__(self, db: Session):
        self.db = db

    async def calculate_product_grade(
        self,
        product_id: int,
        product_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive product grade with full breakdown.

        Args:
            product_id: Product ID
            product_data: Optional pre-fetched product data

        Returns:
            {
                "product_id": 123,
                "grade": "A",
                "score": 92.5,
                "breakdown": {
                    "profit_potential": {"score": 28, "max": 30, "percentage": 93.3, "details": "..."},
                    "trend_score": {"score": 23, "max": 25, "percentage": 92.0, "details": "..."},
                    ...
                },
                "strengths": ["High profit margin", "Strong trend velocity"],
                "weaknesses": ["High market saturation"],
                "recommendation": "Deploy immediately - strong performer",
                "timestamp": "2025-11-27T..."
            }
        """
        logger.info(f"Calculating grade for product {product_id}")

        # Get product data (from cache or DB)
        if not product_data:
            product_data = await self._get_product_data(product_id)

        # Calculate each factor
        profit_score = self._calculate_profit_potential(product_data)
        trend_score = self._calculate_trend_score(product_data)
        saturation_score = self._calculate_saturation_score(product_data)
        quality_score = self._calculate_quality_score(product_data)
        competitive_score = self._calculate_competitive_edge(product_data)

        # Calculate weighted total
        total_score = (
            profit_score["score"] +
            trend_score["score"] +
            saturation_score["score"] +
            quality_score["score"] +
            competitive_score["score"]
        )

        # Convert to letter grade
        letter_grade = self._score_to_letter(total_score)

        # Identify strengths and weaknesses
        strengths = self._identify_strengths([
            profit_score, trend_score, saturation_score, quality_score, competitive_score
        ])
        weaknesses = self._identify_weaknesses([
            profit_score, trend_score, saturation_score, quality_score, competitive_score
        ])

        # Generate recommendation
        recommendation = self._generate_recommendation(
            letter_grade, total_score, strengths, weaknesses
        )

        return {
            "product_id": product_id,
            "product_title": product_data.get("title", "Unknown"),
            "grade": letter_grade,
            "score": round(total_score, 1),
            "breakdown": {
                "profit_potential": profit_score,
                "trend_score": trend_score,
                "market_saturation": saturation_score,
                "quality": quality_score,
                "competitive_edge": competitive_score
            },
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendation": recommendation,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _calculate_profit_potential(self, product: Dict) -> Dict[str, Any]:
        """
        Calculate profit potential score (max 30 points).

        Factors:
        - Profit margin (0-50%)
        - Expected monthly volume (estimated sales)
        - Price point (sweet spot: $20-$80)
        """
        max_score = 30

        margin = product.get("profit_margin", 0) or 0
        price = product.get("price", 0) or 0
        expected_volume = product.get("expected_monthly_sales", 0) or 0

        # Score components
        margin_score = min(margin / 50 * 15, 15)  # 15 points max
        volume_score = min(expected_volume / 100 * 10, 10)  # 10 points max

        # Price point bonus (sweet spot: $20-$80)
        if 20 <= price <= 80:
            price_score = 5
        elif 10 <= price < 20 or 80 < price <= 150:
            price_score = 3
        else:
            price_score = 1

        total = margin_score + volume_score + price_score
        percentage = (total / max_score) * 100

        # Details explanation
        details = f"Margin: {margin:.1f}% ({margin_score:.1f}/15) | "
        details += f"Volume: {expected_volume}/mo ({volume_score:.1f}/10) | "
        details += f"Price: ${price:.2f} ({price_score}/5)"

        return {
            "score": round(total, 1),
            "max": max_score,
            "percentage": round(percentage, 1),
            "details": details,
            "components": {
                "margin": round(margin_score, 1),
                "volume": round(volume_score, 1),
                "price_point": price_score
            }
        }

    def _calculate_trend_score(self, product: Dict) -> Dict[str, Any]:
        """
        Calculate trend score (max 25 points).

        Factors:
        - Velocity score (0-10 scale from velocity detector)
        - Social signals (TikTok/Instagram mentions)
        - Search trend (Google Trends data)
        """
        max_score = 25

        velocity = product.get("velocity_score", 0) or 0
        social_score = product.get("social_score", 0) or 0
        search_trend = product.get("search_trend", 0) or 0

        # Score components
        velocity_score = min(velocity * 1.5, 15)  # 15 points max
        social_points = min(social_score / 10 * 6, 6)  # 6 points max
        search_points = min(search_trend / 100 * 4, 4)  # 4 points max

        total = velocity_score + social_points + search_points
        percentage = (total / max_score) * 100

        details = f"Velocity: {velocity}/10 ({velocity_score:.1f}/15) | "
        details += f"Social: {social_score}/100 ({social_points:.1f}/6) | "
        details += f"Search: {search_trend}/100 ({search_points:.1f}/4)"

        return {
            "score": round(total, 1),
            "max": max_score,
            "percentage": round(percentage, 1),
            "details": details,
            "components": {
                "velocity": round(velocity_score, 1),
                "social": round(social_points, 1),
                "search": round(search_points, 1)
            }
        }

    def _calculate_saturation_score(self, product: Dict) -> Dict[str, Any]:
        """
        Calculate market saturation score (max 20 points).

        Lower saturation = higher score.

        Factors:
        - Competitor count (fewer = better)
        - Market entry rate (slower = better)
        - Product differentiation (more unique = better)
        """
        max_score = 20

        saturation_level = product.get("saturation_level", 50) or 50  # 0-100
        competitor_count = product.get("competitor_count", 0) or 0
        differentiation = product.get("differentiation_score", 0) or 0

        # Invert saturation (low saturation = high score)
        saturation_points = ((100 - saturation_level) / 100) * 10  # 10 points max

        # Competitor penalty
        if competitor_count < 5:
            competitor_points = 6
        elif competitor_count < 20:
            competitor_points = 4
        elif competitor_count < 50:
            competitor_points = 2
        else:
            competitor_points = 0

        # Differentiation bonus
        diff_points = min(differentiation / 10 * 4, 4)  # 4 points max

        total = saturation_points + competitor_points + diff_points
        percentage = (total / max_score) * 100

        details = f"Saturation: {100-saturation_level:.0f}% open ({saturation_points:.1f}/10) | "
        details += f"Competitors: {competitor_count} ({competitor_points}/6) | "
        details += f"Unique: {differentiation}/10 ({diff_points:.1f}/4)"

        return {
            "score": round(total, 1),
            "max": max_score,
            "percentage": round(percentage, 1),
            "details": details,
            "components": {
                "saturation": round(saturation_points, 1),
                "competitors": competitor_points,
                "differentiation": round(diff_points, 1)
            }
        }

    def _calculate_quality_score(self, product: Dict) -> Dict[str, Any]:
        """
        Calculate quality score (max 15 points).

        Factors:
        - Product rating (0-5 stars)
        - Review count (more = better, up to threshold)
        - Complaint rate (lower = better)
        """
        max_score = 15

        rating = product.get("rating", 0) or 0
        review_count = product.get("review_count", 0) or 0
        complaint_rate = product.get("complaint_rate", 0) or 0

        # Rating score
        rating_score = (rating / 5) * 8  # 8 points max

        # Review count (logarithmic scale)
        if review_count >= 100:
            review_score = 4
        elif review_count >= 50:
            review_score = 3
        elif review_count >= 20:
            review_score = 2
        else:
            review_score = 1

        # Complaint penalty (inverted)
        complaint_score = max(0, 3 - (complaint_rate * 10))  # 3 points max

        total = rating_score + review_score + complaint_score
        percentage = (total / max_score) * 100

        details = f"Rating: {rating:.1f}/5 ({rating_score:.1f}/8) | "
        details += f"Reviews: {review_count} ({review_score}/4) | "
        details += f"Complaints: {complaint_rate*100:.1f}% ({complaint_score:.1f}/3)"

        return {
            "score": round(total, 1),
            "max": max_score,
            "percentage": round(percentage, 1),
            "details": details,
            "components": {
                "rating": round(rating_score, 1),
                "reviews": review_score,
                "complaints": round(complaint_score, 1)
            }
        }

    def _calculate_competitive_edge(self, product: Dict) -> Dict[str, Any]:
        """
        Calculate competitive edge score (max 10 points).

        Factors:
        - Price vs competitors (competitive pricing)
        - Feature superiority (better specs/features)
        - Brand strength (if branded)
        """
        max_score = 10

        price_competitiveness = product.get("price_competitiveness", 50) or 50  # 0-100
        feature_superiority = product.get("feature_superiority", 0) or 0  # 0-10
        brand_strength = product.get("brand_strength", 0) or 0  # 0-10

        # Scoring
        price_score = (price_competitiveness / 100) * 5  # 5 points max
        feature_score = (feature_superiority / 10) * 3  # 3 points max
        brand_score = (brand_strength / 10) * 2  # 2 points max

        total = price_score + feature_score + brand_score
        percentage = (total / max_score) * 100

        details = f"Price: {price_competitiveness}% competitive ({price_score:.1f}/5) | "
        details += f"Features: {feature_superiority}/10 ({feature_score:.1f}/3) | "
        details += f"Brand: {brand_strength}/10 ({brand_score:.1f}/2)"

        return {
            "score": round(total, 1),
            "max": max_score,
            "percentage": round(percentage, 1),
            "details": details,
            "components": {
                "price": round(price_score, 1),
                "features": round(feature_score, 1),
                "brand": round(brand_score, 1)
            }
        }

    def _score_to_letter(self, score: float) -> str:
        """Convert numerical score to letter grade"""
        for grade, threshold in self.GRADE_THRESHOLDS.items():
            if score >= threshold:
                return grade
        return "F"

    def _identify_strengths(self, scores: List[Dict]) -> List[str]:
        """Identify product strengths (scores above 80%)"""
        strengths = []
        labels = ["Profit potential", "Trend momentum", "Low competition", "High quality", "Competitive edge"]

        for i, score_data in enumerate(scores):
            if score_data["percentage"] >= 80:
                strengths.append(f"{labels[i]} ({score_data['percentage']:.0f}%)")

        return strengths

    def _identify_weaknesses(self, scores: List[Dict]) -> List[str]:
        """Identify product weaknesses (scores below 60%)"""
        weaknesses = []
        labels = ["Profit potential", "Trend momentum", "Market saturation", "Quality concerns", "Competitive edge"]

        for i, score_data in enumerate(scores):
            if score_data["percentage"] < 60:
                weaknesses.append(f"{labels[i]} ({score_data['percentage']:.0f}%)")

        return weaknesses

    def _generate_recommendation(
        self,
        grade: str,
        score: float,
        strengths: List[str],
        weaknesses: List[str]
    ) -> str:
        """Generate actionable recommendation based on grade"""

        if grade in ["A+", "A", "A-"]:
            return "Deploy immediately - strong performer across all metrics"

        elif grade in ["B+", "B"]:
            if "Profit potential" in str(strengths):
                return "Deploy with ads - good product that needs visibility"
            else:
                return "Monitor closely - solid product but watch margins"

        elif grade in ["B-", "C+", "C"]:
            if weaknesses:
                return f"Address weaknesses before deploying: {', '.join(weaknesses[:2])}"
            else:
                return "Consider deploying but expect average performance"

        elif grade in ["C-", "D"]:
            return "Not recommended - too many red flags"

        else:  # F
            return "Do not deploy - likely to lose money"

    async def _get_product_data(self, product_id: int) -> Dict:
        """Fetch product data from database"""
        from ospra_os.database import Product

        product = self.db.query(Product).filter(Product.id == product_id).first()

        if not product:
            raise ValueError(f"Product {product_id} not found")

        return {
            "title": product.title,
            "profit_margin": product.profit_margin or 0,
            "price": product.price or 0,
            "expected_monthly_sales": product.expected_monthly_sales or 0,
            "velocity_score": product.velocity_score or 0,
            "social_score": product.social_score or 0,
            "search_trend": product.search_trend or 0,
            "saturation_level": product.saturation_level or 50,
            "competitor_count": product.competitor_count or 0,
            "differentiation_score": product.differentiation_score or 0,
            "rating": product.rating or 0,
            "review_count": product.review_count or 0,
            "complaint_rate": product.complaint_rate or 0,
            "price_competitiveness": product.price_competitiveness or 50,
            "feature_superiority": product.feature_superiority or 0,
            "brand_strength": product.brand_strength or 0
        }


# Singleton instance
_grade_engine = None


def get_grade_reasoning_engine(db: Session) -> GradeReasoningEngine:
    """Get or create grade reasoning engine instance"""
    global _grade_engine
    if _grade_engine is None:
        _grade_engine = GradeReasoningEngine(db)
    return _grade_engine
