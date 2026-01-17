"""
DEPRECATED - Image Comparison Routes
====================================
This module has been replaced by the cleaner image enhancement approach.

All comparison modes (text_only, vision_enhanced, img2img, hybrid) have been
removed in favor of a single, reliable background replacement method.

Use /api/images/enhance instead.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/images/comparison", tags=["DEPRECATED - Image Comparison"])


@router.get("/status")
async def deprecated_status():
    """
    DEPRECATED: Use /api/images/status instead.
    """
    return {
        "deprecated": True,
        "message": "Image comparison has been replaced with image enhancement.",
        "use_instead": "/api/images/status",
        "new_endpoint": "/api/images/enhance"
    }


@router.post("/compare")
async def deprecated_compare():
    """
    DEPRECATED: Use /api/images/enhance instead.
    """
    return {
        "deprecated": True,
        "message": "Comparison modes removed. Use /api/images/enhance for background replacement.",
        "use_instead": "/api/images/enhance",
        "reason": "Background replacement is the only reliable method for e-commerce product images."
    }
