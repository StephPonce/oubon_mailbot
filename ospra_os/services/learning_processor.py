"""
Learning Processor - G4: Complete Feedback Loop Phase 3
======================================================

Processes learning events and updates AI model weights.
This is where the AI actually "learns" from real-world outcomes.

When products succeed/fail:
1. Learning events are created (by OutcomeService)
2. This processor applies weight adjustments
3. PersonalLearningWeights are updated
4. Next recommendations use the learned weights

This transforms static AI into a continuously improving system.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from ospra_os.database import (
    AILearningEvent, GlobalLearningWeights, PersonalLearningWeights,
    NicheLearning, get_session
)


class LearningProcessor:
    """
    Processes learning events and updates AI weights.

    This service:
    1. Processes pending AILearningEvent records
    2. Applies weight adjustments from learning
    3. Updates PersonalLearningWeights
    4. Blends global + personal weights
    5. Provides weights to ConfidenceEngine

    The learning formula:
    - Start with default weights (all factors equal)
    - Adjust based on what proves predictive for THIS user
    - Blend 70% global + 30% personal for stability

    Usage:
        processor = LearningProcessor(db)
        processor.process_pending_events(user_id=1)
        weights = processor.get_weights_for_user(user_id=1)
    """

    # Default AI weights (before any learning)
    DEFAULT_WEIGHTS = {
        "historical": 0.25,    # Historical sales trend
        "market": 0.25,        # Market trend (Google Trends, etc.)
        "margin": 0.25,        # Profit margin potential
        "sentiment": 0.25,     # Social media/reviews sentiment
    }

    # Weight blend ratio (global vs personal)
    GLOBAL_WEIGHT = 0.70
    PERSONAL_WEIGHT = 0.30

    # Learning rate (how fast weights change)
    LEARNING_RATE = 1.0

    def __init__(self, db: Session):
        self.db = db

    def process_pending_events(
        self,
        user_id: Optional[int] = None
    ) -> Dict:
        """
        Process all pending learning events.

        For each event:
        1. Extract weight adjustments
        2. Apply to user's personal weights
        3. Normalize weights to sum to 1.0
        4. Mark event as processed

        Args:
            user_id: If provided, only process for this user

        Returns:
            {
                "events_processed": 15,
                "users_updated": 3,
                "weight_changes": {...}
            }
        """
        print("[BRAIN] Processing learning events...")

        # Find pending events
        query = self.db.query(AILearningEvent).filter(
            AILearningEvent.processed == False
        )

        if user_id:
            query = query.filter(AILearningEvent.user_id == user_id)

        pending_events = query.all()

        print(f" Found {len(pending_events)} pending learning events")

        # Group events by user
        events_by_user = {}
        for event in pending_events:
            if event.user_id not in events_by_user:
                events_by_user[event.user_id] = []
            events_by_user[event.user_id].append(event)

        # Process events for each user
        total_processed = 0
        weight_changes = {}

        for user_id, user_events in events_by_user.items():
            changes = self._process_user_events(user_id, user_events)
            weight_changes[user_id] = changes
            total_processed += len(user_events)

        self.db.commit()

        print(f"[SUCCESS] Processed {total_processed} events for {len(events_by_user)} users")

        return {
            "events_processed": total_processed,
            "users_updated": len(events_by_user),
            "weight_changes": weight_changes
        }

    def _process_user_events(
        self,
        user_id: int,
        events: List[AILearningEvent]
    ) -> Dict:
        """
        Process learning events for a single user.

        Aggregates all weight adjustments and applies them.

        Returns:
            Dict of weight changes applied
        """
        # Get or create personal weights
        personal_weights = self.db.query(PersonalLearningWeights).filter(
            and_(
                PersonalLearningWeights.user_id == user_id,
                PersonalLearningWeights.category == "confidence"
            )
        ).first()

        if not personal_weights:
            # Initialize with default weights
            personal_weights = PersonalLearningWeights(
                user_id=user_id,
                category="confidence",
                weights=self.DEFAULT_WEIGHTS.copy(),
                version=1
            )
            self.db.add(personal_weights)
            current_weights = self.DEFAULT_WEIGHTS.copy()
        else:
            current_weights = personal_weights.weights.copy()

        # Aggregate all weight adjustments
        total_adjustments = {factor: 0.0 for factor in self.DEFAULT_WEIGHTS.keys()}

        for event in events:
            adjustments = event.weight_adjustments or {}
            strength = event.lesson_strength or 1.0

            for factor, adjustment in adjustments.items():
                if factor in total_adjustments:
                    total_adjustments[factor] += adjustment * strength * self.LEARNING_RATE

        # Apply adjustments
        new_weights = current_weights.copy()

        for factor, adjustment in total_adjustments.items():
            if factor in new_weights:
                new_weights[factor] += adjustment
                # Ensure weights stay positive
                new_weights[factor] = max(0.05, new_weights[factor])

        # Normalize weights to sum to 1.0
        total_weight = sum(new_weights.values())
        if total_weight > 0:
            new_weights = {
                factor: weight / total_weight
                for factor, weight in new_weights.items()
            }

        # Update personal weights
        personal_weights.weights = new_weights
        personal_weights.version += 1
        personal_weights.updated_at = datetime.now()

        # Mark events as processed
        for event in events:
            event.processed = True
            event.processed_at = datetime.now()

        print(f"[TARGET] Updated weights for user {user_id}:")
        for factor, weight in new_weights.items():
            change = weight - current_weights.get(factor, 0.25)
            sign = "+" if change > 0 else ""
            print(f"   {factor}: {weight:.3f} ({sign}{change:.3f})")

        return {
            "previous": current_weights,
            "adjustments": total_adjustments,
            "new": new_weights
        }

    def get_weights_for_user(
        self,
        user_id: int,
        category: str = "confidence"
    ) -> Dict[str, float]:
        """
        Get effective weights for a user.

        Blends global weights + personal weights:
        - 70% global (learned from all users)
        - 30% personal (learned from this user)

        This provides stability while personalizing.

        Args:
            user_id: User ID
            category: Weight category (default "confidence")

        Returns:
            Dict of factor weights (sums to 1.0)
        """
        # Get global weights
        global_weights_record = self.db.query(GlobalLearningWeights).filter(
            GlobalLearningWeights.category == category
        ).first()

        if global_weights_record:
            global_weights = global_weights_record.weights
        else:
            global_weights = self.DEFAULT_WEIGHTS.copy()

        # Get personal weights
        personal_weights_record = self.db.query(PersonalLearningWeights).filter(
            and_(
                PersonalLearningWeights.user_id == user_id,
                PersonalLearningWeights.category == category
            )
        ).first()

        if personal_weights_record:
            personal_weights = personal_weights_record.weights
        else:
            personal_weights = self.DEFAULT_WEIGHTS.copy()

        # Blend weights
        blended_weights = {}
        for factor in self.DEFAULT_WEIGHTS.keys():
            global_w = global_weights.get(factor, 0.25)
            personal_w = personal_weights.get(factor, 0.25)

            blended_weights[factor] = (
                global_w * self.GLOBAL_WEIGHT +
                personal_w * self.PERSONAL_WEIGHT
            )

        # Normalize (should already be normalized, but just in case)
        total_weight = sum(blended_weights.values())
        if total_weight > 0:
            blended_weights = {
                factor: weight / total_weight
                for factor, weight in blended_weights.items()
            }

        return blended_weights

    def get_niche_adjustment(
        self,
        user_id: int,
        niche: str
    ) -> float:
        """
        Get score adjustment for a specific niche.

        If user has 85% success rate in fitness,
        we boost fitness product scores by +10.

        If user has 20% success rate in home décor,
        we penalize home décor scores by -10.

        Args:
            user_id: User ID
            niche: Niche/category name

        Returns:
            Score adjustment (-10 to +10)
        """
        niche_learning = self.db.query(NicheLearning).filter(
            and_(
                NicheLearning.user_id == user_id,
                NicheLearning.niche == niche
            )
        ).first()

        if niche_learning:
            return niche_learning.niche_score_adjustment
        else:
            return 0.0  # No adjustment if no history

    def get_learning_stats(
        self,
        user_id: int
    ) -> Dict:
        """
        Get learning statistics for a user.

        Returns comprehensive learning metrics:
        - Current weights
        - Niche performance
        - Total learning events processed
        - Weight evolution over time

        Args:
            user_id: User ID

        Returns:
            Dict of learning statistics
        """
        # Get current weights
        weights = self.get_weights_for_user(user_id)

        # Get personal weights record
        personal_weights = self.db.query(PersonalLearningWeights).filter(
            and_(
                PersonalLearningWeights.user_id == user_id,
                PersonalLearningWeights.category == "confidence"
            )
        ).first()

        # Get niche performance
        niche_learnings = self.db.query(NicheLearning).filter(
            NicheLearning.user_id == user_id
        ).all()

        niche_performance = []
        for nl in niche_learnings:
            niche_performance.append({
                "niche": nl.niche,
                "products_deployed": nl.total_products_deployed,
                "success_rate": nl.success_rate,
                "total_revenue": nl.total_revenue,
                "score_adjustment": nl.niche_score_adjustment
            })

        # Sort by success rate
        niche_performance.sort(key=lambda x: x["success_rate"], reverse=True)

        # Count learning events
        total_events = self.db.query(func.count(AILearningEvent.id)).filter(
            and_(
                AILearningEvent.user_id == user_id,
                AILearningEvent.processed == True
            )
        ).scalar()

        # Count positive/negative signals
        positive_events = self.db.query(func.count(AILearningEvent.id)).filter(
            and_(
                AILearningEvent.user_id == user_id,
                AILearningEvent.lesson_type == "positive_signal"
            )
        ).scalar()

        negative_events = self.db.query(func.count(AILearningEvent.id)).filter(
            and_(
                AILearningEvent.user_id == user_id,
                AILearningEvent.lesson_type == "negative_signal"
            )
        ).scalar()

        return {
            "user_id": user_id,
            "current_weights": weights,
            "weight_version": personal_weights.version if personal_weights else 0,
            "last_updated": personal_weights.updated_at if personal_weights else None,
            "niche_performance": niche_performance,
            "total_learning_events": total_events,
            "positive_signals": positive_events,
            "negative_signals": negative_events,
            "learning_ratio": round(positive_events / max(total_events, 1) * 100, 1)
        }

    def update_global_weights(
        self,
        category: str = "confidence"
    ) -> Dict:
        """
        Update global weights based on all users' learning.

        This should be run periodically (weekly) to update
        the baseline weights for all users.

        Aggregates personal weights across all users.

        Args:
            category: Weight category

        Returns:
            Updated global weights
        """
        print(f" Updating global weights for category: {category}")

        # Get all personal weights
        all_personal_weights = self.db.query(PersonalLearningWeights).filter(
            PersonalLearningWeights.category == category
        ).all()

        if not all_personal_weights:
            print("[WARNING]  No personal weights found, keeping defaults")
            return self.DEFAULT_WEIGHTS

        # Average all personal weights
        factor_sums = {factor: 0.0 for factor in self.DEFAULT_WEIGHTS.keys()}
        user_count = len(all_personal_weights)

        for pw in all_personal_weights:
            for factor, weight in pw.weights.items():
                if factor in factor_sums:
                    factor_sums[factor] += weight

        # Calculate averages
        global_weights = {
            factor: sum_weight / user_count
            for factor, sum_weight in factor_sums.items()
        }

        # Normalize
        total_weight = sum(global_weights.values())
        if total_weight > 0:
            global_weights = {
                factor: weight / total_weight
                for factor, weight in global_weights.items()
            }

        # Update or create global weights record
        global_record = self.db.query(GlobalLearningWeights).filter(
            GlobalLearningWeights.category == category
        ).first()

        if global_record:
            global_record.weights = global_weights
            global_record.version += 1
            global_record.updated_at = datetime.now()
        else:
            global_record = GlobalLearningWeights(
                category=category,
                weights=global_weights,
                version=1
            )
            self.db.add(global_record)

        self.db.commit()

        print(f"[SUCCESS] Global weights updated (version {global_record.version}):")
        for factor, weight in global_weights.items():
            print(f"   {factor}: {weight:.3f}")

        return global_weights
