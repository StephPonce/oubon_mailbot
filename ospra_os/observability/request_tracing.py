"""
Request Tracing Middleware for Ospra OS
=======================================

Provides request tracing with unique request IDs for debugging and monitoring.

Features:
- Unique request ID generation
- Request/response logging
- Timing metrics
- Correlation ID propagation
- Error tracking

Usage:
    from ospra_os.observability.request_tracing import RequestTracingMiddleware

    app.add_middleware(RequestTracingMiddleware)

Author: OspraOS
"""

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


# =============================================================================
# CONTEXT VARIABLES
# =============================================================================

# Context variable to store current request ID (accessible anywhere in the request)
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_request_context: ContextVar[Dict[str, Any]] = ContextVar("request_context", default={})


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return _request_id.get()


def get_request_context() -> Dict[str, Any]:
    """Get the current request context from context."""
    return _request_context.get()


def set_request_context(key: str, value: Any):
    """Set a value in the current request context."""
    ctx = _request_context.get()
    ctx[key] = value
    _request_context.set(ctx)


# =============================================================================
# REQUEST TRACING MIDDLEWARE
# =============================================================================

class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds request tracing capabilities.

    For each request:
    1. Generates or extracts a unique request ID
    2. Logs request start with method, path, and client info
    3. Times the request duration
    4. Logs request completion with status code and timing
    5. Adds X-Request-ID header to response
    """

    # Headers to look for incoming trace/request IDs
    REQUEST_ID_HEADERS = [
        "X-Request-ID",
        "X-Correlation-ID",
        "X-Trace-ID",
    ]

    # Paths to skip detailed logging (health checks, etc.)
    SKIP_LOGGING_PATHS = {
        "/health",
        "/health/celery",
        "/favicon.ico",
        "/robots.txt",
    }

    async def dispatch(self, request: Request, call_next):
        # Generate or extract request ID
        request_id = self._get_or_generate_request_id(request)

        # Set in context
        _request_id.set(request_id)
        _request_context.set({
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "start_time": time.time(),
        })

        # Get client info
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")[:100]

        # Log request start (skip for health checks)
        should_log = request.url.path not in self.SKIP_LOGGING_PATHS

        if should_log:
            logger.info(
                f"[{request_id}] → {request.method} {request.url.path} "
                f"| client={client_ip}"
            )

        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log completion
            if should_log:
                log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
                logger.log(
                    log_level,
                    f"[{request_id}] ← {response.status_code} "
                    f"| {duration_ms:.0f}ms | {request.method} {request.url.path}"
                )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Add timing header
            response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"

            return response

        except Exception as e:
            # Calculate duration even on error
            duration_ms = (time.time() - start_time) * 1000

            logger.error(
                f"[{request_id}] ✗ ERROR | {duration_ms:.0f}ms | "
                f"{request.method} {request.url.path} | {type(e).__name__}: {str(e)[:200]}"
            )

            # Re-raise to let error handlers deal with it
            raise

        finally:
            # Clear context
            _request_id.set(None)
            _request_context.set({})

    def _get_or_generate_request_id(self, request: Request) -> str:
        """Get request ID from headers or generate a new one."""
        # Check incoming headers
        for header in self.REQUEST_ID_HEADERS:
            request_id = request.headers.get(header)
            if request_id:
                return request_id

        # Generate new request ID (short UUID for readability)
        return str(uuid.uuid4())[:8]

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, handling proxies."""
        # Check common proxy headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Check other proxy headers
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return "unknown"


# =============================================================================
# TRACING HELPERS
# =============================================================================

class TracingLogger:
    """
    Logger that automatically includes request ID in messages.

    Usage:
        trace_logger = TracingLogger(__name__)
        trace_logger.info("Processing order")  # Automatically includes request ID
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _format_message(self, message: str) -> str:
        """Add request ID prefix to message."""
        request_id = get_request_id()
        if request_id:
            return f"[{request_id}] {message}"
        return message

    def debug(self, message: str, *args, **kwargs):
        self._logger.debug(self._format_message(message), *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self._logger.info(self._format_message(message), *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._logger.warning(self._format_message(message), *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._logger.error(self._format_message(message), *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self._logger.critical(self._format_message(message), *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        self._logger.exception(self._format_message(message), *args, **kwargs)


def trace_function(func):
    """
    Decorator to trace function execution with timing.

    Usage:
        @trace_function
        async def my_function():
            ...
    """
    import functools
    import asyncio

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        request_id = get_request_id() or "no-request"
        func_name = func.__name__
        start = time.time()

        logger.debug(f"[{request_id}] Entering {func_name}")

        try:
            result = await func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            logger.debug(f"[{request_id}] Exiting {func_name} ({duration:.0f}ms)")
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"[{request_id}] {func_name} failed ({duration:.0f}ms): {e}")
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        request_id = get_request_id() or "no-request"
        func_name = func.__name__
        start = time.time()

        logger.debug(f"[{request_id}] Entering {func_name}")

        try:
            result = func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            logger.debug(f"[{request_id}] Exiting {func_name} ({duration:.0f}ms)")
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"[{request_id}] {func_name} failed ({duration:.0f}ms): {e}")
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


logger.info("[SUCCESS] Request tracing module loaded")
