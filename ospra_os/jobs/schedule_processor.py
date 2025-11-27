"""
Background job for processing ad schedules
"""
import asyncio
from datetime import datetime
from ospra_os.services.schedule_manager import ScheduleManager
from ospra_os.core.settings import get_settings


async def process_schedules():
    """
    Background job that runs every 5 minutes
    Activates pending schedules and completes expired ones
    """
    print(f"\n{'='*70}")
    print(f"⏰ SCHEDULE PROCESSOR - {datetime.utcnow().isoformat()}")
    print(f"{'='*70}\n")

    settings = get_settings()
    manager = ScheduleManager(settings.database_url)

    try:
        # Activate pending schedules
        activated = await manager.process_pending_schedules()

        if activated:
            print(f"\n✅ Activated {len(activated)} schedules")

        # Complete expired schedules
        expired = await manager.check_expired_schedules()

        if expired:
            print(f"\n✅ Completed {len(expired)} expired schedules")

        if not activated and not expired:
            print("   No schedules to process")

    except Exception as e:
        print(f"❌ Schedule processor error: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*70}\n")


async def schedule_processor_loop():
    """Run schedule processor in loop"""
    while True:
        await process_schedules()

        # Wait 5 minutes
        await asyncio.sleep(300)


# Start background job on app startup
def start_schedule_processor():
    """Start the schedule processor in background"""
    asyncio.create_task(schedule_processor_loop())
