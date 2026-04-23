"""
API Request Schemas
====================

Input validation models for API endpoints.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# =============================================================================
# PLATFORM CREDENTIALS
# =============================================================================

class PlatformCredentials(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    store_url: Optional[str] = None
    access_token: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


# =============================================================================
# SHOPIFY
# =============================================================================

class ShopifyDeployRequest(BaseModel):
    product_id: Optional[str] = None
    product_data: Optional[Dict[str, Any]] = None


class ShopifyBulkDeployRequest(BaseModel):
    product_ids: Optional[List[str]] = None
    products: Optional[List[Dict[str, Any]]] = None


# =============================================================================
# ALIEXPRESS
# =============================================================================

class AliExpressSearchRequest(BaseModel):
    keywords: str
    min_price: Optional[float] = None
    max_price: Optional[float] = None


class AliExpressAffiliateLinkRequest(BaseModel):
    product_ids: List[str]


class AliExpressFulfillRequest(BaseModel):
    shopify_order: Dict[str, Any]
    aliexpress_product_id: str


class AliExpressSyncRequest(BaseModel):
    products: List[Dict[str, Any]]


class AliExpressMonitorPricesRequest(BaseModel):
    products: List[Dict[str, Any]]
    threshold_percent: float = 10.0


# =============================================================================
# META ADS
# =============================================================================

class MetaProductInfo(BaseModel):
    name: str
    price: float
    image_url: Optional[str] = None
    shopify_url: Optional[str] = None


class MetaCampaignRequest(BaseModel):
    product: MetaProductInfo
    daily_budget: float = 15.0
    auto_activate: bool = False


class MetaBulkCampaignCreateRequest(BaseModel):
    products: List[Dict[str, Any]]
    daily_budget_per_product: float = 10.0


class CampaignStatusUpdate(BaseModel):
    status: str  # "ACTIVE" or "PAUSED"


class AdSetBudgetUpdate(BaseModel):
    daily_budget: Optional[float] = None


# =============================================================================
# SCHEDULING
# =============================================================================

class ScheduleCreateRequest(BaseModel):
    product: Dict[str, Any]
    scheduled_start: str
    scheduled_end: Optional[str] = None
    daily_budget: float = 15.0
    total_budget: Optional[float] = None
    platform: str = "meta"
    target_audience: Optional[Dict[str, Any]] = None


# =============================================================================
# DISCOVERY & CHAT
# =============================================================================

class DiscoverRequest(BaseModel):
    min_score: float = 0.0
    max_per_niche: int = 3
    top_overall: int = 15


class ChatRequest(BaseModel):
    message: str
    dashboard_context: Optional[Dict] = None
    context: Optional[Dict] = None
    conversation_history: Optional[List[Dict]] = None

    def get_context(self) -> Optional[Dict]:
        return self.dashboard_context or self.context


# =============================================================================
# MARKETING
# =============================================================================

class MarketingAngleRequest(BaseModel):
    product_title: str
    niche: Optional[str] = None
    target_audience: Optional[str] = None
    tone: Optional[str] = None


class BulkMarketingRequest(BaseModel):
    products: List[Dict[str, Any]]
    niche: Optional[str] = None


class SmartRecommendationRequest(BaseModel):
    niche: Optional[str] = None
    budget: Optional[float] = None
    limit: int = 10
