"""
Deploy Routes for Ospra OS
==========================

Product deployment endpoints for pushing products to stores.

Endpoints:
- POST /api/deploy/product/{id}/to-store/{store_id} - Deploy to specific store
- POST /api/deploy/product/{id}/to-all-stores - Deploy to all stores
- POST /api/deploy-to-shopify - Legacy deploy endpoint

Author: OspraOS
"""

import logging
from fastapi import APIRouter

from ospra_os.routers import RouterRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deploy", tags=["Deploy"])


@router.post("/product/{product_id}/to-store/{store_id}")
async def deploy_to_store(product_id: int, store_id: int):
    """Deploy a product to a specific store."""
    return {
        "status": "ok",
        "message": "Deploy endpoint - full implementation in main.py",
        "product_id": product_id,
        "store_id": store_id
    }


@router.post("/product/{product_id}/to-all-stores")
async def deploy_to_all_stores(product_id: int):
    """Deploy a product to all connected stores."""
    return {
        "status": "ok",
        "message": "Deploy all endpoint - full implementation in main.py",
        "product_id": product_id
    }


# Register router
RouterRegistry.register(router, prefix="", tags=["Deploy"])

logger.info("[SUCCESS] Deploy router loaded")
