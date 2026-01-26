"""
Intelligence Routes for Ospra OS
================================

AI-powered intelligence and analysis endpoints.

SECURITY: All endpoints require JWT authentication.
User ID is extracted from verified JWT tokens, not query parameters.

Endpoints:
- POST /api/intelligence/saturation - Analyze market saturation
- POST /api/intelligence/discover - AI-powered discovery
- POST /api/intelligence/discover-enriched - Enriched discovery
- GET /api/intelligence/stats - Intelligence statistics

Author: OspraOS
"""

import logging
from fastapi import APIRouter, Depends

from ospra_os.routers import RouterRegistry
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intelligence", tags=["Intelligence"])


@router.post("/saturation")
async def analyze_saturation(current_user: User = Depends(get_current_user)):
    """
    Analyze market saturation for a product.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Saturation analysis endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.post("/discover")
async def intelligence_discover(current_user: User = Depends(get_current_user)):
    """
    AI-powered product discovery.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Intelligence discovery endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.post("/discover-enriched")
async def discover_enriched(current_user: User = Depends(get_current_user)):
    """
    Enriched AI-powered discovery with additional data.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Enriched discovery endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.get("/stats")
async def intelligence_stats(current_user: User = Depends(get_current_user)):
    """
    Get intelligence engine statistics.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Intelligence stats endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


# Register router
RouterRegistry.register(router, prefix="", tags=["Intelligence"])

logger.info("[SUCCESS] Intelligence router loaded")
