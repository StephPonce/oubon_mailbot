"""
Discovery Routes for Ospra OS
=============================

Product discovery and research endpoints.

SECURITY: All endpoints require JWT authentication.
User ID is extracted from verified JWT tokens, not query parameters.

Endpoints:
- POST /api/discover - Discover products
- POST /api/discover-multi - Multi-source discovery
- POST /api/validate-product - Validate a product opportunity

Author: OspraOS
"""

import logging
from fastapi import APIRouter, Depends

from ospra_os.routers import RouterRegistry
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Discovery"])


@router.post("/discover")
async def discover_products(current_user: User = Depends(get_current_user)):
    """
    Discover new product opportunities.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Discovery endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.post("/discover-multi")
async def discover_multi_source(current_user: User = Depends(get_current_user)):
    """
    Multi-source product discovery.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Multi-source discovery endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.post("/validate-product")
async def validate_product(current_user: User = Depends(get_current_user)):
    """
    Validate a product opportunity.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Validate product endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


# Register router
RouterRegistry.register(router, prefix="", tags=["Discovery"])

logger.info("[SUCCESS] Discovery router loaded")
