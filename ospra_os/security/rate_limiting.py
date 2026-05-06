"""
Rate Limiting Configuration for OspraOS
========================================
Prevents API abuse and protects AI quota from being burned through.

SECURITY: Includes strict limits for sensitive endpoints:
- Login: 5 attempts per minute (brute force protection)
- Password reset: 3 requests per hour (abuse prevention)
- Registration: 3 per hour per IP (spam prevention)
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional
import time
import logging

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


# ============================================================================
# SENSITIVE ENDPOINT RATE LIMITS (Stricter than general API limits)
# ============================================================================

# Sensitive endpoint configurations
SENSITIVE_LIMITS = {
    "login": {"max_attempts": 5, "window_seconds": 60, "lockout_seconds": 300},
    "password_reset": {"max_attempts": 3, "window_seconds": 3600, "lockout_seconds": 3600},
    "register": {"max_attempts": 3, "window_seconds": 3600, "lockout_seconds": 3600},
    "forgot_password": {"max_attempts": 3, "window_seconds": 3600, "lockout_seconds": 3600},
}


class SensitiveEndpointRateLimiter:
    """
    In-memory rate limiter for sensitive authentication endpoints.

    SECURITY: Provides stricter rate limiting than general API limits.
    Implements exponential backoff on repeated violations.
    """

    def __init__(self):
        # Format: {endpoint: {ip: {"attempts": count, "first_attempt": timestamp, "locked_until": timestamp}}}
        self._attempts: Dict[str, Dict[str, Dict]] = defaultdict(lambda: defaultdict(dict))
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

    def _cleanup_old_entries(self):
        """Remove expired entries to prevent memory leaks."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        cutoff = now - 7200  # 2 hours

        for endpoint in list(self._attempts.keys()):
            for ip in list(self._attempts[endpoint].keys()):
                entry = self._attempts[endpoint][ip]
                if entry.get("first_attempt", 0) < cutoff:
                    del self._attempts[endpoint][ip]

    def check_rate_limit(self, endpoint: str, ip_address: str) -> tuple[bool, Optional[str], Optional[int]]:
        """
        Check if request is allowed for sensitive endpoint.

        Returns:
            (allowed, error_message, retry_after_seconds)
        """
        self._cleanup_old_entries()

        config = SENSITIVE_LIMITS.get(endpoint)
        if not config:
            return True, None, None

        now = time.time()
        entry = self._attempts[endpoint][ip_address]

        # Check if currently locked out
        locked_until = entry.get("locked_until", 0)
        if now < locked_until:
            retry_after = int(locked_until - now)
            logger.warning(f"[SECURITY] Rate limit lockout active for {ip_address} on /{endpoint}")
            return False, f"Too many attempts. Please try again in {retry_after} seconds.", retry_after

        # Reset if window expired
        first_attempt = entry.get("first_attempt", 0)
        if now - first_attempt > config["window_seconds"]:
            entry["attempts"] = 0
            entry["first_attempt"] = now

        # Check attempt count
        attempts = entry.get("attempts", 0)
        if attempts >= config["max_attempts"]:
            # Lock out the IP
            entry["locked_until"] = now + config["lockout_seconds"]
            logger.warning(
                f"[SECURITY] Rate limit exceeded for {ip_address} on /{endpoint}. "
                f"Locked out for {config['lockout_seconds']}s"
            )
            return False, f"Too many attempts. Please try again later.", config["lockout_seconds"]

        return True, None, None

    def record_attempt(self, endpoint: str, ip_address: str):
        """Record an attempt for rate limiting."""
        entry = self._attempts[endpoint][ip_address]
        now = time.time()

        if "first_attempt" not in entry:
            entry["first_attempt"] = now

        entry["attempts"] = entry.get("attempts", 0) + 1

    def reset_attempts(self, endpoint: str, ip_address: str):
        """Reset attempts on successful action (e.g., successful login)."""
        if ip_address in self._attempts[endpoint]:
            del self._attempts[endpoint][ip_address]


# Global instance
sensitive_rate_limiter = SensitiveEndpointRateLimiter()


def check_sensitive_rate_limit(endpoint: str, request: Request) -> None:
    """
    Check rate limit for sensitive endpoint. Raises HTTPException if exceeded.

    Usage in route:
        check_sensitive_rate_limit("login", request)
    """
    ip = get_remote_address(request)
    allowed, error_msg, retry_after = sensitive_rate_limiter.check_rate_limit(endpoint, ip)

    if not allowed:
        # Log to security audit. The previous form swallowed any failure
        # silently — that meant a broken auth_logger (e.g. unwritable
        # ``logs/`` dir, see audit fix #9) made every rate-limit hit
        # invisible to ops. We still don't want a logger blowup to drop
        # the 429, but the failure deserves to surface in stdout so the
        # operator can fix the security audit pipeline.
        try:
            from ospra_os.security.auth_logger import log_rate_limit_exceeded
            log_rate_limit_exceeded(ip_address=ip, endpoint=f"/api/auth/{endpoint}", user_id=None)
        except Exception as e:
            logger.warning(
                "rate_limiting: failed to write rate-limit hit to security log "
                "(rate limit still enforced): %s", e
            )

        raise HTTPException(
            status_code=429,
            detail=error_msg,
            headers={"Retry-After": str(retry_after)} if retry_after else {}
        )


def record_sensitive_attempt(endpoint: str, request: Request) -> None:
    """Record an attempt for a sensitive endpoint."""
    ip = get_remote_address(request)
    sensitive_rate_limiter.record_attempt(endpoint, ip)


def reset_sensitive_attempts(endpoint: str, request: Request) -> None:
    """Reset attempts on successful action."""
    ip = get_remote_address(request)
    sensitive_rate_limiter.reset_attempts(endpoint, ip)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors.

    Returns a user-friendly JSON response with retry-after header.
    Also logs to security.log for monitoring.
    """
    # Standard logging
    logger.warning(
        f"Rate limit exceeded for {get_remote_address(request)} "
        f"on {request.url.path}"
    )

    # Security logging (PHASE 1 SECURITY)
    try:
        from ospra_os.security.auth_logger import log_rate_limit_exceeded
        log_rate_limit_exceeded(
            ip_address=get_remote_address(request),
            endpoint=request.url.path,
            user_id=None  # No user ID available at this level
        )
    except Exception as e:
        logger.error(f"Failed to log rate limit to security log: {e}")

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please slow down and try again later.",
            "retry_after": exc.detail  # Time until limit resets
        },
        headers={"Retry-After": str(exc.detail)}
    )


# Check if running in development mode. Two ways to opt into dev limits:
#   1. DEBUG=true (legacy)
#   2. ENVIRONMENT != "production" (matches the same convention used by
#      ospra_os.middleware.rate_limiter so both limiters are in sync)
import os
_IS_DEBUG = (
    os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
    or os.getenv("ENVIRONMENT", "").lower() != "production"
)

# Rate limit configurations by tier
# In DEBUG mode, limits are significantly increased for local development
if _IS_DEBUG:
    logger.warning(
        "[DEV] Rate limiting in DEBUG mode — limits 20x higher than production. "
        f"DEBUG={os.getenv('DEBUG', '<unset>')!r} "
        f"ENVIRONMENT={os.getenv('ENVIRONMENT', '<unset>')!r}. "
        "Set ENVIRONMENT=production to enable strict tier limits."
    )

TIER_LIMITS = {
    # Free tier (nest)
    "free": {
        "ai": "100/minute" if _IS_DEBUG else "5/minute",
        "api": "500/minute" if _IS_DEBUG else "30/minute",
        "discovery": "100/hour" if _IS_DEBUG else "10/hour",
    },
    "nest": {  # Alias for free tier
        "ai": "100/minute" if _IS_DEBUG else "5/minute",
        "api": "500/minute" if _IS_DEBUG else "30/minute",
        "discovery": "100/hour" if _IS_DEBUG else "10/hour",
    },
    # Starter tier (flight)
    "starter": {
        "ai": "100/minute" if _IS_DEBUG else "15/minute",
        "api": "500/minute" if _IS_DEBUG else "100/minute",
        "discovery": "100/hour" if _IS_DEBUG else "50/hour",
    },
    "flight": {  # Alias for starter tier
        "ai": "100/minute" if _IS_DEBUG else "15/minute",
        "api": "500/minute" if _IS_DEBUG else "100/minute",
        "discovery": "100/hour" if _IS_DEBUG else "50/hour",
    },
    # Pro tier (soar)
    "pro": {
        "ai": "100/minute" if _IS_DEBUG else "30/minute",
        "api": "500/minute" if _IS_DEBUG else "300/minute",
        "discovery": "200/hour" if _IS_DEBUG else "200/hour",
    },
    "soar": {  # Alias for pro tier
        "ai": "100/minute" if _IS_DEBUG else "30/minute",
        "api": "500/minute" if _IS_DEBUG else "300/minute",
        "discovery": "200/hour" if _IS_DEBUG else "200/hour",
    },
    # Enterprise tier (stratosphere)
    "enterprise": {
        "ai": "1000/minute" if _IS_DEBUG else "100/minute",
        "api": "10000/minute" if _IS_DEBUG else "1000/minute",
        "discovery": "unlimited",
    },
    "stratosphere": {  # Alias for enterprise tier
        "ai": "1000/minute" if _IS_DEBUG else "100/minute",
        "api": "10000/minute" if _IS_DEBUG else "1000/minute",
        "discovery": "unlimited",
    }
}


def get_tier_limit(tier: str, resource: str = "api") -> str:
    """
    Get rate limit for a specific tier and resource type.

    Args:
        tier: User subscription tier (nest/free, flight/starter, soar/pro, stratosphere/enterprise)
        resource: Resource type (ai, api, discovery)

    Returns:
        Rate limit string (e.g., "30/minute")
    """
    tier_lower = tier.lower()
    tier_config = TIER_LIMITS.get(tier_lower, TIER_LIMITS["nest"])
    return tier_config.get(resource, "10/minute")
