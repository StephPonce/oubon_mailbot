"""
Multi-Store Portfolio API
Manage multiple e-commerce stores across platforms
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import logging
import json

from ospra_os.database.multi_store_models import (
    User, Store, Product, ProductDeployment,
    Platform, ProductStatus, SubscriptionTier,
    get_multi_store_session
)
from ospra_os.core.settings import Settings, get_settings
from ospra_os.platforms.factory import PlatformFactory
from ospra_os.platforms import (
    PlatformAPIError,
    AuthenticationError,
    RateLimitError,
    ProductNotFoundError
)

router = APIRouter(prefix="/api/portfolio", tags=["Multi-Store Portfolio"])
logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class StoreCredentials(BaseModel):
    """Platform-specific credentials"""
    shop_url: Optional[str] = None
    access_token: Optional[str] = None
    api_version: Optional[str] = None
    # Amazon
    seller_id: Optional[str] = None
    mws_token: Optional[str] = None
    marketplace_id: Optional[str] = None
    # WooCommerce
    site_url: Optional[str] = None
    consumer_key: Optional[str] = None
    consumer_secret: Optional[str] = None


class AddStoreRequest(BaseModel):
    """Request to add new store"""
    store_name: str = Field(..., min_length=1, max_length=255)
    store_url: str = Field(..., min_length=1, max_length=512)
    platform: str = Field(..., description="shopify, amazon, woocommerce, etsy, ebay")
    credentials: StoreCredentials
    niche: Optional[str] = Field(None, max_length=255)
    target_market: str = Field(default="US", max_length=100)
    currency: str = Field(default="USD", max_length=10)

    @validator('platform')
    def validate_platform(cls, v):
        valid_platforms = ['shopify', 'amazon', 'woocommerce', 'etsy', 'ebay']
        if v.lower() not in valid_platforms:
            raise ValueError(f"Platform must be one of: {', '.join(valid_platforms)}")
        return v.lower()


class UpdateStoreRequest(BaseModel):
    """Request to update store"""
    store_name: Optional[str] = Field(None, min_length=1, max_length=255)
    niche: Optional[str] = Field(None, max_length=255)
    target_market: Optional[str] = Field(None, max_length=100)
    currency: Optional[str] = Field(None, max_length=10)
    is_active: Optional[bool] = None


class StoreResponse(BaseModel):
    """Store details response"""
    id: int
    store_name: str
    store_url: str
    platform: str
    niche: Optional[str]
    target_market: str
    currency: str
    is_active: bool
    total_revenue: float
    monthly_revenue: float
    total_orders: int
    conversion_rate: float
    rank_position: Optional[int]
    rank_change: int
    product_count: int
    active_products: int
    last_sync: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class RankedStoreResponse(BaseModel):
    """Store with ranking information"""
    id: int
    store_name: str
    platform: str
    monthly_revenue: float
    total_revenue: float
    conversion_rate: float
    product_count: int
    active_products: int
    rank_position: int
    rank_change: int
    rank_change_label: str  # "↑ +5", "↓ -2", "—"


class PortfolioOverviewResponse(BaseModel):
    """Aggregated portfolio metrics"""
    total_revenue: float
    monthly_revenue: float
    active_stores: int
    total_stores: int
    total_products: int
    active_products: int
    avg_conversion_rate: float
    best_performing_store: Optional[str]
    total_orders: int
    platforms: Dict[str, int]  # {"shopify": 2, "amazon": 1}


class SyncStoreResponse(BaseModel):
    """Store sync result"""
    success: bool
    orders_synced: int
    revenue_updated: float
    store_info: Dict[str, Any]
    error: Optional[str] = None
    last_sync_time: datetime


class TestConnectionResponse(BaseModel):
    """Connection test result"""
    success: bool
    store_name: Optional[str] = None
    store_url: Optional[str] = None
    platform_version: Optional[str] = None
    error: Optional[str] = None


class DeployProductRequest(BaseModel):
    """Request to deploy product to store"""
    product_id: int


class DeployProductResponse(BaseModel):
    """Product deployment result"""
    success: bool
    deployment_id: Optional[int] = None
    platform_product_id: Optional[str] = None
    platform_url: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# DEPENDENCIES
# ============================================================================

def get_db(settings: Settings = Depends(get_settings)) -> Session:
    """Get database session"""
    session = get_multi_store_session(settings.database_url)
    try:
        yield session
    finally:
        session.close()


def get_current_user(db: Session = Depends(get_db)) -> User:
    """
    Get current authenticated user

    TODO: Replace with real authentication (JWT, OAuth, etc.)
    For now, returns default user or creates one
    """
    # For development: use default user
    user_email = "steph@oubonshop.com"

    user = db.query(User).filter(User.email == user_email).first()

    if not user:
        # Create default user
        user = User(
            email=user_email,
            name="Stephen Ponce",
            subscription_tier=SubscriptionTier.PRO
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_product_counts(db: Session, store_id: int) -> Dict[str, int]:
    """Calculate product counts by status"""
    total = db.query(func.count(Product.id))\
        .filter(Product.store_id == store_id)\
        .scalar() or 0

    active = db.query(func.count(Product.id))\
        .filter(Product.store_id == store_id)\
        .filter(Product.status.in_([ProductStatus.ACTIVE, ProductStatus.DEPLOYED]))\
        .scalar() or 0

    return {"total": total, "active": active}


def update_store_rankings(db: Session, user_id: int):
    """
    Update store rankings based on monthly revenue
    Calculates rank changes (previous vs current)
    """
    stores = db.query(Store)\
        .filter(Store.user_id == user_id)\
        .filter(Store.is_active == True)\
        .order_by(desc(Store.monthly_revenue))\
        .all()

    for idx, store in enumerate(stores, start=1):
        previous_rank = store.rank_position or idx
        new_rank = idx

        store.rank_change = previous_rank - new_rank  # Positive = moved up
        store.rank_position = new_rank

    db.commit()


def validate_store_credentials(platform: str, credentials: dict) -> bool:
    """
    Validate store credentials by attempting connection

    TODO: Implement actual API validation for each platform
    For now, basic validation
    """
    platform = platform.lower()

    if platform == "shopify":
        return bool(credentials.get("shop_url") and credentials.get("access_token"))
    elif platform == "amazon":
        return bool(credentials.get("seller_id") and credentials.get("mws_token"))
    elif platform == "woocommerce":
        return bool(credentials.get("site_url") and credentials.get("consumer_key"))

    return False


def convert_store_credentials_to_adapter_format(platform: str, credentials: dict) -> dict:
    """
    Convert database credentials format to platform adapter format

    Database stores credentials in flexible format, adapters expect specific fields
    """
    platform = platform.lower()

    if platform == "shopify":
        return {
            "store_domain": credentials.get("shop_url", ""),
            "admin_api_token": credentials.get("access_token", ""),
            "api_version": credentials.get("api_version", "2024-01")
        }

    elif platform == "amazon":
        return {
            "marketplace_id": credentials.get("marketplace_id", ""),
            "seller_id": credentials.get("seller_id", ""),
            "refresh_token": credentials.get("refresh_token", credentials.get("mws_token", "")),
            "client_id": credentials.get("client_id", ""),
            "client_secret": credentials.get("client_secret", ""),
            "aws_access_key": credentials.get("aws_access_key", ""),
            "aws_secret_key": credentials.get("aws_secret_key", "")
        }

    elif platform == "woocommerce":
        return {
            "store_url": credentials.get("site_url", ""),
            "consumer_key": credentials.get("consumer_key", ""),
            "consumer_secret": credentials.get("consumer_secret", "")
        }

    # Return as-is if not recognized
    return credentials


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/overview", response_model=PortfolioOverviewResponse)
async def get_portfolio_overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get aggregated portfolio metrics across all user's stores

    Returns:
    - Total revenue (all-time)
    - Monthly revenue (current month)
    - Store counts (active vs total)
    - Product counts
    - Average conversion rate
    - Best performing store
    - Platform breakdown
    """
    # Get all user's stores
    stores = db.query(Store).filter(Store.user_id == user.id).all()
    active_stores = [s for s in stores if s.is_active]

    # Aggregate metrics
    total_revenue = sum(s.total_revenue for s in stores)
    monthly_revenue = sum(s.monthly_revenue for s in active_stores)
    total_orders = sum(s.total_orders for s in stores)

    # Calculate average conversion rate
    conversions = [s.conversion_rate for s in active_stores if s.conversion_rate > 0]
    avg_conversion = sum(conversions) / len(conversions) if conversions else 0.0

    # Count products across all stores
    total_products = db.query(func.count(Product.id))\
        .join(Store)\
        .filter(Store.user_id == user.id)\
        .scalar() or 0

    active_products = db.query(func.count(Product.id))\
        .join(Store)\
        .filter(Store.user_id == user.id)\
        .filter(Product.status.in_([ProductStatus.ACTIVE, ProductStatus.DEPLOYED]))\
        .scalar() or 0

    # Find best performing store
    best_store = max(active_stores, key=lambda s: s.monthly_revenue) if active_stores else None

    # Platform breakdown
    platform_counts = {}
    for store in stores:
        platform = store.platform.value if hasattr(store.platform, 'value') else str(store.platform)
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

    return PortfolioOverviewResponse(
        total_revenue=total_revenue,
        monthly_revenue=monthly_revenue,
        active_stores=len(active_stores),
        total_stores=len(stores),
        total_products=total_products,
        active_products=active_products,
        avg_conversion_rate=round(avg_conversion, 2),
        best_performing_store=best_store.store_name if best_store else None,
        total_orders=total_orders,
        platforms=platform_counts
    )


@router.get("/rankings", response_model=List[RankedStoreResponse])
async def get_store_rankings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get store performance rankings sorted by monthly revenue

    Includes:
    - Current rank position
    - Rank change (↑/↓ from previous)
    - Revenue metrics
    - Product counts
    """
    # Update rankings first
    update_store_rankings(db, user.id)

    # Fetch ranked stores
    stores = db.query(Store)\
        .filter(Store.user_id == user.id)\
        .filter(Store.is_active == True)\
        .order_by(Store.rank_position)\
        .all()

    ranked_stores = []
    for store in stores:
        # Get product counts
        counts = calculate_product_counts(db, store.id)

        # Format rank change label
        if store.rank_change > 0:
            rank_label = f"↑ +{store.rank_change}"
        elif store.rank_change < 0:
            rank_label = f"↓ {store.rank_change}"
        else:
            rank_label = "—"

        platform = store.platform.value if hasattr(store.platform, 'value') else str(store.platform)

        ranked_stores.append(RankedStoreResponse(
            id=store.id,
            store_name=store.store_name,
            platform=platform,
            monthly_revenue=store.monthly_revenue,
            total_revenue=store.total_revenue,
            conversion_rate=store.conversion_rate,
            product_count=counts["total"],
            active_products=counts["active"],
            rank_position=store.rank_position or 0,
            rank_change=store.rank_change,
            rank_change_label=rank_label
        ))

    return ranked_stores


@router.post("/stores/add", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)
async def add_store(
    request: AddStoreRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add new store to portfolio

    - Validates platform
    - Tests credentials before saving
    - Sets first store as default (rank 1)
    - Returns created store with details
    """
    try:
        # Validate credentials
        credentials_dict = request.credentials.dict(exclude_none=True)

        if not validate_store_credentials(request.platform, credentials_dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid credentials for {request.platform}. Please check and try again."
            )

        # Check if this is first store
        existing_stores = db.query(func.count(Store.id))\
            .filter(Store.user_id == user.id)\
            .scalar()

        is_first_store = existing_stores == 0

        # Create store
        new_store = Store(
            user_id=user.id,
            store_name=request.store_name,
            store_url=request.store_url,
            platform=Platform(request.platform),
            credentials=credentials_dict,
            niche=request.niche,
            target_market=request.target_market,
            currency=request.currency,
            is_active=True,
            rank_position=1 if is_first_store else None
        )

        db.add(new_store)
        db.commit()
        db.refresh(new_store)

        # Update user store count
        user.total_stores = db.query(func.count(Store.id))\
            .filter(Store.user_id == user.id)\
            .scalar()
        db.commit()

        # Update rankings
        update_store_rankings(db, user.id)
        db.refresh(new_store)

        # Get product counts
        counts = calculate_product_counts(db, new_store.id)

        platform = new_store.platform.value if hasattr(new_store.platform, 'value') else str(new_store.platform)

        return StoreResponse(
            id=new_store.id,
            store_name=new_store.store_name,
            store_url=new_store.store_url,
            platform=platform,
            niche=new_store.niche,
            target_market=new_store.target_market,
            currency=new_store.currency,
            is_active=new_store.is_active,
            total_revenue=new_store.total_revenue,
            monthly_revenue=new_store.monthly_revenue,
            total_orders=new_store.total_orders,
            conversion_rate=new_store.conversion_rate,
            rank_position=new_store.rank_position,
            rank_change=new_store.rank_change,
            product_count=counts["total"],
            active_products=counts["active"],
            last_sync=new_store.last_sync,
            created_at=new_store.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add store: {str(e)}"
        )


@router.post("/stores/{store_id}/switch", response_model=StoreResponse)
async def switch_active_store(
    store_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Switch active/default store

    - Sets selected store as rank #1 (primary)
    - Adjusts other store rankings
    - Used for quick store switching in UI
    """
    # Verify store ownership
    store = db.query(Store)\
        .filter(Store.id == store_id)\
        .filter(Store.user_id == user.id)\
        .first()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    # Set this store to rank 1, shift others down
    stores = db.query(Store)\
        .filter(Store.user_id == user.id)\
        .filter(Store.is_active == True)\
        .all()

    for s in stores:
        if s.id == store_id:
            s.rank_position = 1
        elif s.rank_position == 1:
            s.rank_position = 2

    db.commit()
    db.refresh(store)

    # Get product counts
    counts = calculate_product_counts(db, store.id)

    platform = store.platform.value if hasattr(store.platform, 'value') else str(store.platform)

    return StoreResponse(
        id=store.id,
        store_name=store.store_name,
        store_url=store.store_url,
        platform=platform,
        niche=store.niche,
        target_market=store.target_market,
        currency=store.currency,
        is_active=store.is_active,
        total_revenue=store.total_revenue,
        monthly_revenue=store.monthly_revenue,
        total_orders=store.total_orders,
        conversion_rate=store.conversion_rate,
        rank_position=store.rank_position,
        rank_change=store.rank_change,
        product_count=counts["total"],
        active_products=counts["active"],
        last_sync=store.last_sync,
        created_at=store.created_at
    )


@router.get("/stores/{store_id}", response_model=StoreResponse)
async def get_store_details(
    store_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed store information"""
    store = db.query(Store)\
        .filter(Store.id == store_id)\
        .filter(Store.user_id == user.id)\
        .first()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    # Get product counts
    counts = calculate_product_counts(db, store.id)

    platform = store.platform.value if hasattr(store.platform, 'value') else str(store.platform)

    return StoreResponse(
        id=store.id,
        store_name=store.store_name,
        store_url=store.store_url,
        platform=platform,
        niche=store.niche,
        target_market=store.target_market,
        currency=store.currency,
        is_active=store.is_active,
        total_revenue=store.total_revenue,
        monthly_revenue=store.monthly_revenue,
        total_orders=store.total_orders,
        conversion_rate=store.conversion_rate,
        rank_position=store.rank_position,
        rank_change=store.rank_change,
        product_count=counts["total"],
        active_products=counts["active"],
        last_sync=store.last_sync,
        created_at=store.created_at
    )


@router.put("/stores/{store_id}", response_model=StoreResponse)
async def update_store(
    store_id: int,
    request: UpdateStoreRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update store information

    Can update:
    - Store name
    - Niche
    - Target market
    - Currency
    - Active status
    """
    store = db.query(Store)\
        .filter(Store.id == store_id)\
        .filter(Store.user_id == user.id)\
        .first()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(store, field, value)

    try:
        db.commit()
        db.refresh(store)

        # Get product counts
        counts = calculate_product_counts(db, store.id)

        platform = store.platform.value if hasattr(store.platform, 'value') else str(store.platform)

        return StoreResponse(
            id=store.id,
            store_name=store.store_name,
            store_url=store.store_url,
            platform=platform,
            niche=store.niche,
            target_market=store.target_market,
            currency=store.currency,
            is_active=store.is_active,
            total_revenue=store.total_revenue,
            monthly_revenue=store.monthly_revenue,
            total_orders=store.total_orders,
            conversion_rate=store.conversion_rate,
            rank_position=store.rank_position,
            rank_change=store.rank_change,
            product_count=counts["total"],
            active_products=counts["active"],
            last_sync=store.last_sync,
            created_at=store.created_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update store: {str(e)}"
        )


@router.delete("/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_store(
    store_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete store from portfolio

    - Prevents deleting if it's the only store
    - Cascades to products and deployments
    - Updates user store count
    """
    # Check if user has other stores
    store_count = db.query(func.count(Store.id))\
        .filter(Store.user_id == user.id)\
        .scalar()

    if store_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the only store. Add another store first."
        )

    # Find and delete store
    store = db.query(Store)\
        .filter(Store.id == store_id)\
        .filter(Store.user_id == user.id)\
        .first()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    try:
        db.delete(store)

        # Update user store count
        user.total_stores = db.query(func.count(Store.id))\
            .filter(Store.user_id == user.id)\
            .scalar()

        db.commit()

        # Update rankings
        update_store_rankings(db, user.id)

        return None

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete store: {str(e)}"
        )


# ============================================================================
# PLATFORM ADAPTER INTEGRATION ENDPOINTS
# ============================================================================

@router.post("/stores/{store_id}/test", response_model=TestConnectionResponse)
async def test_store_connection(
    store_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test connection to store's platform

    - Validates credentials by connecting to platform API
    - Returns store information if successful
    - Useful before adding store or debugging connection issues
    """
    # Get store
    store = db.query(Store).filter(
        Store.id == store_id,
        Store.user_id == user.id
    ).first()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    try:
        # Get platform string
        platform = store.platform.value if hasattr(store.platform, 'value') else str(store.platform)

        # Convert credentials to adapter format
        adapter_credentials = convert_store_credentials_to_adapter_format(
            platform,
            store.credentials
        )

        # Create platform adapter
        adapter = PlatformFactory.get_adapter(platform, adapter_credentials)

        # Test connection
        result = await adapter.test_connection()

        if result.get("success"):
            logger.info(f"Successfully tested connection to store {store_id} ({platform})")

            return TestConnectionResponse(
                success=True,
                store_name=result.get("store_name"),
                store_url=result.get("store_url"),
                platform_version=result.get("platform_version")
            )
        else:
            logger.warning(f"Connection test failed for store {store_id}: {result.get('error')}")

            return TestConnectionResponse(
                success=False,
                error=result.get("error", "Connection failed")
            )

    except AuthenticationError as e:
        logger.error(f"Authentication error for store {store_id}: {e}")
        return TestConnectionResponse(
            success=False,
            error=f"Authentication failed: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Error testing connection for store {store_id}: {e}")
        return TestConnectionResponse(
            success=False,
            error=f"Connection error: {str(e)}"
        )


@router.post("/stores/{store_id}/sync", response_model=SyncStoreResponse)
async def sync_store(
    store_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync store data from platform

    - Fetches recent orders from platform
    - Updates revenue and order metrics
    - Updates store information
    - Records last sync time

    Returns:
    - orders_synced: Number of orders fetched
    - revenue_updated: Total revenue from synced orders
    - store_info: Updated store details
    """
    # Get store
    store = db.query(Store).filter(
        Store.id == store_id,
        Store.user_id == user.id
    ).first()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    try:
        # Get platform string
        platform = store.platform.value if hasattr(store.platform, 'value') else str(store.platform)

        # Convert credentials to adapter format
        adapter_credentials = convert_store_credentials_to_adapter_format(
            platform,
            store.credentials
        )

        # Create platform adapter
        adapter = PlatformFactory.get_adapter(platform, adapter_credentials)

        logger.info(f"Starting sync for store {store_id} ({platform})")

        # Sync orders
        sync_result = await adapter.sync_orders()

        if not sync_result.get("success"):
            logger.error(f"Order sync failed for store {store_id}: {sync_result.get('error')}")
            return SyncStoreResponse(
                success=False,
                orders_synced=0,
                revenue_updated=0.0,
                store_info={},
                error=sync_result.get("error", "Sync failed"),
                last_sync_time=datetime.utcnow()
            )

        # Get updated store info
        store_info_result = await adapter.get_store_info()
        store_info = store_info_result if store_info_result.get("success") else {}

        # Update store metrics
        metrics = sync_result.get("metrics", {})
        orders_synced = sync_result.get("orders_synced", 0)
        revenue = metrics.get("total_revenue", 0.0)

        # Update store record
        store.total_orders += orders_synced
        store.total_revenue += revenue
        store.monthly_revenue = revenue  # This should be filtered by month in production
        store.last_sync = datetime.utcnow()

        db.commit()
        db.refresh(store)

        # Update rankings
        update_store_rankings(db, user.id)

        logger.info(
            f"Successfully synced store {store_id}: "
            f"{orders_synced} orders, ${revenue:.2f} revenue"
        )

        return SyncStoreResponse(
            success=True,
            orders_synced=orders_synced,
            revenue_updated=revenue,
            store_info=store_info,
            last_sync_time=store.last_sync
        )

    except RateLimitError as e:
        logger.warning(f"Rate limit hit for store {store_id}: {e}")
        return SyncStoreResponse(
            success=False,
            orders_synced=0,
            revenue_updated=0.0,
            store_info={},
            error=f"Rate limit exceeded. Please try again in a few moments.",
            last_sync_time=datetime.utcnow()
        )

    except AuthenticationError as e:
        logger.error(f"Authentication error for store {store_id}: {e}")
        return SyncStoreResponse(
            success=False,
            orders_synced=0,
            revenue_updated=0.0,
            store_info={},
            error=f"Authentication failed: {str(e)}",
            last_sync_time=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error syncing store {store_id}: {e}")
        db.rollback()
        return SyncStoreResponse(
            success=False,
            orders_synced=0,
            revenue_updated=0.0,
            store_info={},
            error=f"Sync error: {str(e)}",
            last_sync_time=datetime.utcnow()
        )


@router.get("/stores/{store_id}/orders")
async def get_store_orders(
    store_id: int,
    limit: int = 50,
    status_filter: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch orders from store's platform

    Query Parameters:
    - limit: Max orders to fetch (default 50, max 100)
    - status_filter: Filter by status (any, pending, fulfilled, cancelled)

    Returns:
    - success: bool
    - orders: List of normalized orders
    - total_count: Number of orders returned
    """
    # Get store
    store = db.query(Store).filter(
        Store.id == store_id,
        Store.user_id == user.id
    ).first()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    try:
        # Get platform string
        platform = store.platform.value if hasattr(store.platform, 'value') else str(store.platform)

        # Convert credentials to adapter format
        adapter_credentials = convert_store_credentials_to_adapter_format(
            platform,
            store.credentials
        )

        # Create platform adapter
        adapter = PlatformFactory.get_adapter(platform, adapter_credentials)

        # Fetch orders
        result = await adapter.get_orders(
            limit=min(limit, 100),  # Cap at 100
            status=status_filter or "any"
        )

        if result.get("success"):
            return {
                "success": True,
                "orders": result.get("orders", []),
                "total_count": result.get("total_count", 0),
                "has_more": result.get("has_more", False)
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Failed to fetch orders"),
                "orders": [],
                "total_count": 0
            }

    except Exception as e:
        logger.error(f"Error fetching orders for store {store_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "orders": [],
            "total_count": 0
        }


@router.get("/stores/{store_id}/products")
async def get_store_products(
    store_id: int,
    limit: int = 50,
    published_status: str = "published",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch products from store's platform

    Query Parameters:
    - limit: Max products to fetch (default 50, max 100)
    - published_status: Filter by status (published, draft, any)

    Returns:
    - success: bool
    - products: List of normalized products
    - total_count: Number of products returned
    """
    # Get store
    store = db.query(Store).filter(
        Store.id == store_id,
        Store.user_id == user.id
    ).first()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    try:
        # Get platform string
        platform = store.platform.value if hasattr(store.platform, 'value') else str(store.platform)

        # Convert credentials to adapter format
        adapter_credentials = convert_store_credentials_to_adapter_format(
            platform,
            store.credentials
        )

        # Create platform adapter
        adapter = PlatformFactory.get_adapter(platform, adapter_credentials)

        # Fetch products
        result = await adapter.get_products(
            limit=min(limit, 100),  # Cap at 100
            published_status=published_status
        )

        if result.get("success"):
            return {
                "success": True,
                "products": result.get("products", []),
                "total_count": result.get("total_count", 0),
                "has_more": result.get("has_more", False)
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Failed to fetch products"),
                "products": [],
                "total_count": 0,
                "note": result.get("note", "")  # Helpful for Amazon limitations
            }

    except Exception as e:
        logger.error(f"Error fetching products for store {store_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "products": [],
            "total_count": 0
        }


@router.post("/stores/{store_id}/deploy-product", response_model=DeployProductResponse)
async def deploy_product_to_store(
    store_id: int,
    request: DeployProductRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deploy product to specific store's platform

    - Gets product from database
    - Uses platform adapter to create product on platform
    - Creates ProductDeployment record
    - Returns deployment status and platform details

    Request Body:
    - product_id: ID of product to deploy (from Products table)

    Returns:
    - success: bool
    - deployment_id: Database deployment record ID
    - platform_product_id: ID on platform (e.g., Shopify product ID)
    - platform_url: Direct URL to product on platform
    """
    # Get store
    store = db.query(Store).filter(
        Store.id == store_id,
        Store.user_id == user.id
    ).first()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    # Get product
    product = db.query(Product).filter(
        Product.id == request.product_id,
        Product.store_id == store_id
    ).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found for this store"
        )

    try:
        # Get platform string
        platform = store.platform.value if hasattr(store.platform, 'value') else str(store.platform)

        # Convert credentials to adapter format
        adapter_credentials = convert_store_credentials_to_adapter_format(
            platform,
            store.credentials
        )

        # Create platform adapter
        adapter = PlatformFactory.get_adapter(platform, adapter_credentials)

        # Prepare product data for deployment
        product_data = {
            "title": product.product_name,
            "description": product.description or "",
            "price": float(product.price),
            "sku": product.sku or f"PROD-{product.id}",
            "inventory": product.stock_quantity or 0,
            "images": json.loads(product.images) if product.images else [],
            "tags": product.tags.split(",") if product.tags else [],
            "status": "draft"  # Deploy as draft initially
        }

        # Deploy to platform
        logger.info(f"Deploying product {product.id} to store {store_id} ({platform})")

        result = await adapter.deploy_product(product_data)

        if result.get("success"):
            # Create deployment record
            deployment = ProductDeployment(
                product_id=product.id,
                store_id=store_id,
                platform_product_id=result.get("platform_product_id", ""),
                platform_url=result.get("platform_url", ""),
                deployed_at=datetime.utcnow()
            )

            db.add(deployment)

            # Update product status
            product.status = ProductStatus.DEPLOYED

            db.commit()
            db.refresh(deployment)

            logger.info(
                f"Successfully deployed product {product.id} to {platform}. "
                f"Platform ID: {result.get('platform_product_id')}"
            )

            return DeployProductResponse(
                success=True,
                deployment_id=deployment.id,
                platform_product_id=result.get("platform_product_id"),
                platform_url=result.get("platform_url")
            )
        else:
            logger.warning(
                f"Failed to deploy product {product.id} to store {store_id}: "
                f"{result.get('error')}"
            )

            return DeployProductResponse(
                success=False,
                error=result.get("error", "Deployment failed"),
            )

    except ProductNotFoundError as e:
        logger.error(f"Product not found error: {e}")
        db.rollback()
        return DeployProductResponse(
            success=False,
            error=f"Product not found: {str(e)}"
        )

    except PlatformAPIError as e:
        logger.error(f"Platform API error deploying product: {e}")
        db.rollback()
        return DeployProductResponse(
            success=False,
            error=f"Platform API error: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Error deploying product {request.product_id} to store {store_id}: {e}")
        db.rollback()
        return DeployProductResponse(
            success=False,
            error=f"Deployment error: {str(e)}"
        )
