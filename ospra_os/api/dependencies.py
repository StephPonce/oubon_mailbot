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
# RE-EXPORT AUTH DEPENDENCIES
# ============================================================================

# These are available if you need them directly
__all__ = [
    "CurrentUser",
    "DB",
    "get_current_user",
    "get_db",
]
