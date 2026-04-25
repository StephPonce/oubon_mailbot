"""
Aggregation Engine - GROK RECOMMENDATION #18

Transforms privacy-preserved user contributions into aggregate insights.

KEY PRIVACY GUARANTEES:
1. Minimum 10 users required before any aggregation
2. Minimum 50 samples required before insight is valid
3. Only statistical patterns are computed - never individual data
4. Confidence scores reflect statistical reliability

How it works:
1. Fetch unaggregated contributions (bucketed data only)
2. Group by pattern (niche + buckets)
3. Count samples and unique users
4. If thresholds met: Compute success rate, confidence score
5. Create AggregateInsight record
6. Mark contributions as processed
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func

from ospra_os.database.federated_models import (
    AggregateInsight,
    UserContribution,
    PrivacyConsent
)

logger = logging.getLogger(__name__)


class AggregationEngine:
    """
    Aggregates privacy-preserved contributions into insights.

    CRITICAL: This engine ONLY works with pre-bucketed data.
    No raw values are ever processed.
    """

    # Privacy thresholds
    MIN_USERS_FOR_AGGREGATION = 10
    MIN_SAMPLES_FOR_INSIGHT = 50
    MIN_CONFIDENCE = 0.7

    def __init__(self, db: Session):
        self.db = db

    def aggregate_product_outcomes(self, niche: str = None) -> List[AggregateInsight]:
        """
        Aggregate product outcomes into insights.

        Example output:
        "In smart_home niche, products with price_bucket=10_20,
         rating_bucket=4.5_plus have 73% success rate
         (247 samples from 45 users, confidence=0.89)"

        Args:
            niche: Filter by specific niche, or None for all niches

        Returns:
            List of created AggregateInsight records
        """

        logger.info(f"Starting product outcome aggregation for niche: {niche or 'all'}")

        # Fetch unaggregated product contributions
        query = self.db.query(UserContribution).filter(
            UserContribution.contribution_type == "product_outcome",
            UserContribution.included_in_aggregation == False
        )

        if niche:
            query = query.filter(
                UserContribution.metadata['niche'].astext == niche
            )

        contributions = query.all()

        if not contributions:
            logger.info("No unaggregated product contributions found")
            return []

        logger.info(f"Found {len(contributions)} unaggregated product contributions")

        # Group contributions by pattern (niche + buckets)
        patterns = self._group_product_contributions(contributions)

        # Create insights from patterns that meet thresholds
        insights = []
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        for pattern_key, contrib_list in patterns.items():
            insight = self._create_product_insight(pattern_key, contrib_list, batch_id)
            if insight:
                insights.append(insight)

        logger.info(f"Created {len(insights)} product insights from {len(contributions)} contributions")

        return insights

    def aggregate_pricing_outcomes(self, niche: str = None) -> List[AggregateInsight]:
        """
        Aggregate pricing decisions into insights.

        Example:
        "In fitness niche, price increases of medium magnitude (5-15%)
         led to improved outcomes 62% of the time
         (89 samples from 23 users, confidence=0.81)"
        """

        logger.info(f"Starting pricing outcome aggregation for niche: {niche or 'all'}")

        query = self.db.query(UserContribution).filter(
            UserContribution.contribution_type == "pricing_outcome",
            UserContribution.included_in_aggregation == False
        )

        if niche:
            query = query.filter(
                UserContribution.metadata['niche'].astext == niche
            )

        contributions = query.all()

        if not contributions:
            logger.info("No unaggregated pricing contributions found")
            return []

        logger.info(f"Found {len(contributions)} unaggregated pricing contributions")

        patterns = self._group_pricing_contributions(contributions)
        insights = []
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        for pattern_key, contrib_list in patterns.items():
            insight = self._create_pricing_insight(pattern_key, contrib_list, batch_id)
            if insight:
                insights.append(insight)

        logger.info(f"Created {len(insights)} pricing insights from {len(contributions)} contributions")

        return insights

    def aggregate_ad_outcomes(self, niche: str = None, platform: str = None) -> List[AggregateInsight]:
        """
        Aggregate ad performance into insights.

        Example:
        "For smart_home products on facebook, budget_bucket=medium with
         roas_bucket=good achieves success 78% of the time
         (134 samples from 31 users, confidence=0.85)"
        """

        logger.info(f"Starting ad outcome aggregation for niche: {niche or 'all'}, platform: {platform or 'all'}")

        query = self.db.query(UserContribution).filter(
            UserContribution.contribution_type == "ad_outcome",
            UserContribution.included_in_aggregation == False
        )

        if niche:
            query = query.filter(
                UserContribution.metadata['niche'].astext == niche
            )

        if platform:
            query = query.filter(
                UserContribution.metadata['platform'].astext == platform
            )

        contributions = query.all()

        if not contributions:
            logger.info("No unaggregated ad contributions found")
            return []

        logger.info(f"Found {len(contributions)} unaggregated ad contributions")

        patterns = self._group_ad_contributions(contributions)
        insights = []
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        for pattern_key, contrib_list in patterns.items():
            insight = self._create_ad_insight(pattern_key, contrib_list, batch_id)
            if insight:
                insights.append(insight)

        logger.info(f"Created {len(insights)} ad insights from {len(contributions)} contributions")

        return insights

    # ==================== GROUPING FUNCTIONS ====================

    def _group_product_contributions(
        self,
        contributions: List[UserContribution]
    ) -> Dict[Tuple, List[UserContribution]]:
        """
        Group contributions by pattern.

        Pattern key: (niche, price_bucket, margin_bucket, rating_bucket, velocity_bucket)
        """
        patterns = defaultdict(list)

        for contrib in contributions:
            meta = contrib.contribution_data
            pattern_key = (
                meta.get('niche'),
                meta.get('price_bucket'),
                meta.get('margin_bucket'),
                meta.get('rating_bucket'),
                meta.get('velocity_bucket')
            )
            patterns[pattern_key].append(contrib)

        return dict(patterns)

    def _group_pricing_contributions(
        self,
        contributions: List[UserContribution]
    ) -> Dict[Tuple, List[UserContribution]]:
        """
        Group pricing contributions by pattern.

        Pattern key: (niche, price_bucket, change_direction, change_magnitude)
        """
        patterns = defaultdict(list)

        for contrib in contributions:
            meta = contrib.contribution_data
            pattern_key = (
                meta.get('niche'),
                meta.get('price_bucket'),
                meta.get('change_direction'),
                meta.get('change_magnitude')
            )
            patterns[pattern_key].append(contrib)

        return dict(patterns)

    def _group_ad_contributions(
        self,
        contributions: List[UserContribution]
    ) -> Dict[Tuple, List[UserContribution]]:
        """
        Group ad contributions by pattern.

        Pattern key: (niche, platform, budget_bucket, roas_bucket, ctr_bucket)
        """
        patterns = defaultdict(list)

        for contrib in contributions:
            meta = contrib.contribution_data
            pattern_key = (
                meta.get('niche'),
                meta.get('platform'),
                meta.get('budget_bucket'),
                meta.get('roas_bucket'),
                meta.get('ctr_bucket')
            )
            patterns[pattern_key].append(contrib)

        return dict(patterns)

    # ==================== INSIGHT CREATION ====================

    def _create_product_insight(
        self,
        pattern_key: Tuple,
        contributions: List[UserContribution],
        batch_id: str
    ) -> Optional[AggregateInsight]:
        """
        Create product performance insight if thresholds met.
        """

        # Extract pattern components
        niche, price_bucket, margin_bucket, rating_bucket, velocity_bucket = pattern_key

        # Check privacy thresholds
        unique_users = len(set(c.user_id for c in contributions))
        sample_size = len(contributions)

        if unique_users < self.MIN_USERS_FOR_AGGREGATION:
            logger.debug(f"Pattern {pattern_key}: Only {unique_users} users (need {self.MIN_USERS_FOR_AGGREGATION})")
            return None

        if sample_size < self.MIN_SAMPLES_FOR_INSIGHT:
            logger.debug(f"Pattern {pattern_key}: Only {sample_size} samples (need {self.MIN_SAMPLES_FOR_INSIGHT})")
            return None

        # Calculate success rate
        successes = sum(1 for c in contributions if c.contribution_data.get('outcome') == 'success')
        success_rate = successes / sample_size

        # Calculate confidence (simple binomial confidence interval approximation)
        confidence = self._calculate_confidence(sample_size, success_rate)

        if confidence < self.MIN_CONFIDENCE:
            logger.debug(f"Pattern {pattern_key}: Confidence {confidence:.2f} too low (need {self.MIN_CONFIDENCE})")
            return None

        # Create insight
        insight = AggregateInsight(
            insight_type="product_performance",
            category=niche,
            title=f"Product success pattern in {niche}",
            description=f"Products with price {price_bucket}, margin {margin_bucket}, rating {rating_bucket}, velocity {velocity_bucket} succeed {success_rate:.1%} of the time",
            data={
                "pattern": {
                    "price_bucket": price_bucket,
                    "margin_bucket": margin_bucket,
                    "rating_bucket": rating_bucket,
                    "velocity_bucket": velocity_bucket,
                    "success_rate": round(success_rate, 3)
                },
                "sample_size": sample_size,
                "unique_users": unique_users,
                "confidence": round(confidence, 3)
            },
            sample_size=sample_size,
            confidence=confidence,
            min_sample_threshold=self.MIN_SAMPLES_FOR_INSIGHT,
            applicable_niches=[niche] if niche else [],
            is_active=True
        )

        self.db.add(insight)

        # Mark contributions as aggregated
        for contrib in contributions:
            contrib.included_in_aggregation = True
            contrib.aggregation_batch_id = batch_id

        self.db.commit()

        logger.info(f"Created product insight: {insight.title} (confidence={confidence:.2f}, samples={sample_size}, users={unique_users})")

        return insight

    def _create_pricing_insight(
        self,
        pattern_key: Tuple,
        contributions: List[UserContribution],
        batch_id: str
    ) -> Optional[AggregateInsight]:
        """
        Create pricing decision insight if thresholds met.
        """

        niche, price_bucket, change_direction, change_magnitude = pattern_key

        unique_users = len(set(c.user_id for c in contributions))
        sample_size = len(contributions)

        if unique_users < self.MIN_USERS_FOR_AGGREGATION or sample_size < self.MIN_SAMPLES_FOR_INSIGHT:
            return None

        # Calculate improvement rate
        improvements = sum(1 for c in contributions if c.contribution_data.get('outcome') == 'improved')
        improvement_rate = improvements / sample_size

        confidence = self._calculate_confidence(sample_size, improvement_rate)

        if confidence < self.MIN_CONFIDENCE:
            return None

        insight = AggregateInsight(
            insight_type="pricing_pattern",
            category=niche,
            title=f"Pricing strategy in {niche}",
            description=f"Price {change_direction} of {change_magnitude} magnitude leads to improvement {improvement_rate:.1%} of the time",
            data={
                "pattern": {
                    "price_bucket": price_bucket,
                    "change_direction": change_direction,
                    "change_magnitude": change_magnitude,
                    "improvement_rate": round(improvement_rate, 3)
                },
                "sample_size": sample_size,
                "unique_users": unique_users,
                "confidence": round(confidence, 3)
            },
            sample_size=sample_size,
            confidence=confidence,
            min_sample_threshold=self.MIN_SAMPLES_FOR_INSIGHT,
            applicable_niches=[niche] if niche else [],
            is_active=True
        )

        self.db.add(insight)

        for contrib in contributions:
            contrib.included_in_aggregation = True
            contrib.aggregation_batch_id = batch_id

        self.db.commit()

        logger.info(f"Created pricing insight: {insight.title} (confidence={confidence:.2f})")

        return insight

    def _create_ad_insight(
        self,
        pattern_key: Tuple,
        contributions: List[UserContribution],
        batch_id: str
    ) -> Optional[AggregateInsight]:
        """
        Create ad effectiveness insight if thresholds met.
        """

        niche, platform, budget_bucket, roas_bucket, ctr_bucket = pattern_key

        unique_users = len(set(c.user_id for c in contributions))
        sample_size = len(contributions)

        if unique_users < self.MIN_USERS_FOR_AGGREGATION or sample_size < self.MIN_SAMPLES_FOR_INSIGHT:
            return None

        # Success = good or excellent ROAS
        successes = sum(1 for c in contributions if c.contribution_data.get('roas_bucket') in ['good', 'excellent'])
        success_rate = successes / sample_size

        confidence = self._calculate_confidence(sample_size, success_rate)

        if confidence < self.MIN_CONFIDENCE:
            return None

        insight = AggregateInsight(
            insight_type="ad_effectiveness",
            category=niche,
            title=f"Ad performance on {platform} for {niche}",
            description=f"Budget {budget_bucket} with CTR {ctr_bucket} achieves good/excellent ROAS {success_rate:.1%} of the time",
            data={
                "pattern": {
                    "platform": platform,
                    "budget_bucket": budget_bucket,
                    "roas_bucket": roas_bucket,
                    "ctr_bucket": ctr_bucket,
                    "success_rate": round(success_rate, 3)
                },
                "sample_size": sample_size,
                "unique_users": unique_users,
                "confidence": round(confidence, 3)
            },
            sample_size=sample_size,
            confidence=confidence,
            min_sample_threshold=self.MIN_SAMPLES_FOR_INSIGHT,
            applicable_niches=[niche] if niche else [],
            is_active=True
        )

        self.db.add(insight)

        for contrib in contributions:
            contrib.included_in_aggregation = True
            contrib.aggregation_batch_id = batch_id

        self.db.commit()

        logger.info(f"Created ad insight: {insight.title} (confidence={confidence:.2f})")

        return insight

    # ==================== UTILITY FUNCTIONS ====================

    def _calculate_confidence(self, sample_size: int, success_rate: float) -> float:
        """
        Calculate confidence score using Wilson score interval.

        Higher sample sizes → higher confidence
        Success rates near 0.5 → lower confidence (more variance)
        Success rates near 0 or 1 → higher confidence (less variance)
        """

        import math

        if sample_size == 0:
            return 0.0

        # Wilson score interval (95% confidence)
        z = 1.96  # 95% confidence z-score

        p = success_rate
        n = sample_size

        # Wilson center point
        center = (p + z*z/(2*n)) / (1 + z*z/n)

        # Wilson interval half-width
        spread = (z * math.sqrt((p*(1-p) + z*z/(4*n)) / n)) / (1 + z*z/n)

        # Confidence is inverse of spread (normalized)
        # Smaller spread = higher confidence
        confidence = 1 - min(spread, 1.0)

        return max(0.0, min(1.0, confidence))

    def get_aggregation_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the aggregation process.
        """

        total_contributions = self.db.query(UserContribution).count()
        aggregated = self.db.query(UserContribution).filter(
            UserContribution.included_in_aggregation == True
        ).count()
        pending = total_contributions - aggregated

        total_insights = self.db.query(AggregateInsight).count()
        active_insights = self.db.query(AggregateInsight).filter(
            AggregateInsight.is_active == True
        ).count()

        # Unique contributing users
        unique_users = self.db.query(func.count(func.distinct(UserContribution.user_id))).scalar()

        return {
            "contributions": {
                "total": total_contributions,
                "aggregated": aggregated,
                "pending": pending,
                "aggregation_rate": round(aggregated / total_contributions, 3) if total_contributions > 0 else 0
            },
            "insights": {
                "total": total_insights,
                "active": active_insights
            },
            "users": {
                "contributing": unique_users
            }
        }
