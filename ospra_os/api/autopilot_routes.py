"""
AUTO-PILOT API ROUTES
=====================

Endpoints for managing Oi's autonomous operation mode.

[SECURE] SECURED with JWT Authentication
"""

from fastapi import APIRouter, HTTPException, Depends
from ospra_os.auth.jwt_auth import get_current_user
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from ospra_os.intelligence.auto_pilot import (
    get_auto_pilot,
    AutoPilotStatus,
    check_and_auto_execute
)

# JWT Authentication
from ospra_os.auth.dependencies import require_auth, require_tier, TokenPayload

# SECURITY (2026-08): router-level auth. enable/disable/pause, config
# updates and the aggressive/balanced/conservative presets were ALL callable
# anonymously — an attacker could switch on autopilot or raise its spend caps.
router = APIRouter(
    prefix="/api/autopilot",
    tags=["Auto-Pilot"],
    dependencies=[Depends(get_current_user)],
)


# === Request/Response Models ===

class AutoPilotConfigUpdate(BaseModel):
    """Request to update auto-pilot configuration."""
    status: Optional[str] = None
    max_daily_spend: Optional[float] = None
    max_daily_actions: Optional[int] = None
    undo_window_hours: Optional[int] = None
    notify_on_action: Optional[bool] = None
    notify_on_limit: Optional[bool] = None
    daily_summary: Optional[bool] = None
    action_configs: Optional[Dict[str, Dict[str, Any]]] = None


class ActionTypeConfigUpdate(BaseModel):
    """Request to update a specific action type's config."""
    enabled: Optional[bool] = None
    min_confidence: Optional[float] = None
    max_per_day: Optional[int] = None
    max_value: Optional[float] = None
    require_review_above: Optional[float] = None
    cooldown_minutes: Optional[int] = None


class UndoRequest(BaseModel):
    """Request to undo an action."""
    reason: Optional[str] = None


# === Endpoints ===

@router.get("/config")
async def get_config(user: TokenPayload = Depends(require_auth)):
    """
    Get user's auto-pilot configuration.
    
    Returns current settings including:
    - Global status (enabled/disabled/paused)
    - Daily limits
    - Per-action-type configurations
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    config = engine.get_config(user.user_id)
    
    return {
        "success": True,
        "config": config.to_dict()
    }


@router.put("/config")
async def update_config(
    updates: AutoPilotConfigUpdate,
    user: TokenPayload = Depends(require_auth)
):
    """
    Update auto-pilot configuration.
    
    Allows updating:
    - Global settings (limits, notifications)
    - Per-action-type thresholds
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    
    update_dict = updates.dict(exclude_none=True)
    config = engine.update_config(user.user_id, update_dict)
    
    return {
        "success": True,
        "config": config.to_dict(),
        "message": "Configuration updated"
    }


@router.post("/enable")
async def enable_autopilot(user: TokenPayload = Depends(require_auth)):
    """
    Enable auto-pilot mode.
    
    Once enabled, Oi will automatically execute actions that meet
    the configured thresholds without requiring manual approval.
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    config = engine.enable(user.user_id)
    
    return {
        "success": True,
        "status": config.status.value,
        "message": "[START] Auto-pilot ENABLED. Oi is now autonomous."
    }


@router.post("/disable")
async def disable_autopilot(user: TokenPayload = Depends(require_auth)):
    """
    Disable auto-pilot mode.
    
    All actions will require manual approval.
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    config = engine.disable(user.user_id)
    
    return {
        "success": True,
        "status": config.status.value,
        "message": "[STOP] Auto-pilot DISABLED. All actions require approval."
    }


@router.post("/pause")
async def pause_autopilot(user: TokenPayload = Depends(require_auth)):
    """
    Temporarily pause auto-pilot.
    
    Use when you want to temporarily stop auto-execution without
    losing your configuration.
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    config = engine.pause(user.user_id)
    
    return {
        "success": True,
        "status": config.status.value,
        "message": "[PAUSE] Auto-pilot PAUSED. Use /enable to resume."
    }


@router.put("/action/{action_type}")
async def update_action_config(
    action_type: str,
    updates: ActionTypeConfigUpdate,
    user: TokenPayload = Depends(require_auth)
):
    """
    Update configuration for a specific action type.
    
    Action types:
    - deploy_product
    - pause_ad
    - resume_ad
    - increase_ad_budget
    - decrease_ad_budget
    - adjust_price
    - drop_product
    - reorder_inventory
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    config = engine.get_config(user.user_id)
    
    if action_type not in config.action_configs:
        raise HTTPException(status_code=404, detail=f"Unknown action type: {action_type}")
    
    # Update the specific action config
    action_config = config.action_configs[action_type]
    update_dict = updates.dict(exclude_none=True)
    
    for key, value in update_dict.items():
        if hasattr(action_config, key):
            setattr(action_config, key, value)
    
    return {
        "success": True,
        "action_type": action_type,
        "config": action_config.to_dict(),
        "message": f"Configuration updated for {action_type}"
    }


@router.get("/check")
async def check_can_execute(
    action_type: str,
    confidence: float,
    monetary_value: float = 0.0,
    user: TokenPayload = Depends(require_auth)
):
    """
    Check if an action would be auto-executed.
    
    Useful for previewing what would happen without actually executing.
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    can_execute, reason = engine.can_auto_execute(
        user_id=user.user_id,
        action_type=action_type,
        confidence=confidence,
        monetary_value=monetary_value
    )
    
    return {
        "success": True,
        "would_auto_execute": can_execute,
        "reason": reason,
        "action_type": action_type,
        "confidence": confidence,
        "monetary_value": monetary_value
    }


@router.get("/actions")
async def get_recent_actions(
    limit: int = 20,
    include_undone: bool = False,
    user: TokenPayload = Depends(require_auth)
):
    """
    Get recent auto-executed actions.
    
    Shows history of what Oi has done autonomously.
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    actions = engine.get_recent_actions(
        user_id=user.user_id,
        limit=limit,
        include_undone=include_undone
    )
    
    return {
        "success": True,
        "actions": [a.to_dict() for a in actions],
        "count": len(actions)
    }


@router.post("/actions/{action_id}/undo")
async def undo_action(
    action_id: str,
    request: UndoRequest,
    user: TokenPayload = Depends(require_auth)
):
    """
    Undo an auto-executed action.
    
    Actions can be undone within the undo window (default: 24 hours).
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    success, message = engine.undo_action(action_id, request.reason)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message
    }


@router.get("/summary")
async def get_daily_summary(user: TokenPayload = Depends(require_auth)):
    """
    Get daily auto-pilot summary.
    
    Shows:
    - Actions executed today
    - Success/failure counts
    - Spending and limits
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    summary = engine.get_daily_summary(user.user_id)
    
    return {
        "success": True,
        "summary": summary
    }


@router.get("/status")
async def get_status(user: TokenPayload = Depends(require_auth)):
    """
    Quick status check for auto-pilot.
    
    Returns current operational status and key metrics.
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    config = engine.get_config(user.user_id)
    summary = engine.get_daily_summary(user.user_id)
    
    # Count enabled action types
    enabled_types = [
        k for k, v in config.action_configs.items()
        if v.enabled
    ]
    
    return {
        "success": True,
        "status": config.status.value,
        "is_active": config.status == AutoPilotStatus.ENABLED,
        "enabled_action_types": enabled_types,
        "enabled_count": len(enabled_types),
        "today": {
            "actions_executed": summary["actions_executed"],
            "successful": summary["successful"],
            "total_spend": summary["total_spend"]
        },
        "limits": summary["limits"],
        "remaining": summary["remaining"]
    }


# === Preset Configurations ===

@router.post("/presets/conservative")
async def apply_conservative_preset(user: TokenPayload = Depends(require_auth)):
    """
    Apply conservative auto-pilot preset.
    
    - High confidence thresholds (90%+)
    - Low daily limits
    - Only non-destructive actions enabled
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    
    updates = {
        "max_daily_spend": 50.0,
        "max_daily_actions": 10,
        "action_configs": {
            "deploy_product": {"enabled": True, "min_confidence": 0.90, "max_per_day": 3},
            "pause_ad": {"enabled": True, "min_confidence": 0.90, "max_per_day": 5},
            "resume_ad": {"enabled": True, "min_confidence": 0.85, "max_per_day": 5},
            "increase_ad_budget": {"enabled": False},
            "decrease_ad_budget": {"enabled": True, "min_confidence": 0.90, "max_per_day": 3},
            "adjust_price": {"enabled": False},
            "drop_product": {"enabled": False},
            "reorder_inventory": {"enabled": False},
        }
    }
    
    config = engine.update_config(user.user_id, updates)
    
    return {
        "success": True,
        "preset": "conservative",
        "config": config.to_dict(),
        "message": " Conservative preset applied. Safe, cautious auto-pilot."
    }


@router.post("/presets/balanced")
async def apply_balanced_preset(user: TokenPayload = Depends(require_auth)):
    """
    Apply balanced auto-pilot preset.
    
    - Moderate confidence thresholds (85%)
    - Reasonable daily limits
    - Most actions enabled with safeguards
    
    [SECURE] Requires authentication
    """
    engine = get_auto_pilot()
    
    updates = {
        "max_daily_spend": 100.0,
        "max_daily_actions": 20,
        "action_configs": {
            "deploy_product": {"enabled": True, "min_confidence": 0.85, "max_per_day": 5},
            "pause_ad": {"enabled": True, "min_confidence": 0.80, "max_per_day": 10},
            "resume_ad": {"enabled": True, "min_confidence": 0.80, "max_per_day": 10},
            "increase_ad_budget": {"enabled": True, "min_confidence": 0.90, "max_per_day": 3, "max_value": 25.0},
            "decrease_ad_budget": {"enabled": True, "min_confidence": 0.85, "max_per_day": 5},
            "adjust_price": {"enabled": True, "min_confidence": 0.90, "max_per_day": 3},
            "drop_product": {"enabled": False},
            "reorder_inventory": {"enabled": True, "min_confidence": 0.90, "max_per_day": 2, "max_value": 200.0},
        }
    }
    
    config = engine.update_config(user.user_id, updates)
    
    return {
        "success": True,
        "preset": "balanced",
        "config": config.to_dict(),
        "message": " Balanced preset applied. Good mix of automation and safety."
    }


@router.post("/presets/aggressive")
async def apply_aggressive_preset(
    user: TokenPayload = Depends(require_tier("soar"))  # Requires Soar tier or higher
):
    """
    Apply aggressive auto-pilot preset.
    
    - Lower confidence thresholds (80%)
    - Higher daily limits
    - All actions enabled
    
    [WARNING] Use with caution!
    
    [SECURE] Requires Soar tier or higher
    """
    engine = get_auto_pilot()
    
    updates = {
        "max_daily_spend": 250.0,
        "max_daily_actions": 50,
        "action_configs": {
            "deploy_product": {"enabled": True, "min_confidence": 0.80, "max_per_day": 10},
            "pause_ad": {"enabled": True, "min_confidence": 0.75, "max_per_day": 20},
            "resume_ad": {"enabled": True, "min_confidence": 0.75, "max_per_day": 20},
            "increase_ad_budget": {"enabled": True, "min_confidence": 0.85, "max_per_day": 5, "max_value": 50.0},
            "decrease_ad_budget": {"enabled": True, "min_confidence": 0.80, "max_per_day": 10},
            "adjust_price": {"enabled": True, "min_confidence": 0.85, "max_per_day": 10},
            "drop_product": {"enabled": True, "min_confidence": 0.95, "max_per_day": 2},
            "reorder_inventory": {"enabled": True, "min_confidence": 0.85, "max_per_day": 5, "max_value": 500.0},
        }
    }
    
    config = engine.update_config(user.user_id, updates)
    
    return {
        "success": True,
        "preset": "aggressive",
        "config": config.to_dict(),
        "message": "[HOT] Aggressive preset applied. Maximum automation. Monitor closely!"
    }
