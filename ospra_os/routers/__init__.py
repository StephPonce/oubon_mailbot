"""
Ospra OS Routers Package
========================

Centralized router management for the Ospra OS FastAPI application.
This package provides a clean way to organize and register API routes.

Pattern:
1. Each feature area has its own router file (e.g., dashboard.py, ai.py)
2. Routers are registered through the RouterRegistry
3. Main app includes all routers at startup

Usage in main.py:
    from ospra_os.routers import register_all_routers

    app = FastAPI()
    register_all_routers(app)

Author: OspraOS
"""

import logging
from typing import List, Optional
from fastapi import FastAPI, APIRouter

logger = logging.getLogger(__name__)


class RouterRegistry:
    """
    Centralized registry for all API routers.

    Manages router registration and provides a single point
    for including all routes in the FastAPI application.
    """

    _routers: List[tuple] = []  # (router, prefix, tags)

    @classmethod
    def register(
        cls,
        router: APIRouter,
        prefix: str = "",
        tags: Optional[List[str]] = None
    ):
        """
        Register a router for later inclusion in the app.

        Args:
            router: FastAPI APIRouter instance
            prefix: URL prefix for all routes in this router
            tags: OpenAPI tags for documentation grouping
        """
        cls._routers.append((router, prefix, tags or []))
        logger.debug(f"Registered router: {prefix} with {len(router.routes)} routes")

    @classmethod
    def include_all(cls, app: FastAPI):
        """
        Include all registered routers in the FastAPI application.

        Args:
            app: FastAPI application instance
        """
        for router, prefix, tags in cls._routers:
            app.include_router(router, prefix=prefix, tags=tags)
            logger.info(f"Included router: {prefix or '/'} ({len(router.routes)} routes)")

        logger.info(f"[SUCCESS] {len(cls._routers)} routers registered")

    @classmethod
    def get_route_count(cls) -> int:
        """Get total number of routes across all routers."""
        return sum(len(r[0].routes) for r in cls._routers)

    @classmethod
    def clear(cls):
        """Clear all registered routers (for testing)."""
        cls._routers = []


# Import and register routers
def register_all_routers(app: FastAPI):
    """
    Import all routers and register them with the app.

    This function is called from main.py during app initialization.
    """
    # Import routers here to register them
    from ospra_os.routers import (
        health,
        dashboard,
        ai_providers,
        learning,
        deploy,
        analytics,
        discovery,
        intelligence,
        velocity,
    )

    # Include all registered routers
    RouterRegistry.include_all(app)

    return RouterRegistry.get_route_count()


# Export the registry for direct access
__all__ = [
    "RouterRegistry",
    "register_all_routers",
]
