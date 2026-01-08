"""
Content Test Manager

Specialized manager for testing product content variations:
- Product titles
- Product descriptions
- Product images
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select

from .ab_test_engine import ABTestEngine, TestType
from ospra_os.database.multi_store_models import ABTest, ABTestVariant


class ContentTestManager:
    """
    Manager for product content A/B tests

    Handles testing of titles, descriptions, and images to optimize
    conversion rates through better product presentation.
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        self.engine = ABTestEngine(db_session)

    def create_title_test(
        self,
        product_id: str,
        store_id: str,
        current_title: str,
        variant_titles: List[str],
        test_name: Optional[str] = None,
        duration_days: int = 14,
        traffic_split: Optional[List[float]] = None,
        min_sample_size: int = 100
    ) -> ABTest:
        """
        Create a product title A/B test

        Args:
            product_id: Product to test
            store_id: Store running test
            current_title: Current product title (control)
            variant_titles: Alternative titles to test
            test_name: Custom test name
            duration_days: Test duration
            traffic_split: Traffic distribution
            min_sample_size: Minimum conversions needed

        Returns:
            Created ABTest instance

        Example:
            test = manager.create_title_test(
                product_id="12345",
                store_id="store1",
                current_title="Smart Watch with Fitness Tracker",
                variant_titles=[
                    "Premium Fitness Smart Watch - Track Your Health",
                    "Smart Watch: Monitor Heart Rate, Sleep & Steps"
                ]
            )
        """

        if not test_name:
            test_name = f"Title Test: {current_title[:30]}..."

        # Create variants
        variants = [
            {
                "name": "Control Title",
                "config": {
                    "title": current_title,
                    "title_length": len(current_title),
                    "is_control": True
                }
            }
        ]

        for i, title in enumerate(variant_titles, start=1):
            variants.append({
                "name": f"Variant {i}",
                "config": {
                    "title": title,
                    "title_length": len(title)
                }
            })

        scheduled_end = datetime.utcnow() + timedelta(days=duration_days)

        test = self.engine.create_test(
            name=test_name,
            test_type=TestType.PRODUCT_TITLE,
            product_id=product_id,
            store_id=store_id,
            variants=variants,
            traffic_split=traffic_split,
            scheduled_start=None,
            scheduled_end=scheduled_end,
            min_sample_size=min_sample_size,
            metadata={
                "current_title": current_title,
                "variant_titles": variant_titles
            }
        )

        return test

    def create_description_test(
        self,
        product_id: str,
        store_id: str,
        current_description: str,
        variant_descriptions: List[str],
        test_name: Optional[str] = None,
        duration_days: int = 14,
        traffic_split: Optional[List[float]] = None,
        min_sample_size: int = 100
    ) -> ABTest:
        """
        Create a product description A/B test

        Tests different product description styles:
        - Feature-focused vs benefit-focused
        - Short vs detailed
        - Different formatting/bullet points

        Args:
            product_id: Product to test
            store_id: Store running test
            current_description: Current description (control)
            variant_descriptions: Alternative descriptions
            test_name: Custom test name
            duration_days: Test duration
            traffic_split: Traffic distribution
            min_sample_size: Minimum conversions

        Returns:
            Created ABTest instance
        """

        if not test_name:
            test_name = f"Description Test: Product {product_id}"

        # Analyze description characteristics
        def analyze_description(desc: str) -> Dict[str, Any]:
            return {
                "length": len(desc),
                "word_count": len(desc.split()),
                "has_bullets": "•" in desc or "-" in desc[:100],
                "has_emojis": any(ord(c) > 127 for c in desc[:100])
            }

        # Create variants
        variants = [
            {
                "name": "Control Description",
                "config": {
                    "description": current_description,
                    **analyze_description(current_description),
                    "is_control": True
                }
            }
        ]

        for i, description in enumerate(variant_descriptions, start=1):
            variants.append({
                "name": f"Variant {i}",
                "config": {
                    "description": description,
                    **analyze_description(description)
                }
            })

        scheduled_end = datetime.utcnow() + timedelta(days=duration_days)

        test = self.engine.create_test(
            name=test_name,
            test_type=TestType.PRODUCT_DESCRIPTION,
            product_id=product_id,
            store_id=store_id,
            variants=variants,
            traffic_split=traffic_split,
            scheduled_start=None,
            scheduled_end=scheduled_end,
            min_sample_size=min_sample_size,
            metadata={
                "current_description": current_description[:200],
                "variant_count": len(variant_descriptions)
            }
        )

        return test

    def create_image_test(
        self,
        product_id: str,
        store_id: str,
        current_image_url: str,
        variant_image_urls: List[str],
        test_name: Optional[str] = None,
        duration_days: int = 14,
        traffic_split: Optional[List[float]] = None,
        min_sample_size: int = 100
    ) -> ABTest:
        """
        Create a product image A/B test

        Tests different product images:
        - White background vs lifestyle
        - Different angles
        - With/without model
        - Close-up vs full product

        Args:
            product_id: Product to test
            store_id: Store running test
            current_image_url: Current primary image (control)
            variant_image_urls: Alternative images
            test_name: Custom test name
            duration_days: Test duration
            traffic_split: Traffic distribution
            min_sample_size: Minimum conversions

        Returns:
            Created ABTest instance
        """

        if not test_name:
            test_name = f"Image Test: Product {product_id}"

        # Create variants
        variants = [
            {
                "name": "Control Image",
                "config": {
                    "image_url": current_image_url,
                    "is_control": True
                }
            }
        ]

        for i, image_url in enumerate(variant_image_urls, start=1):
            variants.append({
                "name": f"Variant {i}",
                "config": {
                    "image_url": image_url
                }
            })

        scheduled_end = datetime.utcnow() + timedelta(days=duration_days)

        test = self.engine.create_test(
            name=test_name,
            test_type=TestType.PRODUCT_IMAGE,
            product_id=product_id,
            store_id=store_id,
            variants=variants,
            traffic_split=traffic_split,
            scheduled_start=None,
            scheduled_end=scheduled_end,
            min_sample_size=min_sample_size,
            metadata={
                "current_image_url": current_image_url,
                "variant_image_urls": variant_image_urls
            }
        )

        return test

    def get_content_for_visitor(
        self,
        test_id: int,
        visitor_id: str,
        content_type: str
    ) -> Optional[str]:
        """
        Get content variant for visitor

        Args:
            test_id: Active test ID
            visitor_id: Visitor identifier
            content_type: "title", "description", or "image_url"

        Returns:
            Content to show visitor
        """
        variant = self.engine.get_variant_for_visitor(test_id, visitor_id)

        if not variant:
            return None

        return variant.config.get(content_type)

    def implement_winning_content(
        self,
        test_id: int,
        winner_variant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Apply winning content variant to product

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

        # Extract winning content based on test type
        winning_content = {}

        if test.test_type == TestType.PRODUCT_TITLE.value:
            winning_content["title"] = winner.config.get("title")
        elif test.test_type == TestType.PRODUCT_DESCRIPTION.value:
            winning_content["description"] = winner.config.get("description")
        elif test.test_type == TestType.PRODUCT_IMAGE.value:
            winning_content["image_url"] = winner.config.get("image_url")

        # Update test
        test.winner_variant_id = winner_variant_id
        test.status = "ended"
        test.ended_at = datetime.utcnow()
        test.test_metadata = test.test_metadata or {}
        test.test_metadata["implemented_at"] = datetime.utcnow().isoformat()
        test.test_metadata["winning_content"] = winning_content

        self.db.commit()

        # TODO: Update product in database
        # TODO: Sync to Shopify

        return {
            "success": True,
            "test_id": test_id,
            "test_type": test.test_type,
            "winner_variant_id": winner_variant_id,
            "winning_content": winning_content,
            "product_id": test.product_id,
            "store_id": test.store_id
        }

    def generate_title_variants(
        self,
        current_title: str,
        product_category: Optional[str] = None,
        key_features: Optional[List[str]] = None,
        target_audience: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate title variant suggestions using AI or templates

        Args:
            current_title: Current product title
            product_category: Product category (e.g., "fitness", "home")
            key_features: List of key features to highlight
            target_audience: Target customer (e.g., "fitness enthusiasts")

        Returns:
            List of suggested title variants with rationale
        """
        variants = []

        # 1. Feature-focused variant
        if key_features:
            feature_title = f"{current_title.split()[0]} - {', '.join(key_features[:3])}"
            variants.append({
                "title": feature_title,
                "strategy": "feature_focused",
                "description": "Highlights key product features in title",
                "expected_impact": "Appeals to feature-conscious buyers"
            })

        # 2. Benefit-focused variant
        benefit_words = {
            "fitness": "Get Fit, Stay Healthy",
            "home": "Transform Your Home",
            "tech": "Upgrade Your Lifestyle",
            "beauty": "Look & Feel Amazing"
        }

        if product_category and product_category.lower() in benefit_words:
            benefit = benefit_words[product_category.lower()]
            benefit_title = f"{current_title} - {benefit}"
            variants.append({
                "title": benefit_title,
                "strategy": "benefit_focused",
                "description": "Emphasizes customer benefits",
                "expected_impact": "Emotional appeal to target audience"
            })

        # 3. Question format
        question_title = f"Looking for {current_title}? Here's the Best!"
        variants.append({
            "title": question_title,
            "strategy": "question_format",
            "description": "Engages curiosity with question",
            "expected_impact": "Higher click-through from search"
        })

        # 4. Social proof variant
        social_title = f"{current_title} - Trusted by Thousands"
        variants.append({
            "title": social_title,
            "strategy": "social_proof",
            "description": "Adds credibility with social proof",
            "expected_impact": "Builds trust with new customers"
        })

        # 5. Urgency variant
        urgency_title = f"{current_title} - Limited Stock Available"
        variants.append({
            "title": urgency_title,
            "strategy": "urgency",
            "description": "Creates sense of scarcity",
            "expected_impact": "Encourages faster purchase decisions"
        })

        return variants[:4]  # Return top 4 variants

    def generate_description_variants(
        self,
        current_description: str,
        key_features: Optional[List[str]] = None,
        benefits: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate description variant suggestions

        Args:
            current_description: Current description
            key_features: Product features
            benefits: Customer benefits

        Returns:
            List of suggested description variants
        """
        variants = []

        # 1. Bullet point format
        if key_features:
            bullet_desc = "[NEW] Key Features:\n\n"
            bullet_desc += "\n".join([f"• {feature}" for feature in key_features])

            if benefits:
                bullet_desc += "\n\n Benefits:\n\n"
                bullet_desc += "\n".join([f"• {benefit}" for benefit in benefits])

            variants.append({
                "description": bullet_desc,
                "strategy": "bullet_points",
                "description_meta": "Easy-to-scan bullet format",
                "expected_impact": "Higher readability, better mobile experience"
            })

        # 2. Story format
        story_desc = f"Imagine {benefits[0] if benefits else 'transforming your life'}. "
        story_desc += f"{current_description[:200]}... "
        story_desc += "Join thousands of satisfied customers who made the switch!"

        variants.append({
            "description": story_desc,
            "strategy": "storytelling",
            "description_meta": "Narrative approach with emotional appeal",
            "expected_impact": "Stronger emotional connection"
        })

        # 3. Problem-solution format
        problem_solution = "Tired of low-quality alternatives? "
        problem_solution += f"Our product solves that. {current_description[:150]}... "
        problem_solution += "Experience the difference today!"

        variants.append({
            "description": problem_solution,
            "strategy": "problem_solution",
            "description_meta": "Addresses pain points directly",
            "expected_impact": "Resonates with frustrated customers"
        })

        return variants

    def get_content_test_insights(self, test_id: int) -> Dict[str, Any]:
        """
        Get insights from content test results

        Analyzes which content characteristics drive conversions.
        """
        test_data = self.engine.get_test(test_id, include_results=True)

        if not test_data:
            raise ValueError(f"Test {test_id} not found")

        # Find best performing variant
        best_variant = max(
            test_data["variants"],
            key=lambda v: v.get("conversion_rate", 0)
        )

        insights = {
            "test_id": test_id,
            "test_type": test_data["test_type"],
            "best_variant": best_variant["name"],
            "best_conversion_rate": best_variant["conversion_rate"],
            "insights": []
        }

        # Type-specific insights
        if test_data["test_type"] == "product_title":
            control = next((v for v in test_data["variants"] if v["is_control"]), None)

            if control and best_variant != control:
                title_length_diff = best_variant["config"].get("title_length", 0) - control["config"].get("title_length", 0)

                if title_length_diff > 10:
                    insights["insights"].append("Longer, more descriptive titles perform better")
                elif title_length_diff < -10:
                    insights["insights"].append("Shorter, punchier titles convert higher")

        elif test_data["test_type"] == "product_description":
            # Analyze description characteristics
            best_config = best_variant["config"]

            if best_config.get("has_bullets"):
                insights["insights"].append("Bullet-point formatting improves readability and conversions")

            if best_config.get("has_emojis"):
                insights["insights"].append("Emojis in descriptions increase engagement")

        return insights
