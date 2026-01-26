"""
Analytics Routes for Ospra OS
=============================

Analytics and reporting endpoints.

SECURITY: All endpoints require JWT authentication.
User ID is extracted from verified JWT tokens, not query parameters.

Endpoints:
- GET /analytics/daily - Daily analytics
- GET /analytics/weekly - Weekly analytics
- GET /analytics/costs - Cost tracking
- GET /analytics/labels - Label distribution

Author: OspraOS
"""

import logging
from fastapi import APIRouter, Depends

from ospra_os.routers import RouterRegistry
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/daily")
async def daily_analytics(current_user: User = Depends(get_current_user)):
    """
    Get daily analytics summary.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Daily analytics endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.get("/weekly")
async def weekly_analytics(current_user: User = Depends(get_current_user)):
    """
    Get weekly analytics summary.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Weekly analytics endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.get("/costs")
async def cost_analytics(current_user: User = Depends(get_current_user)):
    """
    Get cost tracking data.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Cost analytics endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.get("/labels")
async def label_analytics(current_user: User = Depends(get_current_user)):
    """
    Get label distribution analytics.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Label analytics endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.get("/cache-stats")
async def cache_stats(current_user: User = Depends(get_current_user)):
    """
    Get cache statistics.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Cache stats endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


# Register router
RouterRegistry.register(router, prefix="", tags=["Analytics"])

logger.info("[SUCCESS] Analytics router loaded")
