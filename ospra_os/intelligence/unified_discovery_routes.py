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
- GET /api/discovery/quick/{niche} - Quick discovery (sentiment ON by default, WITH CACHING)
- POST /api/discovery/enhance-images - Add AI images to existing products
- GET /api/discovery/niches - List available niches
- GET /api/discovery/sources - Get data source status
- GET /api/discovery/health - Health check

PERFORMANCE OPTIMIZATIONS:
- Tier-based caching (4h for NEST, 2h for FLIGHT, 30m for SOAR, 5m for STRATOSPHERE)
- Parallel data source queries
- Instant cache hits for repeat requests
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import os
import time

from ospra_os.auth.dependencies import get_current_user
from ospra_os.auth.jwt_handler import TokenPayload
from ospra_os.core.tiers import (
    SubscriptionTier as TierEnum,
    clamp_request_count,
    get_products_per_request_ceiling,
)

logger = logging.getLogger(__name__)


def _tier_from_payload(user: Optional[TokenPayload]) -> TierEnum:
    """Map a JWT payload to the canonical SubscriptionTier enum.

    Unauthenticated callers get NEST (the free-tier ceiling still applies to
    public/anonymous traffic so an unauth'd user can't stampede the API).
    """
    if user is None or not user.tier:
        return TierEnum.NEST
    try:
        return TierEnum(user.tier.lower())
    except ValueError:
        return TierEnum.NEST


def _cache_tier_from_core(tier: TierEnum):
    """Map ospra_os.core.tiers.SubscriptionTier → product_cache.SubscriptionTier.

    The cache module duplicates the enum to avoid pulling in SQLAlchemy at
    import time, so we cannot use core's enum directly as the cache key. Both
    enums share string values ("nest"/"flight"/"soar"/"stratosphere") so this
    mapping is total and stable.

    Why this matters — the cache is keyed by (niche, tier). If we keep passing
    SubscriptionTier.NEST regardless of the caller, NEST-shaped responses
    (clamped to 10 products, slow TTL) get served back to Stratosphere users
    forever. Per-tier keys also let TIER_CACHE_TTL do its job — NEST holds for
    4h, Stratosphere refreshes every 5min.
    """
    if not CACHE_AVAILABLE:
        return None
    try:
        return SubscriptionTier(tier.value)
    except (ValueError, AttributeError):
        return SubscriptionTier.NEST

# When True, empty discovery responses fall back to hardcoded demo products.
# Default: False. Production MUST NOT silently return fake products — users need
# honest errors so they can see which data sources are failing and fix them.
# Set ALLOW_DEMO_FALLBACK=1 only in local dev with no API keys configured.
ALLOW_DEMO_FALLBACK = os.getenv("ALLOW_DEMO_FALLBACK", "0").lower() in ("1", "true", "yes")


def _is_demo_products(products: List[Dict]) -> bool:
    """True if any product is flagged is_mock — prevents caching/returning demo data."""
    if not products:
        return False
    return any(p.get("is_mock") or p.get("is_demo") for p in products)


def _source_diagnostics(engine) -> Dict:
    """Snapshot of which data sources are live, for error responses."""
    try:
        sources = engine.sources_status if hasattr(engine, "sources_status") else {}
        connected = {k: v for k, v in sources.items() if "[SUCCESS]" in str(v)}
        failed = {k: v for k, v in sources.items() if "[SUCCESS]" not in str(v)}
        return {
            "sources_connected": list(connected.keys()),
            "sources_failed": failed,
            "total_connected": len(connected),
            "total_sources": len(sources),
        }
    except Exception as e:
        return {"diagnostics_error": str(e)}

# Import caching infrastructure
try:
    from ospra_os.product_research.product_cache import (
        get_product_cache,
        get_products_with_cache,
        TIER_CACHE_TTL,
        SubscriptionTier  # Import from cache module to avoid SQLAlchemy dependency
    )
    CACHE_AVAILABLE = True
    logger.info("[SUCCESS] Product cache module loaded for discovery routes")
except ImportError as e:
    CACHE_AVAILABLE = False
    logger.warning(f"[WARNING] Product cache not available: {e}")

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
    count: int = Query(20, ge=1, le=100, description="Number of products (tier-capped)"),
    min_score: float = Query(30.0, ge=0, le=100, description="Minimum OI score"),
    include_sentiment: bool = Query(True, description="Include social sentiment"),
    include_ai_images: bool = Query(False, description="Generate AI images for top products (~$0.04 each)"),
    force_refresh: bool = Query(False, description="Bypass cache and fetch fresh data"),
    current_user: Optional[TokenPayload] = Depends(get_current_user),
):
    """
    Discover products from all available sources WITH CACHING.

    Returns products with:
    - Real supplier data from AliExpress/CJ
    - Social sentiment from X/Twitter and Reddit
    - Trend validation from Google Trends
    - OI Score calculated from all sources
    - AI-generated images (if include_ai_images=true)

    CACHING: Results are cached for 4 hours (NEST tier) to provide instant loads.
    Use force_refresh=true to bypass cache.

    RELIABILITY: Always returns products (uses demo data as ultimate fallback)
    """
    start_time = time.time()
    products: List[Dict] = []
    discovery_error_msg: Optional[str] = None

    # ==== TIER-BASED COUNT CLAMPING ====
    # Free-tier traffic (including anonymous) can't request 100 products at once.
    # The weekly quota is still enforced by tier_enforcement middleware; this is
    # the per-call ceiling on top of that. See ospra_os/core/tiers.py.
    user_tier = _tier_from_payload(current_user)
    original_count = count
    count, was_clamped = clamp_request_count(count, user_tier)
    tier_ceiling = get_products_per_request_ceiling(user_tier)
    if was_clamped:
        logger.info(
            f"[TIER CLAMP] user_tier={user_tier.value} requested={original_count} "
            f"ceiling={tier_ceiling} effective={count}"
        )

    try:
        engine = get_engine()

        # ==== CACHING LAYER ====
        if CACHE_AVAILABLE and not force_refresh and not include_sentiment:
            cache = get_product_cache()
            # Per-tier cache key — see _cache_tier_from_core docstring for why
            # we don't hardcode NEST here.
            tier = _cache_tier_from_core(user_tier)

            cached_entry = cache.get(niche, tier)
            if cached_entry and cached_entry.products and len(cached_entry.products) > 0:
                if _is_demo_products(cached_entry.products):
                    logger.warning(
                        f"[CACHE POISONED] /products?niche={niche} - cache contains demo products, invalidating"
                    )
                    cache.invalidate(niche, tier)
                else:
                    products = [
                        p for p in cached_entry.products if p.get("oi_score", 0) >= min_score
                    ][:count]
                    elapsed = time.time() - start_time

                    logger.info(
                        f"[CACHE HIT] /products?niche={niche} - {len(products)} real products in {elapsed:.3f}s"
                    )

                    if include_ai_images and products:
                        products = await enhance_products_with_images(products, max_images=5)

                    return {
                        "success": True,
                        "niche": niche,
                        "count": len(products),
                        "products": products,
                        "sources_status": engine.sources_status,
                        "ai_images_generated": include_ai_images,
                        "from_cache": True,
                        "cache_age_seconds": cached_entry.age_seconds,
                        "response_time_ms": int(elapsed * 1000),
                        "tier_meta": {
                            "tier": user_tier.value,
                            "per_request_ceiling": tier_ceiling,
                            "requested": original_count,
                            "clamped": was_clamped,
                        },
                    }
            elif cached_entry:
                logger.warning(f"[CACHE EMPTY] /products?niche={niche} - invalidating empty cache")
                cache.invalidate(niche, tier)

        # ==== FRESH DISCOVERY ====
        logger.info(f"[SEARCH] Discovery: niche={niche}, count={count}, sentiment={include_sentiment}")
        fetch_count = max(50, count * 2)

        try:
            products = await engine.discover_products(
                niche=niche,
                max_products=fetch_count,
                min_score=min_score,
                include_sentiment=include_sentiment,
            )
        except Exception as discovery_error:
            logger.error(f"[ERROR] Discovery engine failed: {discovery_error}", exc_info=True)
            discovery_error_msg = str(discovery_error)
            products = []

        # Strip any demo/mock products the engine may have included.
        if products:
            real_products = [p for p in products if not (p.get("is_mock") or p.get("is_demo"))]
            if len(real_products) != len(products):
                logger.warning(
                    f"[DEMO FILTERED] /products?niche={niche} - dropped "
                    f"{len(products) - len(real_products)} demo products"
                )
            products = real_products

        # ==== NO REAL PRODUCTS ====
        if not products:
            diagnostics = _source_diagnostics(engine)

            if ALLOW_DEMO_FALLBACK:
                logger.warning(
                    f"[DEV FALLBACK] /products?niche={niche} - no real products, using demos "
                    f"(ALLOW_DEMO_FALLBACK=1)"
                )
                demo_products = engine._get_demo_products(niche, count)
                elapsed = time.time() - start_time
                return {
                    "success": True,
                    "niche": niche,
                    "count": len(demo_products),
                    "products": demo_products,
                    "sources_status": engine.sources_status,
                    "ai_images_generated": False,
                    "from_cache": False,
                    "is_fallback": True,
                    "warning": "Demo products returned — no real sources produced results.",
                    "discovery_error": discovery_error_msg,
                    "diagnostics": diagnostics,
                    "response_time_ms": int(elapsed * 1000),
                }

            logger.error(
                f"[DISCOVERY FAILED] /products?niche={niche} - no real products available. "
                f"error={discovery_error_msg} diagnostics={diagnostics}"
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "No real products available from any data source",
                    "niche": niche,
                    "discovery_error": discovery_error_msg,
                    "diagnostics": diagnostics,
                    "hint": (
                        "Check /api/discovery/health for source status. "
                        "Common causes: expired/missing API keys, upstream rate limits, "
                        "or temporary provider outage."
                    ),
                },
            )

        # ==== CACHE REAL RESULTS ====
        if CACHE_AVAILABLE and not include_sentiment and not _is_demo_products(products):
            cache = get_product_cache()
            # Same per-tier key as the read above — keeps NEST and Stratosphere
            # entries separate so neither contaminates the other.
            tier = _cache_tier_from_core(user_tier)
            cache.set(
                niche=niche,
                tier=tier,
                products=products,
                metadata={
                    "source": "full_discovery",
                    "include_sentiment": include_sentiment,
                    "is_demo": False,
                },
            )
            logger.info(
                f"[CACHE SET] /products?niche={niche} tier={tier.value} - "
                f"{len(products)} real products cached"
            )

        products = products[:count]

        if include_ai_images and products:
            products = await enhance_products_with_images(products, max_images=5)

        elapsed = time.time() - start_time

        return {
            "success": True,
            "niche": niche,
            "count": len(products),
            "products": products,
            "sources_status": engine.sources_status,
            "ai_images_generated": include_ai_images,
            "from_cache": False,
            "response_time_ms": int(elapsed * 1000),
            "tier_meta": {
                "tier": user_tier.value,
                "per_request_ceiling": tier_ceiling,
                "requested": original_count,
                "clamped": was_clamped,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Discovery failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Unexpected discovery failure",
                "niche": niche,
                "message": str(e),
            },
        )


@router.get("/quick/{niche}")
async def quick_discover(
    niche: str,
    count: int = Query(10, ge=1, le=100),
    include_ai_images: bool = Query(False, description="Generate AI images"),
    include_sentiment: bool = Query(
        True,
        description=(
            "Enrich products with X/Twitter + Reddit sentiment. "
            "Adds up to ~6s (per-source timeout) but powers sentiment_score and "
            "lights up the x_twitter / reddit source badges in the UI. "
            "Safely no-ops if xAI or Reddit aren't configured."
        ),
    ),
    force_refresh: bool = Query(False, description="Bypass cache and fetch fresh data"),
    current_user: Optional[TokenPayload] = Depends(get_current_user),
):
    """
    Quick discovery with caching.

    Honesty contract:
    - Never silently returns demo/mock products.
    - Only real products from live data sources are returned.
    - If all sources fail, returns 503 with diagnostics so the caller knows why.
    - Demo fallback is only enabled when the operator sets ALLOW_DEMO_FALLBACK=1
      (for local dev without API keys); the response then carries is_fallback=True
      so the frontend can display a clear banner.

    Tier clamp:
    - `count` is clamped to the caller's per-request ceiling from
      ospra_os.core.tiers.get_products_per_request_ceiling(tier). Anonymous
      traffic defaults to NEST. When clamped, the response carries
      tier_meta.clamped=True so the UI can nudge the user to upgrade.
    """
    start_time = time.time()
    products = []
    discovery_error_msg: Optional[str] = None

    # ==== TIER CLAMP ====
    caller_tier = _tier_from_payload(current_user)
    requested_count = count
    effective_count, was_clamped = clamp_request_count(requested_count, caller_tier)
    count = effective_count
    tier_meta = {
        "tier": caller_tier.value,
        "per_request_ceiling": get_products_per_request_ceiling(caller_tier),
        "requested": requested_count,
        "clamped": was_clamped,
    }

    try:
        engine = get_engine()

        # ==== CACHING LAYER ====
        # Only serve cache if the cached entry contains REAL products (no demos).
        # Cache key includes tier — see _cache_tier_from_core. Without this, a
        # NEST request that fetched only 10 products poisons the niche-wide
        # cache and Stratosphere users get 10 stale items forever.
        if CACHE_AVAILABLE and not force_refresh:
            cache = get_product_cache()
            tier = _cache_tier_from_core(caller_tier)

            cached_entry = cache.get(niche, tier)
            if cached_entry and cached_entry.products and len(cached_entry.products) > 0:
                if _is_demo_products(cached_entry.products):
                    logger.warning(
                        f"[CACHE POISONED] /quick/{niche} - cache contains demo products, invalidating"
                    )
                    cache.invalidate(niche, tier)
                # If caller wants sentiment but the cached entry was NOT enriched with
                # sentiment, invalidate — otherwise we'd silently serve flat OI scores.
                elif include_sentiment and not cached_entry.metadata.get("include_sentiment", False):
                    logger.info(
                        f"[CACHE STALE] /quick/{niche} - cached entry lacks sentiment "
                        f"enrichment but caller requested it, refetching"
                    )
                    cache.invalidate(niche, tier)
                else:
                    products = cached_entry.products[:count]
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[CACHE HIT] /quick/{niche} - {len(products)} real products in {elapsed:.3f}s"
                    )

                    if include_ai_images and products:
                        products = await enhance_products_with_images(products, max_images=3)

                    return {
                        "success": True,
                        "niche": niche,
                        "count": len(products),
                        "products": products,
                        "ai_images_generated": include_ai_images,
                        "sentiment_included": cached_entry.metadata.get("include_sentiment", False),
                        "from_cache": True,
                        "cache_age_seconds": cached_entry.age_seconds,
                        "cache_ttl_remaining": cached_entry.ttl_remaining_seconds,
                        "response_time_ms": int(elapsed * 1000),
                        "tier_meta": tier_meta,
                    }
            elif cached_entry:
                logger.warning(f"[CACHE EMPTY] /quick/{niche} - invalidating empty cache entry")
                cache.invalidate(niche, tier)

        # ==== FRESH DISCOVERY ====
        logger.info(f"[DISCOVERY] /quick/{niche} - fetching fresh products...")
        fetch_count = max(50, count * 3)

        try:
            products = await engine.discover_products(
                niche=niche,
                max_products=fetch_count,
                include_sentiment=include_sentiment,
            )
        except Exception as discovery_error:
            logger.error(f"[ERROR] Discovery engine failed: {discovery_error}", exc_info=True)
            discovery_error_msg = str(discovery_error)
            products = []

        # Filter out any demo/mock products that upstream sources marked — never return them silently.
        if products:
            real_products = [p for p in products if not (p.get("is_mock") or p.get("is_demo"))]
            if len(real_products) != len(products):
                logger.warning(
                    f"[DEMO FILTERED] /quick/{niche} - dropped {len(products) - len(real_products)} "
                    f"demo products from discovery result"
                )
            products = real_products

        # ==== NO REAL PRODUCTS PATH ====
        if not products:
            diagnostics = _source_diagnostics(engine)

            if ALLOW_DEMO_FALLBACK:
                logger.warning(
                    f"[DEV FALLBACK] /quick/{niche} - no real products, using demos "
                    f"(ALLOW_DEMO_FALLBACK=1)"
                )
                demo_products = engine._get_demo_products(niche, count)
                elapsed = time.time() - start_time
                return {
                    "success": True,
                    "niche": niche,
                    "count": len(demo_products),
                    "products": demo_products,
                    "ai_images_generated": False,
                    "from_cache": False,
                    "is_fallback": True,
                    "warning": "Demo products returned — no real sources produced results.",
                    "discovery_error": discovery_error_msg,
                    "diagnostics": diagnostics,
                    "response_time_ms": int(elapsed * 1000),
                    "tier_meta": tier_meta,
                }

            # Production path: be honest about failure
            logger.error(
                f"[DISCOVERY FAILED] /quick/{niche} - no real products available. "
                f"error={discovery_error_msg} diagnostics={diagnostics}"
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "No real products available from any data source",
                    "niche": niche,
                    "discovery_error": discovery_error_msg,
                    "diagnostics": diagnostics,
                    "hint": (
                        "Check /api/discovery/health for source status. "
                        "Common causes: expired/missing API keys, upstream rate limits, "
                        "or temporary provider outage. Set ALLOW_DEMO_FALLBACK=1 in .env "
                        "for local dev without API keys."
                    ),
                },
            )

        # ==== CACHE REAL RESULTS ====
        if CACHE_AVAILABLE and not _is_demo_products(products):
            cache = get_product_cache()
            tier = _cache_tier_from_core(caller_tier)
            cache_entry = cache.set(
                niche=niche,
                tier=tier,
                products=products,
                metadata={
                    "source": "quick_discovery",
                    "fetched_count": len(products),
                    "requested_count": count,
                    "is_demo": False,
                    "include_sentiment": include_sentiment,
                },
            )
            logger.info(
                f"[CACHE SET] /quick/{niche} tier={tier.value} - "
                f"{len(products)} real products (sentiment={include_sentiment}), "
                f"TTL: {cache_entry.ttl_remaining_seconds}s"
            )

        products = products[:count]

        if include_ai_images and products:
            products = await enhance_products_with_images(products, max_images=3)

        elapsed = time.time() - start_time
        logger.info(
            f"[DISCOVERY] /quick/{niche} - completed with {len(products)} real products "
            f"(sentiment={include_sentiment}) in {elapsed:.2f}s"
        )

        return {
            "success": True,
            "niche": niche,
            "count": len(products),
            "products": products,
            "ai_images_generated": include_ai_images,
            "sentiment_included": include_sentiment,
            "from_cache": False,
            "cache_age_seconds": 0,
            "cache_ttl_remaining": (
                TIER_CACHE_TTL.get(_cache_tier_from_core(caller_tier), 240) * 60
                if CACHE_AVAILABLE
                else 0
            ),
            "response_time_ms": int(elapsed * 1000),
            "tier_meta": tier_meta,
        }

    except HTTPException:
        # Let our own 503 pass through cleanly.
        raise
    except Exception as e:
        logger.error(f"[ERROR] Quick discovery failed completely: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Unexpected discovery failure",
                "niche": niche,
                "message": str(e),
            },
        )


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


@router.get("/cache/status")
async def get_cache_status():
    """
    Get product cache statistics.

    Shows cache hit/miss rates, entries by tier, and TTL configuration.
    """
    try:
        if not CACHE_AVAILABLE:
            return {
                "success": False,
                "error": "Product cache not available",
                "cache_available": False
            }

        cache = get_product_cache()
        stats = cache.get_stats()

        return {
            "success": True,
            "cache_available": True,
            "stats": stats
        }

    except Exception as e:
        logger.error(f"[ERROR] Cache status failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("/cache/warm")
async def warm_cache(
    niches: str = Query("smart_home,tech,kitchen", description="Comma-separated niches to warm")
):
    """
    Pre-warm cache with popular niches for instant loads.

    This fetches products for specified niches and caches them.
    Useful to run on server startup or periodically.
    """
    try:
        if not CACHE_AVAILABLE:
            return {"success": False, "error": "Cache not available"}

        niche_list = [n.strip() for n in niches.split(',')]
        engine = get_engine()
        cache = get_product_cache()
        tier = SubscriptionTier.NEST

        results = {}
        for niche in niche_list:
            start = time.time()
            try:
                # Check if already cached
                existing = cache.get(niche, tier)
                if existing:
                    results[niche] = {
                        "status": "already_cached",
                        "products": len(existing.products),
                        "ttl_remaining": existing.ttl_remaining_seconds
                    }
                    continue

                # Fetch and cache
                products = await engine.discover_products(
                    niche=niche,
                    max_products=50,
                    include_sentiment=False
                )

                if products:
                    cache.set(niche, tier, products, {"source": "cache_warm"})
                    results[niche] = {
                        "status": "cached",
                        "products": len(products),
                        "time_seconds": round(time.time() - start, 2)
                    }
                else:
                    results[niche] = {"status": "no_products", "products": 0}

            except Exception as e:
                results[niche] = {"status": "error", "error": str(e)}

        return {
            "success": True,
            "warmed_niches": results,
            "cache_stats": cache.get_stats()
        }

    except Exception as e:
        logger.error(f"[ERROR] Cache warm failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache/clear")
async def clear_cache(
    niche: str = Query(None, description="Clear specific niche or all if not provided")
):
    """Clear product cache (specific niche or all)."""
    try:
        if not CACHE_AVAILABLE:
            return {"success": False, "error": "Cache not available"}

        cache = get_product_cache()

        if niche:
            cache.invalidate(niche)
            return {"success": True, "cleared": niche}
        else:
            cache.invalidate_all()
            return {"success": True, "cleared": "all"}

    except Exception as e:
        logger.error(f"[ERROR] Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
