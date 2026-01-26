"""
Actions Queue API Routes
=========================

AI-generated actions that require user approval before execution.
Every recommendation becomes an actionable card in the Actions Queue.

Endpoints:
- GET /api/actions - Get actions with filtering
- GET /api/actions/stats - Get action statistics
- GET /api/actions/{id} - Get specific action
- POST /api/actions - Create new action
- POST /api/actions/{id}/approve - Approve and execute action
- POST /api/actions/{id}/skip - Skip/dismiss action
- PUT /api/actions/{id} - Update action payload
- POST /api/actions/approve-all - Approve all high-confidence actions
- DELETE /api/actions/{id} - Delete action
- GET /api/actions/recent-executed - Get recently executed actions with undo status
- POST /api/actions/{id}/undo - Undo an executed action
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import get_db
from ospra_os.database import User
from ospra_os.database.action_models import (
    Action,
    ActionLog,
    AIActionType,
    AIActionStatus,
)
from ospra_os.actions.undo_manager import UndoManager
from ospra_os.services.action_executor import ActionExecutorFactory


router = APIRouter(prefix="/api/actions", tags=["Actions Queue"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ActionFactor(BaseModel):
    """Key factor contributing to action confidence"""
    label: str
    value: float  # Positive or negative impact
    icon: Optional[str] = None


class ActionCreate(BaseModel):
    """Create new action request"""
    action_type: AIActionType
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    confidence: float = Field(..., ge=0, le=100)
    rationale: str
    factors: List[ActionFactor] = []
    payload: Dict[str, Any]
    estimated_impact: Optional[str] = None
    product_image: Optional[str] = None
    store_id: Optional[int] = None
    expires_in_hours: Optional[int] = 72  # Default 72 hours


class ActionUpdate(BaseModel):
    """Update action payload before approval"""
    payload: Dict[str, Any]
    title: Optional[str] = None
    description: Optional[str] = None


class ActionResponse(BaseModel):
    """Action response model"""
    id: int
    user_id: int
    store_id: Optional[int]
    action_type: str
    title: str
    description: Optional[str]
    confidence: float
    rationale: str
    factors: List[Dict[str, Any]]
    payload: Dict[str, Any]
    status: str
    estimated_impact: Optional[str]
    product_image: Optional[str]
    created_at: datetime
    executed_at: Optional[datetime]
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class ActionStatsResponse(BaseModel):
    """Action statistics"""
    pending: int
    approved: int
    executed: int
    skipped: int
    failed: int
    avg_confidence: float


class BulkApproveResponse(BaseModel):
    """Bulk approval result"""
    approved_count: int
    action_ids: List[int]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log_action_change(
    db: Session,
    action: Action,
    old_status: AIActionStatus,
    new_status: AIActionStatus,
    user_id: Optional[int] = None,
    reason: Optional[str] = None,
    log_metadata: Optional[Dict] = None
):
    """Create audit log entry for action status change"""
    log = ActionLog(
        action_id=action.id,
        user_id=user_id,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        log_metadata=log_metadata or {}
    )
    db.add(log)
    db.commit()


# ============================================================================
# ACTION EXECUTION HANDLERS
# ============================================================================

def capture_previous_state(action: Action) -> Dict[str, Any]:
    """
    Capture the current state before executing an action for undo purposes.
    Returns state data that can be used to reverse the action.
    """
    payload = action.payload or {}

    if action.action_type == AIActionType.DEPLOY_PRODUCT:
        # For product deployment, capture that product didn't exist
        return {
            "product_deployed": False,
            "product_name": payload.get("product_name")
        }

    elif action.action_type == AIActionType.ADJUST_PRICE:
        # For price adjustment, capture current price
        return {
            "price": payload.get("current_price"),
            "product_name": payload.get("product_name"),
            "variant_id": payload.get("variant_id")
        }

    elif action.action_type == AIActionType.PAUSE_AD:
        # For pausing ad, capture that it was active
        return {
            "campaign_status": "ACTIVE",
            "campaign_id": payload.get("campaign_id"),
            "campaign_name": payload.get("campaign_name"),
            "platform": payload.get("platform")
        }

    elif action.action_type == AIActionType.RESUME_AD:
        # For resuming ad, capture that it was paused
        return {
            "campaign_status": "PAUSED",
            "campaign_id": payload.get("campaign_id"),
            "campaign_name": payload.get("campaign_name"),
            "platform": payload.get("platform")
        }

    elif action.action_type == AIActionType.DROP_PRODUCT:
        # For dropping product, capture product details
        return {
            "product_active": True,
            "product_name": payload.get("product_name"),
            "shopify_product_id": payload.get("shopify_product_id")
        }

    elif action.action_type == AIActionType.SEND_REFUND:
        # Refunds cannot be undone
        return {}

    elif action.action_type == AIActionType.REPLY_EMAIL:
        # Emails cannot be undone
        return {}

    elif action.action_type == AIActionType.RESTOCK_ALERT:
        # Alerts don't need undo
        return {}

    return {}


async def execute_action(action: Action, db: Session) -> Dict[str, Any]:
    """
    Execute approved action using ActionExecutorFactory.
    Routes to the appropriate executor based on action_type and executes the action.
    Returns execution result with success status and platform response data.
    """
    try:
        # Get the appropriate executor for this action type
        executor = ActionExecutorFactory.get_executor(
            action_type=action.action_type.value,
            db=db,
            user_id=action.user_id
        )

        if not executor:
            return {
                "success": False,
                "error": f"No executor found for action type: {action.action_type}"
            }

        # Execute the action
        result = await executor.execute(action)

        # Convert ExecutionResult to dict for JSON serialization
        return {
            "success": result.success,
            "message": result.message,
            "before_state": result.before_state,
            "after_state": result.after_state,
            "platform_response": result.platform_response,
            "error": result.error,
            "is_undoable": result.is_undoable,
            "undo_payload": result.undo_payload
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Execution error: {str(e)}"
        }


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("", response_model=List[ActionResponse])
async def get_actions(
    status: Optional[AIActionStatus] = Query(None, description="Filter by status"),
    action_type: Optional[AIActionType] = Query(None, description="Filter by action type"),
    min_confidence: Optional[float] = Query(None, ge=0, le=100, description="Minimum confidence score"),
    limit: int = Query(50, le=200, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Results offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get actions with optional filtering.

    Returns actions for the current user, sorted by created_at (newest first).
    """
    query = db.query(Action).filter(Action.user_id == current_user.id)

    if status:
        query = query.filter(Action.status == status)

    if action_type:
        query = query.filter(Action.action_type == action_type)

    if min_confidence is not None:
        query = query.filter(Action.confidence >= min_confidence)

    # Filter out expired actions
    query = query.filter(
        (Action.expires_at.is_(None)) | (Action.expires_at > datetime.utcnow())
    )

    actions = query.order_by(desc(Action.created_at)).offset(offset).limit(limit).all()
    return actions


@router.get("/stats", response_model=ActionStatsResponse)
async def get_action_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get action statistics for current user.

    Returns counts of actions by status and average confidence.
    """
    # Use aggregation instead of loading all records into memory
    from sqlalchemy import func

    # Get counts by status using SQL aggregation
    status_counts = db.query(
        Action.status,
        func.count(Action.id)
    ).filter(
        Action.user_id == current_user.id
    ).group_by(Action.status).all()

    # Get average confidence
    avg_confidence = db.query(
        func.avg(Action.confidence)
    ).filter(
        Action.user_id == current_user.id
    ).scalar() or 0.0

    # Build stats from aggregation results (efficient - no loading all records)
    stats = {
        "pending": 0,
        "approved": 0,
        "executed": 0,
        "skipped": 0,
        "failed": 0,
        "avg_confidence": float(avg_confidence)
    }

    # Map status enum values to stats keys
    for status, count in status_counts:
        if status == AIActionStatus.PENDING:
            stats["pending"] = count
        elif status == AIActionStatus.APPROVED:
            stats["approved"] = count
        elif status == AIActionStatus.EXECUTED:
            stats["executed"] = count
        elif status == AIActionStatus.SKIPPED:
            stats["skipped"] = count
        elif status == AIActionStatus.FAILED:
            stats["failed"] = count

    return ActionStatsResponse(**stats)


@router.get("/recent-executed")
async def get_recent_executed_actions(
    limit: int = Query(20, le=50, description="Max results"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recently executed actions with undo status.

    Returns list of executed actions along with whether they can be undone
    and how much time remains for undo.
    """
    actions = db.query(Action).filter(
        Action.user_id == current_user.id,
        Action.status.in_([AIActionStatus.EXECUTED, AIActionStatus.UNDONE])
    ).order_by(desc(Action.executed_at)).limit(limit).all()

    undo_manager = UndoManager(db)

    result = []
    for action in actions:
        undo_check = undo_manager.can_undo(action)
        result.append({
            "id": action.id,
            "action_type": action.action_type.value,
            "title": action.title,
            "description": action.description,
            "executed_at": action.executed_at.isoformat() if action.executed_at else None,
            "undone_at": action.undone_at.isoformat() if action.undone_at else None,
            "can_undo": undo_check.get("can_undo", False),
            "hours_remaining": undo_check.get("hours_remaining"),
            "undo_deadline": undo_check.get("deadline"),
            "payload": action.payload,
            "execution_result": action.execution_result
        })

    return {"actions": result}


@router.get("/{action_id}", response_model=ActionResponse)
async def get_action(
    action_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific action by ID"""
    action = db.query(Action).filter(
        Action.id == action_id,
        Action.user_id == current_user.id
    ).first()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found"
        )

    return action


@router.post("", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action(
    action_data: ActionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new action.

    AI systems call this endpoint to propose actions for user approval.
    """
    action = Action(
        user_id=current_user.id,
        store_id=action_data.store_id,
        action_type=action_data.action_type,
        title=action_data.title,
        description=action_data.description,
        confidence=action_data.confidence,
        rationale=action_data.rationale,
        factors=[f.dict() for f in action_data.factors],
        payload=action_data.payload,
        estimated_impact=action_data.estimated_impact,
        product_image=action_data.product_image,
        status=AIActionStatus.PENDING
    )

    # Set expiration time
    if action_data.expires_in_hours:
        action.set_default_expiration(hours=action_data.expires_in_hours)

    db.add(action)
    db.commit()
    db.refresh(action)

    # Log creation
    log_action_change(
        db, action,
        old_status=None,
        new_status=AIActionStatus.PENDING,
        user_id=None,  # Created by system
        reason="Action created by AI system"
    )

    return action


@router.post("/{action_id}/approve")
async def approve_action(
    action_id: int,
    execute_now: bool = Query(True, description="Execute action immediately after approval"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Approve action and optionally execute it.

    If execute_now=True (default), the action is executed immediately.
    Otherwise, it's marked as approved and queued for later execution.
    """
    action = db.query(Action).filter(
        Action.id == action_id,
        Action.user_id == current_user.id
    ).first()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found"
        )

    if not action.is_actionable():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action cannot be approved (status: {action.status}, expired: {action.is_expired()})"
        )

    old_status = action.status

    # Update status
    action.status = AIActionStatus.APPROVED
    db.commit()

    # Log approval
    log_action_change(
        db, action,
        old_status=old_status,
        new_status=AIActionStatus.APPROVED,
        user_id=current_user.id,
        reason="User approved action"
    )

    # Execute if requested
    if execute_now:
        # Capture previous state for undo
        action.previous_state = capture_previous_state(action)

        # Set undo deadline based on action type
        undo_manager = UndoManager(db)
        undo_window_hours = undo_manager.UNDO_WINDOWS.get(action.action_type)
        if undo_window_hours and undo_window_hours > 0:
            action.undo_deadline = datetime.utcnow() + timedelta(hours=undo_window_hours)
            action.is_undoable = True
        else:
            action.undo_deadline = None
            action.is_undoable = False

        action.status = AIActionStatus.EXECUTING
        db.commit()

        result = await execute_action(action, db)

        if result.get("success"):
            action.status = AIActionStatus.EXECUTED
            action.executed_at = datetime.utcnow()
            action.execution_result = result
        else:
            action.status = AIActionStatus.FAILED
            action.error_message = result.get("error")

        db.commit()

        # Log execution
        log_action_change(
            db, action,
            old_status=AIActionStatus.EXECUTING,
            new_status=action.status,
            user_id=None,  # Executed by system
            reason="Action executed",
            log_metadata=result
        )

        return {
            "message": "Action approved and executed",
            "action_id": action.id,
            "execution_result": result
        }

    return {
        "message": "Action approved",
        "action_id": action.id
    }


@router.post("/{action_id}/skip")
async def skip_action(
    action_id: int,
    reason: Optional[str] = Query(None, description="Reason for skipping"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Skip/dismiss action without executing it.

    Useful for actions the user doesn't want to perform.
    """
    action = db.query(Action).filter(
        Action.id == action_id,
        Action.user_id == current_user.id
    ).first()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found"
        )

    if not action.is_actionable():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action cannot be skipped (status: {action.status})"
        )

    old_status = action.status
    action.status = AIActionStatus.SKIPPED
    db.commit()

    # Log skip
    log_action_change(
        db, action,
        old_status=old_status,
        new_status=AIActionStatus.SKIPPED,
        user_id=current_user.id,
        reason=reason or "User skipped action"
    )

    return {
        "message": "Action skipped",
        "action_id": action.id
    }


@router.put("/{action_id}", response_model=ActionResponse)
async def update_action(
    action_id: int,
    updates: ActionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update action payload before approval.

    Allows user to tweak action parameters (e.g., adjust price) before executing.
    """
    action = db.query(Action).filter(
        Action.id == action_id,
        Action.user_id == current_user.id
    ).first()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found"
        )

    if action.status != AIActionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update pending actions"
        )

    # Update fields
    if updates.payload:
        action.payload = updates.payload
    if updates.title:
        action.title = updates.title
    if updates.description:
        action.description = updates.description

    action.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(action)

    # Log update
    log_action_change(
        db, action,
        old_status=AIActionStatus.PENDING,
        new_status=AIActionStatus.PENDING,
        user_id=current_user.id,
        reason="User edited action payload",
        log_metadata={"updated_fields": updates.dict(exclude_unset=True)}
    )

    return action


@router.post("/approve-all", response_model=BulkApproveResponse)
async def approve_all_high_confidence(
    confidence_threshold: float = Query(85, ge=0, le=100, description="Minimum confidence to approve"),
    execute_now: bool = Query(True, description="Execute actions immediately"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Approve all high-confidence pending actions.

    Useful for bulk approving trusted AI recommendations.
    """
    # Get high-confidence pending actions
    actions = db.query(Action).filter(
        Action.user_id == current_user.id,
        Action.status == AIActionStatus.PENDING,
        Action.confidence >= confidence_threshold,
        (Action.expires_at.is_(None)) | (Action.expires_at > datetime.utcnow())
    ).all()

    approved_ids = []

    for action in actions:
        old_status = action.status
        action.status = AIActionStatus.APPROVED

        # Log approval
        log_action_change(
            db, action,
            old_status=old_status,
            new_status=AIActionStatus.APPROVED,
            user_id=current_user.id,
            reason=f"Bulk approved (confidence: {action.confidence}%)"
        )

        # Execute if requested
        if execute_now:
            # Capture previous state for undo
            action.previous_state = capture_previous_state(action)

            # Set undo deadline based on action type
            undo_manager_bulk = UndoManager(db)
            undo_window_hours = undo_manager_bulk.UNDO_WINDOWS.get(action.action_type)
            if undo_window_hours and undo_window_hours > 0:
                action.undo_deadline = datetime.utcnow() + timedelta(hours=undo_window_hours)
                action.is_undoable = True
            else:
                action.undo_deadline = None
                action.is_undoable = False

            action.status = AIActionStatus.EXECUTING
            db.commit()

            result = await execute_action(action, db)

            if result.get("success"):
                action.status = AIActionStatus.EXECUTED
                action.executed_at = datetime.utcnow()
                action.execution_result = result
            else:
                action.status = AIActionStatus.FAILED
                action.error_message = result.get("error")

            log_action_change(
                db, action,
                old_status=AIActionStatus.EXECUTING,
                new_status=action.status,
                user_id=None,
                reason="Bulk execution",
                log_metadata=result
            )

        approved_ids.append(action.id)

    db.commit()

    return BulkApproveResponse(
        approved_count=len(approved_ids),
        action_ids=approved_ids
    )


@router.delete("/{action_id}")
async def delete_action(
    action_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete/cancel an action.

    Removes action from queue completely (including audit logs).
    """
    action = db.query(Action).filter(
        Action.id == action_id,
        Action.user_id == current_user.id
    ).first()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found"
        )

    db.delete(action)
    db.commit()

    return {
        "message": "Action deleted",
        "action_id": action_id
    }


@router.post("/{action_id}/undo")
async def undo_action_endpoint(
    action_id: int,
    reason: Optional[str] = Query(None, description="Reason for undo"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Undo an executed action.

    Reverses the action if within the undo time window.
    Different action types have different undo windows:
    - Product deployment: 24 hours
    - Price adjustment: 48 hours
    - Ad pause/resume: 7 days
    - Email/refund: Cannot be undone
    """
    action = db.query(Action).filter(
        Action.id == action_id,
        Action.user_id == current_user.id
    ).first()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found"
        )

    undo_manager = UndoManager(db)
    result = await undo_manager.undo_action(action, current_user.id, reason)

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to undo action")
        )

    return result
