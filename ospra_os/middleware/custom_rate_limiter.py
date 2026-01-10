"""
Custom Rate Limiting Middleware (PHASE 1 SECURITY)
===================================================
In-memory rate limiter with tier-based limits. Can be upgraded to Redis for production.

Features:
- Per-user and per-IP rate limiting
- Tier-based limits from TIER_LIMITS config
- Resource-type aware (api, ai, discovery)
- Sliding window algorithm
- Security event logging
"""

import time
import logging
from collections import defaultdict, deque
from typing import Dict, Deque, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.

    Rate limit format: "X/period" where period can be "minute", "hour", "day"
    Example: "30/minute" means 30 requests per minute
    """

    def __init__(self):
        # Store: {client_key: deque of timestamps}
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._cleanup_interval = 60  # Cleanup old entries every 60 seconds
        self._last_cleanup = time.time()

    def _parse_limit(self, limit_str: str) -> Tuple[int, int]:
        """
        Parse rate limit string into (count, window_seconds).

        Examples:
            "30/minute" -> (30, 60)
            "100/hour" -> (100, 3600)
            "1000/day" -> (1000, 86400)
        """
        count, period = limit_str.split("/")
        count = int(count)

        period_map = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400
        }

        window = period_map.get(period.lower(), 60)
        return count, window

    def is_allowed(self, client_key: str, limit_str: str) -> Tuple[bool, int]:
        """
        Check if request is allowed under rate limit.

        Args:
            client_key: Unique identifier for the client (user_id or IP)
            limit_str: Rate limit string (e.g., "30/minute")

        Returns:
            (is_allowed, remaining_requests)
        """
        max_requests, window_seconds = self._parse_limit(limit_str)
        current_time = time.time()

        # Get request timestamps for this client
        timestamps = self.requests[client_key]

        # Remove timestamps outside the current window (sliding window)
        cutoff_time = current_time - window_seconds
        while timestamps and timestamps[0] < cutoff_time:
            timestamps.popleft()

        # Check if under limit
        if len(timestamps) < max_requests:
            timestamps.append(current_time)
            remaining = max_requests - len(timestamps)
            return True, remaining
        else:
            # Rate limit exceeded
            remaining = 0
            return False, remaining

    def cleanup_old_entries(self):
        """Remove expired entries to prevent memory leaks."""
        current_time = time.time()

        # Only cleanup periodically
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = current_time

        # Remove clients with no recent requests (older than 1 hour)
        cutoff_time = current_time - 3600
        expired_clients = []

        for client_key, timestamps in self.requests.items():
            # Remove old timestamps
            while timestamps and timestamps[0] < cutoff_time:
                timestamps.popleft()

            # Mark for deletion if no recent requests
            if not timestamps:
                expired_clients.append(client_key)

        # Delete expired clients
        for client_key in expired_clients:
            del self.requests[client_key]

        if expired_clients:
            logger.debug(f"[RATE_LIMIT] Cleaned up {len(expired_clients)} expired client entries")


class CustomRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Custom rate limiting middleware with tier-based limits.

    This middleware applies rate limits automatically to all API requests
    based on user tier and resource type, without requiring decorators.
    """

    def __init__(self, app, get_tier_limit_func):
        super().__init__(app)
        self.limiter = InMemoryRateLimiter()
        self.get_tier_limit = get_tier_limit_func
        logger.info("[SECURITY] Custom rate limiting middleware initialized (in-memory)")

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting before processing the request."""

        # Skip rate limiting for specific paths
        if self._should_skip(request):
            return await call_next(request)

        # Determine tier and resource type
        tier = self._extract_tier(request)
        resource = self._determine_resource_type(request)

        # Get rate limit for this tier/resource combination
        limit_str = self.get_tier_limit(tier, resource)

        # Get unique client identifier
        client_key = self._get_client_key(request)

        # Check rate limit
        is_allowed, remaining = self.limiter.is_allowed(client_key, limit_str)

        if is_allowed:
            # Request allowed - add rate limit headers
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit_str)
            response.headers["X-RateLimit-Remaining"] = str(remaining)

            # Periodic cleanup
            self.limiter.cleanup_old_entries()

            return response
        else:
            # Rate limit exceeded - log and return 429
            logger.warning(
                f"[RATE_LIMIT] {tier} tier exceeded {limit_str} limit "
                f"on {request.url.path} from {client_key}"
            )

            # Log security event
            try:
                from ospra_os.security.auth_logger import log_rate_limit_exceeded
                user_id = getattr(request.state, "user_id", None)
                log_rate_limit_exceeded(
                    ip_address=self._get_ip(request),
                    endpoint=request.url.path,
                    user_id=user_id
                )
            except Exception as e:
                logger.error(f"Failed to log rate limit event: {e}")

            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Rate limit: {limit_str}. Please slow down.",
                    "limit": limit_str,
                    "tier": tier,
                    "retry_after": "60"  # Suggest retry after 60 seconds
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(limit_str),
                    "X-RateLimit-Remaining": "0"
                }
            )

    def _should_skip(self, request: Request) -> bool:
        """Determine if rate limiting should be skipped."""
        path = request.url.path

        skip_patterns = [
            "/health",
            "/docs",
            "/openapi.json",
            "/api/auth/",  # Auth endpoints
            "/static/",
        ]

        return any(path.startswith(pattern) for pattern in skip_patterns)

    def _extract_tier(self, request: Request) -> str:
        """Extract user tier from request state or headers."""
        # Try request state (set by auth middleware)
        if hasattr(request.state, "tier"):
            return request.state.tier.lower()

        # Try header (for testing)
        tier_header = request.headers.get("X-User-Tier")
        if tier_header:
            return tier_header.lower()

        # Default to free tier
        return "nest"

    def _determine_resource_type(self, request: Request) -> str:
        """Determine resource type based on endpoint path."""
        path = request.url.path

        # AI resource endpoints
        ai_patterns = [
            "/api/ai/",
            "/api/claude/",
            "/api/intelligence/",
            "/api/ml/",
        ]
        if any(path.startswith(pattern) for pattern in ai_patterns):
            return "ai"

        # Discovery resource endpoints
        discovery_patterns = [
            "/api/discovery/",
            "/api/intelligence/discover",
        ]
        if any(path.startswith(pattern) for pattern in discovery_patterns):
            return "discovery"

        # Default to general API
        return "api"

    def _get_client_key(self, request: Request) -> str:
        """Get unique identifier for rate limiting (user ID or IP)."""
        # Prefer user ID if authenticated
        if hasattr(request.state, "user_id") and request.state.user_id:
            return f"user:{request.state.user_id}"

        # Fall back to IP address
        return f"ip:{self._get_ip(request)}"

    def _get_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check X-Forwarded-For header (for proxies/load balancers)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"
