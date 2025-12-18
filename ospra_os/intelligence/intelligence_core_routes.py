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
- 🧠 OSPRA DISCOVERY (REAL cross-source intelligence)
- 🎨 DALL-E Image Generation
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

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


class DiscoverRequest(BaseModel):
    niches: Optional[List[str]] = None
    max_per_niche: int = 10
    generate_images: bool = False


class ImageGenerateRequest(BaseModel):
    product_name: str
    style: str = "professional"
    count: int = 1


class BannerGenerateRequest(BaseModel):
    product_name: str
    campaign_type: str = "social"


# ============================================================================
# BRIEFING ENDPOINTS
# ============================================================================

@router.get("/briefing/morning")
async def get_morning_briefing(
    user_id: Optional[int] = Query(None),
    store_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    engine = get_briefing_engine(db)
    return await engine.generate_morning_briefing(user_id, store_id)


@router.get("/briefing/on-demand")
async def get_on_demand_briefing(
    user_id: Optional[int] = Query(None),
    store_id: Optional[int] = Query(None),
    focus: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    engine = get_briefing_engine(db)
    return {
        "briefing_text": await engine.generate_on_demand_briefing(user_id, store_id, focus),
        "focus_area": focus,
        "timestamp": datetime.now().isoformat()
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
    builder = get_unified_context_builder(db)
    return await builder.build_full_context(user_id, store_id, force_refresh)


@router.get("/context/summary")
async def get_context_summary(
    user_id: Optional[int] = Query(None),
    store_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    builder = get_unified_context_builder(db)
    context = await builder.build_full_context(user_id, store_id)
    return context.get("summary", {})


@router.post("/context/invalidate")
async def invalidate_context_cache(
    user_id: Optional[int] = Query(None),
    store_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    builder = get_unified_context_builder(db)
    builder.invalidate_cache(user_id, store_id)
    return {"success": True, "message": "Cache invalidated"}


# ============================================================================
# PRODUCT GRADING ENDPOINTS
# ============================================================================

@router.get("/grade/product/{product_id}")
async def grade_product(product_id: int, db: Session = Depends(get_db)):
    engine = get_grade_reasoning_engine(db)
    return await engine.calculate_product_grade(product_id)


@router.post("/grade/bulk")
async def grade_products_bulk(product_ids: List[int], db: Session = Depends(get_db)):
    engine = get_grade_reasoning_engine(db)
    results = []
    for product_id in product_ids:
        try:
            grade = await engine.calculate_product_grade(product_id)
            results.append(grade)
        except Exception as e:
            results.append({"product_id": product_id, "error": str(e)})
    return {"grades": results, "total": len(results)}


# ============================================================================
# PROGRESS FLOW ENDPOINTS
# ============================================================================

@router.get("/progress/product/{product_id}")
async def get_product_progress(product_id: int, db: Session = Depends(get_db)):
    tracker = get_progress_tracker(db)
    return await tracker.get_product_progress(product_id)


@router.post("/progress/product/{product_id}/advance")
async def advance_product_stage(
    product_id: int,
    new_stage: str,
    note: Optional[str] = None,
    db: Session = Depends(get_db)
):
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
    tracker = get_progress_tracker(db)
    stage_enum = LifecycleStage(stage)
    return await tracker.get_products_by_stage(stage_enum, user_id, store_id, limit)


# ============================================================================
# TIER SYSTEM ENDPOINTS
# ============================================================================

@router.get("/tier/info")
async def get_tier_info(user_id: int = Query(...), db: Session = Depends(get_db)):
    tier_system = get_tier_system(db)
    return await tier_system.get_tier_info(user_id)


@router.get("/tier/check-feature")
async def check_feature_access(
    user_id: int = Query(...),
    feature: str = Query(...),
    db: Session = Depends(get_db)
):
    tier_system = get_tier_system(db)
    has_access = await tier_system.check_feature_access(user_id, feature)
    return {"user_id": user_id, "feature": feature, "has_access": has_access}


@router.get("/tier/check-limit")
async def check_usage_limit(
    user_id: int = Query(...),
    limit_type: str = Query(...),
    current_usage: int = Query(...),
    db: Session = Depends(get_db)
):
    tier_system = get_tier_system(db)
    return await tier_system.check_limit(user_id, limit_type, current_usage)


@router.post("/tier/upgrade")
async def upgrade_tier(
    user_id: int,
    request: TierUpgradeRequest,
    db: Session = Depends(get_db)
):
    tier_system = get_tier_system(db)
    tier_enum = Tier(request.new_tier)
    return await tier_system.upgrade_tier(user_id, tier_enum, request.payment_method_id)


# ============================================================================
# ACTION EXECUTOR ENDPOINTS
# ============================================================================

@router.post("/action/preview")
async def preview_action(request: ActionPreviewRequest, db: Session = Depends(get_db)):
    executor = get_action_executor(db)
    action_type = ActionType(request.action_type)
    return await executor.preview_action(action_type, request.params)


@router.post("/action/execute")
async def execute_action(request: ActionExecuteRequest, db: Session = Depends(get_db)):
    executor = get_action_executor(db)
    action_type = ActionType(request.action_type)
    return await executor.execute_action(action_type, request.params, request.user_id)


@router.post("/action/undo/{action_id}")
async def undo_action(action_id: int, db: Session = Depends(get_db)):
    executor = get_action_executor(db)
    return await executor.undo_action(action_id)


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def intelligence_health():
    return {
        "status": "healthy",
        "modules": {
            "unified_context": "active",
            "briefing_engine": "active",
            "grade_reasoning": "active",
            "progress_flow": "active",
            "tier_system": "active",
            "action_executor": "active",
            "ospra_discovery": "active",
            "dalle_images": "active"
        },
        "message": "Intelligence Core is operational"
    }


# ============================================================================
# 🧠 OSPRA INTELLIGENCE DISCOVERY (FULLY INTEGRATED)
# ============================================================================

_ospra_engine = None

def _get_ospra_engine():
    global _ospra_engine
    if _ospra_engine is None:
        try:
            from ospra_os.intelligence.ospra_engine import OspraIntelligenceEngine
            database_url = os.getenv('DATABASE_URL')
            _ospra_engine = OspraIntelligenceEngine(database_url=database_url)
            logger.info("✅ Ospra Intelligence Engine initialized")
        except Exception as e:
            logger.warning(f"⚠️ Ospra Engine not available: {e}")
            _ospra_engine = None
    return _ospra_engine


@router.post("/discover")
async def discover_winning_products(request: DiscoverRequest):
    """
    🔍 DISCOVER WINNING PRODUCTS
    
    Uses ALL connected sources:
    - Google Trends
    - TikTok
    - AliExpress
    - xAI/Grok (Twitter)
    - Reddit
    - Amazon
    - Apify
    
    Only products scoring 7.5+ are saved.
    """
    engine = _get_ospra_engine()
    niches = request.niches or ['smart_home', 'fitness', 'tech_accessories']
    
    if not engine:
        raise HTTPException(status_code=503, detail="Intelligence engine not available")
    
    try:
        winners = await engine.discover_winners(
            niches=niches,
            max_per_niche=request.max_per_niche,
            save_to_db=True,
            generate_images=request.generate_images
        )
        
        return {
            "success": True,
            "message": f"Found {len(winners)} winning products (score 7.5+)",
            "winners": [w.to_dict() for w in winners],
            "count": len(winners),
            "stats": engine.get_stats(),
            "engine": "OSPRA_INTELLIGENCE_V5",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discover/stats")
async def get_discovery_stats():
    engine = _get_ospra_engine()
    if not engine:
        return {"status": "unavailable", "engine_type": "NONE"}
    return {
        "status": "ready",
        "stats": engine.get_stats(),
        "engine_type": "OSPRA_INTELLIGENCE_V5",
        "min_score_threshold": 7.5
    }


@router.get("/discover/health")
async def discovery_engine_health():
    engine = _get_ospra_engine()
    if not engine:
        return {"status": "unavailable", "components": {}}
    
    stats = engine.get_stats()
    return {
        "status": "operational",
        "components": stats.get('connected_sources', {}),
        "engine_type": "OSPRA_INTELLIGENCE_V5"
    }


@router.get("/discover/niches")
async def get_available_discovery_niches():
    engine = _get_ospra_engine()
    
    default_niches = {
        'smart_home': ['smart plug wifi', 'led strip lights', 'smart sensor'],
        'fitness': ['resistance bands', 'yoga mat', 'massage gun'],
        'tech_accessories': ['wireless charger', 'phone stand', 'usb hub'],
        'kitchen': ['air fryer accessories', 'kitchen organizer', 'spice rack'],
        'beauty': ['led face mask', 'facial massager', 'makeup organizer'],
        'pet': ['pet camera', 'automatic feeder', 'dog water fountain'],
        'car': ['car phone mount', 'dash cam', 'car vacuum'],
        'home_office': ['desk organizer', 'monitor stand', 'ergonomic mouse'],
    }
    
    niches = engine.NICHE_KEYWORDS if engine and hasattr(engine, 'NICHE_KEYWORDS') else default_niches
    
    return {
        "success": True,
        "niches": [
            {
                "id": niche_id,
                "name": niche_id.replace('_', ' ').title(),
                "keyword_count": len(keywords),
                "sample_keywords": keywords[:3]
            }
            for niche_id, keywords in niches.items()
        ],
        "total": len(niches)
    }


# ============================================================================
# 🎨 DALL-E IMAGE GENERATION
# ============================================================================

@router.post("/images/generate")
async def generate_product_images(request: ImageGenerateRequest):
    """Generate AI product lifestyle images using DALL-E 3"""
    try:
        from ospra_os.media.ai_image_generator import AIImageGenerator
        
        generator = AIImageGenerator()
        
        if generator.provider != 'dalle':
            raise HTTPException(
                status_code=503,
                detail="DALL-E not configured. Set OPENAI_API_KEY."
            )
        
        if request.count == 1:
            image_path = await generator.generate_lifestyle_image(
                product_name=request.product_name,
                style=request.style
            )
            images = [image_path] if image_path else []
        else:
            images = await generator.generate_product_carousel(
                product_name=request.product_name,
                product_image_url="",
                count=min(request.count, 4)
            )
        
        return {
            "success": True,
            "product_name": request.product_name,
            "style": request.style,
            "images": images,
            "count": len(images),
            "provider": "dall-e-3",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/images/banner")
async def generate_marketing_banner(request: BannerGenerateRequest):
    """Generate marketing banner for ads"""
    try:
        from ospra_os.media.ai_image_generator import AIImageGenerator
        
        generator = AIImageGenerator()
        
        if generator.provider != 'dalle':
            raise HTTPException(status_code=503, detail="DALL-E not configured")
        
        image_path = await generator.generate_marketing_banner(
            product_name=request.product_name,
            campaign_type=request.campaign_type
        )
        
        return {
            "success": True,
            "product_name": request.product_name,
            "campaign_type": request.campaign_type,
            "image": image_path,
            "provider": "dall-e-3",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Banner generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/images/status")
async def get_image_generation_status():
    """Check DALL-E status"""
    try:
        from ospra_os.media.ai_image_generator import AIImageGenerator
        generator = AIImageGenerator()
        return {
            "available": generator.provider == 'dalle',
            "provider": generator.provider,
            "openai_configured": bool(generator.openai_key)
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


# ============================================================================
# 🔗 ALL CONNECTIONS STATUS
# ============================================================================

@router.get("/connections")
async def get_all_connection_status():
    """Get status of ALL intelligence connections"""
    engine = _get_ospra_engine()
    
    if not engine:
        return {
            "status": "engine_not_initialized",
            "connections": {
                "google_trends": False,
                "aliexpress": False,
                "tiktok": False,
                "xai_twitter": False,
                "apify": False,
                "reddit": False,
                "amazon": False,
                "dalle": False,
            },
            "total_connected": 0,
            "total_available": 8
        }
    
    stats = engine.get_stats()
    connected = stats.get('connected_sources', {})
    
    return {
        "status": "operational",
        "connections": connected,
        "total_connected": sum(1 for v in connected.values() if v),
        "total_available": len(connected),
        "discovery_stats": {
            "trends_checked": stats.get('trends_checked', 0),
            "products_found": stats.get('products_found', 0),
            "products_validated": stats.get('products_validated', 0),
            "products_passed": stats.get('products_passed', 0),
            "pass_rate": stats.get('pass_rate', 0),
        }
    }
