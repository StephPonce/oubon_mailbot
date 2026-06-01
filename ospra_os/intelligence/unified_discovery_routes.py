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

from datetime import datetime
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


def _image_budget_for_tier(tier: TierEnum) -> int:
    """How many top products get a Stability-enhanced image per request.

    Image enhancement is the only per-request cost that scales with
    output size (~$0.06/image, capped). NEST users get a teaser (3),
    Stratosphere users get most of their top results enhanced. The
    cap holds even for cache hits — disk-cache hits are free, but the
    budget gates which products got enhanced when first cached.

    NEST=3, FLIGHT=5, SOAR=8, STRATOSPHERE=12.
    """
    return {
        TierEnum.NEST: 3,
        TierEnum.FLIGHT: 5,
        TierEnum.SOAR: 8,
        TierEnum.STRATOSPHERE: 12,
    }.get(tier, 3)


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
    """Get the Stability-backed AI image enhancer (lazy load).

    The integrations.ai_image_generator module exposes AIImageEnhancer —
    Stability-only, no OpenAI/Gemini fallbacks (per product decision: we
    enhance the supplier's product image, never generate from scratch,
    so we never need a text-to-image model).
    """
    global _image_generator
    if _image_generator is None:
        try:
            from ospra_os.integrations.ai_image_generator import get_image_generator as get_gen
            _image_generator = get_gen()
            if getattr(_image_generator, 'stability_key', ''):
                logger.info("[SUCCESS] AI Image Enhancer (Stability) loaded for discovery")
            else:
                logger.warning("[WARNING] AI Image Enhancer loaded but STABILITY_API_KEY not set")
        except Exception as e:
            logger.warning(f"[WARNING] AI Image Enhancer not available: {e}")
            _image_generator = None
    return _image_generator


def _image_generator_available(generator) -> bool:
    """True iff the Stability-backed enhancer has a usable API key."""
    return bool(generator and getattr(generator, 'stability_key', ''))


async def enhance_products_with_images(products: List[Dict], max_images: int = 5) -> List[Dict]:
    """
    Enhance product images via Stability (background removal + clean replacement).

    Only enhances the top N by OI score to cap Stability spend (~$0.06/image).
    Cached on disk by URL hash so repeat hits are free.

    Output keys mirror the legacy multi-provider flow for frontend compat:
      - ai_image_url       (the enhanced URL — kept for existing UI bindings)
      - enhanced_image_url (alias, more descriptive — what the enhancer returns)
      - original_image_url (the supplier URL we started from)
      - image_source       ('stability' | 'cached' | 'generation_failed' | 'error')
    """
    generator = get_image_generator()
    if not _image_generator_available(generator):
        reason = 'not_available' if not generator else 'no_api_key'
        if reason == 'no_api_key':
            logger.warning("No image API configured (need STABILITY_API_KEY)")
        else:
            logger.warning("Image enhancer not available — returning products as-is")
        for p in products:
            p['ai_image_url'] = None
            p['enhanced_image_url'] = None
            p['image_source'] = reason
        return products

    # Only enhance top N products (by score) to cap Stability spend
    sorted_products = sorted(products, key=lambda p: p.get('oi_score', 0), reverse=True)
    products_to_enhance = sorted_products[:max_images]

    logger.info(f" Enhancing top {len(products_to_enhance)} product images via Stability...")

    enhanced_count = 0
    for product in products_to_enhance:
        original_url = product.get('image_url') or product.get('main_image')
        if not original_url:
            product['ai_image_url'] = None
            product['enhanced_image_url'] = None
            product['image_source'] = 'no_source_image'
            continue
        try:
            result = await generator.enhance_product_image(
                image_url=original_url,
                niche=product.get('niche', 'smart_home'),
            )

            if result and result.get('success') and result.get('enhanced_image_url'):
                enhanced = result['enhanced_image_url']
                product['ai_image_url'] = enhanced            # legacy frontend key
                product['enhanced_image_url'] = enhanced       # canonical key
                product['original_image_url'] = result.get('original_url', original_url)
                # 'cached' when disk-cache hit (cost $0), 'stability' for a fresh API call.
                product['image_source'] = 'cached' if result.get('cached') else 'stability'
                enhanced_count += 1
                logger.info(f"   [SUCCESS] {product['image_source']} image for: {product.get('title', '')[:40]}...")
            else:
                product['ai_image_url'] = None
                product['enhanced_image_url'] = None
                product['image_source'] = 'generation_failed'
                if result and result.get('error'):
                    logger.debug(f"   Image enhance failed: {result['error']}")

        except Exception as e:
            logger.warning(f"   [ERROR] Image enhance failed for {product.get('title', '')[:30]}: {e}")
            product['ai_image_url'] = None
            product['enhanced_image_url'] = None
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
    include_captions: bool = Query(
        True,
        description=(
            "Generate Shopify captions via Claude for top 10 products. "
            "Adds ~6-12s on a cold call (cached on subsequent hits). "
            "Set false for fast internal probes / audit scripts."
        ),
    ),
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
                        products = await enhance_products_with_images(
                            products, max_images=_image_budget_for_tier(user_tier)
                        )

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
                include_captions=include_captions,
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
            products = await enhance_products_with_images(
                products, max_images=_image_budget_for_tier(user_tier)
            )

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
    include_captions: bool = Query(
        True,
        description=(
            "Generate Shopify captions via Claude for top 10 products. "
            "Adds ~6-12s on a cold call (cached on subsequent hits). "
            "Set false for fast internal probes / audit scripts."
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
                        products = await enhance_products_with_images(
                            products, max_images=_image_budget_for_tier(caller_tier)
                        )

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
                include_captions=include_captions,
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
            products = await enhance_products_with_images(
                products, max_images=_image_budget_for_tier(caller_tier)
            )

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
        
        if not _image_generator_available(generator):
            return {
                "success": False,
                "error": "No image API configured. Set STABILITY_API_KEY",
                "products": request.products
            }

        enhanced = await enhance_products_with_images(
            request.products,
            max_images=request.max_images
        )

        # 'stability' = fresh API call (~$0.06), 'cached' = disk-cache hit ($0).
        generated_count = sum(1 for p in enhanced if p.get('image_source') == 'stability')
        cached_count = sum(1 for p in enhanced if p.get('image_source') == 'cached')

        return {
            "success": True,
            "products": enhanced,
            "total": len(enhanced),
            "generated": generated_count,
            "cached": cached_count,
            "estimated_cost": round(generated_count * 0.06, 2),
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Image enhancement failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-niche")
async def get_multi_niche_products(
    niches: str = Query("smart_home,tech,kitchen", description="Comma-separated niches"),
    per_niche: int = Query(5, ge=1, le=20, description="Products per niche"),
    include_sentiment: bool = Query(False, description="Include sentiment enrichment (slower)"),
    include_captions: bool = Query(False, description="Generate captions for top products (slower)"),
):
    """Get products across multiple niches."""
    try:
        niche_list = [n.strip() for n in niches.split(',')]
        engine = get_engine()
        results = {}

        for niche in niche_list:
            try:
                # Defaults to fast mode (no sentiment, no captions) since
                # this endpoint is typically used for batch listing. Callers
                # can opt into enrichment via query params if they need it.
                products = await engine.discover_products(
                    niche=niche,
                    max_products=per_niche,
                    include_sentiment=include_sentiment,
                    include_captions=include_captions,
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
        
        # Image enhancer status — Stability-only by design (we enhance the
        # supplier's product photo, never generate from scratch). Legacy
        # openai_configured / gemini_configured fields are retained as
        # constant False for backwards-compat with any older dashboards
        # that read them; new clients should look at active_provider.
        stability_ok = _image_generator_available(generator)
        image_status = {
            "available": generator is not None,
            "stability_configured": stability_ok,
            "openai_configured": False,   # deprecated — Stability-only now
            "gemini_configured": False,   # deprecated — Stability-only now
            "cached_images": (
                len(getattr(generator, 'cache', {})) if generator else 0
            ),
            "active_provider": "stability" if stability_ok else "none",
        }

        return {
            "success": True,
            "sources": engine.sources_status,
            "image_generator": image_status,
            "summary": {
                "total": total,
                "connected": connected,
                "disconnected": total - connected,
                "ai_images_available": stability_ok,
                "ai_provider": image_status["active_provider"],
            },
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
        # Task #36: surface which layer resolved the niche
        resolved_id = client._get_category_id(niche)
        results["category_search"] = {
            "niche": niche,
            "category_id": resolved_id or "not_mapped",
            "resolved_via": (
                "dynamic" if (
                    client._dynamic_category_map and
                    resolved_id and
                    resolved_id in client._dynamic_category_map.values()
                ) else (
                    "hard_coded" if resolved_id else "none"
                )
            ),
            "count": len(category_products),
            "products": category_products[:3]  # First 3 for preview
        }

        # Hard-coded fallback map (legacy snapshot — still consulted)
        results["categories_available_hardcoded"] = client.CATEGORY_MAP
        # Task #36: dynamic map status (live snapshot from /getCategory)
        results["categories_available_dynamic"] = {
            "loaded": client._dynamic_category_map is not None,
            "entry_count": len(client._dynamic_category_map or {}),
            "loaded_at": client._dynamic_category_loaded_at,
            "sample_keys": list((client._dynamic_category_map or {}).keys())[:20],
        }

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


@router.get("/sources-health")
async def sources_health(
    niche: str = Query("smart_home", description="Niche to test all sources against"),
    timeout_per_source: int = Query(15, ge=5, le=60),
):
    """
    Unified health check — pings every wired discovery source in parallel
    and returns a single dashboard view.

    Useful for "is everything connected right now?" debugging without
    visiting 7 separate test endpoints. Each source returns one of:
      - status='ok'         (live data returned)
      - status='no_data'    (connected, returned empty)
      - status='not_configured' (missing env var / token)
      - status='error'      (raised exception)

    Failures of any one source do not affect the others — each runs
    independently with its own timeout.
    """
    import asyncio

    # Each entry: (label, async_callable_returning_health_dict)
    async def _check_meta_ads():
        try:
            from ospra_os.product_research.connectors.apify.meta_ads_library import (
                get_meta_ads_library,
            )
            client = get_meta_ads_library()
            if not client.is_available():
                return {"status": "not_configured", "detail": "APIFY_API_TOKEN missing"}
            # max_ads=20 (not 5): the Apify actor errors when the search
            # window is too small for some keywords (e.g. "smart home"),
            # returning a single {"error": ...} envelope that we cannot
            # parse. 20 is the same window the manual /test-meta-ads probe
            # uses successfully.
            r = await client.search_active_ads(niche.replace("_", " "), max_ads=20)
            return {
                "status": "ok" if r.get("available") else "no_data",
                "ad_count": r.get("ad_count", 0),
                "winners": len(r.get("winners") or []),
                "error": r.get("error"),
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def _check_amazon_movers():
        try:
            from ospra_os.product_research.connectors.amazon_movers_rss import (
                get_amazon_movers_rss,
            )
            scraper = get_amazon_movers_rss()
            r = await scraper.fetch(niche, feed_type="movers", max_items=5)
            return {
                "status": "ok" if r.get("available") else "no_data",
                "item_count": r.get("item_count", 0),
                "cached": r.get("cached", False),
                "error": r.get("error"),
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def _check_amazon_new_releases():
        try:
            from ospra_os.product_research.connectors.amazon_movers_rss import (
                get_amazon_movers_rss,
            )
            scraper = get_amazon_movers_rss()
            r = await scraper.fetch(niche, feed_type="new_releases", max_items=5)
            return {
                "status": "ok" if r.get("available") else "no_data",
                "item_count": r.get("item_count", 0),
                "error": r.get("error"),
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def _check_etsy():
        try:
            from ospra_os.product_research.connectors.apify.etsy_trending import (
                get_etsy_trending,
            )
            scraper = get_etsy_trending()
            if not scraper.is_available():
                return {"status": "not_configured", "detail": "APIFY_API_TOKEN missing"}
            r = await scraper.fetch_trending(niche, max_items=5)
            if r.get("error") == "no_etsy_category_for_niche":
                return {"status": "skipped", "detail": f"no Etsy mapping for '{niche}'"}
            return {
                "status": "ok" if r.get("available") else "no_data",
                "item_count": r.get("item_count", 0),
                "error": r.get("error"),
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def _check_tiktok_shop():
        try:
            from ospra_os.product_research.connectors.apify import TikTokShopScraper
            scraper = TikTokShopScraper()
            apify_ok = scraper.is_available()
            partner_ok = bool(
                os.getenv("TIKTOK_SHOP_APP_KEY") and os.getenv("TIKTOK_SHOP_ACCESS_TOKEN")
            )
            return {
                "status": "ok" if apify_ok else "not_configured",
                "apify_scraper": apify_ok,
                "partner_api_credentials": partner_ok,
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def _check_ae_ds():
        try:
            from ospra_os.aliexpress.ds_client import get_ds_client
            client = get_ds_client()
            return {
                "status": "ok" if client.is_available() else "not_configured",
                "detail": (
                    "AE Dropshipping token + app key configured"
                    if client.is_available()
                    else "Need ALIEXPRESS_APP_KEY/SECRET + dropship OAuth token"
                ),
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def _check_cj():
        try:
            from ospra_os.integrations.cj_dropshipping.client import get_cj_client
            client = get_cj_client()
            cat_loaded = client._dynamic_category_map is None  # not yet loaded vs loaded
            return {
                "status": "ok" if client.is_available() else "not_configured",
                "dynamic_categories_loaded": not cat_loaded,
                "hardcoded_fallback_count": len(client.CATEGORY_MAP),
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    sources = {
        "meta_ads_library":      _check_meta_ads(),
        "amazon_movers_rss":     _check_amazon_movers(),
        "amazon_new_releases":   _check_amazon_new_releases(),
        "etsy_trending":         _check_etsy(),
        "tiktok_shop":           _check_tiktok_shop(),
        "aliexpress_ds_api":     _check_ae_ds(),
        "cj_dropshipping":       _check_cj(),
    }

    # Run all checks in parallel with a per-source timeout
    async def _with_timeout(coro):
        try:
            return await asyncio.wait_for(coro, timeout=timeout_per_source)
        except asyncio.TimeoutError:
            return {"status": "timeout", "detail": f"exceeded {timeout_per_source}s"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    keys = list(sources.keys())
    results = await asyncio.gather(*[_with_timeout(c) for c in sources.values()])
    health = dict(zip(keys, results))

    # Summary line for at-a-glance
    counts = {"ok": 0, "no_data": 0, "skipped": 0, "not_configured": 0, "error": 0, "timeout": 0}
    for r in results:
        counts[r.get("status", "error")] = counts.get(r.get("status", "error"), 0) + 1

    return {
        "success": True,
        "niche": niche,
        "summary": counts,
        "total_sources": len(sources),
        "sources": health,
    }


@router.get("/test-amazon-new-releases")
async def test_amazon_new_releases(
    niche: str = Query("smart_home"),
    max_items: int = Query(10, ge=1, le=50),
):
    """
    Option A smoke-test: Amazon New Releases RSS for a niche.
    Public feed, no auth required.
    """
    try:
        from ospra_os.product_research.connectors.amazon_movers_rss import (
            get_amazon_movers_rss,
        )
        scraper = get_amazon_movers_rss()
        payload = await scraper.fetch(niche, feed_type="new_releases", max_items=max_items)
        keywords = scraper.extract_keywords(payload, top_n=10) if payload.get("available") else []
        return {
            "success": payload.get("available", False),
            "niche": niche,
            "category": payload.get("category"),
            "feed_type": "new_releases",
            "item_count": payload.get("item_count", 0),
            "cached": payload.get("cached", False),
            "items_sample": (payload.get("items") or [])[:5],
            "extracted_keywords": keywords,
            "error": payload.get("error"),
        }
    except Exception as e:
        logger.error(f"[ERROR] Amazon New Releases test failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/test-etsy-trending")
async def test_etsy_trending(
    niche: str = Query("home_decor"),
    max_items: int = Query(10, ge=1, le=50),
):
    """
    Option B smoke-test: Etsy trending products via Apify.
    Returns 'no_etsy_category_for_niche' for niches without a mapping.
    """
    try:
        from ospra_os.product_research.connectors.apify.etsy_trending import (
            get_etsy_trending,
        )
        scraper = get_etsy_trending()
        if not scraper.is_available():
            return {
                "success": False,
                "error": "APIFY_API_TOKEN not configured",
            }
        payload = await scraper.fetch_trending(niche, max_items=max_items)
        keywords = scraper.extract_keywords(payload, top_n=10) if payload.get("available") else []
        return {
            "success": payload.get("available", False),
            "niche": niche,
            "category": payload.get("category"),
            "item_count": payload.get("item_count", 0),
            "items_sample": (payload.get("items") or [])[:5],
            "extracted_keywords": keywords,
            "error": payload.get("error"),
        }
    except Exception as e:
        logger.error(f"[ERROR] Etsy trending test failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/test-tiktok-shop")
async def test_tiktok_shop(
    niche: str = Query("smart_home", description="Niche to query"),
    keyword: str = Query("", description="Optional explicit keyword override"),
    max_items: int = Query(10, ge=1, le=50),
):
    """
    Task #11: smoke-test the TikTok Shop integrations.

    Exercises two layers:
      1. The Apify TikTok scraper (`tiktok_scraper.discover_products`)
         which works without TikTok Shop Partner credentials. This is
         the discovery-relevant path.
      2. The Partner API connector (`tiktok_shop_connector.get_trending`)
         which only runs when TIKTOK_SHOP_APP_KEY + TIKTOK_SHOP_ACCESS_TOKEN
         are configured. Gracefully reports "not configured" otherwise.

    Returns a side-by-side comparison so operators can see which path is
    contributing data and which needs OAuth setup.
    """
    result = {
        "success": True,
        "niche": niche,
        "keyword": keyword or niche.replace("_", " "),
        "apify_scraper": {"available": False, "products": [], "error": None},
        "partner_api": {"available": False, "products": [], "error": None},
    }

    # Layer 1 — Apify scraper (always available if APIFY_API_TOKEN set)
    try:
        from ospra_os.product_research.connectors.apify import TikTokShopScraper
        scraper = TikTokShopScraper()
        if scraper.is_available():
            products = await scraper.discover_products(
                niche=niche,
                max_products=max_items,
                keyword=keyword or None,
            )
            result["apify_scraper"] = {
                "available": True,
                "product_count": len(products or []),
                "products_sample": (products or [])[:5],
            }
        else:
            result["apify_scraper"]["error"] = "APIFY_API_TOKEN not configured"
    except Exception as e:
        result["apify_scraper"]["error"] = str(e)

    # Layer 2 — Partner API (requires per-seller OAuth credentials)
    try:
        if os.getenv("TIKTOK_SHOP_APP_KEY") and os.getenv("TIKTOK_SHOP_ACCESS_TOKEN"):
            from ospra_os.product_research.connectors.tiktok_shop import (
                TikTokShopConnector,
            )
            connector = TikTokShopConnector()
            candidates = await connector.get_trending(category=None, limit=max_items)
            result["partner_api"] = {
                "available": True,
                "product_count": len(candidates or []),
                "products_sample": [
                    {
                        "name": getattr(c, "name", None),
                        "price": getattr(c, "price", None),
                        "trend_score": getattr(c, "trend_score", None),
                        "url": getattr(c, "url", None),
                    }
                    for c in (candidates or [])[:5]
                ],
            }
        else:
            result["partner_api"]["error"] = (
                "TIKTOK_SHOP_APP_KEY / TIKTOK_SHOP_ACCESS_TOKEN not configured — "
                "apply at partner.tiktokshop.com to enable this layer"
            )
    except Exception as e:
        result["partner_api"]["error"] = str(e)

    return result


@router.get("/test-amazon-movers")
async def test_amazon_movers(
    niche: str = Query("smart_home", description="Ospra niche or raw Amazon category slug"),
    max_items: int = Query(10, ge=1, le=50),
):
    """
    Task #12: smoke-test the Amazon Movers & Shakers RSS connector.

    Public feed, no auth required. Returns the top movers (products
    with biggest 24h rank gains) in the niche's Amazon category, the
    extracted trending keywords, and the cache status.
    """
    try:
        from ospra_os.product_research.connectors.amazon_movers_rss import (
            get_amazon_movers_rss,
        )
        scraper = get_amazon_movers_rss()
        payload = await scraper.fetch(niche, max_items=max_items)
        keywords = scraper.extract_keywords(payload, top_n=10) if payload.get("available") else []
        return {
            "success": payload.get("available", False),
            "niche": niche,
            "category": payload.get("category"),
            "item_count": payload.get("item_count", 0),
            "cached": payload.get("cached", False),
            "items_sample": (payload.get("items") or [])[:5],
            "extracted_keywords": keywords,
            "error": payload.get("error"),
        }
    except Exception as e:
        logger.error(f"[ERROR] Amazon Movers test failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/test-meta-ads")
async def test_meta_ads(
    keyword: str = Query("smart plug", description="Ad Library search term"),
    country: str = Query("US", description="ISO alpha-2 country code"),
    max_ads: int = Query(20, ge=1, le=100),
    active_only: bool = Query(True),
):
    """
    Task #10: smoke-test the Meta Ad Library connector.

    Returns:
      - availability status (APIFY_API_TOKEN present?)
      - the connector's full payload: raw ads, aggregated advertisers,
        and the subset that pass the "proven winner" heuristic
        (≥14 days active × ≥3 creative variants × Shopify landing URL)
      - a manual_url the operator can paste in a browser to cross-check
    """
    try:
        from ospra_os.product_research.connectors.apify.meta_ads_library import (
            get_meta_ads_library,
        )
        client = get_meta_ads_library()
        if not client.is_available():
            return {
                "success": False,
                "available": False,
                "error": "APIFY_API_TOKEN not configured",
            }
        result = await client.search_active_ads(
            keyword=keyword,
            country=country,
            max_ads=max_ads,
            active_only=active_only,
        )
        # Trim ads down for the test response — full payload is huge
        if result.get("ads"):
            result["ads_sample"] = result["ads"][:5]
            result["ads_truncated"] = max(0, len(result["ads"]) - 5)
            del result["ads"]
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"[ERROR] Meta Ad Library test failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/test-ae-ds")
async def test_ae_ds(
    product_id: str = Query("", description="AE product_id to fetch detail for"),
    feed_name: str = Query("DS_Global_topsellers", description="DS feed name"),
    feed_page_size: int = Query(5, ge=1, le=20),
):
    """
    Task #24: smoke-test the AE Dropshipping Solution client.

    Returns:
      - availability status (token + app key)
      - a sample of the configured DS feed
      - detailed merchant pricing for `product_id` (if provided)
    """
    try:
        from ospra_os.aliexpress.ds_client import get_ds_client
        client = get_ds_client()

        out = {
            "success": True,
            "available": client.is_available(),
            "feed_name": feed_name,
        }
        if not client.is_available():
            out["error"] = (
                "AE DS API not configured — need ALIEXPRESS_APP_KEY/SECRET "
                "and a non-expired dropship token (api_type='dropship')."
            )
            return out

        # Sample the configured feed so the operator can see live data
        feed_products = await client.get_hot_products(
            feed_name=feed_name,
            page_size=feed_page_size,
        )
        out["feed_sample_count"] = len(feed_products)
        out["feed_sample"] = feed_products[:feed_page_size]

        # If a product_id is provided, fetch its merchant pricing detail
        if product_id:
            detail = await client.get_product_details(product_id)
            out["product_detail"] = detail or {"error": "no detail returned"}
            out["product_id"] = product_id
        return out
    except Exception as e:
        logger.error(f"[ERROR] AE DS test failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("/refresh-cj-categories")
async def refresh_cj_categories(
    force: bool = Query(False, description="Refresh even if cache is fresh"),
):
    """
    Task #36: pull CJ's live category tree from /product/getCategory,
    flatten it to a name→id index, and persist it to the on-disk cache
    used by `CJDropshippingClient._get_category_id`.

    By default this is a no-op if the cache is younger than 7 days;
    pass `force=true` to bypass the TTL.
    """
    try:
        from ospra_os.integrations.cj_dropshipping.client import get_cj_client

        client = get_cj_client()
        if not client.is_available():
            return {
                "success": False,
                "error": "CJ Dropshipping not configured - check CJ_ACCESS_TOKEN",
            }

        before = len(client._dynamic_category_map or {})
        mapping = await client.refresh_category_map(force=force)
        return {
            "success": True,
            "forced": force,
            "entry_count": len(mapping),
            "entries_added": max(0, len(mapping) - before),
            "loaded_at": client._dynamic_category_loaded_at,
            "sample_keys": list(mapping.keys())[:25],
        }
    except Exception as e:
        logger.error(f"[ERROR] CJ category refresh failed: {e}")
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

                # Fetch and cache — warm admin path, skip slow enrichers.
                # Real user calls hitting these niches will fan-out
                # sentiment + captions on top of the cached supplier data.
                products = await engine.discover_products(
                    niche=niche,
                    max_products=50,
                    include_sentiment=False,
                    include_captions=False,
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
        has_images = _image_generator_available(generator)

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
                "ai_image_provider": "stability" if has_images else "none",
            },
            "niches_available": len(engine.NICHE_KEYWORDS),
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


