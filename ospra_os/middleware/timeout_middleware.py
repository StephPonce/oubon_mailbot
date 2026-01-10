"""
Request Timeout Middleware
=========================
Prevents requests from hanging indefinitely by enforcing timeouts.

This middleware wraps all requests with a timeout to protect against:
- Long-running AI operations
- Slow database queries
- Hanging external API calls
- Deadlocks or infinite loops

Configuration:
- Default timeout: 30 seconds
- Returns 504 Gateway Timeout on timeout
- Logs timeout events for monitoring
"""

import asyncio
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from datetime import datetime

logger = logging.getLogger(__name__)

class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request timeouts and prevent hanging requests.
    """

    def __init__(self, app, timeout_seconds: int = 30):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
        logger.info(f"[SECURITY] Request timeout middleware initialized: {timeout_seconds}s")

    async def dispatch(self, request: Request, call_next: Callable):
        """
        Wrap request processing with a timeout.

        If the request takes longer than timeout_seconds, it will be cancelled
        and return a 504 Gateway Timeout error.
        """
        start_time = datetime.utcnow()

        try:
            # Wrap the request processing with asyncio.wait_for timeout
            response = await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds
            )
            return response

        except asyncio.TimeoutError:
            # Log the timeout event
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.warning(
                f"[TIMEOUT] Request timed out after {elapsed:.2f}s: "
                f"{request.method} {request.url.path}"
            )

            # Return 504 Gateway Timeout
            return JSONResponse(
                status_code=504,
                content={
                    "error": "request_timeout",
                    "message": f"Request timed out after {self.timeout_seconds} seconds. "
                               f"Please try again or contact support if this persists.",
                    "timeout_seconds": self.timeout_seconds,
                    "path": str(request.url.path)
                }
            )

        except Exception as e:
            # Log unexpected errors
            logger.error(f"[TIMEOUT_MIDDLEWARE] Error processing request: {e}")
            raise
