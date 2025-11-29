"""
API ROUTES FOR AI ACTIONS

Endpoints for users to interact with AI recommendations:
- GET /api/ai/actions - Get pending actions
- POST /api/ai/actions/{action_id}/accept - Accept action
- POST /api/ai/actions/{action_id}/decline - Decline action
- GET /api/ai/actions/stats - Get action statistics
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from ospra_os.database.multi_store_models import get_db
from ospra_os.intelligence.ai_actions import (
    get_action_manager,
    AIActionManager,
    ActionType
)


router = APIRouter(prefix="/api/ai/actions", tags=["AI Actions"])


class DeclineActionRequest(BaseModel):
    """Request body for declining an action."""
    reason: Optional[str] = None


class CreateActionRequest(BaseModel):
    """Request body for creating a custom action."""
    action_type: str
    title: str
    description: str
    impact_summary: str
    parameters: Dict[str, Any]
    confidence: float = 0.8


@router.get("", response_model=List[Dict[str, Any]])
async def get_pending_actions(
    min_confidence: float = 0.7,
    db: Session = Depends(get_db)
):
    """
    Get all pending AI actions.

    Returns list of actions user can accept/decline.
    Frontend displays these with Accept/Decline buttons.
    """
    action_manager = get_action_manager(db)

    actions = action_manager.get_pending_actions(
        min_confidence=min_confidence
    )

    return [action.to_dict() for action in actions]


@router.post("/{action_id}/accept")
async def accept_action(
    action_id: str,
    db: Session = Depends(get_db)
):
    """
    Accept an AI action - executes it immediately.

    Returns execution result.
    """
    action_manager = get_action_manager(db)

    # User context (would come from auth in production)
    user_context = {
        "user_id": 1,
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
    db: Session = Depends(get_db)
):
    """
    Decline an AI action.

    AI learns from this rejection to improve future recommendations.
    """
    action_manager = get_action_manager(db)

    result = await action_manager.decline_action(
        action_id,
        reason=request.reason
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Decline failed"))

    return result


@router.get("/{action_id}")
async def get_action_details(
    action_id: str,
    db: Session = Depends(get_db)
):
    """Get details of a specific action."""
    action_manager = get_action_manager(db)

    action = action_manager.get_action(action_id)

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    return action.to_dict()


@router.get("/stats/summary")
async def get_action_stats(
    db: Session = Depends(get_db)
):
    """
    Get statistics on AI action acceptance rates.

    Shows which types of actions users accept vs. decline.
    Used for learning and improving recommendations.
    """
    action_manager = get_action_manager(db)

    stats = action_manager.get_action_stats()

    return {
        "action_types": stats,
        "summary": {
            "total_types": len(stats),
            "highest_acceptance": max(
                stats.items(),
                key=lambda x: x[1]["acceptance_rate"]
            )[0] if stats else None,
            "lowest_acceptance": min(
                stats.items(),
                key=lambda x: x[1]["acceptance_rate"]
            )[0] if stats else None
        }
    }


@router.post("/create")
async def create_custom_action(
    request: CreateActionRequest,
    db: Session = Depends(get_db)
):
    """
    Create a custom AI action (for testing or manual proposals).

    Normally actions are created by AI autonomously,
    but this endpoint allows manual creation.
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

    return action.to_dict()


# Example: AI proposes actions based on data analysis
@router.post("/propose-from-analysis")
async def propose_actions_from_analysis(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    AI analyzes current data and proposes actions.

    This is where autonomous AI creates recommendations.
    """
    from ospra_os.intelligence.autonomous_ai import get_autonomous_ai

    action_manager = get_action_manager(db)
    ai = get_autonomous_ai(db)

    # Get AI health check with recommendations
    health = await ai.autonomous_health_check(user_id=user_id)

    # Convert AI recommendations to actionable items
    actions_created = []

    # Example: Pause low-ROAS ads
    for alert in health.get("critical_alerts", []):
        if "ROAS" in alert and "pause" in alert.lower():
            # Extract campaign info from alert
            # This is simplified - would parse alert properly
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
