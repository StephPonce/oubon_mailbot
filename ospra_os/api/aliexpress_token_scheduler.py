"""
Background scheduler for automatic AliExpress token refresh

Runs daily to check if tokens need refreshing.
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from ospra_os.api.aliexpress_token_refresh import refresh_all_tokens

# Create scheduler instance
scheduler = AsyncIOScheduler()


async def scheduled_token_refresh():
    """
    Scheduled task that runs daily to check and refresh tokens
    """
    print("\n" + "=" * 80)
    print(f"[ALARM] SCHEDULED TOKEN REFRESH - {datetime.now().isoformat()}")
    print("=" * 80)

    try:
        results = await refresh_all_tokens()
        print(f"[SUCCESS] Scheduled refresh completed: {results}")
    except Exception as e:
        print(f"[ERROR] Scheduled refresh failed: {e}")
        import traceback
        traceback.print_exc()


def start_token_refresh_scheduler():
    """
    Start the background scheduler for token refresh

    Schedule:
    - Runs daily at 2:00 AM UTC
    - Checks all tokens and refreshes if within 7 days of expiry
    """
    try:
        # Add job to run daily at 2 AM UTC
        scheduler.add_job(
            scheduled_token_refresh,
            trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM UTC daily
            id="aliexpress_token_refresh",
            name="AliExpress Token Refresh",
            replace_existing=True
        )

        # Start the scheduler
        scheduler.start()
        print("[SUCCESS] AliExpress token refresh scheduler started")
        print("   Schedule: Daily at 2:00 AM UTC")
        print("   Refresh window: 7 days before expiry")

    except Exception as e:
        print(f"[ERROR] Failed to start token refresh scheduler: {e}")


def stop_token_refresh_scheduler():
    """Stop the background scheduler"""
    try:
        scheduler.shutdown(wait=False)
        print("[SUCCESS] AliExpress token refresh scheduler stopped")
    except Exception as e:
        print(f"[ERROR] Failed to stop token refresh scheduler: {e}")


async def check_tokens_on_startup():
    """
    Check token status on application startup

    This runs once when the server starts to ensure tokens are valid.
    """
    print("\n" + "=" * 80)
    print("[START] STARTUP TOKEN CHECK")
    print("=" * 80)

    try:
        results = await refresh_all_tokens()
        print(f"[SUCCESS] Startup token check completed: {results}")
    except Exception as e:
        print(f"[ERROR] Startup token check failed: {e}")
        import traceback
        traceback.print_exc()
