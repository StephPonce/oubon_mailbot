"""
Unit tests for ConfidenceEngine.

Tests the confidence scoring system that calculates transparent,
factor-based confidence scores for AI actions.
"""
import pytest
from unittest.mock import MagicMock

from ospra_os.intelligence.confidence_engine import (
    ConfidenceEngine,
    ConfidenceFactor,
    ConfidenceScore,
    FactorType,
    FactorCategory
)


class TestConfidenceFactor:
    """Test ConfidenceFactor dataclass"""

    def test_weighted_value_calculation(self):
        """Test that weighted_value is calculated correctly"""
        factor = ConfidenceFactor(
            name="Test Factor",
            category=FactorCategory.FINANCIAL,
            value=20.0,
            weight=0.8,
            factor_type=FactorType.POSITIVE,
            description="Test description"
        )
        assert factor.weighted_value == 16.0  # 20 * 0.8

    def test_to_dict(self):
        """Test factor serialization to dict"""
        factor = ConfidenceFactor(
            name="High Margin",
            category=FactorCategory.FINANCIAL,
            value=15.5,
            weight=1.2,
            factor_type=FactorType.POSITIVE,
            description="Excellent profit margin",
            icon="dollar-sign"
        )

        result = factor.to_dict()

        assert result["name"] == "High Margin"
        assert result["category"] == "financial"
        assert result["value"] == 15.5
        assert result["weight"] == 1.2
        assert result["weighted_value"] == 18.6  # 15.5 * 1.2
        assert result["type"] == "positive"
        assert result["description"] == "Excellent profit margin"
        assert result["icon"] == "dollar-sign"


class TestConfidenceScore:
    """Test ConfidenceScore dataclass"""

    def test_positive_factors_filter(self):
        """Test filtering of positive factors"""
        factors = [
            ConfidenceFactor("Pos1", FactorCategory.MARKET, 10, 1.0, FactorType.POSITIVE, "desc1"),
            ConfidenceFactor("Neg1", FactorCategory.RISK, -5, 1.0, FactorType.NEGATIVE, "desc2"),
            ConfidenceFactor("Pos2", FactorCategory.TREND, 8, 1.0, FactorType.POSITIVE, "desc3"),
        ]

        score = ConfidenceScore(
            score=75.0,
            base_score=50.0,
            factors=factors
        )

        assert len(score.positive_factors) == 2
        assert all(f.factor_type == FactorType.POSITIVE for f in score.positive_factors)

    def test_negative_factors_filter(self):
        """Test filtering of negative factors"""
        factors = [
            ConfidenceFactor("Pos1", FactorCategory.MARKET, 10, 1.0, FactorType.POSITIVE, "desc1"),
            ConfidenceFactor("Neg1", FactorCategory.RISK, -5, 1.0, FactorType.NEGATIVE, "desc2"),
            ConfidenceFactor("Neg2", FactorCategory.COMPETITION, -8, 1.0, FactorType.NEGATIVE, "desc3"),
        ]

        score = ConfidenceScore(
            score=75.0,
            base_score=50.0,
            factors=factors
        )

        assert len(score.negative_factors) == 2
        assert all(f.factor_type == FactorType.NEGATIVE for f in score.negative_factors)

    def test_total_positive_calculation(self):
        """Test sum of positive weighted values"""
        factors = [
            ConfidenceFactor("Pos1", FactorCategory.MARKET, 10, 1.0, FactorType.POSITIVE, "desc1"),
            ConfidenceFactor("Neg1", FactorCategory.RISK, -5, 1.0, FactorType.NEGATIVE, "desc2"),
            ConfidenceFactor("Pos2", FactorCategory.TREND, 8, 0.5, FactorType.POSITIVE, "desc3"),
        ]

        score = ConfidenceScore(
            score=75.0,
            base_score=50.0,
            factors=factors
        )

        # 10 * 1.0 + 8 * 0.5 = 14
        assert score.total_positive == 14.0

    def test_total_negative_calculation(self):
        """Test sum of negative weighted values"""
        factors = [
            ConfidenceFactor("Pos1", FactorCategory.MARKET, 10, 1.0, FactorType.POSITIVE, "desc1"),
            ConfidenceFactor("Neg1", FactorCategory.RISK, -5, 1.0, FactorType.NEGATIVE, "desc2"),
            ConfidenceFactor("Neg2", FactorCategory.COMPETITION, -8, 0.5, FactorType.NEGATIVE, "desc3"),
        ]

        score = ConfidenceScore(
            score=75.0,
            base_score=50.0,
            factors=factors
        )

        # -5 * 1.0 + -8 * 0.5 = -9
        assert score.total_negative == -9.0

    def test_to_dict(self):
        """Test score serialization to dict"""
        factors = [
            ConfidenceFactor("Pos1", FactorCategory.MARKET, 10, 1.0, FactorType.POSITIVE, "desc1"),
            ConfidenceFactor("Neg1", FactorCategory.RISK, -5, 1.0, FactorType.NEGATIVE, "desc2"),
        ]

        score = ConfidenceScore(
            score=55.0,
            base_score=50.0,
            factors=factors,
            explanation="Test explanation",
            recommendation="Test recommendation",
            risk_level="medium"
        )

        result = score.to_dict()

        assert result["score"] == 55.0
        assert result["base_score"] == 50.0
        assert len(result["factors"]) == 2
        assert len(result["positive_factors"]) == 1
        assert len(result["negative_factors"]) == 1
        assert result["total_positive"] == 10.0
        assert result["total_negative"] == -5.0
        assert result["explanation"] == "Test explanation"
        assert result["recommendation"] == "Test recommendation"
        assert result["risk_level"] == "medium"
        assert result["breakdown"]["base"] == 50.0
        assert result["breakdown"]["adjustments"] == 5.0
        assert result["breakdown"]["final"] == 55.0


class TestConfidenceEngine:
    """Test ConfidenceEngine calculations"""

    def test_initialization(self):
        """Test engine initialization"""
        engine = ConfidenceEngine()
        assert engine.user_weights == {}

    def test_initialization_with_user_weights(self):
        """Test engine initialization with custom weights"""
        weights = {"financial_margin": 1.5, "market_velocity": 0.8}
        engine = ConfidenceEngine(user_weights=weights)
        assert engine.user_weights == weights

    # === MARGIN FACTOR TESTS ===

    def test_margin_factor_excellent(self):
        """Test excellent margin (>= 60%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_margin_factor(65.0)

        assert factor.name == "Excellent Margin"
        assert factor.category == FactorCategory.FINANCIAL
        assert factor.value == 20
        assert factor.weight == 1.2
        assert factor.factor_type == FactorType.POSITIVE

    def test_margin_factor_strong(self):
        """Test strong margin (45-59%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_margin_factor(50.0)

        assert factor.name == "Strong Margin"
        assert factor.value == 15
        assert factor.factor_type == FactorType.POSITIVE

    def test_margin_factor_acceptable(self):
        """Test acceptable margin (30-44%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_margin_factor(35.0)

        assert factor.name == "Acceptable Margin"
        assert factor.value == 8
        assert factor.factor_type == FactorType.POSITIVE

    def test_margin_factor_low(self):
        """Test low margin (< 30%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_margin_factor(20.0)

        assert factor.name == "Low Margin"
        assert factor.value == -10
        assert factor.factor_type == FactorType.NEGATIVE

    # === VELOCITY FACTOR TESTS ===

    def test_velocity_factor_high(self):
        """Test high velocity (>= 85)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_velocity_factor(90.0)

        assert factor.name == "High Demand Velocity"
        assert factor.category == FactorCategory.MARKET
        assert factor.value == 18
        assert factor.factor_type == FactorType.POSITIVE

    def test_velocity_factor_good(self):
        """Test good velocity (70-84)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_velocity_factor(75.0)

        assert factor.name == "Good Demand"
        assert factor.value == 12

    def test_velocity_factor_moderate(self):
        """Test moderate velocity (50-69)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_velocity_factor(55.0)

        assert factor.name == "Moderate Demand"
        assert factor.value == 5
        assert factor.factor_type == FactorType.NEUTRAL

    def test_velocity_factor_low(self):
        """Test low velocity (< 50)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_velocity_factor(30.0)

        assert factor.name == "Low Demand"
        assert factor.value == -8
        assert factor.factor_type == FactorType.NEGATIVE

    # === SATURATION FACTOR TESTS ===

    def test_saturation_very_low(self):
        """Test very low saturation (<= 20%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_saturation_factor(15.0)

        assert factor.name == "Very Low Competition"
        assert factor.value == 15
        assert factor.factor_type == FactorType.POSITIVE

    def test_saturation_low(self):
        """Test low saturation (21-40%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_saturation_factor(30.0)

        assert factor.name == "Low Competition"
        assert factor.value == 10

    def test_saturation_moderate(self):
        """Test moderate saturation (41-60%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_saturation_factor(50.0)

        assert factor.name == "Moderate Competition"
        assert factor.value == 0
        assert factor.factor_type == FactorType.NEUTRAL

    def test_saturation_high(self):
        """Test high saturation (61-80%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_saturation_factor(70.0)

        assert factor.name == "High Competition"
        assert factor.value == -10

    def test_saturation_oversaturated(self):
        """Test oversaturated market (> 80%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_saturation_factor(90.0)

        assert factor.name == "Oversaturated Market"
        assert factor.value == -18
        assert factor.factor_type == FactorType.NEGATIVE

    # === TREND FACTOR TESTS ===

    def test_trend_strong_uptrend(self):
        """Test strong uptrend (> 20%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_trend_factor(25.0)

        assert factor.name == "Strong Uptrend"
        assert factor.value == 12
        assert factor.factor_type == FactorType.POSITIVE

    def test_trend_positive(self):
        """Test positive trend (5-20%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_trend_factor(10.0)

        assert factor.name == "Positive Trend"
        assert factor.value == 6

    def test_trend_declining(self):
        """Test declining interest (< -20%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_trend_factor(-25.0)

        assert factor.name == "Declining Interest"
        assert factor.value == -12
        assert factor.factor_type == FactorType.NEGATIVE

    def test_trend_slight_decline(self):
        """Test slight decline (-5 to -20%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_trend_factor(-10.0)

        assert factor.name == "Slight Decline"
        assert factor.value == -5

    def test_trend_neutral(self):
        """Test neutral trend (-5 to 5%)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_trend_factor(2.0)

        assert factor is None

    # === REVIEW FACTOR TESTS ===

    def test_review_excellent(self):
        """Test excellent reviews (>= 4.5 stars, >= 100 reviews)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_review_factor(4.7, 150)

        assert factor.name == "Excellent Reviews"
        assert factor.value == 12
        assert factor.factor_type == FactorType.POSITIVE

    def test_review_good(self):
        """Test good reviews (>= 4.0 stars, >= 50 reviews)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_review_factor(4.2, 80)

        assert factor.name == "Good Reviews"
        assert factor.value == 8

    def test_review_poor(self):
        """Test poor reviews (< 3.5 stars)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_review_factor(3.2, 100)

        assert factor.name == "Poor Reviews"
        assert factor.value == -15
        assert factor.factor_type == FactorType.NEGATIVE

    def test_review_limited(self):
        """Test limited reviews (< 10 reviews)"""
        engine = ConfidenceEngine()
        factor = engine._calculate_review_factor(4.0, 5)

        assert factor.name == "Limited Reviews"
        assert factor.value == -5

    def test_review_average(self):
        """Test average reviews"""
        engine = ConfidenceEngine()
        factor = engine._calculate_review_factor(3.8, 30)

        assert factor.name == "Average Reviews"
        assert factor.value == 3
        assert factor.factor_type == FactorType.NEUTRAL

    # === PRODUCT CONFIDENCE CALCULATION TESTS ===

    def test_calculate_product_confidence_basic(self):
        """Test basic product confidence calculation"""
        engine = ConfidenceEngine()

        product = {
            "profit_margin": 50.0,
            "sell_price": 49.99,
            "velocity_score": 80,
            "saturation_score": 30,
            "niche": "smart_home"
        }

        result = engine.calculate_product_confidence(product)

        assert isinstance(result, ConfidenceScore)
        assert 0 <= result.score <= 100
        assert result.base_score == 40  # deploy_product base
        assert len(result.factors) > 0
        assert result.risk_level in ["low", "medium", "high"]

    def test_calculate_product_confidence_high_score(self):
        """Test product with excellent metrics yields high confidence"""
        engine = ConfidenceEngine()

        product = {
            "profit_margin": 65.0,  # Excellent
            "sell_price": 75.00,
            "velocity_score": 90,  # High demand
            "saturation_score": 15,  # Very low competition
            "trend_direction": 25,  # Strong uptrend
            "review_score": 4.7,
            "review_count": 200,
            "niche": "smart_home"
        }

        result = engine.calculate_product_confidence(product)

        assert result.score >= 70  # Should be high confidence
        assert len(result.positive_factors) > len(result.negative_factors)

    def test_calculate_product_confidence_low_score(self):
        """Test product with poor metrics yields low confidence"""
        engine = ConfidenceEngine()

        product = {
            "profit_margin": 20.0,  # Low
            "sell_price": 49.99,
            "velocity_score": 30,  # Low demand
            "saturation_score": 90,  # Oversaturated
            "trend_direction": -25,  # Declining
            "review_score": 3.0,  # Poor
            "review_count": 100,
            "niche": "smart_home"
        }

        result = engine.calculate_product_confidence(product)

        assert result.score <= 50  # Should be low confidence
        assert len(result.negative_factors) >= len(result.positive_factors)

    def test_calculate_product_confidence_with_historical_data(self):
        """Test product confidence with historical performance data"""
        engine = ConfidenceEngine()

        product = {
            "profit_margin": 50.0,
            "niche": "fitness"
        }

        historical_data = {
            "similar_product_performance": {
                "success_rate": 0.8,
                "sample_size": 10
            },
            "niche_performance": {
                "avg_conversion": 0.02,
                "your_conversion": 0.03
            }
        }

        result = engine.calculate_product_confidence(product, historical_data=historical_data)

        # Should include historical factors
        factor_names = [f.name for f in result.factors]
        assert any("Historical" in name or "Performance" in name for name in factor_names)

    # === PRICE ADJUSTMENT CONFIDENCE TESTS ===

    def test_calculate_price_adjustment_confidence_basic(self):
        """Test basic price adjustment confidence"""
        engine = ConfidenceEngine()

        result = engine.calculate_price_adjustment_confidence(
            current_price=50.0,
            new_price=55.0,
            supplier_change=10.0  # 10% supplier increase
        )

        assert isinstance(result, ConfidenceScore)
        assert result.base_score == 50  # adjust_price base
        assert len(result.factors) > 0

    def test_price_adjustment_large_increase_penalty(self):
        """Test penalty for large price increases"""
        engine = ConfidenceEngine()

        result = engine.calculate_price_adjustment_confidence(
            current_price=50.0,
            new_price=60.0,  # 20% increase
            supplier_change=5.0
        )

        factor_names = [f.name for f in result.factors]
        assert "Large Price Increase" in factor_names

    def test_price_adjustment_competitive_pricing(self):
        """Test competitive pricing factor"""
        engine = ConfidenceEngine()

        result = engine.calculate_price_adjustment_confidence(
            current_price=50.0,
            new_price=52.0,
            supplier_change=4.0,
            competitor_prices=[53.0, 55.0, 54.0]  # New price is competitive
        )

        factor_names = [f.name for f in result.factors]
        assert "Competitive Pricing" in factor_names

    def test_price_adjustment_premium_pricing(self):
        """Test premium pricing penalty"""
        engine = ConfidenceEngine()

        result = engine.calculate_price_adjustment_confidence(
            current_price=50.0,
            new_price=60.0,
            supplier_change=5.0,
            competitor_prices=[45.0, 48.0, 50.0]  # New price is above market
        )

        factor_names = [f.name for f in result.factors]
        assert "Premium Pricing" in factor_names

    # === AD PAUSE CONFIDENCE TESTS ===

    def test_calculate_ad_pause_confidence_basic(self):
        """Test basic ad pause confidence"""
        engine = ConfidenceEngine()

        result = engine.calculate_ad_pause_confidence(
            roas=0.8,
            spend=100.0,
            conversions=5,
            days_running=10
        )

        assert isinstance(result, ConfidenceScore)
        assert result.base_score == 45  # pause_ad base
        assert len(result.factors) > 0

    def test_ad_pause_low_roas(self):
        """Test pause recommendation for low ROAS"""
        engine = ConfidenceEngine()

        result = engine.calculate_ad_pause_confidence(
            roas=0.5,  # Below 1.0x breakeven
            spend=200.0,
            conversions=3,
            days_running=14
        )

        # Should have positive factor for pausing (ROAS below target)
        positive_factors = [f for f in result.factors if f.factor_type == FactorType.POSITIVE]
        assert any("ROAS" in f.name for f in positive_factors)

    def test_ad_pause_healthy_roas(self):
        """Test negative factor for healthy ROAS"""
        engine = ConfidenceEngine()

        result = engine.calculate_ad_pause_confidence(
            roas=2.5,  # Healthy ROAS
            spend=100.0,
            conversions=15,
            days_running=14
        )

        # Should have negative factor for pausing (campaign is profitable)
        negative_factors = [f for f in result.factors if f.factor_type == FactorType.NEGATIVE]
        assert any("ROAS" in f.name for f in negative_factors)

    def test_ad_pause_learning_period(self):
        """Test learning period factor"""
        engine = ConfidenceEngine()

        result = engine.calculate_ad_pause_confidence(
            roas=0.8,
            spend=50.0,
            conversions=2,
            days_running=3  # Still learning
        )

        factor_names = [f.name for f in result.factors]
        assert "Still in Learning Period" in factor_names

    def test_ad_pause_low_ctr(self):
        """Test low CTR factor"""
        engine = ConfidenceEngine()

        result = engine.calculate_ad_pause_confidence(
            roas=0.8,
            spend=100.0,
            conversions=5,
            days_running=10,
            ctr=0.3  # Low CTR
        )

        factor_names = [f.name for f in result.factors]
        assert "Low Click-Through Rate" in factor_names

    def test_ad_pause_strong_ctr(self):
        """Test strong CTR factor"""
        engine = ConfidenceEngine()

        result = engine.calculate_ad_pause_confidence(
            roas=1.5,
            spend=100.0,
            conversions=10,
            days_running=14,
            ctr=2.5  # Strong CTR
        )

        factor_names = [f.name for f in result.factors]
        assert "Strong Click-Through Rate" in factor_names

    # === SCORE FINALIZATION TESTS ===

    def test_finalize_score_clamping_upper(self):
        """Test score is clamped to 100"""
        engine = ConfidenceEngine()

        factors = [
            ConfidenceFactor("Huge Positive", FactorCategory.MARKET, 100, 1.0, FactorType.POSITIVE, "test")
        ]

        result = engine._finalize_score(50, factors, "deploy_product")

        assert result.score == 100  # Should be clamped

    def test_finalize_score_clamping_lower(self):
        """Test score is clamped to 0"""
        engine = ConfidenceEngine()

        factors = [
            ConfidenceFactor("Huge Negative", FactorCategory.RISK, -100, 1.0, FactorType.NEGATIVE, "test")
        ]

        result = engine._finalize_score(50, factors, "deploy_product")

        assert result.score == 0  # Should be clamped

    def test_finalize_score_risk_levels(self):
        """Test risk level classification"""
        engine = ConfidenceEngine()

        # High confidence = low risk
        result_low = engine._finalize_score(85, [], "deploy_product")
        assert result_low.risk_level == "low"
        assert "safe to approve" in result_low.recommendation.lower()

        # Medium-high confidence = medium risk
        result_med1 = engine._finalize_score(70, [], "deploy_product")
        assert result_med1.risk_level == "medium"

        # Medium confidence = medium risk
        result_med2 = engine._finalize_score(50, [], "deploy_product")
        assert result_med2.risk_level == "medium"

        # Low confidence = high risk
        result_high = engine._finalize_score(30, [], "deploy_product")
        assert result_high.risk_level == "high"
        assert "manual review" in result_high.recommendation.lower()

    def test_finalize_score_user_weights(self):
        """Test user-specific weight application"""
        user_weights = {
            "financial_excellent_margin": 1.5  # Boost financial margin weight
        }
        engine = ConfidenceEngine(user_weights=user_weights)

        factors = [
            ConfidenceFactor("Excellent Margin", FactorCategory.FINANCIAL, 20, 1.2, FactorType.POSITIVE, "test")
        ]

        result = engine._finalize_score(50, factors, "deploy_product")

        # Weight should be multiplied: 1.2 * 1.5 = 1.8
        # Score: 50 + (20 * 1.8) = 86
        assert result.score == 86.0

    def test_finalize_score_explanation_generation(self):
        """Test explanation generation from factors"""
        engine = ConfidenceEngine()

        factors = [
            ConfidenceFactor("Strong Margin", FactorCategory.FINANCIAL, 15, 1.0, FactorType.POSITIVE, "Good profit"),
            ConfidenceFactor("High Demand", FactorCategory.MARKET, 18, 1.0, FactorType.POSITIVE, "Strong sales"),
            ConfidenceFactor("High Competition", FactorCategory.COMPETITION, -10, 1.0, FactorType.NEGATIVE, "Crowded"),
            ConfidenceFactor("Low Margin", FactorCategory.FINANCIAL, -8, 1.0, FactorType.NEGATIVE, "Poor profit")
        ]

        result = engine._finalize_score(50, factors, "deploy_product")

        assert "Strong Margin" in result.explanation or "High Demand" in result.explanation
        assert "High Competition" in result.explanation or "Low Margin" in result.explanation

    # === EDGE CASES ===

    def test_product_confidence_empty_product(self):
        """Test product confidence with minimal data"""
        engine = ConfidenceEngine()

        product = {}

        result = engine.calculate_product_confidence(product)

        assert isinstance(result, ConfidenceScore)
        assert result.score == result.base_score  # No adjustments

    def test_product_confidence_missing_optional_fields(self):
        """Test product with missing optional fields doesn't crash"""
        engine = ConfidenceEngine()

        product = {
            "profit_margin": 50.0
            # Missing: price, velocity, saturation, etc.
        }

        result = engine.calculate_product_confidence(product)

        assert isinstance(result, ConfidenceScore)
        assert result.score > 0

    def test_shipping_factor_fast(self):
        """Test fast shipping factor"""
        engine = ConfidenceEngine()
        factor = engine._calculate_shipping_factor(5)

        assert factor.name == "Fast Shipping"
        assert factor.value == 6
        assert factor.factor_type == FactorType.POSITIVE

    def test_shipping_factor_slow(self):
        """Test slow shipping factor"""
        engine = ConfidenceEngine()
        factor = engine._calculate_shipping_factor(25)

        assert factor.name == "Slow Shipping"
        assert factor.value == -10
        assert factor.factor_type == FactorType.NEGATIVE

    def test_supplier_factor_reliable(self):
        """Test reliable supplier factor"""
        engine = ConfidenceEngine()
        factor = engine._calculate_supplier_factor(95)

        assert factor.name == "Reliable Supplier"
        assert factor.value == 8
        assert factor.factor_type == FactorType.POSITIVE

    def test_supplier_factor_risky(self):
        """Test risky supplier factor"""
        engine = ConfidenceEngine()
        factor = engine._calculate_supplier_factor(65)

        assert factor.name == "Supplier Risk"
        assert factor.value == -10
        assert factor.factor_type == FactorType.NEGATIVE
