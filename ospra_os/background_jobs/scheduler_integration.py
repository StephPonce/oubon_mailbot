"""
Scheduler Integration for FastAPI

Example integration of AutoDiscoveryJob with FastAPI application.
Shows how to start/stop background jobs with the app lifecycle.

Usage:
    from ospra_os.background_jobs.scheduler_integration import setup_background_jobs

    # In FastAPI app startup
    @app.on_event("startup")
    async def startup():
        await setup_background_jobs(app)

Author: OspraOS
Date: November 2025
"""

import logging
from typing import Optional
from fastapi import FastAPI

from ospra_os.background_jobs.auto_discovery import AutoDiscoveryJob
from ospra_os.background_jobs.daily_ranking_job import DailyRankingJob
from ospra_os.core.settings import get_settings

logger = logging.getLogger(__name__)


# Global scheduler instances
_auto_discovery_job: Optional[AutoDiscoveryJob] = None
_daily_ranking_job: Optional[DailyRankingJob] = None


async def setup_background_jobs(app: FastAPI):
    """
    Setup and start background jobs when FastAPI app starts.

    Args:
        app: FastAPI application instance
    """
    global _auto_discovery_job

    try:
        logger.info("Setting up background jobs...")

        # Get settings
        settings = get_settings()

        # Check if auto-discovery is enabled in environment
        if not getattr(settings, 'AUTO_DISCOVERY_ENABLED', True):
            logger.info("Auto-discovery disabled in settings")
            return

        # Get database URL
        database_url = getattr(settings, 'DATABASE_URL', None)
        if not database_url:
            logger.warning("No DATABASE_URL configured, skipping auto-discovery setup")
            return

        # Create auto-discovery job
        _auto_discovery_job = AutoDiscoveryJob(database_url=database_url)

        # Get schedule settings
        discovery_hour = getattr(settings, 'DISCOVERY_HOUR', 3)  # 3 AM default
        discovery_interval_hours = getattr(settings, 'DISCOVERY_INTERVAL_HOURS', None)

        # Schedule the job
        _auto_discovery_job.schedule_discovery(
            hour=discovery_hour,
            interval_hours=discovery_interval_hours
        )

        # Store in app state for access in routes
        app.state.auto_discovery_job = _auto_discovery_job

        # === Setup Daily Ranking Job ===
        logger.info("Setting up daily ranking job...")

        global _daily_ranking_job
        _daily_ranking_job = DailyRankingJob(database_url=database_url)

        # Get ranking schedule settings (default 3 AM)
        ranking_hour = getattr(settings, 'RANKING_HOUR', 3)
        ranking_minute = getattr(settings, 'RANKING_MINUTE', 0)

        # Schedule the ranking job
        _daily_ranking_job.schedule_rankings(hour=ranking_hour, minute=ranking_minute)

        # Store in app state
        app.state.daily_ranking_job = _daily_ranking_job

        logger.info("[SUCCESS] Background jobs setup complete")

    except Exception as e:
        logger.error(f"Failed to setup background jobs: {e}")
        # Don't crash the app if background jobs fail to start
        logger.warning("App will continue without background jobs")


async def shutdown_background_jobs(app: FastAPI):
    """
    Shutdown background jobs when FastAPI app stops.

    Args:
        app: FastAPI application instance
    """
    global _auto_discovery_job, _daily_ranking_job

    try:
        logger.info("Shutting down background jobs...")

        if _auto_discovery_job:
            # Unschedule all jobs
            _auto_discovery_job.unschedule_discovery()

            # Shutdown scheduler
            if _auto_discovery_job.scheduler.running:
                _auto_discovery_job.scheduler.shutdown(wait=True)

            _auto_discovery_job = None

        if _daily_ranking_job:
            # Unschedule ranking job
            _daily_ranking_job.unschedule_rankings()

            # Shutdown scheduler
            if _daily_ranking_job.scheduler.running:
                _daily_ranking_job.scheduler.shutdown(wait=True)

            _daily_ranking_job = None

        logger.info("[SUCCESS] Background jobs shutdown complete")

    except Exception as e:
        logger.error(f"Error during background jobs shutdown: {e}")


def get_auto_discovery_job() -> Optional[AutoDiscoveryJob]:
    """
    Get the global auto-discovery job instance.

    Returns:
        AutoDiscoveryJob instance or None if not initialized
    """
    return _auto_discovery_job


def get_daily_ranking_job() -> Optional[DailyRankingJob]:
    """
    Get the global daily ranking job instance.

    Returns:
        DailyRankingJob instance or None if not initialized
    """
    return _daily_ranking_job


# FastAPI integration example
async def fastapi_integration_example():
    """
    Example of how to integrate with FastAPI app.

    Add to your main FastAPI application:

    ```python
    from fastapi import FastAPI
    from ospra_os.background_jobs.scheduler_integration import (
        setup_background_jobs,
        shutdown_background_jobs
    )

    app = FastAPI()

    @app.on_event("startup")
    async def startup():
        await setup_background_jobs(app)

    @app.on_event("shutdown")
    async def shutdown():
        await shutdown_background_jobs(app)
    ```
    """
    pass


# Manual control example
async def manual_control_example():
    """
    Example of manual control without FastAPI.

    ```python
    from ospra_os.background_jobs import start_auto_discovery_scheduler

    # Start scheduler (runs daily at 3 AM)
    job = start_auto_discovery_scheduler(
        database_url="postgresql://..."
    )

    # Or run every 12 hours
    job = start_auto_discovery_scheduler(
        database_url="postgresql://...",
        interval_hours=12
    )

    # Run discovery manually for specific user
    result = await job.run_discovery_for_user(user_id=123)

    # Run discovery for all users
    results = await job.run_discovery_for_all_users()

    # Get statistics
    stats = job.get_discovery_stats(user_id=123, days=30)

    # Stop scheduler
    job.unschedule_discovery()
    ```
    """
    pass
