"""
Federated Learning Service - GROK RECOMMENDATION #18

High-level service that orchestrates privacy-preserving collective intelligence.

This service provides a simple API for:
1. Recording user outcomes (with consent checking)
2. Aggregating contributions into insights
3. Retrieving insights for recommendations
4. Managing privacy consent

Usage:
    from ospra_os.federated.service import FederatedLearningService

    service = FederatedLearningService(db)

    # Record a product outcome
    service.record_product_outcome(
        user_id=123,
        niche="smart_home",
        outcome="success",
        price=24.99,
        margin=45.0,
        rating=4.7,
        velocity=87
    )

    # Aggregate insights
    insights = service.aggregate_all()

    # Get recommendations
    recommendations = service.get_recommendations(
        user_id=123,
        niche="smart_home",
        context="product_selection"
    )
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from ospra_os.federated.data_collector import PrivacyPreservingCollector
from ospra_os.federated.aggregation_engine import AggregationEngine
from ospra_os.database.federated_models import (
    AggregateInsight,
    UserContribution,
    InsightApplication,
    PrivacyConsent
)

logger = logging.getLogger(__name__)


class FederatedLearningService:
    """
    High-level service for federated learning operations.

    Orchestrates data collection, aggregation, and insight retrieval
    while maintaining privacy guarantees.
    """

    def __init__(self, db: Session):
        self.db = db
        self.collector = PrivacyPreservingCollector(db)
        self.aggregator = AggregationEngine(db)

    # ==================== CONSENT MANAGEMENT ====================

    def enable_federated_learning(
        self,
        user_id: int,
        contribute_products: bool = True,
        contribute_pricing: bool = True,
        contribute_ads: bool = True
    ) -> PrivacyConsent:
        """
        Enable federated learning for a user.

        Creates or updates consent record with granular permissions.
        """

        consent = self.db.query(PrivacyConsent).filter(
            PrivacyConsent.user_id == user_id
        ).first()

        if consent:
            # Update existing consent
            consent.federated_learning_enabled = True
            consent.contribution_enabled = True
            consent.contribute_product_data = contribute_products
            consent.contribute_pricing_data = contribute_pricing
            consent.contribute_ad_data = contribute_ads
            consent.updated_at = datetime.now(timezone.utc)

            # Log consent change
            consent.consent_history.append({
                "action": "enabled",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scopes": {
                    "products": contribute_products,
                    "pricing": contribute_pricing,
                    "ads": contribute_ads
                }
            })
        else:
            # Create new consent
            consent = PrivacyConsent(
                user_id=user_id,
                federated_learning_enabled=True,
                aggregate_insights_enabled=True,
                contribution_enabled=True,
                contribute_product_data=contribute_products,
                contribute_pricing_data=contribute_pricing,
                contribute_ad_data=contribute_ads,
                consented_at=datetime.now(timezone.utc),
                consent_history=[{
                    "action": "opted_in",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "scopes": {
                        "products": contribute_products,
                        "pricing": contribute_pricing,
                        "ads": contribute_ads
                    }
                }]
            )
            self.db.add(consent)

        self.db.commit()

        logger.info(f"Federated learning enabled for user {user_id}")

        return consent

    def disable_federated_learning(self, user_id: int) -> Optional[PrivacyConsent]:
        """
        Disable federated learning for a user.

        Stops future data collection (does not delete past contributions).
        """

        consent = self.db.query(PrivacyConsent).filter(
            PrivacyConsent.user_id == user_id
        ).first()

        if not consent:
            return None

        consent.federated_learning_enabled = False
        consent.contribution_enabled = False
        consent.updated_at = datetime.now(timezone.utc)

        # Log consent change
        consent.consent_history.append({
            "action": "disabled",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        self.db.commit()

        logger.info(f"Federated learning disabled for user {user_id}")

        return consent

    def get_consent_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get consent status for a user.
        """

        consent = self.db.query(PrivacyConsent).filter(
            PrivacyConsent.user_id == user_id
        ).first()

        if not consent:
            return {
                "enabled": False,
                "opted_in": False,
                "contribution_enabled": False,
                "scopes": {
                    "products": False,
                    "pricing": False,
                    "ads": False
                }
            }

        return {
            "enabled": consent.federated_learning_enabled,
            "opted_in": consent.contribution_enabled,
            "contribution_enabled": consent.contribution_enabled,
            "scopes": {
                "products": consent.contribute_product_data,
                "pricing": consent.contribute_pricing_data,
                "ads": consent.contribute_ad_data
            },
            "consented_at": consent.consented_at.isoformat() if consent.consented_at else None,
            "consent_version": consent.consent_version
        }

    # ==================== DATA RECORDING ====================

    def record_product_outcome(
        self,
        user_id: int,
        niche: str,
        outcome: str,
        price: float = None,
        margin: float = None,
        rating: float = None,
        velocity: int = None
    ) -> Optional[UserContribution]:
        """
        Record a product deployment outcome.

        Data is automatically bucketed before storage.
        """

        return self.collector.collect_product_outcome(
            user_id=user_id,
            niche=niche,
            outcome=outcome,
            price=price,
            margin=margin,
            rating=rating,
            velocity=velocity
        )

    def record_pricing_outcome(
        self,
        user_id: int,
        niche: str,
        old_price: float,
        new_price: float,
        outcome: str
    ) -> Optional[UserContribution]:
        """
        Record a pricing decision outcome.
        """

        return self.collector.collect_pricing_outcome(
            user_id=user_id,
            niche=niche,
            old_price=old_price,
            new_price=new_price,
            outcome=outcome
        )

    def record_ad_outcome(
        self,
        user_id: int,
        niche: str,
        platform: str,
        roas: float = None,
        ctr: float = None,
        budget: float = None,
        outcome: str = "unknown"
    ) -> Optional[UserContribution]:
        """
        Record an ad campaign outcome.
        """

        return self.collector.collect_ad_outcome(
            user_id=user_id,
            niche=niche,
            platform=platform,
            roas=roas,
            ctr=ctr,
            budget=budget,
            outcome=outcome
        )

    # ==================== AGGREGATION ====================

    def aggregate_all(self, niche: str = None) -> Dict[str, List[AggregateInsight]]:
        """
        Run all aggregation processes.

        Returns:
            Dict with keys: product_insights, pricing_insights, ad_insights
        """

        logger.info(f"Starting full aggregation for niche: {niche or 'all'}")

        product_insights = self.aggregator.aggregate_product_outcomes(niche=niche)
        pricing_insights = self.aggregator.aggregate_pricing_outcomes(niche=niche)
        ad_insights = self.aggregator.aggregate_ad_outcomes(niche=niche)

        logger.info(f"Aggregation complete: {len(product_insights)} product, {len(pricing_insights)} pricing, {len(ad_insights)} ad insights")

        return {
            "product_insights": product_insights,
            "pricing_insights": pricing_insights,
            "ad_insights": ad_insights
        }

    def aggregate_products(self, niche: str = None) -> List[AggregateInsight]:
        """Run product aggregation only."""
        return self.aggregator.aggregate_product_outcomes(niche=niche)

    def aggregate_pricing(self, niche: str = None) -> List[AggregateInsight]:
        """Run pricing aggregation only."""
        return self.aggregator.aggregate_pricing_outcomes(niche=niche)

    def aggregate_ads(self, niche: str = None, platform: str = None) -> List[AggregateInsight]:
        """Run ad aggregation only."""
        return self.aggregator.aggregate_ad_outcomes(niche=niche, platform=platform)

    # ==================== INSIGHT RETRIEVAL ====================

    def get_recommendations(
        self,
        user_id: int,
        niche: str = None,
        context: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get personalized recommendations based on aggregate insights.

        Args:
            user_id: User requesting recommendations
            niche: Filter by niche
            context: Context for recommendations (e.g., "product_selection", "pricing_strategy")
            limit: Maximum number of recommendations

        Returns:
            List of recommendations with insight data and confidence scores
        """

        # Check if user has insights enabled
        consent = self.db.query(PrivacyConsent).filter(
            PrivacyConsent.user_id == user_id
        ).first()

        if not consent or not consent.aggregate_insights_enabled:
            logger.info(f"User {user_id} has not enabled aggregate insights")
            return []

        # Build query
        query = self.db.query(AggregateInsight).filter(
            AggregateInsight.is_active == True
        )

        # Filter by niche
        if niche:
            query = query.filter(
                AggregateInsight.category == niche
            )

        # Filter by context
        if context == "product_selection":
            query = query.filter(AggregateInsight.insight_type == "product_performance")
        elif context == "pricing_strategy":
            query = query.filter(AggregateInsight.insight_type == "pricing_pattern")
        elif context == "ad_campaign":
            query = query.filter(AggregateInsight.insight_type == "ad_effectiveness")

        # Order by confidence and sample size
        insights = query.order_by(
            AggregateInsight.confidence.desc(),
            AggregateInsight.sample_size.desc()
        ).limit(limit).all()

        # Format recommendations
        recommendations = []
        for insight in insights:
            recommendations.append({
                "id": insight.id,
                "type": insight.insight_type,
                "niche": insight.category,
                "title": insight.title,
                "description": insight.description,
                "pattern": insight.data.get("pattern", {}),
                "confidence": insight.confidence,
                "sample_size": insight.sample_size,
                "times_applied": insight.times_applied,
                "success_rate": insight.success_when_applied,
                "recommendation": self._format_recommendation(insight)
            })

        return recommendations

    def apply_insight(
        self,
        user_id: int,
        insight_id: int,
        context: Dict[str, Any] = None
    ) -> InsightApplication:
        """
        Record that a user applied an insight.

        This creates a feedback loop to measure insight effectiveness.
        """

        application = InsightApplication(
            user_id=user_id,
            insight_id=insight_id,
            context=context or {},
            applied_at=datetime.now(timezone.utc)
        )

        self.db.add(application)

        # Increment usage counter on insight
        insight = self.db.query(AggregateInsight).filter(
            AggregateInsight.id == insight_id
        ).first()

        if insight:
            insight.times_applied += 1

        self.db.commit()

        logger.info(f"User {user_id} applied insight {insight_id}")

        return application

    def record_insight_outcome(
        self,
        application_id: int,
        outcome: str
    ) -> Optional[InsightApplication]:
        """
        Record the outcome of applying an insight.

        Args:
            application_id: ID of the InsightApplication record
            outcome: "success", "partial", or "failure"
        """

        application = self.db.query(InsightApplication).filter(
            InsightApplication.id == application_id
        ).first()

        if not application:
            return None

        application.outcome = outcome
        application.outcome_recorded_at = datetime.now(timezone.utc)

        # Update insight success rate
        insight = self.db.query(AggregateInsight).filter(
            AggregateInsight.id == application.insight_id
        ).first()

        if insight:
            # Recalculate success rate from all applications
            applications = self.db.query(InsightApplication).filter(
                InsightApplication.insight_id == insight.id,
                InsightApplication.outcome.isnot(None)
            ).all()

            if applications:
                successes = sum(1 for app in applications if app.outcome == "success")
                insight.success_when_applied = successes / len(applications)

        self.db.commit()

        logger.info(f"Recorded outcome '{outcome}' for application {application_id}")

        return application

    # ==================== STATISTICS ====================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the federated learning system.
        """

        # Aggregation stats
        agg_stats = self.aggregator.get_aggregation_stats()

        # User participation
        total_users = self.db.query(PrivacyConsent).count()
        opted_in_users = self.db.query(PrivacyConsent).filter(
            PrivacyConsent.contribution_enabled == True
        ).count()

        # Insight applications
        total_applications = self.db.query(InsightApplication).count()
        applications_with_outcome = self.db.query(InsightApplication).filter(
            InsightApplication.outcome.isnot(None)
        ).count()

        return {
            "system": {
                "total_users": total_users,
                "opted_in_users": opted_in_users,
                "opt_in_rate": round(opted_in_users / total_users, 3) if total_users > 0 else 0,
                "ready_for_aggregation": agg_stats["contributions"]["pending"] >= self.aggregator.MIN_SAMPLES_FOR_INSIGHT
            },
            "contributions": agg_stats["contributions"],
            "insights": agg_stats["insights"],
            "applications": {
                "total": total_applications,
                "with_outcome": applications_with_outcome,
                "completion_rate": round(applications_with_outcome / total_applications, 3) if total_applications > 0 else 0
            },
            "privacy": {
                "min_users_required": self.aggregator.MIN_USERS_FOR_AGGREGATION,
                "min_samples_required": self.aggregator.MIN_SAMPLES_FOR_INSIGHT,
                "min_confidence_required": self.aggregator.MIN_CONFIDENCE
            }
        }

    # ==================== UTILITY ====================

    def _format_recommendation(self, insight: AggregateInsight) -> str:
        """
        Format an insight into a human-readable recommendation.
        """

        pattern = insight.data.get("pattern", {})

        if insight.insight_type == "product_performance":
            return (
                f"Products in the {pattern.get('price_bucket', 'unknown')} price range "
                f"with {pattern.get('rating_bucket', 'unknown')} ratings tend to "
                f"succeed {pattern.get('success_rate', 0):.1%} of the time "
                f"(based on {insight.sample_size} similar deployments)"
            )

        elif insight.insight_type == "pricing_pattern":
            return (
                f"Price {pattern.get('change_direction', 'changes')} of "
                f"{pattern.get('change_magnitude', 'unknown')} magnitude lead to "
                f"improvement {pattern.get('improvement_rate', 0):.1%} of the time "
                f"(based on {insight.sample_size} pricing decisions)"
            )

        elif insight.insight_type == "ad_effectiveness":
            return (
                f"On {pattern.get('platform', 'this platform')}, "
                f"{pattern.get('budget_bucket', 'unknown')} budgets achieve "
                f"good/excellent ROAS {pattern.get('success_rate', 0):.1%} of the time "
                f"(based on {insight.sample_size} campaigns)"
            )

        return insight.description or insight.title
