"""
AI Image Generation API Routes
===============================
Endpoints for generating brand-consistent product images.

Routes:
- POST /api/images/generate - Generate AI image for a product
- POST /api/images/batch - Generate images for multiple products
- GET /api/images/status - Check image generation service status
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["AI Images"])

# Import image generator
try:
    from ospra_os.integrations.ai_image_generator import (
        get_image_generator,
        generate_product_image,
        enhance_products_with_ai_images
    )
    IMAGE_GENERATOR_AVAILABLE = True
except ImportError as e:
    IMAGE_GENERATOR_AVAILABLE = False
    logger.warning(f"[WARNING] AI Image Generator not available: {e}")


# ============================================================================
# REQUEST MODELS
# ============================================================================

class ImageGenerateRequest(BaseModel):
    product_title: str
    niche: str = "smart_home"
    original_image_url: Optional[str] = None
    tags: Optional[List[str]] = []
    force_regenerate: bool = False


class BatchImageRequest(BaseModel):
    products: List[dict]  # List of products with title, niche, image_url
    max_concurrent: int = 3


# ============================================================================
# ROUTES
# ============================================================================

@router.get("/status")
async def get_image_service_status():
    """Check AI image generation service status"""
    if not IMAGE_GENERATOR_AVAILABLE:
        return {
            "available": False,
            "message": "AI Image Generator module not loaded",
            "openai_configured": False,
            "gemini_configured": False,
            "stability_configured": False
        }
    
    generator = get_image_generator()
    
    # Safe attribute access (backwards compatibility)
    openai_avail = getattr(generator, 'openai_available', False)
    gemini_avail = getattr(generator, 'gemini_available', False)
    stability_avail = getattr(generator, 'stability_available', False)
    
    return {
        "available": True,
        "openai_configured": openai_avail,
        "gemini_configured": gemini_avail,
        "stability_configured": stability_avail,
        "cached_images": len(generator.cache) if hasattr(generator, 'cache') else 0,
        "active_provider": (
            "openai" if openai_avail else
            "gemini" if gemini_avail else
            "stability" if stability_avail else
            "none"
        ),
        "message": "Ready to generate brand-consistent product images"
    }


@router.post("/generate")
async def generate_image(request: ImageGenerateRequest):
    """
    Generate AI product image for Oubon Shop aesthetic.
    
    Returns AI-generated image URL and keeps original as reference.
    """
    if not IMAGE_GENERATOR_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI Image Generator not available. Check OPENAI_API_KEY or STABILITY_API_KEY."
        )
    
    generator = get_image_generator()
    
    if not generator.openai_available and not generator.stability_available:
        # Return original image as fallback
        return {
            "success": True,
            "ai_image_url": request.original_image_url,
            "original_image_url": request.original_image_url,
            "source": "fallback",
            "message": "No AI API configured - using original image"
        }
    
    try:
        result = await generator.generate_product_image(
            product_title=request.product_title,
            niche=request.niche,
            original_image_url=request.original_image_url,
            tags=request.tags,
            force_regenerate=request.force_regenerate
        )
        
        return {
            "success": True,
            **result
        }
        
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return {
            "success": False,
            "ai_image_url": request.original_image_url,
            "original_image_url": request.original_image_url,
            "source": "error",
            "error": str(e)
        }


@router.post("/batch")
async def generate_batch_images(request: BatchImageRequest):
    """
    Generate AI images for multiple products.
    
    Useful for enhancing discovery results with brand-consistent images.
    """
    if not IMAGE_GENERATOR_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI Image Generator not available"
        )
    
    try:
        enhanced_products = await enhance_products_with_ai_images(request.products)
        
        return {
            "success": True,
            "products": enhanced_products,
            "total": len(enhanced_products),
            "generated": sum(1 for p in enhanced_products if p.get('image_source') != 'fallback')
        }
        
    except Exception as e:
        logger.error(f"Batch image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regenerate/{product_id}")
async def regenerate_product_image(
    product_id: str,
    product_title: str,
    niche: str = "smart_home"
):
    """Force regenerate image for a specific product"""
    if not IMAGE_GENERATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI Image Generator not available")
    
    generator = get_image_generator()
    
    try:
        result = await generator.generate_product_image(
            product_title=product_title,
            niche=niche,
            force_regenerate=True
        )
        
        return {
            "success": True,
            "product_id": product_id,
            **result
        }
        
    except Exception as e:
        logger.error(f"Regeneration failed for {product_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
