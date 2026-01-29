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

UPDATED: GROK RECOMMENDATION #14 - Multi-Tenant Isolation
- Uses tenant-scoped database for automatic data isolation
- Audit logging for compliance tracking
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import List, Dict, Optional, Any, Literal
import re

from ospra_os.tenancy import get_tenant_db, get_tenant, log_success, log_failure
from ospra_os.tenancy.queries import TenantScopedSession
from ospra_os.tenancy.context import TenantContext
from ospra_os.services.store_service import StoreService


router = APIRouter(prefix="/api/stores", tags=["Stores"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class StoreCreate(BaseModel):
    """Request model for creating a new store

    SECURITY: Validated fields with proper length limits and format checks.
    """
    store_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Store display name"
    )
    store_url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Store URL"
    )
    platform: Literal["shopify", "amazon", "woocommerce", "etsy", "ebay"] = Field(
        ...,
        description="Platform type"
    )
    credentials: Dict[str, str] = Field(
        ...,
        description="Platform-specific credentials (key-value pairs)"
    )
    niche: Optional[str] = Field(
        None,
        max_length=100,
        description="Store niche (e.g., fitness, smart_home)"
    )

    @field_validator('store_url')
    @classmethod
    def validate_store_url(cls, v: str) -> str:
        """Validate store URL format"""
        # Basic URL validation - must have scheme or be a domain
        url_pattern = re.compile(
            r'^https?://[^\s<>"{}|\\^`\[\]]+$|^[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}$'
        )
        if not url_pattern.match(v):
            raise ValueError('Invalid store URL format')
        return v

    @field_validator('credentials')
    @classmethod
    def validate_credentials(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate credentials structure and size"""
        if len(v) > 20:
            raise ValueError('Too many credential fields (max 20)')
        for key, value in v.items():
            if len(key) > 100:
                raise ValueError(f'Credential key too long: {key[:20]}...')
            if len(str(value)) > 1000:
                raise ValueError(f'Credential value too long for key: {key}')
        return v


class StoreStatusUpdate(BaseModel):
    """Request model for updating store status

    SECURITY: Status field restricted to valid enum values.
    """
    status: Literal["active", "paused", "disconnected", "error"] = Field(
        ...,
        description="New status"
    )
    sync_error: Optional[str] = Field(
        None,
        max_length=1000,
        description="Error message if status is error"
    )


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
    tenant_db: TenantScopedSession = Depends(get_tenant_db),
    tenant: TenantContext = Depends(get_tenant)
):
    """
    List all stores for the current user.

    Returns stores with status, metrics, and pending actions count.
    **Tenant-isolated**: Automatically filtered to current user.
    """
    service = StoreService(tenant_db.raw_session)
    stores = service.get_user_stores(tenant.user_id)
    return stores


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(
    store_id: int,
    tenant_db: TenantScopedSession = Depends(get_tenant_db),
    tenant: TenantContext = Depends(get_tenant)
):
    """
    Get detailed information for a specific store.

    Requires store ownership.
    **Tenant-isolated**: Can only access own stores.
    """
    service = StoreService(tenant_db.raw_session)
    store = service.get_store(store_id, tenant.user_id)

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or access denied"
        )

    return store


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_store(
    store_data: StoreCreate,
    request: Request,
    tenant_db: TenantScopedSession = Depends(get_tenant_db),
    tenant: TenantContext = Depends(get_tenant)
):
    """
    Create a new store for the current user.

    Supports Shopify, Amazon, and WooCommerce platforms.
    New stores start in 'setup' status.
    **Tenant-isolated**: Store automatically assigned to current user.
    **Audit logged**: Store creation tracked for compliance.
    """
    service = StoreService(tenant_db.raw_session)

    try:
        new_store = service.create_store(
            user_id=tenant.user_id,
            store_name=store_data.store_name,
            store_url=store_data.store_url,
            platform=store_data.platform,
            credentials=store_data.credentials,
            niche=store_data.niche,
        )

        # Audit log for compliance
        log_success(
            db=tenant_db.raw_session,
            action="store.create",
            resource_type="Store",
            resource_id=new_store.get("id"),
            request=request,
            metadata={
                "store_name": store_data.store_name,
                "platform": store_data.platform,
                "niche": store_data.niche
            }
        )

        return new_store
    except ValueError as e:
        log_failure(
            db=tenant_db.raw_session,
            action="store.create",
            resource_type="Store",
            request=request,
            error_message="Store creation failed"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Store operation failed. Please try again."
        )


@router.patch("/{store_id}/status", response_model=Dict[str, Any])
async def update_store_status(
    store_id: int,
    status_update: StoreStatusUpdate,
    request: Request,
    tenant_db: TenantScopedSession = Depends(get_tenant_db),
    tenant: TenantContext = Depends(get_tenant)
):
    """
    Update store status.

    Valid statuses: active, paused, disconnected, error, setup
    **Tenant-isolated**: Can only update own stores.
    **Audit logged**: Status changes tracked for compliance.
    """
    service = StoreService(tenant_db.raw_session)

    updated_store = service.update_store_status(
        store_id=store_id,
        user_id=tenant.user_id,
        status=status_update.status,
        sync_error=status_update.sync_error
    )

    if not updated_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or access denied"
        )

    # Audit log
    log_success(
        db=tenant_db.raw_session,
        action="store.status_update",
        resource_type="Store",
        resource_id=store_id,
        request=request,
        metadata={
            "new_status": status_update.status,
            "sync_error": status_update.sync_error
        }
    )

    return updated_store


# ============================================================================
# CROSS-STORE LEARNING ENDPOINTS
# ============================================================================

@router.post("/generate-learnings", response_model=Dict[str, int])
async def generate_cross_store_learnings(
    tenant_db: TenantScopedSession = Depends(get_tenant_db),
    tenant: TenantContext = Depends(get_tenant)
):
    """
    Generate cross-store learning insights.

    Analyzes performance across all user stores and generates
    recommendations to apply successful products/strategies from
    Store A to Store B (when niches match).

    Example: "Yoga mats convert at 4.2% in Fitness First,
             recommend for Health Hub."
    **Tenant-isolated**: Only analyzes your own stores.
    """
    service = StoreService(tenant_db.raw_session)
    learnings_count = service.generate_cross_store_learnings(tenant.user_id)

    return {
        "learnings_generated": learnings_count
    }


@router.get("/{store_id}/insights", response_model=List[InsightResponse])
async def get_cross_store_insights(
    store_id: int,
    limit: int = 10,
    tenant_db: TenantScopedSession = Depends(get_tenant_db),
    tenant: TenantContext = Depends(get_tenant)
):
    """
    Get cross-store learning insights for a specific store.

    Returns recommendations from other stores with matching niches.
    Insights show projected conversion rates and revenue based on
    performance in source stores.
    **Tenant-isolated**: Only sees insights from your own stores.
    """
    service = StoreService(tenant_db.raw_session)

    # Verify store ownership
    store = service.get_store(store_id, tenant.user_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or access denied"
        )

    insights = service.get_cross_store_insights(
        store_id=store_id,
        user_id=tenant.user_id,
        limit=limit
    )

    return insights


@router.post("/insights/{learning_id}/apply", response_model=Dict[str, Any])
async def apply_cross_store_learning(
    learning_id: int,
    request: Request,
    tenant_db: TenantScopedSession = Depends(get_tenant_db),
    tenant: TenantContext = Depends(get_tenant)
):
    """
    Mark a cross-store learning as applied.

    This indicates the user has implemented the recommendation
    (e.g., added the product to their target store).
    **Tenant-isolated**: Can only apply your own learnings.
    **Audit logged**: Application tracked for analytics.
    """
    service = StoreService(tenant_db.raw_session)

    result = service.apply_cross_store_learning(
        learning_id=learning_id,
        user_id=tenant.user_id
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning not found or access denied"
        )

    # Audit log
    log_success(
        db=tenant_db.raw_session,
        action="store.learning_applied",
        resource_type="CrossStoreLearning",
        resource_id=learning_id,
        request=request
    )

    return result


@router.post("/insights/{learning_id}/dismiss", response_model=Dict[str, Any])
async def dismiss_cross_store_learning(
    learning_id: int,
    request: Request,
    reason: Optional[str] = None,
    tenant_db: TenantScopedSession = Depends(get_tenant_db),
    tenant: TenantContext = Depends(get_tenant)
):
    """
    Dismiss a cross-store learning recommendation.

    Optionally provide a reason for dismissal (e.g., "Product not relevant to niche").
    **Tenant-isolated**: Can only dismiss your own learnings.
    **Audit logged**: Dismissal tracked for improving recommendations.
    """
    service = StoreService(tenant_db.raw_session)

    result = service.dismiss_cross_store_learning(
        learning_id=learning_id,
        user_id=tenant.user_id,
        reason=reason
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning not found or access denied"
        )

    # Audit log
    log_success(
        db=tenant_db.raw_session,
        action="store.learning_dismissed",
        resource_type="CrossStoreLearning",
        resource_id=learning_id,
        request=request,
        metadata={"reason": reason}
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
