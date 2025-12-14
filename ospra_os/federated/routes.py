"""
Federated Learning API Routes - GROK RECOMMENDATION #18

FastAPI endpoints for privacy-preserving collective intelligence.

Endpoints:
- POST /api/federated/consent/enable - Opt into federated learning
- POST /api/federated/consent/disable - Opt out of federated learning
- GET /api/federated/consent/status - Get consent status
- POST /api/federated/record/product - Record product outcome
- POST /api/federated/record/pricing - Record pricing outcome
- POST /api/federated/record/ad - Record ad outcome
- POST /api/federated/aggregate - Run aggregation
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
from ospra_os.database.multi_store_models import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/federated", tags=["federated-learning"])


# ==================== REQUEST/RESPONSE MODELS ====================

class ConsentRequest(BaseModel):
    user_id: int
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
    user_id: int
    niche: str
    outcome: str = Field(..., description="success, partial, or failure")
    price: Optional[float] = None
    margin: Optional[float] = None
    rating: Optional[float] = None
    velocity: Optional[int] = None


class PricingOutcomeRequest(BaseModel):
    user_id: int
    niche: str
    old_price: float
    new_price: float
    outcome: str = Field(..., description="improved, maintained, or declined")


class AdOutcomeRequest(BaseModel):
    user_id: int
    niche: str
    platform: str = Field(..., description="facebook, google, tiktok, etc.")
    roas: Optional[float] = None
    ctr: Optional[float] = None
    budget: Optional[float] = None
    outcome: str = "unknown"


class AggregateRequest(BaseModel):
    niche: Optional[str] = None
    aggregate_products: bool = True
    aggregate_pricing: bool = True
    aggregate_ads: bool = True


class RecommendationsRequest(BaseModel):
    user_id: int
    niche: Optional[str] = None
    context: Optional[str] = Field(None, description="product_selection, pricing_strategy, or ad_campaign")
    limit: int = 10


class ApplyInsightRequest(BaseModel):
    user_id: int
    insight_id: int
    context: Optional[Dict[str, Any]] = None


class InsightOutcomeRequest(BaseModel):
    application_id: int
    outcome: str = Field(..., description="success, partial, or failure")


# ==================== CONSENT ENDPOINTS ====================

@router.post("/consent/enable")
def enable_federated_learning(
    request: ConsentRequest,
    db: Session = Depends(get_db)
):
    """
    Enable federated learning for a user.

    This allows the user to contribute anonymized data and receive
    aggregate insights from the collective intelligence system.
    """

    try:
        service = FederatedLearningService(db)

        consent = service.enable_federated_learning(
            user_id=request.user_id,
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
        logger.error(f"Error enabling federated learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/consent/disable")
def disable_federated_learning(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Disable federated learning for a user.

    Stops future data collection (does not delete past contributions).
    """

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
        logger.error(f"Error disabling federated learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consent/status", response_model=ConsentStatusResponse)
def get_consent_status(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get consent status for a user.
    """

    try:
        service = FederatedLearningService(db)
        status = service.get_consent_status(user_id)
        return status

    except Exception as e:
        logger.error(f"Error getting consent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== DATA RECORDING ENDPOINTS ====================

@router.post("/record/product")
def record_product_outcome(
    request: ProductOutcomeRequest,
    db: Session = Depends(get_db)
):
    """
    Record a product deployment outcome.

    Data is automatically anonymized and bucketed before storage.
    Only users who have opted into federated learning can contribute.
    """

    try:
        service = FederatedLearningService(db)

        contribution = service.record_product_outcome(
            user_id=request.user_id,
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
        logger.error(f"Error recording product outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record/pricing")
def record_pricing_outcome(
    request: PricingOutcomeRequest,
    db: Session = Depends(get_db)
):
    """
    Record a pricing decision outcome.
    """

    try:
        service = FederatedLearningService(db)

        contribution = service.record_pricing_outcome(
            user_id=request.user_id,
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
        logger.error(f"Error recording pricing outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record/ad")
def record_ad_outcome(
    request: AdOutcomeRequest,
    db: Session = Depends(get_db)
):
    """
    Record an ad campaign outcome.
    """

    try:
        service = FederatedLearningService(db)

        contribution = service.record_ad_outcome(
            user_id=request.user_id,
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
        logger.error(f"Error recording ad outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AGGREGATION ENDPOINTS ====================

@router.post("/aggregate")
def run_aggregation(
    request: AggregateRequest,
    db: Session = Depends(get_db)
):
    """
    Run aggregation to create insights from contributions.

    This should typically be run as a background task (Celery).
    For testing, it can be triggered manually via this endpoint.
    """

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

    except Exception as e:
        logger.error(f"Error running aggregation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== INSIGHT RETRIEVAL ENDPOINTS ====================

@router.post("/recommendations")
def get_recommendations(
    request: RecommendationsRequest,
    db: Session = Depends(get_db)
):
    """
    Get personalized recommendations based on aggregate insights.

    Returns insights most relevant to the user's niche and context,
    ranked by confidence and sample size.
    """

    try:
        service = FederatedLearningService(db)

        recommendations = service.get_recommendations(
            user_id=request.user_id,
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
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply-insight")
def apply_insight(
    request: ApplyInsightRequest,
    db: Session = Depends(get_db)
):
    """
    Record that a user applied an insight.

    This creates a feedback loop to measure insight effectiveness.
    """

    try:
        service = FederatedLearningService(db)

        application = service.apply_insight(
            user_id=request.user_id,
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
        logger.error(f"Error applying insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/insight-outcome")
def record_insight_outcome(
    request: InsightOutcomeRequest,
    db: Session = Depends(get_db)
):
    """
    Record the outcome of applying an insight.

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
        raise HTTPException(status_code=500, detail=str(e))


# ==================== STATISTICS ENDPOINTS ====================

@router.get("/stats")
def get_statistics(db: Session = Depends(get_db)):
    """
    Get comprehensive statistics about the federated learning system.

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
        raise HTTPException(status_code=500, detail=str(e))


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
