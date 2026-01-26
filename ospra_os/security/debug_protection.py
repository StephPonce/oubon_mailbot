"""
Debug Endpoint Protection for Ospra OS
======================================

Middleware and utilities to protect debug endpoints in production.

CRITICAL: Debug endpoints should NEVER be accessible in production.
This module provides:
1. Middleware to block /debug/* routes in production
2. Dependency injection for individual endpoint protection
3. Environment detection utilities

Author: OspraOS Security
"""

import os
import logging
from typing import Optional
from functools import wraps
from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Import consolidated is_production from env_validator
from ospra_os.core.env_validator import is_production

logger = logging.getLogger(__name__)


def debug_endpoints_enabled() -> bool:
    """
    Check if debug endpoints should be enabled.

    Debug endpoints are ONLY enabled when:
    1. Not in production AND
    2. ENABLE_DEBUG_ENDPOINTS is explicitly set to "true"

    This is a defense-in-depth approach.
    """
    if is_production():
        return False

    # Require explicit opt-in for debug endpoints
    return os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true"


class DebugEndpointProtectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to block debug endpoints in production.

    Blocks any request to paths containing:
    - /debug/
    - /api/debug/

    Returns 404 (not 403) to avoid revealing endpoint existence.

    Usage:
        app.add_middleware(DebugEndpointProtectionMiddleware)
    """

    DEBUG_PATH_PATTERNS = [
        "/debug/",
        "/api/debug/",
        "/_debug/",
    ]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.lower()

        # Check if this is a debug endpoint
        is_debug_path = any(pattern in path for pattern in self.DEBUG_PATH_PATTERNS)

        if is_debug_path and not debug_endpoints_enabled():
            # Log the attempt
            client_ip = request.client.host if request.client else "unknown"
            logger.warning(
                f"Blocked debug endpoint access: {request.method} {request.url.path} "
                f"from {client_ip}"
            )

            # Return 404 to not reveal endpoint exists
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"}
            )

        return await call_next(request)


async def require_debug_mode():
    """
    FastAPI dependency to require debug mode for an endpoint.

    Usage:
        @router.get("/debug/something")
        async def debug_something(_: None = Depends(require_debug_mode)):
            ...
    """
    if not debug_endpoints_enabled():
        raise HTTPException(
            status_code=404,
            detail="Not found"
        )


def debug_only(func):
    """
    Decorator to make a route debug-only.

    Usage:
        @app.get("/debug/routes")
        @debug_only
        async def debug_routes():
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not debug_endpoints_enabled():
            raise HTTPException(
                status_code=404,
                detail="Not found"
            )
        return await func(*args, **kwargs)
    return wrapper


def get_debug_status() -> dict:
    """Get current debug configuration status."""
    return {
        "is_production": is_production(),
        "debug_endpoints_enabled": debug_endpoints_enabled(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "enable_debug_endpoints_flag": os.getenv("ENABLE_DEBUG_ENDPOINTS", "false"),
        "cloud_detection": {
            "render": bool(os.getenv("RENDER")),
            "railway": bool(os.getenv("RAILWAY_ENVIRONMENT")),
            "vercel": bool(os.getenv("VERCEL")),
            "heroku": bool(os.getenv("HEROKU")),
            "aws_lambda": bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME")),
            "gcp": bool(os.getenv("GOOGLE_CLOUD_PROJECT")),
        }
    }
