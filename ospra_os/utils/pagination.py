"""
Pagination Utilities for Ospra OS
=================================

Provides safe pagination helpers that prevent resource exhaustion attacks.

Features:
- Maximum limit enforcement
- Default limits
- Offset validation
- Cursor-based pagination support

Usage:
    from ospra_os.utils.pagination import safe_pagination, PaginationParams

    @router.get("/products")
    async def list_products(pagination: PaginationParams = Depends(safe_pagination)):
        query = db.query(Product).offset(pagination.offset).limit(pagination.limit)
        ...

Author: OspraOS
"""

from dataclasses import dataclass
from typing import Optional
from fastapi import Query


# =============================================================================
# CONSTANTS
# =============================================================================

# Global pagination limits
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100  # Never allow more than 100 items per request
MAX_OFFSET = 10000   # Prevent deep pagination attacks


# =============================================================================
# PAGINATION PARAMS
# =============================================================================

@dataclass
class PaginationParams:
    """Validated pagination parameters."""
    limit: int
    offset: int
    page: int

    @property
    def skip(self) -> int:
        """Alias for offset (SQLAlchemy style)."""
        return self.offset


def safe_pagination(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})"),
    offset: Optional[int] = Query(None, ge=0, le=MAX_OFFSET, description="Direct offset (overrides page)")
) -> PaginationParams:
    """
    FastAPI dependency for safe pagination.

    Enforces:
    - Maximum items per page (100)
    - Maximum offset (10000)
    - Valid page numbers

    Usage:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends(safe_pagination)):
            items = db.query(Item).offset(pagination.offset).limit(pagination.limit).all()

    Also callable directly (e.g. from tests or non-FastAPI code) with bare
    int kwargs — the FastAPI ``Query`` sentinels are detected and replaced
    with their plain-Python defaults so the function works in both contexts.
    """
    # When this function is invoked directly (not through FastAPI's
    # dependency injection), the defaults are FastAPI Query() sentinel
    # objects rather than ints. Coerce them back to plain defaults so
    # arithmetic and comparison operations don't blow up.
    from fastapi.params import Query as _QueryParam

    if isinstance(page, _QueryParam):
        page = 1
    if isinstance(per_page, _QueryParam):
        per_page = DEFAULT_PAGE_SIZE
    if isinstance(offset, _QueryParam):
        offset = None

    # Calculate offset from page if not directly provided
    if offset is None:
        calculated_offset = (page - 1) * per_page
    else:
        calculated_offset = offset

    # Enforce maximum offset
    calculated_offset = min(calculated_offset, MAX_OFFSET)

    # Enforce maximum limit
    safe_limit = min(per_page, MAX_PAGE_SIZE)

    return PaginationParams(
        limit=safe_limit,
        offset=calculated_offset,
        page=page
    )


def safe_limit(
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description=f"Maximum items to return (max {MAX_PAGE_SIZE})")
) -> int:
    """
    Simple limit-only dependency when full pagination isn't needed.

    Usage:
        @router.get("/recent")
        async def get_recent(limit: int = Depends(safe_limit)):
            items = db.query(Item).limit(limit).all()
    """
    from fastapi.params import Query as _QueryParam
    if isinstance(limit, _QueryParam):
        limit = DEFAULT_PAGE_SIZE
    return min(limit, MAX_PAGE_SIZE)


# =============================================================================
# RESPONSE HELPERS
# =============================================================================

def paginated_response(
    items: list,
    total: int,
    pagination: PaginationParams
) -> dict:
    """
    Create a standardized paginated response.

    Args:
        items: The items for the current page
        total: Total count of items (for all pages)
        pagination: The pagination parameters used

    Returns:
        Standardized response with items and pagination metadata
    """
    total_pages = (total + pagination.limit - 1) // pagination.limit if pagination.limit > 0 else 0

    return {
        "items": items,
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.limit,
            "offset": pagination.offset,
            "total": total,
            "total_pages": total_pages,
            "has_next": pagination.offset + pagination.limit < total,
            "has_prev": pagination.offset > 0,
        }
    }


# =============================================================================
# QUERY HELPERS
# =============================================================================

def apply_pagination(query, pagination: PaginationParams):
    """
    Apply pagination to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        pagination: PaginationParams from safe_pagination

    Returns:
        Query with offset and limit applied
    """
    return query.offset(pagination.offset).limit(pagination.limit)


def bounded_all(query, max_items: int = MAX_PAGE_SIZE):
    """
    Execute .all() with a safety limit.

    Use this instead of naked .all() calls to prevent memory exhaustion.

    Args:
        query: SQLAlchemy query object
        max_items: Maximum items to return (default: MAX_PAGE_SIZE)

    Returns:
        List of items, limited to max_items
    """
    return query.limit(max_items).all()
