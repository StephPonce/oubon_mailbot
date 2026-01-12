"""
Ad Test Manager

Specialized manager for testing ad creatives and ad copy for Meta/TikTok campaigns.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select

from .ab_test_engine import ABTestEngine, TestType
from ospra_os.database import ABTest, ABTestVariant


class AdTestManager:
    """
    Manager for ad creative and copy A/B tests

    Handles testing of:
    - Ad images/videos
    - Ad headlines
    - Ad copy/descriptions
    - Call-to-action buttons
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        self.engine = ABTestEngine(db_session)

    def create_ad_creative_test(
        self,
        product_id: str,
        store_id: str,
        campaign_id: str,
        control_creative: Dict[str, Any],
        variant_creatives: List[Dict[str, Any]],
        test_name: Optional[str] = None,
        duration_days: int = 7,
        traffic_split: Optional[List[float]] = None,
        min_sample_size: int = 50
    ) -> ABTest:
        """
        Create an ad creative A/B test

        Tests different ad visuals (images/videos) to optimize CTR and conversions.

        Args:
            product_id: Product being advertised
            store_id: Store running ads
            campaign_id: Ad campaign ID (Meta/TikTok)
            control_creative: Current ad creative
                {
                    "image_url": "https://...",
                    "video_url": None,  # or video URL
                    "format": "image",  # or "video"
                    "headline": "Ad headline",
                    "description": "Ad copy"
                }
            variant_creatives: Alternative creatives to test
            test_name: Custom test name
            duration_days: Test duration
            traffic_split: Traffic distribution
            min_sample_size: Minimum conversions

        Returns:
            Created ABTest instance
        """

        if not test_name:
            test_name = f"Ad Creative Test: {campaign_id}"

        # Create variants
        variants = [
            {
                "name": "Control Creative",
                "config": {
                    **control_creative,
                    "is_control": True,
                    "creative_type": control_creative.get("format", "image")
                }
            }
        ]

        for i, creative in enumerate(variant_creatives, start=1):
            creative_type = creative.get("format", "image")
            variant_name = f"Variant {i} ({creative_type})"

            variants.append({
                "name": variant_name,
                "config": {
                    **creative,
                    "creative_type": creative_type
                }
            })

        scheduled_end = datetime.utcnow() + timedelta(days=duration_days)

        test = self.engine.create_test(
            name=test_name,
            test_type=TestType.AD_CREATIVE,
            product_id=product_id,
            store_id=store_id,
            variants=variants,
            traffic_split=traffic_split,
            scheduled_start=None,
            scheduled_end=scheduled_end,
            min_sample_size=min_sample_size,
            metadata={
                "campaign_id": campaign_id,
                "platform": "meta",  # or "tiktok"
                "creative_formats": [v.get("format") for v in [control_creative] + variant_creatives]
            }
        )

        return test

    def create_ad_copy_test(
        self,
        product_id: str,
        store_id: str,
        campaign_id: str,
        control_copy: Dict[str, str],
        variant_copies: List[Dict[str, str]],
        test_name: Optional[str] = None,
        duration_days: int = 7,
        traffic_split: Optional[List[float]] = None,
        min_sample_size: int = 50
    ) -> ABTest:
        """
        Create an ad copy A/B test

        Tests different ad copy variations to optimize messaging.

        Args:
            product_id: Product being advertised
            store_id: Store running ads
            campaign_id: Ad campaign ID
            control_copy: Current ad copy
                {
                    "headline": "Main headline",
                    "description": "Ad description",
                    "cta": "Shop Now"  # Call-to-action
                }
            variant_copies: Alternative copy to test
            test_name: Custom test name
            duration_days: Test duration
            traffic_split: Traffic distribution
            min_sample_size: Minimum conversions

        Returns:
            Created ABTest instance
        """

        if not test_name:
            test_name = f"Ad Copy Test: {campaign_id}"

        # Create variants
        variants = [
            {
                "name": "Control Copy",
                "config": {
                    **control_copy,
                    "is_control": True,
                    "headline_length": len(control_copy.get("headline", "")),
                    "description_length": len(control_copy.get("description", ""))
                }
            }
        ]

        for i, copy in enumerate(variant_copies, start=1):
            variants.append({
                "name": f"Variant {i}",
                "config": {
                    **copy,
                    "headline_length": len(copy.get("headline", "")),
                    "description_length": len(copy.get("description", ""))
                }
            })

        scheduled_end = datetime.utcnow() + timedelta(days=duration_days)

        test = self.engine.create_test(
            name=test_name,
            test_type=TestType.AD_COPY,
            product_id=product_id,
            store_id=store_id,
            variants=variants,
            traffic_split=traffic_split,
            scheduled_start=None,
            scheduled_end=scheduled_end,
            min_sample_size=min_sample_size,
            metadata={
                "campaign_id": campaign_id,
                "platform": "meta"
            }
        )

        return test

    def get_ad_variant_for_campaign(
        self,
        test_id: int,
        visitor_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get ad variant to show to visitor

        Args:
            test_id: Active ad test
            visitor_id: Visitor identifier

        Returns:
            Ad creative/copy configuration
        """
        variant = self.engine.get_variant_for_visitor(test_id, visitor_id)

        if not variant:
            return None

        return variant.config

    def record_ad_click(
        self,
        test_id: int,
        variant_id: int,
        visitor_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record ad click event

        Args:
            test_id: Test ID
            variant_id: Variant clicked
            visitor_id: Visitor who clicked
            metadata: Additional click data (device, location, etc.)
        """
        # Record as impression first (saw the ad)
        self.engine.record_impression(test_id, variant_id, visitor_id, metadata)

        # Record click event
        from ospra_os.database import ABTestEvent, ABTestVariant
        from sqlalchemy import select

        event = ABTestEvent(
            test_id=test_id,
            variant_id=variant_id,
            visitor_id=visitor_id,
            event_type="click",
            metadata=metadata or {},
            created_at=datetime.utcnow()
        )
        self.db.add(event)

        # Update variant click count
        variant_result = self.db.execute(
            select(ABTestVariant).where(ABTestVariant.id == variant_id)
        )
        variant = variant_result.scalar_one_or_none()
        if variant:
            variant.clicks += 1

        self.db.commit()

    def get_ad_test_metrics(self, test_id: int) -> Dict[str, Any]:
        """
        Get ad-specific performance metrics

        Returns:
            Ad test metrics including CTR, CPC, ROAS
        """
        test_data = self.engine.get_test(test_id, include_results=True)

        if not test_data:
            raise ValueError(f"Test {test_id} not found")

        # Calculate ad metrics for each variant
        for variant in test_data["variants"]:
            impressions = variant["impressions"]
            clicks = variant["clicks"]
            conversions = variant["conversions"]
            revenue = variant["revenue"]

            # Click-through rate
            variant["ctr"] = (clicks / impressions * 100) if impressions > 0 else 0

            # Cost per click (assuming $1 CPM)
            cpm = 1.00
            total_cost = (impressions / 1000) * cpm
            variant["total_ad_spend"] = round(total_cost, 2)
            variant["cpc"] = round(total_cost / clicks, 2) if clicks > 0 else 0

            # Return on ad spend
            variant["roas"] = round(revenue / total_cost, 2) if total_cost > 0 else 0

            # Cost per acquisition
            variant["cpa"] = round(total_cost / conversions, 2) if conversions > 0 else 0

        return {
            **test_data,
            "ad_metrics": {
                "focus": "ctr_and_roas",
                "key_metrics": ["ctr", "cpc", "roas", "cpa"]
            }
        }

    def implement_winning_ad(
        self,
        test_id: int,
        winner_variant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Apply winning ad variant to campaign

        Args:
            test_id: Test ID
            winner_variant_id: Manual winner selection

        Returns:
            Implementation result
        """
        # Get test
        test_result = self.db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = test_result.scalar_one_or_none()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        # Determine winner
        if not winner_variant_id:
            winner_variant_id = self.engine.determine_winner(test_id)

            if not winner_variant_id:
                raise ValueError("Cannot determine winner - insufficient data")

        # Get winning variant
        variant_result = self.db.execute(
            select(ABTestVariant).where(ABTestVariant.id == winner_variant_id)
        )
        winner = variant_result.scalar_one_or_none()

        if not winner:
            raise ValueError(f"Winner variant {winner_variant_id} not found")

        winning_config = winner.config

        # Update test
        test.winner_variant_id = winner_variant_id
        test.status = "ended"
        test.ended_at = datetime.utcnow()
        test.test_metadata = test.test_metadata or {}
        test.test_metadata["implemented_at"] = datetime.utcnow().isoformat()
        test.test_metadata["winning_ad_config"] = winning_config

        self.db.commit()

        # TODO: Update Meta/TikTok campaign via API
        # TODO: Pause losing ad variants
        # TODO: Scale winning ad variant budget

        return {
            "success": True,
            "test_id": test_id,
            "test_type": test.test_type,
            "winner_variant_id": winner_variant_id,
            "winning_config": winning_config,
            "campaign_id": test.test_metadata.get("campaign_id"),
            "next_steps": [
                "Update campaign with winning creative",
                "Pause losing variants",
                "Consider scaling budget on winner"
            ]
        }

    def generate_ad_copy_variants(
        self,
        product_name: str,
        key_benefit: str,
        target_audience: Optional[str] = None,
        tone: str = "exciting"
    ) -> List[Dict[str, Any]]:
        """
        Generate ad copy variant suggestions

        Args:
            product_name: Product being advertised
            key_benefit: Main benefit to highlight
            target_audience: Target customer segment
            tone: Ad tone (exciting, professional, friendly, urgent)

        Returns:
            List of suggested ad copy variants
        """
        variants = []

        # 1. Problem-solution approach
        variants.append({
            "headline": f"Struggling with {key_benefit.lower()}?",
            "description": f"{product_name} is the solution you've been looking for. Join thousands of happy customers!",
            "cta": "Shop Now",
            "strategy": "problem_solution",
            "expected_impact": "Resonates with pain points"
        })

        # 2. Social proof approach
        variants.append({
            "headline": f"Why Everyone Loves {product_name}",
            "description": f"[STAR][STAR][STAR][STAR][STAR] Rated 5 stars by thousands. Experience {key_benefit} like never before!",
            "cta": "See Why",
            "strategy": "social_proof",
            "expected_impact": "Builds trust through popularity"
        })

        # 3. Urgency approach
        variants.append({
            "headline": f"Limited Stock: {product_name}",
            "description": f"Don't miss out! {key_benefit} with our best-selling product. Order now before it's gone!",
            "cta": "Grab Yours",
            "strategy": "urgency",
            "expected_impact": "Drives immediate action"
        })

        # 4. Value proposition approach
        variants.append({
            "headline": f"Get {key_benefit} in Just Days",
            "description": f"{product_name} delivers results fast. Free shipping + 30-day guarantee!",
            "cta": "Start Now",
            "strategy": "value_proposition",
            "expected_impact": "Clear value communication"
        })

        # 5. Curiosity approach
        variants.append({
            "headline": f"The Secret to {key_benefit}",
            "description": f"Discover what {target_audience or 'smart shoppers'} already know. Try {product_name} today!",
            "cta": "Learn More",
            "strategy": "curiosity",
            "expected_impact": "Engages interest"
        })

        return variants

    def get_creative_performance_insights(
        self,
        test_id: int
    ) -> Dict[str, Any]:
        """
        Analyze which creative elements drive best performance

        Returns insights about:
        - Image vs video performance
        - Headline length impact
        - CTA effectiveness
        """
        test_data = self.engine.get_test(test_id, include_results=True)

        if not test_data:
            raise ValueError(f"Test {test_id} not found")

        insights = {
            "test_id": test_id,
            "test_type": test_data["test_type"],
            "insights": []
        }

        # Find best performer
        best_variant = max(
            test_data["variants"],
            key=lambda v: v.get("conversion_rate", 0)
        )

        control = next((v for v in test_data["variants"] if v["is_control"]), None)

        # Creative type insights
        if test_data["test_type"] == "ad_creative":
            best_format = best_variant["config"].get("creative_type", "image")
            control_format = control["config"].get("creative_type", "image") if control else None

            if best_format != control_format:
                insights["insights"].append(
                    f"{best_format.capitalize()} format outperforms {control_format} by "
                    f"{best_variant['conversion_rate'] - control['conversion_rate']:.1f}%"
                )

        # Copy insights
        elif test_data["test_type"] == "ad_copy":
            best_headline_len = best_variant["config"].get("headline_length", 0)
            control_headline_len = control["config"].get("headline_length", 0) if control else 0

            if best_headline_len < control_headline_len - 10:
                insights["insights"].append("Shorter headlines drive higher conversions")
            elif best_headline_len > control_headline_len + 10:
                insights["insights"].append("Longer, descriptive headlines perform better")

            # CTA analysis
            best_cta = best_variant["config"].get("cta", "")
            if best_cta:
                insights["insights"].append(f"CTA '{best_cta}' is most effective")

        # Performance summary
        insights["best_variant"] = {
            "name": best_variant["name"],
            "conversion_rate": best_variant["conversion_rate"],
            "ctr": best_variant.get("ctr", 0),
            "config": best_variant["config"]
        }

        return insights
