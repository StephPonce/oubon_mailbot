"""
Auto-Pilot API Routes

API endpoints for managing autonomous action execution.
Implements GROK RECOMMENDATION #7: Auto-Pilot Mode Toggle.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

from ospra_os.database import (
    User, UserSettings, AutoPilotLog, get_db
)
from ospra_os.database.action_models import Action
from ospra_os.actions.auto_pilot import AutoPilotEngine
from ospra_os.auth.jwt_auth import get_current_user

router = APIRouter(prefix="/api/auto-pilot", tags=["auto-pilot"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AutoPilotStatusResponse(BaseModel):
    """Auto-pilot status and statistics"""
    enabled: bool
    threshold: float
    today: Dict[str, int]
    week: Dict[str, int]
    skip_breakdown: Dict[str, int]
    settings: Dict[str, Any]


class ToggleAutoPilotRequest(BaseModel):
    """Request to enable/disable auto-pilot"""
    enabled: bool


class UpdateSettingsRequest(BaseModel):
    """Request to update auto-pilot settings.

    SECURITY: All numeric fields have bounded ranges.
    """
    auto_pilot_threshold: Optional[float] = Field(None, ge=0, le=100)
    daily_auto_execute_limit: Optional[int] = Field(None, ge=0, le=100)
    max_auto_spend: Optional[float] = Field(None, ge=0, le=100000, description="Max $100,000 auto-spend limit")
    notify_on_auto_execute: Optional[bool] = None
    daily_summary_email: Optional[bool] = None


class UpdateActionRuleRequest(BaseModel):
    """Request to update rules for a specific action type"""
    enabled: bool
    threshold: Optional[float] = Field(None, ge=0, le=100)


class AutoPilotLogResponse(BaseModel):
    """Auto-pilot decision log entry"""
    id: int
    action_id: int
    action_title: str
    action_type: str
    confidence: float
    threshold_used: float
    executed: bool
    skipped_reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/status", response_model=AutoPilotStatusResponse)
async def get_auto_pilot_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current auto-pilot status, settings, and statistics.

    Returns:
    - enabled: Whether auto-pilot is currently active
    - threshold: Global confidence threshold
    - today: Today's execution stats (executed, skipped, remaining_limit)
    - week: Weekly execution count
    - skip_breakdown: Count of actions skipped by reason
    - settings: Full settings object
    """
    engine = AutoPilotEngine(db=db, user_id=current_user.id)
    stats = engine.get_stats()

    # Add full settings to response
    settings_dict = {
        "auto_pilot_enabled": engine.settings.auto_pilot_enabled,
        "auto_pilot_threshold": engine.settings.auto_pilot_threshold,
        "auto_pilot_rules": engine.settings.auto_pilot_rules or {},
        "notify_on_auto_execute": engine.settings.notify_on_auto_execute,
        "daily_summary_email": engine.settings.daily_summary_email,
        "daily_auto_execute_limit": engine.settings.daily_auto_execute_limit,
        "max_auto_spend": engine.settings.max_auto_spend
    }

    return {
        **stats,
        "settings": settings_dict
    }


@router.post("/toggle")
async def toggle_auto_pilot(
    request: ToggleAutoPilotRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enable or disable auto-pilot mode.

    Body:
    - enabled: true to enable, false to disable

    Returns:
    - message: Confirmation message
    - enabled: New enabled state
    """
    # Get or create settings
    settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()

    if not settings:
        settings = UserSettings(
            user_id=current_user.id,
            auto_pilot_enabled=request.enabled,
            auto_pilot_threshold=85.0,
            auto_pilot_rules={},
            daily_auto_execute_limit=20,
            max_auto_spend=500.0
        )
        db.add(settings)
    else:
        settings.auto_pilot_enabled = request.enabled
        settings.updated_at = datetime.utcnow()

    db.commit()

    status = "enabled" if request.enabled else "disabled"

    return {
        "success": True,
        "message": f"Auto-pilot {status} successfully",
        "enabled": request.enabled
    }


@router.put("/settings")
async def update_auto_pilot_settings(
    request: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update auto-pilot settings (threshold, limits, notifications).

    Body (all optional):
    - auto_pilot_threshold: Global confidence threshold (0-100)
    - daily_auto_execute_limit: Max actions per day (0-100)
    - max_auto_spend: Max $ spend per day
    - notify_on_auto_execute: Notify when action auto-executes
    - daily_summary_email: Send daily summary email

    Returns:
    - message: Confirmation message
    - settings: Updated settings object
    """
    # Get or create settings
    settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()

    if not settings:
        settings = UserSettings(
            user_id=current_user.id,
            auto_pilot_enabled=False,
            auto_pilot_threshold=85.0,
            auto_pilot_rules={},
            daily_auto_execute_limit=20,
            max_auto_spend=500.0
        )
        db.add(settings)

    # Update fields if provided
    if request.auto_pilot_threshold is not None:
        settings.auto_pilot_threshold = request.auto_pilot_threshold

    if request.daily_auto_execute_limit is not None:
        settings.daily_auto_execute_limit = request.daily_auto_execute_limit

    if request.max_auto_spend is not None:
        settings.max_auto_spend = request.max_auto_spend

    if request.notify_on_auto_execute is not None:
        settings.notify_on_auto_execute = request.notify_on_auto_execute

    if request.daily_summary_email is not None:
        settings.daily_summary_email = request.daily_summary_email

    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)

    return {
        "success": True,
        "message": "Auto-pilot settings updated successfully",
        "settings": {
            "auto_pilot_threshold": settings.auto_pilot_threshold,
            "daily_auto_execute_limit": settings.daily_auto_execute_limit,
            "max_auto_spend": settings.max_auto_spend,
            "notify_on_auto_execute": settings.notify_on_auto_execute,
            "daily_summary_email": settings.daily_summary_email
        }
    }


@router.put("/rules/{action_type}")
async def update_action_type_rule(
    action_type: str,
    request: UpdateActionRuleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update auto-pilot rules for a specific action type.

    Path:
    - action_type: Action type (e.g., "deploy_product", "adjust_price")

    Body:
    - enabled: Whether auto-pilot is allowed for this action type
    - threshold: Custom confidence threshold for this action type (optional)

    Returns:
    - message: Confirmation message
    - action_type: The action type that was updated
    - rule: The updated rule
    """
    # Get or create settings
    settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()

    if not settings:
        settings = UserSettings(
            user_id=current_user.id,
            auto_pilot_enabled=False,
            auto_pilot_threshold=85.0,
            auto_pilot_rules={},
            daily_auto_execute_limit=20,
            max_auto_spend=500.0
        )
        db.add(settings)

    # Update rules
    rules = settings.auto_pilot_rules or {}

    rule = {
        "enabled": request.enabled
    }

    if request.threshold is not None:
        rule["threshold"] = request.threshold

    rules[action_type] = rule
    settings.auto_pilot_rules = rules
    settings.updated_at = datetime.utcnow()

    # Mark as modified for SQLAlchemy to detect JSON change
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(settings, "auto_pilot_rules")

    db.commit()
    db.refresh(settings)

    return {
        "success": True,
        "message": f"Rule for '{action_type}' updated successfully",
        "action_type": action_type,
        "rule": rule
    }


@router.get("/logs", response_model=List[AutoPilotLogResponse])
async def get_auto_pilot_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    executed_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent auto-pilot decision logs.

    Query params:
    - limit: Max number of logs to return (1-500, default 50)
    - offset: Number of logs to skip (for pagination)
    - executed_only: If true, only return executed actions

    Returns:
    - List of auto-pilot log entries with action details
    """
    query = db.query(AutoPilotLog).filter(
        AutoPilotLog.user_id == current_user.id
    )

    if executed_only:
        query = query.filter(AutoPilotLog.executed == True)

    logs = query.order_by(
        AutoPilotLog.created_at.desc()
    ).limit(limit).offset(offset).all()

    # Enrich with action details
    result = []
    for log in logs:
        action = db.query(Action).filter(Action.id == log.action_id).first()

        result.append({
            "id": log.id,
            "action_id": log.action_id,
            "action_title": action.title if action else "Unknown",
            "action_type": str(action.action_type) if action else "unknown",
            "confidence": log.confidence,
            "threshold_used": log.threshold_used,
            "executed": log.executed,
            "skipped_reason": log.skipped_reason,
            "created_at": log.created_at
        })

    return result


@router.delete("/logs")
async def clear_auto_pilot_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clear all auto-pilot logs for the current user.

    Returns:
    - message: Confirmation message
    - deleted_count: Number of logs deleted
    """
    count = db.query(AutoPilotLog).filter(
        AutoPilotLog.user_id == current_user.id
    ).delete()

    db.commit()

    return {
        "success": True,
        "message": f"Cleared {count} auto-pilot log(s)",
        "deleted_count": count
    }
