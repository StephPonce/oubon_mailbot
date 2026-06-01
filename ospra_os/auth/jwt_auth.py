"""
JWT Authentication System for Ospra Intelligence
================================================

Provides:
- Password hashing with bcrypt
- JWT token generation/validation
- FastAPI dependencies for protected routes
- Session-based user identification (replaces user_id query params)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import bcrypt as _bcrypt
from pydantic import BaseModel, ConfigDict, EmailStr

# Import from correct modular architecture (NOT legacy multi_store_models!)
from ospra_os.database import User, SubscriptionTier, get_db
from ospra_os.database.connection import SessionLocal


# ============================================================================
# CONFIGURATION
# ============================================================================

# Secret key for JWT signing - REQUIRED in production
_jwt_secret = os.getenv("JWT_SECRET_KEY")
if not _jwt_secret:
    import warnings
    warnings.warn(
        "JWT_SECRET_KEY environment variable not set! "
        "Using insecure default for development only. "
        "Set JWT_SECRET_KEY in production!",
        RuntimeWarning
    )
    # Only allow default in development - check for common production indicators
    _is_production = (
        os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") or
        os.getenv("RENDER", "") == "true" or  # Render.com deployment
        os.getenv("RAILWAY_ENVIRONMENT", "") != "" or  # Railway deployment
        os.getenv("VERCEL", "") == "1"  # Vercel deployment
    )
    if _is_production:
        raise RuntimeError(
            "CRITICAL: JWT_SECRET_KEY must be set in production! "
            "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    _jwt_secret = "ospra-dev-secret-DO-NOT-USE-IN-PRODUCTION"

SECRET_KEY = _jwt_secret
ALGORITHM = "HS256"
# Token lifetimes — SINGLE SOURCE OF TRUTH for the whole app. jwt_handler
# imports these (rather than defining its own) so the two JWT modules can
# never silently drift. They previously disagreed (jwt_auth 24h/30d vs
# jwt_handler 15m/7d); jwt_auth is the live mint path, so we standardize here.
# Override via env to tighten the access-token lifetime once the frontend's
# refresh flow is confirmed to handle shorter sessions.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))  # default 24h
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))


# ============================================================================
# PASSWORD HASHING
# ============================================================================

# =============================================================================
# bcrypt directly — no passlib
# =============================================================================
#
# We previously used ``passlib.context.CryptContext(schemes=["bcrypt"])``,
# but passlib 1.7.4 runs an internal self-test the first time the bcrypt
# backend is loaded. That self-test sends a >72-byte secret through
# bcrypt to detect a long-truncation behaviour. bcrypt 4.x and 5.x raise
# ``ValueError`` on >72-byte input instead of truncating, so the
# self-test crashes before any of our code can run. The result is every
# login/registration call dies with
#   ``password cannot be longer than 72 bytes`` — even for a 17-char
# password — purely because passlib never finishes initialising.
#
# Calling the bcrypt library directly avoids the broken self-test and
# also lets us pre-hash with SHA-256 to lift the 72-byte ceiling for end
# users. The on-disk hash format is unchanged ($2b$…), so existing
# bcrypt-only hashes from before this migration still verify via the
# legacy fallback in ``verify_password``.
#
# bcrypt cost factor — 12 is the OWASP 2024 recommendation; raise to
# 13/14 if a CPU upgrade makes 12 too cheap.
_BCRYPT_ROUNDS = 12


def _pre_hash(password: str) -> bytes:
    """Pre-hash the password to a fixed 64-byte hex string before bcrypt.

    bcrypt has a hard 72-byte input limit. bcrypt>=4 (we're on 5.0)
    raises ``ValueError`` when handed anything longer; older versions
    silently truncated. The industry-standard mitigation — used by
    Dropbox, AWS Cognito, and others — is to SHA-256 the password first
    so the input to bcrypt is always exactly 64 hex chars regardless of
    how long the user's password is. This:

      • lifts the 72-byte ceiling (users can paste passphrases)
      • keeps bcrypt's slow-hash properties intact
      • makes the verify path deterministic across bcrypt versions
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 + bcrypt (see ``_pre_hash``)."""
    salt = _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return _bcrypt.hashpw(_pre_hash(password), salt).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Tries the new SHA-256 + bcrypt scheme first. Falls back to plain
    bcrypt for any legacy hashes that pre-date the pre-hash migration —
    those will still verify, and the caller is expected to re-hash and
    persist the new format on the next successful auth call.
    """
    if not hashed_password:
        return False
    hash_bytes = hashed_password.encode("ascii")
    # New scheme: SHA-256 → bcrypt
    try:
        if _bcrypt.checkpw(_pre_hash(plain_password), hash_bytes):
            return True
    except (ValueError, TypeError):
        # Malformed hash — fall through to the legacy attempt.
        pass
    # Legacy bcrypt-only hashes.
    try:
        secret = plain_password.encode("utf-8")
        # bcrypt 5.x raises on >72 bytes; legacy hashes were created
        # against passwords that fit, but truncate defensively.
        if len(secret) > 72:
            secret = secret[:72]
        return _bcrypt.checkpw(secret, hash_bytes)
    except (ValueError, TypeError):
        return False


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TokenData(BaseModel):
    """Data encoded in JWT token"""
    user_id: int
    email: str
    tier: str
    exp: datetime


class TokenResponse(BaseModel):
    """Response when issuing tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: dict


class UserCreate(BaseModel):
    """Request body for user registration"""
    email: EmailStr
    password: str
    name: Optional[str] = None  # Optional - will default to email username
    tier: Optional[str] = "nest"  # Default tier


class UserLogin(BaseModel):
    """Request body for login"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User data returned to client (no sensitive info)"""
    id: int
    email: str
    name: str
    subscription_tier: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# TOKEN GENERATION
# ============================================================================

def create_access_token(user: User) -> str:
    """
    Create JWT access token for a user.
    
    Args:
        user: User model instance
        
    Returns:
        Encoded JWT string
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(user.id),  # Subject (user ID as string)
        "email": user.email,
        "tier": user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user: User) -> str:
    """
    Create JWT refresh token for a user.
    
    Args:
        user: User model instance
        
    Returns:
        Encoded JWT string
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "sub": str(user.id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT string
        
    Returns:
        Decoded payload dict
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# DATABASE HELPERS
# ============================================================================

# NOTE: get_db() is imported from ospra_os.database (consolidated implementation)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email address"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user_data: UserCreate) -> User:
    """
    Create a new user.
    
    Args:
        db: Database session
        user_data: User registration data
        
    Returns:
        Created User instance
        
    Raises:
        HTTPException: If email already exists
    """
    # Check if email exists
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Default name to email username if not provided
    user_name = user_data.name if user_data.name else user_data.email.split("@")[0]
    
    # Create user with hashed password
    user = User(
        email=user_data.email,
        name=user_name,
        password_hash=hash_password(user_data.password),
        subscription_tier=SubscriptionTier.NEST,  # Start at free tier
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        # Log the error for debugging
        print(f"[ERROR] Failed to create user {user_data.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account. Please try again."
        )

    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate user with email and password.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password
        
    Returns:
        User if authenticated, None otherwise
    """
    user = get_user_by_email(db, email)
    
    if not user:
        return None
    
    # Check if user has password_hash (for migrated users)
    if not hasattr(user, 'password_hash') or not user.password_hash:
        return None
        
    if not verify_password(password, user.password_hash):
        return None
        
    return user


# ============================================================================
# FASTAPI DEPENDENCIES
# ============================================================================

# HTTP Bearer scheme for token extraction
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get current authenticated user.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id}
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
        
    Returns:
        Authenticated User instance
        
    Raises:
        HTTPException: If not authenticated or token invalid
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decode token
    payload = decode_token(credentials.credentials)
    
    # Validate token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user ID from token
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch user from database
    user = get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    try:
        user.last_login = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        # Non-critical error - don't fail auth if last_login update fails
        print(f"[WARNING] Failed to update last_login for user {user.id}: {str(e)}")

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    FastAPI dependency for optional authentication.
    Returns None if not authenticated instead of raising exception.
    
    Usage:
        @router.get("/public-or-personalized")
        async def route(user: Optional[User] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello, {user.name}!"}
            return {"message": "Hello, guest!"}
    """
    if not credentials:
        return None
    
    try:
        payload = decode_token(credentials.credentials)
        
        if payload.get("type") != "access":
            return None
            
        user_id = payload.get("sub")
        if not user_id:
            return None
            
        return get_user_by_id(db, int(user_id))
        
    except HTTPException:
        return None


def require_tier(min_tier: str):
    """
    FastAPI dependency factory to require minimum subscription tier.
    
    Usage:
        @router.get("/pro-feature")
        async def pro_feature(user: User = Depends(require_tier("soar"))):
            return {"access": "granted"}
    
    Args:
        min_tier: Minimum required tier ("nest", "flight", "soar", "stratosphere")
        
    Returns:
        Dependency function
    """
    tier_order = ["nest", "flight", "soar", "stratosphere"]
    
    async def tier_checker(user: User = Depends(get_current_user)) -> User:
        user_tier = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
        
        user_tier_index = tier_order.index(user_tier.lower()) if user_tier.lower() in tier_order else 0
        required_tier_index = tier_order.index(min_tier.lower()) if min_tier.lower() in tier_order else 0
        
        if user_tier_index < required_tier_index:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "tier_required",
                    "message": f"This feature requires {min_tier.capitalize()} tier or higher",
                    "current_tier": user_tier,
                    "required_tier": min_tier,
                    "upgrade_url": f"/subscription/upgrade?to={min_tier}"
                }
            )
        
        return user
    
    return tier_checker


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def user_to_dict(user: User) -> dict:
    """Convert User model to safe dictionary (no password)"""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "subscription_tier": user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def generate_tokens(user: User) -> TokenResponse:
    """Generate access and refresh tokens for a user"""
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_to_dict(user)
    )
