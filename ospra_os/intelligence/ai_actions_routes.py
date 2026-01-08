"""
API ROUTES FOR AI ACTIONS

Endpoints for users to interact with AI recommendations:
- GET /api/ai/actions - Get pending actions
- GET /api/ai/actions/stats/summary - Get action statistics
- POST /api/ai/actions/propose - Propose a new action
- POST /api/ai/actions/{action_id}/accept - Accept action
- POST /api/ai/actions/{action_id}/decline - Decline action
- GET /api/ai/actions/{action_id} - Get action details

[SECURE] SECURED with JWT Authentication

IMPORTANT: Static routes must come BEFORE dynamic routes (/{action_id})
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from ospra_os.database.multi_store_models import get_db
from ospra_os.intelligence.ai_actions import (
    get_action_manager,
    AIActionManager,
    ActionType
)

# JWT Authentication
from ospra_os.auth.dependencies import require_auth, require_tier, TokenPayload


router = APIRouter(prefix="/api/ai/actions", tags=["AI Actions"])


class DeclineActionRequest(BaseModel):
    """Request body for declining an action."""
    reason: Optional[str] = None


class ProposeActionRequest(BaseModel):
    """Request body for proposing a new action."""
    action_type: str
    title: str
    description: str
    impact_summary: str
    parameters: Dict[str, Any] = {}
    confidence: float = 0.8


class CreateActionRequest(BaseModel):
    """Request body for creating a custom action."""
    action_type: str
    title: str
    description: str
    impact_summary: str
    parameters: Dict[str, Any]
    confidence: float = 0.8


# =============================================================================
# STATIC ROUTES (must come BEFORE dynamic routes)
# =============================================================================

@router.get("")
async def get_pending_actions(
    min_confidence: float = Query(default=0.5),
    action_type: Optional[str] = Query(default=None),
    user: TokenPayload = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get all pending AI actions.

    Returns list of actions user can accept/decline.
    Frontend displays these with Accept/Decline buttons.
    
    [SECURE] Requires authentication
    """
    action_manager = get_action_manager(db)

    actions = action_manager.get_pending_actions(
        min_confidence=min_confidence
    )
    
    # Filter by action type if specified
    if action_type:
        actions = [a for a in actions if a.action_type.value == action_type]

    return [action.to_dict() for action in actions]


@router.get("/stats/summary")
async def get_action_stats_summary(
    user: TokenPayload = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get statistics on AI action acceptance rates.

    Shows which types of actions users accept vs. decline.
    Used for learning and improving recommendations.
    
    [SECURE] Requires authentication
    """
    action_manager = get_action_manager(db)

    stats = action_manager.get_action_stats()
    
    # Calculate totals
    total_proposed = sum(s.get("total", 0) for s in stats.values()) if stats else 0
    total_accepted = sum(s.get("accepted", 0) for s in stats.values()) if stats else 0
    total_declined = sum(s.get("declined", 0) for s in stats.values()) if stats else 0

    return {
        "total_proposed": total_proposed,
        "total_accepted": total_accepted,
        "total_declined": total_declined,
        "acceptance_rate": (total_accepted / total_proposed * 100) if total_proposed > 0 else 0,
        "action_types": stats,
        "summary": {
            "total_types": len(stats),
            "highest_acceptance": max(
                stats.items(),
                key=lambda x: x[1].get("acceptance_rate", 0)
            )[0] if stats else None,
            "lowest_acceptance": min(
                stats.items(),
                key=lambda x: x[1].get("acceptance_rate", 0)
            )[0] if stats else None
        }
    }


@router.post("/propose")
async def propose_action(
    request: ProposeActionRequest,
    user: TokenPayload = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Propose a new AI action.
    
    Creates an action that will appear in the user's action queue
    for review and approval.
    
    [SECURE] Requires authentication
    """
    action_manager = get_action_manager(db)

    try:
        action_type = ActionType(request.action_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action type. Must be one of: {[t.value for t in ActionType]}"
        )

    action = action_manager.create_action(
        action_type=action_type,
        title=request.title,
        description=request.description,
        impact_summary=request.impact_summary,
        parameters=request.parameters,
        confidence=request.confidence
    )

    return {
        "success": True,
        "action": action.to_dict(),
        "message": f"Action proposed: {request.title}"
    }


@router.post("/create")
async def create_custom_action(
    request: CreateActionRequest,
    user: TokenPayload = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Create a custom AI action (for testing or manual proposals).

    Normally actions are created by AI autonomously,
    but this endpoint allows manual creation.
    
    [SECURE] Requires authentication
    """
    action_manager = get_action_manager(db)

    try:
        action_type = ActionType(request.action_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action type. Must be one of: {[t.value for t in ActionType]}"
        )

    action = action_manager.create_action(
        action_type=action_type,
        title=request.title,
        description=request.description,
        impact_summary=request.impact_summary,
        parameters=request.parameters,
        confidence=request.confidence
    )

    return {
        "success": True,
        "action": action.to_dict()
    }


@router.post("/propose-from-analysis")
async def propose_actions_from_analysis(
    user: TokenPayload = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    AI analyzes current data and proposes actions.

    This is where autonomous AI creates recommendations.
    
    [SECURE] Requires authentication
    """
    from ospra_os.intelligence.autonomous_ai import get_autonomous_ai

    action_manager = get_action_manager(db)
    ai = get_autonomous_ai(db)

    # Get AI health check with recommendations
    health = await ai.autonomous_health_check(user_id=user.user_id)

    # Convert AI recommendations to actionable items
    actions_created = []

    # Example: Pause low-ROAS ads
    for alert in health.get("critical_alerts", []):
        if "ROAS" in alert and "pause" in alert.lower():
            # Extract campaign info from alert
            import re
            match = re.search(r"Campaign '([^']+)'", alert)
            if match:
                campaign_name = match.group(1)

                # Find campaign in database
                from ospra_os.database.multi_store_models import AdCampaign
                campaign = db.query(AdCampaign).filter(
                    AdCampaign.campaign_name == campaign_name
                ).first()

                if campaign:
                    action = action_manager.create_action(
                        action_type=ActionType.PAUSE_AD,
                        title=f"Pause underperforming campaign: {campaign_name}",
                        description=f"This campaign has low ROAS. Pausing will save budget.",
                        impact_summary=f"Save ${campaign.daily_budget:.2f}/day",
                        parameters={
                            "campaign_id": campaign.id,
                            "reason": "Low ROAS detected by AI"
                        },
                        confidence=0.85
                    )

                    actions_created.append(action.to_dict())

    return {
        "actions_proposed": len(actions_created),
        "actions": actions_created,
        "ai_analysis": {
            "health_score": health.get("health_score"),
            "critical_alerts": len(health.get("critical_alerts", [])),
            "confidence": health.get("ai_confidence")
        }
    }


# =============================================================================
# DYNAMIC ROUTES (must come AFTER static routes)
# =============================================================================

@router.get("/{action_id}")
async def get_action_details(
    action_id: str,
    user: TokenPayload = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific action.
    
    [SECURE] Requires authentication
    """
    action_manager = get_action_manager(db)

    action = action_manager.get_action(action_id)

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    return action.to_dict()


@router.post("/{action_id}/accept")
async def accept_action(
    action_id: str,
    user: TokenPayload = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Accept an AI action - executes it immediately.

    Returns execution result.
    
    [SECURE] Requires authentication
    """
    action_manager = get_action_manager(db)

    # User context from JWT token
    user_context = {
        "user_id": user.user_id,
        "email": user.email,
        "tier": user.tier,
        "timestamp": None
    }

    result = await action_manager.accept_action(action_id, user_context)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Execution failed"))

    return result


@router.post("/{action_id}/decline")
async def decline_action(
    action_id: str,
    request: DeclineActionRequest,
    user: TokenPayload = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Decline an AI action.

    AI learns from this rejection to improve future recommendations.
    
    [SECURE] Requires authentication
    """
    action_manager = get_action_manager(db)

    result = await action_manager.decline_action(
        action_id,
        reason=request.reason
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Decline failed"))

    return result
