"""
Password Reset API Routes
==========================

Endpoints:
- POST /api/auth/forgot-password - Request password reset email
- POST /api/auth/reset-password - Reset password with token
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import secrets
import uuid

from ospra_os.database import User, PasswordResetToken, get_db
from ospra_os.auth.jwt_auth import hash_password, get_user_by_email, verify_password
from ospra_os.services.email_service import send_password_reset_email


router = APIRouter(prefix="/api/auth", tags=["Password Reset"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ForgotPasswordRequest(BaseModel):
    """Request model for forgot password"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request model for password reset"""
    token: str
    new_password: str


class VerifyTokenRequest(BaseModel):
    """Request model for token verification"""
    token: str


# ============================================================================
# DATABASE TOKEN STORAGE
# ============================================================================
# Tokens are now stored in database to persist across server restarts

def create_reset_token(email: str, db: Session) -> str:
    """
    Generate a secure reset token and store it in database.

    Args:
        email: User's email address
        db: Database session

    Returns:
        str: Reset token (UUID format)
    """
    # Generate secure random token
    token = str(uuid.uuid4())

    # Create database record with 1 hour expiration
    reset_token = PasswordResetToken(
        token=token,
        email=email,
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )

    db.add(reset_token)
    db.commit()

    return token


def validate_reset_token(token: str, db: Session) -> str | None:
    """
    Validate reset token and return email if valid.

    Args:
        token: Reset token to validate
        db: Database session

    Returns:
        str | None: Email if token is valid, None otherwise
    """
    # Query database for token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token
    ).first()

    if not reset_token:
        return None

    # Check if token is valid (not expired and not used)
    if not reset_token.is_valid:
        return None

    return reset_token.email


def invalidate_reset_token(token: str, db: Session):
    """Mark token as used after successful password reset"""
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token
    ).first()

    if reset_token:
        reset_token.used = True
        db.commit()


# ============================================================================
# FORGOT PASSWORD ENDPOINT
# ============================================================================

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset email.

    Sends a reset link to the user's email if the account exists.
    Always returns success to prevent email enumeration.

    Args:
        request: Email address

    Returns:
        Success message (always, to prevent email enumeration)
    """
    email = request.email.lower().strip()

    # Check if user exists
    user = get_user_by_email(db, email)

    if user:
        # Generate reset token (stored in database)
        reset_token = create_reset_token(email, db)

        # Send email
        email_result = await send_password_reset_email(
            to_email=email,
            reset_token=reset_token,
            user_name=user.name
        )

        if not email_result.get("success"):
            # Log error but don't reveal to user
            print(f"Failed to send password reset email: {email_result.get('error')}")

    # Always return success to prevent email enumeration
    return {
        "success": True,
        "message": "If an account exists with that email, a password reset link has been sent."
    }


# ============================================================================
# VERIFY RESET TOKEN ENDPOINT
# ============================================================================

@router.post("/verify-reset-token", status_code=status.HTTP_200_OK)
async def verify_reset_token_endpoint(
    request: VerifyTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Verify if a reset token is valid.

    Used by the frontend to check token validity before showing reset form.

    Args:
        request: Token to verify

    Returns:
        valid: Boolean indicating if token is valid
    """
    # Validate token
    email = validate_reset_token(request.token, db)

    return {
        "valid": email is not None,
        "email": email if email else None
    }


# ============================================================================
# RESET PASSWORD ENDPOINT
# ============================================================================

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using valid token.

    Args:
        request: Token and new password

    Returns:
        Success message

    Raises:
        HTTPException: If token is invalid or expired
    """
    # Validate token (check database)
    email = validate_reset_token(request.token, db)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    # Validate new password
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )

    # Get user
    user = get_user_by_email(db, email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if new password is the same as current password
    if verify_password(request.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as your current password. Please choose a different password."
        )

    # Update password
    user.password_hash = hash_password(request.new_password)
    db.commit()

    # Invalidate token (mark as used in database)
    invalidate_reset_token(request.token, db)

    return {
        "success": True,
        "message": "Password has been reset successfully. You can now login with your new password."
    }


# ============================================================================
# TOKEN CLEANUP (Optional - Run periodically)
# ============================================================================

def cleanup_expired_tokens(db: Session):
    """
    Remove expired tokens from database.

    This should be called periodically (e.g., via background task)
    to keep the database clean.

    Args:
        db: Database session

    Returns:
        int: Number of expired tokens removed
    """
    now = datetime.utcnow()

    # Find and delete all expired tokens
    expired_count = db.query(PasswordResetToken).filter(
        PasswordResetToken.expires_at < now
    ).delete()

    db.commit()

    return expired_count
