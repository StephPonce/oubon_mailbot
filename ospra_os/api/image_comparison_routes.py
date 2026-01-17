"""
AI Image Comparison API
=======================
Generate images with ALL modes for side-by-side comparison.

This helps you decide which mode works best for your products.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["AI Images"])

# Import image generator
try:
    from ospra_os.integrations.ai_image_generator import get_image_generator
    IMAGE_GENERATOR_AVAILABLE = True
except ImportError as e:
    IMAGE_GENERATOR_AVAILABLE = False
    logger.warning(f"AI Image Generator not available: {e}")


class CompareRequest(BaseModel):
    product_title: str
    niche: str = "smart_home"
    original_image_url: Optional[str] = None
    additional_image_urls: Optional[List[str]] = None  # NEW: Multiple images for hybrid mode
    modes: Optional[List[str]] = None  # If None, try all available modes


@router.post("/compare")
async def compare_all_modes(request: CompareRequest):
    """
    Generate images with ALL available modes for comparison.
    
    Returns side-by-side results so you can see which mode works best.
    
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
        # NEW: Hybrid mode requires BOTH OpenAI and Stability
        if generator.openai_available and generator.stability_available and request.original_image_url:
            modes_to_test.append("hybrid")
    
    if not modes_to_test:
        raise HTTPException(
            status_code=400, 
            detail="No image generation modes available. Configure OPENAI_API_KEY or STABILITY_API_KEY."
        )
    
    # Collect all image URLs
    all_image_urls = []
    if request.original_image_url:
        all_image_urls.append(request.original_image_url)
    if request.additional_image_urls:
        all_image_urls.extend(request.additional_image_urls[:2])  # Max 2 additional
    
    results = {
        "product_title": request.product_title,
        "niche": request.niche,
        "original_image_url": request.original_image_url,
        "additional_image_urls": request.additional_image_urls,
        "total_images": len(all_image_urls),
        "modes_tested": modes_to_test,
        "comparisons": {}
    }
    
    # Cost estimates
    cost_estimates = {
        "text_only": 0.04,
        "vision_enhanced": 0.07,
        "img2img": 0.03,
        "hybrid": 0.06  # GPT-4V (~$0.03) + Stability (~$0.03)
    }
    
    # Generate with each mode
    for mode in modes_to_test:
        import time
        start_time = time.time()
        
        try:
            result = await generator.generate_product_image(
                product_title=request.product_title,
                niche=request.niche,
                original_image_url=request.original_image_url,
                additional_image_urls=request.additional_image_urls,  # Pass all images!
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
    
    # Add recommendations (prioritize hybrid > img2img > vision_enhanced > text_only)
    successful_modes = [m for m, r in results["comparisons"].items() if r.get("success")]
    
    if "hybrid" in successful_modes:
        results["recommendation"] = {
            "best_match": "hybrid",
            "reason": "🔥 Best of both worlds: Multi-image AI understanding + exact structure preservation"
        }
    elif "img2img" in successful_modes:
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


@router.get("/compare/status")
async def get_compare_status():
    """Check which comparison modes are available"""
    import os
    
    if not IMAGE_GENERATOR_AVAILABLE:
        return {"available": False, "modes": [], "api_keys_status": {}}
    
    generator = get_image_generator()
    
    # Get actual key status (for debugging)
    openai_key = os.getenv('OPENAI_API_KEY')
    stability_key = os.getenv('STABILITY_API_KEY')
    
    api_keys_status = {
        "openai": {
            "configured": bool(openai_key),
            "key_preview": f"{openai_key[:8]}..." if openai_key else None
        },
        "stability": {
            "configured": bool(stability_key),
            "key_preview": f"{stability_key[:8]}..." if stability_key else None
        }
    }
    
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
    else:
        # Show disabled mode with instructions
        modes.append({
            "id": "img2img",
            "name": "Image Transform (Stability AI)",
            "description": "DISABLED: Add STABILITY_API_KEY to Render Dashboard to enable",
            "requires_original": True,
            "cost": "$0.03",
            "speed": "Medium (~5s)",
            "accuracy": "Best match - keeps exact shape",
            "disabled": True,
            "disabled_reason": "STABILITY_API_KEY not configured in environment"
        })
    
    # NEW: Hybrid mode (requires BOTH OpenAI AND Stability)
    if generator.openai_available and generator.stability_available:
        modes.append({
            "id": "hybrid",
            "name": "🔥 Hybrid (GPT-4V + Stability AI)",
            "description": "BEST MODE: AI analyzes ALL images → Stability preserves exact product structure",
            "requires_original": True,
            "cost": "$0.06",
            "speed": "Slower (~12s)",
            "accuracy": "MAXIMUM - multi-image understanding + exact structure",
            "recommended": True
        })
    elif generator.openai_available or generator.stability_available:
        # Show what's missing for hybrid
        missing = []
        if not generator.openai_available:
            missing.append("OPENAI_API_KEY")
        if not generator.stability_available:
            missing.append("STABILITY_API_KEY")
        modes.append({
            "id": "hybrid",
            "name": "🔥 Hybrid (GPT-4V + Stability AI)",
            "description": f"DISABLED: Requires both {' and '.join(missing)}",
            "requires_original": True,
            "cost": "$0.06",
            "speed": "Slower (~12s)",
            "accuracy": "MAXIMUM - multi-image understanding + exact structure",
            "disabled": True,
            "disabled_reason": f"Missing: {', '.join(missing)}"
        })
    
    return {
        "available": True,
        "modes": modes,
        "openai_configured": generator.openai_available,
        "stability_configured": generator.stability_available,
        "api_keys_status": api_keys_status,
        "note": "Use POST /api/images/compare to test all modes on a product"
    }
