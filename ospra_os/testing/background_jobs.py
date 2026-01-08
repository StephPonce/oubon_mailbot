"""
Background Jobs for A/B Testing

Automated test monitoring, management, and notifications.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
import logging

from ospra_os.database.multi_store_models import (
    get_multi_store_session,
    ABTest,
    ABTestVariant
)
from .ab_test_engine import ABTestEngine, TestStatus
from .shopify_integration import ShopifyABTestIntegration

logger = logging.getLogger(__name__)


class ABTestMonitor:
    """
    Background monitor for A/B tests

    Jobs:
    - Check for tests that should be auto-ended
    - Check for tests that reached statistical significance
    - Auto-implement winners (if configured)
    - Send notifications
    """

    def __init__(self, database_url: str = "sqlite:///./multi_store.db"):
        self.database_url = database_url

    def monitor_tests(self):
        """
        Main monitoring job - runs hourly

        Checks:
        1. Tests that should be ended (scheduled_end reached)
        2. Tests with significant results
        3. Tests ready for winner implementation
        """
        logger.info("[SEARCH] A/B Test Monitor: Starting hourly check...")

        db = get_multi_store_session(self.database_url)
        try:
            engine = ABTestEngine(db)

            # 1. Check for tests to auto-end
            self._auto_end_tests(db, engine)

            # 2. Check for statistically significant tests
            self._check_significant_tests(db, engine)

            # 3. Auto-implement winners (if configured)
            self._auto_implement_winners(db, engine)

            logger.info("[SUCCESS] A/B Test Monitor: Hourly check complete")

        except Exception as e:
            logger.error(f"[ERROR] A/B Test Monitor failed: {e}")
        finally:
            db.close()

    def _auto_end_tests(self, db: Session, engine: ABTestEngine):
        """Auto-end tests that have reached their scheduled end time"""
        now = datetime.utcnow()

        # Find running tests with scheduled_end in the past
        result = db.execute(
            select(ABTest).where(
                and_(
                    ABTest.status == TestStatus.RUNNING.value,
                    ABTest.scheduled_end <= now
                )
            )
        )
        tests_to_end = result.scalars().all()

        if not tests_to_end:
            logger.info("   No tests to auto-end")
            return

        logger.info(f"   Found {len(tests_to_end)} tests to auto-end")

        for test in tests_to_end:
            try:
                # Check if test has auto_implement_winner configured
                auto_implement = test.test_metadata.get("auto_implement_winner", False)

                engine.end_test(
                    test.id,
                    implement_winner=auto_implement
                )

                logger.info(f"   [SUCCESS] Auto-ended test {test.id}: {test.name}")

                if auto_implement:
                    logger.info(f"      [START] Auto-implemented winner for test {test.id}")

            except Exception as e:
                logger.error(f"   [ERROR] Failed to end test {test.id}: {e}")

    def _check_significant_tests(self, db: Session, engine: ABTestEngine):
        """Check for tests that have reached statistical significance"""
        # Find running tests
        result = db.execute(
            select(ABTest).where(ABTest.status == TestStatus.RUNNING.value)
        )
        running_tests = result.scalars().all()

        if not running_tests:
            logger.info("   No running tests to check")
            return

        logger.info(f"   Checking {len(running_tests)} running tests for significance...")

        for test in running_tests:
            try:
                # Check if test has enough data
                variants_result = db.execute(
                    select(ABTestVariant).where(ABTestVariant.test_id == test.id)
                )
                variants = variants_result.scalars().all()

                max_conversions = max(v.conversions for v in variants)

                if max_conversions < test.min_sample_size:
                    continue  # Not enough data yet

                # Check statistical significance
                significance = engine.check_statistical_significance(test.id)

                # Check if any variant is significant
                has_significant = any(
                    result.get("is_significant", False)
                    for result in significance.values()
                )

                if has_significant:
                    logger.info(f"   [STATS] Test {test.id} has statistically significant results!")

                    # TODO: Send notification
                    # self._send_notification(test, significance)

            except Exception as e:
                logger.error(f"   [ERROR] Failed to check test {test.id}: {e}")

    def _auto_implement_winners(self, db: Session, engine: ABTestEngine):
        """Auto-implement winners for ended tests (if configured)"""
        # Find ended tests that haven't been implemented yet
        result = db.execute(
            select(ABTest).where(
                and_(
                    ABTest.status == TestStatus.ENDED.value,
                    ABTest.winner_variant_id.isnot(None)
                )
            )
        )
        ended_tests = result.scalars().all()

        if not ended_tests:
            logger.info("   No tests ready for winner implementation")
            return

        logger.info(f"   Found {len(ended_tests)} ended tests")

        for test in ended_tests:
            try:
                # Check if already implemented
                if test.test_metadata.get("implemented_at"):
                    continue  # Already implemented

                # Check if auto-implement is enabled
                if not test.test_metadata.get("auto_implement_winner", False):
                    continue  # Manual implementation required

                # Get winning variant
                variant_result = db.execute(
                    select(ABTestVariant).where(
                        ABTestVariant.id == test.winner_variant_id
                    )
                )
                winner = variant_result.scalar_one_or_none()

                if not winner:
                    continue

                # Implement winner via Shopify
                shopify = ShopifyABTestIntegration(db)
                result = shopify.apply_test_winner(
                    test_type=test.test_type,
                    store_id=test.store_id,
                    product_id=test.product_id,
                    winning_config=winner.config
                )

                if result.get("success"):
                    # Mark as implemented
                    test.test_metadata["implemented_at"] = datetime.utcnow().isoformat()
                    test.test_metadata["shopify_result"] = result
                    db.commit()

                    logger.info(f"   [START] Implemented winner for test {test.id}: {test.name}")
                else:
                    logger.error(f"   [ERROR] Failed to implement winner for test {test.id}: {result.get('error')}")

            except Exception as e:
                logger.error(f"   [ERROR] Failed to implement winner for test {test.id}: {e}")

    def cleanup_old_tests(self, days: int = 90):
        """
        Clean up old test data

        Archives or deletes tests older than specified days.

        Args:
            days: Number of days to keep test data
        """
        logger.info(f" Cleaning up tests older than {days} days...")

        db = get_multi_store_session(self.database_url)
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Find old ended tests
            result = db.execute(
                select(ABTest).where(
                    and_(
                        ABTest.status == TestStatus.ENDED.value,
                        ABTest.ended_at <= cutoff_date
                    )
                )
            )
            old_tests = result.scalars().all()

            if not old_tests:
                logger.info("   No old tests to clean up")
                return

            logger.info(f"   Found {len(old_tests)} old tests to archive")

            for test in old_tests:
                # Archive test data to metadata before deletion
                test.test_metadata["archived_at"] = datetime.utcnow().isoformat()
                test.test_metadata["archived"] = True

            db.commit()

            logger.info(f"   [SUCCESS] Archived {len(old_tests)} old tests")

        except Exception as e:
            logger.error(f"   [ERROR] Cleanup failed: {e}")
        finally:
            db.close()

    def send_test_summary(self):
        """
        Send daily test summary

        Reports:
        - Active tests count
        - Tests with significant results
        - Tests requiring action
        """
        logger.info("[EMAIL] Generating A/B test summary...")

        db = get_multi_store_session(self.database_url)
        try:
            # Count tests by status
            result = db.execute(select(ABTest))
            all_tests = result.scalars().all()

            running = sum(1 for t in all_tests if t.status == TestStatus.RUNNING.value)
            paused = sum(1 for t in all_tests if t.status == TestStatus.PAUSED.value)
            ended = sum(1 for t in all_tests if t.status == TestStatus.ENDED.value)

            summary = {
                "date": datetime.utcnow().isoformat(),
                "running_tests": running,
                "paused_tests": paused,
                "ended_tests": ended,
                "total_tests": len(all_tests)
            }

            logger.info(f"   [STATS] A/B Test Summary:")
            logger.info(f"      Running: {running}")
            logger.info(f"      Paused: {paused}")
            logger.info(f"      Ended: {ended}")
            logger.info(f"      Total: {len(all_tests)}")

            # TODO: Send email/Slack notification with summary

        except Exception as e:
            logger.error(f"   [ERROR] Summary generation failed: {e}")
        finally:
            db.close()


# ============================================================================
# SCHEDULER INTEGRATION
# ============================================================================

def setup_abtesting_jobs(scheduler):
    """
    Setup A/B testing background jobs

    Jobs:
    - Hourly test monitoring
    - Daily test summary
    - Weekly cleanup

    Args:
        scheduler: APScheduler instance
    """
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    monitor = ABTestMonitor()

    # Hourly test monitoring
    scheduler.add_job(
        monitor.monitor_tests,
        trigger=IntervalTrigger(hours=1),
        id="abtesting_hourly_monitor",
        name="A/B Test Hourly Monitor",
        replace_existing=True
    )

    # Daily test summary (8 AM)
    scheduler.add_job(
        monitor.send_test_summary,
        trigger=CronTrigger(hour=8, minute=0),
        id="abtesting_daily_summary",
        name="A/B Test Daily Summary",
        replace_existing=True
    )

    # Weekly cleanup (Sunday 2 AM)
    scheduler.add_job(
        monitor.cleanup_old_tests,
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="abtesting_weekly_cleanup",
        name="A/B Test Weekly Cleanup",
        replace_existing=True
    )

    logger.info("[SUCCESS] A/B Testing background jobs configured:")
    logger.info("   • Hourly test monitoring")
    logger.info("   • Daily test summary (8 AM)")
    logger.info("   • Weekly cleanup (Sunday 2 AM)")


print("[SUCCESS] A/B Testing background jobs loaded successfully")
