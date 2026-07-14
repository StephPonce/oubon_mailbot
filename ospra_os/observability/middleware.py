"""
FastAPI Middleware for Request Logging and Tracing
Provides automatic request/response logging and context propagation.
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .logger import get_logger, LogContext
from .error_tracking import add_breadcrumb

logger = get_logger(__name__)

# T11: only these request headers are safe to attach to Sentry breadcrumbs.
# Anything carrying credentials (Authorization, Cookie, *-Token, *-Api-Key,
# *-Secret, X-Signature/Hmac) is redacted so it never reaches a third party.
_SAFE_HEADER_ALLOWLIST = frozenset({
    "host", "user-agent", "accept", "accept-encoding", "accept-language",
    "content-type", "content-length", "referer", "origin", "connection",
    "x-request-id", "x-forwarded-for", "x-forwarded-proto", "x-real-ip",
})


def _safe_headers(headers) -> dict:
    """Return only allowlisted headers; everything else is [REDACTED]."""
    safe = {}
    for name, value in headers.items():
        safe[name] = value if name.lower() in _SAFE_HEADER_ALLOWLIST else "[REDACTED]"
    return safe


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all HTTP requests and responses.

    Features:
    - Automatic request/response logging
    - Request ID generation and tracking
    - Duration measurement
    - Context propagation (user_id, store_id, etc.)
    - Breadcrumb trails for error tracking
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Extract user context from JWT token (if available)
        user_id = None
        store_id = None

        # Try to extract user_id from request state (set by auth middleware)
        if hasattr(request.state, "user_id"):
            user_id = request.state.user_id
        if hasattr(request.state, "store_id"):
            store_id = request.state.store_id

        # Start timing
        start_time = time.time()

        # Create log context for this request
        context = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        }

        if user_id:
            context["user_id"] = user_id
        if store_id:
            context["store_id"] = store_id

        # Add request breadcrumb for error tracking.
        # T11: dict(request.headers) shipped Authorization/Cookie/token headers
        # to Sentry (a third party) on EVERY exception. Redact to an allowlist
        # of safe, non-sensitive headers.
        add_breadcrumb(
            message=f"{request.method} {request.url.path}",
            category="http.request",
            level="info",
            data={
                "method": request.method,
                "url": str(request.url),
                "headers": _safe_headers(request.headers),
            }
        )

        # Log request with context
        with LogContext(**context):
            logger.info(
                f"Request started: {request.method} {request.url.path}",
                extra={"query_params": dict(request.query_params)}
            )

            try:
                # Process request
                response = await call_next(request)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Add response breadcrumb
                add_breadcrumb(
                    message=f"Response {response.status_code}",
                    category="http.response",
                    level="info",
                    data={
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    }
                )

                # Log response
                logger.info(
                    f"Request completed: {request.method} {request.url.path}",
                    extra={
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    }
                )

                # Add custom headers
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

                return response

            except Exception as e:
                # Calculate duration even on error
                duration_ms = (time.time() - start_time) * 1000

                # Log error
                logger.error(
                    f"Request failed: {request.method} {request.url.path}",
                    extra={
                        "error": str(e),
                        "duration_ms": round(duration_ms, 2),
                    },
                    exc_info=True
                )

                # Re-raise to be handled by exception handlers
                raise
