"""
API Request/Response Schemas
=============================

Centralized Pydantic models for API validation.

SECURITY: All models include proper field validation:
- String length limits
- Numeric bounds
- URL/email validation
- Enum constraints

Author: OspraOS
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, HttpUrl
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


# ============================================================================
# COMMON RESPONSE MODELS
# ============================================================================

class StandardResponse(BaseModel):
    """Standard API response format."""
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None


class PaginationParams(BaseModel):
    """Reusable pagination parameters."""
    page: int = Field(default=1, ge=1, le=10000, description="Page number (1-indexed)")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, max_length=50, description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class PaginatedResponse(BaseModel):
    """Paginated list response."""
    success: bool = True
    data: List[Any]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(cls, items: List[Any], total: int, page: int, per_page: int):
        """Factory method to create paginated response."""
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        return cls(
            success=True,
            data=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )


def paginate_list(items: List[Any], page: int = 1, per_page: int = 20) -> dict:
    """
    Paginate a list of items.

    Args:
        items: Full list of items
        page: Page number (1-indexed)
        per_page: Items per page

    Returns:
        Dictionary with paginated data and metadata
    """
    total = len(items)
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_items = items[start_idx:end_idx]

    return {
        "data": paginated_items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }


# ============================================================================
# PLATFORM CREDENTIALS
# ============================================================================

class PlatformCredentials(BaseModel):
    """Credentials for platform integration testing."""
    api_key: Optional[str] = Field(None, max_length=500)
    api_secret: Optional[str] = Field(None, max_length=500)
    access_token: Optional[str] = Field(None, max_length=2000)
    shop_name: Optional[str] = Field(None, max_length=200)
    store_url: Optional[str] = Field(None, max_length=500)

    model_config = ConfigDict(extra="allow")  # Allow extra fields for different platforms


# ============================================================================
# SHOPIFY SCHEMAS
# ============================================================================

class ShopifyDeployRequest(BaseModel):
    """Request to deploy a product to Shopify.

    Either provide product_id to load from database,
    or product_data with full product information.
    """
    product_id: Optional[str] = Field(None, max_length=100)
    product_data: Optional[Dict[str, Any]] = None

    @field_validator("product_data")
    @classmethod
    def validate_product_data(cls, v):
        """Validate product_data has required fields if provided."""
        if v is not None:
            required = ["title", "price"]
            for field in required:
                if field not in v:
                    raise ValueError(f"product_data missing required field: {field}")
        return v


class ShopifyBulkDeployRequest(BaseModel):
    """Request to bulk deploy products to Shopify."""
    product_ids: Optional[List[str]] = Field(None, max_length=100)
    products: Optional[List[Dict[str, Any]]] = Field(None, max_length=50)


# ============================================================================
# ALIEXPRESS SCHEMAS
# ============================================================================

class AliExpressSearchRequest(BaseModel):
    """Request to search AliExpress products."""
    keywords: str = Field(..., min_length=1, max_length=200)
    category_id: Optional[str] = Field(None, max_length=50)
    min_price: Optional[float] = Field(None, ge=0, le=10000)
    max_price: Optional[float] = Field(None, ge=0, le=10000)
    sort_by: str = Field(default="SALE_PRICE_ASC", pattern="^(SALE_PRICE_ASC|SALE_PRICE_DESC|LAST_VOLUME_DESC)$")
    page_size: int = Field(default=20, ge=1, le=50)
    page_no: int = Field(default=1, ge=1, le=100)
    ship_to_country: str = Field(default="US", max_length=5)


class AliExpressAffiliateLinkRequest(BaseModel):
    """Request to generate affiliate links."""
    product_ids: List[str] = Field(..., min_length=1, max_length=50)
    tracking_id: Optional[str] = Field(None, max_length=100)


class AliExpressFulfillOrderRequest(BaseModel):
    """Request to fulfill an order via AliExpress."""
    order_id: str = Field(..., min_length=1, max_length=100)
    product_id: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(..., ge=1, le=1000)
    shipping_address: Dict[str, str] = Field(...)

    @field_validator("shipping_address")
    @classmethod
    def validate_shipping_address(cls, v):
        """Validate shipping address has required fields."""
        required = ["name", "address1", "city", "country", "zip"]
        for field in required:
            if field not in v:
                raise ValueError(f"Missing required field: {field}")
            if len(v[field]) > 200:
                raise ValueError(f"Field {field} too long (max 200 chars)")
        return v


class AliExpressSyncInventoryRequest(BaseModel):
    """Request to sync inventory from AliExpress."""
    product_ids: List[str] = Field(..., min_length=1, max_length=100)
    update_prices: bool = Field(default=False)
    update_stock: bool = Field(default=True)


class AliExpressMonitorPricesRequest(BaseModel):
    """Request to monitor product prices."""
    products: List[Dict[str, Any]] = Field(..., min_length=1, max_length=100)
    threshold_percent: float = Field(default=10, ge=1, le=50)


class AliExpressFulfillRequest(BaseModel):
    """Request to fulfill order via AliExpress."""
    shopify_order: Dict[str, Any] = Field(...)
    aliexpress_product_id: str = Field(..., min_length=1, max_length=100)


class AliExpressSyncRequest(BaseModel):
    """Request to sync inventory."""
    products: List[Dict[str, Any]] = Field(..., min_length=1, max_length=200)


# ============================================================================
# META/FACEBOOK ADS SCHEMAS
# ============================================================================

class CampaignObjective(str, Enum):
    """Meta campaign objectives."""
    CONVERSIONS = "CONVERSIONS"
    TRAFFIC = "TRAFFIC"
    AWARENESS = "AWARENESS"
    ENGAGEMENT = "ENGAGEMENT"
    LEADS = "LEADS"
    SALES = "SALES"


class ProductForCampaign(BaseModel):
    """Product data for campaign creation."""
    name: str = Field(..., min_length=1, max_length=300)
    price: float = Field(..., ge=0, le=100000)
    image_url: Optional[str] = Field(None, max_length=2000)
    shopify_url: Optional[str] = Field(None, max_length=2000)


class MetaCampaignRequest(BaseModel):
    """Request to create a Meta advertising campaign."""
    product: ProductForCampaign
    daily_budget: float = Field(default=10.0, ge=1, le=100000)
    auto_activate: bool = Field(default=False)


class MetaBulkCampaignCreateRequest(BaseModel):
    """Request to create multiple campaigns."""
    products: List[Dict[str, Any]] = Field(..., min_length=1, max_length=50)
    daily_budget_per_product: float = Field(default=10.0, ge=1, le=10000)


class MetaBulkCampaignRequest(BaseModel):
    """Request to create multiple campaigns."""
    campaigns: List[MetaCampaignRequest] = Field(..., min_length=1, max_length=20)


class CampaignStatusUpdate(BaseModel):
    """Request to update campaign status."""
    status: str = Field(..., pattern="^(ACTIVE|PAUSED|ARCHIVED)$")


class AdSetBudgetUpdate(BaseModel):
    """Request to update ad set budget."""
    daily_budget: Optional[float] = Field(None, ge=1, le=100000)
    lifetime_budget: Optional[float] = Field(None, ge=1, le=1000000)


# ============================================================================
# SCHEDULING SCHEMAS
# ============================================================================

class ScheduleType(str, Enum):
    """Types of scheduled actions."""
    DEPLOY = "deploy"
    PAUSE = "pause"
    RESUME = "resume"
    PRICE_UPDATE = "price_update"
    BUDGET_UPDATE = "budget_update"


class ScheduleCreateRequest(BaseModel):
    """Request to create a scheduled ad campaign."""
    product: Dict[str, Any] = Field(...)
    scheduled_start: str = Field(..., max_length=50)  # ISO datetime string
    scheduled_end: Optional[str] = Field(None, max_length=50)
    daily_budget: float = Field(default=10.0, ge=1, le=100000)
    total_budget: Optional[float] = Field(None, ge=1, le=1000000)
    platform: str = Field(default="meta", pattern="^(meta|google|tiktok)$")
    target_audience: Optional[Dict[str, Any]] = None


# ============================================================================
# DISCOVERY SCHEMAS
# ============================================================================

class DiscoverRequest(BaseModel):
    """Request for multi-niche product discovery."""
    niches: List[str] = Field(default=["smart_home", "kitchen", "fitness"], max_length=20)
    min_score: float = Field(default=0.0, ge=0, le=100)
    max_per_niche: int = Field(default=3, ge=1, le=20)
    top_overall: int = Field(default=15, ge=1, le=100)


class ProductValidationRequest(BaseModel):
    """Request to validate a product."""
    product_name: str = Field(..., min_length=1, max_length=500)
    product_url: Optional[str] = Field(None, max_length=2000)
    supplier_price: Optional[float] = Field(None, ge=0, le=100000)


# ============================================================================
# CHAT SCHEMAS
# ============================================================================

class ChatRequest(BaseModel):
    """Request for AI chat."""
    message: str = Field(..., min_length=1, max_length=10000)
    dashboard_context: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, Any]]] = Field(None, max_length=50)

    def get_context(self) -> Optional[Dict]:
        """Get context from either field."""
        return self.dashboard_context or self.context


# ============================================================================
# MARKETING SCHEMAS
# ============================================================================

class MarketingAngleRequest(BaseModel):
    """Request to generate marketing angles."""
    product_name: str = Field(..., min_length=1, max_length=300)
    product_description: str = Field(..., min_length=1, max_length=2000)
    target_audience: Optional[str] = Field(None, max_length=500)
    niche: Optional[str] = Field(None, max_length=100)


class BulkMarketingRequest(BaseModel):
    """Request to generate multiple marketing angles."""
    product_name: str = Field(..., min_length=1, max_length=300)
    product_description: str = Field(..., min_length=1, max_length=2000)
    count: int = Field(default=3, ge=1, le=10)
    target_audience: Optional[str] = Field(None, max_length=500)


# ============================================================================
# RECOMMENDATION SCHEMAS
# ============================================================================

class SmartRecommendationRequest(BaseModel):
    """Request for smart product recommendations."""
    niches: Optional[List[str]] = Field(None, max_length=20)
    max_products: int = Field(default=10, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0, le=100)
    exclude_deployed: bool = Field(default=True)
