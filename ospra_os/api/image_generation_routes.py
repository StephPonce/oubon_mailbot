"""
AI Image Generation & Comparison API Routes - V3
=================================================
Enhanced with multi-image support and better error handling.

Modes:
- text_only: DALL-E from title (fast, cheap, may not match)
- vision_enhanced: GPT-4V analyzes multiple images → DALL-E generates (good match)
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
import os
import asyncio
import aiohttp

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
    additional_image_urls: Optional[List[str]] = None  # NEW: Multiple images
    tags: Optional[List[str]] = []
    force_regenerate: bool = False
    mode: Literal["text_only", "vision_enhanced", "img2img", "hybrid"] = "vision_enhanced"


class BatchImageRequest(BaseModel):
    products: List[dict]  # List of products with title, niche, image_url, additional_images
    max_concurrent: int = 2
    mode: Literal["text_only", "vision_enhanced", "img2img", "hybrid"] = "vision_enhanced"


class CompareRequest(BaseModel):
    product_title: str
    niche: str = "smart_home"
    original_image_url: Optional[str] = None
    additional_image_urls: Optional[List[str]] = None  # NEW: Multiple images
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
            "quality": "May not match original product",
            "supports_multi_image": False
        })
        available_modes.append({
            "mode": "vision_enhanced", 
            "name": "Vision Enhanced",
            "description": "AI analyzes up to 3 product images, then generates matching styled version",
            "provider": "GPT-4V + DALL-E 3",
            "cost": "~$0.06-0.08",
            "quality": "Good match to original product",
            "recommended": True,
            "supports_multi_image": True
        })
    
    if generator.stability_available:
        available_modes.append({
            "mode": "img2img",
            "name": "Image-to-Image",
            "description": "Transforms original image while keeping product structure",
            "provider": "Stability AI",
            "cost": "~$0.02-0.04",
            "quality": "Best match - keeps exact product shape",
            "supports_multi_image": False
        })
    
    # Hybrid mode requires BOTH OpenAI AND Stability
    if generator.openai_available and generator.stability_available:
        available_modes.append({
            "mode": "hybrid",
            "name": "Hybrid (GPT-4V + Stability AI)",
            "description": "GPT-4V analyzes multiple images for deep understanding, Stability AI preserves exact product structure",
            "provider": "GPT-4V + Stability AI",
            "cost": "~$0.06",
            "quality": "BEST - Multi-image understanding + exact structure preservation",
            "recommended_for": "Products with multiple angles available",
            "supports_multi_image": True
        })
    
    # Check API keys explicitly
    openai_key = os.getenv('OPENAI_API_KEY')
    stability_key = os.getenv('STABILITY_API_KEY')
    
    return {
        "available": True,
        "openai_configured": generator.openai_available,
        "stability_configured": generator.stability_available,
        "gemini_configured": generator.gemini_available,
        "modes": available_modes,
        "default_mode": "vision_enhanced" if generator.openai_available else "img2img" if generator.stability_available else "text_only",
        "cached_images": len(generator.cache),
        "api_keys": {
            "openai": f"{openai_key[:20]}..." if openai_key else "NOT SET",
            "stability": f"{stability_key[:20]}..." if stability_key else "NOT SET"
        },
        "features": {
            "multi_image_support": True,
            "niche_specific_styling": True,
            "enhanced_prompts": True
        },
        "message": "V3 ready - Multi-image support enabled with niche-specific styling"
    }


# ============================================================================
# ROUTES - GENERATION
# ============================================================================

@router.post("/generate")
async def generate_image(request: ImageGenerateRequest):
    """
    Generate AI product image for Oubon Shop aesthetic.
    
    V3 Features:
    - Multi-image input: Pass additional_image_urls for better AI context
    - Niche-specific styling: AI uses category-appropriate aesthetics
    - Enhanced prompts: More detailed instructions for better results
    
    Modes:
    - text_only: Fast, cheap, but may not match original product
    - vision_enhanced: GPT-4V analyzes up to 3 images → DALL-E generates (recommended)
    - img2img: Stability AI transforms original (best structure match)
    """
    if not IMAGE_GENERATOR_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI Image Generator not available. Check API keys."
        )
    
    generator = get_image_generator()
    
    # Check if requested mode is available
    mode = request.mode
    if mode == "hybrid" and not (generator.openai_available and generator.stability_available):
        # Hybrid needs both - fall back to best available
        if generator.stability_available and request.original_image_url:
            mode = "img2img"
        elif generator.openai_available:
            mode = "vision_enhanced" if request.original_image_url else "text_only"
        else:
            mode = "text_only"
        logger.warning(f"Hybrid mode unavailable, falling back to {mode}")
    elif mode == "vision_enhanced" and not generator.openai_available:
        mode = "img2img" if generator.stability_available else "text_only"
        logger.warning(f"Vision mode unavailable, falling back to {mode}")
    elif mode == "img2img" and not generator.stability_available:
        mode = "vision_enhanced" if generator.openai_available else "text_only"
        logger.warning(f"Img2img mode unavailable, falling back to {mode}")
    
    # Check if we need original image for requested mode
    if mode in ["vision_enhanced", "img2img"] and not request.original_image_url:
        mode = "text_only"
        logger.warning("No original image provided, falling back to text_only mode")
    
    try:
        result = await generator.generate_product_image(
            product_title=request.product_title,
            niche=request.niche,
            original_image_url=request.original_image_url,
            additional_image_urls=request.additional_image_urls,  # NEW
            tags=request.tags,
            force_regenerate=request.force_regenerate,
            mode=mode
        )
        
        return {
            "success": True,
            "requested_mode": request.mode,
            "actual_mode": result.get("mode", mode),
            "images_provided": 1 + len(request.additional_image_urls or []),
            "images_analyzed": result.get("images_analyzed", 0),
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
    
    Each product can include:
    - title: Product name
    - niche: Category
    - image_url: Primary image
    - additional_images: List of additional angles (up to 2)
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
            "generated": sum(1 for p in enhanced_products if p.get('image_source') not in ['fallback', 'error']),
            "multi_image_used": sum(1 for p in enhanced_products if p.get('images_analyzed', 0) > 1)
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
    additional_image_urls: List[str] = None,
    mode: Literal["text_only", "vision_enhanced", "img2img", "hybrid"] = "vision_enhanced"
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
            additional_image_urls=additional_image_urls,
            force_regenerate=True,
            mode=mode
        )
        
        return {
            "success": True,
            "product_id": product_id,
            "mode": result.get("mode", mode),
            "images_analyzed": result.get("images_analyzed", 0),
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
    
    # Check API keys
    openai_key = os.getenv('OPENAI_API_KEY')
    stability_key = os.getenv('STABILITY_API_KEY')
    
    modes = []
    
    if generator.openai_available:
        modes.append({
            "id": "text_only",
            "name": "Text Only (DALL-E 3)",
            "description": "Generates from product title - doesn't see original image",
            "requires_original": False,
            "cost": "$0.04",
            "speed": "Fast (~3s)",
            "accuracy": "May not match product",
            "supports_multi_image": False
        })
        modes.append({
            "id": "vision_enhanced", 
            "name": "Vision Enhanced (GPT-4V + DALL-E)",
            "description": "AI analyzes up to 3 images, then generates matching styled version",
            "requires_original": True,
            "cost": "$0.07",
            "speed": "Medium (~8s)",
            "accuracy": "Good match",
            "supports_multi_image": True,
            "recommended": True
        })
    
    if generator.stability_available:
        modes.append({
            "id": "img2img",
            "name": "Image Transform (Stability AI)",
            "description": "Transforms original image while keeping product structure",
            "requires_original": True,
            "cost": "$0.03",
            "speed": "Medium (~5s)",
            "accuracy": "Best match - keeps exact shape",
            "supports_multi_image": False
        })
    
    # Hybrid mode - requires BOTH OpenAI AND Stability
    if generator.openai_available and generator.stability_available:
        modes.append({
            "id": "hybrid",
            "name": "Hybrid (GPT-4V + Stability AI)",
            "description": "GPT-4V analyzes multiple images for deep understanding, Stability AI preserves product structure",
            "requires_original": True,
            "cost": "$0.06",
            "speed": "Slower (~12s)",
            "accuracy": "BEST - Multi-image understanding + exact structure",
            "supports_multi_image": True,
            "recommended": True
        })
    
    return {
        "available": True,
        "modes": modes,
        "openai_configured": generator.openai_available,
        "stability_configured": generator.stability_available,
        "api_keys_status": {
            "openai": "✅ Set" if openai_key else "❌ Not set",
            "stability": "✅ Set" if stability_key else "❌ Not set"
        },
        "note": "Use POST /api/images/compare to test all modes on a product"
    }


@router.post("/compare")
async def compare_all_modes(request: CompareRequest):
    """
    Generate images with ALL available modes for side-by-side comparison.
    
    V3: Now supports multiple input images for vision_enhanced mode.
    
    Example request:
    {
        "product_title": "Smart LED Desk Lamp",
        "niche": "smart_home",
        "original_image_url": "https://...",
        "additional_image_urls": ["https://...", "https://..."]  // Optional
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
        # Hybrid mode requires BOTH OpenAI AND Stability AND an original image
        if generator.openai_available and generator.stability_available and request.original_image_url:
            modes_to_test.append("hybrid")
    
    if not modes_to_test:
        raise HTTPException(
            status_code=400, 
            detail="No image generation modes available. Configure OPENAI_API_KEY or STABILITY_API_KEY."
        )
    
    # Count total images
    total_images = 1 if request.original_image_url else 0
    total_images += len(request.additional_image_urls or [])
    
    results = {
        "product_title": request.product_title,
        "niche": request.niche,
        "original_image_url": request.original_image_url,
        "additional_images_provided": len(request.additional_image_urls or []),
        "total_images": total_images,
        "modes_tested": modes_to_test,
        "comparisons": {}
    }
    
    # Cost estimates
    cost_estimates = {
        "text_only": 0.04,
        "vision_enhanced": 0.07,
        "img2img": 0.03,
        "hybrid": 0.06
    }
    
    # Generate with each mode
    for mode in modes_to_test:
        start_time = time.time()
        
        try:
            # Only pass additional images for vision_enhanced
            additional = request.additional_image_urls if mode == "vision_enhanced" else None
            
            result = await generator.generate_product_image(
                product_title=request.product_title,
                niche=request.niche,
                original_image_url=request.original_image_url,
                additional_image_urls=additional,
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
                "images_analyzed": result.get("images_analyzed", 0),
                "note": result.get("note", ""),
                "product_analysis": result.get("product_analysis", None),
                "prompt_preview": result.get("prompt_used", "")[:200] + "..." if result.get("prompt_used") else None
            }
            
        except Exception as e:
            logger.error(f"[COMPARE] {mode} failed: {e}")
            results["comparisons"][mode] = {
                "success": False,
                "error": str(e),
                "time_seconds": round(time.time() - start_time, 2)
            }
    
    # Add recommendations - prioritize hybrid > img2img > vision_enhanced > text_only
    successful_modes = [m for m, r in results["comparisons"].items() if r.get("success")]
    
    if "hybrid" in successful_modes:
        imgs = results["comparisons"]["hybrid"].get("images_analyzed", 0)
        results["recommendation"] = {
            "best_match": "hybrid",
            "reason": f"BEST: GPT-4V analyzed {imgs} image(s) for deep understanding + Stability AI preserved exact structure"
        }
    elif "img2img" in successful_modes:
        results["recommendation"] = {
            "best_match": "img2img",
            "reason": "Keeps original product structure while enhancing style"
        }
    elif "vision_enhanced" in successful_modes:
        imgs = results["comparisons"]["vision_enhanced"].get("images_analyzed", 0)
        results["recommendation"] = {
            "best_match": "vision_enhanced",
            "reason": f"AI analyzed {imgs} image(s) for accurate product recreation"
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


# ============================================================================
# DEBUG ENDPOINT
# ============================================================================

@router.get("/debug")
async def debug_image_generation():
    """Debug endpoint to check configuration and diagnose issues - reads env vars at RUNTIME"""
    
    # Read env vars at RUNTIME (not cached)
    openai_key = os.getenv('OPENAI_API_KEY', '')
    stability_key = os.getenv('STABILITY_API_KEY', '')
    
    debug_info = {
        "module_loaded": IMAGE_GENERATOR_AVAILABLE,
        "environment": {
            "OPENAI_API_KEY": f"{openai_key[:20]}..." if openai_key else "NOT SET ❌",
            "STABILITY_API_KEY": f"{stability_key[:15]}...{stability_key[-4:]}" if stability_key else "NOT SET ❌",
            "GOOGLE_AI_API_KEY": "Set" if os.getenv('GOOGLE_AI_API_KEY') else "NOT SET"
        },
        "recommendations": []
    }
    
    if not openai_key:
        debug_info["recommendations"].append(
            "Set OPENAI_API_KEY for text_only and vision_enhanced modes"
        )
    
    if not stability_key:
        debug_info["recommendations"].append(
            "Set STABILITY_API_KEY for img2img mode (best for product accuracy)"
        )
        debug_info["recommendations"].append(
            "Get your key at: https://platform.stability.ai/account/keys"
        )
    
    if IMAGE_GENERATOR_AVAILABLE:
        generator = get_image_generator()
        debug_info["generator"] = {
            "openai_available": generator.openai_available,
            "stability_available": generator.stability_available,
            "gemini_available": generator.gemini_available,
            "cache_size": len(generator.cache)
        }
    
    return debug_info


@router.post("/test/stability")
async def test_stability_ai():
    """
    Test Stability AI API connection.
    
    This will:
    1. Check if STABILITY_API_KEY is set
    2. Make a simple API call to verify the key works
    3. Return detailed status
    """
    stability_key = os.getenv('STABILITY_API_KEY')
    
    if not stability_key:
        return {
            "success": False,
            "error": "STABILITY_API_KEY not set in environment",
            "fix": "Add STABILITY_API_KEY to your .env file",
            "get_key": "https://platform.stability.ai/account/keys"
        }
    
    # Test the API with account balance check
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.stability.ai/v1/user/balance",
                headers={"Authorization": f"Bearer {stability_key}"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    credits = data.get('credits', 0)
                    
                    return {
                        "success": True,
                        "api_key": f"{stability_key[:15]}...{stability_key[-4:]}",
                        "credits": credits,
                        "credits_status": "✅ Has credits" if credits > 0 else "❌ No credits - add at https://platform.stability.ai/account/credits",
                        "v1_api": "Available",
                        "v2beta_api": "Available",
                        "message": "Stability AI connection successful!"
                    }
                elif response.status == 401:
                    return {
                        "success": False,
                        "error": "Invalid API key",
                        "status_code": 401,
                        "fix": "Check your STABILITY_API_KEY - it may be expired or incorrect",
                        "get_key": "https://platform.stability.ai/account/keys"
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"API returned status {response.status}",
                        "details": error_text[:200],
                        "status_code": response.status
                    }
                    
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "Connection timeout",
            "fix": "Stability AI may be experiencing issues - try again later"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.post("/test/download")
async def test_image_download(image_url: str = "https://cf.cjdropshipping.com/e45906a8-2238-4439-b1a3-2931f50b13c8.jpg"):
    """
    Test if we can download an image from a URL.
    This helps debug why img2img might be failing.
    """
    import base64
    
    results = {
        "url": image_url,
        "steps": []
    }
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'image/*,*/*;q=0.8',
            'Referer': 'https://www.cjdropshipping.com/'
        }
        
        results["steps"].append(f"Attempting download with headers: {list(headers.keys())}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                image_url,
                timeout=aiohttp.ClientTimeout(total=30),
                headers=headers,
                allow_redirects=True
            ) as response:
                results["status_code"] = response.status
                results["content_type"] = response.headers.get('content-type', 'unknown')
                results["steps"].append(f"Response status: {response.status}")
                
                if response.status == 200:
                    image_bytes = await response.read()
                    results["image_size_bytes"] = len(image_bytes)
                    results["steps"].append(f"Downloaded {len(image_bytes):,} bytes")
                    
                    if len(image_bytes) > 1000:
                        # Successfully downloaded
                        results["success"] = True
                        results["base64_preview"] = base64.b64encode(image_bytes[:100]).decode()[:50] + "..."
                        results["message"] = "✅ Image download successful!"
                    else:
                        results["success"] = False
                        results["error"] = "Image too small - likely an error page"
                        # Show what we got
                        try:
                            results["response_text"] = image_bytes.decode('utf-8')[:500]
                        except:
                            results["response_text"] = "(binary data)"
                else:
                    results["success"] = False
                    error_text = await response.text()
                    results["error"] = f"HTTP {response.status}"
                    results["response_text"] = error_text[:500]
                    
    except asyncio.TimeoutError:
        results["success"] = False
        results["error"] = "Timeout after 30 seconds"
    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        results["error_type"] = type(e).__name__
    
    return results


@router.post("/test/generate")
async def test_generate_image(
    test_url: str = "https://ae01.alicdn.com/kf/S1c66c5e8655d4c5c8b7a5e1d3f4e5f6g/Smart-LED-Desk-Lamp.jpg"
):
    """
    Quick test to generate an image with all available modes.
    
    Provide a test_url or use the default AliExpress product image.
    """
    if not IMAGE_GENERATOR_AVAILABLE:
        return {"success": False, "error": "Image generator not available"}
    
    generator = get_image_generator()
    
    results = {
        "test_image": test_url,
        "modes_tested": [],
        "results": {}
    }
    
    # Test each available mode
    if generator.openai_available:
        results["modes_tested"].append("text_only")
        try:
            result = await generator.generate_product_image(
                product_title="Smart LED Desk Lamp with Touch Control",
                niche="smart_home",
                mode="text_only",
                force_regenerate=True
            )
            results["results"]["text_only"] = {
                "success": bool(result.get("ai_image_url")),
                "source": result.get("source"),
                "url": result.get("ai_image_url")
            }
        except Exception as e:
            results["results"]["text_only"] = {"success": False, "error": str(e)}
    
    if generator.stability_available:
        results["modes_tested"].append("img2img")
        try:
            result = await generator.generate_product_image(
                product_title="Smart LED Desk Lamp with Touch Control",
                niche="smart_home",
                original_image_url=test_url,
                mode="img2img",
                force_regenerate=True
            )
            results["results"]["img2img"] = {
                "success": bool(result.get("ai_image_url") and result.get("source") != "fallback"),
                "source": result.get("source"),
                "api_version": result.get("api_version"),
                "url": result.get("ai_image_url")
            }
        except Exception as e:
            results["results"]["img2img"] = {"success": False, "error": str(e)}
    
    return results


@router.post("/test/img2img-verbose")
async def test_img2img_verbose(
    image_url: str = "https://cf.cjdropshipping.com/e45906a8-2238-4439-b1a3-2931f50b13c8.jpg",
    product_title: str = "Airtag Wallet Men Smart Wallet"
):
    """
    Verbose test of img2img pipeline - shows each step for debugging.
    """
    import base64
    from PIL import Image
    import io
    
    steps = []
    result = {"url": image_url, "title": product_title}
    
    # Step 1: Check Stability API key
    stability_key = os.getenv('STABILITY_API_KEY', '')
    steps.append({
        "step": 1,
        "name": "Check API Key",
        "success": bool(stability_key),
        "key_preview": f"{stability_key[:10]}...{stability_key[-4:]}" if stability_key else "NOT SET"
    })
    
    if not stability_key:
        result["steps"] = steps
        result["error"] = "STABILITY_API_KEY not set"
        return result
    
    # Step 2: Download image
    steps.append({"step": 2, "name": "Download Image", "status": "starting..."})
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'image/*,*/*;q=0.8',
            'Referer': 'https://www.cjdropshipping.com/'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                image_url,
                timeout=aiohttp.ClientTimeout(total=30),
                headers=headers,
                allow_redirects=True
            ) as response:
                steps[-1]["http_status"] = response.status
                steps[-1]["content_type"] = response.headers.get('content-type', 'unknown')
                
                if response.status != 200:
                    steps[-1]["success"] = False
                    steps[-1]["error"] = f"HTTP {response.status}"
                    result["steps"] = steps
                    result["error"] = "Image download failed"
                    return result
                
                image_bytes = await response.read()
                steps[-1]["image_size"] = len(image_bytes)
                
                if len(image_bytes) < 1000:
                    steps[-1]["success"] = False
                    steps[-1]["error"] = "Image too small"
                    result["steps"] = steps
                    result["error"] = "Downloaded image too small"
                    return result
                
                steps[-1]["success"] = True
                steps[-1]["status"] = f"Downloaded {len(image_bytes):,} bytes"
    
    except Exception as e:
        steps[-1]["success"] = False
        steps[-1]["error"] = str(e)
        result["steps"] = steps
        result["error"] = f"Download exception: {e}"
        return result
    
    # Step 2.5: Resize image for SDXL
    steps.append({"step": 2.5, "name": "Resize for SDXL", "status": "resizing..."})
    try:
        img = Image.open(io.BytesIO(image_bytes))
        steps[-1]["original_size"] = f"{img.size[0]}x{img.size[1]}"
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Resize to 1024x1024
        width, height = img.size
        target = 1024
        if width < height:
            new_width = target
            new_height = int(height * (target / width))
        else:
            new_height = target
            new_width = int(width * (target / height))
        
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        left = (new_width - target) // 2
        top = (new_height - target) // 2
        img = img.crop((left, top, left + target, top + target))
        
        output = io.BytesIO()
        img.save(output, format='PNG', quality=95)
        output.seek(0)
        image_bytes = output.read()
        
        steps[-1]["success"] = True
        steps[-1]["new_size"] = "1024x1024"
        steps[-1]["new_bytes"] = len(image_bytes)
    except Exception as e:
        steps[-1]["success"] = False
        steps[-1]["error"] = str(e)
        # Continue with original bytes
    
    # Step 3: Call Stability v1 API
    steps.append({"step": 3, "name": "Stability v1 API", "status": "calling..."})
    
    style_prompt = f"""Transform this product photo into a premium e-commerce hero shot.
Style: modern tech minimalist
Background: clean white or soft gray gradient
Keep the exact product shape and details.
Professional studio quality."""
    
    try:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field('init_image', image_bytes, filename='image.png', content_type='image/png')
            form.add_field('init_image_mode', 'IMAGE_STRENGTH')
            form.add_field('image_strength', '0.35')
            form.add_field('text_prompts[0][text]', style_prompt)
            form.add_field('text_prompts[0][weight]', '1')
            form.add_field('cfg_scale', '7')
            form.add_field('samples', '1')
            form.add_field('steps', '30')
            
            async with session.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image",
                headers={
                    "Authorization": f"Bearer {stability_key}",
                    "Accept": "application/json"
                },
                data=form,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                steps[-1]["http_status"] = response.status
                
                if response.status == 200:
                    data = await response.json()
                    steps[-1]["success"] = True
                    steps[-1]["status"] = "Image generated!"
                    
                    # Save the result
                    result_base64 = data['artifacts'][0]['base64']
                    result["success"] = True
                    result["api_version"] = "v1"
                    result["generated_image_preview"] = result_base64[:100] + "..."
                    result["steps"] = steps
                    return result
                else:
                    error_text = await response.text()
                    steps[-1]["success"] = False
                    steps[-1]["error"] = error_text[:300]
                    
                    # Parse error for helpful message
                    if response.status == 400:
                        steps[-1]["hint"] = "Bad request - image may be wrong format or too large"
                    elif response.status == 401:
                        steps[-1]["hint"] = "Invalid API key"
                    elif response.status == 402:
                        steps[-1]["hint"] = "Out of credits"
                    elif response.status == 403:
                        steps[-1]["hint"] = "Access denied - check API permissions"
    
    except Exception as e:
        steps[-1]["success"] = False
        steps[-1]["error"] = str(e)
        steps[-1]["error_type"] = type(e).__name__
    
    # Step 4: Try v2beta API as fallback (with mode=image-to-image)
    steps.append({"step": 4, "name": "Stability v2beta API (core, img2img)", "status": "calling..."})
    
    try:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field('image', image_bytes, filename='image.png', content_type='image/png')
            form.add_field('prompt', style_prompt)
            form.add_field('mode', 'image-to-image')  # CRITICAL!
            form.add_field('strength', '0.35')
            form.add_field('output_format', 'png')
            
            async with session.post(
                "https://api.stability.ai/v2beta/stable-image/generate/core",
                headers={
                    "Authorization": f"Bearer {stability_key}",
                    "Accept": "image/*"
                },
                data=form,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                steps[-1]["http_status"] = response.status
                
                if response.status == 200:
                    result_bytes = await response.read()
                    steps[-1]["success"] = True
                    steps[-1]["status"] = f"Generated {len(result_bytes):,} bytes"
                    
                    result["success"] = True
                    result["api_version"] = "v2beta"
                    result["generated_size"] = len(result_bytes)
                    result["steps"] = steps
                    return result
                else:
                    error_text = await response.text()
                    steps[-1]["success"] = False
                    steps[-1]["error"] = error_text[:300]
    
    except Exception as e:
        steps[-1]["success"] = False
        steps[-1]["error"] = str(e)
    
    result["steps"] = steps
    result["success"] = False
    result["error"] = "Both v1 and v2beta APIs failed"
    return result
