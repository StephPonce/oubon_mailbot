"""
API routes for managing background jobs
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from ospra_os.jobs.scheduler import get_scheduler

router = APIRouter(prefix="/api/jobs", tags=["Background Jobs"])


class JobStatus(BaseModel):
    id: str
    name: str
    next_run_time: Optional[str]
    trigger: str


class SchedulerStatus(BaseModel):
    is_running: bool
    total_jobs: int
    jobs: List[JobStatus]


@router.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status():
    """
    Get the current status of the background job scheduler
    """
    scheduler = get_scheduler()
    status = scheduler.get_job_status()

    return SchedulerStatus(
        is_running=status['is_running'],
        total_jobs=status['total_jobs'],
        jobs=[JobStatus(**job) for job in status['jobs']]
    )


@router.post("/start")
async def start_scheduler():
    """
    Start the background job scheduler
    """
    try:
        scheduler = get_scheduler()
        scheduler.start()
        return {"message": "Scheduler started successfully", "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scheduler: {str(e)}")


@router.post("/stop")
async def stop_scheduler():
    """
    Stop the background job scheduler
    """
    try:
        scheduler = get_scheduler()
        scheduler.stop()
        return {"message": "Scheduler stopped successfully", "status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop scheduler: {str(e)}")


@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: str):
    """
    Manually trigger a specific job to run immediately
    """
    scheduler = get_scheduler()

    if not scheduler.is_running:
        raise HTTPException(status_code=400, detail="Scheduler is not running")

    job = scheduler.scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    try:
        # Trigger job immediately
        job.modify(next_run_time=datetime.now())
        return {
            "message": f"Job '{job.name}' scheduled to run immediately",
            "job_id": job_id,
            "job_name": job.name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run job: {str(e)}")


@router.get("/jobs")
async def list_jobs():
    """
    List all configured background jobs
    """
    scheduler = get_scheduler()
    jobs = []

    for job in scheduler.scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
            "pending": job.pending
        })

    return {
        "jobs": jobs,
        "total": len(jobs)
    }
