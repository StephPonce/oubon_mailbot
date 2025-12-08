"""
Auto-Deployment Background Job

Scheduled job that runs hourly to check for high-scoring products
and auto-deploy them to Shopify.

Schedule: Every hour (configurable)
Safety: Only runs if explicitly enabled by admin

Author: OspraOS
Date: December 2025
"""

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

from ospra_os.services.auto_deployer import AutoDeployer

logger = logging.getLogger(__name__)


class AutoDeployJob:
    """Background job for automated product deployment"""

    def __init__(self):
        self.deployer = AutoDeployer()
        self.scheduler = AsyncIOScheduler()
        logger.info("✅ AutoDeployJob initialized")

    async def run_check(self):
        """
        Run auto-deployment check.
        Called by scheduler every hour.
        """
        try:
            logger.info("")
            logger.info("=" * 70)
            logger.info(f"🤖 AUTO-DEPLOY JOB: Starting at {datetime.now()}")
            logger.info("=" * 70)

            result = await self.deployer.check_and_deploy()

            if result.get("success"):
                deployed = result.get("deployed", 0)
                if deployed > 0:
                    logger.info(f"✅ Auto-deploy job completed: {deployed} products deployed")
                else:
                    logger.info(f"ℹ️  Auto-deploy job completed: {result.get('reason', 'No action taken')}")
            else:
                logger.warning(f"⚠️  Auto-deploy job completed with issues: {result.get('reason', 'Unknown')}")

            logger.info("=" * 70)
            return result

        except Exception as e:
            logger.error(f"❌ Auto-deploy job failed: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def start(self):
        """Start the scheduler"""
        try:
            # Schedule auto-deploy check to run every hour
            self.scheduler.add_job(
                self.run_check,
                trigger="interval",
                hours=1,  # Run every hour
                id="auto_deploy_hourly_check",
                name="Auto-Deploy Hourly Check",
                replace_existing=True,
                max_instances=1  # Prevent overlapping runs
            )

            self.scheduler.start()
            logger.info("✅ Auto-deploy scheduler started (runs every hour)")

            # Log next run time
            job = self.scheduler.get_job("auto_deploy_hourly_check")
            if job and job.next_run_time:
                logger.info(f"   📅 Next auto-deploy check: {job.next_run_time}")

        except Exception as e:
            logger.error(f"❌ Failed to start auto-deploy scheduler: {e}")

    def stop(self):
        """Stop the scheduler"""
        try:
            self.scheduler.shutdown()
            logger.info("⏸️  Auto-deploy scheduler stopped")
        except Exception as e:
            logger.error(f"❌ Failed to stop auto-deploy scheduler: {e}")


# Global instance
_auto_deploy_job = None


def get_auto_deploy_job() -> AutoDeployJob:
    """Get or create auto-deploy job singleton"""
    global _auto_deploy_job
    if _auto_deploy_job is None:
        _auto_deploy_job = AutoDeployJob()
    return _auto_deploy_job


def start_auto_deploy_scheduler():
    """Start the auto-deploy background scheduler"""
    job = get_auto_deploy_job()
    job.start()
    return job
