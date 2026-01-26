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
        logger.info("[SUCCESS] AutoDeployJob initialized")

    async def run_check(self):
        """
        Run auto-deployment check.
        Called by scheduler every hour.
        """
        try:
            logger.info("")
            logger.info("=" * 70)
            logger.info(f"[AI] AUTO-DEPLOY JOB: Starting at {datetime.now()}")
            logger.info("=" * 70)

            result = await self.deployer.check_and_deploy()

            if result.get("success"):
                deployed = result.get("deployed", 0)
                if deployed > 0:
                    logger.info(f"[SUCCESS] Auto-deploy job completed: {deployed} products deployed")
                else:
                    logger.info(f"[INFO]  Auto-deploy job completed: {result.get('reason', 'No action taken')}")
            else:
                logger.warning(f"[WARNING]  Auto-deploy job completed with issues: {result.get('reason', 'Unknown')}")

            logger.info("=" * 70)
            return result

        except Exception as e:
            # Log full error details server-side only (not to stdout)
            import traceback
            logger.error(f"[ERROR] Auto-deploy job failed: {e}\n{traceback.format_exc()}")
            return {"success": False, "error": "Auto-deploy job failed"}

    def start(self):
        """Start the scheduler"""
        import os

        # Skip scheduler in test mode to avoid event loop conflicts
        if os.getenv("APP_ENV") == "testing":
            logger.debug("[TEST] Skipping auto-deploy scheduler in test mode")
            return

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
            logger.info("[SUCCESS] Auto-deploy scheduler started (runs every hour)")

            # Log next run time
            job = self.scheduler.get_job("auto_deploy_hourly_check")
            if job and job.next_run_time:
                logger.info(f"    Next auto-deploy check: {job.next_run_time}")

        except (RuntimeError, Exception) as e:
            # Silently handle event loop errors in test environments
            if "Event loop is closed" in str(e) or "no running event loop" in str(e).lower():
                logger.debug(f"[WARNING]  Scheduler not started (event loop unavailable): {e}")
            else:
                logger.error(f"[ERROR] Failed to start auto-deploy scheduler: {e}")

    def stop(self):
        """Stop the scheduler"""
        try:
            self.scheduler.shutdown()
            logger.info("[PAUSE]  Auto-deploy scheduler stopped")
        except Exception as e:
            logger.error(f"[ERROR] Failed to stop auto-deploy scheduler: {e}")


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
