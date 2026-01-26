"""
Store Service - GROK RECOMMENDATION #11: Multi-Store Selector with Cross-Store Learning

Handles store management and cross-store learning generation.
Users can manage multiple Shopify/Amazon/WooCommerce stores and apply learnings across them.

Example: "Yoga mats convert at 4.2% in Fitness First (Store A),
         recommend for Health Hub (Store B) if niche matches."
"""

from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, and_
from datetime import datetime, timedelta

from ospra_os.database import (
    Store,
    Product,
    CrossStoreLearning,
    StoreStatus,
    Platform,
    User
)
from ospra_os.database.action_models import Action


class StoreService:
    """
    Service for managing multiple stores and cross-store learning.

    Features:
    - List user stores with status and metrics
    - Switch between stores seamlessly
    - Generate cross-store learnings
    - Apply insights from Store A to Store B
    """

    def __init__(self, db: Session):
        self.db = db

    # ========================================================================
    # STORE MANAGEMENT
    # ========================================================================

    def get_user_stores(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all stores for a user with status and metrics.

        Returns:
            List of stores with:
            - id, name, platform, status
            - pending_actions_count
            - total_revenue, monthly_revenue
            - total_products
            - last_sync

        OPTIMIZED: Uses subqueries to avoid N+1 query pattern
        """
        # Subquery for product counts
        product_count_subq = self.db.query(
            Product.store_id,
            func.count(Product.id).label('product_count')
        ).group_by(Product.store_id).subquery()

        # Subquery for pending action counts
        pending_actions_subq = self.db.query(
            Action.store_id,
            func.count(Action.id).label('pending_count')
        ).filter(Action.status == "pending")\
            .group_by(Action.store_id).subquery()

        # Main query with left joins to subqueries
        stores_with_counts = self.db.query(
            Store,
            func.coalesce(product_count_subq.c.product_count, 0).label('product_count'),
            func.coalesce(pending_actions_subq.c.pending_count, 0).label('pending_count')
        ).outerjoin(
            product_count_subq, Store.id == product_count_subq.c.store_id
        ).outerjoin(
            pending_actions_subq, Store.id == pending_actions_subq.c.store_id
        ).filter(Store.user_id == user_id).all()

        store_data = []
        stores_to_update = []

        for store, product_count, pending_actions in stores_with_counts:
            # Track stores that need pending_actions_count update
            if store.pending_actions_count != pending_actions:
                store.pending_actions_count = pending_actions
                stores_to_update.append(store)

            store_data.append({
                "id": store.id,
                "store_name": store.store_name,
                "store_url": store.store_url,
                "platform": store.platform.value,
                "status": store.status.value,
                "niche": store.niche,
                "pending_actions_count": pending_actions,
                "total_revenue": store.total_revenue,
                "monthly_revenue": store.monthly_revenue,
                "total_orders": store.total_orders,
                "conversion_rate": store.conversion_rate,
                "total_products": product_count,
                "last_sync": store.last_sync.isoformat() if store.last_sync else None,
                "sync_error": store.sync_error,
                "created_at": store.created_at.isoformat(),
            })

        # Batch commit updates if any
        if stores_to_update:
            self.db.commit()

        return store_data

    def get_store(self, store_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get single store by ID (with user ownership check).

        Args:
            store_id: Store ID
            user_id: User ID for ownership verification

        Returns:
            Store data or None if not found/unauthorized
        """
        store = self.db.query(Store)\
            .filter(Store.id == store_id)\
            .filter(Store.user_id == user_id)\
            .first()

        if not store:
            return None

        # Count products
        product_count = self.db.query(func.count(Product.id))\
            .filter(Product.store_id == store.id)\
            .scalar() or 0

        # Count pending actions
        pending_actions = self.db.query(func.count(Action.id))\
            .filter(Action.store_id == store.id)\
            .filter(Action.status == "pending")\
            .scalar() or 0

        return {
            "id": store.id,
            "store_name": store.store_name,
            "store_url": store.store_url,
            "platform": store.platform.value,
            "status": store.status.value,
            "niche": store.niche,
            "target_market": store.target_market,
            "currency": store.currency,
            "pending_actions_count": pending_actions,
            "total_revenue": store.total_revenue,
            "monthly_revenue": store.monthly_revenue,
            "total_orders": store.total_orders,
            "conversion_rate": store.conversion_rate,
            "total_products": product_count,
            "last_sync": store.last_sync.isoformat() if store.last_sync else None,
            "sync_error": store.sync_error,
            "created_at": store.created_at.isoformat(),
            "updated_at": store.updated_at.isoformat(),
        }

    def create_store(
        self,
        user_id: int,
        store_name: str,
        store_url: str,
        platform: str,
        credentials: Dict[str, Any],
        niche: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new store for user.

        Args:
            user_id: User ID
            store_name: Store display name
            store_url: Store URL
            platform: Platform type (shopify, amazon, woocommerce)
            credentials: Platform-specific credentials
            niche: Store niche (optional)

        Returns:
            Created store data
        """
        new_store = Store(
            user_id=user_id,
            store_name=store_name,
            store_url=store_url,
            platform=Platform(platform.lower()),
            credentials=credentials,
            niche=niche,
            status=StoreStatus.SETUP,
            is_active=True,
        )

        self.db.add(new_store)
        self.db.commit()
        self.db.refresh(new_store)

        # Update user's total_stores count
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.total_stores = self.db.query(func.count(Store.id))\
                .filter(Store.user_id == user_id)\
                .scalar() or 0
            self.db.commit()

        return {
            "id": new_store.id,
            "store_name": new_store.store_name,
            "platform": new_store.platform.value,
            "status": new_store.status.value,
            "niche": new_store.niche,
        }

    def update_store_status(
        self,
        store_id: int,
        user_id: int,
        status: str,
        sync_error: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update store status.

        Args:
            store_id: Store ID
            user_id: User ID for ownership verification
            status: New status (active, paused, disconnected, error)
            sync_error: Error message if status is error

        Returns:
            Updated store data or None if not found
        """
        store = self.db.query(Store)\
            .filter(Store.id == store_id)\
            .filter(Store.user_id == user_id)\
            .first()

        if not store:
            return None

        store.status = StoreStatus(status.lower())
        store.sync_error = sync_error
        store.updated_at = datetime.utcnow()

        # Update is_active for backward compatibility
        store.is_active = store.status in [StoreStatus.ACTIVE, StoreStatus.SETUP]

        self.db.commit()
        self.db.refresh(store)

        return {
            "id": store.id,
            "status": store.status.value,
            "sync_error": store.sync_error,
            "updated_at": store.updated_at.isoformat(),
        }

    # ========================================================================
    # CROSS-STORE LEARNING
    # ========================================================================

    def generate_cross_store_learnings(self, user_id: int) -> int:
        """
        Generate cross-store learning insights for all user stores.

        Analyzes performance in each store and generates recommendations
        for other stores with matching/compatible niches.

        Returns:
            Number of learnings generated
        """
        stores = self.db.query(Store)\
            .filter(Store.user_id == user_id)\
            .filter(Store.status == StoreStatus.ACTIVE)\
            .all()

        if len(stores) < 2:
            return 0  # Need at least 2 stores for cross-learning

        learnings_created = 0

        # For each store, find top performing products
        for source_store in stores:
            # Get top 10 products by conversion rate (with minimum orders)
            top_products = self.db.query(Product)\
                .filter(Product.store_id == source_store.id)\
                .filter(Product.total_sales >= 20)\
                .filter(Product.conversion_rate >= 2.0)\
                .order_by(desc(Product.conversion_rate))\
                .limit(10)\
                .all()

            # For each top product, generate learning for other stores
            for product in top_products:
                for target_store in stores:
                    if target_store.id == source_store.id:
                        continue  # Skip same store

                    # Check if learning already exists
                    existing = self.db.query(CrossStoreLearning)\
                        .filter(CrossStoreLearning.source_store_id == source_store.id)\
                        .filter(CrossStoreLearning.target_store_id == target_store.id)\
                        .filter(CrossStoreLearning.product_id == product.id)\
                        .filter(CrossStoreLearning.status == "pending")\
                        .first()

                    if existing:
                        continue  # Skip if already exists

                    # Calculate niche match score
                    niche_match = self._calculate_niche_match(
                        source_store.niche,
                        target_store.niche
                    )

                    if niche_match < 30:
                        continue  # Skip if niches don't match well

                    # Calculate projected performance
                    projected_conversion = product.conversion_rate * (niche_match / 100)
                    projected_monthly_revenue = (
                        product.total_revenue / max(1, product.total_sales)
                    ) * projected_conversion * 100  # Rough estimate

                    # Generate insight and recommendation
                    insight = (
                        f"{product.product_name} converts at {product.conversion_rate:.1f}% "
                        f"in {source_store.store_name} ({source_store.niche or 'general'})"
                    )

                    recommendation = (
                        f"Add {product.product_name} to {target_store.store_name} - "
                        f"projected {projected_conversion:.1f}% conversion rate"
                    )

                    # Create learning
                    learning = CrossStoreLearning(
                        source_store_id=source_store.id,
                        target_store_id=target_store.id,
                        learning_type="product_performance",
                        product_id=product.id,
                        product_name=product.product_name,
                        product_category=product.ai_tags[0] if product.ai_tags else None,
                        source_conversion_rate=product.conversion_rate,
                        source_revenue=product.total_revenue,
                        source_orders=product.total_sales,
                        source_avg_order_value=(
                            product.total_revenue / max(1, product.total_sales)
                        ),
                        applicable_niches=[source_store.niche, target_store.niche],
                        niche_match_score=niche_match,
                        insight=insight,
                        recommendation=recommendation,
                        confidence_score=min(90, niche_match + 20),  # Higher if good niche match
                        projected_conversion_rate=projected_conversion,
                        projected_monthly_revenue=projected_monthly_revenue,
                        projected_roi=150.0,  # Estimate
                        status="pending",
                    )

                    self.db.add(learning)
                    learnings_created += 1

        self.db.commit()
        return learnings_created

    def get_cross_store_insights(
        self,
        store_id: int,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get cross-store learning insights for a specific store.

        Args:
            store_id: Target store ID
            user_id: User ID for ownership verification
            limit: Maximum number of insights to return

        Returns:
            List of insights from other stores

        OPTIMIZED: Uses JOIN to avoid N+1 query pattern for source stores
        """
        # Verify store ownership
        store = self.db.query(Store)\
            .filter(Store.id == store_id)\
            .filter(Store.user_id == user_id)\
            .first()

        if not store:
            return []

        # Create alias for source store to join with learnings
        SourceStore = Store

        # Get learnings with source store in a single query using join
        learnings_with_source = self.db.query(
            CrossStoreLearning,
            SourceStore.store_name.label('source_store_name'),
            SourceStore.niche.label('source_store_niche')
        ).join(
            SourceStore, CrossStoreLearning.source_store_id == SourceStore.id
        ).filter(
            CrossStoreLearning.target_store_id == store_id
        ).filter(
            CrossStoreLearning.status == "pending"
        ).order_by(
            desc(CrossStoreLearning.confidence_score)
        ).limit(limit).all()

        insights = []
        for learning, source_store_name, source_store_niche in learnings_with_source:
            insights.append({
                "id": learning.id,
                "learning_type": learning.learning_type,
                "source_store_name": source_store_name or "Unknown",
                "source_store_niche": source_store_niche,
                "product_name": learning.product_name,
                "product_category": learning.product_category,
                "source_conversion_rate": learning.source_conversion_rate,
                "source_revenue": learning.source_revenue,
                "source_orders": learning.source_orders,
                "niche_match_score": learning.niche_match_score,
                "insight": learning.insight,
                "recommendation": learning.recommendation,
                "confidence_score": learning.confidence_score,
                "projected_conversion_rate": learning.projected_conversion_rate,
                "projected_monthly_revenue": learning.projected_monthly_revenue,
                "projected_roi": learning.projected_roi,
                "status": learning.status,
                "created_at": learning.created_at.isoformat(),
            })

        return insights

    def apply_cross_store_learning(
        self,
        learning_id: int,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Mark a cross-store learning as applied.

        Args:
            learning_id: Learning ID
            user_id: User ID for ownership verification

        Returns:
            Updated learning data or None if not found
        """
        learning = self.db.query(CrossStoreLearning)\
            .filter(CrossStoreLearning.id == learning_id)\
            .first()

        if not learning:
            return None

        # Verify ownership via target store
        target_store = self.db.query(Store)\
            .filter(Store.id == learning.target_store_id)\
            .filter(Store.user_id == user_id)\
            .first()

        if not target_store:
            return None

        learning.status = "applied"
        learning.applied_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(learning)

        return {
            "id": learning.id,
            "status": learning.status,
            "applied_at": learning.applied_at.isoformat(),
        }

    def dismiss_cross_store_learning(
        self,
        learning_id: int,
        user_id: int,
        reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Dismiss a cross-store learning recommendation.

        Args:
            learning_id: Learning ID
            user_id: User ID for ownership verification
            reason: Reason for dismissal (optional)

        Returns:
            Updated learning data or None if not found
        """
        learning = self.db.query(CrossStoreLearning)\
            .filter(CrossStoreLearning.id == learning_id)\
            .first()

        if not learning:
            return None

        # Verify ownership via target store
        target_store = self.db.query(Store)\
            .filter(Store.id == learning.target_store_id)\
            .filter(Store.user_id == user_id)\
            .first()

        if not target_store:
            return None

        learning.status = "dismissed"
        learning.dismissed_at = datetime.utcnow()
        learning.dismissal_reason = reason
        self.db.commit()
        self.db.refresh(learning)

        return {
            "id": learning.id,
            "status": learning.status,
            "dismissed_at": learning.dismissed_at.isoformat(),
            "dismissal_reason": learning.dismissal_reason,
        }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _calculate_niche_match(
        self,
        source_niche: Optional[str],
        target_niche: Optional[str]
    ) -> float:
        """
        Calculate niche compatibility score (0-100).

        Args:
            source_niche: Source store niche
            target_niche: Target store niche

        Returns:
            Match score (0-100)
        """
        if not source_niche or not target_niche:
            return 50.0  # Neutral if niche not specified

        # Exact match
        if source_niche.lower() == target_niche.lower():
            return 100.0

        # Define niche compatibility groups
        niche_groups = {
            "fitness": ["fitness", "yoga", "wellness", "health", "sports"],
            "home": ["smart_home", "home", "home_improvement", "furniture"],
            "beauty": ["beauty", "skincare", "cosmetics", "wellness"],
            "tech": ["tech", "electronics", "gadgets", "smart_home"],
            "fashion": ["fashion", "clothing", "apparel", "accessories"],
        }

        # Check if niches are in same group
        for group, keywords in niche_groups.items():
            if source_niche.lower() in keywords and target_niche.lower() in keywords:
                return 80.0  # High compatibility

        # Partial match (shared keywords)
        source_words = set(source_niche.lower().replace("_", " ").split())
        target_words = set(target_niche.lower().replace("_", " ").split())
        overlap = len(source_words & target_words)

        if overlap > 0:
            return 60.0  # Some compatibility

        return 30.0  # Low compatibility
