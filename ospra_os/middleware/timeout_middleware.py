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
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request timeouts and prevent hanging requests.

    Supports a `path_overrides` mapping for routes that legitimately need
    longer budgets (cold-call winner-first discovery hits 8 Meta queries
    + N AE searches; 30s isn't enough for the cold path).
    """

    # Per-path timeout overrides. Each entry is a (prefix, seconds) tuple
    # and matches if the request path STARTS WITH the prefix. Order matters:
    # first match wins, so put more specific prefixes before general ones.
    DEFAULT_PATH_OVERRIDES: list[tuple[str, int]] = [
        # /products with sentiment ON does Amazon-reviews scraping +
        # AI grading per product. Empirically 30-60s.
        ("/api/discovery/products", 90),
        # /quick/{niche} is the active discovery endpoint used by
        # ProductDiscovery.jsx. With the winner-first restructure it
        # runs 9 parallel trend sources → per-winner AE+CJ sourcing →
        # sentiment enrichment. Cold path is 25-30s; warm path is
        # under 1s via the in-memory cache. 120s headroom covers Apify
        # cold-start outliers (Meta Ad Library has been seen at ~55s)
        # and any per-source timeouts firing back-to-back.
        # (Old /winners override was retired with the endpoint itself —
        # the winner-first logic now lives behind /quick.)
        ("/api/discovery/quick", 120),
    ]

    def __init__(
        self,
        app,
        timeout_seconds: int = 30,
        path_overrides: list[tuple[str, int]] | None = None,
    ):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
        self.path_overrides = path_overrides if path_overrides is not None else self.DEFAULT_PATH_OVERRIDES
        logger.info(
            f"[SECURITY] Request timeout middleware initialized: "
            f"{timeout_seconds}s default + {len(self.path_overrides)} per-path overrides"
        )

    def _timeout_for(self, path: str) -> int:
        """Return the appropriate timeout for `path` — first matching
        override prefix wins, else the global default."""
        for prefix, seconds in self.path_overrides:
            if path.startswith(prefix):
                return seconds
        return self.timeout_seconds

    async def dispatch(self, request: Request, call_next: Callable):
        """
        Wrap request processing with a timeout.

        If the request takes longer than the configured budget for this
        path, it will be cancelled and return a 504 Gateway Timeout error.
        """
        start_time = datetime.now(timezone.utc)
        effective_timeout = self._timeout_for(request.url.path)

        try:
            # Wrap the request processing with asyncio.wait_for timeout
            response = await asyncio.wait_for(
                call_next(request),
                timeout=effective_timeout
            )
            return response

        except asyncio.TimeoutError:
            # Log the timeout event (use the per-path budget, not the default)
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.warning(
                f"[TIMEOUT] Request timed out after {elapsed:.2f}s "
                f"(budget {effective_timeout}s): "
                f"{request.method} {request.url.path}"
            )

            # Return 504 Gateway Timeout
            return JSONResponse(
                status_code=504,
                content={
                    "error": "request_timeout",
                    "message": f"Request timed out after {effective_timeout} seconds. "
                               f"Please try again or contact support if this persists.",
                    "timeout_seconds": effective_timeout,
                    "path": str(request.url.path)
                }
            )

        except Exception as e:
            # Log unexpected errors
            logger.error(f"[TIMEOUT_MIDDLEWARE] Error processing request: {e}")
            raise
