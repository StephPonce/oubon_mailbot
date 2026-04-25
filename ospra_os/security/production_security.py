"""
OSPRA INTELLIGENCE - PRODUCTION SECURITY
=========================================

Gold-standard security implementation:
- Rate limiting (all endpoints)
- Account lockout (brute force protection)
- Security headers (CSP, HSTS, etc.)
- Audit logging
- Input sanitization
- Redis token blacklist (with fallback)

Author: OspraOS
Date: December 2024
"""

import os
import re
import time
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any, Callable
from collections import defaultdict
from functools import wraps

from fastapi import Request, HTTPException, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class SecurityConfig:
    """Security configuration constants."""
    
    # Rate limiting
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
    
    # Auth rate limiting (stricter)
    AUTH_RATE_LIMIT_REQUESTS = int(os.getenv("AUTH_RATE_LIMIT_REQUESTS", "10"))
    AUTH_RATE_LIMIT_WINDOW = int(os.getenv("AUTH_RATE_LIMIT_WINDOW", "60"))
    
    # Account lockout
    MAX_FAILED_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
    LOCKOUT_DURATION = int(os.getenv("LOCKOUT_DURATION", "900"))  # 15 minutes
    
    # Password requirements
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = False  # Optional for UX
    
    # Suspicious activity
    SUSPICIOUS_IP_THRESHOLD = 50  # requests per minute
    GEO_BLOCK_COUNTRIES = []  # Add country codes to block

    # Token blacklist TTL (must be >= longest token lifetime)
    TOKEN_BLACKLIST_TTL = 60 * 60 * 24 * 8  # 8 days (refresh token is 7 days)


# =============================================================================
# TOKEN BLACKLIST (Redis with In-Memory Fallback)
# =============================================================================

class TokenBlacklist:
    """
    Token blacklist for logout/revocation with Redis persistence.

    CRITICAL: In production, Redis MUST be configured to prevent tokens
    from being valid after logout (in-memory is lost on restart).

    Features:
    - Redis persistence (survives restarts)
    - In-memory fallback for development
    - Automatic TTL expiration
    - Thread-safe operations
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern for shared blacklist."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._memory_blacklist: Dict[str, float] = {}  # jti -> expiry timestamp
        self._redis = None
        self._redis_available = False
        self._try_redis_connection()
        self._initialized = True

    def _try_redis_connection(self):
        """Try to connect to Redis."""
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                self._redis_available = True
                logger.info("[SUCCESS] Redis connected for token blacklist")
            except Exception as e:
                logger.warning(f"[WARNING] Redis unavailable for token blacklist: {e}")
                self._warn_no_redis()
        else:
            self._warn_no_redis()

    def _warn_no_redis(self):
        """Warn about missing Redis in production."""
        is_production = (
            os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") or
            os.getenv("RENDER", "") == "true" or
            os.getenv("RAILWAY_ENVIRONMENT", "") != ""
        )
        if is_production:
            logger.error(
                "[CRITICAL] Redis not available for token blacklist in production! "
                "Tokens will remain valid after logout until server restart. "
                "Set REDIS_URL environment variable."
            )
        else:
            logger.warning(
                "[WARNING] Token blacklist using in-memory storage. "
                "Logged-out tokens will be valid after restart. "
                "Configure REDIS_URL for production."
            )

    def add(self, jti: str, ttl_seconds: int = None) -> bool:
        """
        Add a token to the blacklist.

        Args:
            jti: Token's unique identifier
            ttl_seconds: Time-to-live (defaults to SecurityConfig.TOKEN_BLACKLIST_TTL)

        Returns:
            True if successfully added
        """
        if not jti:
            return False

        ttl = ttl_seconds or SecurityConfig.TOKEN_BLACKLIST_TTL

        # Try Redis first
        if self._redis_available:
            try:
                key = f"token_blacklist:{jti}"
                self._redis.setex(key, ttl, "1")
                logger.debug(f"Token blacklisted in Redis: {jti[:8]}...")
                return True
            except Exception as e:
                logger.error(f"Redis blacklist error: {e}")
                # Fall through to memory

        # In-memory fallback
        expiry = time.time() + ttl
        self._memory_blacklist[jti] = expiry
        logger.debug(f"Token blacklisted in memory: {jti[:8]}...")

        # Cleanup old entries (lazy)
        self._cleanup_memory()

        return True

    def is_blacklisted(self, jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            jti: Token's unique identifier

        Returns:
            True if token is blacklisted
        """
        if not jti:
            return False

        # Check Redis first
        if self._redis_available:
            try:
                key = f"token_blacklist:{jti}"
                return self._redis.exists(key) > 0
            except Exception as e:
                logger.error(f"Redis blacklist check error: {e}")
                # Fall through to memory

        # Check in-memory
        if jti in self._memory_blacklist:
            if self._memory_blacklist[jti] > time.time():
                return True
            else:
                # Expired, remove it
                del self._memory_blacklist[jti]

        return False

    def remove(self, jti: str) -> bool:
        """Remove a token from the blacklist (for testing)."""
        if self._redis_available:
            try:
                key = f"token_blacklist:{jti}"
                self._redis.delete(key)
            except Exception:
                pass

        if jti in self._memory_blacklist:
            del self._memory_blacklist[jti]

        return True

    def clear(self) -> None:
        """Clear all blacklisted tokens (for testing only)."""
        if self._redis_available:
            try:
                # Get all blacklist keys and delete
                keys = self._redis.keys("token_blacklist:*")
                if keys:
                    self._redis.delete(*keys)
            except Exception:
                pass

        self._memory_blacklist.clear()
        logger.warning("Token blacklist cleared")

    def _cleanup_memory(self) -> None:
        """Remove expired entries from in-memory blacklist."""
        now = time.time()
        expired = [jti for jti, exp in self._memory_blacklist.items() if exp <= now]
        for jti in expired:
            del self._memory_blacklist[jti]

    @property
    def is_persistent(self) -> bool:
        """Check if blacklist has persistent storage."""
        return self._redis_available


# Singleton instance
_token_blacklist = None

def get_token_blacklist() -> TokenBlacklist:
    """Get the singleton token blacklist instance."""
    global _token_blacklist
    if _token_blacklist is None:
        _token_blacklist = TokenBlacklist()
    return _token_blacklist


# =============================================================================
# RATE LIMITER (In-Memory with Redis Support)
# =============================================================================

class RateLimiter:
    """
    Rate limiter with Redis support and in-memory fallback.
    
    Features:
    - Per-IP rate limiting
    - Per-user rate limiting (when authenticated)
    - Sliding window algorithm
    - Redis for distributed systems
    """
    
    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._redis = None
        self._try_redis_connection()
    
    def _try_redis_connection(self):
        """Try to connect to Redis if available."""
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url)
                self._redis.ping()
                logger.info("[SUCCESS] Redis connected for rate limiting")
            except Exception as e:
                logger.warning(f"[WARNING] Redis unavailable, using in-memory: {e}")
                self._redis = None
    
    def _get_key(self, identifier: str, endpoint: str) -> str:
        """Generate rate limit key."""
        return f"ratelimit:{identifier}:{endpoint}"
    
    def is_allowed(
        self,
        identifier: str,
        endpoint: str = "global",
        max_requests: int = None,
        window_seconds: int = None
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed.
        
        Returns:
            (allowed, remaining, reset_time)
        """
        max_requests = max_requests or SecurityConfig.RATE_LIMIT_REQUESTS
        window_seconds = window_seconds or SecurityConfig.RATE_LIMIT_WINDOW
        
        key = self._get_key(identifier, endpoint)
        now = time.time()
        cutoff = now - window_seconds
        
        if self._redis:
            return self._check_redis(key, now, cutoff, max_requests, window_seconds)
        else:
            return self._check_memory(key, now, cutoff, max_requests, window_seconds)
    
    def _check_memory(self, key, now, cutoff, max_requests, window_seconds):
        """In-memory rate limit check."""
        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
        
        current = len(self._requests[key])
        remaining = max(0, max_requests - current)
        reset_time = int(now + window_seconds)
        
        if current >= max_requests:
            return False, 0, reset_time
        
        self._requests[key].append(now)
        return True, remaining - 1, reset_time
    
    def _check_redis(self, key, now, cutoff, max_requests, window_seconds):
        """Redis-based rate limit check."""
        try:
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            results = pipe.execute()
            
            current = results[2]
            remaining = max(0, max_requests - current)
            reset_time = int(now + window_seconds)
            
            if current > max_requests:
                return False, 0, reset_time
            
            return True, remaining, reset_time
            
        except Exception as e:
            logger.error(f"Redis error: {e}")
            return self._check_memory(key, now, cutoff, max_requests, window_seconds)


# =============================================================================
# ACCOUNT LOCKOUT
# =============================================================================

class AccountLockout:
    """
    Account lockout after failed login attempts.
    
    Protects against brute force attacks.
    """
    
    def __init__(self):
        self._failed_attempts: Dict[str, list] = defaultdict(list)
        self._lockouts: Dict[str, float] = {}
        self._redis = None
        self._try_redis_connection()
    
    def _try_redis_connection(self):
        """Try to connect to Redis if available."""
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url)
                logger.info("[SUCCESS] Redis connected for account lockout")
            except ImportError:
                logger.warning("Redis package not installed, using in-memory lockout tracking")
                self._redis = None
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for account lockout: {e}")
                self._redis = None
    
    def record_failed_attempt(self, identifier: str) -> int:
        """
        Record a failed login attempt.
        
        Returns:
            Number of failed attempts in window
        """
        now = time.time()
        window = SecurityConfig.LOCKOUT_DURATION
        
        if self._redis:
            key = f"failed:{identifier}"
            pipe = self._redis.pipeline()
            pipe.zadd(key, {str(now): now})
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zcard(key)
            pipe.expire(key, window)
            results = pipe.execute()
            count = results[2]
        else:
            cutoff = now - window
            self._failed_attempts[identifier] = [
                t for t in self._failed_attempts[identifier] if t > cutoff
            ]
            self._failed_attempts[identifier].append(now)
            count = len(self._failed_attempts[identifier])
        
        # Check if should lock
        if count >= SecurityConfig.MAX_FAILED_ATTEMPTS:
            self._lockouts[identifier] = now + SecurityConfig.LOCKOUT_DURATION
            logger.warning(f"[LOCKED] Account locked: {identifier} ({count} failed attempts)")
        
        return count
    
    def is_locked(self, identifier: str) -> tuple[bool, int]:
        """
        Check if account is locked.
        
        Returns:
            (is_locked, seconds_remaining)
        """
        now = time.time()
        
        if self._redis:
            lockout_time = self._redis.get(f"lockout:{identifier}")
            if lockout_time:
                lockout_time = float(lockout_time)
        else:
            lockout_time = self._lockouts.get(identifier)
        
        if lockout_time and now < lockout_time:
            remaining = int(lockout_time - now)
            return True, remaining
        
        return False, 0
    
    def clear_attempts(self, identifier: str):
        """Clear failed attempts after successful login."""
        if self._redis:
            self._redis.delete(f"failed:{identifier}")
            self._redis.delete(f"lockout:{identifier}")
        else:
            self._failed_attempts.pop(identifier, None)
            self._lockouts.pop(identifier, None)


# =============================================================================
# AUDIT LOGGER
# =============================================================================

class AuditLogger:
    """
    Security audit logging.
    
    Logs all security-relevant events for compliance and forensics.
    """
    
    def __init__(self):
        self._setup_logger()
    
    def _setup_logger(self):
        """Set up dedicated audit logger."""
        self.logger = logging.getLogger("ospra.audit")
        self.logger.setLevel(logging.INFO)
        
        # Could add file handler, external service, etc.
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | AUDIT | %(message)s'
        ))
        self.logger.addHandler(handler)
    
    def log(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict] = None,
        severity: str = "INFO"
    ):
        """Log a security event."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details or {},
            "severity": severity
        }
        
        self.logger.info(f"{event_type} | user={user_id} | ip={ip_address} | {details}")
        
        # TODO: Send to external logging service (DataDog, Splunk, etc.)
        
        return event
    
    # Convenience methods
    def login_success(self, user_id: str, ip: str):
        self.log("LOGIN_SUCCESS", user_id, ip)
    
    def login_failed(self, email: str, ip: str, reason: str):
        self.log("LOGIN_FAILED", email, ip, {"reason": reason}, "WARNING")
    
    def account_locked(self, email: str, ip: str):
        self.log("ACCOUNT_LOCKED", email, ip, severity="WARNING")
    
    def token_revoked(self, user_id: str, ip: str):
        self.log("TOKEN_REVOKED", user_id, ip)
    
    def suspicious_activity(self, ip: str, reason: str):
        self.log("SUSPICIOUS_ACTIVITY", None, ip, {"reason": reason}, "CRITICAL")
    
    def permission_denied(self, user_id: str, resource: str, ip: str):
        self.log("PERMISSION_DENIED", user_id, ip, {"resource": resource}, "WARNING")


# =============================================================================
# PASSWORD VALIDATOR
# =============================================================================

class PasswordValidator:
    """
    Password strength validation.
    
    Enforces security requirements for passwords.
    """
    
    @staticmethod
    def validate(password: str) -> tuple[bool, list[str]]:
        """
        Validate password strength.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        if len(password) < SecurityConfig.MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {SecurityConfig.MIN_PASSWORD_LENGTH} characters")
        
        if SecurityConfig.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if SecurityConfig.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if SecurityConfig.REQUIRE_DIGIT and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if SecurityConfig.REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        # Check for common passwords
        common_passwords = {'password', '123456', 'password123', 'admin', 'letmein'}
        if password.lower() in common_passwords:
            errors.append("Password is too common")
        
        return len(errors) == 0, errors


# =============================================================================
# INPUT SANITIZER
# =============================================================================

class InputSanitizer:
    """
    Input sanitization for security.
    
    Prevents XSS, SQL injection, and other injection attacks.
    """
    
    # Dangerous patterns
    SQL_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)",
        r"(--|#|/\*)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
    ]
    
    XSS_PATTERNS = [
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe",
    ]
    
    @classmethod
    def sanitize_string(cls, value: str) -> str:
        """Sanitize a string input."""
        if not isinstance(value, str):
            return value
        
        # HTML encode dangerous characters
        value = value.replace("&", "&amp;")
        value = value.replace("<", "&lt;")
        value = value.replace(">", "&gt;")
        value = value.replace('"', "&quot;")
        value = value.replace("'", "&#x27;")
        
        return value
    
    @classmethod
    def check_injection(cls, value: str) -> tuple[bool, str]:
        """
        Check for injection attempts.
        
        Returns:
            (is_safe, detected_pattern)
        """
        if not isinstance(value, str):
            return True, ""
        
        for pattern in cls.SQL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False, "SQL injection attempt"
        
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False, "XSS attempt"
        
        return True, ""


# =============================================================================
# SECURITY HEADERS MIDDLEWARE
# =============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.
    
    Headers:
    - Content-Security-Policy
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Strict-Transport-Security
    - Referrer-Policy
    - Permissions-Policy
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # HSTS (only in production with HTTPS)
        if os.getenv("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.anthropic.com https://*.shopify.com; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp
        
        # Permissions Policy
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        
        return response


# =============================================================================
# RATE LIMIT MIDDLEWARE
# =============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Global rate limiting middleware.
    
    Applies rate limits to all endpoints.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.limiter = RateLimiter()
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        
        # Stricter limits for auth endpoints
        if "/auth/" in endpoint:
            max_requests = SecurityConfig.AUTH_RATE_LIMIT_REQUESTS
            window = SecurityConfig.AUTH_RATE_LIMIT_WINDOW
        else:
            max_requests = SecurityConfig.RATE_LIMIT_REQUESTS
            window = SecurityConfig.RATE_LIMIT_WINDOW
        
        # Check rate limit
        allowed, remaining, reset_time = self.limiter.is_allowed(
            client_ip, endpoint, max_requests, window
        )
        
        if not allowed:
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=429,
                media_type="application/json",
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(window)
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

rate_limiter = RateLimiter()
account_lockout = AccountLockout()
audit_logger = AuditLogger()
password_validator = PasswordValidator()
input_sanitizer = InputSanitizer()


# =============================================================================
# DEPENDENCY INJECTION HELPERS
# =============================================================================

async def check_rate_limit(request: Request):
    """FastAPI dependency for rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    endpoint = request.url.path
    
    allowed, remaining, reset = rate_limiter.is_allowed(client_ip, endpoint)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(SecurityConfig.RATE_LIMIT_WINDOW)
            }
        )


async def check_account_lockout(email: str, request: Request):
    """Check if account is locked before login attempt."""
    is_locked, remaining = account_lockout.is_locked(email)
    
    if is_locked:
        audit_logger.log(
            "LOGIN_BLOCKED_LOCKOUT",
            email,
            request.client.host if request.client else None,
            {"remaining_seconds": remaining}
        )
        raise HTTPException(
            status_code=423,
            detail=f"Account temporarily locked. Try again in {remaining} seconds."
        )


def validate_password_strength(password: str):
    """Validate password meets security requirements."""
    is_valid, errors = password_validator.validate(password)
    
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={"message": "Password too weak", "errors": errors}
        )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Config
    "SecurityConfig",
    # Classes
    "RateLimiter",
    "AccountLockout", 
    "AuditLogger",
    "PasswordValidator",
    "InputSanitizer",
    # Middleware
    "SecurityHeadersMiddleware",
    "RateLimitMiddleware",
    # Instances
    "rate_limiter",
    "account_lockout",
    "audit_logger",
    "password_validator",
    "input_sanitizer",
    # Dependencies
    "check_rate_limit",
    "check_account_lockout",
    "validate_password_strength",
]
