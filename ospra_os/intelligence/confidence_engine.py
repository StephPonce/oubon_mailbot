"""
Confidence Scoring Engine

Implements GROK RECOMMENDATION #10: Confidence Scoring with transparent breakdowns.

Provides 0-100% confidence scores with detailed factor breakdowns showing exactly
WHY an AI decision has a certain confidence level. This builds trust and helps
users make informed decisions about which actions to approve.

Features:
- Transparent factor-based scoring
- Category-weighted factors (market, financial, competition, trend, etc.)
- Risk level classification (low, medium, high)
- Detailed explanations and recommendations
- User-specific weight learning integration (G4: Complete Feedback Loop)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from sqlalchemy.orm import Session


class FactorType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class FactorCategory(str, Enum):
    MARKET = "market"
    FINANCIAL = "financial"
    COMPETITION = "competition"
    TREND = "trend"
    HISTORICAL = "historical"
    RISK = "risk"
    QUALITY = "quality"


@dataclass
class ConfidenceFactor:
    """A single factor contributing to confidence score"""
    name: str
    category: FactorCategory
    value: float  # -100 to +100 contribution
    weight: float  # 0 to 1, importance of this factor
    factor_type: FactorType
    description: str
    raw_data: Optional[Dict[str, Any]] = None
    icon: str = "info"

    @property
    def weighted_value(self) -> float:
        return self.value * self.weight

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "value": round(self.value, 1),
            "weight": self.weight,
            "weighted_value": round(self.weighted_value, 1),
            "type": self.factor_type.value,
            "description": self.description,
            "icon": self.icon
        }


@dataclass
class ConfidenceScore:
    """Complete confidence score with breakdown"""
    score: float  # 0-100 final score
    base_score: float  # Starting base score
    factors: List[ConfidenceFactor] = field(default_factory=list)
    explanation: str = ""
    recommendation: str = ""
    risk_level: str = "medium"  # low, medium, high

    @property
    def positive_factors(self) -> List[ConfidenceFactor]:
        return [f for f in self.factors if f.factor_type == FactorType.POSITIVE]

    @property
    def negative_factors(self) -> List[ConfidenceFactor]:
        return [f for f in self.factors if f.factor_type == FactorType.NEGATIVE]

    @property
    def total_positive(self) -> float:
        return sum(f.weighted_value for f in self.positive_factors)

    @property
    def total_negative(self) -> float:
        return sum(f.weighted_value for f in self.negative_factors)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "base_score": self.base_score,
            "factors": [f.to_dict() for f in self.factors],
            "positive_factors": [f.to_dict() for f in self.positive_factors],
            "negative_factors": [f.to_dict() for f in self.negative_factors],
            "total_positive": round(self.total_positive, 1),
            "total_negative": round(self.total_negative, 1),
            "explanation": self.explanation,
            "recommendation": self.recommendation,
            "risk_level": self.risk_level,
            "breakdown": {
                "base": self.base_score,
                "adjustments": round(self.score - self.base_score, 1),
                "final": round(self.score, 1)
            }
        }


class ConfidenceEngine:
    """
    Engine for calculating transparent confidence scores.

    Integrates with G4 Complete Feedback Loop to use learned weights
    from real sales performance data.
    """

    # Base scores for different action types
    BASE_SCORES = {
        "deploy_product": 40,
        "adjust_price": 50,
        "pause_ad": 45,
        "resume_ad": 45,
        "drop_product": 35,
        "reply_email": 55,
        "send_refund": 40,
        "restock_alert": 50,
    }

    # Factor weights by category (defaults before learning)
    CATEGORY_WEIGHTS = {
        FactorCategory.MARKET: 1.0,
        FactorCategory.FINANCIAL: 1.2,
        FactorCategory.COMPETITION: 0.9,
        FactorCategory.TREND: 0.8,
        FactorCategory.HISTORICAL: 1.1,
        FactorCategory.RISK: 1.0,
        FactorCategory.QUALITY: 0.7,
    }

    def __init__(
        self,
        db: Optional[Session] = None,
        user_id: Optional[int] = None,
        user_weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize confidence engine with optional learning integration.

        Args:
            db: Database session for learning integration
            user_id: User ID to fetch learned weights for
            user_weights: Pre-computed user weights (if already fetched)
        """
        self.db = db
        self.user_id = user_id
        self.user_weights = user_weights or {}
        self.learning_processor = None

        # Initialize LearningProcessor if db and user_id provided
        if db and user_id:
            try:
                from ospra_os.services.learning_processor import LearningProcessor
                self.learning_processor = LearningProcessor(db)
            except ImportError:
                print("⚠️  LearningProcessor not available - using default weights")

    def get_learned_weights(self) -> Dict[str, float]:
        """
        Get learned weights for this user from the feedback loop.

        Returns weights that have been optimized based on what actually
        works for this specific user's sales history.

        Returns:
            Dict of factor weights (historical, market, margin, sentiment)
        """
        if not self.learning_processor or not self.user_id:
            # Return equal default weights
            return {
                "historical": 0.25,
                "market": 0.25,
                "margin": 0.25,
                "sentiment": 0.25
            }

        return self.learning_processor.get_weights_for_user(self.user_id)

    def get_niche_adjustment(self, niche: str) -> float:
        """
        Get score adjustment for a specific niche based on user's history.

        If user has 85% success in fitness, boost fitness scores by +10.
        If user has 20% success in home_decor, penalize by -10.

        Args:
            niche: Product niche/category

        Returns:
            Score adjustment (-10 to +10)
        """
        if not self.learning_processor or not self.user_id:
            return 0.0

        return self.learning_processor.get_niche_adjustment(self.user_id, niche)

    def calculate_product_confidence(
        self,
        product: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None,
        historical_data: Optional[Dict[str, Any]] = None
    ) -> ConfidenceScore:
        """Calculate confidence score for deploying a product"""

        factors = []
        base_score = self.BASE_SCORES["deploy_product"]

        # === FINANCIAL FACTORS ===

        # Profit Margin
        margin = product.get("profit_margin") or product.get("margin", 0)
        if margin > 0:
            margin_factor = self._calculate_margin_factor(margin)
            factors.append(margin_factor)

        # Price Point
        price = product.get("sell_price") or product.get("price", 0)
        price_factor = self._calculate_price_factor(price, product.get("niche"))
        if price_factor:
            factors.append(price_factor)

        # === MARKET FACTORS ===

        # Velocity Score
        velocity = product.get("velocity_score", 0)
        if velocity > 0:
            velocity_factor = self._calculate_velocity_factor(velocity)
            factors.append(velocity_factor)

        # Saturation Score
        saturation = product.get("saturation_score", 50)
        saturation_factor = self._calculate_saturation_factor(saturation)
        factors.append(saturation_factor)

        # === TREND FACTORS ===

        # Trend Direction
        trend = product.get("trend_direction") or product.get("trend_score", 0)
        trend_factor = self._calculate_trend_factor(trend)
        if trend_factor:
            factors.append(trend_factor)

        # Social Sentiment
        sentiment = product.get("social_sentiment", 0)
        if sentiment != 0:
            sentiment_factor = self._calculate_sentiment_factor(sentiment)
            factors.append(sentiment_factor)

        # === QUALITY FACTORS ===

        # Review Score
        reviews = product.get("review_score") or product.get("rating", 0)
        review_count = product.get("review_count", 0)
        if reviews > 0:
            review_factor = self._calculate_review_factor(reviews, review_count)
            factors.append(review_factor)

        # Image Quality
        image_score = product.get("image_quality_score", 0)
        if image_score > 0:
            image_factor = self._calculate_image_factor(image_score)
            factors.append(image_factor)

        # === HISTORICAL FACTORS ===

        if historical_data:
            # Similar Product Performance
            similar_perf = historical_data.get("similar_product_performance")
            if similar_perf:
                hist_factor = self._calculate_historical_factor(similar_perf)
                factors.append(hist_factor)

            # Niche Performance
            niche_perf = historical_data.get("niche_performance")
            if niche_perf:
                niche_factor = self._calculate_niche_factor(niche_perf, product.get("niche"))
                factors.append(niche_factor)

        # === RISK FACTORS ===

        # Supplier Reliability
        supplier_score = product.get("supplier_reliability", 0)
        if supplier_score > 0:
            supplier_factor = self._calculate_supplier_factor(supplier_score)
            factors.append(supplier_factor)

        # Shipping Time Risk
        shipping_days = product.get("shipping_days", 0)
        if shipping_days > 0:
            shipping_factor = self._calculate_shipping_factor(shipping_days)
            factors.append(shipping_factor)

        # Calculate final score (with niche adjustment from learned data)
        product_niche = product.get("niche") or product.get("category")
        return self._finalize_score(base_score, factors, "deploy_product", product_niche=product_niche)

    def calculate_price_adjustment_confidence(
        self,
        current_price: float,
        new_price: float,
        supplier_change: float,
        competitor_prices: Optional[List[float]] = None,
        historical_elasticity: Optional[float] = None
    ) -> ConfidenceScore:
        """Calculate confidence for a price adjustment"""

        factors = []
        base_score = self.BASE_SCORES["adjust_price"]

        price_change_pct = ((new_price - current_price) / current_price) * 100

        # Margin Protection
        factors.append(ConfidenceFactor(
            name="Margin Protection",
            category=FactorCategory.FINANCIAL,
            value=15 if supplier_change > 0 else 10,
            weight=1.0,
            factor_type=FactorType.POSITIVE,
            description=f"Adjusting to maintain margins after {supplier_change:+.1f}% supplier change",
            icon="shield"
        ))

        # Price Increase Risk
        if price_change_pct > 10:
            factors.append(ConfidenceFactor(
                name="Large Price Increase",
                category=FactorCategory.RISK,
                value=-min(15, price_change_pct / 2),
                weight=1.0,
                factor_type=FactorType.NEGATIVE,
                description=f"{price_change_pct:.1f}% increase may impact sales",
                icon="trending-up"
            ))

        # Competitor Comparison
        if competitor_prices:
            avg_competitor = sum(competitor_prices) / len(competitor_prices)
            if new_price <= avg_competitor:
                factors.append(ConfidenceFactor(
                    name="Competitive Pricing",
                    category=FactorCategory.COMPETITION,
                    value=12,
                    weight=0.9,
                    factor_type=FactorType.POSITIVE,
                    description=f"New price ${new_price:.2f} is at or below market avg ${avg_competitor:.2f}",
                    icon="check"
                ))
            else:
                premium_pct = ((new_price - avg_competitor) / avg_competitor) * 100
                factors.append(ConfidenceFactor(
                    name="Premium Pricing",
                    category=FactorCategory.COMPETITION,
                    value=-min(10, premium_pct / 2),
                    weight=0.9,
                    factor_type=FactorType.NEGATIVE,
                    description=f"Price {premium_pct:.1f}% above market average",
                    icon="alert-triangle"
                ))

        # Historical Elasticity
        if historical_elasticity is not None:
            if historical_elasticity < 1:  # Inelastic
                factors.append(ConfidenceFactor(
                    name="Low Price Sensitivity",
                    category=FactorCategory.HISTORICAL,
                    value=10,
                    weight=1.1,
                    factor_type=FactorType.POSITIVE,
                    description="Historical data shows customers are not price-sensitive",
                    icon="thumbs-up"
                ))
            else:  # Elastic
                factors.append(ConfidenceFactor(
                    name="High Price Sensitivity",
                    category=FactorCategory.HISTORICAL,
                    value=-8,
                    weight=1.1,
                    factor_type=FactorType.NEGATIVE,
                    description="Historical data shows price increases reduce sales",
                    icon="thumbs-down"
                ))

        return self._finalize_score(base_score, factors, "adjust_price")

    def calculate_ad_pause_confidence(
        self,
        roas: float,
        spend: float,
        conversions: int,
        days_running: int,
        ctr: Optional[float] = None,
        cpc: Optional[float] = None
    ) -> ConfidenceScore:
        """Calculate confidence for pausing an ad"""

        factors = []
        base_score = self.BASE_SCORES["pause_ad"]

        # ROAS Factor (main driver)
        if roas < 1.0:
            roas_penalty = min(25, (1.0 - roas) * 50)
            factors.append(ConfidenceFactor(
                name="ROAS Below Target",
                category=FactorCategory.FINANCIAL,
                value=roas_penalty,
                weight=1.2,
                factor_type=FactorType.POSITIVE,  # Positive for pausing
                description=f"ROAS is {roas:.2f}x, below 1.0x breakeven",
                icon="trending-down"
            ))
        elif roas < 1.5:
            factors.append(ConfidenceFactor(
                name="ROAS Below Optimal",
                category=FactorCategory.FINANCIAL,
                value=10,
                weight=1.0,
                factor_type=FactorType.POSITIVE,
                description=f"ROAS is {roas:.2f}x, below 1.5x target",
                icon="alert-triangle"
            ))
        else:
            factors.append(ConfidenceFactor(
                name="ROAS is Healthy",
                category=FactorCategory.FINANCIAL,
                value=-20,
                weight=1.2,
                factor_type=FactorType.NEGATIVE,
                description=f"ROAS is {roas:.2f}x, campaign is profitable",
                icon="check"
            ))

        # Spend Factor
        if spend > 100 and conversions < 3:
            factors.append(ConfidenceFactor(
                name="High Spend, Low Conversions",
                category=FactorCategory.FINANCIAL,
                value=15,
                weight=1.0,
                factor_type=FactorType.POSITIVE,
                description=f"${spend:.0f} spent with only {conversions} conversions",
                icon="dollar-sign"
            ))

        # CTR Factor
        if ctr is not None:
            if ctr < 0.5:
                factors.append(ConfidenceFactor(
                    name="Low Click-Through Rate",
                    category=FactorCategory.QUALITY,
                    value=10,
                    weight=0.8,
                    factor_type=FactorType.POSITIVE,
                    description=f"CTR is {ctr:.2f}%, below 0.5% threshold",
                    icon="mouse-pointer"
                ))
            elif ctr > 2.0:
                factors.append(ConfidenceFactor(
                    name="Strong Click-Through Rate",
                    category=FactorCategory.QUALITY,
                    value=-8,
                    weight=0.8,
                    factor_type=FactorType.NEGATIVE,
                    description=f"CTR is {ctr:.2f}%, ad creative is working",
                    icon="mouse-pointer"
                ))

        # Learning Period
        if days_running < 7:
            factors.append(ConfidenceFactor(
                name="Still in Learning Period",
                category=FactorCategory.RISK,
                value=-12,
                weight=1.0,
                factor_type=FactorType.NEGATIVE,
                description=f"Only {days_running} days of data, may need more time",
                icon="clock"
            ))

        return self._finalize_score(base_score, factors, "pause_ad")

    # === FACTOR CALCULATION HELPERS ===

    def _calculate_margin_factor(self, margin: float) -> ConfidenceFactor:
        """Calculate confidence factor for profit margin"""

        if margin >= 60:
            return ConfidenceFactor(
                name="Excellent Margin",
                category=FactorCategory.FINANCIAL,
                value=20,
                weight=1.2,
                factor_type=FactorType.POSITIVE,
                description=f"{margin:.0f}% profit margin is exceptional",
                icon="dollar-sign"
            )
        elif margin >= 45:
            return ConfidenceFactor(
                name="Strong Margin",
                category=FactorCategory.FINANCIAL,
                value=15,
                weight=1.2,
                factor_type=FactorType.POSITIVE,
                description=f"{margin:.0f}% margin provides healthy profit",
                icon="dollar-sign"
            )
        elif margin >= 30:
            return ConfidenceFactor(
                name="Acceptable Margin",
                category=FactorCategory.FINANCIAL,
                value=8,
                weight=1.0,
                factor_type=FactorType.POSITIVE,
                description=f"{margin:.0f}% margin meets minimum threshold",
                icon="dollar-sign"
            )
        else:
            return ConfidenceFactor(
                name="Low Margin",
                category=FactorCategory.FINANCIAL,
                value=-10,
                weight=1.2,
                factor_type=FactorType.NEGATIVE,
                description=f"{margin:.0f}% margin may not cover costs",
                icon="alert-triangle"
            )

    def _calculate_velocity_factor(self, velocity: float) -> ConfidenceFactor:
        """Calculate confidence factor for sales velocity"""

        if velocity >= 85:
            return ConfidenceFactor(
                name="High Demand Velocity",
                category=FactorCategory.MARKET,
                value=18,
                weight=1.0,
                factor_type=FactorType.POSITIVE,
                description=f"Velocity score {velocity:.0f} indicates strong demand",
                icon="zap"
            )
        elif velocity >= 70:
            return ConfidenceFactor(
                name="Good Demand",
                category=FactorCategory.MARKET,
                value=12,
                weight=1.0,
                factor_type=FactorType.POSITIVE,
                description=f"Velocity score {velocity:.0f} shows steady demand",
                icon="trending-up"
            )
        elif velocity >= 50:
            return ConfidenceFactor(
                name="Moderate Demand",
                category=FactorCategory.MARKET,
                value=5,
                weight=0.8,
                factor_type=FactorType.NEUTRAL,
                description=f"Velocity score {velocity:.0f} is average",
                icon="minus"
            )
        else:
            return ConfidenceFactor(
                name="Low Demand",
                category=FactorCategory.MARKET,
                value=-8,
                weight=1.0,
                factor_type=FactorType.NEGATIVE,
                description=f"Velocity score {velocity:.0f} indicates weak demand",
                icon="trending-down"
            )

    def _calculate_saturation_factor(self, saturation: float) -> ConfidenceFactor:
        """Calculate confidence factor for market saturation"""

        if saturation <= 20:
            return ConfidenceFactor(
                name="Very Low Competition",
                category=FactorCategory.COMPETITION,
                value=15,
                weight=0.9,
                factor_type=FactorType.POSITIVE,
                description=f"Only {saturation:.0f}% market saturation",
                icon="target"
            )
        elif saturation <= 40:
            return ConfidenceFactor(
                name="Low Competition",
                category=FactorCategory.COMPETITION,
                value=10,
                weight=0.9,
                factor_type=FactorType.POSITIVE,
                description=f"{saturation:.0f}% saturation leaves room to compete",
                icon="users"
            )
        elif saturation <= 60:
            return ConfidenceFactor(
                name="Moderate Competition",
                category=FactorCategory.COMPETITION,
                value=0,
                weight=0.8,
                factor_type=FactorType.NEUTRAL,
                description=f"{saturation:.0f}% saturation is manageable",
                icon="users"
            )
        elif saturation <= 80:
            return ConfidenceFactor(
                name="High Competition",
                category=FactorCategory.COMPETITION,
                value=-10,
                weight=0.9,
                factor_type=FactorType.NEGATIVE,
                description=f"{saturation:.0f}% saturation means crowded market",
                icon="alert-triangle"
            )
        else:
            return ConfidenceFactor(
                name="Oversaturated Market",
                category=FactorCategory.COMPETITION,
                value=-18,
                weight=1.0,
                factor_type=FactorType.NEGATIVE,
                description=f"{saturation:.0f}% saturation — very hard to compete",
                icon="x-circle"
            )

    def _calculate_trend_factor(self, trend: float) -> Optional[ConfidenceFactor]:
        """Calculate confidence factor for trend momentum"""

        if trend > 20:
            return ConfidenceFactor(
                name="Strong Uptrend",
                category=FactorCategory.TREND,
                value=12,
                weight=0.8,
                factor_type=FactorType.POSITIVE,
                description=f"Search interest up {trend:.0f}% recently",
                icon="trending-up"
            )
        elif trend > 5:
            return ConfidenceFactor(
                name="Positive Trend",
                category=FactorCategory.TREND,
                value=6,
                weight=0.8,
                factor_type=FactorType.POSITIVE,
                description=f"Growing interest (+{trend:.0f}%)",
                icon="trending-up"
            )
        elif trend < -20:
            return ConfidenceFactor(
                name="Declining Interest",
                category=FactorCategory.TREND,
                value=-12,
                weight=0.9,
                factor_type=FactorType.NEGATIVE,
                description=f"Search interest down {abs(trend):.0f}%",
                icon="trending-down"
            )
        elif trend < -5:
            return ConfidenceFactor(
                name="Slight Decline",
                category=FactorCategory.TREND,
                value=-5,
                weight=0.7,
                factor_type=FactorType.NEGATIVE,
                description=f"Interest declining ({trend:.0f}%)",
                icon="trending-down"
            )
        return None

    def _calculate_sentiment_factor(self, sentiment: float) -> ConfidenceFactor:
        """Calculate confidence factor for social sentiment"""

        if sentiment > 0.5:
            return ConfidenceFactor(
                name="Positive Sentiment",
                category=FactorCategory.MARKET,
                value=10,
                weight=0.7,
                factor_type=FactorType.POSITIVE,
                description="Social media sentiment is positive",
                icon="heart"
            )
        elif sentiment < -0.3:
            return ConfidenceFactor(
                name="Negative Sentiment",
                category=FactorCategory.MARKET,
                value=-12,
                weight=0.8,
                factor_type=FactorType.NEGATIVE,
                description="Social media sentiment is concerning",
                icon="alert-circle"
            )
        return ConfidenceFactor(
            name="Neutral Sentiment",
            category=FactorCategory.MARKET,
            value=0,
            weight=0.5,
            factor_type=FactorType.NEUTRAL,
            description="Social sentiment is neutral",
            icon="minus"
        )

    def _calculate_review_factor(self, rating: float, count: int) -> ConfidenceFactor:
        """Calculate confidence factor for product reviews"""

        # Weight by both rating AND count
        if rating >= 4.5 and count >= 100:
            return ConfidenceFactor(
                name="Excellent Reviews",
                category=FactorCategory.QUALITY,
                value=12,
                weight=0.8,
                factor_type=FactorType.POSITIVE,
                description=f"{rating:.1f}★ from {count:,} reviews",
                icon="star"
            )
        elif rating >= 4.0 and count >= 50:
            return ConfidenceFactor(
                name="Good Reviews",
                category=FactorCategory.QUALITY,
                value=8,
                weight=0.7,
                factor_type=FactorType.POSITIVE,
                description=f"{rating:.1f}★ from {count:,} reviews",
                icon="star"
            )
        elif rating < 3.5:
            return ConfidenceFactor(
                name="Poor Reviews",
                category=FactorCategory.QUALITY,
                value=-15,
                weight=0.9,
                factor_type=FactorType.NEGATIVE,
                description=f"{rating:.1f}★ indicates quality issues",
                icon="alert-triangle"
            )
        elif count < 10:
            return ConfidenceFactor(
                name="Limited Reviews",
                category=FactorCategory.QUALITY,
                value=-5,
                weight=0.6,
                factor_type=FactorType.NEGATIVE,
                description=f"Only {count} reviews — limited data",
                icon="help-circle"
            )
        return ConfidenceFactor(
            name="Average Reviews",
            category=FactorCategory.QUALITY,
            value=3,
            weight=0.6,
            factor_type=FactorType.NEUTRAL,
            description=f"{rating:.1f}★ from {count} reviews",
            icon="star"
        )

    def _calculate_image_factor(self, score: float) -> Optional[ConfidenceFactor]:
        """Calculate confidence factor for image quality"""

        if score >= 80:
            return ConfidenceFactor(
                name="High-Quality Images",
                category=FactorCategory.QUALITY,
                value=8,
                weight=0.6,
                factor_type=FactorType.POSITIVE,
                description="Professional product photography",
                icon="image"
            )
        elif score < 50:
            return ConfidenceFactor(
                name="Poor Image Quality",
                category=FactorCategory.QUALITY,
                value=-8,
                weight=0.7,
                factor_type=FactorType.NEGATIVE,
                description="Images may hurt conversion",
                icon="image-off"
            )
        return None

    def _calculate_historical_factor(self, perf: Dict) -> ConfidenceFactor:
        """Calculate factor based on similar product performance"""

        success_rate = perf.get("success_rate", 0.5)
        sample_size = perf.get("sample_size", 0)

        if sample_size < 3:
            return ConfidenceFactor(
                name="Limited Historical Data",
                category=FactorCategory.HISTORICAL,
                value=-5,
                weight=0.8,
                factor_type=FactorType.NEGATIVE,
                description="Few similar products to compare",
                icon="database"
            )

        if success_rate >= 0.7:
            return ConfidenceFactor(
                name="Strong Historical Performance",
                category=FactorCategory.HISTORICAL,
                value=15,
                weight=1.1,
                factor_type=FactorType.POSITIVE,
                description=f"Similar products succeed {success_rate*100:.0f}% of the time",
                icon="check-circle"
            )
        elif success_rate <= 0.3:
            return ConfidenceFactor(
                name="Weak Historical Performance",
                category=FactorCategory.HISTORICAL,
                value=-12,
                weight=1.1,
                factor_type=FactorType.NEGATIVE,
                description=f"Similar products only succeed {success_rate*100:.0f}% of the time",
                icon="x-circle"
            )

        return ConfidenceFactor(
            name="Mixed Historical Results",
            category=FactorCategory.HISTORICAL,
            value=0,
            weight=0.8,
            factor_type=FactorType.NEUTRAL,
            description=f"{success_rate*100:.0f}% success rate for similar products",
            icon="minus"
        )

    def _calculate_niche_factor(self, perf: Dict, niche: str) -> Optional[ConfidenceFactor]:
        """Calculate factor based on niche performance"""

        conversion_rate = perf.get("avg_conversion", 0)
        your_rate = perf.get("your_conversion", 0)

        if your_rate > conversion_rate * 1.2:
            return ConfidenceFactor(
                name=f"Strong {niche} Performance",
                category=FactorCategory.HISTORICAL,
                value=12,
                weight=1.0,
                factor_type=FactorType.POSITIVE,
                description=f"Your store converts well in {niche}",
                icon="award"
            )
        elif your_rate < conversion_rate * 0.8:
            return ConfidenceFactor(
                name=f"Weak {niche} Performance",
                category=FactorCategory.HISTORICAL,
                value=-8,
                weight=1.0,
                factor_type=FactorType.NEGATIVE,
                description=f"Your store underperforms in {niche}",
                icon="alert-triangle"
            )
        return None

    def _calculate_supplier_factor(self, score: float) -> Optional[ConfidenceFactor]:
        """Calculate factor for supplier reliability"""

        if score >= 90:
            return ConfidenceFactor(
                name="Reliable Supplier",
                category=FactorCategory.RISK,
                value=8,
                weight=0.8,
                factor_type=FactorType.POSITIVE,
                description="Supplier has excellent track record",
                icon="shield-check"
            )
        elif score < 70:
            return ConfidenceFactor(
                name="Supplier Risk",
                category=FactorCategory.RISK,
                value=-10,
                weight=0.9,
                factor_type=FactorType.NEGATIVE,
                description="Supplier has quality/shipping concerns",
                icon="alert-triangle"
            )
        return None

    def _calculate_shipping_factor(self, days: int) -> Optional[ConfidenceFactor]:
        """Calculate factor for shipping time"""

        if days <= 7:
            return ConfidenceFactor(
                name="Fast Shipping",
                category=FactorCategory.RISK,
                value=6,
                weight=0.6,
                factor_type=FactorType.POSITIVE,
                description=f"{days}-day shipping improves satisfaction",
                icon="truck"
            )
        elif days >= 21:
            return ConfidenceFactor(
                name="Slow Shipping",
                category=FactorCategory.RISK,
                value=-10,
                weight=0.8,
                factor_type=FactorType.NEGATIVE,
                description=f"{days}-day shipping may cause complaints",
                icon="clock"
            )
        return None

    def _calculate_price_factor(self, price: float, niche: str) -> Optional[ConfidenceFactor]:
        """Calculate factor based on price point"""

        # Define typical ranges by niche
        ranges = {
            "smart_home": (30, 150),
            "fitness": (20, 100),
            "home_goods": (15, 80),
            "electronics": (30, 200),
            "default": (20, 100)
        }

        low, high = ranges.get(niche, ranges["default"])

        if low <= price <= high:
            return ConfidenceFactor(
                name="Optimal Price Point",
                category=FactorCategory.FINANCIAL,
                value=5,
                weight=0.6,
                factor_type=FactorType.POSITIVE,
                description=f"${price:.2f} is within sweet spot for {niche or 'this category'}",
                icon="check"
            )
        elif price > high * 1.5:
            return ConfidenceFactor(
                name="Premium Price",
                category=FactorCategory.FINANCIAL,
                value=-8,
                weight=0.7,
                factor_type=FactorType.NEGATIVE,
                description=f"${price:.2f} is above typical range",
                icon="alert-triangle"
            )
        return None

    def _finalize_score(
        self,
        base_score: float,
        factors: List[ConfidenceFactor],
        action_type: str,
        product_niche: Optional[str] = None
    ) -> ConfidenceScore:
        """
        Finalize the confidence score with learned weights and niche adjustments.

        Applies:
        1. User-specific learned weights from G4 feedback loop
        2. Niche-specific adjustments based on user's success history
        3. Final score clamping and risk classification
        """

        # Get learned weights from feedback loop
        learned_weights = self.get_learned_weights()

        # Apply learned category weights to factors
        for factor in factors:
            # Map factor categories to learned weight keys
            category_to_weight_key = {
                FactorCategory.HISTORICAL: "historical",
                FactorCategory.MARKET: "market",
                FactorCategory.FINANCIAL: "margin",  # Maps to margin weight
                FactorCategory.TREND: "sentiment",    # Maps to sentiment weight
                FactorCategory.COMPETITION: "market",
                FactorCategory.RISK: "historical",    # Risk learned from historical data
                FactorCategory.QUALITY: "sentiment",  # Quality correlates with sentiment
            }

            weight_key = category_to_weight_key.get(factor.category)
            if weight_key and weight_key in learned_weights:
                # Apply learned weight multiplier (0.25 baseline becomes 0.23 or 0.28, etc.)
                learned_multiplier = learned_weights[weight_key] / 0.25  # Normalize to 1.0 baseline
                factor.weight *= learned_multiplier

            # Also apply any pre-computed user weights (for backward compatibility)
            factor_key = f"{factor.category.value}_{factor.name.lower().replace(' ', '_')}"
            if factor_key in self.user_weights:
                factor.weight *= self.user_weights[factor_key]

        # Calculate total adjustment
        total_adjustment = sum(f.weighted_value for f in factors)

        # Calculate final score (clamped to 0-100)
        final_score = max(0, min(100, base_score + total_adjustment))

        # Apply niche adjustment from learned performance
        if product_niche:
            niche_adjustment = self.get_niche_adjustment(product_niche)
            final_score += niche_adjustment
            final_score = max(0, min(100, final_score))  # Re-clamp after niche adjustment

            # Add niche adjustment as a virtual factor for transparency
            if niche_adjustment != 0:
                niche_factor = ConfidenceFactor(
                    name=f"{product_niche.title()} Niche Performance",
                    category=FactorCategory.HISTORICAL,
                    value=niche_adjustment,
                    weight=1.0,
                    factor_type=FactorType.POSITIVE if niche_adjustment > 0 else FactorType.NEGATIVE,
                    description=f"Based on your {abs(niche_adjustment * 10):.0f}% success rate in {product_niche}",
                    icon="award" if niche_adjustment > 0 else "alert-circle"
                )
                factors.append(niche_factor)

        # Determine risk level
        if final_score >= 85:
            risk_level = "low"
            recommendation = "Strong buy signal — safe to approve"
        elif final_score >= 70:
            risk_level = "medium"
            recommendation = "Good opportunity — review factors before approving"
        elif final_score >= 50:
            risk_level = "medium"
            recommendation = "Moderate confidence — consider testing with limited exposure"
        else:
            risk_level = "high"
            recommendation = "High risk — manual review strongly recommended"

        # Generate explanation
        top_positive = sorted(
            [f for f in factors if f.factor_type == FactorType.POSITIVE],
            key=lambda x: x.weighted_value,
            reverse=True
        )[:2]

        top_negative = sorted(
            [f for f in factors if f.factor_type == FactorType.NEGATIVE],
            key=lambda x: x.weighted_value
        )[:2]

        explanation_parts = []
        if top_positive:
            explanation_parts.append(f"Strengths: {', '.join(f.name for f in top_positive)}")
        if top_negative:
            explanation_parts.append(f"Concerns: {', '.join(f.name for f in top_negative)}")

        explanation = ". ".join(explanation_parts) if explanation_parts else "Balanced factors."

        return ConfidenceScore(
            score=final_score,
            base_score=base_score,
            factors=factors,
            explanation=explanation,
            recommendation=recommendation,
            risk_level=risk_level
        )
