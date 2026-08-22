"""
FASTAPI AUTHENTICATION DEPENDENCIES
====================================

Reusable dependencies for protecting API endpoints.

Usage:
    from ospra_os.auth.dependencies import require_auth, require_tier
    
    @router.get("/protected")
    async def protected_endpoint(user: TokenPayload = Depends(require_auth)):
        return {"user_id": user.user_id}
    
    @router.get("/premium")
    async def premium_endpoint(user: TokenPayload = Depends(require_tier("soar"))):
        return {"premium": True}

Author: Ospra OS
Date: December 2024
"""

from typing import Optional, List, Callable
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from .jwt_handler import (
    TokenPayload,
    validate_access_token,
    extract_token_from_header
)

logger = logging.getLogger(__name__)


# ============================================================================
# SECURITY SCHEME
# ============================================================================

# HTTPBearer for Swagger UI integration
security = HTTPBearer(auto_error=False)


# ============================================================================
# TIER HIERARCHY
# ============================================================================

# Tier levels (higher number = more access)
TIER_LEVELS = {
    "nest": 0,
    "flight": 1,
    "soar": 2,
    "stratosphere": 3,
    "admin": 99  # Special admin tier
}


def get_tier_level(tier: str) -> int:
    """Get numeric level for a tier."""
    return TIER_LEVELS.get(tier.lower(), 0)


def tier_has_access(user_tier: str, required_tier: str) -> bool:
    """Check if user tier has access to required tier level."""
    return get_tier_level(user_tier) >= get_tier_level(required_tier)


# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[TokenPayload]:
    """
    Get current user from JWT token (OPTIONAL — returns None when absent).

    RENAMED 2026-08. This was called `get_current_user`, identical in name to
    the STRICT dependency in ospra_os/auth/jwt_auth.py that raises 401 — and
    `ospra_os.auth` re-exported THIS one. So `from ospra_os.auth import
    get_current_user` produced a dependency that reads as protection and gates
    nothing; that is why several discovery routes were effectively public.

    Use this ONLY for endpoints that genuinely serve anonymous callers with
    different behaviour when logged in. If a route must reject anonymous
    callers, import get_current_user from ospra_os.auth.jwt_auth.
    """
    token = None
    
    # Try to get token from HTTPBearer
    if credentials:
        token = credentials.credentials
    
    # Fallback: Try Authorization header directly
    if not token:
        auth_header = request.headers.get("Authorization", "")
        token = extract_token_from_header(auth_header)
    
    if not token:
        return None
    
    # Validate token
    payload = validate_access_token(token)
    
    return payload


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> TokenPayload:
    """
    Require valid authentication.
    
    Raises 401 if not authenticated.
    Use this for protected endpoints.
    """
    user = await get_current_user(request, credentials)
    
    if user is None:
        logger.warning(f"Unauthorized access attempt: {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user


def require_tier(minimum_tier: str) -> Callable:
    """
    Factory for tier-based authorization.
    
    Usage:
        @router.get("/premium")
        async def premium(user: TokenPayload = Depends(require_tier("soar"))):
            ...
    """
    async def tier_checker(
        user: TokenPayload = Depends(require_auth)
    ) -> TokenPayload:
        if not tier_has_access(user.tier, minimum_tier):
            logger.warning(
                f"User {user.user_id} (tier={user.tier}) attempted to access "
                f"{minimum_tier}+ endpoint"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {minimum_tier} tier or higher. "
                       f"Your tier: {user.tier}"
            )
        return user
    
    return tier_checker


def require_any_tier(allowed_tiers: List[str]) -> Callable:
    """
    Require user to have one of the specified tiers.
    
    Usage:
        @router.get("/special")
        async def special(user = Depends(require_any_tier(["soar", "stratosphere"]))):
            ...
    """
    async def tier_checker(
        user: TokenPayload = Depends(require_auth)
    ) -> TokenPayload:
        if user.tier.lower() not in [t.lower() for t in allowed_tiers]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires one of: {', '.join(allowed_tiers)}. "
                       f"Your tier: {user.tier}"
            )
        return user
    
    return tier_checker


async def require_admin(
    user: TokenPayload = Depends(require_auth)
) -> TokenPayload:
    """
    Require admin access.

    Section A/C: the real admin signal is the DB ``users.is_admin`` flag
    (deny-by-default), not a JWT tier claim. This used to check
    ``tier == "admin"`` — a value nothing ever set, so it denied everyone AND
    couldn't be granted without re-minting tokens. Now it loads the caller's
    row and checks is_admin / is_superuser, matching require_admin_user.
    """
    from ospra_os.database.connection import get_session
    from ospra_os.database import User

    session = get_session()
    try:
        db_user = session.query(User).filter(User.id == user.user_id).first()
        is_admin = bool(
            db_user and (getattr(db_user, "is_admin", False) or getattr(db_user, "is_superuser", False))
        )
    finally:
        session.close()

    if not is_admin:
        logger.warning(f"Non-admin user {user.user_id} attempted admin access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


# ============================================================================
# OPTIONAL AUTH
# ============================================================================

async def optional_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[TokenPayload]:
    """
    Optional authentication.
    
    Returns user if authenticated, None otherwise.
    Use for endpoints that behave differently for logged-in users.
    """
    return await get_current_user(request, credentials)


# ============================================================================
# RATE LIMIT HELPERS
# ============================================================================

def get_rate_limit_key(user: Optional[TokenPayload], request: Request) -> str:
    """
    Get rate limit key based on user or IP.
    
    Authenticated users get per-user limits.
    Anonymous users get per-IP limits.
    """
    if user:
        return f"user:{user.user_id}"
    
    # Get client IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    
    return f"ip:{ip}"


def get_tier_rate_limit(tier: str) -> dict:
    """
    Get rate limits for a tier.
    
    Returns dict with requests_per_minute and requests_per_day.
    """
    limits = {
        "nest": {"per_minute": 60, "per_day": 1000},
        "flight": {"per_minute": 120, "per_day": 5000},
        "soar": {"per_minute": 300, "per_day": 20000},
        "stratosphere": {"per_minute": 1000, "per_day": 100000},
        "admin": {"per_minute": 10000, "per_day": 1000000},
    }
    return limits.get(tier.lower(), limits["nest"])


# ============================================================================
# CONVENIENCE ALIASES
# ============================================================================

# Common dependency aliases
CurrentUser = Depends(require_auth)
OptionalUser = Depends(optional_auth)
FlightUser = Depends(require_tier("flight"))
SoarUser = Depends(require_tier("soar"))
StratosphereUser = Depends(require_tier("stratosphere"))
AdminUser = Depends(require_admin)


# Backwards-compatible alias. Deliberately NOT exported from ospra_os.auth —
# see the rename note above. Anything importing this name should be reviewed:
# it does not reject anonymous callers.
get_current_user = get_current_user_optional
