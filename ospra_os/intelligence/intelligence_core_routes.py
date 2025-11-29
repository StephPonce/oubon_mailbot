"""
INTELLIGENCE CORE API ROUTES

Exposes all Intelligence Core functionality via REST API.

Endpoints:
- Briefings (morning, on-demand)
- Product grading (calculate, bulk)
- Progress tracking (by product, by stage)
- Unified context (full, summary)
- Actions (preview, execute, undo)
- Tier management (check, upgrade)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel

from ospra_os.database.multi_store_models import get_db
from ospra_os.intelligence.unified_context import get_unified_context_builder
from ospra_os.intelligence.briefing_engine import get_briefing_engine
from ospra_os.intelligence.grade_reasoning import get_grade_reasoning_engine
from ospra_os.intelligence.progress_flow import get_progress_tracker, LifecycleStage
from ospra_os.intelligence.tier_system import get_tier_system, Tier
from ospra_os.intelligence.action_executor import get_action_executor, ActionType

router = APIRouter(prefix="/api/intelligence", tags=["Intelligence Core"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ActionPreviewRequest(BaseModel):
    action_type: str
    params: dict


class ActionExecuteRequest(BaseModel):
    action_type: str
    params: dict
    user_id: int


class TierUpgradeRequest(BaseModel):
    new_tier: str
    payment_method_id: Optional[str] = None


# ============================================================================
# BRIEFING ENDPOINTS
# ============================================================================

@router.get("/briefing/morning")
async def get_morning_briefing(
    user_id: Optional[int] = Query(None),
    store_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get morning AI briefing.

    Returns:
    - Professional briefing text (no emojis)
    - Attention items requiring action
    - Key metrics summary
    - Recommended actions
    """
    engine = get_briefing_engine(db)
    return await engine.generate_morning_briefing(user_id, store_id)


@router.get("/briefing/on-demand")
async def get_on_demand_briefing(
    user_id: Optional[int] = Query(None),
    store_id: Optional[int] = Query(None),
    focus: Optional[str] = Query(None, description="products, ads, emails, competitors"),
    db: Session = Depends(get_db)
):
    """
    Get on-demand AI briefing, optionally focused on specific area.
    """
    engine = get_briefing_engine(db)
    return {
        "briefing_text": await engine.generate_on_demand_briefing(user_id, store_id, focus),
        "focus_area": focus,
        "timestamp": "now"
    }


# ============================================================================
# UNIFIED CONTEXT ENDPOINTS
# ============================================================================

@router.get("/context/full")
async def get_full_context(
    user_id: Optional[int] = Query(None),
    store_id: Optional[int] = Query(None),
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Get complete unified context (ALL data aggregated).

    This is the "brain's eyes" - everything the AI sees at once.
    """
    builder = get_unified_context_builder(db)
    return await builder.build_full_context(user_id, store_id, force_refresh)


@router.get("/context/summary")
async def get_context_summary(
    user_id: Optional[int] = Query(None),
    store_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get executive summary from unified context.
    """
    builder = get_unified_context_builder(db)
    context = await builder.build_full_context(user_id, store_id)
    return context.get("summary", {})


@router.post("/context/invalidate")
async def invalidate_context_cache(
    user_id: Optional[int] = Query(None),
    store_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Invalidate cached context to force refresh.
    """
    builder = get_unified_context_builder(db)
    builder.invalidate_cache(user_id, store_id)
    return {"success": True, "message": "Cache invalidated"}


# ============================================================================
# PRODUCT GRADING ENDPOINTS
# ============================================================================

@router.get("/grade/product/{product_id}")
async def grade_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    Calculate comprehensive product grade with full breakdown.

    Returns:
    - Letter grade (A+, A, B+, B, C+, C, D, F)
    - Numerical score (0-100)
    - Detailed breakdown by factor
    - Strengths and weaknesses
    - Actionable recommendation
    """
    engine = get_grade_reasoning_engine(db)
    return await engine.calculate_product_grade(product_id)


@router.post("/grade/bulk")
async def grade_products_bulk(
    product_ids: List[int],
    db: Session = Depends(get_db)
):
    """
    Grade multiple products at once.
    """
    engine = get_grade_reasoning_engine(db)

    results = []
    for product_id in product_ids:
        try:
            grade = await engine.calculate_product_grade(product_id)
            results.append(grade)
        except Exception as e:
            results.append({
                "product_id": product_id,
                "error": str(e)
            })

    return {"grades": results, "total": len(results)}


# ============================================================================
# PROGRESS FLOW ENDPOINTS
# ============================================================================

@router.get("/progress/product/{product_id}")
async def get_product_progress(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    Get complete progress information for product.

    Returns:
    - Current lifecycle stage
    - Progress percentage
    - Days in current stage
    - Next milestone
    - Stage history
    - All milestones with completion status
    """
    tracker = get_progress_tracker(db)
    return await tracker.get_product_progress(product_id)


@router.post("/progress/product/{product_id}/advance")
async def advance_product_stage(
    product_id: int,
    new_stage: str,
    note: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Manually advance product to new lifecycle stage.
    """
    tracker = get_progress_tracker(db)
    stage_enum = LifecycleStage(new_stage)
    return await tracker.advance_stage(product_id, stage_enum, note)


@router.get("/progress/by-stage/{stage}")
async def get_products_by_stage(
    stage: str,
    user_id: Optional[int] = Query(None),
    store_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """
    Get all products in a specific lifecycle stage.

    Stages: discovery, analysis, deploy, active, review, dropped
    """
    tracker = get_progress_tracker(db)
    stage_enum = LifecycleStage(stage)
    return await tracker.get_products_by_stage(stage_enum, user_id, store_id, limit)


# ============================================================================
# TIER SYSTEM ENDPOINTS
# ============================================================================

@router.get("/tier/info")
async def get_tier_info(
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get complete tier information for user.

    Returns:
    - Current tier (starter, pro, enterprise)
    - Pricing
    - Feature access
    - Usage limits
    - Current usage
    """
    tier_system = get_tier_system(db)
    return await tier_system.get_tier_info(user_id)


@router.get("/tier/check-feature")
async def check_feature_access(
    user_id: int = Query(...),
    feature: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Check if user has access to specific feature.

    Features: ai_briefings, auto_deploy, ad_automation, etc.
    """
    tier_system = get_tier_system(db)
    has_access = await tier_system.check_feature_access(user_id, feature)
    return {
        "user_id": user_id,
        "feature": feature,
        "has_access": has_access
    }


@router.get("/tier/check-limit")
async def check_usage_limit(
    user_id: int = Query(...),
    limit_type: str = Query(...),
    current_usage: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Check if user has exceeded usage limit.

    Limits: max_products, ai_briefings_per_day, auto_actions_per_day, etc.
    """
    tier_system = get_tier_system(db)
    return await tier_system.check_limit(user_id, limit_type, current_usage)


@router.post("/tier/upgrade")
async def upgrade_tier(
    user_id: int,
    request: TierUpgradeRequest,
    db: Session = Depends(get_db)
):
    """
    Upgrade user to new tier.

    Tiers: starter ($29/mo), pro ($99/mo), enterprise ($299/mo)
    """
    tier_system = get_tier_system(db)
    tier_enum = Tier(request.new_tier)
    return await tier_system.upgrade_tier(user_id, tier_enum, request.payment_method_id)


# ============================================================================
# ACTION EXECUTOR ENDPOINTS
# ============================================================================

@router.post("/action/preview")
async def preview_action(
    request: ActionPreviewRequest,
    db: Session = Depends(get_db)
):
    """
    Preview what an action will do (without executing).

    Returns:
    - Action description
    - Impact
    - Reversibility
    - Estimated time
    - Requires confirmation
    """
    executor = get_action_executor(db)
    action_type = ActionType(request.action_type)
    return await executor.preview_action(action_type, request.params)


@router.post("/action/execute")
async def execute_action(
    request: ActionExecuteRequest,
    db: Session = Depends(get_db)
):
    """
    Execute one-click action.

    Actions:
    - deploy_product
    - pause_campaign
    - discontinue_product
    - adjust_price
    - create_campaign
    - reply_email

    Returns:
    - Action ID (for undo)
    - Status
    - Result
    - Undo availability
    """
    executor = get_action_executor(db)
    action_type = ActionType(request.action_type)
    return await executor.execute_action(action_type, request.params, request.user_id)


@router.post("/action/undo/{action_id}")
async def undo_action(
    action_id: int,
    db: Session = Depends(get_db)
):
    """
    Undo a previously executed action.
    """
    executor = get_action_executor(db)
    return await executor.undo_action(action_id)


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def intelligence_health():
    """
    Health check for Intelligence Core.
    """
    return {
        "status": "healthy",
        "modules": {
            "unified_context": "active",
            "briefing_engine": "active",
            "grade_reasoning": "active",
            "progress_flow": "active",
            "tier_system": "active",
            "action_executor": "active"
        },
        "message": "Intelligence Core is operational"
    }
