"""
Common API Response Schemas
============================

Shared response models used across multiple API endpoints.
"""

from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field


# ============================================================================
# GENERIC RESPONSE MODELS
# ============================================================================

class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    detail: str


class StatusResponse(BaseModel):
    """Simple status response"""
    status: str
    message: str


# ============================================================================
# PAGINATED RESPONSES
# ============================================================================

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.

    Example:
        PaginatedResponse[TemplateResponse](
            items=[...],
            total=100,
            page=1,
            per_page=20,
            pages=5
        )
    """
    items: List[T]
    total: int
    page: int
    per_page: int
    pages: int

    class Config:
        from_attributes = True


# ============================================================================
# STATS RESPONSES
# ============================================================================

class CountResponse(BaseModel):
    """Simple count response"""
    count: int


class PercentageResponse(BaseModel):
    """Percentage with optional context"""
    percentage: float = Field(..., ge=0, le=100)
    value: Optional[int] = None
    total: Optional[int] = None


# ============================================================================
# ID RESPONSES (for creation endpoints)
# ============================================================================

class IdResponse(BaseModel):
    """Response containing only an ID"""
    id: int


class IdsResponse(BaseModel):
    """Response containing multiple IDs"""
    ids: List[int]
    count: int


# ============================================================================
# CATEGORY/ENUM RESPONSES
# ============================================================================

class CategoryOption(BaseModel):
    """Category or enum option"""
    value: str
    label: str
    description: Optional[str] = None


class CategoriesResponse(BaseModel):
    """List of category options"""
    categories: List[CategoryOption]
