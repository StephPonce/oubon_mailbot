"""
AI Image Generation & Comparison API Routes
============================================
Endpoints for generating brand-consistent product images.

Modes:
- text_only: DALL-E from title (fast, cheap, may not match)
- vision_enhanced: GPT-4V analyzes → DALL-E generates (good match)
- img2img: Stability transforms original (best match)

Routes:
- POST /api/images/generate - Generate AI image for a product
- POST /api/images/batch - Generate images for multiple products
- POST /api/images/compare - Compare all modes side-by-side
- GET /api/images/status - Check image generation service status
- GET /api/images/compare/status - Check comparison availability
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Literal
import logging
import time

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
    mode: Literal["text_only", "vision_enhanced", "img2img"] = "vision_enhanced"


class BatchImageRequest(BaseModel):
    products: List[dict]  # List of products with title, niche, image_url
    max_concurrent: int = 2
    mode: Literal["text_only", "vision_enhanced", "img2img"] = "vision_enhanced"


class CompareRequest(BaseModel):
    product_title: str
    niche: str = "smart_home"
    original_image_url: Optional[str] = None
    modes: Optional[List[str]] = None  # If None, try all available modes


# ============================================================================
# ROUTES - STATUS
# ============================================================================

@router.get("/status")
async def get_image_service_status():
    """Check AI image generation service status and available modes"""
    if not IMAGE_GENERATOR_AVAILABLE:
        return {
            "available": False,
            "message": "AI Image Generator module not loaded",
            "modes": []
        }
    
    generator = get_image_generator()
    
    available_modes = []
    
    # Check which modes are available
    if generator.openai_available:
        available_modes.append({
            "mode": "text_only",
            "name": "Text-to-Image",
            "description": "Generates new image from product title only",
            "provider": "DALL-E 3",
            "cost": "~$0.04",
            "quality": "May not match original product"
        })
        available_modes.append({
            "mode": "vision_enhanced", 
            "name": "Vision Enhanced",
            "description": "AI analyzes original image, then generates matching styled version",
            "provider": "GPT-4V + DALL-E 3",
            "cost": "~$0.06-0.08",
            "quality": "Good match to original product",
            "recommended": True
        })
    
    if generator.stability_available:
        available_modes.append({
            "mode": "img2img",
            "name": "Image-to-Image",
            "description": "Transforms original image while keeping product structure",
            "provider": "Stability AI",
            "cost": "~$0.02-0.04",
            "quality": "Best match - keeps exact product shape"
        })
    
    return {
        "available": True,
        "openai_configured": generator.openai_available,
        "stability_configured": generator.stability_available,
        "gemini_configured": generator.gemini_available,
        "modes": available_modes,
        "default_mode": "vision_enhanced" if generator.openai_available else "img2img" if generator.stability_available else "text_only",
        "cached_images": len(generator.cache),
        "message": "Ready to generate brand-consistent product images"
    }


# ============================================================================
# ROUTES - GENERATION
# ============================================================================

@router.post("/generate")
async def generate_image(request: ImageGenerateRequest):
    """
    Generate AI product image for Oubon Shop aesthetic.
    
    Modes:
    - text_only: Fast, cheap, but may not match original product
    - vision_enhanced: GPT-4V analyzes original → DALL-E generates (recommended)
    - img2img: Stability AI transforms original (best structure match)
    
    Returns AI-generated image URL and keeps original as reference.
    """
    if not IMAGE_GENERATOR_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI Image Generator not available. Check API keys."
        )
    
    generator = get_image_generator()
    
    # Check if requested mode is available
    mode = request.mode
    if mode == "vision_enhanced" and not generator.openai_available:
        mode = "img2img" if generator.stability_available else "text_only"
        logger.warning(f"Vision mode unavailable, falling back to {mode}")
    elif mode == "img2img" and not generator.stability_available:
        mode = "vision_enhanced" if generator.openai_available else "text_only"
        logger.warning(f"Img2img mode unavailable, falling back to {mode}")
    
    # Check if we need original image for requested mode
    if mode in ["vision_enhanced", "img2img"] and not request.original_image_url:
        # Can't do vision/img2img without original image
        mode = "text_only"
        logger.warning("No original image provided, falling back to text_only mode")
    
    try:
        result = await generator.generate_product_image(
            product_title=request.product_title,
            niche=request.niche,
            original_image_url=request.original_image_url,
            tags=request.tags,
            force_regenerate=request.force_regenerate,
            mode=mode
        )
        
        return {
            "success": True,
            "requested_mode": request.mode,
            "actual_mode": result.get("mode", mode),
            **result
        }
        
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return {
            "success": False,
            "ai_image_url": request.original_image_url,
            "original_image_url": request.original_image_url,
            "source": "error",
            "mode": "none",
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
    
    generator = get_image_generator()
    
    try:
        enhanced_products = await generator.generate_batch(
            request.products,
            max_concurrent=request.max_concurrent,
            mode=request.mode
        )
        
        return {
            "success": True,
            "products": enhanced_products,
            "total": len(enhanced_products),
            "mode": request.mode,
            "generated": sum(1 for p in enhanced_products if p.get('image_source') not in ['fallback', 'error'])
        }
        
    except Exception as e:
        logger.error(f"Batch image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regenerate/{product_id}")
async def regenerate_product_image(
    product_id: str,
    product_title: str,
    niche: str = "smart_home",
    original_image_url: str = None,
    mode: str = "vision_enhanced"
):
    """Force regenerate image for a specific product"""
    if not IMAGE_GENERATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI Image Generator not available")
    
    generator = get_image_generator()
    
    try:
        result = await generator.generate_product_image(
            product_title=product_title,
            niche=niche,
            original_image_url=original_image_url,
            force_regenerate=True,
            mode=mode
        )
        
        return {
            "success": True,
            "product_id": product_id,
            "mode": result.get("mode", mode),
            **result
        }
        
    except Exception as e:
        logger.error(f"Regeneration failed for {product_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROUTES - COMPARISON (Sample All Modes)
# ============================================================================

@router.get("/compare/status")
async def get_compare_status():
    """Check which comparison modes are available"""
    if not IMAGE_GENERATOR_AVAILABLE:
        return {"available": False, "modes": []}
    
    generator = get_image_generator()
    
    modes = []
    
    if generator.openai_available:
        modes.append({
            "id": "text_only",
            "name": "Text Only (DALL-E 3)",
            "description": "Generates from product title - doesn't see original image",
            "requires_original": False,
            "cost": "$0.04",
            "speed": "Fast (~3s)",
            "accuracy": "May not match product"
        })
        modes.append({
            "id": "vision_enhanced", 
            "name": "Vision Enhanced (GPT-4V + DALL-E)",
            "description": "AI analyzes your image first, then generates matching styled version",
            "requires_original": True,
            "cost": "$0.07",
            "speed": "Medium (~8s)",
            "accuracy": "Good match"
        })
    
    if generator.stability_available:
        modes.append({
            "id": "img2img",
            "name": "Image Transform (Stability AI)",
            "description": "Transforms original image while keeping product structure",
            "requires_original": True,
            "cost": "$0.03",
            "speed": "Medium (~5s)",
            "accuracy": "Best match - keeps exact shape"
        })
    
    return {
        "available": True,
        "modes": modes,
        "openai_configured": generator.openai_available,
        "stability_configured": generator.stability_available,
        "note": "Use POST /api/images/compare to test all modes on a product"
    }


@router.post("/compare")
async def compare_all_modes(request: CompareRequest):
    """
    Generate images with ALL available modes for side-by-side comparison.
    
    This helps you decide which mode works best for your products.
    
    Example response:
    {
        "original": "https://...",
        "results": {
            "text_only": { "url": "...", "cost": "$0.04", "time": "3.2s" },
            "vision_enhanced": { "url": "...", "cost": "$0.07", "time": "8.1s" },
            "img2img": { "url": "...", "cost": "$0.03", "time": "5.4s" }
        }
    }
    """
    if not IMAGE_GENERATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI Image Generator not available")
    
    generator = get_image_generator()
    
    # Determine which modes to test
    modes_to_test = request.modes or []
    
    if not modes_to_test:
        # Auto-detect available modes
        if generator.openai_available:
            modes_to_test.append("text_only")
            if request.original_image_url:
                modes_to_test.append("vision_enhanced")
        if generator.stability_available and request.original_image_url:
            modes_to_test.append("img2img")
    
    if not modes_to_test:
        raise HTTPException(
            status_code=400, 
            detail="No image generation modes available. Configure OPENAI_API_KEY or STABILITY_API_KEY."
        )
    
    results = {
        "product_title": request.product_title,
        "niche": request.niche,
        "original_image_url": request.original_image_url,
        "modes_tested": modes_to_test,
        "comparisons": {}
    }
    
    # Cost estimates
    cost_estimates = {
        "text_only": 0.04,
        "vision_enhanced": 0.07,
        "img2img": 0.03
    }
    
    # Generate with each mode
    for mode in modes_to_test:
        start_time = time.time()
        
        try:
            result = await generator.generate_product_image(
                product_title=request.product_title,
                niche=request.niche,
                original_image_url=request.original_image_url,
                force_regenerate=True,  # Always regenerate for comparison
                mode=mode
            )
            
            elapsed = time.time() - start_time
            
            results["comparisons"][mode] = {
                "success": True,
                "ai_image_url": result.get("ai_image_url"),
                "source": result.get("source"),
                "time_seconds": round(elapsed, 2),
                "estimated_cost": f"${cost_estimates.get(mode, 0.05):.2f}",
                "note": result.get("note", ""),
                "product_analysis": result.get("product_analysis", None)  # Only for vision mode
            }
            
        except Exception as e:
            results["comparisons"][mode] = {
                "success": False,
                "error": str(e),
                "time_seconds": round(time.time() - start_time, 2)
            }
    
    # Add recommendations
    successful_modes = [m for m, r in results["comparisons"].items() if r.get("success")]
    
    if "img2img" in successful_modes:
        results["recommendation"] = {
            "best_match": "img2img",
            "reason": "Keeps original product structure while enhancing style"
        }
    elif "vision_enhanced" in successful_modes:
        results["recommendation"] = {
            "best_match": "vision_enhanced",
            "reason": "AI analyzed your product before generating"
        }
    elif "text_only" in successful_modes:
        results["recommendation"] = {
            "best_match": "text_only",
            "reason": "Only option available - may not match original product"
        }
    
    # Calculate total cost
    total_cost = sum(
        cost_estimates.get(m, 0.05) 
        for m, r in results["comparisons"].items() 
        if r.get("success")
    )
    results["total_cost"] = f"${total_cost:.2f}"
    
    return results
