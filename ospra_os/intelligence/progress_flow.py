"""
PROGRESS FLOW - PRODUCT LIFECYCLE TRACKER

Tracks products through their entire lifecycle with visual progress indicators.

Lifecycle stages:
1. DISCOVERY - Product found by intelligence engine
2. ANALYSIS - Being graded and evaluated
3. DEPLOY - Ready to deploy / deployment in progress
4. ACTIVE - Live in store and selling
5. REVIEW - Performance review period (30/60/90 days)
6. DROPPED - Discontinued or removed

Features:
- Auto-progression based on events
- Progress percentage (0-100%)
- Next milestone tracking
- Historical stage tracking
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ospra_os.database.multi_store_models import Product, ProductStatus

logger = logging.getLogger(__name__)


class LifecycleStage(str, Enum):
    """Product lifecycle stages"""
    DISCOVERY = "discovery"
    ANALYSIS = "analysis"
    DEPLOY = "deploy"
    ACTIVE = "active"
    REVIEW = "review"
    DROPPED = "dropped"


class ProgressFlowTracker:
    """
    Tracks product progress through lifecycle stages.

    Provides:
    - Current stage
    - Progress percentage within stage
    - Next milestone
    - Days in current stage
    - Historical stage transitions
    """

    # Stage progression rules
    STAGE_PROGRESSION = {
        LifecycleStage.DISCOVERY: LifecycleStage.ANALYSIS,
        LifecycleStage.ANALYSIS: LifecycleStage.DEPLOY,
        LifecycleStage.DEPLOY: LifecycleStage.ACTIVE,
        LifecycleStage.ACTIVE: LifecycleStage.REVIEW,
        LifecycleStage.REVIEW: None,  # Can go to ACTIVE or DROPPED
    }

    # Expected duration in each stage (days)
    STAGE_DURATIONS = {
        LifecycleStage.DISCOVERY: 1,  # Quick discovery
        LifecycleStage.ANALYSIS: 2,   # AI grading
        LifecycleStage.DEPLOY: 3,     # Deployment prep
        LifecycleStage.ACTIVE: 30,    # First review at 30 days
        LifecycleStage.REVIEW: 7,     # Review period
    }

    def __init__(self, db: Session):
        self.db = db

    async def get_product_progress(self, product_id: int) -> Dict[str, Any]:
        """
        Get complete progress information for product.

        Returns:
            {
                "product_id": 123,
                "current_stage": "active",
                "progress_percentage": 75,
                "days_in_stage": 23,
                "next_milestone": "30-day review",
                "next_milestone_date": "2025-12-05",
                "stage_history": [
                    {"stage": "discovery", "entered": "2025-11-01", "duration_days": 1},
                    {"stage": "analysis", "entered": "2025-11-02", "duration_days": 2},
                    ...
                ],
                "milestones": {
                    "discovered": {"date": "2025-11-01", "completed": true},
                    "analyzed": {"date": "2025-11-02", "completed": true},
                    "deployed": {"date": "2025-11-05", "completed": true},
                    "30_day_review": {"date": "2025-12-05", "completed": false},
                    "60_day_review": {"date": "2026-01-04", "completed": false},
                    "90_day_review": {"date": "2026-02-03", "completed": false}
                }
            }
        """
        logger.info(f"Getting progress for product {product_id}")

        product = self.db.query(Product).filter(Product.id == product_id).first()

        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Determine current stage
        current_stage = self._determine_stage(product)

        # Calculate progress percentage
        progress_pct = self._calculate_progress(product, current_stage)

        # Get days in current stage
        days_in_stage = self._get_days_in_stage(product, current_stage)

        # Get next milestone
        next_milestone, next_date = self._get_next_milestone(product, current_stage)

        # Build stage history
        stage_history = self._build_stage_history(product)

        # Get all milestones
        milestones = self._get_all_milestones(product)

        return {
            "product_id": product_id,
            "product_title": product.title,
            "current_stage": current_stage.value,
            "progress_percentage": progress_pct,
            "days_in_stage": days_in_stage,
            "next_milestone": next_milestone,
            "next_milestone_date": next_date.isoformat() if next_date else None,
            "stage_history": stage_history,
            "milestones": milestones,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def advance_stage(
        self,
        product_id: int,
        new_stage: LifecycleStage,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Manually advance product to new stage.

        Args:
            product_id: Product ID
            new_stage: Target stage
            note: Optional note about the transition

        Returns:
            Updated progress info
        """
        logger.info(f"Advancing product {product_id} to stage {new_stage.value}")

        product = self.db.query(Product).filter(Product.id == product_id).first()

        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Update product status based on stage
        status_mapping = {
            LifecycleStage.DISCOVERY: ProductStatus.DISCOVERED,
            LifecycleStage.ANALYSIS: ProductStatus.DISCOVERED,
            LifecycleStage.DEPLOY: ProductStatus.QUEUED,
            LifecycleStage.ACTIVE: ProductStatus.ACTIVE,
            LifecycleStage.REVIEW: ProductStatus.ACTIVE,
            LifecycleStage.DROPPED: ProductStatus.DISCONTINUED
        }

        product.status = status_mapping[new_stage]

        # Update timestamps
        if new_stage == LifecycleStage.DEPLOY and not product.queued_at:
            product.queued_at = datetime.utcnow()

        if new_stage == LifecycleStage.ACTIVE and not product.deployed_at:
            product.deployed_at = datetime.utcnow()

        self.db.commit()

        # Get updated progress
        return await self.get_product_progress(product_id)

    def _determine_stage(self, product: Product) -> LifecycleStage:
        """Determine current lifecycle stage from product status"""

        if product.status == ProductStatus.DISCONTINUED:
            return LifecycleStage.DROPPED

        if product.status == ProductStatus.ACTIVE:
            # Check if in review period (30/60/90 days)
            if product.deployed_at:
                days_active = (datetime.utcnow() - product.deployed_at).days

                # Review periods: 30, 60, 90 days
                if days_active in range(28, 35) or days_active in range(58, 65) or days_active in range(88, 95):
                    return LifecycleStage.REVIEW

            return LifecycleStage.ACTIVE

        if product.status in [ProductStatus.QUEUED, ProductStatus.DEPLOYING, ProductStatus.DEPLOYED]:
            return LifecycleStage.DEPLOY

        if product.grade and product.grade != "":
            return LifecycleStage.ANALYSIS

        return LifecycleStage.DISCOVERY

    def _calculate_progress(self, product: Product, stage: LifecycleStage) -> int:
        """
        Calculate progress percentage within current stage.

        Progress based on:
        - DISCOVERY: Always 100% (instant)
        - ANALYSIS: Based on grade completion
        - DEPLOY: Based on deployment steps
        - ACTIVE: Based on days active vs 30-day milestone
        - REVIEW: Based on review completion
        """

        if stage == LifecycleStage.DISCOVERY:
            return 100

        if stage == LifecycleStage.ANALYSIS:
            # Has grade = 100%
            return 100 if product.grade else 50

        if stage == LifecycleStage.DEPLOY:
            # Based on deployment status
            if product.status == ProductStatus.DEPLOYED:
                return 100
            elif product.status == ProductStatus.DEPLOYING:
                return 75
            elif product.status == ProductStatus.QUEUED:
                return 25
            else:
                return 10

        if stage == LifecycleStage.ACTIVE:
            # Progress toward 30-day milestone
            if product.deployed_at:
                days_active = (datetime.utcnow() - product.deployed_at).days
                return min(int((days_active / 30) * 100), 100)
            return 0

        if stage == LifecycleStage.REVIEW:
            # Review progress (assume 7-day review period)
            return 50  # In progress

        if stage == LifecycleStage.DROPPED:
            return 100

        return 0

    def _get_days_in_stage(self, product: Product, stage: LifecycleStage) -> int:
        """Calculate days product has been in current stage"""

        reference_date = datetime.utcnow()

        if stage == LifecycleStage.DISCOVERY:
            if product.discovered_at:
                return (reference_date - product.discovered_at).days
            return 0

        if stage == LifecycleStage.ANALYSIS:
            # Time since discovery or grading started
            start_date = product.discovered_at or product.created_at
            return (reference_date - start_date).days

        if stage == LifecycleStage.DEPLOY:
            if product.queued_at:
                return (reference_date - product.queued_at).days
            return 0

        if stage == LifecycleStage.ACTIVE:
            if product.deployed_at:
                return (reference_date - product.deployed_at).days
            return 0

        if stage == LifecycleStage.REVIEW:
            # Assume entered review 2 days ago (configurable)
            return 2

        if stage == LifecycleStage.DROPPED:
            if product.updated_at:
                return (reference_date - product.updated_at).days
            return 0

        return 0

    def _get_next_milestone(
        self,
        product: Product,
        stage: LifecycleStage
    ) -> Tuple[str, Optional[datetime]]:
        """Get next milestone name and date"""

        if stage == LifecycleStage.DISCOVERY:
            return "AI Analysis", datetime.utcnow() + timedelta(days=1)

        if stage == LifecycleStage.ANALYSIS:
            return "Deploy Decision", datetime.utcnow() + timedelta(days=2)

        if stage == LifecycleStage.DEPLOY:
            return "Go Live", datetime.utcnow() + timedelta(days=3)

        if stage == LifecycleStage.ACTIVE:
            if product.deployed_at:
                days_active = (datetime.utcnow() - product.deployed_at).days

                if days_active < 30:
                    return "30-Day Review", product.deployed_at + timedelta(days=30)
                elif days_active < 60:
                    return "60-Day Review", product.deployed_at + timedelta(days=60)
                elif days_active < 90:
                    return "90-Day Review", product.deployed_at + timedelta(days=90)
                else:
                    return "Quarterly Review", product.deployed_at + timedelta(days=120)

            return "30-Day Review", None

        if stage == LifecycleStage.REVIEW:
            return "Review Complete", datetime.utcnow() + timedelta(days=7)

        if stage == LifecycleStage.DROPPED:
            return "Archived", None

        return "Unknown", None

    def _build_stage_history(self, product: Product) -> List[Dict[str, Any]]:
        """Build historical list of stage transitions"""
        history = []

        # Discovery
        if product.discovered_at:
            history.append({
                "stage": "discovery",
                "entered": product.discovered_at.isoformat(),
                "duration_days": 1
            })

        # Analysis (when grade was assigned)
        if product.grade:
            analysis_date = product.discovered_at + timedelta(days=1) if product.discovered_at else product.created_at
            history.append({
                "stage": "analysis",
                "entered": analysis_date.isoformat(),
                "duration_days": 2
            })

        # Deploy
        if product.queued_at:
            history.append({
                "stage": "deploy",
                "entered": product.queued_at.isoformat(),
                "duration_days": (product.deployed_at - product.queued_at).days if product.deployed_at else 0
            })

        # Active
        if product.deployed_at:
            history.append({
                "stage": "active",
                "entered": product.deployed_at.isoformat(),
                "duration_days": (datetime.utcnow() - product.deployed_at).days
            })

        return history

    def _get_all_milestones(self, product: Product) -> Dict[str, Any]:
        """Get all product milestones with completion status"""
        milestones = {}

        # Discovered
        milestones["discovered"] = {
            "date": product.discovered_at.isoformat() if product.discovered_at else None,
            "completed": bool(product.discovered_at)
        }

        # Analyzed
        if product.grade:
            analyze_date = product.discovered_at + timedelta(days=1) if product.discovered_at else product.created_at
            milestones["analyzed"] = {
                "date": analyze_date.isoformat(),
                "completed": True
            }
        else:
            milestones["analyzed"] = {
                "date": None,
                "completed": False
            }

        # Deployed
        milestones["deployed"] = {
            "date": product.deployed_at.isoformat() if product.deployed_at else None,
            "completed": bool(product.deployed_at)
        }

        # Review milestones
        if product.deployed_at:
            milestones["30_day_review"] = {
                "date": (product.deployed_at + timedelta(days=30)).isoformat(),
                "completed": (datetime.utcnow() - product.deployed_at).days >= 30
            }
            milestones["60_day_review"] = {
                "date": (product.deployed_at + timedelta(days=60)).isoformat(),
                "completed": (datetime.utcnow() - product.deployed_at).days >= 60
            }
            milestones["90_day_review"] = {
                "date": (product.deployed_at + timedelta(days=90)).isoformat(),
                "completed": (datetime.utcnow() - product.deployed_at).days >= 90
            }
        else:
            milestones["30_day_review"] = {"date": None, "completed": False}
            milestones["60_day_review"] = {"date": None, "completed": False}
            milestones["90_day_review"] = {"date": None, "completed": False}

        return milestones

    async def get_products_by_stage(
        self,
        stage: LifecycleStage,
        user_id: Optional[int] = None,
        store_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get all products in a specific lifecycle stage.

        Args:
            stage: Lifecycle stage to filter by
            user_id: Optional user filter
            store_id: Optional store filter
            limit: Max results to return

        Returns:
            List of products with progress info
        """
        # Map stage to product status
        status_mapping = {
            LifecycleStage.DISCOVERY: [ProductStatus.DISCOVERED],
            LifecycleStage.ANALYSIS: [ProductStatus.DISCOVERED],
            LifecycleStage.DEPLOY: [ProductStatus.QUEUED, ProductStatus.DEPLOYING, ProductStatus.DEPLOYED],
            LifecycleStage.ACTIVE: [ProductStatus.ACTIVE],
            LifecycleStage.REVIEW: [ProductStatus.ACTIVE],
            LifecycleStage.DROPPED: [ProductStatus.DISCONTINUED]
        }

        query = self.db.query(Product).filter(Product.status.in_(status_mapping.get(stage, [])))

        if store_id:
            query = query.filter(Product.store_id == store_id)

        products = query.limit(limit).all()

        # Build progress info for each
        results = []
        for product in products:
            progress = await self.get_product_progress(product.id)
            results.append(progress)

        return results


# Singleton instance
_progress_tracker = None


def get_progress_tracker(db: Session) -> ProgressFlowTracker:
    """Get or create progress flow tracker instance"""
    global _progress_tracker
    if _progress_tracker is None:
        _progress_tracker = ProgressFlowTracker(db)
    return _progress_tracker
