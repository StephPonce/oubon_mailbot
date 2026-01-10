"""
Global Rate Limiting Middleware
================================
Automatically applies rate limits to all API routes based on user tier.

This middleware works with SlowAPI to enforce tier-based rate limiting without
requiring @limiter.limit() decorators on individual routes.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
import logging

logger = logging.getLogger(__name__)


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to apply rate limiting globally to all API endpoints.

    Works with SlowAPI limiter to enforce tier-based limits without decorators.
    """

    def __init__(self, app, limiter, get_tier_limit_func):
        """
        Initialize the global rate limiting middleware.

        Args:
            app: FastAPI application instance
            limiter: SlowAPI Limiter instance
            get_tier_limit_func: Function to get rate limit for a tier/resource
        """
        super().__init__(app)
        self.limiter = limiter
        self.get_tier_limit = get_tier_limit_func
        logger.info("[SECURITY] Global rate limiting middleware initialized")

    async def dispatch(self, request: Request, call_next):
        """
        Apply rate limiting before processing the request.

        Rate limits are applied based on:
        - User tier (from JWT token or header)
        - Resource type (api, ai, discovery based on endpoint)
        """
        # Skip rate limiting for health and auth endpoints
        if self._should_skip_rate_limit(request):
            return await call_next(request)

        # Determine tier and resource type
        tier = self._extract_tier(request)
        resource = self._determine_resource_type(request)

        # Get rate limit for this tier/resource combination
        limit = self.get_tier_limit(tier, resource)

        try:
            # Apply rate limit using SlowAPI
            await self.limiter.check_limits(
                request,
                limit,
                key_func=lambda r: self._get_client_identifier(r)
            )

            # Rate limit passed, continue to endpoint
            return await call_next(request)

        except RateLimitExceeded as exc:
            # Rate limit exceeded - log and return 429
            logger.warning(
                f"[RATE_LIMIT] {tier} tier exceeded {limit} limit "
                f"on {request.url.path} from {self._get_client_identifier(request)}"
            )

            # Security logging handled by rate_limit_exceeded_handler
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Please slow down and try again later.",
                    "limit": limit,
                    "tier": tier,
                    "retry_after": exc.detail if hasattr(exc, 'detail') else "60"
                },
                headers={"Retry-After": str(exc.detail) if hasattr(exc, 'detail') else "60"}
            )

    def _should_skip_rate_limit(self, request: Request) -> bool:
        """
        Determine if rate limiting should be skipped for this request.

        Skip for:
        - Health checks
        - Authentication endpoints
        - Static files
        """
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
        """
        Extract user tier from request.

        Checks (in order):
        1. JWT token (if authenticated)
        2. X-User-Tier header
        3. Defaults to 'free'
        """
        # Try to get tier from request state (set by auth middleware)
        if hasattr(request.state, "tier"):
            return request.state.tier.lower()

        # Try to get from header (for testing)
        tier_header = request.headers.get("X-User-Tier")
        if tier_header:
            return tier_header.lower()

        # Default to free tier
        return "free"

    def _determine_resource_type(self, request: Request) -> str:
        """
        Determine resource type based on endpoint path.

        Returns:
            'ai' for AI endpoints
            'discovery' for product discovery
            'api' for general API calls (default)
        """
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

    def _get_client_identifier(self, request: Request) -> str:
        """
        Get unique identifier for rate limiting.

        Uses (in priority order):
        1. User ID (if authenticated)
        2. IP address
        """
        # Try to get user ID from request state
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        return request.client.host if request.client else "unknown"
