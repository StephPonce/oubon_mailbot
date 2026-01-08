"""
USAGE TRACKING API ROUTES

Endpoints for tracking and querying user usage against tier limits.

[SECURE] SECURED with JWT Authentication
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, Optional
from pydantic import BaseModel

from ospra_os.database.multi_store_models import SessionLocal, get_db
from ospra_os.core.usage_tracking import (
    UsageTracker,
    TierUsageEnforcer,
    UsageType,
    get_tracker,
    get_enforcer,
)

# JWT Authentication
from ospra_os.auth.dependencies import require_auth, require_tier, TokenPayload

router = APIRouter(prefix="/api/usage", tags=["Usage Tracking"])


# ==================== REQUEST MODELS ====================

class RecordUsageRequest(BaseModel):
    action: str  # e.g., "aliexpress_search", "product_discovery"
    count: int = 1
    store_id: Optional[int] = None
    product_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class CheckLimitRequest(BaseModel):
    action: str


# ==================== TRACKING ENDPOINTS ====================

@router.post("/record")
async def record_usage(
    request: RecordUsageRequest,
    user: TokenPayload = Depends(require_auth)
):
    """
    Record a usage event.
    
    Actions:
    - product_discovery
    - aliexpress_search
    - aliexpress_enrichment
    - product_deploy
    - email_automation
    - ai_query
    - ai_briefing
    - inventory_check
    
    [SECURE] Requires authentication
    """
    db = SessionLocal()
    try:
        enforcer = get_enforcer(db)
        
        # First check if action is allowed
        check = enforcer.can_perform(user.user_id, request.action, request.count)
        
        if not check.get("allowed"):
            return {
                "success": False,
                "recorded": False,
                "reason": check.get("reason", "Limit reached"),
                "current": check.get("current"),
                "limit": check.get("limit"),
                "upgrade_suggestion": check.get("upgrade_suggestion")
            }
        
        # Record the action
        result = enforcer.record_action(
            user_id=user.user_id,
            action=request.action,
            count=request.count,
            store_id=request.store_id,
            product_id=request.product_id,
            event_data=request.metadata
        )
        
        return {
            "success": result.get("success", False),
            "recorded": True,
            "daily_count": result.get("daily_count"),
            "weekly_count": result.get("weekly_count"),
            "monthly_count": result.get("monthly_count")
        }
        
    finally:
        db.close()


@router.post("/check")
async def check_limit(
    request: CheckLimitRequest,
    user: TokenPayload = Depends(require_auth)
):
    """
    Check if a user can perform an action.
    
    Returns:
    - allowed: bool
    - current: current usage count
    - limit: tier limit
    - remaining: how many more allowed
    
    [SECURE] Requires authentication
    """
    db = SessionLocal()
    try:
        enforcer = get_enforcer(db)
        result = enforcer.can_perform(user.user_id, request.action)
        return result
    finally:
        db.close()


# ==================== QUERY ENDPOINTS ====================

@router.get("/dashboard")
async def get_usage_dashboard(user: TokenPayload = Depends(require_auth)):
    """
    Get complete usage dashboard for the authenticated user.
    
    Shows all usage metrics with their limits based on tier.
    
    [SECURE] Requires authentication
    """
    db = SessionLocal()
    try:
        enforcer = get_enforcer(db)
        dashboard = enforcer.get_usage_dashboard(user.user_id)
        return dashboard
    finally:
        db.close()


@router.get("/history/{action}")
async def get_usage_history(
    action: str,
    days: int = 30,
    user: TokenPayload = Depends(require_auth)
):
    """
    Get usage history for a specific action over the past N days.
    
    [SECURE] Requires authentication
    """
    db = SessionLocal()
    try:
        tracker = get_tracker(db)
        
        # Map action to usage type
        action_to_type = {
            "product_discovery": UsageType.PRODUCT_DISCOVERY,
            "aliexpress_search": UsageType.ALIEXPRESS_SEARCH,
            "aliexpress_enrichment": UsageType.ALIEXPRESS_ENRICHMENT,
            "product_deploy": UsageType.PRODUCT_DEPLOY,
            "email_automation": UsageType.EMAIL_AUTOMATION,
            "ai_query": UsageType.AI_QUERY,
            "ai_briefing": UsageType.AI_BRIEFING,
            "inventory_check": UsageType.INVENTORY_CHECK,
        }
        
        usage_type = action_to_type.get(action)
        if not usage_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action: {action}"
            )
        
        history = tracker.get_usage_history(user.user_id, usage_type, days)
        
        return {
            "user_id": user.user_id,
            "action": action,
            "days": days,
            "history": history
        }
        
    finally:
        db.close()


@router.get("/all")
async def get_all_usage(user: TokenPayload = Depends(require_auth)):
    """
    Get all usage stats for the authenticated user (daily, weekly, monthly).
    
    [SECURE] Requires authentication
    """
    db = SessionLocal()
    try:
        tracker = get_tracker(db)
        usage = tracker.get_all_usage(user.user_id)
        return {
            "user_id": user.user_id,
            "usage": usage
        }
    finally:
        db.close()


# ==================== TIER INFO ENDPOINTS ====================

@router.get("/tier")
async def get_user_tier_info(user: TokenPayload = Depends(require_auth)):
    """
    Get user's current tier and all associated limits.
    
    [SECURE] Requires authentication
    """
    db = SessionLocal()
    try:
        enforcer = get_enforcer(db)
        tier = enforcer.get_user_tier(user.user_id)
        
        # Get all limits for this tier
        from ospra_os.core.tiers import get_tier_definition
        tier_def = get_tier_definition(tier)
        
        return {
            "user_id": user.user_id,
            "tier": tier,
            "tier_info": tier_def
        }
        
    finally:
        db.close()


# ==================== HEALTH CHECK ====================

@router.get("/health")
async def usage_health():
    """
    Health check for usage tracking system.
    
    [WARNING] Public endpoint (no auth required)
    """
    db = SessionLocal()
    try:
        # Test that we can query the database
        tracker = get_tracker(db)
        
        return {
            "status": "healthy",
            "message": "Usage tracking system operational"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
    finally:
        db.close()
