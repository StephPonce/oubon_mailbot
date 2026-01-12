"""
Daily Product Ranking Job

Runs daily at 3 AM to:
1. Calculate composite scores for all products
2. Generate rankings (top 20)
3. Store historical snapshots in RankingHistory table
4. Calculate rank changes from previous day
5. Send email notifications for Top 10 and ELITE entries

Author: OspraOS
Date: November 2025
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ospra_os.database import (
    get_multi_store_session,
    RankingHistory
)
from ospra_os.intelligence.ranking_engine import RankingEngine
from ospra_os.notifications.ranking_notifier import RankingNotifier

logger = logging.getLogger(__name__)


class DailyRankingJob:
    """
    Background job for daily product ranking calculations.
    """

    def __init__(self, database_url: str):
        """
        Initialize the daily ranking job.

        Args:
            database_url: Database connection string
        """
        self.database_url = database_url
        self.scheduler = BackgroundScheduler()
        self.job_id = "daily_product_rankings"

        logger.info("DailyRankingJob initialized")

    def schedule_rankings(self, hour: int = 3, minute: int = 0):
        """
        Schedule daily ranking job to run at specified time.

        Args:
            hour: Hour of day (0-23), default 3 AM
            minute: Minute of hour (0-59), default 0
        """
        try:
            # Remove existing job if any
            self.unschedule_rankings()

            # Create cron trigger (runs daily at specified time)
            trigger = CronTrigger(hour=hour, minute=minute)

            # Schedule the job
            self.scheduler.add_job(
                self._run_daily_ranking,
                trigger=trigger,
                id=self.job_id,
                name="Daily Product Rankings",
                replace_existing=True,
                misfire_grace_time=3600  # Allow 1 hour grace time if missed
            )

            # Start scheduler if not running
            if not self.scheduler.running:
                self.scheduler.start()

            logger.info(f"[SUCCESS] Daily ranking job scheduled for {hour:02d}:{minute:02d}")

        except Exception as e:
            logger.error(f"Failed to schedule ranking job: {e}")

    def unschedule_rankings(self):
        """Remove scheduled ranking job."""
        try:
            if self.scheduler.get_job(self.job_id):
                self.scheduler.remove_job(self.job_id)
                logger.info("Ranking job unscheduled")
        except Exception as e:
            logger.warning(f"Error unscheduling ranking job: {e}")

    async def _run_daily_ranking(self):
        """
        Internal method that runs the daily ranking calculation.
        Called by scheduler.
        """
        logger.info("[TOP] Starting daily product ranking job...")

        try:
            # Get database session
            session = get_multi_store_session(self.database_url)
            engine = RankingEngine(session)

            # Generate current rankings
            current_rankings = await engine.generate_daily_rankings()

            # Get previous rankings (yesterday)
            yesterday = datetime.utcnow() - timedelta(days=1)
            previous_rankings = self._get_previous_rankings(session, yesterday)

            # Store rankings in history
            self._store_ranking_history(
                session,
                current_rankings,
                previous_rankings
            )

            logger.info(f"[SUCCESS] Daily ranking job complete: {len(current_rankings)} products ranked")

            return {
                "success": True,
                "products_ranked": len(current_rankings),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Daily ranking job failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def _get_previous_rankings(self, session, date) -> Dict[int, int]:
        """
        Get product rankings from previous day.

        Args:
            session: Database session
            date: Date to query

        Returns:
            Dict mapping product_id to rank
        """
        try:
            # Query most recent rankings for each product before target date
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)

            previous = session.query(RankingHistory).filter(
                RankingHistory.snapshot_date.between(start_of_day, end_of_day)
            ).all()

            return {r.product_id: r.rank for r in previous}

        except Exception as e:
            logger.warning(f"Could not fetch previous rankings: {e}")
            return {}

    def _store_ranking_history(
        self,
        session,
        current_rankings: List[Dict],
        previous_rankings: Dict[int, int]
    ):
        """
        Store current rankings in history table with rank changes.
        Send email notifications for products entering Top 10 or ELITE tier.

        Args:
            session: Database session
            current_rankings: List of ranked products
            previous_rankings: Dict of previous ranks by product_id
        """
        try:
            now = datetime.utcnow()

            # Track products that need notifications
            top_10_entries = []
            elite_entries = []

            for product in current_rankings:
                product_id = product["product_id"]
                current_rank = product["rank"]
                previous_rank = previous_rankings.get(product_id)

                # Calculate rank change
                if previous_rank is not None:
                    rank_change = previous_rank - current_rank  # Positive = moved up
                    if rank_change > 0:
                        rank_direction = "up"
                    elif rank_change < 0:
                        rank_direction = "down"
                    else:
                        rank_direction = "stable"
                else:
                    rank_change = 0
                    rank_direction = "new"  # New entry to rankings

                # Create history record
                history = RankingHistory(
                    product_id=product_id,
                    rank=current_rank,
                    composite_score=product["composite_score"],
                    score_breakdown=product["score_breakdown"],
                    previous_rank=previous_rank,
                    rank_change=rank_change,
                    rank_direction=rank_direction,
                    tier_name=product["tier"]["name"],
                    snapshot_date=now
                )

                session.add(history)

                # Check for notification triggers
                # Top 10 entry: product wasn't in top 10 before, now is
                if current_rank <= 10 and (previous_rank is None or previous_rank > 10):
                    top_10_entries.append((product, previous_rank))
                    logger.info(f"[TOP] Product {product_id} entered Top 10 at rank #{current_rank}")

                # ELITE tier entry: product reached top 3
                if current_rank <= 3 and (previous_rank is None or previous_rank > 3):
                    elite_entries.append(product)
                    logger.info(f" Product {product_id} entered ELITE tier at rank #{current_rank}")

            session.commit()
            logger.info(f"Stored {len(current_rankings)} ranking history records")

            # Send notifications after successful commit
            self._send_notifications(top_10_entries, elite_entries)

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store ranking history: {e}")

    def _send_notifications(
        self,
        top_10_entries: List[tuple],
        elite_entries: List[Dict]
    ):
        """
        Send email notifications for ranking milestones.

        Args:
            top_10_entries: List of (product, previous_rank) tuples for Top 10 entries
            elite_entries: List of products that entered ELITE tier (Top 3)
        """
        try:
            # Get notification emails from environment
            notification_emails_str = os.getenv('RANKING_NOTIFICATION_EMAILS', '')

            if not notification_emails_str:
                logger.info("No notification emails configured (RANKING_NOTIFICATION_EMAILS not set)")
                return

            # Parse comma-separated email list
            notification_emails = [email.strip() for email in notification_emails_str.split(',') if email.strip()]

            if not notification_emails:
                logger.warning("RANKING_NOTIFICATION_EMAILS is set but contains no valid emails")
                return

            logger.info(f"Sending notifications to {len(notification_emails)} recipient(s)")

            # Initialize notifier
            notifier = RankingNotifier()

            # Send Top 10 entry notifications
            for product, previous_rank in top_10_entries:
                try:
                    notifier.notify_top_10_entry(
                        product=product,
                        previous_rank=previous_rank,
                        to_emails=notification_emails
                    )
                except Exception as e:
                    logger.error(f"Failed to send Top 10 notification for product {product.get('product_id')}: {e}")

            # Send ELITE tier notifications
            for product in elite_entries:
                try:
                    notifier.notify_elite_entry(
                        product=product,
                        to_emails=notification_emails
                    )
                except Exception as e:
                    logger.error(f"Failed to send ELITE notification for product {product.get('product_id')}: {e}")

            if top_10_entries or elite_entries:
                logger.info(f"[EMAIL]  Sent {len(top_10_entries)} Top 10 and {len(elite_entries)} ELITE notifications")

        except Exception as e:
            logger.error(f"Error sending ranking notifications: {e}")

    async def run_ranking_manually(self) -> Dict:
        """
        Manually trigger ranking calculation (for testing/debugging).

        Returns:
            Result dict with success status and stats
        """
        logger.info("Manual ranking calculation triggered")
        return await self._run_daily_ranking()

    def get_ranking_stats(self, days: int = 30) -> Dict:
        """
        Get ranking job statistics.

        Args:
            days: Number of days to look back

        Returns:
            Dict with ranking stats
        """
        try:
            session = get_multi_store_session(self.database_url)
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            total_snapshots = session.query(RankingHistory).filter(
                RankingHistory.snapshot_date >= cutoff_date
            ).count()

            # Get unique products ranked
            unique_products = session.query(RankingHistory.product_id).filter(
                RankingHistory.snapshot_date >= cutoff_date
            ).distinct().count()

            return {
                "total_snapshots": total_snapshots,
                "unique_products_ranked": unique_products,
                "days_tracked": days,
                "scheduler_running": self.scheduler.running
            }

        except Exception as e:
            logger.error(f"Failed to get ranking stats: {e}")
            return {"error": str(e)}


def start_daily_ranking_scheduler(
    database_url: str,
    hour: int = 3,
    minute: int = 0
) -> DailyRankingJob:
    """
    Convenience function to create and start daily ranking job.

    Args:
        database_url: Database connection string
        hour: Hour to run (0-23), default 3 AM
        minute: Minute to run (0-59), default 0

    Returns:
        DailyRankingJob instance
    """
    job = DailyRankingJob(database_url)
    job.schedule_rankings(hour=hour, minute=minute)
    return job


logger.info("[SUCCESS] DailyRankingJob module loaded")
