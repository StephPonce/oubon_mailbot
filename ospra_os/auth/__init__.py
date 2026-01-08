"""
OSPRA OS AUTHENTICATION PACKAGE
===============================

JWT-based authentication for secure API access.

Usage:
    # In routes
    from ospra_os.auth.dependencies import require_auth, require_tier
    
    @router.get("/protected")
    async def protected(user: TokenPayload = Depends(require_auth)):
        return {"user_id": user.user_id}
    
    # For token operations
    from ospra_os.auth.jwt_handler import create_token_pair, verify_password

Components:
- jwt_handler: Token creation, validation, and password hashing
- dependencies: FastAPI dependencies for route protection
- routes: Authentication API endpoints

Author: Ospra OS
Date: December 2024
"""

from .jwt_handler import (
    # Token creation
    create_access_token,
    create_refresh_token,
    create_token_pair,
    
    # Token validation
    decode_token,
    validate_access_token,
    validate_refresh_token,
    
    # Token refresh
    refresh_access_token,
    
    # Logout
    logout,
    blacklist_token,
    is_token_blacklisted,
    
    # Password handling
    hash_password,
    verify_password,
    
    # Utilities
    extract_token_from_header,
    get_token_info,
    
    # Data classes
    TokenPayload,
    TokenPair,
    
    # Config
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

from .dependencies import (
    # Main dependencies
    require_auth,
    optional_auth,
    require_tier,
    require_any_tier,
    require_admin,
    
    # Optional user
    get_current_user,
    
    # Tier helpers
    tier_has_access,
    get_tier_level,
    TIER_LEVELS,
    
    # Rate limit helpers
    get_rate_limit_key,
    get_tier_rate_limit,
    
    # Security scheme
    security,
)

from .routes import router

__all__ = [
    # Token creation
    "create_access_token",
    "create_refresh_token", 
    "create_token_pair",
    
    # Token validation
    "decode_token",
    "validate_access_token",
    "validate_refresh_token",
    
    # Token management
    "refresh_access_token",
    "logout",
    "blacklist_token",
    "is_token_blacklisted",
    
    # Password
    "hash_password",
    "verify_password",
    
    # Dependencies
    "require_auth",
    "optional_auth",
    "require_tier",
    "require_any_tier",
    "require_admin",
    "get_current_user",
    
    # Tier helpers
    "tier_has_access",
    "get_tier_level",
    "TIER_LEVELS",
    
    # Rate limits
    "get_rate_limit_key",
    "get_tier_rate_limit",
    
    # Data classes
    "TokenPayload",
    "TokenPair",
    
    # Router
    "router",
    
    # Config
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
]
