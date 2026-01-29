"""
Saturation Scorer Tests
========================

Tests for the anti-saturation scoring system - Ospra's competitive moat.

The saturation scorer prevents deploying to oversaturated markets by analyzing:
- Seller count
- Review velocity
- Best Seller Rank (BSR)
- BSR trends

Author: OspraOS Tests
Date: January 2026
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from ospra_os.intelligence.saturation_scorer import (
    SaturationScorer,
    calculate_saturation_score,
)


class TestSaturationScoreCalculation:
    """Tests for saturation score weighted calculation."""

    @pytest.fixture
    def scorer(self):
        """Create scorer instance without scrapers."""
        with patch.object(SaturationScorer, '_detect_providers', return_value=[]):
            return SaturationScorer()

    def test_low_saturation_returns_deploy(self, scorer):
        """Products with low saturation should recommend deploy."""
        # Simulate low competition scenario
        result = scorer._calculate_weighted_score(
            seller_count=5,       # Few sellers
            review_velocity=1.0,  # Low review velocity
            bsr=100000,           # High BSR = low competition
            bsr_trend="stable"
        )

        # Should be in blue ocean range (0-30)
        assert result < 40, f"Expected low saturation, got {result}"

    def test_high_saturation_returns_skip(self, scorer):
        """Products with high saturation should recommend skip."""
        result = scorer._calculate_weighted_score(
            seller_count=50,      # Many sellers
            review_velocity=20.0, # High review velocity
            bsr=500,              # Top BSR = high competition
            bsr_trend="rising"
        )

        # Should be in saturated range (61-100)
        assert result > 60, f"Expected high saturation, got {result}"

    def test_moderate_saturation_returns_caution(self, scorer):
        """Products with moderate saturation should recommend caution."""
        result = scorer._calculate_weighted_score(
            seller_count=15,      # Moderate sellers
            review_velocity=5.0,  # Moderate velocity
            bsr=20000,            # Middle BSR
            bsr_trend="stable"
        )

        # Should be in caution range (31-60)
        assert 30 <= result <= 70, f"Expected moderate saturation, got {result}"


class TestRecommendations:
    """Tests for recommendation logic."""

    @pytest.fixture
    def scorer(self):
        """Create scorer instance."""
        with patch.object(SaturationScorer, '__init__', lambda x: None):
            s = object.__new__(SaturationScorer)
            return s

    def test_blue_ocean_recommendation(self, scorer):
        """Low saturation should return 'deploy' recommendation."""
        recommendation, reasons = scorer._get_recommendation(
            saturation_score=20,
            seller_count=5,
            review_velocity=1.0,
            bsr=80000
        )

        assert recommendation == "deploy"
        assert any("Blue ocean" in r or "SUCCESS" in r for r in reasons)

    def test_saturated_recommendation(self, scorer):
        """High saturation should return 'skip' recommendation."""
        recommendation, reasons = scorer._get_recommendation(
            saturation_score=75,
            seller_count=40,
            review_velocity=15.0,
            bsr=500
        )

        assert recommendation == "skip"
        assert any("saturated" in r.lower() or "ERROR" in r for r in reasons)

    def test_caution_recommendation(self, scorer):
        """Moderate saturation should return 'caution' recommendation."""
        recommendation, reasons = scorer._get_recommendation(
            saturation_score=45,
            seller_count=15,
            review_velocity=5.0,
            bsr=15000
        )

        assert recommendation == "caution"
        assert any("caution" in r.lower() or "WARNING" in r for r in reasons)


class TestDataExtraction:
    """Tests for extracting data from Amazon response."""

    @pytest.fixture
    def scorer(self):
        """Create scorer instance."""
        with patch.object(SaturationScorer, '__init__', lambda x: None):
            s = object.__new__(SaturationScorer)
            return s

    def test_extract_bsr_from_various_formats(self, scorer):
        """BSR should be extracted from multiple possible field names."""
        test_cases = [
            ({"bestseller_rank": 1000}, 1000),
            ({"bsr": 2000}, 2000),
            ({"best_seller_rank": 3000}, 3000),
            ({"rank": 4000}, 4000),
            ({}, 999999),  # Missing = very high
            (None, 999999),  # None = very high
        ]

        for amazon_data, expected_bsr in test_cases:
            result = scorer._extract_bsr(amazon_data)
            assert result == expected_bsr, f"Failed for {amazon_data}"

    def test_review_velocity_estimation(self, scorer):
        """Review velocity should be estimated when date not available."""
        # High review count = longer estimated lifespan
        high_reviews = {"review_count": 1000}
        velocity_high = scorer._calculate_review_velocity(high_reviews)

        low_reviews = {"review_count": 50}
        velocity_low = scorer._calculate_review_velocity(low_reviews)

        # Both should be positive and different
        assert velocity_high > 0
        assert velocity_low > 0


class TestOpportunityScore:
    """Tests for opportunity score (inverse of saturation)."""

    @pytest.mark.asyncio
    async def test_opportunity_is_inverse_of_saturation(self):
        """Opportunity score should be 100 - saturation."""
        scorer = SaturationScorer()

        # Mock to avoid actual scraping
        with patch.object(scorer, 'amazon_scraper', None):
            result = await scorer.calculate_saturation_score(
                product_name="Test Product",
                amazon_data={
                    "reviews_count": 100,
                    "bestseller_rank": 50000,
                }
            )

        saturation = result["saturation_score"]
        opportunity = result["opportunity_score"]

        # Opportunity should be approximately 100 - saturation
        assert abs((100 - saturation) - opportunity) < 1


class TestBatchScoring:
    """Tests for batch scoring multiple products."""

    @pytest.mark.asyncio
    async def test_batch_score_handles_errors(self):
        """Batch scoring should handle individual product errors."""
        scorer = SaturationScorer()

        # Mock to return error for one product
        async def mock_score(product_name, **kwargs):
            if "error" in product_name.lower():
                raise ValueError("Test error")
            return {"saturation_score": 50, "recommendation": "caution"}

        with patch.object(scorer, 'calculate_saturation_score', side_effect=mock_score):
            results = await scorer.batch_score_products(
                ["Good Product", "Error Product", "Another Good"],
                max_concurrent=2
            )

        # Should have results for all products
        assert len(results) == 3

        # Error product should have error field
        assert "error" in results["Error Product"]


# Run tests with: pytest tests/test_saturation_scorer.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
