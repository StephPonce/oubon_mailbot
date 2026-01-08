"""
Outcome Service - G4: Complete Feedback Loop Phase 2
===================================================

Tracks outcomes of AI recommendations by comparing predictions vs reality.
This is the KEY feedback mechanism that enables AI learning.

When AI recommends a product:
1. We record what it predicted (revenue, sales, confidence)
2. After 7+ days, we compare actual performance vs predicted
3. We classify the outcome (exceptional, success, moderate, poor, failure)
4. We create learning events to update the AI

This closes the loop: AI → Prediction → Reality → Learning
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from ospra_os.database import (
    RecommendationOutcome, ProductPerformance, AILearningEvent,
    ConfidenceCalibration, NicheLearning, Product, Action,
    PerformanceOutcome, get_session
)
from ospra_os.services.sales_sync_service import SalesSyncService


class OutcomeService:
    """
    Tracks and evaluates outcomes of AI recommendations.

    This service:
    1. Records predictions when user accepts recommendation
    2. Evaluates outcomes after 7+ days
    3. Classifies performance (exceptional → failure)
    4. Creates learning events for AI improvement
    5. Updates niche learning statistics
    6. Updates confidence calibration metrics

    Usage:
        service = OutcomeService(db)
        # When user accepts recommendation:
        outcome = service.create_outcome_record(action, product)
        # Daily task to evaluate pending outcomes:
        results = await service.evaluate_outcomes(user_id=1)
    """

    # Minimum days before evaluating outcome
    MIN_TRACKING_DAYS = 7

    # Classification thresholds (vs predicted performance)
    EXCEPTIONAL_THRESHOLD = 1.5    # >150% of predicted
    SUCCESS_THRESHOLD = 1.0        # 100-150% of predicted
    MODERATE_THRESHOLD = 0.5       # 50-100% of predicted
    POOR_THRESHOLD = 0.25          # 25-50% of predicted
    # <25% = failure

    def __init__(self, db: Session):
        self.db = db
        self.sales_sync = SalesSyncService(db)

    def create_outcome_record(
        self,
        action: Action,
        product: Product,
        confidence_score: float,
        confidence_breakdown: Dict,
        ai_reasoning: str,
        projected_daily_sales: Optional[float] = None,
        projected_monthly_revenue: Optional[float] = None,
        projected_margin: Optional[float] = None,
        projected_roi: Optional[float] = None
    ) -> RecommendationOutcome:
        """
        Create outcome record when user accepts recommendation.

        This captures what the AI predicted at the time of recommendation,
        so we can later compare it to reality.

        Args:
            action: The pending action that was accepted
            product: The product being deployed
            confidence_score: AI's confidence (0-100)
            confidence_breakdown: Dict of factor scores
            ai_reasoning: Text explanation of why AI recommended this
            projected_*: AI's performance predictions

        Returns:
            RecommendationOutcome record
        """
        print(f"[NOTE] Creating outcome record for product {product.id}")

        outcome = RecommendationOutcome(
            user_id=product.user_id,
            action_id=action.id,
            product_id=product.id,
            recommendation_type="product_deploy",
            confidence_score=confidence_score,
            confidence_breakdown=confidence_breakdown,
            ai_reasoning=ai_reasoning,
            projected_daily_sales=projected_daily_sales,
            projected_monthly_revenue=projected_monthly_revenue,
            projected_margin=projected_margin,
            projected_roi=projected_roi,
            was_accepted=True,
            accepted_at=datetime.now(),
            outcome=PerformanceOutcome.pending.value,
            tracking_started_at=datetime.now()
        )

        self.db.add(outcome)
        self.db.commit()
        self.db.refresh(outcome)

        print(f"[SUCCESS] Outcome record created: ID {outcome.id}")
        return outcome

    def record_rejection(
        self,
        action: Action,
        product: Product,
        confidence_score: float,
        rejection_reason: str
    ) -> RecommendationOutcome:
        """
        Record when user rejects a recommendation.

        Rejections are valuable learning signals too!
        They tell us what users don't want.
        """
        outcome = RecommendationOutcome(
            user_id=product.user_id,
            action_id=action.id,
            product_id=product.id,
            recommendation_type="product_deploy",
            confidence_score=confidence_score,
            was_accepted=False,
            rejected_at=datetime.now(),
            rejection_reason=rejection_reason,
            outcome=PerformanceOutcome.pending.value
        )

        self.db.add(outcome)
        self.db.commit()

        return outcome

    async def evaluate_outcomes(
        self,
        user_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Evaluate pending outcomes that are ready (>7 days old).

        For each outcome:
        1. Fetch actual performance from ProductPerformance
        2. Compare actual vs predicted
        3. Classify outcome
        4. Calculate accuracy score
        5. Create learning event
        6. Update niche learning
        7. Update confidence calibration

        Args:
            user_id: If provided, only evaluate for this user

        Returns:
            List of evaluation results
        """
        print("[SEARCH] Evaluating pending outcomes...")

        # Find outcomes ready to evaluate
        cutoff_date = datetime.now() - timedelta(days=self.MIN_TRACKING_DAYS)

        query = self.db.query(RecommendationOutcome).filter(
            and_(
                RecommendationOutcome.outcome == PerformanceOutcome.pending.value,
                RecommendationOutcome.was_accepted == True,
                RecommendationOutcome.tracking_started_at <= cutoff_date
            )
        )

        if user_id:
            query = query.filter(RecommendationOutcome.user_id == user_id)

        pending_outcomes = query.all()

        print(f"[STATS] Found {len(pending_outcomes)} outcomes ready to evaluate")

        results = []
        for outcome in pending_outcomes:
            try:
                result = await self._evaluate_single_outcome(outcome)
                results.append(result)
            except Exception as e:
                print(f"[ERROR] Error evaluating outcome {outcome.id}: {e}")
                results.append({
                    "success": False,
                    "outcome_id": outcome.id,
                    "error": str(e)
                })

        return results

    async def _evaluate_single_outcome(
        self,
        outcome: RecommendationOutcome
    ) -> Dict:
        """
        Evaluate a single outcome.

        Returns:
            {
                "success": True,
                "outcome_id": 123,
                "classification": "success",
                "outcome_score": 85,
                "accuracy_score": 92,
                "actual_revenue": 650.25,
                "projected_revenue": 450.00,
                "performance_ratio": 1.44
            }
        """
        print(f"  Evaluating outcome {outcome.id} for product {outcome.product_id}")

        # Calculate tracking period
        days_tracked = (datetime.now() - outcome.tracking_started_at).days

        # Fetch actual performance from ProductPerformance
        performance_summary = self.sales_sync.get_product_performance_summary(
            product_id=outcome.product_id,
            days=days_tracked
        )

        if "error" in performance_summary:
            return {
                "success": False,
                "outcome_id": outcome.id,
                "error": "No performance data available"
            }

        # Extract actual metrics
        actual_daily_sales = performance_summary["avg_daily_orders"]
        actual_revenue = performance_summary["total_revenue"]
        actual_profit = performance_summary["total_profit"]
        actual_margin = performance_summary["avg_margin"]

        # Update outcome with actual performance
        outcome.actual_daily_sales_avg = actual_daily_sales
        outcome.actual_total_revenue = actual_revenue
        outcome.actual_total_profit = actual_profit
        outcome.actual_margin = actual_margin
        outcome.tracking_ended_at = datetime.now()
        outcome.tracking_days = days_tracked

        # Classify outcome
        classification, outcome_score, accuracy_score = self._classify_outcome(
            outcome,
            performance_summary
        )

        outcome.outcome = classification
        outcome.outcome_score = outcome_score
        outcome.accuracy_score = accuracy_score

        # Create learning event
        learning_event = self._create_learning_event(outcome, performance_summary)

        # Update niche learning
        product = self.db.query(Product).get(outcome.product_id)
        if product and product.niche:
            self._update_niche_learning(
                user_id=outcome.user_id,
                niche=product.niche,
                product_id=product.id,
                outcome_classification=classification,
                revenue=actual_revenue,
                profit=actual_profit,
                margin=actual_margin
            )

        # Update confidence calibration
        self._update_confidence_calibration(
            user_id=outcome.user_id,
            recommendation_type=outcome.recommendation_type,
            confidence_score=outcome.confidence_score,
            was_successful=(classification in ["exceptional", "success"])
        )

        self.db.commit()

        print(f"[SUCCESS] Outcome classified as: {classification} (score: {outcome_score})")

        return {
            "success": True,
            "outcome_id": outcome.id,
            "product_id": outcome.product_id,
            "classification": classification,
            "outcome_score": outcome_score,
            "accuracy_score": accuracy_score,
            "actual_revenue": actual_revenue,
            "projected_revenue": outcome.projected_monthly_revenue,
            "days_tracked": days_tracked
        }

    def _classify_outcome(
        self,
        outcome: RecommendationOutcome,
        performance: Dict
    ) -> Tuple[str, float, float]:
        """
        Classify outcome based on actual vs predicted performance.

        Classification:
        - exceptional: >150% of predicted (score 100)
        - success: 100-150% of predicted (score 75-100)
        - moderate: 50-100% of predicted (score 50-75)
        - poor: 25-50% of predicted (score 25-50)
        - failure: <25% of predicted (score 0-25)

        Returns:
            (classification, outcome_score, accuracy_score)
        """
        # Compare actual vs predicted revenue
        actual_revenue = performance["total_revenue"]
        projected_revenue = outcome.projected_monthly_revenue or 1.0

        if projected_revenue == 0:
            # Avoid division by zero
            projected_revenue = 1.0

        ratio = actual_revenue / projected_revenue

        # Classify based on ratio
        if ratio >= self.EXCEPTIONAL_THRESHOLD:
            classification = PerformanceOutcome.exceptional.value
            outcome_score = 100
        elif ratio >= self.SUCCESS_THRESHOLD:
            classification = PerformanceOutcome.success.value
            # Linear scale 75-100 between 100% and 150%
            outcome_score = 75 + ((ratio - 1.0) / 0.5) * 25
        elif ratio >= self.MODERATE_THRESHOLD:
            classification = PerformanceOutcome.moderate.value
            # Linear scale 50-75 between 50% and 100%
            outcome_score = 50 + ((ratio - 0.5) / 0.5) * 25
        elif ratio >= self.POOR_THRESHOLD:
            classification = PerformanceOutcome.poor.value
            # Linear scale 25-50 between 25% and 50%
            outcome_score = 25 + ((ratio - 0.25) / 0.25) * 25
        else:
            classification = PerformanceOutcome.failure.value
            # Linear scale 0-25 between 0% and 25%
            outcome_score = min(ratio / 0.25 * 25, 25)

        # Calculate accuracy score (how close prediction was to reality)
        # 100% accuracy = exact match
        # 0% accuracy = completely wrong
        error_ratio = abs(actual_revenue - projected_revenue) / projected_revenue
        accuracy_score = max(0, 100 - (error_ratio * 100))

        return classification, outcome_score, accuracy_score

    def _create_learning_event(
        self,
        outcome: RecommendationOutcome,
        performance: Dict
    ) -> AILearningEvent:
        """
        Create learning event from outcome.

        This generates the signal that will update AI weights.
        """
        # Determine lesson type
        if outcome.outcome in ["exceptional", "success"]:
            lesson_type = "positive_signal"
            lesson_strength = 1.0 if outcome.outcome == "exceptional" else 0.75
        elif outcome.outcome == "moderate":
            lesson_type = "neutral"
            lesson_strength = 0.5
        else:
            lesson_type = "negative_signal"
            lesson_strength = 1.0 if outcome.outcome == "failure" else 0.75

        # Determine which factors were validated/invalidated
        # by looking at confidence breakdown
        confidence_breakdown = outcome.confidence_breakdown or {}

        factors_validated = []
        factors_invalidated = []

        if lesson_type == "positive_signal":
            # High-scoring factors were validated
            for factor, score in confidence_breakdown.items():
                if score > 70:
                    factors_validated.append(factor)
        elif lesson_type == "negative_signal":
            # High-scoring factors were invalidated
            for factor, score in confidence_breakdown.items():
                if score > 70:
                    factors_invalidated.append(factor)

        # Calculate weight adjustments
        weight_adjustments = {}

        if lesson_type == "positive_signal":
            # Increase weights for validated factors
            for factor in factors_validated:
                weight_adjustments[factor] = 0.05 * lesson_strength
        elif lesson_type == "negative_signal":
            # Decrease weights for invalidated factors
            for factor in factors_invalidated:
                weight_adjustments[factor] = -0.05 * lesson_strength

        # Create learning event
        event = AILearningEvent(
            user_id=outcome.user_id,
            outcome_id=outcome.id,
            event_type="product_outcome",
            context={
                "product_id": outcome.product_id,
                "confidence": outcome.confidence_score,
                "outcome": outcome.outcome,
                "actual_revenue": performance["total_revenue"],
                "projected_revenue": outcome.projected_monthly_revenue,
                "performance_ratio": performance["total_revenue"] / (outcome.projected_monthly_revenue or 1.0)
            },
            lesson_type=lesson_type,
            lesson_strength=lesson_strength,
            factors_validated=factors_validated,
            factors_invalidated=factors_invalidated,
            weight_adjustments=weight_adjustments,
            processed=False
        )

        self.db.add(event)
        print(f" Learning event created: {lesson_type} (strength {lesson_strength})")

        return event

    def _update_niche_learning(
        self,
        user_id: int,
        niche: str,
        product_id: int,
        outcome_classification: str,
        revenue: float,
        profit: float,
        margin: float
    ):
        """
        Update NicheLearning statistics.

        Tracks which niches work well for this user.
        """
        # Find or create niche learning record
        niche_learning = self.db.query(NicheLearning).filter(
            and_(
                NicheLearning.user_id == user_id,
                NicheLearning.niche == niche
            )
        ).first()

        if not niche_learning:
            niche_learning = NicheLearning(
                user_id=user_id,
                niche=niche,
                first_product_at=datetime.now()
            )
            self.db.add(niche_learning)

        # Update stats
        niche_learning.total_products_deployed += 1

        if outcome_classification in ["exceptional", "success"]:
            niche_learning.successful_products += 1
        elif outcome_classification == "failure":
            niche_learning.failed_products += 1

        niche_learning.total_revenue += revenue
        niche_learning.total_profit += profit

        # Recalculate success rate
        if niche_learning.total_products_deployed > 0:
            niche_learning.success_rate = (
                (niche_learning.successful_products / niche_learning.total_products_deployed) * 100
            )

        # Recalculate average margin
        if niche_learning.total_revenue > 0:
            niche_learning.average_margin = (
                (niche_learning.total_profit / niche_learning.total_revenue) * 100
            )

        # Update best product if this one is better
        if revenue > niche_learning.best_product_revenue:
            niche_learning.best_product_id = product_id
            niche_learning.best_product_revenue = revenue

        # Calculate niche score adjustment
        # +10 for >80% success rate
        # +5 for 60-80%
        # 0 for 40-60%
        # -5 for 20-40%
        # -10 for <20%
        if niche_learning.success_rate >= 80:
            niche_learning.niche_score_adjustment = 10
        elif niche_learning.success_rate >= 60:
            niche_learning.niche_score_adjustment = 5
        elif niche_learning.success_rate >= 40:
            niche_learning.niche_score_adjustment = 0
        elif niche_learning.success_rate >= 20:
            niche_learning.niche_score_adjustment = -5
        else:
            niche_learning.niche_score_adjustment = -10

        niche_learning.last_product_at = datetime.now()
        niche_learning.updated_at = datetime.now()

        print(f"[TREND] Niche '{niche}' updated: {niche_learning.success_rate:.1f}% success rate")

    def _update_confidence_calibration(
        self,
        user_id: int,
        recommendation_type: str,
        confidence_score: float,
        was_successful: bool
    ):
        """
        Update confidence calibration statistics.

        Tracks how accurate our confidence scores are.
        If AI says 80% confidence, does product succeed 80% of the time?
        """
        # Determine confidence bucket (10% buckets)
        bucket_min = int(confidence_score / 10) * 10
        bucket_max = bucket_min + 10

        # Find or create calibration record
        calibration = self.db.query(ConfidenceCalibration).filter(
            and_(
                ConfidenceCalibration.user_id == user_id,
                ConfidenceCalibration.confidence_bucket_min == bucket_min,
                ConfidenceCalibration.recommendation_type == recommendation_type
            )
        ).first()

        if not calibration:
            calibration = ConfidenceCalibration(
                user_id=user_id,
                confidence_bucket_min=bucket_min,
                confidence_bucket_max=bucket_max,
                recommendation_type=recommendation_type,
                expected_success_rate=bucket_min + 5  # Middle of bucket
            )
            self.db.add(calibration)

        # Update statistics
        calibration.total_recommendations += 1
        if was_successful:
            calibration.successful_outcomes += 1

        # Recalculate actual success rate
        calibration.actual_success_rate = (
            (calibration.successful_outcomes / calibration.total_recommendations) * 100
        )

        # Calculate calibration error
        calibration.calibration_error = (
            calibration.actual_success_rate - calibration.expected_success_rate
        )

        calibration.updated_at = datetime.now()

        print(f"[TARGET] Calibration updated: {bucket_min}-{bucket_max}% bucket → {calibration.actual_success_rate:.1f}% actual")
