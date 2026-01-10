"""
Rate Limiting Configuration for OspraOS
========================================
Prevents API abuse and protects AI quota from being burned through.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


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


# Rate limit configurations by tier
TIER_LIMITS = {
    "free": {
        "ai": "5/minute",          # 5 AI requests per minute
        "api": "30/minute",        # 30 API requests per minute
        "discovery": "10/hour",    # 10 product discoveries per hour
    },
    "starter": {
        "ai": "15/minute",
        "api": "100/minute",
        "discovery": "50/hour",
    },
    "pro": {
        "ai": "30/minute",
        "api": "300/minute",
        "discovery": "200/hour",
    },
    "enterprise": {
        "ai": "100/minute",
        "api": "1000/minute",
        "discovery": "unlimited",
    }
}


def get_tier_limit(tier: str, resource: str = "api") -> str:
    """
    Get rate limit for a specific tier and resource type.

    Args:
        tier: User subscription tier (free, starter, pro, enterprise)
        resource: Resource type (ai, api, discovery)

    Returns:
        Rate limit string (e.g., "30/minute")
    """
    tier_config = TIER_LIMITS.get(tier.lower(), TIER_LIMITS["free"])
    return tier_config.get(resource, "10/minute")
