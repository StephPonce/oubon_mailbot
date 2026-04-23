"""
Shared API Dependencies
=======================

Provides clean type aliases and dependency functions for use in API routes.

Usage:
    from ospra_os.api.dependencies import CurrentUser, DB

    @router.post("/protected-route")
    async def protected_route(
        current_user: CurrentUser,
        db: DB
    ):
        return {"user_id": current_user.id}
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from ospra_os.auth.jwt_auth import get_current_user, get_db
from ospra_os.database import User


# ============================================================================
# TYPE ALIASES FOR CLEAN ROUTE SIGNATURES
# ============================================================================

# Current authenticated user (requires valid JWT token)
CurrentUser = Annotated[User, Depends(get_current_user)]

# Database session
DB = Annotated[Session, Depends(get_db)]


# ============================================================================
# PAGINATION DEPENDENCIES
# ============================================================================

from dataclasses import dataclass
from fastapi import Query


@dataclass
class PaginationParams:
    """Pagination parameters extracted from query string."""
    page: int
    per_page: int
    offset: int

    @property
    def skip(self) -> int:
        """Alias for offset."""
        return self.offset


def get_pagination(
    page: int = Query(1, ge=1, le=10000, description="Page number (1-indexed)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page")
) -> PaginationParams:
    """
    Dependency to extract pagination parameters from query string.

    Usage:
        @router.get("/items")
        async def list_items(pagination: Pagination):
            items = db.query(Item).offset(pagination.offset).limit(pagination.per_page).all()
    """
    offset = (page - 1) * per_page
    return PaginationParams(page=page, per_page=per_page, offset=offset)


# Type alias for pagination dependency
Pagination = Annotated[PaginationParams, Depends(get_pagination)]


def paginated_response(data: list, total: int, pagination: PaginationParams) -> dict:
    """
    Create a paginated response dictionary.

    Usage:
        return paginated_response(items, total_count, pagination)
    """
    total_pages = (total + pagination.per_page - 1) // pagination.per_page if pagination.per_page > 0 else 0
    return {
        "success": True,
        "data": data,
        "total": total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total_pages": total_pages,
        "has_next": pagination.page < total_pages,
        "has_prev": pagination.page > 1
    }


# ============================================================================
# RE-EXPORT AUTH DEPENDENCIES
# ============================================================================

# These are available if you need them directly
__all__ = [
    "CurrentUser",
    "DB",
    "Pagination",
    "PaginationParams",
    "get_current_user",
    "get_db",
    "get_pagination",
    "paginated_response",
]
