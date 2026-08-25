"""
HYBRID LEARNING API ROUTES

Endpoints for the AI learning system.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from ospra_os.auth.jwt_auth import get_current_user
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from ospra_os.database import SessionLocal
from ospra_os.learning.hybrid_learning_engine import get_learning_engine

logger = logging.getLogger(__name__)
# SECURITY (2026-08): router-level auth. This router had NO Depends()
# anywhere. GET /personal/{user_id} exposed any tenant's model weights, GET
# /events returned all tenants' learning events, and POST /custom-weights,
# /personal/learn, /feedback and /record-ad-metrics allowed ANONYMOUS WRITES
# into any user's AI scoring model. Handlers still take user_id from the URL —
# that must be replaced with the token's user before this is considered done.
router = APIRouter(
    prefix="/api/learning",
    tags=["Learning"],
    dependencies=[Depends(get_current_user)],
)


# ==================== REQUEST MODELS ====================

class SaleData(BaseModel):
    product_id: str
    product_name: str
    niche: str
    price: float
    units_sold: int
    revenue: float
    predicted_score: float
    date: str


class LearnRequest(BaseModel):
    user_id: int
    sales: List[SaleData]


class ScoreRequest(BaseModel):
    score: float
    niche: str
    price: float
    user_id: Optional[int] = None


class CustomWeightsRequest(BaseModel):
    user_id: int
    weights: Dict[str, float]


class FeedbackRequest(BaseModel):
    user_id: int
    product_id: str
    action: str  # "recommended", "added_to_store", "ignored", "first_sale", "30_day_performance"
    details: Optional[Dict[str, Any]] = None


# ==================== GLOBAL BRAIN ENDPOINTS ====================

@router.get("/global/weights")
async def get_global_weights():
    """
    Get current Global Brain weights.
    
    Available to ALL tiers - this is the network effect.
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        weights = engine.get_global_weights()
        return weights
    finally:
        db.close()


@router.post("/global/contribute")
async def contribute_to_global(request: LearnRequest, current_user=Depends(get_current_user)):
    """
    Contribute sales data to Global Brain learning.
    
    ALL tiers can contribute (and benefit from) global learning.
    Higher tiers have higher contribution weight.
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        
        sales_data = [sale.dict() for sale in request.sales]
        result = await engine.learn_global(sales_data, current_user.id)
        
        return result
    finally:
        db.close()


# ==================== PERSONAL LAYER ENDPOINTS ====================

@router.get("/personal/{user_id}")
async def get_personal_weights(user_id: int, current_user=Depends(get_current_user)):
    """
    Get personal learning weights for the AUTHENTICATED user.

    SECURITY (2026-08): `user_id` in the path is IGNORED — the identity comes
    from the token. It used to be honoured, so any authenticated tenant could
    read any other tenant's model weights, best niches and price ranges by
    changing a number in the URL. The path parameter is kept only so existing
    frontend URLs keep working; a mismatch is logged.

    Requires Soar tier or higher.
    """
    if user_id != current_user.id:
        logger.warning(
            "[SECURITY] /learning/personal path user_id=%s ignored; serving "
            "authenticated user %s", user_id, current_user.id
        )
    user_id = current_user.id
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        weights = engine.get_personal_weights(user_id)
        
        if not weights:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return weights
    finally:
        db.close()


@router.post("/personal/learn")
async def learn_personal(request: LearnRequest, current_user=Depends(get_current_user)):
    """
    Update personal learning layer for a user.
    
    Requires Soar tier or higher.
    Stratosphere users get accelerated learning (2x).
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        
        sales_data = [sale.dict() for sale in request.sales]
        result = await engine.learn_personal(current_user.id, sales_data)
        
        return result
    finally:
        db.close()


# ==================== FEEDBACK ENDPOINTS ====================

@router.post("/feedback")
async def record_feedback(request: FeedbackRequest, current_user=Depends(get_current_user)):
    """
    Record user action feedback for learning.

    This endpoint tracks the full product lifecycle:
    - "recommended": Claude suggested this product
    - "added_to_store": User added product to their store
    - "ignored": User rejected recommendation
    - "first_sale": Product made first sale
    - "30_day_performance": Performance after 30 days

    Example:
    {
        "user_id": 1,
        "product_id": "abc123",
        "action": "first_sale",
        "details": {
            "predicted_score": 85,
            "actual_revenue": 459.99,
            "units_sold": 12,
            "days_to_first_sale": 3
        }
    }
    """
    from datetime import datetime
    from ospra_os.learning.hybrid_learning_engine import LearningEvent

    db = SessionLocal()
    try:
        # Record the feedback event
        event = LearningEvent(
            user_id=current_user.id,
            event_type=request.action,
            details={
                "product_id": request.product_id,
                **(request.details or {})
            }
        )
        db.add(event)
        db.commit()

        # If it's a sale event, trigger learning
        if request.action in ["first_sale", "30_day_performance"] and request.details:
            engine = get_learning_engine(db)

            # Convert to sale format for learning
            sale_data = [{
                "product_id": request.product_id,
                "predicted_score": request.details.get("predicted_score", 0),
                "revenue": request.details.get("actual_revenue", 0),
                "units_sold": request.details.get("units_sold", 0),
                "niche": request.details.get("niche", "unknown"),
                "price": request.details.get("price", 0),
                "product_name": request.details.get("product_name", ""),
                "date": datetime.now(timezone.utc).isoformat()
            }]

            # Trigger learning cycle
            await engine.learn_global(sale_data, current_user.id)
            await engine.learn_personal(current_user.id, sale_data)

        # PostHog activation funnel (task #38) — fire FIRST_SALE on the
        # `first_sale` action. PostHog dedupes per-user-per-event server-side
        # for clean funnel reporting.
        if request.action == "first_sale":
            try:
                from ospra_os.observability.posthog_client import (
                    capture as posthog_capture,
                    FunnelEvent,
                )
                details = request.details or {}
                posthog_capture(
                    current_user.id,
                    FunnelEvent.FIRST_SALE,
                    properties={
                        "product_id": request.product_id,
                        "revenue": details.get("actual_revenue", 0),
                        "units_sold": details.get("units_sold", 0),
                        "days_to_first_sale": details.get("days_to_first_sale"),
                    },
                )
            except Exception as _e:
                # Telemetry failures must never break the feedback path.
                pass

        return {
            "success": True,
            "message": f"Feedback recorded: {request.action}",
            "event_id": event.id if hasattr(event, 'id') else None
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record feedback. Please try again."
        )
    finally:
        db.close()


@router.get("/insights/{user_id}")
async def get_learning_insights(user_id: int, current_user=Depends(get_current_user)):
    """
    Get actionable learning insights for a user.

    Returns what the AI has learned about this user's preferences:
    - Best performing niches
    - Optimal price ranges
    - Success patterns
    - Recommendations to avoid
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)

        # SECURITY: path user_id ignored — insights are the caller's own.
        user_id = current_user.id
        personal = engine.get_personal_weights(user_id)
        global_weights = engine.get_global_weights()

        if not personal:
            # Return global insights only
            return {
                "user_id": user_id,
                "tier": "global_only",
                "insights": {
                    "global_brain": global_weights,
                    "personal_patterns": None,
                    "message": "Upgrade to Soar tier for personalized insights"
                }
            }

        # Build actionable insights
        insights = {
            "user_id": user_id,
            "learning_cycles": personal.learning_cycles,
            "products_analyzed": personal.sales_analyzed,
            "ai_accuracy": f"{personal.accuracy_rate * 100:.1f}%",
            "best_niches": personal.best_performing_niches[:5] if personal.best_performing_niches else [],
            "optimal_price_range": personal.optimal_price_range,
            "peak_selling_days": personal.peak_selling_days,
            "recommendations": []
        }

        # Generate recommendations based on patterns
        if personal.best_performing_niches:
            insights["recommendations"].append(
                f"Focus on {', '.join(personal.best_performing_niches[:3])} - your strongest niches"
            )

        if personal.optimal_price_range:
            min_p = personal.optimal_price_range.get('min', 0)
            max_p = personal.optimal_price_range.get('max', 0)
            if min_p > 0 and max_p > 0:
                insights["recommendations"].append(
                    f"Target ${min_p:.0f}-${max_p:.0f} price range for best conversion"
                )

        return insights

    finally:
        db.close()


# ==================== SCORING ENDPOINTS ====================

@router.post("/score/adjusted")
async def get_adjusted_score(request: ScoreRequest, current_user=Depends(get_current_user)):
    """
    Get AI-adjusted score for a product.
    
    Uses Global Brain for all users.
    Uses Personal Layer for Soar+ users (if available).
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        
        product = {
            "score": request.score,
            "niche": request.niche,
            "price": request.price
        }
        
        result = await engine.get_adjusted_score(product, current_user.id)
        
        return result
    finally:
        db.close()


# ==================== STRATOSPHERE ENDPOINTS ====================

@router.post("/custom-weights")
async def set_custom_weights(request: CustomWeightsRequest, current_user=Depends(get_current_user)):
    """
    Set custom scoring weights.
    
    Stratosphere tier ONLY.
    
    Example weights (must sum to 1.0):
    {
        "google_trends_weight": 0.30,
        "reddit_mentions_weight": 0.10,
        "aliexpress_orders_weight": 0.35,
        "price_competitiveness_weight": 0.15,
        "trend_velocity_weight": 0.10
    }
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        
        result = await engine.set_custom_weights(current_user.id, request.weights)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.get("reason", "Failed to set custom weights")
            )
        
        return result
    finally:
        db.close()


# ==================== AD PERFORMANCE ENDPOINTS ====================

@router.post("/record-ad-metrics")
async def record_ad_performance(
    product_id: str,
    metrics: Dict[str, Any],
    current_user=Depends(get_current_user),
):
    """
    Record ad performance metrics for a product.

    This endpoint tracks advertising performance to help the AI learn which
    products get good ROAS and which advertising strategies work best.

    Example:
    ```json
    {
        "user_id": 1,
        "product_id": "prod_12345",
        "metrics": {
            "platform": "facebook",  // facebook, google, tiktok, etc.
            "campaign_id": "camp_67890",
            "spend": 150.00,
            "impressions": 45000,
            "clicks": 1200,
            "conversions": 35,
            "revenue": 1750.00,
            "date_start": "2025-12-01",
            "date_end": "2025-12-07",
            "niche": "smart_home",
            "product_name": "Smart WiFi LED Bulb",
            "price": 29.99
        }
    }
    ```

    Calculated metrics:
    - CTR (Click-Through Rate): clicks / impressions
    - CPC (Cost Per Click): spend / clicks
    - Conversion Rate: conversions / clicks
    - CPA (Cost Per Acquisition): spend / conversions
    - ROAS (Return on Ad Spend): revenue / spend
    """
    from datetime import datetime
    from ospra_os.database import SessionLocal
    from ospra_os.learning.hybrid_learning_engine import LearningEvent

    db = SessionLocal()
    try:
        # Calculate derived metrics
        spend = float(metrics.get("spend", 0))
        impressions = int(metrics.get("impressions", 0))
        clicks = int(metrics.get("clicks", 0))
        conversions = int(metrics.get("conversions", 0))
        revenue = float(metrics.get("revenue", 0))

        # Calculate performance ratios
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cpc = (spend / clicks) if clicks > 0 else 0
        conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0
        cpa = (spend / conversions) if conversions > 0 else 0
        roas = (revenue / spend) if spend > 0 else 0

        # Create learning event
        event = LearningEvent(
            # SECURITY: identity from the token, never the request. This used
            # to accept a caller-supplied user_id, so anyone could write ad
            # performance into ANOTHER tenant's learning model and steer their
            # product scoring.
            user_id=current_user.id,
            event_type="ad_performance",
            details={
                "product_id": product_id,  # Include product_id in details
                **metrics,  # Include all raw metrics
                # Add calculated metrics
                "ctr": round(ctr, 2),
                "cpc": round(cpc, 2),
                "conversion_rate": round(conversion_rate, 2),
                "cpa": round(cpa, 2),
                "roas": round(roas, 2),
                "source": "ad_metrics_api",
                "recorded_at": datetime.now(timezone.utc).isoformat()
            }
        )
        db.add(event)
        db.commit()

        return {
            "success": True,
            "message": "Ad performance recorded",
            "calculated_metrics": {
                "ctr": f"{ctr:.2f}%",
                "cpc": f"${cpc:.2f}",
                "conversion_rate": f"{conversion_rate:.2f}%",
                "cpa": f"${cpa:.2f}",
                "roas": f"{roas:.2f}x"
            }
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record ad performance. Please try again."
        )
    finally:
        db.close()


# ==================== REPORT ENDPOINTS ====================

@router.get("/report")
async def get_learning_report(current_user=Depends(get_current_user)):
    """
    Get comprehensive learning report.
    
    Shows Global Brain stats for everyone.
    Shows Personal Layer stats for Soar+ users.
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        report = await engine.get_learning_report(current_user.id)
        return report
    finally:
        db.close()


@router.get("/health")
async def learning_health():
    """Health check for learning system"""
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        weights = engine.get_global_weights()

        return {
            "status": "healthy",
            "global_brain": {
                "learning_cycles": weights.get("learning_cycles", 0),
                "users_contributing": weights.get("total_users_contributing", 0),
                "accuracy": weights.get("accuracy", {}).get("accuracy_rate", 0)
            }
        }
    finally:
        db.close()


# ==================== MANUAL ANALYSIS TRIGGERS ====================

@router.post("/analyze/global")
async def trigger_global_analysis():
    """
    Manually trigger global pattern analysis.

    This runs the same calculation as the daily scheduled job.
    Useful for:
    - Immediately updating patterns after seeding data
    - Testing the analysis pipeline
    - On-demand recalculation

    Returns:
        Status of the analysis job
    """
    try:
        from ospra_os.learning.analysis_jobs import calculate_global_patterns

        await calculate_global_patterns()

        return {
            "success": True,
            "message": "Global pattern analysis completed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Global analysis failed. Please try again."
        )


@router.post("/analyze/personal/{user_id}")
async def trigger_personal_analysis(user_id: int, current_user=Depends(get_current_user)):
    """
    Manually trigger personal pattern analysis for a specific user.

    Args:
        user_id: User ID to analyze

    Returns:
        Status of the analysis job
    """
    # SECURITY: the path user_id is IGNORED — analysis always runs for the
    # authenticated caller. Honouring it let one tenant trigger (and shape)
    # another tenant's personal model.
    if user_id != current_user.id:
        logger.warning(
            "[SECURITY] /learning/analyze/personal path user_id=%s ignored; "
            "analysing authenticated user %s", user_id, current_user.id
        )
    user_id = current_user.id

    try:
        from ospra_os.learning.analysis_jobs import calculate_personal_patterns

        await calculate_personal_patterns(user_id)

        return {
            "success": True,
            "message": f"Personal pattern analysis completed for user {user_id}",
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Personal analysis failed. Please try again."
        )


@router.post("/analyze/all-users")
async def trigger_all_users_analysis():
    """
    Manually trigger personal pattern analysis for all users.

    This runs the same calculation as the daily scheduled job.

    Returns:
        Status of the analysis job
    """
    try:
        from ospra_os.learning.analysis_jobs import calculate_all_personal_patterns

        await calculate_all_personal_patterns()

        return {
            "success": True,
            "message": "Personal pattern analysis completed for all users",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis failed. Please try again."
        )


# ==================== LEARNING STATUS & SCHEDULER ====================

@router.get("/status")
async def get_learning_status():
    """
    Get comprehensive self-learning system status.
    
    Shows:
    - Whether learning is active
    - How many cycles have run
    - Recent learning events
    - Accuracy metrics
    - Scheduler status
    """
    try:
        # Try to get full status from scheduler
        from ospra_os.learning.learning_scheduler import get_learning_status as get_status
        return await get_status()
    except ImportError as ie:
        # Scheduler module not available
        pass
    except Exception as e:
        # Log but continue to fallback
        import logging
        logging.warning(f"Scheduler status failed: {e}")
    
    # Fallback: Try to get basic status from database
    db = None
    try:
        db = SessionLocal()
        engine = get_learning_engine(db)
        weights = engine.get_global_weights()
        
        return {
            "status": "active" if weights.get("learning_cycles", 0) > 0 else "pending_data",
            "learning_cycles": weights.get("learning_cycles", 0),
            "total_sales_analyzed": weights.get("total_sales_analyzed", 0),
            "accuracy": weights.get("accuracy", {}),
            "last_updated": weights.get("last_updated"),
            "scheduler_running": False,
            "note": "Using fallback status (scheduler not running)"
        }
    except Exception as e:
        logger.error(f"Learning status check failed: {e}")
        # Database not available or tables don't exist
        return {
            "status": "not_initialized",
            "learning_cycles": 0,
            "total_sales_analyzed": 0,
            "accuracy": {},
            "error": "Learning system not initialized",
            "fix": "Run database migrations or initialize learning tables"
        }
    finally:
        if db:
            db.close()


@router.post("/trigger-now")
async def trigger_learning_now():
    """
    Manually trigger a learning cycle immediately.
    
    Useful for testing or after importing sales data.
    """
    try:
        from ospra_os.learning.learning_scheduler import run_daily_learning_cycle
        
        await run_daily_learning_cycle()
        
        return {
            "success": True,
            "message": "Learning cycle completed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Learning scheduler module not available"
        )
    except Exception as e:
        logger.error(f"Learning trigger failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Learning trigger failed. Please try again."
        )


@router.get("/events")
async def get_recent_learning_events(limit: int = 50):
    """
    Get recent learning events (sales, cancellations, etc.)
    
    Useful for debugging and verifying webhooks are recording.
    """
    db = None
    try:
        from ospra_os.database import AILearningEvent
        
        db = SessionLocal()
        events = db.query(AILearningEvent).order_by(
            AILearningEvent.timestamp.desc()
        ).limit(limit).all()
        
        return {
            "count": len(events),
            "events": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "product_id": e.product_id,
                    "details": e.details,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None
                }
                for e in events
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get learning events: {e}")
        return {
            "count": 0,
            "events": [],
            "error": "Failed to retrieve learning events",
            "note": "AILearningEvent table may not exist. Run migrations."
        }
    finally:
        if db:
            db.close()


# REMOVED 2026-08: POST /api/learning/simulate-sale
#
# This endpoint was UNAUTHENTICATED (this router declares no auth dependency)
# and wrote AILearningEvent(user_id=1, event_type="sale") — "sale" is in
# ORGANIC_SALE_EVENT_TYPES (ospra_os/database/performance_models.py), the tuple
# the provenance guard treats as REAL revenue. So any anonymous caller could
# inject fabricated sales that the G4 learning aggregations counted as organic
# outcomes and fed into weight adjustments.
#
# That re-opened the exact door migration 008 closed: 008 purged the seeded
# 'historical_sale' batch precisely so the learning system would be
# organic-only. The guard keys on event TYPE, not on details["source"], so the
# "source": "simulation" marker this endpoint set was invisible to it — the
# rows are indistinguishable from real sales after the fact.
#
# If a sale-injection hook is ever needed again it MUST: require
# get_current_user, write event_type="simulated_sale", and that type must be
# added to SEEDED_EVENT_TYPES so the aggregations exclude it by construction.

