"""
Token Refresh Job for OAuth Integrations
=========================================

Background job that automatically refreshes OAuth tokens before they expire.

Supports:
- AliExpress tokens (30 day expiry, refresh 3 days before)
- Gmail tokens (when implemented)

Runs every 6 hours to check for tokens approaching expiry and refreshes them proactively.

Author: OspraOS
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from ospra_os.database import get_multi_store_session
from ospra_os.aliexpress.oauth import AliExpressOAuth, AliExpressToken

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Refresh tokens this many days before expiry
ALIEXPRESS_REFRESH_BUFFER_DAYS = 3

# How often to check for expiring tokens (hours)
CHECK_INTERVAL_HOURS = 6


# =============================================================================
# TOKEN REFRESH JOB
# =============================================================================

class TokenRefreshJob:
    """
    Background job for automatically refreshing OAuth tokens.

    Proactively refreshes tokens before they expire to prevent
    service interruptions.
    """

    def __init__(self, database_url: str):
        """
        Initialize the token refresh job.

        Args:
            database_url: Database connection string
        """
        self.database_url = database_url
        self.scheduler = BackgroundScheduler()
        self.job_id = "oauth_token_refresh"

        # Track refresh statistics
        self.stats = {
            "last_run": None,
            "tokens_refreshed": 0,
            "tokens_failed": 0,
            "total_runs": 0
        }

        logger.info("TokenRefreshJob initialized")

    def schedule_refresh(self, interval_hours: int = CHECK_INTERVAL_HOURS):
        """
        Schedule the token refresh job to run periodically.

        Args:
            interval_hours: How often to check for expiring tokens (default: 6 hours)
        """
        try:
            # Remove existing job if any
            self.unschedule_refresh()

            # Create interval trigger
            trigger = IntervalTrigger(hours=interval_hours)

            # Schedule the job
            self.scheduler.add_job(
                self._run_token_refresh,
                trigger=trigger,
                id=self.job_id,
                name="OAuth Token Refresh",
                replace_existing=True,
                next_run_time=datetime.now()  # Run immediately on startup
            )

            # Start scheduler if not running
            if not self.scheduler.running:
                self.scheduler.start()

            logger.info(f"[SUCCESS] Token refresh job scheduled to run every {interval_hours} hours")

        except Exception as e:
            logger.error(f"Failed to schedule token refresh job: {e}")

    def unschedule_refresh(self):
        """Remove scheduled token refresh job."""
        try:
            if self.scheduler.get_job(self.job_id):
                self.scheduler.remove_job(self.job_id)
                logger.info("Token refresh job unscheduled")
        except Exception as e:
            logger.warning(f"Error unscheduling token refresh job: {e}")

    def _run_token_refresh(self):
        """
        Internal method that runs the token refresh check.
        Called by scheduler.
        """
        logger.info("[TOKEN] Starting OAuth token refresh check...")

        self.stats["last_run"] = datetime.now(timezone.utc)
        self.stats["total_runs"] += 1

        refreshed = 0
        failed = 0

        try:
            # Refresh AliExpress tokens
            ae_result = self._refresh_aliexpress_tokens()
            refreshed += ae_result.get("refreshed", 0)
            failed += ae_result.get("failed", 0)

            # Future: Add Gmail token refresh here
            # gmail_result = self._refresh_gmail_tokens()
            # refreshed += gmail_result.get("refreshed", 0)
            # failed += gmail_result.get("failed", 0)

            self.stats["tokens_refreshed"] += refreshed
            self.stats["tokens_failed"] += failed

            logger.info(f"[SUCCESS] Token refresh complete: {refreshed} refreshed, {failed} failed")

            return {
                "success": True,
                "tokens_refreshed": refreshed,
                "tokens_failed": failed,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Token refresh job failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def _refresh_aliexpress_tokens(self) -> Dict[str, int]:
        """
        Proactively refresh the platform AliExpress dropship token when it's
        approaching expiry.

        Re-audit M9: the old implementation queried the legacy AliExpressToken
        ORM model, whose columns (is_valid, expires_at) don't physically exist
        in the `aliexpress_tokens` table the OAuth callback actually writes
        (api_type/obtained_at/expires_in schema) — so this job errored on
        every run and was dead code. It now reads the REAL token store and
        delegates to the DS client's signed refresh (single refresh
        implementation, shared with the on-demand self-heal).
        """
        try:
            app_key = os.getenv("ALIEXPRESS_APP_KEY")
            app_secret = os.getenv("ALIEXPRESS_APP_SECRET")
            if not app_key or not app_secret:
                logger.debug("AliExpress OAuth not configured, skipping token refresh")
                return {"refreshed": 0, "failed": 0}

            from ospra_os.database.aliexpress_tokens import load_token
            payload = load_token("dropship")
            if not payload or not payload.get("refresh_token"):
                logger.debug("No dropship refresh_token stored — nothing to refresh")
                return {"refreshed": 0, "failed": 0}
            if not payload.get("needs_refresh") and not payload.get("is_expired"):
                logger.debug("AliExpress dropship token still fresh")
                return {"refreshed": 0, "failed": 0}

            import asyncio as _asyncio
            from ospra_os.aliexpress.ds_client import AliExpressDSClient
            ok = _asyncio.run(AliExpressDSClient()._refresh_token())
            if ok:
                logger.info("[SUCCESS] AliExpress dropship token proactively refreshed")
                return {"refreshed": 1, "failed": 0}
            logger.warning("AliExpress dropship token refresh failed — will retry next cycle")
            return {"refreshed": 0, "failed": 1}

        except Exception as e:
            logger.error(f"AliExpress token refresh check failed: {e}")
            return {"refreshed": 0, "failed": 1}

    def get_expiring_tokens_status(self) -> Dict[str, Any]:
        """
        Get status of tokens approaching expiry.

        Returns:
            Dict with token status information
        """
        try:
            session = get_multi_store_session(self.database_url)
            now = datetime.now(timezone.utc)

            # AliExpress tokens (limit for performance)
            ae_tokens = session.query(AliExpressToken).filter(
                AliExpressToken.is_valid == True
            ).limit(100).all()

            ae_status = []
            for token in ae_tokens:
                time_until_expiry = token.expires_at - now
                days_until_expiry = time_until_expiry.days

                ae_status.append({
                    "id": token.id,
                    "expires_at": token.expires_at.isoformat(),
                    "days_until_expiry": days_until_expiry,
                    "needs_refresh": days_until_expiry <= ALIEXPRESS_REFRESH_BUFFER_DAYS,
                    "has_refresh_token": token.refresh_token is not None
                })

            return {
                "aliexpress": {
                    "total_tokens": len(ae_tokens),
                    "tokens": ae_status
                },
                "refresh_buffer_days": ALIEXPRESS_REFRESH_BUFFER_DAYS,
                "check_interval_hours": CHECK_INTERVAL_HOURS,
                "scheduler_running": self.scheduler.running,
                "stats": self.stats
            }

        except Exception as e:
            logger.error(f"Failed to get token status: {e}")
            return {"error": str(e)}

    def run_refresh_manually(self) -> Dict:
        """
        Manually trigger token refresh (for testing/debugging).

        Returns:
            Result dict with success status and stats
        """
        logger.info("Manual token refresh triggered")
        return self._run_token_refresh()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def start_token_refresh_scheduler(
    database_url: str,
    interval_hours: int = CHECK_INTERVAL_HOURS
) -> TokenRefreshJob:
    """
    Convenience function to create and start token refresh job.

    Args:
        database_url: Database connection string
        interval_hours: How often to check (default: 6 hours)

    Returns:
        TokenRefreshJob instance
    """
    job = TokenRefreshJob(database_url)
    job.schedule_refresh(interval_hours=interval_hours)
    return job


logger.info("[SUCCESS] TokenRefreshJob module loaded")
