"""
DEPRECATED - Image Processing Routes (Old)
==========================================
This module has been replaced by the cleaner image_generation_routes.py

The new approach uses:
- Stability AI background removal (reliable)
- Custom background compositing (Oubon Shop aesthetic)
- Simpler API: /api/images/enhance

This file kept for backwards compatibility but routes are disabled.
"""

from fastapi import APIRouter

# This router intentionally has no routes to avoid conflicts
# Use /api/images/enhance from image_generation_routes.py instead
router = APIRouter(
    prefix="/api/images-old",  # Changed prefix to avoid conflicts
    tags=["DEPRECATED - Old Image Processing"]
)


@router.get("/deprecated")
async def deprecated_notice():
    """
    This image processing API has been deprecated.
    """
    return {
        "deprecated": True,
        "message": "Use /api/images/enhance for image enhancement",
        "new_endpoints": {
            "enhance": "/api/images/enhance",
            "batch": "/api/images/enhance/batch",
            "status": "/api/images/status",
            "backgrounds": "/api/images/backgrounds"
        }
    }
