"""
AUTHENTICATION API ROUTES
=========================

Endpoints for user authentication and session management.

Endpoints:
- POST /api/auth/register - Create new account
- POST /api/auth/login - Login and get tokens
- POST /api/auth/refresh - Refresh access token
- POST /api/auth/logout - Logout and revoke tokens
- GET /api/auth/me - Get current user info
- GET /api/auth/verify - Verify token validity

Author: Ospra OS
Date: December 2024
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import logging
import os

from .jwt_handler import (
    create_token_pair,
    refresh_access_token,
    logout as jwt_logout,
    hash_password,
    verify_password,
    get_token_info,
    TokenPair
)
from .dependencies import (
    require_auth,
    optional_auth,
    TokenPayload
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    name: Optional[str] = None
    tier: Optional[str] = "nest"  # Default to nest if not specified


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request."""
    refresh_token: Optional[str] = None  # Optional but recommended


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User info response."""
    id: int
    email: str
    name: Optional[str]
    tier: str
    created_at: Optional[str]


class MessageResponse(BaseModel):
    """Simple message response."""
    success: bool
    message: str


# ============================================================================
# MOCK USER DATABASE (Replace with real database in production)
# ============================================================================

# In-memory user storage for development
# TODO: Replace with Supabase/PostgreSQL in production
_users_db: dict = {}
_user_id_counter = 1


def _get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email from mock DB."""
    return _users_db.get(email.lower())


def _get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID from mock DB."""
    for user in _users_db.values():
        if user["id"] == user_id:
            return user
    return None


def _create_user(email: str, password_hash: str, name: Optional[str] = None, tier: str = "nest") -> dict:
    """Create user in mock DB."""
    global _user_id_counter
    
    from datetime import datetime
    
    # Validate tier
    valid_tiers = ["nest", "flight", "soar", "stratosphere"]
    if tier.lower() not in valid_tiers:
        tier = "nest"
    
    user = {
        "id": _user_id_counter,
        "email": email.lower(),
        "password_hash": password_hash,
        "name": name,
        "tier": tier.lower(),
        "created_at": datetime.utcnow().isoformat(),
    }
    
    _users_db[email.lower()] = user
    _user_id_counter += 1
    
    return user


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/register")
async def register(request: RegisterRequest):
    """
    Register a new user account.
    
    Returns access and refresh tokens on successful registration.
    """
    # Check if user exists
    if _get_user_by_email(request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate password strength
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    # Hash password
    password_hash = hash_password(request.password)
    
    # Create user with selected tier
    user = _create_user(
        email=request.email,
        password_hash=password_hash,
        name=request.name,
        tier=request.tier or "nest"
    )
    
    logger.info(f"New user registered: {user['email']} (ID: {user['id']})")
    
    # Generate tokens
    tokens = create_token_pair(
        user_id=user["id"],
        email=user["email"],
        tier=user["tier"]
    )
    
    # Return tokens WITH user object (frontend expects this)
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name"),
            "tier": user["tier"],
            "subscription_tier": user["tier"],  # Backend field name
            "created_at": user.get("created_at")
        }
    }


@router.post("/login")
async def login(request: LoginRequest):
    """
    Login with email and password.
    
    Returns access and refresh tokens on successful login.
    """
    # Find user
    user = _get_user_by_email(request.email)
    
    if not user:
        logger.warning(f"Login attempt for non-existent email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(request.password, user["password_hash"]):
        logger.warning(f"Failed login attempt for: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    logger.info(f"User logged in: {user['email']} (ID: {user['id']})")
    
    # Generate tokens
    tokens = create_token_pair(
        user_id=user["id"],
        email=user["email"],
        tier=user["tier"]
    )
    
    # Return tokens WITH user object (frontend expects this)
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name"),
            "tier": user["tier"],
            "subscription_tier": user["tier"],
            "created_at": user.get("created_at")
        }
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(request: RefreshRequest):
    """
    Refresh access token using refresh token.
    
    Also rotates refresh token for security.
    """
    # Get user's current tier (might have changed)
    # For now, decode the refresh token to get user info
    from .jwt_handler import validate_refresh_token
    
    payload = validate_refresh_token(request.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Get current user tier from DB
    user = _get_user_by_id(payload.user_id)
    tier = user["tier"] if user else "nest"
    
    # Refresh tokens
    result = refresh_access_token(request.refresh_token, tier)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    new_access, new_refresh = result
    
    logger.info(f"Tokens refreshed for user {payload.user_id}")
    
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=15 * 60  # 15 minutes
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: LogoutRequest,
    http_request: Request,
    user: TokenPayload = Depends(require_auth)
):
    """
    Logout and revoke tokens.
    
    Blacklists both access and refresh tokens.
    """
    # Get access token from header
    auth_header = http_request.headers.get("Authorization", "")
    access_token = auth_header.replace("Bearer ", "") if auth_header else ""
    
    # Logout
    jwt_logout(access_token, request.refresh_token)
    
    logger.info(f"User logged out: {user.email} (ID: {user.user_id})")
    
    return MessageResponse(
        success=True,
        message="Successfully logged out"
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: TokenPayload = Depends(require_auth)):
    """
    Get current authenticated user's information.
    """
    # Get full user data from DB
    full_user = _get_user_by_id(user.user_id)
    
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=full_user["id"],
        email=full_user["email"],
        name=full_user.get("name"),
        tier=full_user["tier"],
        created_at=full_user.get("created_at")
    )


@router.get("/verify")
async def verify_token(user: Optional[TokenPayload] = Depends(optional_auth)):
    """
    Verify if current token is valid.
    
    Returns token info if valid, error if not.
    """
    if user is None:
        return {
            "valid": False,
            "message": "No valid token provided"
        }
    
    return {
        "valid": True,
        "user_id": user.user_id,
        "email": user.email,
        "tier": user.tier,
        "expires_at": user.exp.isoformat(),
        "time_until_expiry": str(user.time_until_expiry())
    }


@router.get("/token-info")
async def get_token_details(
    http_request: Request,
    user: TokenPayload = Depends(require_auth)
):
    """
    Get detailed information about the current token.
    
    Useful for debugging token issues.
    """
    auth_header = http_request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header else ""
    
    return get_token_info(token)


# ============================================================================
# ADMIN ENDPOINTS (for development/testing)
# ============================================================================

@router.get("/debug/users")
async def list_users():
    """
    [DEBUG] List all users.
    
    Only available in development mode.
    """
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not available in production"
        )
    
    # Return users without password hashes
    return {
        "users": [
            {
                "id": u["id"],
                "email": u["email"],
                "name": u.get("name"),
                "tier": u["tier"],
                "created_at": u.get("created_at")
            }
            for u in _users_db.values()
        ],
        "count": len(_users_db)
    }


@router.post("/debug/set-tier")
async def set_user_tier(
    email: str,
    tier: str,
    user: TokenPayload = Depends(require_auth)
):
    """
    [DEBUG] Set a user's tier.
    
    Only available in development mode.
    """
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not available in production"
        )
    
    valid_tiers = ["nest", "flight", "soar", "stratosphere", "admin"]
    if tier.lower() not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier. Must be one of: {valid_tiers}"
        )
    
    target_user = _get_user_by_email(email)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    target_user["tier"] = tier.lower()
    
    return {
        "success": True,
        "message": f"Set {email} to tier: {tier}",
        "user": {
            "id": target_user["id"],
            "email": target_user["email"],
            "tier": target_user["tier"]
        }
    }
