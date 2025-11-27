"""
Core A/B Testing Engine for Ospra OS

Manages creation, execution, and analysis of A/B tests across products.
Supports price tests, content tests, and ad creative tests.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
import random
import hashlib
from enum import Enum

from ospra_os.database.multi_store_models import (
    ABTest, ABTestVariant, ABTestEvent, ABTestAssignment
)


class TestStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    ENDED = "ended"


class TestType(str, Enum):
    PRICE = "price"
    PRODUCT_TITLE = "product_title"
    PRODUCT_DESCRIPTION = "product_description"
    PRODUCT_IMAGE = "product_image"
    AD_CREATIVE = "ad_creative"
    AD_COPY = "ad_copy"


class EventType(str, Enum):
    IMPRESSION = "impression"
    CLICK = "click"
    ADD_TO_CART = "add_to_cart"
    PURCHASE = "purchase"


class ABTestEngine:
    """
    Core A/B Testing Engine

    Handles test lifecycle, variant assignment, event tracking, and results analysis.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def create_test(
        self,
        name: str,
        test_type: TestType,
        product_id: str,
        store_id: str,
        variants: List[Dict[str, Any]],
        traffic_split: Optional[List[float]] = None,
        scheduled_start: Optional[datetime] = None,
        scheduled_end: Optional[datetime] = None,
        min_sample_size: int = 100,
        confidence_level: float = 0.95,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ABTest:
        """
        Create a new A/B test

        Args:
            name: Test name (e.g., "Smart Watch Price Test $29 vs $39")
            test_type: Type of test (price, title, description, etc.)
            product_id: Product being tested
            store_id: Store running the test
            variants: List of variant configs, e.g.:
                [
                    {"name": "Control", "config": {"price": 29.99}},
                    {"name": "Higher Price", "config": {"price": 39.99}}
                ]
            traffic_split: Traffic % for each variant (must sum to 100)
            scheduled_start: When to start test (None = manual start)
            scheduled_end: When to end test
            min_sample_size: Minimum conversions before declaring winner
            confidence_level: Statistical confidence (0.95 = 95%)
            metadata: Additional test metadata

        Returns:
            Created ABTest instance
        """

        # Validate variants
        if len(variants) < 2:
            raise ValueError("A/B test requires at least 2 variants")

        # Default traffic split: equal distribution
        if traffic_split is None:
            traffic_split = [100 / len(variants)] * len(variants)

        # Validate traffic split
        if len(traffic_split) != len(variants):
            raise ValueError("Traffic split must match number of variants")
        if abs(sum(traffic_split) - 100) > 0.01:
            raise ValueError("Traffic split must sum to 100")

        # Determine initial status
        status = TestStatus.DRAFT
        if scheduled_start and scheduled_start <= datetime.utcnow():
            status = TestStatus.RUNNING
        elif scheduled_start:
            status = TestStatus.SCHEDULED

        # Create test
        test = ABTest(
            name=name,
            test_type=test_type.value,
            product_id=product_id,
            store_id=store_id,
            status=status.value,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            min_sample_size=min_sample_size,
            confidence_level=confidence_level,
            metadata=metadata or {}
        )

        self.db.add(test)
        self.db.flush()  # Get test.id

        # Create variants
        for i, variant_config in enumerate(variants):
            variant = ABTestVariant(
                test_id=test.id,
                name=variant_config["name"],
                config=variant_config.get("config", {}),
                traffic_percentage=traffic_split[i],
                is_control=i == 0  # First variant is control
            )
            self.db.add(variant)

        self.db.commit()
        self.db.refresh(test)

        return test

    def get_test(self, test_id: int, include_results: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get test details with current results

        Args:
            test_id: Test ID
            include_results: Whether to calculate current results

        Returns:
            Test data with variants and results
        """
        result = self.db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = result.scalar_one_or_none()

        if not test:
            return None

        # Get variants
        variants_result = self.db.execute(
            select(ABTestVariant).where(ABTestVariant.test_id == test_id)
        )
        variants = variants_result.scalars().all()

        test_data = {
            "id": test.id,
            "name": test.name,
            "test_type": test.test_type,
            "product_id": test.product_id,
            "store_id": test.store_id,
            "status": test.status,
            "scheduled_start": test.scheduled_start.isoformat() if test.scheduled_start else None,
            "scheduled_end": test.scheduled_end.isoformat() if test.scheduled_end else None,
            "started_at": test.started_at.isoformat() if test.started_at else None,
            "ended_at": test.ended_at.isoformat() if test.ended_at else None,
            "min_sample_size": test.min_sample_size,
            "confidence_level": test.confidence_level,
            "winner_variant_id": test.winner_variant_id,
            "test_metadata": test.test_metadata,
            "variants": []
        }

        # Add variant data
        for variant in variants:
            variant_data = {
                "id": variant.id,
                "name": variant.name,
                "config": variant.config,
                "traffic_percentage": variant.traffic_percentage,
                "is_control": variant.is_control,
                "impressions": variant.impressions,
                "clicks": variant.clicks,
                "conversions": variant.conversions,
                "revenue": float(variant.revenue) if variant.revenue else 0.0
            }

            # Calculate rates
            if variant.impressions > 0:
                variant_data["ctr"] = (variant.clicks / variant.impressions) * 100
                variant_data["conversion_rate"] = (variant.conversions / variant.impressions) * 100
            else:
                variant_data["ctr"] = 0.0
                variant_data["conversion_rate"] = 0.0

            if variant.conversions > 0:
                variant_data["avg_order_value"] = float(variant.revenue) / variant.conversions
            else:
                variant_data["avg_order_value"] = 0.0

            test_data["variants"].append(variant_data)

        # Calculate statistical significance if requested
        if include_results and test.status in [TestStatus.RUNNING.value, TestStatus.ENDED.value]:
            from .statistics import StatisticalCalculator

            calculator = StatisticalCalculator()

            # Find control variant
            control = next((v for v in test_data["variants"] if v["is_control"]), None)

            if control:
                for variant in test_data["variants"]:
                    if not variant["is_control"]:
                        significance = calculator.calculate_significance(
                            control_conversions=control["conversions"],
                            control_impressions=control["impressions"],
                            variant_conversions=variant["conversions"],
                            variant_impressions=variant["impressions"],
                            confidence_level=test.confidence_level
                        )
                        variant["statistical_significance"] = significance

        return test_data

    def list_tests(
        self,
        store_id: Optional[str] = None,
        product_id: Optional[str] = None,
        status: Optional[TestStatus] = None,
        test_type: Optional[TestType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all tests with optional filters

        Args:
            store_id: Filter by store
            product_id: Filter by product
            status: Filter by status
            test_type: Filter by type
            limit: Max results
            offset: Pagination offset

        Returns:
            List of test summaries
        """
        query = select(ABTest)

        # Apply filters
        filters = []
        if store_id:
            filters.append(ABTest.store_id == store_id)
        if product_id:
            filters.append(ABTest.product_id == product_id)
        if status:
            filters.append(ABTest.status == status.value)
        if test_type:
            filters.append(ABTest.test_type == test_type.value)

        if filters:
            query = query.where(and_(*filters))

        query = query.order_by(ABTest.created_at.desc()).limit(limit).offset(offset)

        result = self.db.execute(query)
        tests = result.scalars().all()

        # Get summaries
        test_list = []
        for test in tests:
            test_list.append({
                "id": test.id,
                "name": test.name,
                "test_type": test.test_type,
                "product_id": test.product_id,
                "store_id": test.store_id,
                "status": test.status,
                "started_at": test.started_at.isoformat() if test.started_at else None,
                "ended_at": test.ended_at.isoformat() if test.ended_at else None,
                "winner_variant_id": test.winner_variant_id,
                "created_at": test.created_at.isoformat()
            })

        return test_list

    def start_test(self, test_id: int) -> ABTest:
        """Start a draft or scheduled test"""
        result = self.db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = result.scalar_one_or_none()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        if test.status not in [TestStatus.DRAFT.value, TestStatus.SCHEDULED.value]:
            raise ValueError(f"Cannot start test in status: {test.status}")

        test.status = TestStatus.RUNNING.value
        test.started_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(test)

        return test

    def pause_test(self, test_id: int) -> ABTest:
        """Pause a running test"""
        result = self.db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = result.scalar_one_or_none()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        if test.status != TestStatus.RUNNING.value:
            raise ValueError(f"Cannot pause test in status: {test.status}")

        test.status = TestStatus.PAUSED.value

        self.db.commit()
        self.db.refresh(test)

        return test

    def resume_test(self, test_id: int) -> ABTest:
        """Resume a paused test"""
        result = self.db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = result.scalar_one_or_none()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        if test.status != TestStatus.PAUSED.value:
            raise ValueError(f"Cannot resume test in status: {test.status}")

        test.status = TestStatus.RUNNING.value

        self.db.commit()
        self.db.refresh(test)

        return test

    def end_test(
        self,
        test_id: int,
        implement_winner: bool = False,
        winner_variant_id: Optional[int] = None
    ) -> ABTest:
        """
        End a test and optionally implement winner

        Args:
            test_id: Test ID
            implement_winner: Whether to apply winning variant
            winner_variant_id: Manual winner selection (overrides auto-detection)

        Returns:
            Updated test
        """
        result = self.db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = result.scalar_one_or_none()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        if test.status not in [TestStatus.RUNNING.value, TestStatus.PAUSED.value]:
            raise ValueError(f"Cannot end test in status: {test.status}")

        # Determine winner if not manually specified
        if implement_winner and not winner_variant_id:
            winner_variant_id = self.determine_winner(test_id)

        test.status = TestStatus.ENDED.value
        test.ended_at = datetime.utcnow()
        test.winner_variant_id = winner_variant_id

        self.db.commit()

        # Implement winner if requested
        if implement_winner and winner_variant_id:
            self.implement_winner(test_id, winner_variant_id)

        self.db.refresh(test)
        return test

    def get_variant_for_visitor(
        self,
        test_id: int,
        visitor_id: str
    ) -> Optional[ABTestVariant]:
        """
        Assign visitor to a variant (consistent assignment)

        Uses deterministic hashing to ensure same visitor always gets same variant.

        Args:
            test_id: Test ID
            visitor_id: Unique visitor identifier (IP, session ID, etc.)

        Returns:
            Assigned variant
        """
        # Check for existing assignment
        result = self.db.execute(
            select(ABTestAssignment).where(
                and_(
                    ABTestAssignment.test_id == test_id,
                    ABTestAssignment.visitor_id == visitor_id
                )
            )
        )
        assignment = result.scalar_one_or_none()

        if assignment:
            # Return existing assignment
            variant_result = self.db.execute(
                select(ABTestVariant).where(ABTestVariant.id == assignment.variant_id)
            )
            return variant_result.scalar_one_or_none()

        # Get test and variants
        test_result = self.db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = test_result.scalar_one_or_none()

        if not test or test.status != TestStatus.RUNNING.value:
            return None

        variants_result = self.db.execute(
            select(ABTestVariant).where(ABTestVariant.test_id == test_id)
        )
        variants = list(variants_result.scalars().all())

        if not variants:
            return None

        # Deterministic variant selection based on visitor ID
        hash_value = int(hashlib.md5(f"{test_id}:{visitor_id}".encode()).hexdigest(), 16)
        random.seed(hash_value)

        # Weighted random selection based on traffic percentage
        weights = [v.traffic_percentage for v in variants]
        selected_variant = random.choices(variants, weights=weights)[0]

        # Reset random seed
        random.seed()

        # Save assignment
        new_assignment = ABTestAssignment(
            test_id=test_id,
            variant_id=selected_variant.id,
            visitor_id=visitor_id,
            assigned_at=datetime.utcnow()
        )
        self.db.add(new_assignment)
        self.db.commit()

        return selected_variant

    def record_impression(
        self,
        test_id: int,
        variant_id: int,
        visitor_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record that visitor saw the variant"""
        event = ABTestEvent(
            test_id=test_id,
            variant_id=variant_id,
            visitor_id=visitor_id,
            event_type=EventType.IMPRESSION.value,
            metadata=metadata or {},
            created_at=datetime.utcnow()
        )
        self.db.add(event)

        # Update variant impression count
        variant_result = self.db.execute(
            select(ABTestVariant).where(ABTestVariant.id == variant_id)
        )
        variant = variant_result.scalar_one_or_none()
        if variant:
            variant.impressions += 1

        self.db.commit()

    def record_conversion(
        self,
        test_id: int,
        variant_id: int,
        visitor_id: str,
        revenue: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a conversion event (purchase)"""
        event = ABTestEvent(
            test_id=test_id,
            variant_id=variant_id,
            visitor_id=visitor_id,
            event_type=EventType.PURCHASE.value,
            revenue=revenue,
            metadata=metadata or {},
            created_at=datetime.utcnow()
        )
        self.db.add(event)

        # Update variant conversion count and revenue
        variant_result = self.db.execute(
            select(ABTestVariant).where(ABTestVariant.id == variant_id)
        )
        variant = variant_result.scalar_one_or_none()
        if variant:
            variant.conversions += 1
            if revenue:
                variant.revenue = (variant.revenue or 0) + revenue

        self.db.commit()

    def calculate_results(self, test_id: int) -> Dict[str, Any]:
        """
        Calculate current results for all variants

        Returns performance metrics for each variant
        """
        test_data = self.get_test(test_id, include_results=True)

        if not test_data:
            raise ValueError(f"Test {test_id} not found")

        return {
            "test_id": test_id,
            "test_name": test_data["name"],
            "status": test_data["status"],
            "variants": test_data["variants"],
            "winner_variant_id": test_data["winner_variant_id"]
        }

    def check_statistical_significance(
        self,
        test_id: int
    ) -> Dict[int, Dict[str, Any]]:
        """
        Check if any variant has statistically significant results vs control

        Returns:
            Dict mapping variant_id to significance results
        """
        from .statistics import StatisticalCalculator

        test_data = self.get_test(test_id, include_results=False)

        if not test_data:
            raise ValueError(f"Test {test_id} not found")

        calculator = StatisticalCalculator()

        # Find control variant
        control = next((v for v in test_data["variants"] if v["is_control"]), None)

        if not control:
            raise ValueError("No control variant found")

        significance_results = {}

        for variant in test_data["variants"]:
            if variant["is_control"]:
                continue

            result = calculator.calculate_significance(
                control_conversions=control["conversions"],
                control_impressions=control["impressions"],
                variant_conversions=variant["conversions"],
                variant_impressions=variant["impressions"],
                confidence_level=test_data["confidence_level"]
            )

            significance_results[variant["id"]] = result

        return significance_results

    def determine_winner(self, test_id: int) -> Optional[int]:
        """
        Determine winning variant based on conversion rate and statistical significance

        Returns:
            Winning variant ID, or None if no clear winner
        """
        test_data = self.get_test(test_id, include_results=False)

        if not test_data:
            raise ValueError(f"Test {test_id} not found")

        # Get test model for min_sample_size
        test_result = self.db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = test_result.scalar_one_or_none()

        # Check if minimum sample size met
        max_conversions = max(v["conversions"] for v in test_data["variants"])
        if max_conversions < test.min_sample_size:
            return None  # Not enough data

        # Get significance results
        significance_results = self.check_statistical_significance(test_id)

        # Find variant with highest conversion rate that is statistically significant
        best_variant = None
        best_conversion_rate = 0

        for variant in test_data["variants"]:
            variant_id = variant["id"]
            conversion_rate = variant["conversion_rate"]

            # Control is always a candidate
            if variant["is_control"]:
                if conversion_rate > best_conversion_rate:
                    best_variant = variant_id
                    best_conversion_rate = conversion_rate
            # Other variants must be statistically significant
            elif variant_id in significance_results:
                sig_result = significance_results[variant_id]
                if sig_result["is_significant"] and conversion_rate > best_conversion_rate:
                    best_variant = variant_id
                    best_conversion_rate = conversion_rate

        return best_variant

    def implement_winner(self, test_id: int, winner_variant_id: int):
        """
        Apply winning variant as the default for the product

        This will be called by type-specific managers (PriceTestManager, etc.)
        to actually apply the winning configuration.
        """
        # Get test and variant
        test_result = self.db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = test_result.scalar_one_or_none()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        variant_result = self.db.execute(
            select(ABTestVariant).where(ABTestVariant.id == winner_variant_id)
        )
        variant = variant_result.scalar_one_or_none()

        if not variant:
            raise ValueError(f"Variant {winner_variant_id} not found")

        # Store implementation metadata
        test.test_metadata = test.test_metadata or {}
        test.test_metadata["implemented_at"] = datetime.utcnow().isoformat()
        test.test_metadata["winning_config"] = variant.config

        self.db.commit()

        # Note: Actual implementation (updating Shopify, etc.) is handled by
        # type-specific managers in price_test_manager.py, content_test_manager.py, etc.
