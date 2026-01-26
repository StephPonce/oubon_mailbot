"""
Deploy Routes for Ospra OS
==========================

Product deployment endpoints for pushing products to stores.

SECURITY: All endpoints require JWT authentication.
User ID is extracted from verified JWT tokens, not query parameters.

Endpoints:
- POST /api/deploy/product/{id}/to-store/{store_id} - Deploy to specific store
- POST /api/deploy/product/{id}/to-all-stores - Deploy to all stores
- POST /api/deploy-to-shopify - Legacy deploy endpoint

Author: OspraOS
"""

import logging
from fastapi import APIRouter, Depends

from ospra_os.routers import RouterRegistry
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deploy", tags=["Deploy"])


@router.post("/product/{product_id}/to-store/{store_id}")
async def deploy_to_store(
    product_id: int,
    store_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Deploy a product to a specific store.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Deploy endpoint - full implementation in main.py",
        "product_id": product_id,
        "store_id": store_id,
        "user_id": current_user.id
    }


@router.post("/product/{product_id}/to-all-stores")
async def deploy_to_all_stores(
    product_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Deploy a product to all connected stores.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Deploy all endpoint - full implementation in main.py",
        "product_id": product_id,
        "user_id": current_user.id
    }


# Register router
RouterRegistry.register(router, prefix="", tags=["Deploy"])

logger.info("[SUCCESS] Deploy router loaded")
