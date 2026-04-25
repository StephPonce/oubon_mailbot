"""
Authentication API Routes - FIXED
=================================

Endpoints:
- POST /api/auth/register - Create new account
- POST /api/auth/login - Login and get tokens
- POST /api/auth/refresh - Refresh access token
- GET /api/auth/me - Get current user info
- POST /api/auth/logout - Logout (client-side token removal)
- POST /api/auth/change-password - Change password (FIXED to accept JSON body)
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional

from ospra_os.security.security_audit import (
    log_login_success,
    log_login_failed,
    log_password_changed,
    log_security_event,
    SecurityEventType,
)
from ospra_os.auth.jwt_auth import (
    UserCreate,
    UserLogin,
    TokenResponse,
    get_db,
    get_user_by_email,
    create_user,
    authenticate_user,
    get_current_user,
    decode_token,
    generate_tokens,
    create_access_token,
    user_to_dict,
    get_user_by_id,
    verify_password,
    hash_password,
)
from ospra_os.database import User

# Try to import email service, but don't fail if it doesn't exist
try:
    from ospra_os.services.email_service import send_welcome_email
except ImportError:
    send_welcome_email = None

# PostHog activation funnel (task #38) — optional. The posthog_client module is
# always importable because every public function is a no-op when PostHog is
# unconfigured, so we don't need a try/except here.
from ospra_os.observability.posthog_client import (
    capture as posthog_capture,
    identify as posthog_identify,
    FunnelEvent,
)


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ============================================================================
# REQUEST MODELS
# ============================================================================

class ChangePasswordRequest(BaseModel):
    """Request body for password change"""
    current_password: str
    new_password: str


class RefreshTokenRequest(BaseModel):
    """Request body for token refresh"""
    refresh_token: str


# ============================================================================
# REGISTRATION
# ============================================================================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.

    Returns access and refresh tokens upon successful registration.
    New users start at the Nest (free) tier.
    Sends a welcome email in the background.
    """
    # Check if email already exists
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = create_user(db, user_data)

    # Send welcome email in background (if available)
    if send_welcome_email:
        background_tasks.add_task(
            send_welcome_email,
            to_email=user.email,
            user_name=user.name
        )

    # PostHog activation funnel (task #38) — fire SIGNUP and seed identify()
    # with cohort-friendly properties. Both calls are no-ops when PostHog is
    # disabled, so they never break registration.
    posthog_identify(
        user.id,
        properties={
            "plan": getattr(user, "subscription_tier", "nest"),
            "signup_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    posthog_capture(
        user.id,
        FunnelEvent.SIGNUP,
        properties={"plan": getattr(user, "subscription_tier", "nest")},
    )

    # Generate tokens
    return generate_tokens(user)


# ============================================================================
# LOGIN
# ============================================================================

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Login with email and password.

    Returns access and refresh tokens upon successful authentication.
    """
    user = authenticate_user(db, credentials.email, credentials.password)

    if not user:
        # SECURITY AUDIT: Log failed login
        log_login_failed(
            email=credentials.email,
            reason="Invalid credentials",
            request=request,
            db=db,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    try:
        user.last_login = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        # Non-critical error - don't fail login if last_login update fails
        pass

    # SECURITY AUDIT: Log successful login
    log_login_success(
        user_id=user.id,
        user_email=user.email,
        request=request,
        db=db,
    )

    # Generate tokens
    return generate_tokens(user)


# ============================================================================
# TOKEN REFRESH
# ============================================================================

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh an expired access token using a valid refresh token.
    
    Body:
        refresh_token: The refresh token issued during login
        
    Returns new access and refresh tokens.
    """
    # Decode refresh token
    try:
        payload = decode_token(request.refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Validate token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type - expected refresh token"
        )
    
    # Get user
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Generate new tokens
    return generate_tokens(user)


# ============================================================================
# CURRENT USER
# ============================================================================

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """
    Get current authenticated user's profile.
    
    Requires valid access token in Authorization header.
    """
    return {
        "success": True,
        "user": user_to_dict(user),
        "subscription": {
            "tier": user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier),
            "started": user.subscription_started.isoformat() if user.subscription_started else None,
            "expires": user.subscription_expires.isoformat() if user.subscription_expires else None,
        }
    }


# ============================================================================
# LOGOUT (Client-side - just returns success)
# ============================================================================

@router.post("/logout")
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout endpoint.

    Note: JWT tokens are stateless, so actual token invalidation
    happens client-side by removing the stored tokens.

    This endpoint exists for:
    1. Consistency in API design
    2. Future token blacklist implementation
    3. Logging logout events
    """
    # SECURITY AUDIT: Log logout
    log_security_event(
        event_type=SecurityEventType.LOGOUT,
        user_id=user.id,
        user_email=user.email,
        message="User logged out",
        request=request,
        db=db,
    )

    return {
        "success": True,
        "message": "Logged out successfully",
        "note": "Please remove stored tokens on client"
    }


# ============================================================================
# PASSWORD CHANGE - FIXED TO ACCEPT JSON BODY
# ============================================================================

@router.post("/change-password")
async def change_password(
    http_request: Request,
    request: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user's password.

    Requires current password for verification.
    Accepts JSON body with current_password and new_password.
    """
    # Verify current password
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Validate new password
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters"
        )

    # Check if new password is the same as current password
    if verify_password(request.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as your current password"
        )

    # Update password
    try:
        user.password_hash = hash_password(request.new_password)
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password. Please try again."
        )

    # SECURITY AUDIT: Log password change
    log_password_changed(
        user_id=user.id,
        user_email=user.email,
        via_reset=False,
        request=http_request,
        db=db,
    )

    return {
        "success": True,
        "message": "Password changed successfully"
    }


# ============================================================================
# CHECK EMAIL AVAILABILITY
# ============================================================================

@router.get("/check-email")
async def check_email(email: str, db: Session = Depends(get_db)):
    """
    Check if an email is available for registration.
    
    Used for real-time validation during signup.
    """
    existing = get_user_by_email(db, email)
    
    return {
        "available": existing is None,
        "email": email
    }
