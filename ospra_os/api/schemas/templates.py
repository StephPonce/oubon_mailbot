"""
Template Vault API Response Schemas
====================================

Response models for template marketplace endpoints.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# TEMPLATE RESPONSES
# ============================================================================

class TemplateResponse(BaseModel):
    """Basic template information for list views"""
    id: int
    name: str
    description: str
    short_description: Optional[str] = None
    category: str
    tags: List[str] = []
    niches: List[str] = []
    is_free: bool
    price: float
    status: str
    creator_id: int

    # Stats
    uses_count: int = 0
    avg_rating: Optional[float] = None
    review_count: int = 0

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateDetailResponse(TemplateResponse):
    """
    Full template details including actions.

    Only returned when user has access to the template.
    """
    actions: List[Dict[str, Any]]
    variables: List[Dict[str, Any]] = []
    requirements: Dict[str, Any] = {}

    # Access info
    user_has_access: bool = False
    user_is_creator: bool = False

    # Reviews
    reviews: List[Dict[str, Any]] = []


class TemplateBrowseResponse(BaseModel):
    """Paginated template list for browse endpoint"""
    templates: List[TemplateResponse]
    total: int
    page: int
    per_page: int
    pages: int


class TemplateFeaturedResponse(BaseModel):
    """Featured templates list"""
    templates: List[TemplateResponse]


# ============================================================================
# TEMPLATE OPERATIONS
# ============================================================================

class TemplateSubmitResponse(BaseModel):
    """Response after submitting template for review"""
    status: str
    message: str


class TemplateUsageResponse(BaseModel):
    """Response after applying a template to a store"""
    usage_id: int
    status: str
    actions_total: int
    message: str


class TemplatePurchaseResponse(BaseModel):
    """Response after purchasing a template"""
    purchase_id: int
    transaction_id: str
    amount_paid: float
    message: str


class TemplateReviewResponse(BaseModel):
    """Response after adding a review"""
    review_id: int
    is_verified: bool
    message: str


# ============================================================================
# TEMPLATE METADATA
# ============================================================================

class TemplateCategoryOption(BaseModel):
    """Template category option"""
    value: str
    label: str


class TemplateCategoriesResponse(BaseModel):
    """List of available template categories"""
    categories: List[TemplateCategoryOption]


class TemplateStatsResponse(BaseModel):
    """Marketplace overview statistics"""
    total_templates: int
    total_uses: int
    avg_rating: float
    featured_count: int
