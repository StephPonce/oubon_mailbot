"""
AUTHENTICATION API ROUTES
=========================

Endpoints for user authentication and session management.
Now uses PostgreSQL database for persistent user storage.

Endpoints:
- POST /api/auth/register - Create new account
- POST /api/auth/login - Login and get tokens
- POST /api/auth/refresh - Refresh access token
- POST /api/auth/logout - Logout and revoke tokens
- GET /api/auth/me - Get current user info
- GET /api/auth/verify - Verify token validity

Author: Ospra OS
Date: December 2024 (Fixed January 2026 - PostgreSQL)
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
import os
import secrets

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

# Database imports - USE REAL POSTGRESQL DATABASE
from ospra_os.database.connection import get_db
from ospra_os.database import User, SubscriptionTier, PasswordResetToken

# Email service for password reset
try:
    from ospra_os.services.email_service import send_password_reset_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False

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


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request."""
    token: str
    password: str = Field(..., min_length=8, description="Minimum 8 characters")


# ============================================================================
# DATABASE HELPER FUNCTIONS - POSTGRESQL
# ============================================================================

def _get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email from PostgreSQL database."""
    return db.query(User).filter(User.email == email.lower()).first()


def _get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID from PostgreSQL database."""
    return db.query(User).filter(User.id == user_id).first()


def _create_user(db: Session, email: str, password_hash: str, name: Optional[str] = None, tier: str = "nest") -> User:
    """Create user in PostgreSQL database."""
    # Validate and map tier
    tier_map = {
        "nest": SubscriptionTier.NEST,
        "flight": SubscriptionTier.FLIGHT,
        "soar": SubscriptionTier.SOAR,
        "stratosphere": SubscriptionTier.STRATOSPHERE,
        # Legacy mappings
        "free": SubscriptionTier.NEST,
        "starter": SubscriptionTier.FLIGHT,
        "pro": SubscriptionTier.SOAR,
        "enterprise": SubscriptionTier.STRATOSPHERE,
    }
    
    subscription_tier = tier_map.get(tier.lower(), SubscriptionTier.NEST)
    
    # Default name to email username if not provided (name is NOT NULL in DB)
    user_name = name if name else email.split("@")[0]
    
    user = User(
        email=email.lower(),
        password_hash=password_hash,
        name=user_name,
        subscription_tier=subscription_tier,
        created_at=datetime.utcnow(),
        # Note: is_active column doesn't exist in User model - removed
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


def _user_to_dict(user: User) -> dict:
    """Convert User model to dictionary."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "tier": user.subscription_tier.value if user.subscription_tier else "nest",
        "subscription_tier": user.subscription_tier.value if user.subscription_tier else "nest",
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    Returns access and refresh tokens on successful registration.
    Users are persisted to PostgreSQL database.
    """
    # Check if user exists
    if _get_user_by_email(db, request.email):
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
    
    # Create user in PostgreSQL
    user = _create_user(
        db=db,
        email=request.email,
        password_hash=password_hash,
        name=request.name,
        tier=request.tier or "nest"
    )
    
    logger.info(f"New user registered: {user.email} (ID: {user.id})")
    
    # Get tier value
    tier = user.subscription_tier.value if user.subscription_tier else "nest"
    
    # Generate tokens
    tokens = create_token_pair(
        user_id=user.id,
        email=user.email,
        tier=tier
    )
    
    # Return tokens WITH user object (frontend expects this)
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
        "user": _user_to_dict(user)
    }


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    Returns access and refresh tokens on successful login.
    """
    # Find user in PostgreSQL
    user = _get_user_by_email(db, request.email)
    
    if not user:
        logger.warning(f"Login attempt for non-existent email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        logger.warning(f"Failed login attempt for: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    logger.info(f"User logged in: {user.email} (ID: {user.id})")
    
    # Get tier value
    tier = user.subscription_tier.value if user.subscription_tier else "nest"
    
    # Generate tokens
    tokens = create_token_pair(
        user_id=user.id,
        email=user.email,
        tier=tier
    )
    
    # Return tokens WITH user object (frontend expects this)
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
        "user": _user_to_dict(user)
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(request: RefreshRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token.
    
    Also rotates refresh token for security.
    """
    # Get user's current tier (might have changed)
    from .jwt_handler import validate_refresh_token
    
    payload = validate_refresh_token(request.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Get current user tier from PostgreSQL
    user = _get_user_by_id(db, payload.user_id)
    tier = user.subscription_tier.value if user and user.subscription_tier else "nest"
    
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
async def get_current_user_info(
    user: TokenPayload = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user's information.
    """
    # Get full user data from PostgreSQL
    full_user = _get_user_by_id(db, user.user_id)
    
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    tier = full_user.subscription_tier.value if full_user.subscription_tier else "nest"
    
    return UserResponse(
        id=full_user.id,
        email=full_user.email,
        name=full_user.name,
        tier=tier,
        created_at=full_user.created_at.isoformat() if full_user.created_at else None
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
# PASSWORD RESET ENDPOINTS
# ============================================================================

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Request a password reset email.
    
    For security, always returns success even if email doesn't exist.
    This prevents email enumeration attacks.
    """
    # Find user (but don't reveal if they exist)
    user = _get_user_by_email(db, request.email)
    
    if user:
        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # Delete any existing tokens for this email
        db.query(PasswordResetToken).filter(
            PasswordResetToken.email == request.email.lower()
        ).delete()
        
        # Create new token
        reset_token = PasswordResetToken(
            token=token,
            email=request.email.lower(),
            expires_at=expires_at,
            used=False
        )
        db.add(reset_token)
        db.commit()
        
        # Build reset URL
        app_url = os.getenv("APP_URL", "https://ospra.io")
        reset_link = f"{app_url}/reset-password?token={token}"
        
        # Send email
        if EMAIL_SERVICE_AVAILABLE:
            result = send_password_reset_email(
                to=user.email,
                reset_link=reset_link,
                user_name=user.name
            )
            if not result.get("success"):
                logger.error(f"Failed to send reset email to {user.email}: {result.get('error')}")
        else:
            logger.warning(f"Email service not available. Reset link: {reset_link}")
        
        logger.info(f"Password reset requested for: {request.email}")
    else:
        logger.info(f"Password reset requested for non-existent email: {request.email}")
    
    # Always return success to prevent email enumeration
    return MessageResponse(
        success=True,
        message="If an account exists with this email, you will receive a password reset link."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset password using token from email.
    
    Token is single-use and expires after 1 hour.
    """
    # Find token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == request.token
    ).first()
    
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Check if token is valid
    if reset_token.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link has already been used"
        )
    
    if reset_token.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link has expired. Please request a new one."
        )
    
    # Find user
    user = _get_user_by_email(db, reset_token.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    user.password_hash = hash_password(request.password)
    
    # Mark token as used
    reset_token.used = True
    
    db.commit()
    
    logger.info(f"Password reset completed for: {user.email}")
    
    return MessageResponse(
        success=True,
        message="Password successfully reset. You can now login with your new password."
    )


# ============================================================================
# ADMIN ENDPOINTS (for development/testing)
# ============================================================================

@router.get("/debug/users")
async def list_users(db: Session = Depends(get_db)):
    """
    [DEBUG] List all users.
    
    Only available in development mode.
    """
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not available in production"
        )
    
    users = db.query(User).all()
    
    return {
        "users": [_user_to_dict(u) for u in users],
        "count": len(users)
    }


@router.post("/debug/set-tier")
async def set_user_tier(
    email: str,
    tier: str,
    user: TokenPayload = Depends(require_auth),
    db: Session = Depends(get_db)
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
    
    tier_map = {
        "nest": SubscriptionTier.NEST,
        "flight": SubscriptionTier.FLIGHT,
        "soar": SubscriptionTier.SOAR,
        "stratosphere": SubscriptionTier.STRATOSPHERE,
        "admin": SubscriptionTier.STRATOSPHERE,  # Admin gets highest tier
    }
    
    if tier.lower() not in tier_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier. Must be one of: {list(tier_map.keys())}"
        )
    
    target_user = _get_user_by_email(db, email)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    target_user.subscription_tier = tier_map[tier.lower()]
    db.commit()
    
    return {
        "success": True,
        "message": f"Set {email} to tier: {tier}",
        "user": _user_to_dict(target_user)
    }
