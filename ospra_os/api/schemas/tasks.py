"""
Task Monitoring API Response Schemas
=====================================

Response models for Celery task monitoring and management endpoints.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel


# ============================================================================
# TASK STATUS RESPONSES
# ============================================================================

class TaskStatusResponse(BaseModel):
    """Task status information"""
    task_id: str
    status: str
    ready: bool
    successful: Optional[bool]
    failed: Optional[bool]
    result: Optional[Any]
    error: Optional[str]


class ActiveTaskResponse(BaseModel):
    """Active task information"""
    task_id: str
    name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    worker: str


class ScheduledTaskResponse(BaseModel):
    """Scheduled task information"""
    task_id: str
    name: str
    eta: Optional[str] = None
    worker: str


class ActiveTasksListResponse(BaseModel):
    """List of active tasks"""
    tasks: List[ActiveTaskResponse]
    count: int


class ScheduledTasksListResponse(BaseModel):
    """List of scheduled tasks"""
    tasks: List[ScheduledTaskResponse]
    count: int


# ============================================================================
# TASK OPERATIONS
# ============================================================================

class RevokeTaskResponse(BaseModel):
    """Response after revoking a task"""
    status: str
    task_id: str
    terminated: bool
    message: str


class TaskTriggerResponse(BaseModel):
    """Response after triggering a task"""
    task_id: str
    status: str
    message: str
    track_at: str


# ============================================================================
# WORKER STATS
# ============================================================================

class WorkerStatsResponse(BaseModel):
    """Worker statistics"""
    worker_name: str
    status: str
    active_tasks: int
    processed_tasks: int


class WorkerStatsListResponse(BaseModel):
    """List of worker statistics"""
    workers: List[WorkerStatsResponse]
    total_workers: int


# ============================================================================
# QUEUE STATS
# ============================================================================

class QueueStatsResponse(BaseModel):
    """Task queue statistics"""
    high_priority: int
    default: int
    low_priority: int
    scheduled: int
    message: Optional[str] = None


# ============================================================================
# BEAT SCHEDULE
# ============================================================================

class BeatScheduleItem(BaseModel):
    """Celery Beat scheduled task"""
    name: str
    task: str
    schedule: str
    options: Dict[str, Any] = {}


class BeatScheduleResponse(BaseModel):
    """List of Celery Beat scheduled tasks"""
    schedule: List[BeatScheduleItem]
    count: int
