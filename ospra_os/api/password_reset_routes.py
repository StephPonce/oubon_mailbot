"""
Password Reset API Routes
==========================

SECURITY: Rate limited to prevent email bombing and brute force attacks.

Endpoints:
- POST /api/auth/forgot-password - Request password reset email (3/hour)
- POST /api/auth/reset-password - Reset password with token (5/hour)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import secrets
import uuid
import logging

from ospra_os.database import User, PasswordResetToken, get_db
from ospra_os.auth.jwt_auth import hash_password, get_user_by_email, verify_password
from ospra_os.services.email_service import send_password_reset_email
from ospra_os.security.rate_limiting import limiter
from ospra_os.security.security_audit import (
    log_password_reset_requested,
    log_password_changed,
    log_security_event,
    SecurityEventType,
    SecuritySeverity,
)

logger = logging.getLogger(__name__)

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
# DATABASE TOKEN STORAGE (Hashed for Security)
# ============================================================================
# SECURITY: Tokens are hashed before storage so that if the database is
# compromised, attackers cannot use the tokens to reset passwords.

import hashlib


def _hash_token(token: str) -> str:
    """
    Hash a reset token for secure storage.

    Uses SHA-256 which is fast enough for token validation but secure
    enough that tokens cannot be reversed from the hash.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_reset_token(email: str, db: Session) -> str:
    """
    Generate a secure reset token and store its HASH in database.

    SECURITY: Only the hash is stored. The plain token is returned to the
    user and sent via email. Even if the database is compromised, the
    attacker cannot determine the original tokens.

    Args:
        email: User's email address
        db: Database session

    Returns:
        str: Reset token (plain - this is sent to user via email)
    """
    # Generate secure random token (this is what the user receives)
    plain_token = secrets.token_urlsafe(32)  # More secure than UUID

    # Hash the token before storing
    token_hash = _hash_token(plain_token)

    # Create database record with 1 hour expiration
    # Store the HASH, not the plain token
    reset_token = PasswordResetToken(
        token=token_hash,  # SECURITY: Hashed token stored
        email=email,
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )

    db.add(reset_token)
    db.commit()

    logger.info(f"Password reset token created for {email[:3]}***")

    # Return the plain token (this goes in the email)
    return plain_token


def validate_reset_token(token: str, db: Session) -> str | None:
    """
    Validate reset token and return email if valid.

    SECURITY: The incoming token is hashed and compared against the
    stored hash. This prevents timing attacks and ensures tokens
    cannot be extracted from the database.

    Args:
        token: Reset token to validate (plain token from email link)
        db: Database session

    Returns:
        str | None: Email if token is valid, None otherwise
    """
    # Hash the incoming token to compare with stored hash
    token_hash = _hash_token(token)

    # Query database for the hashed token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token_hash
    ).first()

    if not reset_token:
        logger.debug("Reset token not found")
        return None

    # Check if token is valid (not expired and not used)
    if not reset_token.is_valid:
        logger.debug("Reset token expired or already used")
        return None

    return reset_token.email


def invalidate_reset_token(token: str, db: Session):
    """Mark token as used after successful password reset."""
    # Hash the token to find it in the database
    token_hash = _hash_token(token)

    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token_hash
    ).first()

    if reset_token:
        reset_token.used = True
        db.commit()


# ============================================================================
# FORGOT PASSWORD ENDPOINT
# ============================================================================

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("3/hour")  # SECURITY: Prevent email bombing
async def forgot_password(
    http_request: Request,  # Required for rate limiting
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset email.

    SECURITY: Rate limited to 3 requests per hour per IP to prevent:
    - Email bombing attacks
    - Email enumeration attempts
    - Spam/abuse of email service

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
            logger.error(f"Failed to send password reset email to {email[:3]}***")

        # SECURITY AUDIT: Log password reset request
        log_password_reset_requested(
            email=email,
            user_id=user.id,
            request=http_request,
            db=db,
        )

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
@limiter.limit("5/hour")  # SECURITY: Prevent brute force token guessing
async def reset_password(
    http_request: Request,  # Required for rate limiting
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using valid token.

    SECURITY: Rate limited to 5 requests per hour per IP to prevent:
    - Brute force token guessing
    - Credential stuffing attacks

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

    # SECURITY AUDIT: Log successful password change
    log_password_changed(
        user_id=user.id,
        user_email=email,
        via_reset=True,
        request=http_request,
        db=db,
    )

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
