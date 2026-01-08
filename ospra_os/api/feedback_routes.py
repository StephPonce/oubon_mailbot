"""
Feedback Loop API - G4: Complete Feedback Loop
================================================

FastAPI endpoints for the G4 feedback loop system that enables the AI
to learn from real sales performance data.

This is the KILLER FEATURE that transforms Ospra from "AI that guesses"
to "AI that proves it works with real data."

Endpoints:
- POST /api/feedback/sync               - Trigger sales data sync
- GET  /api/feedback/performance/{id}    - Get product performance
- GET  /api/feedback/performance         - Get all product performance
- POST /api/feedback/evaluate            - Evaluate pending outcomes
- GET  /api/feedback/outcomes            - Get recommendation outcomes
- GET  /api/feedback/learning-stats      - Get AI learning statistics [STAR] KEY
- POST /api/feedback/process-learning    - Process learning events
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database.multi_store_models import User
from ospra_os.database import get_session, Store, Product
from sqlalchemy.orm import Session

from ospra_os.services.sales_sync_service import SalesSyncService
from ospra_os.services.outcome_service import OutcomeService
from ospra_os.services.learning_processor import LearningProcessor

router = APIRouter(prefix="/api/feedback", tags=["G4: Feedback Loop"])


# ==================== RESPONSE MODELS ====================

class SyncResponse(BaseModel):
    success: bool
    message: str
    stores_synced: int
    products_updated: int
    orders_fetched: int
    errors: List[str]


class ProductPerformanceResponse(BaseModel):
    product_id: int
    product_name: str
    niche: Optional[str]
    days: int
    total_orders: int
    total_units_sold: int
    total_revenue: float
    total_profit: float
    avg_daily_orders: float
    avg_daily_revenue: float
    avg_margin: float
    daily_snapshots: int


class OutcomeResponse(BaseModel):
    outcome_id: int
    product_id: int
    product_name: str
    confidence_score: float
    projected_revenue: float
    actual_revenue: Optional[float]
    outcome: str  # pending, exceptional, success, moderate, poor, failure
    outcome_score: Optional[float]
    accuracy_score: Optional[float]
    tracking_days: int
    created_at: datetime


class NichePerformance(BaseModel):
    niche: str
    products_deployed: int
    success_rate: float
    total_revenue: float
    score_adjustment: float  # -10 to +10


class LearningStatsResponse(BaseModel):
    user_id: int
    success_rate: float
    avg_accuracy: float
    total_recommendations: int
    successful: int
    failed: int
    current_weights: Dict[str, float]
    weight_version: int
    last_updated: Optional[datetime]
    niche_performance: List[NichePerformance]
    total_learning_events: int
    positive_signals: int
    negative_signals: int
    learning_ratio: float


class ProcessLearningResponse(BaseModel):
    success: bool
    events_processed: int
    users_updated: int
    weight_changes: Dict[str, Any]


class EvaluateResponse(BaseModel):
    success: bool
    outcomes_evaluated: int
    learning_events_created: int
    results: List[Dict[str, Any]]


# ==================== ENDPOINTS ====================

@router.post("/sync", response_model=SyncResponse)
async def sync_sales_data(
    days_back: int = Query(default=1, ge=1, le=30, description="Number of days to sync"),
    store_id: Optional[int] = Query(default=None, description="Specific store ID to sync"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Trigger sales data sync from Shopify/Amazon.

    This is the FIRST STEP in the feedback loop - syncing real sales data
    so the AI can see what actually works.

    Args:
        days_back: Number of days of historical data to sync (1-30)
        store_id: Optional specific store to sync (defaults to all user's stores)

    Returns:
        Sync results including orders fetched and products updated
    """
    try:
        service = SalesSyncService(db)

        if store_id:
            # Sync specific store
            store = db.query(Store).filter(
                Store.id == store_id,
                Store.user_id == user.id
            ).first()

            if not store:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Store {store_id} not found"
                )

            result = await service.sync_store(store, days_back)

            return SyncResponse(
                success=result["success"],
                message=f"Synced {days_back} days from {store.store_name}",
                stores_synced=1,
                products_updated=result.get("products_updated", 0),
                orders_fetched=result.get("orders_fetched", 0),
                errors=[result.get("error")] if result.get("error") else []
            )
        else:
            # Sync all user's stores
            results = await service.sync_all_stores(user_id=user.id, days_back=days_back)

            total_products = sum(r.get("products_updated", 0) for r in results if r["success"])
            total_orders = sum(r.get("orders_fetched", 0) for r in results if r["success"])
            errors = [r.get("error") for r in results if not r["success"]]

            return SyncResponse(
                success=len([r for r in results if r["success"]]) > 0,
                message=f"Synced {len(results)} stores for {days_back} days",
                stores_synced=len(results),
                products_updated=total_products,
                orders_fetched=total_orders,
                errors=errors
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing sales data: {str(e)}"
        )


@router.get("/performance/{product_id}", response_model=ProductPerformanceResponse)
def get_product_performance(
    product_id: int,
    days: int = Query(default=30, ge=1, le=365, description="Number of days to aggregate"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Get performance summary for a specific product.

    Shows real sales data: orders, revenue, profit, margins.
    """
    try:
        # Verify product belongs to user
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.user_id == user.id
        ).first()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found"
            )

        service = SalesSyncService(db)
        summary = service.get_product_performance_summary(product_id, days)

        if summary.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=summary["error"]
            )

        return ProductPerformanceResponse(
            product_id=product_id,
            product_name=product.name or "Unknown",
            niche=product.niche,
            days=days,
            total_orders=summary["total_orders"],
            total_units_sold=summary["total_units_sold"],
            total_revenue=summary["total_revenue"],
            total_profit=summary["total_profit"],
            avg_daily_orders=summary["avg_daily_orders"],
            avg_daily_revenue=summary["avg_daily_revenue"],
            avg_margin=summary["avg_margin"],
            daily_snapshots=summary["daily_snapshots"]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving performance data: {str(e)}"
        )


@router.get("/performance", response_model=List[ProductPerformanceResponse])
def get_all_performance(
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Get performance summary for all user's products.
    """
    try:
        products = db.query(Product).filter(Product.user_id == user.id).all()
        service = SalesSyncService(db)

        results = []
        for product in products:
            summary = service.get_product_performance_summary(product.id, days)
            if not summary.get("error"):
                results.append(ProductPerformanceResponse(
                    product_id=product.id,
                    product_name=product.name or "Unknown",
                    niche=product.niche,
                    days=days,
                    total_orders=summary["total_orders"],
                    total_units_sold=summary["total_units_sold"],
                    total_revenue=summary["total_revenue"],
                    total_profit=summary["total_profit"],
                    avg_daily_orders=summary["avg_daily_orders"],
                    avg_daily_revenue=summary["avg_daily_revenue"],
                    avg_margin=summary["avg_margin"],
                    daily_snapshots=summary["daily_snapshots"]
                ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving performance data: {str(e)}"
        )


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_outcomes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Evaluate pending recommendation outcomes.

    This is STEP 2 of the feedback loop: comparing AI predictions to reality.
    """
    try:
        service = OutcomeService(db)
        results = await service.evaluate_outcomes(user_id=user.id)

        learning_events = sum(r.get("learning_events_created", 0) for r in results)

        return EvaluateResponse(
            success=True,
            outcomes_evaluated=len(results),
            learning_events_created=learning_events,
            results=results
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error evaluating outcomes: {str(e)}"
        )


@router.get("/outcomes", response_model=List[OutcomeResponse])
def get_outcomes(
    status_filter: Optional[str] = Query(default=None, description="Filter by status (pending, exceptional, success, etc.)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Get list of recommendation outcomes.

    Shows what AI predicted vs what actually happened.
    """
    try:
        from ospra_os.database import RecommendationOutcome

        query = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.user_id == user.id
        )

        if status_filter:
            query = query.filter(RecommendationOutcome.outcome == status_filter)

        outcomes = query.order_by(RecommendationOutcome.created_at.desc()).limit(100).all()

        results = []
        for outcome in outcomes:
            product = db.query(Product).filter(Product.id == outcome.product_id).first()

            tracking_days = 0
            if outcome.tracking_started_at:
                tracking_days = (datetime.now() - outcome.tracking_started_at).days

            results.append(OutcomeResponse(
                outcome_id=outcome.id,
                product_id=outcome.product_id,
                product_name=product.name if product else "Unknown",
                confidence_score=outcome.confidence_score,
                projected_revenue=outcome.projected_monthly_revenue or 0,
                actual_revenue=outcome.actual_total_revenue,
                outcome=outcome.outcome,
                outcome_score=outcome.outcome_score,
                accuracy_score=outcome.accuracy_score,
                tracking_days=tracking_days,
                created_at=outcome.created_at
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving outcomes: {str(e)}"
        )


@router.get("/learning-stats", response_model=LearningStatsResponse)
def get_learning_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Get AI learning statistics for the user.

    [STAR] THIS IS THE KILLER ENDPOINT [STAR]

    Returns:
    - Success rate: "AI has 78% success rate for you"
    - Current learned weights
    - Niche performance: "You succeed 85% in fitness, 45% in home décor"
    - Confidence calibration: "When AI says 80%, it's actually 82% accurate"

    This is what proves Ospra's value with REAL DATA.
    """
    try:
        processor = LearningProcessor(db)
        stats = processor.get_learning_stats(user.id)

        # Calculate success rate from outcomes
        from ospra_os.database import RecommendationOutcome

        total_outcomes = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.user_id == user.id,
            RecommendationOutcome.outcome != "pending"
        ).count()

        successful_outcomes = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.user_id == user.id,
            RecommendationOutcome.outcome.in_(["exceptional", "success"])
        ).count()

        failed_outcomes = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.user_id == user.id,
            RecommendationOutcome.outcome.in_(["poor", "failure"])
        ).count()

        success_rate = (successful_outcomes / total_outcomes * 100) if total_outcomes > 0 else 0

        # Calculate average accuracy
        from sqlalchemy import func
        avg_accuracy_query = db.query(func.avg(RecommendationOutcome.accuracy_score)).filter(
            RecommendationOutcome.user_id == user.id,
            RecommendationOutcome.accuracy_score != None
        ).scalar()

        avg_accuracy = avg_accuracy_query or 0

        # Convert niche performance to response format
        niche_performance_list = [
            NichePerformance(
                niche=np["niche"],
                products_deployed=np["products_deployed"],
                success_rate=np["success_rate"],
                total_revenue=np["total_revenue"],
                score_adjustment=np["score_adjustment"]
            )
            for np in stats["niche_performance"]
        ]

        return LearningStatsResponse(
            user_id=user.id,
            success_rate=round(success_rate, 1),
            avg_accuracy=round(avg_accuracy, 1),
            total_recommendations=total_outcomes,
            successful=successful_outcomes,
            failed=failed_outcomes,
            current_weights=stats["current_weights"],
            weight_version=stats["weight_version"],
            last_updated=stats["last_updated"],
            niche_performance=niche_performance_list,
            total_learning_events=stats["total_learning_events"],
            positive_signals=stats["positive_signals"],
            negative_signals=stats["negative_signals"],
            learning_ratio=stats["learning_ratio"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving learning stats: {str(e)}"
        )


@router.post("/process-learning", response_model=ProcessLearningResponse)
def process_learning_events(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Process pending learning events and update AI weights.

    This is STEP 3 of the feedback loop: applying the lessons learned.
    """
    try:
        processor = LearningProcessor(db)
        result = processor.process_pending_events(user_id=user.id)

        return ProcessLearningResponse(
            success=True,
            events_processed=result["events_processed"],
            users_updated=result["users_updated"],
            weight_changes=result["weight_changes"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing learning events: {str(e)}"
        )
