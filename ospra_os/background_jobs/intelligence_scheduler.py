"""
INTELLIGENCE CORE BACKGROUND JOBS

Schedules:
- Morning briefings (6 AM daily)
- Product grading (every 6 hours)
- Progress tracking updates (daily)
"""

import logging
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from ospra_os.database.multi_store_models import get_db, SessionLocal
from ospra_os.intelligence.briefing_engine import get_briefing_engine
from ospra_os.intelligence.grade_reasoning import get_grade_reasoning_engine
from ospra_os.intelligence.progress_flow import get_progress_tracker

logger = logging.getLogger(__name__)


class IntelligenceScheduler:
    """Manages background jobs for Intelligence Core"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.db: Session = SessionLocal()

    async def generate_morning_briefings(self):
        """Generate morning briefings for all users at 6 AM"""
        logger.info("🌅 Generating morning briefings for all users...")

        try:
            briefing_engine = get_briefing_engine(self.db)

            # For now, generate briefing for default user (user_id=1)
            # In production, iterate through all active users
            briefing = await briefing_engine.generate_morning_briefing(user_id=1)

            logger.info(f"✅ Morning briefing generated: {len(briefing.get('briefing_text', ''))} chars")

            # TODO: Send notification/email with briefing
            # await send_briefing_notification(user_id=1, briefing=briefing)

        except Exception as e:
            logger.error(f"❌ Failed to generate morning briefings: {e}")

    async def grade_all_products(self):
        """Grade all products for intelligence scoring"""
        logger.info("📊 Starting product grading job...")

        try:
            from ospra_os.database.multi_store_models import Product

            grade_engine = get_grade_reasoning_engine(self.db)

            # Get all products that need grading
            products = self.db.query(Product).filter(Product.status != "discontinued").all()

            graded_count = 0
            for product in products:
                try:
                    grade_data = await grade_engine.calculate_product_grade(product.id)

                    # Update product with grade
                    product.grade = grade_data['grade']
                    graded_count += 1

                except Exception as e:
                    logger.error(f"Failed to grade product {product.id}: {e}")
                    continue

            self.db.commit()
            logger.info(f"✅ Product grading complete: {graded_count}/{len(products)} products graded")

        except Exception as e:
            logger.error(f"❌ Product grading job failed: {e}")
            self.db.rollback()

    async def update_product_progress(self):
        """Update product lifecycle progress for all products"""
        logger.info("🔄 Updating product progress tracking...")

        try:
            from ospra_os.database.multi_store_models import Product

            progress_tracker = get_progress_tracker(self.db)

            # Get all active products
            products = self.db.query(Product).filter(Product.status != "discontinued").all()

            updated_count = 0
            for product in products:
                try:
                    progress_data = await progress_tracker.get_product_progress(product.id)

                    # Check if product should advance to next stage
                    # Auto-advancement logic would go here

                    updated_count += 1

                except Exception as e:
                    logger.error(f"Failed to update progress for product {product.id}: {e}")
                    continue

            logger.info(f"✅ Progress tracking updated: {updated_count}/{len(products)} products")

        except Exception as e:
            logger.error(f"❌ Progress update job failed: {e}")

    def start(self):
        """Start the Intelligence Core scheduler"""
        logger.info("🚀 Starting Intelligence Core scheduler...")

        # Morning briefings at 6 AM daily
        self.scheduler.add_job(
            self.generate_morning_briefings,
            trigger=CronTrigger(hour=6, minute=0),
            id='morning_briefings',
            name='Generate Morning Briefings',
            replace_existing=True
        )
        logger.info("   📅 Morning briefings: Daily at 6:00 AM")

        # Product grading every 6 hours
        self.scheduler.add_job(
            self.grade_all_products,
            trigger=IntervalTrigger(hours=6),
            id='product_grading',
            name='Grade All Products',
            replace_existing=True
        )
        logger.info("   📅 Product grading: Every 6 hours")

        # Progress tracking updates daily at midnight
        self.scheduler.add_job(
            self.update_product_progress,
            trigger=CronTrigger(hour=0, minute=0),
            id='progress_updates',
            name='Update Product Progress',
            replace_existing=True
        )
        logger.info("   📅 Progress updates: Daily at midnight")

        # Start scheduler
        self.scheduler.start()
        logger.info("✅ Intelligence Core scheduler started")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("⏹️  Intelligence Core scheduler stopped")


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
