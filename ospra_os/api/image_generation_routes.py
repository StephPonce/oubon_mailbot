"""
Image Enhancement Routes - CLEAN VERSION
=========================================
Single purpose: Enhance product images for Oubon Shop.

Endpoints:
- GET  /api/images/status - Check if enhancement is available
- POST /api/images/enhance - Enhance a single image
- POST /api/images/enhance/batch - Enhance multiple images
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import logging

from ospra_os.integrations.ai_image_generator import (
    get_image_enhancer,
    enhance_product_image,
    enhance_product_batch,
    BACKGROUND_STYLES,
    NICHE_BACKGROUNDS
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["Image Enhancement"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class EnhanceRequest(BaseModel):
    """Request to enhance a single product image"""
    image_url: str = Field(..., description="URL of the product image to enhance")
    niche: str = Field(default="smart_home", description="Product category for styling")
    background_style: Optional[str] = Field(default=None, description="Override background style")
    add_shadow: bool = Field(default=True, description="Add subtle shadow under product")


class BatchEnhanceRequest(BaseModel):
    """Request to enhance multiple product images"""
    images: List[Dict] = Field(..., description="List of images with 'url', optional 'id' and 'title'")
    niche: str = Field(default="smart_home", description="Default niche for all images")
    max_concurrent: int = Field(default=3, ge=1, le=5, description="Max parallel requests")


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/status")
async def get_status():
    """
    Check if image enhancement is available and properly configured.
    """
    enhancer = get_image_enhancer()
    status = await enhancer.check_status()
    
    return {
        **status,
        "endpoints": {
            "enhance": "POST /api/images/enhance",
            "batch": "POST /api/images/enhance/batch",
            "status": "GET /api/images/status"
        },
        "message": "Image enhancement ready" if status["available"] else "Stability API key not configured"
    }


@router.post("/enhance")
async def enhance_image(request: EnhanceRequest):
    """
    Enhance a single product image.
    
    Removes the ugly supplier background and adds a clean,
    professional background matching Oubon Shop aesthetic.
    
    **How it works:**
    1. Downloads the original image
    2. Removes background using Stability AI
    3. Composites product onto clean background
    4. Returns enhanced image as base64
    
    **Cost:** ~$0.06 per image (6 Stability credits)
    **Time:** ~3-5 seconds
    """
    logger.info(f"[ENHANCE] Request for: {request.image_url[:50]}...")
    
    result = await enhance_product_image(
        image_url=request.image_url,
        niche=request.niche,
        background_style=request.background_style
    )
    
    if not result["success"]:
        logger.error(f"[ENHANCE] Failed: {result.get('error')}")
        # Return result anyway (includes error details)
    
    return result


@router.post("/enhance/batch")
async def enhance_batch(request: BatchEnhanceRequest):
    """
    Enhance multiple product images in parallel.
    
    **Input format:**
    ```json
    {
        "images": [
            {"url": "https://...", "id": "prod1", "title": "Widget"},
            {"url": "https://...", "id": "prod2", "title": "Gadget"}
        ],
        "niche": "smart_home",
        "max_concurrent": 3
    }
    ```
    
    **Cost:** ~$0.06 per image
    **Recommendation:** Keep batch size under 10 for reasonable response times
    """
    if not request.images:
        raise HTTPException(status_code=400, detail="No images provided")
    
    if len(request.images) > 20:
        raise HTTPException(
            status_code=400, 
            detail="Batch size limited to 20 images. Split into multiple requests."
        )
    
    logger.info(f"[BATCH] Enhancing {len(request.images)} images...")
    
    results = await enhance_product_batch(
        images=request.images,
        niche=request.niche
    )
    
    # Summary stats
    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful
    
    return {
        "total": len(results),
        "successful": successful,
        "failed": failed,
        "estimated_cost": f"${successful * 0.06:.2f}",
        "results": results
    }


@router.get("/backgrounds")
async def list_backgrounds():
    """
    List available background styles for image enhancement.
    """
    return {
        "styles": {
            key: {
                "name": style["name"],
                "description": style["description"]
            }
            for key, style in BACKGROUND_STYLES.items()
        },
        "niche_defaults": NICHE_BACKGROUNDS,
        "tip": "Pass 'background_style' to override the default for a niche"
    }


# ============================================================================
# LEGACY ENDPOINT REDIRECTS (for backwards compatibility)
# ============================================================================

@router.post("/generate")
async def legacy_generate(request: EnhanceRequest):
    """
    DEPRECATED: Use /enhance instead.
    This redirects to the new enhance endpoint for backwards compatibility.
    """
    return await enhance_image(request)


@router.post("/compare")
async def legacy_compare():
    """
    DEPRECATED: Comparison modes removed.
    Use /enhance for the single best approach.
    """
    return {
        "message": "Comparison modes have been removed.",
        "reason": "Background replacement is the only reliable method for e-commerce.",
        "use_instead": "POST /api/images/enhance",
        "documentation": "GET /api/images/status"
    }


@router.get("/compare/status")
async def legacy_compare_status():
    """
    DEPRECATED: Redirects to main status endpoint.
    """
    return await get_status()
