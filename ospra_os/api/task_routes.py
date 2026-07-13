"""
Task Monitoring API - GROK RECOMMENDATION #13

FastAPI endpoints for monitoring and managing Celery tasks.

Endpoints:
- GET /api/tasks/status/{task_id} - Get task status
- GET /api/tasks/active - List active tasks
- GET /api/tasks/scheduled - List scheduled tasks
- POST /api/tasks/revoke/{task_id} - Cancel task
- GET /api/tasks/stats - Get worker statistics
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel

from ospra_os.celery_app import celery_app
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User, get_db
from ospra_os.tenancy.context import TenantContext
from ospra_os.observability.posthog_client import capture as posthog_capture, FunnelEvent
from ospra_os.api.schemas import (
    TaskStatusResponse,
    ActiveTaskResponse,
    ScheduledTaskResponse,
    RevokeTaskResponse,
    TaskTriggerResponse,
    WorkerStatsResponse,
    QueueStatsResponse,
    BeatScheduleItem,
    BeatScheduleResponse,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ==================== ENDPOINTS ====================

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get status of a specific task.

    Returns:
    - Task state (PENDING, STARTED, SUCCESS, FAILURE, RETRY)
    - Result if completed
    - Error message if failed
    - Progress information if available
    """
    try:
        result = celery_app.AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "status": result.state,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "failed": result.failed() if result.ready() else None,
            "result": None,
            "error": None
        }

        if result.ready():
            if result.successful():
                response["result"] = result.result
            elif result.failed():
                response["error"] = str(result.info)

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving task status. Please try again."
        )


@router.get("/active", response_model=List[ActiveTaskResponse])
def get_active_tasks(
    user: User = Depends(get_current_user)
):
    """
    Get list of currently active tasks across all workers.

    Returns:
    - Task ID
    - Task name
    - Arguments
    - Worker name
    """
    try:
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()

        if not active_tasks:
            return []

        # Flatten tasks from all workers
        all_tasks = []
        for worker_name, tasks in active_tasks.items():
            for task in tasks:
                all_tasks.append({
                    "task_id": task["id"],
                    "name": task["name"],
                    "args": task.get("args", []),
                    "kwargs": task.get("kwargs", {}),
                    "worker": worker_name
                })

        return all_tasks

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving active tasks. Please try again."
        )


@router.get("/scheduled", response_model=List[ScheduledTaskResponse])
def get_scheduled_tasks(
    user: User = Depends(get_current_user)
):
    """
    Get list of scheduled (queued but not yet running) tasks.
    """
    try:
        inspect = celery_app.control.inspect()
        scheduled_tasks = inspect.scheduled()

        if not scheduled_tasks:
            return []

        # Flatten tasks from all workers
        all_scheduled = []
        for worker_name, tasks in scheduled_tasks.items():
            for task in tasks:
                all_scheduled.append({
                    "task_id": task["request"]["id"],
                    "name": task["request"]["name"],
                    "eta": task.get("eta"),
                    "worker": worker_name
                })

        return all_scheduled

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving scheduled tasks. Please try again."
        )


@router.post("/revoke/{task_id}", response_model=RevokeTaskResponse)
def revoke_task(
    task_id: str,
    terminate: bool = False,
    user: User = Depends(get_current_user)
):
    """
    Cancel a running or pending task.

    Args:
        task_id: Task ID to cancel
        terminate: If True, terminate running task immediately
                  If False, prevent task from starting (if not started)

    Returns:
        Confirmation message
    """
    try:
        celery_app.control.revoke(task_id, terminate=terminate)

        return {
            "status": "revoked",
            "task_id": task_id,
            "terminated": terminate,
            "message": f"Task {task_id} has been {'terminated' if terminate else 'revoked'}"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error revoking task. Please try again."
        )


@router.get("/stats", response_model=List[WorkerStatsResponse])
def get_worker_stats(
    user: User = Depends(get_current_user)
):
    """
    Get statistics for all Celery workers.

    Returns:
    - Worker name
    - Status (online/offline)
    - Number of active tasks
    - Number of processed tasks
    """
    try:
        inspect = celery_app.control.inspect()

        # Get worker stats
        stats = inspect.stats()
        active = inspect.active()

        if not stats:
            return []

        worker_list = []
        for worker_name, worker_stats in stats.items():
            active_count = len(active.get(worker_name, [])) if active else 0

            worker_list.append({
                "worker_name": worker_name,
                "status": "online",
                "active_tasks": active_count,
                "processed_tasks": worker_stats.get("total", {}).get("ospra.tasks", 0)
            })

        return worker_list

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving worker stats. Please try again."
        )


@router.get("/queues", response_model=QueueStatsResponse)
def get_queue_stats(
    user: User = Depends(get_current_user)
):
    """
    Get statistics about task queues.

    Returns queue lengths for:
    - high_priority
    - default
    - low_priority
    - scheduled
    """
    try:
        # Note: This requires additional monitoring setup
        # For now, return placeholder
        return {
            "high_priority": 0,
            "default": 0,
            "low_priority": 0,
            "scheduled": 0,
            "message": "Queue monitoring requires additional setup (Redis keys inspection)"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving queue stats. Please try again."
        )


@router.get("/beat-schedule", response_model=List[BeatScheduleItem])
def get_beat_schedule(
    user: User = Depends(get_current_user)
):
    """
    Get list of scheduled periodic tasks from Celery Beat.

    Returns:
    - Task name
    - Schedule (cron or interval)
    - Last run time
    - Next run time
    """
    try:
        schedule = celery_app.conf.beat_schedule

        schedule_list = []
        for task_name, task_config in schedule.items():
            schedule_list.append({
                "name": task_name,
                "task": task_config["task"],
                "schedule": str(task_config["schedule"]),
                "options": task_config.get("options", {})
            })

        return schedule_list

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving beat schedule. Please try again."
        )


# ==================== TASK TRIGGER ENDPOINTS ====================
#
# T33: every trigger below used to accept a client-supplied user_id/store_id
# and act on it — an authenticated user could run discovery, analysis, or
# daily-brief emails AS ANY OTHER USER, sync any store, and /trigger/send-email
# accepted arbitrary to/subject/body (an authenticated open mail relay on our
# domain). All identity now comes from the JWT; store access is verified with
# the canonical TenantContext.can_access_store ownership check.

@router.post("/trigger/discover-products", response_model=TaskTriggerResponse)
def trigger_product_discovery(
    user: User = Depends(get_current_user)
):
    """Manually trigger product discovery for the CALLING user (T33)."""
    try:
        from ospra_os.tasks.product_tasks import discover_products_for_user

        result = discover_products_for_user.delay(user.id)

        posthog_capture(
            user.id,
            FunnelEvent.FIRST_DISCOVERY,
            properties={"target_user_id": user.id},
        )

        return {
            "task_id": result.id,
            "status": "queued",
            "message": "Product discovery queued",
            "track_at": f"/api/tasks/status/{result.id}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error triggering product discovery. Please try again."
        )


@router.post("/trigger/sync-store", response_model=TaskTriggerResponse)
def trigger_store_sync(
    store_id: int,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Manually trigger Shopify store sync.

    T33: verifies the caller OWNS store_id (TenantContext.can_access_store)
    before queueing. 404 covers both missing and not-yours.
    """
    tenant = TenantContext(tenant_id=user.id, user_id=user.id)
    if not tenant.can_access_store(store_id, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Store not found")
    try:
        from ospra_os.tasks.sync_tasks import sync_shopify_products

        result = sync_shopify_products.delay(store_id)

        return {
            "task_id": result.id,
            "status": "queued",
            "message": f"Store sync queued for store {store_id}",
            "track_at": f"/api/tasks/status/{result.id}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error triggering store sync. Please try again."
        )


@router.post("/trigger/send-email", response_model=TaskTriggerResponse)
def trigger_email_send(
    subject: str,
    body: str,
    user: User = Depends(get_current_user)
):
    """Send a test email to YOURSELF.

    T33: the recipient is always the authenticated user's own address. The
    old form accepted arbitrary to/subject/body — an authenticated open mail
    relay that could spam anyone from our domain.
    """
    try:
        from ospra_os.tasks.email_tasks import send_email

        result = send_email.delay(user.email, subject, body)

        return {
            "task_id": result.id,
            "status": "queued",
            "message": f"Email send queued to {user.email}",
            "track_at": f"/api/tasks/status/{result.id}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error triggering email send. Please try again."
        )


@router.post("/trigger/analyze-performance", response_model=TaskTriggerResponse)
def trigger_performance_analysis(
    user: User = Depends(get_current_user)
):
    """Manually trigger performance analysis for the CALLING user (T33)."""
    try:
        from ospra_os.tasks.analytics_tasks import generate_analytics_report

        result = generate_analytics_report.delay(user.id)

        return {
            "task_id": result.id,
            "status": "queued",
            "message": "Performance analysis queued",
            "track_at": f"/api/tasks/status/{result.id}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error triggering performance analysis. Please try again."
        )


@router.post("/trigger/daily-brief", response_model=TaskTriggerResponse)
def trigger_daily_brief(
    user: User = Depends(get_current_user)
):
    """Manually trigger the daily brief email for the CALLING user (T33)."""
    try:
        from ospra_os.tasks.email_tasks import send_daily_brief_to_user

        result = send_daily_brief_to_user.delay(user.id)

        return {
            "task_id": result.id,
            "status": "queued",
            "message": "Daily brief queued",
            "track_at": f"/api/tasks/status/{result.id}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error triggering daily brief. Please try again."
        )
