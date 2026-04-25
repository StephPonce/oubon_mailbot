"""
JWT AUTHENTICATION HANDLER
==========================

Secure token-based authentication for Ospra Intelligence.

Features:
- JWT access tokens (15 min expiry)
- Refresh tokens (7 day expiry)
- Token blacklisting for logout
- Secure password hashing (passlib/bcrypt)

STANDARDIZED: Uses python-jose and passlib for consistency with jwt_auth.py

Author: Ospra OS
Date: December 2024
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import logging

# JWT handling - standardized on python-jose (same as jwt_auth.py)
try:
    from jose import jwt, JWTError
    from jose.exceptions import ExpiredSignatureError
    HAS_JWT = True
except ImportError:
    jwt = None
    JWTError = Exception
    ExpiredSignatureError = Exception
    HAS_JWT = False
    print("[WARNING]  python-jose not installed. Run: pip install python-jose[cryptography]")

# Password hashing - call bcrypt directly (passlib's bcrypt backend
# self-test crashes against bcrypt>=4 because of the 72-byte limit).
import hashlib as _hashlib
try:
    import bcrypt as _bcrypt
    pwd_context = None  # legacy alias kept for downstream imports
    HAS_BCRYPT = True
except ImportError:
    _bcrypt = None
    pwd_context = None
    HAS_BCRYPT = False
    print("[WARNING]  bcrypt not installed. Run: pip install bcrypt")

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

def _get_jwt_secret() -> str:
    """Get JWT secret key, requiring it in production."""
    secret = os.getenv("JWT_SECRET_KEY")

    if secret:
        return secret

    # Check if we're in production
    is_production = (
        os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") or
        os.getenv("RENDER", "") == "true" or
        os.getenv("RAILWAY_ENVIRONMENT", "") != "" or
        os.getenv("VERCEL", "") == "1"
    )

    if is_production:
        raise RuntimeError(
            "CRITICAL: JWT_SECRET_KEY must be set in production! "
            "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    # Development only - warn and use insecure default
    import warnings
    warnings.warn(
        "JWT_SECRET_KEY not set! Using insecure default for development only. "
        "Tokens will be invalidated on server restart.",
        RuntimeWarning
    )
    logger.warning(
        "[WARNING]  JWT_SECRET_KEY not set! Using insecure default. "
        "Set JWT_SECRET_KEY in .env for production."
    )
    return "ospra-dev-jwt-handler-DO-NOT-USE-IN-PRODUCTION"

JWT_SECRET_KEY = _get_jwt_secret()
JWT_ALGORITHM = "HS256"

# Token expiry times
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived for security
REFRESH_TOKEN_EXPIRE_DAYS = 7    # Longer-lived for convenience


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TokenPayload:
    """Decoded JWT token payload."""
    user_id: int
    email: str
    tier: str
    token_type: str  # "access" or "refresh"
    jti: str  # Unique token ID for revocation
    exp: datetime
    iat: datetime
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.now(timezone.utc) > self.exp
    
    def time_until_expiry(self) -> timedelta:
        """Get time remaining until expiry."""
        return self.exp - datetime.now(timezone.utc)


@dataclass 
class TokenPair:
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds


# ============================================================================
# TOKEN BLACKLIST (Redis with In-Memory Fallback)
# ============================================================================

# Import persistent token blacklist from security module
try:
    from ospra_os.security.production_security import get_token_blacklist, TokenBlacklist
    _persistent_blacklist = get_token_blacklist()
    logger.info(
        f"[SUCCESS] Token blacklist initialized "
        f"(persistent={_persistent_blacklist.is_persistent})"
    )
except ImportError as e:
    logger.warning(f"[WARNING] Could not import TokenBlacklist: {e}")
    _persistent_blacklist = None


def blacklist_token(jti: str) -> None:
    """Add token to blacklist (for logout).

    Uses Redis if available, falls back to in-memory.
    """
    if _persistent_blacklist:
        _persistent_blacklist.add(jti)
    else:
        # Fallback to module-level set if import failed
        _fallback_blacklist.add(jti)
    logger.info(f"Token blacklisted: {jti[:8]}...")


def is_token_blacklisted(jti: str) -> bool:
    """Check if token is blacklisted."""
    if _persistent_blacklist:
        return _persistent_blacklist.is_blacklisted(jti)
    return jti in _fallback_blacklist


def clear_blacklist() -> None:
    """Clear all blacklisted tokens (for testing only)."""
    if _persistent_blacklist:
        _persistent_blacklist.clear()
    _fallback_blacklist.clear()


# Emergency fallback if security module fails to load
_fallback_blacklist: set = set()


# ============================================================================
# PASSWORD HASHING (Standardized on passlib - same as jwt_auth.py)
# ============================================================================

_BCRYPT_ROUNDS = 12


def _pre_hash(password: str) -> bytes:
    """SHA-256 pre-hash to lift bcrypt's 72-byte ceiling."""
    return _hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")


def hash_password(password: str) -> str:
    """
    Hash a password using SHA-256 + bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string ($2b$… bcrypt format)
    """
    if not HAS_BCRYPT or _bcrypt is None:
        raise RuntimeError("bcrypt not installed")

    salt = _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return _bcrypt.hashpw(_pre_hash(password), salt).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against its hash.

    Tries the new SHA-256 + bcrypt scheme first, then falls back to
    plain bcrypt for any legacy hashes from before the pre-hash
    migration.

    Args:
        password: Plain text password to check
        hashed: Stored password hash

    Returns:
        True if password matches
    """
    if not HAS_BCRYPT or _bcrypt is None:
        raise RuntimeError("bcrypt not installed")

    if not hashed:
        return False
    hash_bytes = hashed.encode("ascii")

    # New scheme.
    try:
        if _bcrypt.checkpw(_pre_hash(password), hash_bytes):
            return True
    except (ValueError, TypeError) as e:
        logger.debug(f"Pre-hash verify path: {e}")

    # Legacy bcrypt-only fallback.
    try:
        secret = password.encode("utf-8")
        if len(secret) > 72:
            secret = secret[:72]
        return _bcrypt.checkpw(secret, hash_bytes)
    except (ValueError, TypeError) as e:
        logger.error(f"Password verification error: {e}")
        return False


# ============================================================================
# TOKEN CREATION
# ============================================================================

def create_access_token(
    user_id: int,
    email: str,
    tier: str = "nest",
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's database ID
        email: User's email
        tier: Subscription tier (nest/flight/soar/stratosphere)
        expires_delta: Custom expiration time

    Returns:
        JWT access token string
    """
    if not HAS_JWT:
        raise RuntimeError("python-jose not installed")
    
    # Set expiration
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Generate unique token ID
    jti = secrets.token_hex(16)
    
    # Build payload
    payload = {
        "sub": str(user_id),  # Subject (user ID)
        "email": email,
        "tier": tier,
        "type": "access",
        "jti": jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    
    # Encode token
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    logger.debug(f"Created access token for user {user_id}, expires {expire}")
    
    return token


def create_refresh_token(
    user_id: int,
    email: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.

    Refresh tokens are longer-lived and used to obtain new access tokens.

    Args:
        user_id: User's database ID
        email: User's email
        expires_delta: Custom expiration time

    Returns:
        JWT refresh token string
    """
    if not HAS_JWT:
        raise RuntimeError("python-jose not installed")
    
    # Set expiration (longer than access token)
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Generate unique token ID
    jti = secrets.token_hex(16)
    
    # Build payload (minimal data for refresh tokens)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "refresh",
        "jti": jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    
    # Encode token
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    logger.debug(f"Created refresh token for user {user_id}, expires {expire}")
    
    return token


def create_token_pair(
    user_id: int,
    email: str,
    tier: str = "nest"
) -> TokenPair:
    """
    Create both access and refresh tokens.
    
    Args:
        user_id: User's database ID
        email: User's email
        tier: Subscription tier
        
    Returns:
        TokenPair with both tokens
    """
    access_token = create_access_token(user_id, email, tier)
    refresh_token = create_refresh_token(user_id, email)
    
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


# ============================================================================
# TOKEN VALIDATION
# ============================================================================

def decode_token(token: str) -> Optional[TokenPayload]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenPayload if valid, None if invalid
    """
    if not HAS_JWT:
        raise RuntimeError("python-jose not installed")

    try:
        # Decode token using python-jose
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        # Check if blacklisted
        jti = payload.get("jti", "")
        if is_token_blacklisted(jti):
            logger.warning(f"Attempted use of blacklisted token: {jti[:8]}...")
            return None

        # Build TokenPayload
        return TokenPayload(
            user_id=int(payload.get("sub", 0)),
            email=payload.get("email", ""),
            tier=payload.get("tier", "nest"),
            token_type=payload.get("type", "access"),
            jti=jti,
            exp=datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc),
            iat=datetime.fromtimestamp(payload.get("iat", 0), tz=timezone.utc),
        )

    except ExpiredSignatureError:
        logger.debug("Token expired")
        return None

    except JWTError as e:
        logger.warning(f"Invalid token: {e}")
        return None

    except Exception as e:
        logger.error(f"Token decode error: {e}")
        return None


def validate_access_token(token: str) -> Optional[TokenPayload]:
    """
    Validate an access token.
    
    Args:
        token: JWT access token
        
    Returns:
        TokenPayload if valid access token, None otherwise
    """
    payload = decode_token(token)
    
    if payload is None:
        return None
    
    # Verify it's an access token
    if payload.token_type != "access":
        logger.warning("Refresh token used as access token")
        return None
    
    return payload


def validate_refresh_token(token: str) -> Optional[TokenPayload]:
    """
    Validate a refresh token.
    
    Args:
        token: JWT refresh token
        
    Returns:
        TokenPayload if valid refresh token, None otherwise
    """
    payload = decode_token(token)
    
    if payload is None:
        return None
    
    # Verify it's a refresh token
    if payload.token_type != "refresh":
        logger.warning("Access token used as refresh token")
        return None
    
    return payload


# ============================================================================
# TOKEN REFRESH
# ============================================================================

def refresh_access_token(refresh_token: str, tier: str = "nest") -> Optional[Tuple[str, str]]:
    """
    Use a refresh token to get a new access token.
    
    Also rotates the refresh token for security.
    
    Args:
        refresh_token: Valid refresh token
        tier: User's current tier (may have changed)
        
    Returns:
        Tuple of (new_access_token, new_refresh_token) or None if invalid
    """
    # Validate refresh token
    payload = validate_refresh_token(refresh_token)
    
    if payload is None:
        return None
    
    # Blacklist old refresh token (rotation)
    blacklist_token(payload.jti)
    
    # Create new tokens
    new_access = create_access_token(payload.user_id, payload.email, tier)
    new_refresh = create_refresh_token(payload.user_id, payload.email)
    
    logger.info(f"Refreshed tokens for user {payload.user_id}")
    
    return (new_access, new_refresh)


# ============================================================================
# LOGOUT (TOKEN REVOCATION)
# ============================================================================

def logout(access_token: str, refresh_token: Optional[str] = None) -> bool:
    """
    Logout by blacklisting tokens.
    
    Args:
        access_token: Current access token
        refresh_token: Current refresh token (optional but recommended)
        
    Returns:
        True if successful
    """
    success = True
    
    # Blacklist access token
    access_payload = decode_token(access_token)
    if access_payload:
        blacklist_token(access_payload.jti)
    else:
        success = False
    
    # Blacklist refresh token if provided
    if refresh_token:
        refresh_payload = decode_token(refresh_token)
        if refresh_payload:
            blacklist_token(refresh_payload.jti)
        else:
            success = False
    
    return success


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def extract_token_from_header(authorization: str) -> Optional[str]:
    """
    Extract JWT token from Authorization header.
    
    Args:
        authorization: Full Authorization header value
        
    Returns:
        Token string or None
    """
    if not authorization:
        return None
    
    parts = authorization.split()
    
    if len(parts) != 2:
        return None
    
    scheme, token = parts
    
    if scheme.lower() != "bearer":
        return None
    
    return token


def get_token_info(token: str) -> Dict[str, Any]:
    """
    Get information about a token (for debugging).
    
    Args:
        token: JWT token
        
    Returns:
        Dict with token info
    """
    payload = decode_token(token)
    
    if payload is None:
        return {"valid": False, "error": "Invalid or expired token"}
    
    return {
        "valid": True,
        "user_id": payload.user_id,
        "email": payload.email,
        "tier": payload.tier,
        "type": payload.token_type,
        "expires_at": payload.exp.isoformat(),
        "issued_at": payload.iat.isoformat(),
        "time_until_expiry": str(payload.time_until_expiry()),
        "is_expired": payload.is_expired(),
        "is_blacklisted": is_token_blacklisted(payload.jti)
    }
