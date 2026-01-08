"""
SCHEDULER STATUS API ROUTES
===========================

Endpoints for checking scheduler status and running jobs manually.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from ospra_os.core.tiers import SubscriptionTier
from ospra_os.middleware.rate_limiter import check_discovery_rate_limit, record_discovery


router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"])


class ScheduledJobInfo(BaseModel):
    """Information about a scheduled job."""
    id: str
    name: str
    next_run: Optional[str]
    trigger: str
    running: bool = False


class SchedulerStatusResponse(BaseModel):
    """Scheduler status response."""
    running: bool
    jobs: List[ScheduledJobInfo]
    uptime_hours: Optional[float] = None


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """
    Get status of all scheduled background jobs.
    
    Shows:
    - Which jobs are scheduled
    - When they'll next run
    - Whether scheduler is running
    """
    jobs = []
    running = False
    
    # Check Intelligence Scheduler
    try:
        from ospra_os.background_jobs.intelligence_scheduler import get_intelligence_scheduler
        intel_scheduler = get_intelligence_scheduler()
        
        if intel_scheduler and intel_scheduler.scheduler.running:
            running = True
            
            for job in intel_scheduler.scheduler.get_jobs():
                jobs.append(ScheduledJobInfo(
                    id=job.id,
                    name=job.name or job.id,
                    next_run=job.next_run_time.isoformat() if job.next_run_time else None,
                    trigger=str(job.trigger),
                    running=False
                ))
    except Exception as e:
        pass  # Scheduler not initialized
    
    # Check Auto-Discovery Scheduler
    try:
        from ospra_os.background_jobs.scheduler_integration import get_auto_discovery_job
        discovery_job = get_auto_discovery_job()
        
        if discovery_job and discovery_job.scheduler.running:
            running = True
            
            for job in discovery_job.scheduler.get_jobs():
                jobs.append(ScheduledJobInfo(
                    id=job.id,
                    name=job.name or job.id,
                    next_run=job.next_run_time.isoformat() if job.next_run_time else None,
                    trigger=str(job.trigger),
                    running=False
                ))
    except Exception as e:
        pass
    
    # Check Daily Ranking Scheduler
    try:
        from ospra_os.background_jobs.scheduler_integration import get_daily_ranking_job
        ranking_job = get_daily_ranking_job()
        
        if ranking_job and ranking_job.scheduler.running:
            running = True
            
            for job in ranking_job.scheduler.get_jobs():
                jobs.append(ScheduledJobInfo(
                    id=job.id,
                    name=job.name or job.id,
                    next_run=job.next_run_time.isoformat() if job.next_run_time else None,
                    trigger=str(job.trigger),
                    running=False
                ))
    except Exception as e:
        pass
    
    return SchedulerStatusResponse(
        running=running,
        jobs=jobs,
        uptime_hours=None  # Would track from startup time
    )


@router.post("/run/discovery")
async def run_discovery_now(
    user_id: int = 1,
    tier: str = "stratosphere",
    on_demand: bool = True
):
    """
    Manually trigger product discovery.
    
    Respects tier rate limits unless on_demand=True (Stratosphere only).
    """
    try:
        tier_enum = SubscriptionTier(tier.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {tier}")
    
    # Check rate limit
    rate_check = await check_discovery_rate_limit(
        user_id=user_id,
        tier=tier_enum,
        on_demand=on_demand
    )
    
    if not rate_check["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={
                "error": rate_check["error"],
                "retry_after_minutes": rate_check.get("retry_after_minutes"),
                "upgrade_message": rate_check.get("upgrade_message")
            }
        )
    
    # Run discovery
    try:
        from ospra_os.background_jobs.scheduler_integration import get_auto_discovery_job
        discovery_job = get_auto_discovery_job()
        
        if not discovery_job:
            raise HTTPException(
                status_code=503,
                detail="Discovery scheduler not initialized"
            )
        
        # Run for user
        result = await discovery_job.run_discovery_for_user(user_id=user_id)
        
        # Record the request
        record_discovery(user_id)
        
        return {
            "success": True,
            "result": result,
            "triggered_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run/grading")
async def run_product_grading():
    """
    Manually trigger product grading.
    
    Updates AI scores for all products.
    """
    try:
        from ospra_os.background_jobs.intelligence_scheduler import get_intelligence_scheduler
        scheduler = get_intelligence_scheduler()
        
        if not scheduler:
            raise HTTPException(
                status_code=503,
                detail="Intelligence scheduler not initialized"
            )
        
        await scheduler.grade_all_products()
        
        return {
            "success": True,
            "message": "Product grading completed",
            "triggered_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run/briefing")
async def run_morning_briefing(user_id: int = 1):
    """
    Manually trigger morning briefing generation.
    
    Creates AI briefing for specified user.
    """
    try:
        from ospra_os.background_jobs.intelligence_scheduler import get_intelligence_scheduler
        scheduler = get_intelligence_scheduler()
        
        if not scheduler:
            raise HTTPException(
                status_code=503,
                detail="Intelligence scheduler not initialized"
            )
        
        await scheduler.generate_morning_briefings()
        
        return {
            "success": True,
            "message": "Morning briefing generated",
            "user_id": user_id,
            "triggered_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_scheduler_config():
    """
    Get scheduler configuration.
    
    Shows what jobs run and when.
    """
    return {
        "intelligence_jobs": {
            "morning_briefings": "Daily at 6:00 AM",
            "product_grading": "Every 6 hours",
            "progress_updates": "Daily at midnight"
        },
        "discovery_jobs": {
            "auto_discovery": "Configurable (default: every 6 hours)",
            "daily_ranking": "Daily at 3:00 AM"
        },
        "rate_limits": {
            "nest": "3/day, 4-hour intervals",
            "flight": "10/day, 2-hour intervals",
            "soar": "Unlimited, 30-min intervals",
            "stratosphere": "Unlimited, 5-min intervals + on-demand"
        }
    }
