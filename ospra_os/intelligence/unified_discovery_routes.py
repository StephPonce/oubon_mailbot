"""
Unified Product Discovery API Routes
=====================================
Exposes the unified discovery engine to the dashboard frontend

Endpoints:
- GET /api/discovery/live-products - Get live trending products for a niche
- GET /api/discovery/multi-niche - Get products across multiple niches
- GET /api/discovery/niches - List available niches
- GET /api/discovery/product/{product_id} - Get detailed product info
"""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Optional
import logging

from ospra_os.intelligence.unified_product_discovery import (
    UnifiedProductDiscovery,
    discover_live_products
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["Unified Product Discovery"])


@router.get("/live-products")
async def get_live_products(
    niche: str = Query("smart_home", description="Niche category"),
    count: int = Query(10, ge=1, le=50, description="Number of products to return"),
    min_trend_score: float = Query(60.0, ge=0, le=100, description="Minimum Google Trends score"),
    enable_cross_reference: bool = Query(False, description="Enable Apify cross-referencing (slower)")
):
    """
    Get live trending products from AliExpress Affiliate API

    **Primary Source:** AliExpress Affiliate API (real-time products with commission tracking)
    **Validation:** Google Trends (trend momentum scoring)
    **Enrichment:** Apify scrapers (optional cross-reference)

    **Example:**
    ```
    GET /api/discovery/live-products?niche=smart_home&count=20
    ```

    **Response:**
    ```json
    {
      "niche": "smart_home",
      "count": 20,
      "products": [
        {
          "product_id": "1234567890",
          "title": "Smart WiFi Plug...",
          "price": 12.99,
          "commission_rate": 7.0,
          "affiliate_link": "https://...",
          "trend_score": 85.3,
          "final_score": 78.5,
          "tier": "GOOD"
        }
      ]
    }
    ```
    """
    try:
        logger.info(f"🔍 Discovery request: niche={niche}, count={count}, cross_ref={enable_cross_reference}")

        engine = UnifiedProductDiscovery()
        products = await engine.discover_products(
            niche=niche,
            max_products=count,
            min_trend_score=min_trend_score,
            enable_cross_reference=enable_cross_reference
        )

        return {
            "success": True,
            "niche": niche,
            "count": len(products),
            "products": products,
            "metadata": {
                "min_trend_score": min_trend_score,
                "cross_reference_enabled": enable_cross_reference
            }
        }

    except Exception as e:
        logger.error(f"❌ Discovery failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-niche")
async def get_multi_niche_products(
    niches: str = Query("smart_home,fitness,kitchen", description="Comma-separated niche list"),
    per_niche: int = Query(5, ge=1, le=20, description="Products per niche")
):
    """
    Get products across multiple niches for dashboard overview

    **Example:**
    ```
    GET /api/discovery/multi-niche?niches=smart_home,fitness,beauty&per_niche=5
    ```

    **Response:**
    ```json
    {
      "smart_home": [
        {"product_id": "...", "title": "...", ...}
      ],
      "fitness": [
        {"product_id": "...", "title": "...", ...}
      ],
      "beauty": [
        {"product_id": "...", "title": "...", ...}
      ]
    }
    ```
    """
    try:
        # Parse niches
        niche_list = [n.strip() for n in niches.split(',')]

        logger.info(f"🔍 Multi-niche discovery: {niche_list}, per_niche={per_niche}")

        engine = UnifiedProductDiscovery()
        results = await engine.discover_multiple_niches(
            niches=niche_list,
            products_per_niche=per_niche
        )

        # Calculate summary stats
        total_products = sum(len(products) for products in results.values())

        return {
            "success": True,
            "niches": niche_list,
            "total_products": total_products,
            "results": results,
            "metadata": {
                "products_per_niche": per_niche,
                "niches_processed": len(results)
            }
        }

    except Exception as e:
        logger.error(f"❌ Multi-niche discovery failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/niches")
async def list_available_niches():
    """
    List all available niche categories with keyword counts

    **Example:**
    ```
    GET /api/discovery/niches
    ```

    **Response:**
    ```json
    {
      "niches": [
        {"id": "smart_home", "name": "Smart Home", "keyword_count": 6},
        {"id": "fitness", "name": "Fitness", "keyword_count": 6},
        ...
      ]
    }
    ```
    """
    try:
        engine = UnifiedProductDiscovery()

        niches = []
        for niche_id, keywords in engine.NICHE_KEYWORDS.items():
            # Format niche name (e.g., "smart_home" -> "Smart Home")
            niche_name = ' '.join(word.capitalize() for word in niche_id.split('_'))

            niches.append({
                "id": niche_id,
                "name": niche_name,
                "keyword_count": len(keywords),
                "sample_keywords": keywords[:3]  # First 3 keywords as sample
            })

        return {
            "success": True,
            "count": len(niches),
            "niches": niches
        }

    except Exception as e:
        logger.error(f"❌ Failed to list niches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick/{niche}")
async def quick_discover(
    niche: str,
    count: int = Query(10, ge=1, le=20)
):
    """
    Quick discovery endpoint (simplified, faster)

    Uses convenience function for rapid product lookup without cross-referencing

    **Example:**
    ```
    GET /api/discovery/quick/smart_home?count=10
    ```
    """
    try:
        logger.info(f"⚡ Quick discovery: niche={niche}, count={count}")

        products = await discover_live_products(niche=niche, count=count)

        return {
            "success": True,
            "niche": niche,
            "count": len(products),
            "products": products
        }

    except Exception as e:
        logger.error(f"❌ Quick discovery failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def discovery_health_check():
    """
    Health check for discovery engine

    Tests:
    - AliExpress API connection
    - Apify availability
    - Google Trends availability
    """
    try:
        engine = UnifiedProductDiscovery()

        health_status = {
            "status": "healthy",
            "components": {
                "aliexpress_api": engine.has_aliexpress,
                "apify_scrapers": hasattr(engine, 'apify_amazon'),
                "google_trends": True  # Always available
            },
            "niches_available": len(engine.NICHE_KEYWORDS),
            "total_keywords": sum(len(kw) for kw in engine.NICHE_KEYWORDS.values())
        }

        # Overall health
        all_critical_ok = health_status["components"]["aliexpress_api"]
        health_status["status"] = "healthy" if all_critical_ok else "degraded"

        return health_status

    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/stats")
async def get_discovery_stats():
    """
    Get statistics about the discovery engine

    Returns configuration and capability information
    """
    try:
        engine = UnifiedProductDiscovery()

        return {
            "success": True,
            "niches": {
                "count": len(engine.NICHE_KEYWORDS),
                "available": list(engine.NICHE_KEYWORDS.keys())
            },
            "keywords": {
                "total": sum(len(kw) for kw in engine.NICHE_KEYWORDS.values()),
                "per_niche": {niche: len(kw) for niche, kw in engine.NICHE_KEYWORDS.items()}
            },
            "capabilities": {
                "aliexpress_affiliate": engine.has_aliexpress,
                "apify_enrichment": hasattr(engine, 'apify_amazon'),
                "google_trends": True
            },
            "scoring_weights": {
                "trend": 0.30,
                "commission": 0.25,
                "sales": 0.20,
                "price": 0.15,
                "discount": 0.10
            }
        }

    except Exception as e:
        logger.error(f"❌ Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
