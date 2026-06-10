"""
Amazon FBA API Routes - GROK RECOMMENDATION #16

REST API endpoints for Amazon FBA operations.

Endpoints:
- GET  /api/amazon/accounts - List connected accounts
- POST /api/amazon/accounts - Connect new account
- GET  /api/amazon/accounts/{id} - Get account details
- DELETE /api/amazon/accounts/{id} - Disconnect account

- GET  /api/amazon/research/search - Search catalog for product research
- GET  /api/amazon/research/analyze/{asin} - Analyze product profitability

- GET  /api/amazon/listings - Get listings
- POST /api/amazon/listings - Create listing
- PUT  /api/amazon/listings/{id}/publish - Publish listing to Amazon
- POST /api/amazon/listings/sync - Sync all listings

- GET  /api/amazon/orders - Get orders
- POST /api/amazon/orders/sync - Sync orders from Amazon

- POST /api/amazon/inventory/sync - Sync FBA inventory

- POST /api/amazon/shipments - Create FBA inbound shipment
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from ospra_os.database.db import get_db
from ospra_os.services.amazon_service import AmazonService
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/amazon", tags=["Amazon FBA"])


def _get_owned_account(service: AmazonService, account_id: int, current_user: User):
    """SECURITY: load an Amazon account ONLY if it belongs to the caller.

    Raises 404 (not 403) for both missing and foreign accounts so the
    endpoint never acts as an account-ID existence oracle.
    """
    account = service.get_account(account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    return account


def _get_owned_listing(db: Session, listing_id: int, current_user: User):
    """SECURITY: load a listing ONLY if its parent account belongs to the caller."""
    from ospra_os.database.amazon_models import AmazonListing, AmazonAccount

    listing = (
        db.query(AmazonListing)
        .join(AmazonAccount, AmazonListing.account_id == AmazonAccount.id)
        .filter(AmazonListing.id == listing_id, AmazonAccount.user_id == current_user.id)
        .first()
    )
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    return listing


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ConnectAccountRequest(BaseModel):
    """Request to connect Amazon account.

    SECURITY: user_id removed - extracted from JWT token instead.
    """
    seller_id: str = Field(..., description="Amazon Seller ID")
    marketplace_id: str = Field(default="ATVPDKIKX0DER", description="Marketplace ID")
    account_name: Optional[str] = Field(None, description="Account nickname")

    # OAuth credentials
    lwa_client_id: str = Field(..., description="LWA OAuth client ID")
    lwa_client_secret: str = Field(..., description="LWA OAuth client secret")
    refresh_token: str = Field(..., description="LWA refresh token")

    # AWS credentials
    aws_access_key: str = Field(..., description="AWS access key")
    aws_secret_key: str = Field(..., description="AWS secret key")
    role_arn: Optional[str] = Field(None, description="AWS IAM role ARN")


class CreateListingRequest(BaseModel):
    """Request to create listing"""
    account_id: int = Field(..., description="Amazon account ID")
    sku: str = Field(..., description="Your SKU")
    asin: Optional[str] = Field(None, description="ASIN (if matching existing product)")
    title: str = Field(..., description="Product title", max_length=200)
    price: float = Field(..., description="Selling price", gt=0)
    cost: float = Field(..., description="Your cost", gt=0)
    quantity: int = Field(..., description="Initial inventory quantity", ge=0)
    condition: str = Field(default="new_new", description="Condition type")
    fulfillment_channel: str = Field(default="FBA", description="FBA or FBM")
    description: Optional[str] = Field(None, description="Product description")
    bullet_points: Optional[List[str]] = Field(None, description="Feature bullets (max 5)")
    main_image: Optional[str] = Field(None, description="Main image URL")
    shopify_product_id: Optional[int] = Field(None, description="Link to Shopify product")


class AnalyzeProductRequest(BaseModel):
    """Request to analyze product profitability"""
    account_id: int = Field(..., description="Amazon account ID")
    asin: str = Field(..., description="Product ASIN")
    cost: float = Field(..., description="Your cost per unit", gt=0)


class SyncOrdersRequest(BaseModel):
    """Request to sync orders"""
    account_id: int = Field(..., description="Amazon account ID")
    created_after: Optional[str] = Field(None, description="ISO 8601 date (e.g., 2025-01-01T00:00:00Z)")
    days_back: int = Field(default=7, description="Days to look back if created_after not provided", ge=1, le=90)


# ============================================================================
# ACCOUNT MANAGEMENT
# ============================================================================

@router.get("/accounts")
async def get_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all Amazon accounts for a user.

    Returns list of connected Amazon Seller Central accounts.
    """
    try:
        user_id = current_user.id
        service = AmazonService(db)
        accounts = service.get_accounts(user_id)

        return {
            "status": "success",
            "accounts": [
                {
                    "id": acc.id,
                    "seller_id": acc.seller_id,
                    "account_name": acc.account_name,
                    "marketplace_id": acc.marketplace_id,
                    "status": acc.status,
                    "last_sync_at": acc.last_sync_at.isoformat() if acc.last_sync_at else None,
                    "created_at": acc.created_at.isoformat()
                }
                for acc in accounts
            ]
        }

    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


@router.post("/accounts")
async def connect_account(
    request: ConnectAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Connect Amazon Seller Central account.

    SECURITY: Requires JWT authentication. User ID extracted from token.

    Requires:
    - LWA OAuth credentials (client_id, client_secret, refresh_token)
    - AWS IAM credentials (access_key, secret_key)
    - Seller ID and marketplace

    Tests connection before saving.
    """
    try:
        user_id = current_user.id
        service = AmazonService(db)

        account = service.connect_account(
            user_id=user_id,
            seller_id=request.seller_id,
            marketplace_id=request.marketplace_id,
            lwa_client_id=request.lwa_client_id,
            lwa_client_secret=request.lwa_client_secret,
            refresh_token=request.refresh_token,
            aws_access_key=request.aws_access_key,
            aws_secret_key=request.aws_secret_key,
            role_arn=request.role_arn,
            account_name=request.account_name
        )

        return {
            "status": "success" if account.status == "active" else "error",
            "message": "Account connected successfully" if account.status == "active" else "Connection test failed",
            "account": {
                "id": account.id,
                "seller_id": account.seller_id,
                "account_name": account.account_name,
                "marketplace_id": account.marketplace_id,
                "status": account.status,
                "sync_error": account.sync_error
            }
        }

    except Exception as e:
        logger.error(f"Error connecting account: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect Amazon account"
        )


@router.get("/accounts/{account_id}")
async def get_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get Amazon account details with statistics.

    SECURITY: caller must own the account.
    """
    try:
        service = AmazonService(db)
        account = _get_owned_account(service, account_id, current_user)

        stats = service.get_account_statistics(account_id)

        return {
            "status": "success",
            "account": {
                "id": account.id,
                "user_id": account.user_id,
                "seller_id": account.seller_id,
                "account_name": account.account_name,
                "marketplace_id": account.marketplace_id,
                "status": account.status,
                "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
                "sync_error": account.sync_error,
                "created_at": account.created_at.isoformat()
            },
            "statistics": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


@router.delete("/accounts/{account_id}")
async def disconnect_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect Amazon account.

    SECURITY: caller must own the account.
    """
    try:
        service = AmazonService(db)
        _get_owned_account(service, account_id, current_user)
        success = service.disconnect_account(account_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )

        return {
            "status": "success",
            "message": "Account disconnected"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


# ============================================================================
# PRODUCT RESEARCH
# ============================================================================

@router.get("/research/search")
async def research_products(
    account_id: int = Query(..., description="Amazon account ID"),
    keywords: str = Query(..., description="Search keywords"),
    max_results: int = Query(default=20, ge=1, le=50, description="Max results"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search Amazon catalog for product research.

    SECURITY: caller must own the account.

    Returns products with:
    - Basic info (ASIN, title, brand, image)
    - Sales rank and category
    - Buy box price
    - Estimated FBA fees
    - Estimated profit margin

    Use for finding profitable products to sell.
    """
    try:
        service = AmazonService(db)
        _get_owned_account(service, account_id, current_user)
        results = service.research_products(
            account_id=account_id,
            keywords=keywords,
            max_results=max_results
        )

        return {
            "status": "success",
            "query": keywords,
            "results": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Error researching products: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


@router.post("/research/analyze")
async def analyze_product(
    request: AnalyzeProductRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze product profitability.

    Deep dive into a specific ASIN:
    - Current buy box price
    - FBA fee breakdown (fulfillment, referral, storage)
    - Profit calculation (revenue - fees - cost)
    - ROI and margin percentages
    - Recommendation (profitable / low margin / unprofitable)

    Use after finding promising products in research phase.
    """
    try:
        service = AmazonService(db)
        _get_owned_account(service, request.account_id, current_user)
        analysis = service.analyze_product_profitability(
            account_id=request.account_id,
            asin=request.asin,
            cost=request.cost
        )

        return {
            "status": "success",
            "analysis": analysis
        }

    except Exception as e:
        logger.error(f"Error analyzing product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


# ============================================================================
# LISTING MANAGEMENT
# ============================================================================

@router.get("/listings")
async def get_listings(
    account_id: int = Query(..., description="Amazon account ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get Amazon listings.

    SECURITY: caller must own the account.
    """
    try:
        from ospra_os.database.amazon_models import AmazonListing

        _get_owned_account(AmazonService(db), account_id, current_user)
        query = db.query(AmazonListing).filter(
            AmazonListing.account_id == account_id
        )

        if status_filter:
            query = query.filter(AmazonListing.status == status_filter)

        listings = query.limit(limit).all()

        return {
            "status": "success",
            "listings": [
                {
                    "id": listing.id,
                    "sku": listing.sku,
                    "asin": listing.asin,
                    "title": listing.title,
                    "price": float(listing.price),
                    "cost": float(listing.cost) if listing.cost else None,
                    "inventory_quantity": listing.inventory_quantity,
                    "status": listing.status,
                    "fulfillment_channel": listing.fulfillment_channel,
                    "shopify_product_id": listing.shopify_product_id,
                    "created_at": listing.created_at.isoformat()
                }
                for listing in listings
            ],
            "count": len(listings)
        }

    except Exception as e:
        logger.error(f"Error getting listings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


@router.post("/listings")
async def create_listing(
    request: CreateListingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create Amazon product listing (draft).

    Creates listing in database as draft status.
    Use PUT /listings/{id}/publish to publish to Amazon.

    Supports:
    - FBA or FBM fulfillment
    - Linking to Shopify product (cross-platform inventory)
    - Product details (title, description, bullets, images)
    """
    try:
        service = AmazonService(db)
        _get_owned_account(service, request.account_id, current_user)

        listing = service.create_listing(
            account_id=request.account_id,
            sku=request.sku,
            asin=request.asin,
            title=request.title,
            price=request.price,
            cost=request.cost,
            quantity=request.quantity,
            condition=request.condition,
            fulfillment_channel=request.fulfillment_channel,
            description=request.description,
            bullet_points=request.bullet_points,
            main_image=request.main_image,
            shopify_product_id=request.shopify_product_id
        )

        return {
            "status": "success",
            "message": "Listing created (draft)",
            "listing": {
                "id": listing.id,
                "sku": listing.sku,
                "asin": listing.asin,
                "title": listing.title,
                "price": float(listing.price),
                "status": listing.status
            }
        }

    except Exception as e:
        logger.error(f"Error creating listing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


@router.put("/listings/{listing_id}/publish")
async def publish_listing(
    listing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Publish listing to Amazon.

    SECURITY: caller must own the listing's account.

    Note: Amazon may take several minutes to process listing.
    """
    try:
        _get_owned_listing(db, listing_id, current_user)
        service = AmazonService(db)
        success = service.publish_listing(listing_id)

        if success:
            return {
                "status": "success",
                "message": "Listing published to Amazon"
            }
        else:
            return {
                "status": "error",
                "message": "Failed to publish listing"
            }

    except Exception as e:
        logger.error(f"Error publishing listing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


@router.post("/listings/sync")
async def sync_listings(
    account_id: int = Query(..., description="Amazon account ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync all listings from Amazon.

    SECURITY: caller must own the account.
    """
    try:
        service = AmazonService(db)
        _get_owned_account(service, account_id, current_user)
        count = service.sync_listings(account_id)

        return {
            "status": "success",
            "message": f"Synced {count} listings",
            "synced_count": count
        }

    except Exception as e:
        logger.error(f"Error syncing listings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


# ============================================================================
# ORDER MANAGEMENT
# ============================================================================

@router.get("/orders")
async def get_orders(
    account_id: int = Query(..., description="Amazon account ID"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get Amazon orders.

    SECURITY: caller must own the account.
    """
    try:
        from ospra_os.database.amazon_models import AmazonOrder
        from sqlalchemy import desc

        _get_owned_account(AmazonService(db), account_id, current_user)
        orders = db.query(AmazonOrder).filter(
            AmazonOrder.account_id == account_id
        ).order_by(desc(AmazonOrder.purchase_date)).limit(limit).all()

        return {
            "status": "success",
            "orders": [
                {
                    "id": order.id,
                    "amazon_order_id": order.amazon_order_id,
                    "order_status": order.order_status,
                    "fulfillment_channel": order.fulfillment_channel,
                    "order_total": float(order.order_total) if order.order_total else None,
                    "currency": order.currency,
                    "purchase_date": order.purchase_date.isoformat(),
                    "buyer_email": order.buyer_email,
                    "ship_city": order.ship_city,
                    "ship_state": order.ship_state
                }
                for order in orders
            ],
            "count": len(orders)
        }

    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


@router.post("/orders/sync")
async def sync_orders(
    request: SyncOrdersRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync orders from Amazon.

    SECURITY: caller must own the account.
    """
    try:
        service = AmazonService(db)
        _get_owned_account(service, request.account_id, current_user)
        count = service.sync_orders(
            account_id=request.account_id,
            created_after=request.created_after,
            days_back=request.days_back
        )

        return {
            "status": "success",
            "message": f"Synced {count} orders",
            "synced_count": count
        }

    except Exception as e:
        logger.error(f"Error syncing orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


# ============================================================================
# FBA INVENTORY
# ============================================================================

@router.post("/inventory/sync")
async def sync_inventory(
    account_id: int = Query(..., description="Amazon account ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync FBA inventory from Amazon.

    SECURITY: caller must own the account.
    """
    try:
        service = AmazonService(db)
        _get_owned_account(service, account_id, current_user)
        count = service.sync_inventory(account_id)

        return {
            "status": "success",
            "message": f"Synced inventory for {count} SKUs",
            "synced_count": count
        }

    except Exception as e:
        logger.error(f"Error syncing inventory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operation failed. Please try again later."
        )


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check():
    """
    Health check for Amazon integration.

    Returns service status and available features.
    """
    return {
        "status": "healthy",
        "service": "amazon_fba",
        "features": {
            "account_management": True,
            "product_research": True,
            "listing_management": True,
            "order_sync": True,
            "inventory_sync": True,
            "profitability_analysis": True,
            "multi_marketplace": True
        },
        "supported_marketplaces": [
            "ATVPDKIKX0DER",  # US
            "A2EUQ1WTGCTBG2",  # CA
            "A1AM78C64UM0Y8",  # MX
            "A1F83G8C2ARO7P",  # UK
            "A1PA6795UKMFR9",  # DE
            "A13V1IB3VIYBER",  # FR
            "APJ6JRA9NG5V4",   # IT
            "A1RKKUPIHCS9HS",  # ES
            "A1VC38T7YXB528",  # JP
            "A39IBJ37TRP1C6"   # AU
        ]
    }
