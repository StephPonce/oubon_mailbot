"""
SMART CACHE API ROUTES
======================

Endpoints for managing and monitoring the smart sentiment cache.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from ospra_os.intelligence.smart_sentiment_cache import (
    get_sentiment_cache,
    get_cached_or_fetch_sentiment
)

router = APIRouter(prefix="/api/cache", tags=["Smart Cache"])


class RefreshRequest(BaseModel):
    product_id: str
    current_velocity: Optional[float] = None
    current_sales_velocity: Optional[float] = None
    manual: bool = False
    sources: Optional[List[str]] = None


@router.get("/sentiment/stats")
async def get_cache_stats():
    """
    Get sentiment cache statistics.
    
    Returns:
    - Hit/miss counts
    - Hit rate percentage
    - Number of cached products
    - Estimated cache size
    """
    cache = get_sentiment_cache()
    stats = cache.get_stats()
    
    return {
        "success": True,
        "stats": stats
    }


@router.get("/sentiment/{product_id}")
async def get_cached_sentiment(product_id: str):
    """
    Get cached sentiment for a product (if available).
    
    Returns cached data or null if not in cache.
    """
    cache = get_sentiment_cache()
    cached = cache.get(product_id)
    
    if cached:
        return {
            "success": True,
            "cached": True,
            "data": cached.to_dict()
        }
    else:
        return {
            "success": True,
            "cached": False,
            "data": None
        }


@router.post("/sentiment/should-refresh")
async def check_should_refresh(request: RefreshRequest):
    """
    Check if sentiment cache should be refreshed for a product.
    
    Takes into account:
    - Cache expiry
    - Velocity changes
    - Sales changes
    - Manual refresh cooldown
    """
    cache = get_sentiment_cache()
    
    should_refresh, reason = cache.should_refresh(
        product_id=request.product_id,
        current_velocity=request.current_velocity,
        current_sales_velocity=request.current_sales_velocity,
        manual=request.manual,
        sources=request.sources
    )
    
    return {
        "success": True,
        "should_refresh": should_refresh,
        "reason": reason.value
    }


@router.delete("/sentiment/{product_id}")
async def invalidate_cached_sentiment(product_id: str):
    """
    Invalidate (delete) cached sentiment for a product.
    """
    cache = get_sentiment_cache()
    cache.invalidate(product_id)
    
    return {
        "success": True,
        "message": f"Cache invalidated for {product_id}"
    }


@router.delete("/sentiment")
async def clear_all_cache():
    """
    Clear the entire sentiment cache.
    
    [WARNING] Use with caution - forces re-fetch of all sentiment data.
    """
    cache = get_sentiment_cache()
    cache.invalidate_all()
    
    return {
        "success": True,
        "message": "All sentiment cache cleared"
    }


@router.get("/sentiment/all")
async def get_all_cached():
    """
    Get all cached items (for debugging).
    
    Returns list of all cached sentiments with metadata.
    """
    cache = get_sentiment_cache()
    items = cache.get_all_cached()
    
    return {
        "success": True,
        "count": len(items),
        "items": items
    }
