"""
Velocity Routes for Ospra OS
============================

Product velocity tracking and performance monitoring.

SECURITY: All endpoints require JWT authentication.
User ID is extracted from verified JWT tokens, not query parameters.

Endpoints:
- GET /api/velocity/stats - Get velocity statistics
- GET /api/velocity/tier-products - Get products by tier
- GET /api/velocity/phase/{phase} - Get products by lifecycle phase

Author: OspraOS
"""

import logging
from fastapi import APIRouter, Depends

from ospra_os.routers import RouterRegistry
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/velocity", tags=["Velocity"])


@router.get("/stats")
async def velocity_stats(current_user: User = Depends(get_current_user)):
    """
    Get velocity statistics.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Velocity stats endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.get("/tier-products")
async def tier_products(current_user: User = Depends(get_current_user)):
    """
    Get products organized by tier.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Tier products endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.get("/phase/{phase}")
async def products_by_phase(
    phase: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get products by lifecycle phase.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Products by phase endpoint - full implementation in main.py",
        "phase": phase,
        "user_id": current_user.id
    }


# Register router
RouterRegistry.register(router, prefix="", tags=["Velocity"])

logger.info("[SUCCESS] Velocity router loaded")
