"""
Security Headers Middleware
===========================

Adds essential security headers to all HTTP responses to protect against
common web vulnerabilities.

Headers added:
- X-Content-Type-Options: Prevents MIME type sniffing
- X-Frame-Options: Prevents clickjacking attacks
- X-XSS-Protection: Enables browser XSS filtering
- Strict-Transport-Security: Enforces HTTPS
- Content-Security-Policy: Controls resource loading
- Referrer-Policy: Controls referrer information
- Permissions-Policy: Controls browser features

Author: Ospra OS Security
"""

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    These headers protect against:
    - Clickjacking (X-Frame-Options)
    - MIME type confusion (X-Content-Type-Options)
    - XSS attacks (X-XSS-Protection, CSP)
    - Protocol downgrade (HSTS)
    - Information leakage (Referrer-Policy)
    """

    def __init__(self, app, enable_hsts: bool = True):
        """
        Initialize security headers middleware.

        Args:
            app: FastAPI/Starlette application
            enable_hsts: Enable HSTS header (disable for local development)
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts

        # Check if we're in production
        self.is_production = (
            os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") or
            os.getenv("RENDER", "") == "true" or
            os.getenv("RAILWAY_ENVIRONMENT", "") != "" or
            os.getenv("VERCEL", "") == "1"
        )

        logger.info(f"[SECURITY] Security headers middleware initialized (HSTS={'enabled' if enable_hsts else 'disabled'})")

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking - deny all framing
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS filter in browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=(), "
            "payment=()"
        )

        # HSTS - only in production or if explicitly enabled
        if self.enable_hsts and self.is_production:
            # 1 year max-age, include subdomains
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content Security Policy
        # Restrictive but allows API usage and inline styles for some frameworks
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",  # Allow inline for React
            "style-src 'self' 'unsafe-inline'",   # Allow inline styles
            "img-src 'self' data: https:",        # Allow images from HTTPS
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self' https://api.openai.com https://api.anthropic.com https://api.stripe.com",
            "frame-ancestors 'none'",             # Prevent framing (same as X-Frame-Options)
            "form-action 'self'",                 # Restrict form submissions
            "base-uri 'self'",                    # Restrict base tag
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        return response
