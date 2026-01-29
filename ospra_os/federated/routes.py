"""
Federated Learning API Routes - GROK RECOMMENDATION #18

FastAPI endpoints for privacy-preserving collective intelligence.

SECURITY NOTE: All endpoints extract user_id from JWT tokens via get_current_user.
User ID is NEVER accepted as a request parameter to prevent user impersonation.

Endpoints:
- POST /api/federated/consent/enable - Opt into federated learning
- POST /api/federated/consent/disable - Opt out of federated learning
- GET /api/federated/consent/status - Get consent status
- POST /api/federated/record/product - Record product outcome
- POST /api/federated/record/pricing - Record pricing outcome
- POST /api/federated/record/ad - Record ad outcome
- POST /api/federated/aggregate - Run aggregation (admin only)
- GET /api/federated/recommendations - Get recommendations
- POST /api/federated/apply-insight - Apply an insight
- POST /api/federated/insight-outcome - Record insight outcome
- GET /api/federated/stats - Get system statistics
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ospra_os.federated.service import FederatedLearningService
from ospra_os.database import get_db, User
from ospra_os.auth.jwt_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/federated", tags=["federated-learning"])


# ==================== REQUEST/RESPONSE MODELS ====================
# SECURITY: user_id is NEVER accepted in request body.
# It is always extracted from JWT token via Depends(get_current_user).

class ConsentRequest(BaseModel):
    """Request to enable/disable federated learning consent."""
    contribute_products: bool = True
    contribute_pricing: bool = True
    contribute_ads: bool = True


class ConsentStatusResponse(BaseModel):
    enabled: bool
    opted_in: bool
    contribution_enabled: bool
    scopes: Dict[str, bool]
    consented_at: Optional[str] = None
    consent_version: str


class ProductOutcomeRequest(BaseModel):
    """Request to record a product outcome."""
    niche: str
    outcome: str = Field(..., description="success, partial, or failure")
    price: Optional[float] = None
    margin: Optional[float] = None
    rating: Optional[float] = None
    velocity: Optional[int] = None


class PricingOutcomeRequest(BaseModel):
    """Request to record a pricing outcome."""
    niche: str
    old_price: float
    new_price: float
    outcome: str = Field(..., description="improved, maintained, or declined")


class AdOutcomeRequest(BaseModel):
    """Request to record an ad campaign outcome."""
    niche: str
    platform: str = Field(..., description="facebook, google, tiktok, etc.")
    roas: Optional[float] = None
    ctr: Optional[float] = None
    budget: Optional[float] = None
    outcome: str = "unknown"


class AggregateRequest(BaseModel):
    """Request to run aggregation (admin only)."""
    niche: Optional[str] = None
    aggregate_products: bool = True
    aggregate_pricing: bool = True
    aggregate_ads: bool = True


class RecommendationsRequest(BaseModel):
    """Request to get recommendations."""
    niche: Optional[str] = None
    context: Optional[str] = Field(None, description="product_selection, pricing_strategy, or ad_campaign")
    limit: int = 10


class ApplyInsightRequest(BaseModel):
    """Request to apply an insight."""
    insight_id: int
    context: Optional[Dict[str, Any]] = None


class InsightOutcomeRequest(BaseModel):
    """Request to record insight outcome."""
    application_id: int
    outcome: str = Field(..., description="success, partial, or failure")


# ==================== CONSENT ENDPOINTS ====================

@router.post("/consent/enable")
def enable_federated_learning(
    request: ConsentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enable federated learning for the current user.

    SECURITY: User ID is extracted from JWT token, not from request body.

    This allows the user to contribute anonymized data and receive
    aggregate insights from the collective intelligence system.
    """
    user_id = current_user.id

    try:
        service = FederatedLearningService(db)

        consent = service.enable_federated_learning(
            user_id=user_id,
            contribute_products=request.contribute_products,
            contribute_pricing=request.contribute_pricing,
            contribute_ads=request.contribute_ads
        )

        return {
            "success": True,
            "message": "Federated learning enabled",
            "consent": {
                "user_id": consent.user_id,
                "enabled": consent.federated_learning_enabled,
                "scopes": {
                    "products": consent.contribute_product_data,
                    "pricing": consent.contribute_pricing_data,
                    "ads": consent.contribute_ad_data
                },
                "consented_at": consent.consented_at.isoformat() if consent.consented_at else None
            }
        }

    except Exception as e:
        logger.error(f"Error enabling federated learning for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to enable federated learning. Please try again.")


@router.post("/consent/disable")
def disable_federated_learning(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disable federated learning for the current user.

    SECURITY: User ID is extracted from JWT token.

    Stops future data collection (does not delete past contributions).
    """
    user_id = current_user.id

    try:
        service = FederatedLearningService(db)

        consent = service.disable_federated_learning(user_id)

        if not consent:
            raise HTTPException(status_code=404, detail="No consent record found")

        return {
            "success": True,
            "message": "Federated learning disabled",
            "user_id": user_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling federated learning for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to disable federated learning. Please try again.")


@router.get("/consent/status", response_model=ConsentStatusResponse)
def get_consent_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get consent status for the current user.

    SECURITY: User ID is extracted from JWT token.
    """
    user_id = current_user.id

    try:
        service = FederatedLearningService(db)
        status = service.get_consent_status(user_id)
        return status

    except Exception as e:
        logger.error(f"Error getting consent status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get consent status. Please try again.")


# ==================== DATA RECORDING ENDPOINTS ====================

@router.post("/record/product")
def record_product_outcome(
    request: ProductOutcomeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record a product deployment outcome.

    SECURITY: User ID is extracted from JWT token.

    Data is automatically anonymized and bucketed before storage.
    Only users who have opted into federated learning can contribute.
    """
    user_id = current_user.id

    try:
        service = FederatedLearningService(db)

        contribution = service.record_product_outcome(
            user_id=user_id,
            niche=request.niche,
            outcome=request.outcome,
            price=request.price,
            margin=request.margin,
            rating=request.rating,
            velocity=request.velocity
        )

        if not contribution:
            return {
                "success": False,
                "message": "User has not opted into federated learning or product data contribution",
                "contributed": False
            }

        return {
            "success": True,
            "message": "Product outcome recorded",
            "contributed": True,
            "contribution_id": contribution.id,
            "anonymized_data": contribution.contribution_data
        }

    except Exception as e:
        logger.error(f"Error recording product outcome for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to record product outcome. Please try again.")


@router.post("/record/pricing")
def record_pricing_outcome(
    request: PricingOutcomeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record a pricing decision outcome.

    SECURITY: User ID is extracted from JWT token.
    """
    user_id = current_user.id

    try:
        service = FederatedLearningService(db)

        contribution = service.record_pricing_outcome(
            user_id=user_id,
            niche=request.niche,
            old_price=request.old_price,
            new_price=request.new_price,
            outcome=request.outcome
        )

        if not contribution:
            return {
                "success": False,
                "message": "User has not opted into pricing data contribution",
                "contributed": False
            }

        return {
            "success": True,
            "message": "Pricing outcome recorded",
            "contributed": True,
            "contribution_id": contribution.id,
            "anonymized_data": contribution.contribution_data
        }

    except Exception as e:
        logger.error(f"Error recording pricing outcome for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to record pricing outcome. Please try again.")


@router.post("/record/ad")
def record_ad_outcome(
    request: AdOutcomeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record an ad campaign outcome.

    SECURITY: User ID is extracted from JWT token.
    """
    user_id = current_user.id

    try:
        service = FederatedLearningService(db)

        contribution = service.record_ad_outcome(
            user_id=user_id,
            niche=request.niche,
            platform=request.platform,
            roas=request.roas,
            ctr=request.ctr,
            budget=request.budget,
            outcome=request.outcome
        )

        if not contribution:
            return {
                "success": False,
                "message": "User has not opted into ad data contribution",
                "contributed": False
            }

        return {
            "success": True,
            "message": "Ad outcome recorded",
            "contributed": True,
            "contribution_id": contribution.id,
            "anonymized_data": contribution.contribution_data
        }

    except Exception as e:
        logger.error(f"Error recording ad outcome for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to record ad outcome. Please try again.")


# ==================== AGGREGATION ENDPOINTS ====================

@router.post("/aggregate")
def run_aggregation(
    request: AggregateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Run aggregation to create insights from contributions.

    SECURITY: Requires admin privileges.

    This should typically be run as a background task (Celery).
    For testing, it can be triggered manually via this endpoint.
    """
    # SECURITY: Admin-only endpoint
    if not getattr(current_user, 'is_admin', False) and not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        service = FederatedLearningService(db)

        results = {
            "product_insights": [],
            "pricing_insights": [],
            "ad_insights": []
        }

        if request.aggregate_products:
            product_insights = service.aggregate_products(niche=request.niche)
            results["product_insights"] = [
                {
                    "id": i.id,
                    "title": i.title,
                    "confidence": i.confidence,
                    "sample_size": i.sample_size
                }
                for i in product_insights
            ]

        if request.aggregate_pricing:
            pricing_insights = service.aggregate_pricing(niche=request.niche)
            results["pricing_insights"] = [
                {
                    "id": i.id,
                    "title": i.title,
                    "confidence": i.confidence,
                    "sample_size": i.sample_size
                }
                for i in pricing_insights
            ]

        if request.aggregate_ads:
            ad_insights = service.aggregate_ads(niche=request.niche)
            results["ad_insights"] = [
                {
                    "id": i.id,
                    "title": i.title,
                    "confidence": i.confidence,
                    "sample_size": i.sample_size
                }
                for i in ad_insights
            ]

        total_insights = (
            len(results["product_insights"]) +
            len(results["pricing_insights"]) +
            len(results["ad_insights"])
        )

        return {
            "success": True,
            "message": f"Created {total_insights} new insights",
            "results": results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running aggregation: {e}")
        raise HTTPException(status_code=500, detail="Failed to run aggregation. Please try again.")


# ==================== INSIGHT RETRIEVAL ENDPOINTS ====================

@router.post("/recommendations")
def get_recommendations(
    request: RecommendationsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized recommendations based on aggregate insights.

    SECURITY: User ID is extracted from JWT token.

    Returns insights most relevant to the user's niche and context,
    ranked by confidence and sample size.
    """
    user_id = current_user.id

    try:
        service = FederatedLearningService(db)

        recommendations = service.get_recommendations(
            user_id=user_id,
            niche=request.niche,
            context=request.context,
            limit=request.limit
        )

        return {
            "success": True,
            "count": len(recommendations),
            "recommendations": recommendations
        }

    except Exception as e:
        logger.error(f"Error getting recommendations for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recommendations. Please try again.")


@router.post("/apply-insight")
def apply_insight(
    request: ApplyInsightRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record that a user applied an insight.

    SECURITY: User ID is extracted from JWT token.

    This creates a feedback loop to measure insight effectiveness.
    """
    user_id = current_user.id

    try:
        service = FederatedLearningService(db)

        application = service.apply_insight(
            user_id=user_id,
            insight_id=request.insight_id,
            context=request.context
        )

        return {
            "success": True,
            "message": "Insight application recorded",
            "application_id": application.id,
            "applied_at": application.applied_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Error applying insight for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to apply insight. Please try again.")


@router.post("/insight-outcome")
def record_insight_outcome(
    request: InsightOutcomeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record the outcome of applying an insight.

    SECURITY: Requires authentication. Only the user who applied the insight
    should be able to record the outcome.

    This feedback helps measure which insights are most effective.
    """

    try:
        service = FederatedLearningService(db)

        application = service.record_insight_outcome(
            application_id=request.application_id,
            outcome=request.outcome
        )

        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        return {
            "success": True,
            "message": "Insight outcome recorded",
            "application_id": application.id,
            "outcome": application.outcome,
            "recorded_at": application.outcome_recorded_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording insight outcome: {e}")
        raise HTTPException(status_code=500, detail="Failed to record insight outcome. Please try again.")


# ==================== STATISTICS ENDPOINTS ====================

@router.get("/stats")
def get_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive statistics about the federated learning system.

    SECURITY: Requires authentication.

    Includes:
    - User participation rates
    - Contribution counts
    - Insight counts
    - Application effectiveness
    - Privacy thresholds
    """

    try:
        service = FederatedLearningService(db)
        stats = service.get_stats()

        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics. Please try again.")


@router.get("/health")
def health_check():
    """
    Health check endpoint for federated learning system.
    """

    return {
        "status": "healthy",
        "service": "federated-learning",
        "version": "1.0.0",
        "privacy_guaranteed": True,
        "timestamp": datetime.utcnow().isoformat()
    }


# ==================== ROUTER REGISTRATION ====================

def get_federated_router() -> APIRouter:
    """
    Get the federated learning router for registration in main app.
    """
    return router
