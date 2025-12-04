"""
Authentication API Routes
=========================

Endpoints:
- POST /api/auth/register - Create new account
- POST /api/auth/login - Login and get tokens
- POST /api/auth/refresh - Refresh access token
- GET /api/auth/me - Get current user info
- POST /api/auth/logout - Logout (client-side token removal)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

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
)
from ospra_os.database.multi_store_models import User


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ============================================================================
# REGISTRATION
# ============================================================================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    Returns access and refresh tokens upon successful registration.
    New users start at the Nest (free) tier.
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
    
    # Generate tokens
    return generate_tokens(user)


# ============================================================================
# LOGIN
# ============================================================================

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    Returns access and refresh tokens upon successful authentication.
    """
    user = authenticate_user(db, credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Generate tokens
    return generate_tokens(user)


# ============================================================================
# TOKEN REFRESH
# ============================================================================

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """
    Refresh an expired access token using a valid refresh token.
    
    Body:
        refresh_token: The refresh token issued during login
        
    Returns new access and refresh tokens.
    """
    # Decode refresh token
    try:
        payload = decode_token(refresh_token)
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
async def logout(user: User = Depends(get_current_user)):
    """
    Logout endpoint.
    
    Note: JWT tokens are stateless, so actual token invalidation
    happens client-side by removing the stored tokens.
    
    This endpoint exists for:
    1. Consistency in API design
    2. Future token blacklist implementation
    3. Logging logout events
    """
    return {
        "success": True,
        "message": "Logged out successfully",
        "note": "Please remove stored tokens on client"
    }


# ============================================================================
# PASSWORD CHANGE
# ============================================================================

@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user's password.
    
    Requires current password for verification.
    """
    from ospra_os.auth.jwt_auth import verify_password, hash_password
    
    # Verify current password
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters"
        )
    
    # Update password
    user.password_hash = hash_password(new_password)
    db.commit()
    
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
