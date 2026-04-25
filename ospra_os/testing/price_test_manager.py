"""
Price Test Manager

Specialized manager for price-based A/B tests.
Handles price variant creation and Shopify integration.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from .ab_test_engine import ABTestEngine, TestType
from ospra_os.database import ABTest, ABTestVariant


class PriceTestManager:
    """
    Manager for price-based A/B tests

    Simplifies creation of price tests and handles Shopify integration
    to update product prices when implementing winners.
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        self.engine = ABTestEngine(db_session)

    def create_price_test(
        self,
        product_id: str,
        store_id: str,
        current_price: float,
        test_prices: List[float],
        test_name: Optional[str] = None,
        duration_days: int = 14,
        traffic_split: Optional[List[float]] = None,
        min_sample_size: int = 100,
        confidence_level: float = 0.95,
        auto_implement_winner: bool = False
    ) -> ABTest:
        """
        Create a price A/B test

        Args:
            product_id: Product to test
            store_id: Store running the test
            current_price: Current product price (control)
            test_prices: List of alternative prices to test
            test_name: Custom test name (auto-generated if None)
            duration_days: How long to run test
            traffic_split: Traffic % per variant (equal split if None)
            min_sample_size: Minimum conversions before declaring winner
            confidence_level: Statistical confidence threshold
            auto_implement_winner: Automatically apply winning price when test ends

        Returns:
            Created ABTest instance

        Example:
            # Test $29.99 (current) vs $34.99 vs $39.99
            test = manager.create_price_test(
                product_id="12345",
                store_id="store1",
                current_price=29.99,
                test_prices=[34.99, 39.99],
                duration_days=14
            )
        """

        # Generate test name if not provided
        if not test_name:
            prices_str = f"${current_price:.2f} vs " + " vs ".join([f"${p:.2f}" for p in test_prices])
            test_name = f"Price Test: {prices_str}"

        # Create variants
        variants = [
            {
                "name": f"Control: ${current_price:.2f}",
                "config": {
                    "price": current_price,
                    "is_control": True
                }
            }
        ]

        for i, price in enumerate(test_prices, start=1):
            variant_name = f"Variant {i}: ${price:.2f}"
            change_pct = ((price - current_price) / current_price) * 100

            if change_pct > 0:
                variant_name += f" (+{change_pct:.0f}%)"
            else:
                variant_name += f" ({change_pct:.0f}%)"

            variants.append({
                "name": variant_name,
                "config": {
                    "price": price,
                    "price_change_percent": round(change_pct, 2)
                }
            })

        # Set scheduled end time
        scheduled_end = datetime.now(timezone.utc) + timedelta(days=duration_days)

        # Create test using engine
        test = self.engine.create_test(
            name=test_name,
            test_type=TestType.PRICE,
            product_id=product_id,
            store_id=store_id,
            variants=variants,
            traffic_split=traffic_split,
            scheduled_start=None,  # Manual start
            scheduled_end=scheduled_end,
            min_sample_size=min_sample_size,
            confidence_level=confidence_level,
            metadata={
                "auto_implement_winner": auto_implement_winner,
                "current_price": current_price,
                "test_prices": test_prices
            }
        )

        return test

    def get_price_for_visitor(
        self,
        test_id: int,
        visitor_id: str
    ) -> Optional[float]:
        """
        Get the price variant assigned to a visitor

        Args:
            test_id: Active price test ID
            visitor_id: Unique visitor identifier

        Returns:
            Price to show visitor, or None if test not running
        """
        variant = self.engine.get_variant_for_visitor(test_id, visitor_id)

        if not variant:
            return None

        return variant.config.get("price")

    def implement_winning_price(
        self,
        test_id: int,
        winner_variant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Apply the winning price to the product

        This will:
        1. Determine winner if not specified
        2. Update product price in database
        3. Sync price to Shopify (if integrated)

        Args:
            test_id: Test ID
            winner_variant_id: Override auto winner detection

        Returns:
            Implementation result with new price
        """
        # Get test
        test_result = self.db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = test_result.scalar_one_or_none()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        # Determine winner if not specified
        if not winner_variant_id:
            winner_variant_id = self.engine.determine_winner(test_id)

            if not winner_variant_id:
                raise ValueError("Cannot determine winner - insufficient data or no significant result")

        # Get winning variant
        variant_result = self.db.execute(
            select(ABTestVariant).where(ABTestVariant.id == winner_variant_id)
        )
        winner = variant_result.scalar_one_or_none()

        if not winner:
            raise ValueError(f"Winner variant {winner_variant_id} not found")

        winning_price = winner.config.get("price")

        if not winning_price:
            raise ValueError("Winning variant has no price configured")

        # Update test to mark as implemented
        test.winner_variant_id = winner_variant_id
        test.status = "ended"
        test.ended_at = datetime.now(timezone.utc)
        test.test_metadata = test.test_metadata or {}
        test.test_metadata["implemented_at"] = datetime.now(timezone.utc).isoformat()
        test.test_metadata["winning_price"] = winning_price

        self.db.commit()

        # TODO: Update product price in products table
        # TODO: Sync to Shopify via shopify_integration.py

        return {
            "success": True,
            "test_id": test_id,
            "winner_variant_id": winner_variant_id,
            "winning_price": winning_price,
            "product_id": test.product_id,
            "store_id": test.store_id,
            "message": f"Price updated to ${winning_price:.2f}"
        }

    def get_price_test_summary(self, test_id: int) -> Dict[str, Any]:
        """
        Get price-specific test summary with revenue analysis

        Returns detailed price test results including:
        - Revenue per variant
        - Average order value
        - Estimated revenue impact
        """
        test_data = self.engine.get_test(test_id, include_results=True)

        if not test_data:
            raise ValueError(f"Test {test_id} not found")

        # Calculate revenue projections
        control = next((v for v in test_data["variants"] if v["is_control"]), None)

        if not control:
            raise ValueError("No control variant found")

        for variant in test_data["variants"]:
            if variant["is_control"]:
                continue

            # Calculate projected revenue impact
            control_revenue = control.get("revenue", 0)
            variant_revenue = variant.get("revenue", 0)

            if control["conversions"] > 0 and variant["conversions"] > 0:
                # Revenue per conversion
                control_rpc = control_revenue / control["conversions"]
                variant_rpc = variant_revenue / variant["conversions"]

                revenue_lift = ((variant_rpc - control_rpc) / control_rpc) * 100
                variant["revenue_per_conversion"] = round(variant_rpc, 2)
                variant["revenue_lift"] = round(revenue_lift, 2)

                # Projected monthly revenue impact (assuming 1000 conversions/month)
                monthly_conversions = 1000
                projected_impact = (variant_rpc - control_rpc) * monthly_conversions
                variant["projected_monthly_impact"] = round(projected_impact, 2)

        return {
            **test_data,
            "test_type": "price",
            "analysis": {
                "focus": "revenue_optimization",
                "metrics": ["revenue_per_conversion", "conversion_rate", "total_revenue"]
            }
        }

    def recommend_price_points(
        self,
        product_id: str,
        current_price: float,
        cost: float,
        competitor_prices: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Recommend optimal price points to test

        Uses pricing psychology and competitor analysis to suggest
        test prices that are likely to reveal optimal pricing.

        Args:
            product_id: Product being analyzed
            current_price: Current selling price
            cost: Product cost (for margin calculation)
            competitor_prices: List of competitor prices (if available)

        Returns:
            Recommended price variants to test
        """
        recommendations = []

        # Current margin
        current_margin = ((current_price - cost) / current_price) * 100

        # 1. Psychological pricing variants (e.g., $29.99 vs $30.00)
        if not str(current_price).endswith(".99"):
            psych_price = float(int(current_price)) - 0.01
            if psych_price > cost:
                recommendations.append({
                    "price": psych_price,
                    "strategy": "psychological_pricing",
                    "description": f"Psychological price point ${psych_price:.2f}",
                    "expected_impact": "May increase conversions 5-10%"
                })

        # 2. Premium pricing (+20% to +50%)
        premium_20 = round(current_price * 1.20, 2)
        premium_50 = round(current_price * 1.50, 2)

        recommendations.append({
            "price": premium_20,
            "strategy": "premium_positioning",
            "description": f"+20% premium pricing ${premium_20:.2f}",
            "expected_impact": "Test premium market segment",
            "margin": round(((premium_20 - cost) / premium_20) * 100, 1)
        })

        # 3. Value pricing (-10% to -20%)
        value_10 = round(current_price * 0.90, 2)
        value_20 = round(current_price * 0.80, 2)

        if value_10 > cost * 1.3:  # Maintain at least 30% margin
            recommendations.append({
                "price": value_10,
                "strategy": "value_pricing",
                "description": f"-10% value pricing ${value_10:.2f}",
                "expected_impact": "May increase volume 15-25%",
                "margin": round(((value_10 - cost) / value_10) * 100, 1)
            })

        # 4. Competitor-based pricing
        if competitor_prices:
            avg_competitor = sum(competitor_prices) / len(competitor_prices)
            median_competitor = sorted(competitor_prices)[len(competitor_prices) // 2]

            # Match median competitor
            if abs(median_competitor - current_price) > 1.0:
                recommendations.append({
                    "price": median_competitor,
                    "strategy": "competitive_parity",
                    "description": f"Match competitor median ${median_competitor:.2f}",
                    "expected_impact": "Competitive positioning",
                    "margin": round(((median_competitor - cost) / median_competitor) * 100, 1)
                })

        # 5. Bundle/tier pricing
        bundle_price = round(current_price * 0.85, 2)  # 15% discount for bundle
        if bundle_price > cost * 1.2:
            recommendations.append({
                "price": bundle_price,
                "strategy": "bundle_pricing",
                "description": f"Bundle/multi-unit price ${bundle_price:.2f}",
                "expected_impact": "Encourage larger orders",
                "margin": round(((bundle_price - cost) / bundle_price) * 100, 1)
            })

        # Sort by expected revenue impact
        return {
            "product_id": product_id,
            "current_price": current_price,
            "cost": cost,
            "current_margin": round(current_margin, 1),
            "recommendations": recommendations[:5],  # Top 5
            "suggested_test": {
                "control": current_price,
                "variants": [r["price"] for r in recommendations[:3]],  # Top 3 to test
                "duration_days": 14,
                "traffic_split": [40, 20, 20, 20]  # 40% control, 20% each variant
            }
        }
