"""
Feedback Loop Tasks - G4: Complete Feedback Loop
=================================================

Automated Celery tasks for the G4 feedback loop system.

These tasks run automatically in the background to:
1. Sync sales data from Shopify/Amazon (every 6 hours)
2. Evaluate AI recommendations vs reality (daily)
3. Process learning events and update AI weights (daily)

This automation is what enables continuous learning without manual intervention.

Scheduled Jobs:
- sync_all_stores_task: Every 6 hours
- evaluate_outcomes_task: Daily at 2 AM
- process_learning_task: Daily at 3 AM
- daily_feedback_loop: Daily at 4 AM (master task)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from ospra_os.celery_app import celery_app
from ospra_os.tasks.base import UserTask
from ospra_os.services.sales_sync_service import SalesSyncService
from ospra_os.services.outcome_service import OutcomeService
from ospra_os.services.learning_processor import LearningProcessor

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=UserTask,
    name="ospra_os.tasks.feedback_tasks.sync_all_stores_task",
    max_retries=3,
    default_retry_delay=300,
    rate_limit="10/h"  # Max 10 full syncs per hour
)
def sync_all_stores_task(self, days_back: int = 1) -> Dict[str, Any]:
    """
    Sync sales data from all active stores.

    This is STEP 1 of the feedback loop - fetching real sales data.

    Runs every 6 hours to keep performance data fresh.

    Args:
        days_back: Number of days to sync (default 1 for incremental sync)

    Returns:
        Sync summary with stores synced and products updated
    """
    logger.info(f"[REFRESH] Starting sales sync for all stores ({days_back} days)")

    try:
        service = SalesSyncService(self.db)

        # Use import to avoid circular dependencies
        import asyncio
        results = asyncio.run(service.sync_all_stores(days_back=days_back))

        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]

        total_products = sum(r.get("products_updated", 0) for r in successful)
        total_orders = sum(r.get("orders_fetched", 0) for r in successful)

        logger.info(
            f"[SUCCESS] Sales sync complete: {len(successful)}/{len(results)} stores synced, "
            f"{total_products} products updated, {total_orders} orders fetched"
        )

        if failed:
            logger.warning(f"[WARNING]  {len(failed)} stores failed to sync")

        return {
            "status": "success",
            "stores_synced": len(successful),
            "stores_failed": len(failed),
            "products_updated": total_products,
            "orders_fetched": total_orders,
            "errors": [r.get("error") for r in failed if r.get("error")]
        }

    except Exception as e:
        logger.error(f"[ERROR] Sales sync failed: {e}")
        raise


@celery_app.task(
    bind=True,
    base=UserTask,
    name="ospra_os.tasks.feedback_tasks.evaluate_outcomes_task",
    max_retries=2,
    default_retry_delay=600
)
def evaluate_outcomes_task(self) -> Dict[str, Any]:
    """
    Evaluate pending recommendation outcomes.

    This is STEP 2 of the feedback loop - comparing AI predictions to reality.

    For recommendations made 7+ days ago, compares predicted performance
    to actual sales data and generates learning signals.

    Runs daily to evaluate newly matured outcomes.

    Returns:
        Evaluation summary with outcomes evaluated and learning events created
    """
    logger.info("[STATS] Starting outcome evaluation")

    try:
        service = OutcomeService(self.db)

        # Use import to avoid circular dependencies
        import asyncio
        results = asyncio.run(service.evaluate_outcomes())

        learning_events = sum(r.get("learning_events_created", 0) for r in results)

        logger.info(
            f"[SUCCESS] Outcome evaluation complete: {len(results)} outcomes evaluated, "
            f"{learning_events} learning events created"
        )

        # Calculate breakdown by outcome type
        outcome_breakdown = {}
        for result in results:
            outcome_type = result.get("outcome")
            if outcome_type:
                outcome_breakdown[outcome_type] = outcome_breakdown.get(outcome_type, 0) + 1

        return {
            "status": "success",
            "outcomes_evaluated": len(results),
            "learning_events_created": learning_events,
            "outcome_breakdown": outcome_breakdown
        }

    except Exception as e:
        logger.error(f"[ERROR] Outcome evaluation failed: {e}")
        raise


@celery_app.task(
    bind=True,
    base=UserTask,
    name="ospra_os.tasks.feedback_tasks.process_learning_task",
    max_retries=2,
    default_retry_delay=600
)
def process_learning_task(self) -> Dict[str, Any]:
    """
    Process pending learning events and update AI weights.

    This is STEP 3 of the feedback loop - applying the lessons learned.

    Processes all learning events generated by outcome evaluation
    and updates user-specific AI weights based on what actually works.

    Runs daily after outcome evaluation.

    Returns:
        Processing summary with events processed and users updated
    """
    logger.info("[BRAIN] Starting learning event processing")

    try:
        processor = LearningProcessor(self.db)
        result = processor.process_pending_events()

        logger.info(
            f"[SUCCESS] Learning processing complete: {result['events_processed']} events processed, "
            f"{result['users_updated']} users updated"
        )

        return {
            "status": "success",
            "events_processed": result["events_processed"],
            "users_updated": result["users_updated"],
            "weight_changes": result.get("weight_changes", {})
        }

    except Exception as e:
        logger.error(f"[ERROR] Learning processing failed: {e}")
        raise


@celery_app.task(
    bind=True,
    base=UserTask,
    name="ospra_os.tasks.feedback_tasks.update_global_weights_task",
    max_retries=2,
    default_retry_delay=900
)
def update_global_weights_task(self) -> Dict[str, Any]:
    """
    Update global AI weights based on all users' learning.

    Aggregates personalized weights across all users to create
    a global baseline that benefits everyone.

    Runs weekly.

    Returns:
        Updated global weights
    """
    logger.info(" Starting global weights update")

    try:
        processor = LearningProcessor(self.db)
        global_weights = processor.update_global_weights(category="confidence")

        logger.info(f"[SUCCESS] Global weights updated: {global_weights}")

        return {
            "status": "success",
            "global_weights": global_weights
        }

    except Exception as e:
        logger.error(f"[ERROR] Global weights update failed: {e}")
        raise


@celery_app.task(
    bind=True,
    base=UserTask,
    name="ospra_os.tasks.feedback_tasks.daily_feedback_loop",
    max_retries=1,
    default_retry_delay=1800
)
def daily_feedback_loop(self) -> Dict[str, Any]:
    """
    Master task that orchestrates the complete feedback loop.

    Runs the full cycle:
    1. Sync sales data from stores
    2. Evaluate outcomes (AI predictions vs reality)
    3. Process learning events
    4. Update AI weights

    This is the COMPLETE G4 feedback loop in one automated task.

    Runs once daily.

    Returns:
        Complete feedback loop summary
    """
    logger.info(" Starting daily feedback loop")

    results = {
        "status": "success",
        "started_at": datetime.now().isoformat(),
        "steps": {}
    }

    try:
        # Step 1: Sync sales data
        logger.info("Step 1/3: Syncing sales data...")
        sync_result = sync_all_stores_task.apply().get()
        results["steps"]["sync"] = sync_result

        # Step 2: Evaluate outcomes
        logger.info("Step 2/3: Evaluating outcomes...")
        evaluate_result = evaluate_outcomes_task.apply().get()
        results["steps"]["evaluate"] = evaluate_result

        # Step 3: Process learning
        logger.info("Step 3/3: Processing learning...")
        learning_result = process_learning_task.apply().get()
        results["steps"]["learning"] = learning_result

        results["completed_at"] = datetime.now().isoformat()
        results["duration_seconds"] = (
            datetime.fromisoformat(results["completed_at"]) -
            datetime.fromisoformat(results["started_at"])
        ).total_seconds()

        logger.info(
            f"[SUCCESS] Daily feedback loop complete in {results['duration_seconds']:.1f}s: "
            f"{sync_result['products_updated']} products synced, "
            f"{evaluate_result['outcomes_evaluated']} outcomes evaluated, "
            f"{learning_result['events_processed']} learning events processed"
        )

        return results

    except Exception as e:
        logger.error(f"[ERROR] Daily feedback loop failed: {e}")
        results["status"] = "failed"
        results["error"] = str(e)
        raise


# ====================================================================================
# CELERY BEAT SCHEDULE
# ====================================================================================
#
# Add these entries to your celery_app beat_schedule configuration:
#
# 'feedback-sync-sales': {
#     'task': 'ospra_os.tasks.feedback_tasks.sync_all_stores_task',
#     'schedule': crontab(hour='*/6'),  # Every 6 hours
#     'args': (1,)  # Sync last 1 day
# },
#
# 'feedback-evaluate-outcomes': {
#     'task': 'ospra_os.tasks.feedback_tasks.evaluate_outcomes_task',
#     'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
# },
#
# 'feedback-process-learning': {
#     'task': 'ospra_os.tasks.feedback_tasks.process_learning_task',
#     'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
# },
#
# 'feedback-daily-loop': {
#     'task': 'ospra_os.tasks.feedback_tasks.daily_feedback_loop',
#     'schedule': crontab(hour=4, minute=0),  # Daily at 4 AM
# },
#
# 'feedback-update-global-weights': {
#     'task': 'ospra_os.tasks.feedback_tasks.update_global_weights_task',
#     'schedule': crontab(day_of_week=1, hour=1, minute=0),  # Weekly on Monday at 1 AM
# },
#
# ====================================================================================
