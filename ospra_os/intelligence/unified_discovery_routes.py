"""
Product Discovery API Routes
=============================
Exposes the ProductDiscoveryEngine to the dashboard frontend.

10 Data Sources:
- AliExpress (Affiliate + Dropshipping APIs)
- CJ Dropshipping (US/EU warehouses)
- TikTok Shop (via Apify)
- Amazon Bestsellers (via Apify)
- X/Twitter Sentiment (via xAI Grok)
- Reddit Sentiment
- Google Trends
- Claude AI (analysis)
- OpenAI (images) ← NOW INTEGRATED

Endpoints:
- GET /api/discovery/products - Get products for a niche (with optional AI images)
- GET /api/discovery/quick/{niche} - Quick discovery (no sentiment, no images)
- POST /api/discovery/enhance-images - Add AI images to existing products
- GET /api/discovery/niches - List available niches
- GET /api/discovery/sources - Get data source status
- GET /api/discovery/health - Health check
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["Product Discovery"])

# Lazy load to avoid import errors
_engine = None
_image_generator = None


def get_engine():
    global _engine
    if _engine is None:
        from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine
        _engine = ProductDiscoveryEngine()
    return _engine


def get_image_generator():
    """Get AI image generator (lazy load)"""
    global _image_generator
    if _image_generator is None:
        try:
            from ospra_os.integrations.ai_image_generator import get_image_generator as get_gen
            _image_generator = get_gen()
            if _image_generator.openai_available or _image_generator.stability_available:
                logger.info("[SUCCESS] AI Image Generator loaded for discovery")
            else:
                logger.warning("[WARNING] AI Image Generator loaded but no API keys configured")
        except Exception as e:
            logger.warning(f"[WARNING] AI Image Generator not available: {e}")
            _image_generator = None
    return _image_generator


async def enhance_products_with_images(products: List[Dict], max_images: int = 5) -> List[Dict]:
    """
    Add AI-generated images to products.
    
    Only generates images for top products to save API costs (~$0.04/image).
    """
    generator = get_image_generator()
    if not generator:
        logger.warning("No image generator available - returning products without AI images")
        for p in products:
            p['ai_image_url'] = None
            p['image_source'] = 'not_available'
        return products
    
    if not generator.openai_available and not generator.stability_available:
        logger.warning("No AI image API configured (need OPENAI_API_KEY or STABILITY_API_KEY)")
        for p in products:
            p['ai_image_url'] = None
            p['image_source'] = 'no_api_key'
        return products
    
    # Only generate for top N products (by score) to save costs
    sorted_products = sorted(products, key=lambda p: p.get('oi_score', 0), reverse=True)
    products_to_enhance = sorted_products[:max_images]
    
    logger.info(f" Generating AI images for top {len(products_to_enhance)} products...")
    
    enhanced_count = 0
    for product in products_to_enhance:
        try:
            result = await generator.generate_product_image(
                product_title=product.get('title', 'Product'),
                niche=product.get('niche', 'smart_home'),
                original_image_url=product.get('image_url') or product.get('main_image'),
                tags=product.get('tags', [])
            )
            
            if result and result.get('ai_image_url'):
                product['ai_image_url'] = result['ai_image_url']
                product['original_image_url'] = result.get('original_image_url', product.get('image_url'))
                product['image_source'] = result.get('source', 'openai')
                enhanced_count += 1
                logger.info(f"   [SUCCESS] Generated image for: {product.get('title', '')[:40]}...")
            else:
                product['ai_image_url'] = None
                product['image_source'] = 'generation_failed'
                
        except Exception as e:
            logger.warning(f"   [ERROR] Image generation failed for {product.get('title', '')[:30]}: {e}")
            product['ai_image_url'] = None
            product['image_source'] = 'error'
    
    # Mark remaining products as not enhanced
    for product in sorted_products[max_images:]:
        product['ai_image_url'] = None
        product['image_source'] = 'not_in_top_n'
    
    logger.info(f" Image generation complete: {enhanced_count}/{len(products_to_enhance)} successful")
    return products


# ============================================================================
# REQUEST MODELS
# ============================================================================

class EnhanceImagesRequest(BaseModel):
    """Request to enhance products with AI images"""
    products: List[dict]
    max_images: int = 5


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/products")
@router.get("/live-products")
async def get_products(
    niche: str = Query("smart_home", description="Product category"),
    count: int = Query(20, ge=1, le=50, description="Number of products"),
    min_score: float = Query(30.0, ge=0, le=100, description="Minimum OI score"),
    include_sentiment: bool = Query(True, description="Include social sentiment"),
    include_ai_images: bool = Query(False, description="Generate AI images for top products (~$0.04 each)")
):
    """
    Discover products from all available sources.
    
    Returns products with:
    - Real supplier data from AliExpress/CJ
    - Social sentiment from X/Twitter and Reddit
    - Trend validation from Google Trends
    - OI Score calculated from all sources
    - AI-generated images (if include_ai_images=true)
    
    Note: AI images cost ~$0.04 per image via OpenAI DALL-E 3.
    Only top 5 products get AI images by default to control costs.
    """
    try:
        logger.info(f"[SEARCH] Discovery: niche={niche}, count={count}, sentiment={include_sentiment}, ai_images={include_ai_images}")
        
        engine = get_engine()
        products = await engine.discover_products(
            niche=niche,
            max_products=count,
            min_score=min_score,
            include_sentiment=include_sentiment
        )
        
        # Generate AI images if requested
        if include_ai_images and products:
            products = await enhance_products_with_images(products, max_images=5)
        
        return {
            "success": True,
            "niche": niche,
            "count": len(products),
            "products": products,
            "sources_status": engine.sources_status,
            "ai_images_generated": include_ai_images
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Discovery failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick/{niche}")
async def quick_discover(
    niche: str,
    count: int = Query(10, ge=1, le=20),
    include_ai_images: bool = Query(False, description="Generate AI images")
):
    """Quick discovery without sentiment analysis (faster)."""
    try:
        engine = get_engine()
        products = await engine.discover_products(
            niche=niche,
            max_products=count,
            include_sentiment=False
        )
        
        # Generate AI images if requested
        if include_ai_images and products:
            products = await enhance_products_with_images(products, max_images=3)
        
        return {
            "success": True,
            "niche": niche,
            "count": len(products),
            "products": products,
            "ai_images_generated": include_ai_images
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Quick discovery failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enhance-images")
async def enhance_images(request: EnhanceImagesRequest):
    """
    Add AI-generated images to existing products.
    
    Use this to enhance products that were discovered without AI images.
    
    Cost: ~$0.04 per image (OpenAI DALL-E 3)
    
    Example:
    ```json
    {
        "products": [
            {"title": "Smart LED Strip", "niche": "smart_home", "image_url": "..."},
            {"title": "WiFi Plug", "niche": "smart_home", "image_url": "..."}
        ],
        "max_images": 5
    }
    ```
    """
    try:
        generator = get_image_generator()
        
        if not generator:
            return {
                "success": False,
                "error": "AI Image Generator not available",
                "products": request.products
            }
        
        if not generator.openai_available and not generator.stability_available:
            return {
                "success": False,
                "error": "No AI image API configured. Set OPENAI_API_KEY or STABILITY_API_KEY",
                "products": request.products
            }
        
        enhanced = await enhance_products_with_images(
            request.products, 
            max_images=request.max_images
        )
        
        generated_count = sum(1 for p in enhanced if p.get('image_source') in ['openai', 'stability', 'cache'])
        
        return {
            "success": True,
            "products": enhanced,
            "total": len(enhanced),
            "generated": generated_count,
            "estimated_cost": generated_count * 0.04
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Image enhancement failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-niche")
async def get_multi_niche_products(
    niches: str = Query("smart_home,tech,kitchen", description="Comma-separated niches"),
    per_niche: int = Query(5, ge=1, le=20, description="Products per niche")
):
    """Get products across multiple niches."""
    try:
        niche_list = [n.strip() for n in niches.split(',')]
        engine = get_engine()
        results = {}
        
        for niche in niche_list:
            try:
                products = await engine.discover_products(
                    niche=niche,
                    max_products=per_niche,
                    include_sentiment=False
                )
                results[niche] = products
            except Exception as e:
                logger.warning(f"Failed {niche}: {e}")
                results[niche] = []
        
        total = sum(len(p) for p in results.values())
        
        return {
            "success": True,
            "niches": niche_list,
            "total_products": total,
            "results": results,
            "sources_status": engine.sources_status
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Multi-niche failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/niches")
async def list_niches():
    """List all available product niches."""
    try:
        engine = get_engine()
        
        niches = []
        for niche_id, keywords in engine.NICHE_KEYWORDS.items():
            niches.append({
                "id": niche_id,
                "name": ' '.join(w.capitalize() for w in niche_id.split('_')),
                "keywords": keywords[:3],
                "keyword_count": len(keywords)
            })
        
        return {
            "success": True,
            "count": len(niches),
            "niches": niches
        }
        
    except Exception as e:
        logger.error(f"[ERROR] List niches failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def get_sources_status():
    """Get status of all 10 data sources including AI image generation."""
    try:
        engine = get_engine()
        generator = get_image_generator()
        
        connected = sum(1 for s in engine.sources_status.values() if '[SUCCESS]' in s)
        total = len(engine.sources_status)
        
        # Add image generator status
        image_status = {
            "available": generator is not None,
            "openai_configured": getattr(generator, 'openai_available', False) if generator else False,
            "gemini_configured": getattr(generator, 'gemini_available', False) if generator else False,
            "stability_configured": getattr(generator, 'stability_available', False) if generator else False,
            "cached_images": len(generator.cache) if generator and hasattr(generator, 'cache') else 0,
            "active_provider": (
                "openai" if (generator and getattr(generator, 'openai_available', False)) else
                "gemini" if (generator and getattr(generator, 'gemini_available', False)) else
                "stability" if (generator and getattr(generator, 'stability_available', False)) else
                "none"
            )
        }
        
        return {
            "success": True,
            "sources": engine.sources_status,
            "image_generator": image_status,
            "summary": {
                "total": total,
                "connected": connected,
                "disconnected": total - connected,
                "ai_images_available": image_status["openai_configured"] or image_status["gemini_configured"] or image_status["stability_configured"],
                "ai_provider": image_status["active_provider"]
            }
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Sources status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-cj")
async def test_cj_directly(
    keyword: str = Query("smart plug", description="Search keyword"),
    niche: str = Query("smart_home", description="Niche for category search"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Direct CJ Dropshipping test endpoint.
    
    Tests both keyword and category-based searches.
    """
    try:
        from ospra_os.integrations.cj_dropshipping.client import get_cj_client
        
        client = get_cj_client()
        
        if not client.is_available():
            return {
                "success": False,
                "error": "CJ Dropshipping not configured - check CJ_ACCESS_TOKEN",
                "token_present": bool(client.access_token)
            }
        
        results = {
            "keyword_search": [],
            "category_search": [],
            "categories_available": []
        }
        
        # Test keyword search
        logger.info(f"[TEST] CJ keyword search: {keyword}")
        keyword_products = await client.search_products(keyword, page_size=limit)
        results["keyword_search"] = {
            "query": keyword,
            "count": len(keyword_products),
            "products": keyword_products[:3]  # First 3 for preview
        }
        
        # Test category search
        logger.info(f"[TEST] CJ category search: {niche}")
        category_products = await client.search_by_niche(niche, page_size=limit)
        results["category_search"] = {
            "niche": niche,
            "category_id": client.CATEGORY_MAP.get(niche.lower(), "not_mapped"),
            "count": len(category_products),
            "products": category_products[:3]  # First 3 for preview
        }
        
        # List available category mappings
        results["categories_available"] = client.CATEGORY_MAP
        
        # Try to get CJ's actual categories
        try:
            cj_categories = await client.get_categories()
            results["cj_categories_sample"] = cj_categories[:10] if cj_categories else []
        except Exception as e:
            results["cj_categories_sample"] = f"Error: {e}"
        
        return {
            "success": True,
            "results": results,
            "summary": {
                "keyword_found": len(keyword_products),
                "category_found": len(category_products),
                "total_unique": len(keyword_products) + len(category_products)  # May have overlap
            }
        }
        
    except Exception as e:
        logger.error(f"[ERROR] CJ test failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/health")
async def health_check():
    """Health check for discovery engine including AI image capability."""
    try:
        engine = get_engine()
        generator = get_image_generator()
        
        has_suppliers = engine.aliexpress_available or engine.cj_available
        
        # Check AI image providers
        openai_avail = generator and getattr(generator, 'openai_available', False)
        gemini_avail = generator and getattr(generator, 'gemini_available', False)
        stability_avail = generator and getattr(generator, 'stability_available', False)
        has_images = openai_avail or gemini_avail or stability_avail
        
        return {
            "status": "healthy" if has_suppliers else "degraded",
            "sources": engine.sources_status,
            "capabilities": {
                "aliexpress": engine.aliexpress_available,
                "cj_dropshipping": engine.cj_available,
                "tiktok": engine.apify_available and engine.tiktok_scraper is not None,
                "amazon": engine.apify_available and engine.amazon_scraper is not None,
                "x_twitter": engine.xai_available,
                "reddit": engine.reddit_available,
                "google_trends": engine.trends_available,
                "ai_images": has_images,
                "ai_image_provider": (
                    "openai" if openai_avail else
                    "gemini" if gemini_avail else
                    "stability" if stability_avail else
                    "none"
                )
            },
            "niches_available": len(engine.NICHE_KEYWORDS)
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}
