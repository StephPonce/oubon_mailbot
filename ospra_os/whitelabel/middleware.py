"""
White-Label Middleware - GROK RECOMMENDATION #19

Automatically resolves white-label branding for each request.
Attaches branding info to request.state for use in templates and responses.
"""

import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.orm import Session

from ospra_os.whitelabel.service import WhiteLabelService
from ospra_os.database.db import get_db

logger = logging.getLogger(__name__)


class WhiteLabelMiddleware(BaseHTTPMiddleware):
    """
    Middleware that resolves white-label branding for each request.

    Attaches `request.state.whitelabel` with branding configuration.
    Priority: custom domain > user's partner > slug parameter > default
    """

    # Paths to skip (static files, webhooks, health checks)
    SKIP_PATHS = [
        "/static/",
        "/favicon.ico",
        "/robots.txt",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/webhooks/"
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and resolve white-label branding"""

        # Skip middleware for certain paths
        if any(request.url.path.startswith(path) for path in self.SKIP_PATHS):
            request.state.whitelabel = None
            return await call_next(request)

        # Initialize whitelabel state
        request.state.whitelabel = None

        try:
            # Get database session
            db = next(get_db())
            service = WhiteLabelService(db)

            # Extract resolution parameters from request
            domain = self._extract_domain(request)
            slug = self._extract_slug(request)
            user_id = self._extract_user_id(request)

            # Resolve branding
            branding = service.resolve_branding_for_request(
                domain=domain,
                slug=slug,
                user_id=user_id
            )

            if branding:
                request.state.whitelabel = branding
                logger.debug(
                    f"Resolved white-label branding for {request.url.path}: "
                    f"{branding.get('brand_name')} (partner: {branding.get('partner_slug')})"
                )

        except Exception as e:
            # Log error but don't break the request
            logger.error(f"White-label middleware error: {e}", exc_info=True)
            request.state.whitelabel = None

        # Continue with request
        response = await call_next(request)

        # Add white-label header (for debugging)
        if request.state.whitelabel:
            response.headers["X-WhiteLabel-Partner"] = request.state.whitelabel.get("partner_slug", "")

        return response

    def _extract_domain(self, request: Request) -> str:
        """Extract domain from request"""
        # Use Host header
        host = request.headers.get("host", "")

        # Remove port if present
        if ":" in host:
            host = host.split(":")[0]

        return host

    def _extract_slug(self, request: Request) -> str:
        """Extract white-label slug from query parameter or header"""
        # Try query parameter first
        slug = request.query_params.get("wl")
        if slug:
            return slug

        # Try custom header
        slug = request.headers.get("x-whitelabel-slug")
        if slug:
            return slug

        return None

    def _extract_user_id(self, request: Request) -> int:
        """Extract user ID from request state (set by auth middleware)"""
        # This assumes JWT auth middleware runs before this middleware
        # and sets request.state.user_id
        if hasattr(request.state, "user_id"):
            return request.state.user_id

        # Alternative: try to get from user object
        if hasattr(request.state, "user"):
            user = request.state.user
            if hasattr(user, "id"):
                return user.id

        return None


def get_whitelabel_branding(request: Request) -> dict:
    """
    Helper function to get white-label branding from request.
    Returns None if no white-label branding is active.

    Usage in route handlers:
        branding = get_whitelabel_branding(request)
        if branding:
            brand_name = branding["brand_name"]
    """
    if hasattr(request.state, "whitelabel"):
        return request.state.whitelabel
    return None


def is_whitelabel_request(request: Request) -> bool:
    """
    Check if request is from a white-label partner.

    Usage in route handlers:
        if is_whitelabel_request(request):
            # Custom logic for white-label requests
    """
    branding = get_whitelabel_branding(request)
    return branding is not None
