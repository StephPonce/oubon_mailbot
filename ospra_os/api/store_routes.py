"""
Store Management API Routes - GROK RECOMMENDATION #11
======================================================

Multi-store selector with cross-store learning capabilities.

Endpoints:
- GET /api/stores - List all user stores
- GET /api/stores/{store_id} - Get single store details
- POST /api/stores - Create new store
- PATCH /api/stores/{store_id}/status - Update store status
- POST /api/stores/generate-learnings - Generate cross-store insights
- GET /api/stores/{store_id}/insights - Get cross-store recommendations
- POST /api/stores/insights/{learning_id}/apply - Apply a learning
- POST /api/stores/insights/{learning_id}/dismiss - Dismiss a learning
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

from ospra_os.database import get_db
from ospra_os.database.multi_store_models import User
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.services.store_service import StoreService


router = APIRouter(prefix="/api/stores", tags=["Stores"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class StoreCreate(BaseModel):
    """Request model for creating a new store"""
    store_name: str = Field(..., description="Store display name")
    store_url: str = Field(..., description="Store URL")
    platform: str = Field(..., description="Platform type (shopify, amazon, woocommerce)")
    credentials: Dict[str, Any] = Field(..., description="Platform-specific credentials")
    niche: Optional[str] = Field(None, description="Store niche (e.g., fitness, smart_home)")


class StoreStatusUpdate(BaseModel):
    """Request model for updating store status"""
    status: str = Field(..., description="New status (active, paused, disconnected, error)")
    sync_error: Optional[str] = Field(None, description="Error message if status is error")


class StoreResponse(BaseModel):
    """Response model for store data"""
    id: int
    store_name: str
    store_url: str
    platform: str
    status: str
    niche: Optional[str]
    pending_actions_count: int
    total_revenue: float
    monthly_revenue: float
    total_orders: int
    conversion_rate: float
    total_products: int
    last_sync: Optional[str]
    sync_error: Optional[str]
    created_at: str


class InsightResponse(BaseModel):
    """Response model for cross-store insight"""
    id: int
    learning_type: str
    source_store_name: str
    source_store_niche: Optional[str]
    product_name: str
    product_category: Optional[str]
    source_conversion_rate: float
    source_revenue: float
    source_orders: int
    niche_match_score: float
    insight: str
    recommendation: str
    confidence_score: float
    projected_conversion_rate: Optional[float]
    projected_monthly_revenue: Optional[float]
    projected_roi: Optional[float]
    status: str
    created_at: str


# ============================================================================
# STORE MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("", response_model=List[StoreResponse])
async def list_stores(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all stores for the current user.

    Returns stores with status, metrics, and pending actions count.
    """
    service = StoreService(db)
    stores = service.get_user_stores(current_user.id)
    return stores


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(
    store_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information for a specific store.

    Requires store ownership.
    """
    service = StoreService(db)
    store = service.get_store(store_id, current_user.id)

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or access denied"
        )

    return store


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_store(
    store_data: StoreCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new store for the current user.

    Supports Shopify, Amazon, and WooCommerce platforms.
    New stores start in 'setup' status.
    """
    service = StoreService(db)

    try:
        new_store = service.create_store(
            user_id=current_user.id,
            store_name=store_data.store_name,
            store_url=store_data.store_url,
            platform=store_data.platform,
            credentials=store_data.credentials,
            niche=store_data.niche,
        )
        return new_store
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{store_id}/status", response_model=Dict[str, Any])
async def update_store_status(
    store_id: int,
    status_update: StoreStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update store status.

    Valid statuses: active, paused, disconnected, error, setup
    """
    service = StoreService(db)

    updated_store = service.update_store_status(
        store_id=store_id,
        user_id=current_user.id,
        status=status_update.status,
        sync_error=status_update.sync_error
    )

    if not updated_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or access denied"
        )

    return updated_store


# ============================================================================
# CROSS-STORE LEARNING ENDPOINTS
# ============================================================================

@router.post("/generate-learnings", response_model=Dict[str, int])
async def generate_cross_store_learnings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate cross-store learning insights.

    Analyzes performance across all user stores and generates
    recommendations to apply successful products/strategies from
    Store A to Store B (when niches match).

    Example: "Yoga mats convert at 4.2% in Fitness First,
             recommend for Health Hub."
    """
    service = StoreService(db)
    learnings_count = service.generate_cross_store_learnings(current_user.id)

    return {
        "learnings_generated": learnings_count
    }


@router.get("/{store_id}/insights", response_model=List[InsightResponse])
async def get_cross_store_insights(
    store_id: int,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get cross-store learning insights for a specific store.

    Returns recommendations from other stores with matching niches.
    Insights show projected conversion rates and revenue based on
    performance in source stores.
    """
    service = StoreService(db)

    # Verify store ownership
    store = service.get_store(store_id, current_user.id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or access denied"
        )

    insights = service.get_cross_store_insights(
        store_id=store_id,
        user_id=current_user.id,
        limit=limit
    )

    return insights


@router.post("/insights/{learning_id}/apply", response_model=Dict[str, Any])
async def apply_cross_store_learning(
    learning_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a cross-store learning as applied.

    This indicates the user has implemented the recommendation
    (e.g., added the product to their target store).
    """
    service = StoreService(db)

    result = service.apply_cross_store_learning(
        learning_id=learning_id,
        user_id=current_user.id
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning not found or access denied"
        )

    return result


@router.post("/insights/{learning_id}/dismiss", response_model=Dict[str, Any])
async def dismiss_cross_store_learning(
    learning_id: int,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dismiss a cross-store learning recommendation.

    Optionally provide a reason for dismissal (e.g., "Product not relevant to niche").
    """
    service = StoreService(db)

    result = service.dismiss_cross_store_learning(
        learning_id=learning_id,
        user_id=current_user.id,
        reason=reason
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning not found or access denied"
        )

    return result


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health", tags=["Health"])
async def store_service_health():
    """
    Health check for store service.
    """
    return {
        "status": "healthy",
        "service": "stores",
        "features": {
            "multi_store_support": True,
            "cross_store_learning": True,
            "platforms": ["shopify", "amazon", "woocommerce"],
        }
    }
