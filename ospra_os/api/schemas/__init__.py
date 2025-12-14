"""
API Response Schemas
====================

Centralized response models for all API endpoints.

Usage:
    from ospra_os.api.schemas import TemplateResponse, TaskStatusResponse
    from ospra_os.api.schemas.common import SuccessResponse
"""

# Common schemas
from .common import (
    SuccessResponse,
    ErrorResponse,
    StatusResponse,
    PaginatedResponse,
    CountResponse,
    PercentageResponse,
    IdResponse,
    IdsResponse,
    CategoryOption,
    CategoriesResponse,
)

# Template schemas
from .templates import (
    TemplateResponse,
    TemplateDetailResponse,
    TemplateBrowseResponse,
    TemplateFeaturedResponse,
    TemplateSubmitResponse,
    TemplateUsageResponse,
    TemplatePurchaseResponse,
    TemplateReviewResponse,
    TemplateCategoryOption,
    TemplateCategoriesResponse,
    TemplateStatsResponse,
)

# Task schemas
from .tasks import (
    TaskStatusResponse,
    ActiveTaskResponse,
    ScheduledTaskResponse,
    ActiveTasksListResponse,
    ScheduledTasksListResponse,
    RevokeTaskResponse,
    TaskTriggerResponse,
    WorkerStatsResponse,
    WorkerStatsListResponse,
    QueueStatsResponse,
    BeatScheduleItem,
    BeatScheduleResponse,
)


__all__ = [
    # Common
    "SuccessResponse",
    "ErrorResponse",
    "StatusResponse",
    "PaginatedResponse",
    "CountResponse",
    "PercentageResponse",
    "IdResponse",
    "IdsResponse",
    "CategoryOption",
    "CategoriesResponse",
    # Templates
    "TemplateResponse",
    "TemplateDetailResponse",
    "TemplateBrowseResponse",
    "TemplateFeaturedResponse",
    "TemplateSubmitResponse",
    "TemplateUsageResponse",
    "TemplatePurchaseResponse",
    "TemplateReviewResponse",
    "TemplateCategoryOption",
    "TemplateCategoriesResponse",
    "TemplateStatsResponse",
    # Tasks
    "TaskStatusResponse",
    "ActiveTaskResponse",
    "ScheduledTaskResponse",
    "ActiveTasksListResponse",
    "ScheduledTasksListResponse",
    "RevokeTaskResponse",
    "TaskTriggerResponse",
    "WorkerStatsResponse",
    "WorkerStatsListResponse",
    "QueueStatsResponse",
    "BeatScheduleItem",
    "BeatScheduleResponse",
]
