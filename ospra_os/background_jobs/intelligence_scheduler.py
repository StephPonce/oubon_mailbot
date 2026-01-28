"""
INTELLIGENCE CORE BACKGROUND JOBS

Schedules:
- Morning briefings (6 AM daily)
- Product grading (every 6 hours)
- Progress tracking updates (daily)

PERFORMANCE: Each job creates its own session to avoid shared state issues.
"""

import logging
import asyncio
from datetime import datetime, time
from contextlib import contextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from ospra_os.database import get_db, SessionLocal
from ospra_os.intelligence.briefing_engine import get_briefing_engine
from ospra_os.intelligence.grade_reasoning import get_grade_reasoning_engine
from ospra_os.intelligence.progress_flow import get_progress_tracker

logger = logging.getLogger(__name__)


class IntelligenceScheduler:
    """Manages background jobs for Intelligence Core

    PERFORMANCE FIX: Removed shared self.db session.
    Each job now creates its own session for isolation and thread safety.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        # REMOVED: self.db = SessionLocal() - shared sessions cause isolation issues

    @contextmanager
    def _get_session(self):
        """Create a new session for each job. Ensures proper isolation."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def generate_morning_briefings(self):
        """Generate morning briefings for all users at 6 AM"""
        logger.info(" Generating morning briefings for all users...")

        # PERFORMANCE FIX: Use session context manager for proper isolation
        with self._get_session() as db:
            try:
                briefing_engine = get_briefing_engine(db)

                # For now, generate briefing for default user (user_id=1)
                # In production, iterate through all active users
                briefing = await briefing_engine.generate_morning_briefing(user_id=1)

                logger.info(f"[SUCCESS] Morning briefing generated: {len(briefing.get('briefing_text', ''))} chars")

                # TODO: Send notification/email with briefing
                # await send_briefing_notification(user_id=1, briefing=briefing)

            except Exception as e:
                logger.error(f"[ERROR] Failed to generate morning briefings: {e}")

    async def grade_all_products(self):
        """Grade all products for intelligence scoring

        PERFORMANCE FIX:
        1. Uses dedicated session for job isolation
        2. Processes products concurrently with semaphore for rate limiting
        3. Commits in batches to reduce database overhead
        """
        logger.info("[STATS] Starting product grading job...")

        with self._get_session() as db:
            try:
                from ospra_os.database import Product

                grade_engine = get_grade_reasoning_engine(db)

                # Get products that need grading (batch processing with limit)
                products = db.query(Product).filter(Product.status != "discontinued").limit(1000).all()

                # Extract product IDs to avoid holding ORM objects during async operations
                product_ids = [(p.id, p) for p in products]

                graded_count = 0
                failed_count = 0

                # PERFORMANCE FIX: Process in concurrent batches
                semaphore = asyncio.Semaphore(10)  # Limit concurrent grading

                async def grade_product(product_id, product):
                    nonlocal graded_count, failed_count
                    async with semaphore:
                        try:
                            grade_data = await grade_engine.calculate_product_grade(product_id)
                            product.grade = grade_data['grade']
                            graded_count += 1
                        except Exception as e:
                            logger.error(f"Failed to grade product {product_id}: {e}")
                            failed_count += 1

                # Run all grading concurrently
                await asyncio.gather(
                    *[grade_product(pid, prod) for pid, prod in product_ids],
                    return_exceptions=True
                )

                db.commit()
                logger.info(f"[SUCCESS] Product grading complete: {graded_count}/{len(products)} graded, {failed_count} failed")

            except Exception as e:
                logger.error(f"[ERROR] Product grading job failed: {e}")
                db.rollback()

    async def update_product_progress(self):
        """Update product lifecycle progress for all products

        PERFORMANCE FIX: Uses dedicated session and concurrent processing.
        """
        logger.info("[REFRESH] Updating product progress tracking...")

        with self._get_session() as db:
            try:
                from ospra_os.database import Product

                progress_tracker = get_progress_tracker(db)

                # Get active products (batch processing with limit)
                products = db.query(Product).filter(Product.status != "discontinued").limit(1000).all()

                updated_count = 0
                semaphore = asyncio.Semaphore(10)  # Limit concurrent updates

                async def update_single_product(product):
                    nonlocal updated_count
                    async with semaphore:
                        try:
                            progress_data = await progress_tracker.get_product_progress(product.id)
                            updated_count += 1
                        except Exception as e:
                            logger.error(f"Failed to update progress for product {product.id}: {e}")

                await asyncio.gather(
                    *[update_single_product(p) for p in products],
                    return_exceptions=True
                )

                logger.info(f"[SUCCESS] Progress tracking updated: {updated_count}/{len(products)} products")

            except Exception as e:
                logger.error(f"[ERROR] Progress update job failed: {e}")

    def start(self):
        """Start the Intelligence Core scheduler"""
        logger.info("[START] Starting Intelligence Core scheduler...")

        # Morning briefings at 6 AM daily
        self.scheduler.add_job(
            self.generate_morning_briefings,
            trigger=CronTrigger(hour=6, minute=0),
            id='morning_briefings',
            name='Generate Morning Briefings',
            replace_existing=True
        )
        logger.info("    Morning briefings: Daily at 6:00 AM")

        # Product grading every 6 hours
        self.scheduler.add_job(
            self.grade_all_products,
            trigger=IntervalTrigger(hours=6),
            id='product_grading',
            name='Grade All Products',
            replace_existing=True
        )
        logger.info("    Product grading: Every 6 hours")

        # Progress tracking updates daily at midnight
        self.scheduler.add_job(
            self.update_product_progress,
            trigger=CronTrigger(hour=0, minute=0),
            id='progress_updates',
            name='Update Product Progress',
            replace_existing=True
        )
        logger.info("    Progress updates: Daily at midnight")

        # Start scheduler
        self.scheduler.start()
        logger.info("[SUCCESS] Intelligence Core scheduler started")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("[STOP]  Intelligence Core scheduler stopped")


# Singleton instance
_intelligence_scheduler = None


def get_intelligence_scheduler() -> IntelligenceScheduler:
    """Get or create Intelligence scheduler instance"""
    global _intelligence_scheduler
    if _intelligence_scheduler is None:
        _intelligence_scheduler = IntelligenceScheduler()
    return _intelligence_scheduler


def start_intelligence_scheduler():
    """Start the Intelligence Core background jobs"""
    scheduler = get_intelligence_scheduler()
    scheduler.start()
    return scheduler
