"""
Image Enhancement Routes - WITH CACHING
========================================
Enhance product images with caching to avoid duplicate API costs.

Endpoints:
- GET  /api/images/status - Check if enhancement is available
- POST /api/images/enhance - Enhance a single image (with cache)
- POST /api/images/enhance/batch - Enhance multiple images (with cache)
- GET  /api/images/cached/{product_id} - Get cached enhanced images for product
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import logging
import json

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User
from ospra_os.database.connection import get_db
from sqlalchemy.orm import Session
from ospra_os.integrations.ai_image_generator import (
    get_image_enhancer,
    enhance_product_image,
    enhance_product_batch,
    BACKGROUND_STYLES,
    NICHE_BACKGROUNDS,
    check_enhanced_image_exists,
    get_enhanced_image_url
)

# Import cache models
try:
    from ospra_os.database.enhanced_image_cache import EnhancedImageCache, ProductEnhancedImages
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    EnhancedImageCache = None
    ProductEnhancedImages = None

logger = logging.getLogger(__name__)


# ============================================================================
# CACHE HELPERS
# ============================================================================

def get_cached_enhanced_image(db: Session, original_url: str) -> Optional[str]:
    """Check if we have a cached enhanced version of this image."""
    if not CACHE_AVAILABLE or not db:
        return None
    try:
        url_hash = EnhancedImageCache.hash_url(original_url)
        cached = db.query(EnhancedImageCache).filter(
            EnhancedImageCache.original_url_hash == url_hash
        ).first()
        if cached:
            logger.info(f"[CACHE HIT] Found cached enhanced image for {original_url[:50]}...")
            return cached.enhanced_url
    except Exception as e:
        logger.warning(f"[CACHE] Error checking cache: {e}")
    return None


def save_enhanced_image_to_cache(
    db: Session,
    original_url: str,
    enhanced_url: str,
    product_id: Optional[str] = None,
    niche: Optional[str] = None
):
    """Save enhanced image to cache (both URL-level and product-level)."""
    if not CACHE_AVAILABLE or not db:
        return
    try:
        url_hash = EnhancedImageCache.hash_url(original_url)

        # Check if already cached (shouldn't happen but safety)
        existing = db.query(EnhancedImageCache).filter(
            EnhancedImageCache.original_url_hash == url_hash
        ).first()
        if existing:
            return

        # Create new cache entry
        cache_entry = EnhancedImageCache(
            original_url_hash=url_hash,
            original_url=original_url,
            enhanced_url=enhanced_url,
            product_id=product_id,
            niche=niche,
            enhancement_type="background_removal"
        )
        db.add(cache_entry)
        db.commit()
        logger.info(f"[CACHE] Saved enhanced image to cache: {original_url[:50]}...")

        # ALSO update product-level cache for fast product_id lookups
        if product_id:
            update_product_enhanced_images(
                db=db,
                product_id=product_id,
                enhanced_urls=[enhanced_url],
                original_urls=[original_url]
            )
    except Exception as e:
        logger.warning(f"[CACHE] Error saving to cache: {e}")
        db.rollback()


def update_product_enhanced_images(
    db: Session,
    product_id: str,
    enhanced_urls: List[str],
    original_urls: List[str]
):
    """Update or create product enhanced images record."""
    if not CACHE_AVAILABLE or not db or not product_id:
        return
    try:
        # Find or create product record
        product_cache = db.query(ProductEnhancedImages).filter(
            ProductEnhancedImages.product_id == product_id
        ).first()

        if product_cache:
            # Update existing
            existing_enhanced = product_cache.get_enhanced_urls()
            existing_original = product_cache.get_original_urls()
            # Merge new URLs with existing
            all_enhanced = list(set(existing_enhanced + enhanced_urls))
            all_original = list(set(existing_original + original_urls))
            product_cache.set_enhanced_urls(all_enhanced)
            product_cache.set_original_urls(all_original)
            cost = float(product_cache.total_cost_usd or 0) + (len(enhanced_urls) * 0.06)
            product_cache.total_cost_usd = f"{cost:.2f}"
        else:
            # Create new
            product_cache = ProductEnhancedImages(
                product_id=product_id,
                total_cost_usd=f"{len(enhanced_urls) * 0.06:.2f}"
            )
            product_cache.set_enhanced_urls(enhanced_urls)
            product_cache.set_original_urls(original_urls)
            db.add(product_cache)

        db.commit()
        logger.info(f"[CACHE] Updated product {product_id} with {len(enhanced_urls)} enhanced images")
    except Exception as e:
        logger.warning(f"[CACHE] Error updating product cache: {e}")
        db.rollback()

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
    product_id: Optional[str] = Field(default=None, description="Product ID for caching")
    skip_cache: bool = Field(default=False, description="Force re-enhancement (ignore cache)")


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
async def enhance_image(
    request: EnhanceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enhance a single product image WITH FILE-BASED CACHING.

    Removes the ugly supplier background and adds a clean,
    professional background matching Oubon Shop aesthetic.

    **File-Based Caching:** Enhanced images are saved to disk.
    If this image was enhanced before, returns cached file URL instantly (FREE).

    **How it works:**
    1. Check disk for existing enhanced image file
    2. If not cached: Download, enhance via Stability AI, save to disk
    3. Returns persistent file URL (NOT base64)

    **Cost:** ~$0.06 per image (FREE if cached on disk)
    **Time:** ~3-5 seconds (instant if cached)
    """
    logger.info(f"[ENHANCE] Request for: {request.image_url[:50]}...")
    logger.info(f"[ENHANCE] Niche: {request.niche}, Background: {request.background_style or 'auto'}")

    # The enhance_product_image function now handles file-based caching internally
    # It checks disk first, and saves to disk after processing
    result = await enhance_product_image(
        image_url=request.image_url,
        niche=request.niche,
        background_style=request.background_style,
        skip_cache=request.skip_cache
    )

    if not result["success"]:
        logger.error(f"[ENHANCE] Failed: {result.get('error')}")
    else:
        logger.info(f"[ENHANCE] Success! Background used: {result.get('background_style')}, cached: {result.get('cached', False)}")

        # Also save to database cache for product-level lookups
        enhanced_url = result.get("enhanced_image_url")
        if enhanced_url and not result.get("cached"):
            save_enhanced_image_to_cache(
                db=db,
                original_url=request.image_url,
                enhanced_url=enhanced_url,
                product_id=request.product_id,
                niche=request.niche
            )
            result["cost"] = "~$0.06"
        elif result.get("cached"):
            result["cost"] = "$0.00"

    return result


@router.post("/enhance/batch")
async def enhance_batch(
    request: BatchEnhanceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enhance multiple product images in parallel WITH CACHING.

    **Caching:** Already-enhanced images are returned from cache instantly (FREE).

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

    **Cost:** ~$0.06 per NEW image (cached images are FREE)
    **Recommendation:** Keep batch size under 10 for reasonable response times
    """
    if not request.images:
        raise HTTPException(status_code=400, detail="No images provided")

    if len(request.images) > 20:
        raise HTTPException(
            status_code=400,
            detail="Batch size limited to 20 images. Split into multiple requests."
        )

    logger.info(f"[BATCH] Processing {len(request.images)} images (checking cache first)...")

    # Separate cached vs needs-enhancement
    cached_results = []
    needs_enhancement = []

    for img in request.images:
        url = img.get("url") or img.get("image_url")
        if not url:
            continue

        cached_url = get_cached_enhanced_image(db, url)
        if cached_url:
            cached_results.append({
                "success": True,
                "enhanced_image_url": cached_url,
                "original_url": url,
                "id": img.get("id"),
                "title": img.get("title"),
                "cached": True
            })
        else:
            needs_enhancement.append(img)

    logger.info(f"[BATCH] {len(cached_results)} cached, {len(needs_enhancement)} need enhancement")

    # Enhance only non-cached images
    new_results = []
    if needs_enhancement:
        new_results = await enhance_product_batch(
            images=needs_enhancement,
            niche=request.niche
        )

        # Cache successful enhancements
        product_enhanced_urls = []
        product_original_urls = []
        product_id = None

        for img, result in zip(needs_enhancement, new_results):
            if result.get("success") and result.get("enhanced_image_url"):
                url = img.get("url") or img.get("image_url")
                save_enhanced_image_to_cache(
                    db=db,
                    original_url=url,
                    enhanced_url=result["enhanced_image_url"],
                    product_id=img.get("id"),
                    niche=request.niche
                )
                result["cached"] = False

                # Collect for product-level cache
                product_enhanced_urls.append(result["enhanced_image_url"])
                product_original_urls.append(url)
                if img.get("id"):
                    product_id = img.get("id").split("_img_")[0]  # Extract base product ID

        # Update product-level cache if we have a product ID
        if product_id and product_enhanced_urls:
            update_product_enhanced_images(
                db=db,
                product_id=product_id,
                enhanced_urls=product_enhanced_urls,
                original_urls=product_original_urls
            )

    # Combine results
    all_results = cached_results + new_results

    # Summary stats
    successful = sum(1 for r in all_results if r.get("success"))
    failed = len(all_results) - successful
    from_cache = sum(1 for r in all_results if r.get("cached"))
    new_enhanced = successful - from_cache

    return {
        "total": len(all_results),
        "successful": successful,
        "failed": failed,
        "from_cache": from_cache,
        "newly_enhanced": new_enhanced,
        "estimated_cost": f"${new_enhanced * 0.06:.2f}",
        "results": all_results
    }


@router.get("/cached/{product_id}")
async def get_cached_images(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all cached enhanced images for a product.

    Returns the product's enhanced images if they exist in cache.
    Use this to check if a product has already been enhanced.
    """
    if not CACHE_AVAILABLE:
        return {"success": False, "error": "Image caching not available"}

    try:
        product_cache = db.query(ProductEnhancedImages).filter(
            ProductEnhancedImages.product_id == product_id
        ).first()

        if not product_cache:
            return {
                "success": True,
                "cached": False,
                "product_id": product_id,
                "enhanced_urls": [],
                "message": "No cached images for this product"
            }

        return {
            "success": True,
            "cached": True,
            "product_id": product_id,
            "primary_enhanced_url": product_cache.primary_enhanced_url,
            "enhanced_urls": product_cache.get_enhanced_urls(),
            "original_urls": product_cache.get_original_urls(),
            "image_count": product_cache.image_count,
            "total_cost": product_cache.total_cost_usd
        }
    except Exception as e:
        logger.error(f"[CACHE] Error retrieving cached images: {e}")
        return {"success": False, "error": str(e)}


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


@router.post("/check-cache")
async def check_image_cache(
    image_urls: List[str] = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    """
    Check if images are already cached on disk.

    Returns a mapping of original URLs to their cached enhanced URLs.
    Use this to avoid unnecessary API calls by pre-checking cache status.

    **Request:**
    ```json
    {"image_urls": ["https://...", "https://..."]}
    ```

    **Response:**
    ```json
    {
        "cached": {"https://original1.jpg": "/static/images/enhanced/abc123.png"},
        "not_cached": ["https://original2.jpg"],
        "total": 2,
        "cached_count": 1
    }
    ```
    """
    from ospra_os.integrations.ai_image_generator import get_enhanced_images_dir, get_image_url_hash

    cached = {}
    not_cached = []

    # Debug: log the enhanced images directory
    enhanced_dir = get_enhanced_images_dir()
    logger.info(f"[CACHE-CHECK] Enhanced images dir: {enhanced_dir}, exists: {enhanced_dir.exists()}")
    if enhanced_dir.exists():
        existing_files = list(enhanced_dir.glob("*.png"))
        logger.info(f"[CACHE-CHECK] Found {len(existing_files)} cached files on disk")

    for url in image_urls:
        cached_url = check_enhanced_image_exists(url)
        if cached_url:
            cached[url] = cached_url
            logger.info(f"[CACHE-CHECK] ✅ HIT: {url[:60]}... -> {cached_url}")
        else:
            not_cached.append(url)
            # Debug: show what hash we were looking for
            url_hash = get_image_url_hash(url)
            logger.info(f"[CACHE-CHECK] ❌ MISS: {url[:60]}... (looking for {url_hash}.png)")

    logger.info(f"[CACHE-CHECK] Result: {len(cached)} cached, {len(not_cached)} not cached out of {len(image_urls)} total")

    return {
        "cached": cached,
        "not_cached": not_cached,
        "total": len(image_urls),
        "cached_count": len(cached)
    }


@router.get("/cache-status")
async def get_cache_status(current_user: User = Depends(get_current_user)):
    """
    Get status of the image cache - shows how many images are cached on disk.
    Use this to verify caching is working.
    """
    from ospra_os.integrations.ai_image_generator import get_enhanced_images_dir

    enhanced_dir = get_enhanced_images_dir()
    cached_files = list(enhanced_dir.glob("*.png")) if enhanced_dir.exists() else []

    return {
        "cache_directory": str(enhanced_dir),
        "directory_exists": enhanced_dir.exists(),
        "cached_images_count": len(cached_files),
        "cached_hashes": [f.stem for f in cached_files[:20]],  # First 20 hashes
        "total_size_mb": round(sum(f.stat().st_size for f in cached_files) / (1024*1024), 2) if cached_files else 0
    }


@router.post("/cache-index")
async def index_cache_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Index all cached files on disk into the database.

    This is a repair utility - if files exist on disk but aren't in the DB,
    this will create EnhancedImageCache entries for them so lookups work.

    Note: Since we don't have the original URLs for existing files,
    we store the hash as a placeholder in original_url field.
    """
    from ospra_os.integrations.ai_image_generator import get_enhanced_images_dir

    if not CACHE_AVAILABLE:
        return {"success": False, "error": "Cache not available"}

    enhanced_dir = get_enhanced_images_dir()
    if not enhanced_dir.exists():
        return {"success": False, "error": "Cache directory doesn't exist"}

    cached_files = list(enhanced_dir.glob("*.png"))
    indexed = 0
    skipped = 0
    errors = []

    for file_path in cached_files:
        try:
            file_hash = file_path.stem  # Get filename without extension
            enhanced_url = f"/static/images/enhanced/{file_hash}.png"

            # Check if already in DB (by hash)
            existing = db.query(EnhancedImageCache).filter(
                EnhancedImageCache.original_url_hash == file_hash
            ).first()

            if existing:
                skipped += 1
                continue

            # Create new entry - use hash as placeholder URL since we don't know original
            cache_entry = EnhancedImageCache(
                original_url_hash=file_hash,
                original_url=f"legacy_cached:{file_hash}",  # Placeholder
                enhanced_url=enhanced_url,
                product_id=None,  # Unknown
                niche=None,
                enhancement_type="background_removal"
            )
            db.add(cache_entry)
            indexed += 1

        except Exception as e:
            errors.append(f"{file_path.name}: {str(e)}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"Database commit failed: {e}"}

    logger.info(f"[CACHE-INDEX] Indexed {indexed} files, skipped {skipped} existing, {len(errors)} errors")

    return {
        "success": True,
        "total_files": len(cached_files),
        "indexed": indexed,
        "skipped": skipped,
        "errors": errors[:10] if errors else []
    }


@router.get("/cache-lookup-test/{url_hash}")
async def test_cache_lookup(
    url_hash: str,
    current_user: User = Depends(get_current_user)
):
    """
    Debug endpoint: Test if a specific hash exists in cache.

    Check both file system and database for a given hash.
    """
    from ospra_os.integrations.ai_image_generator import get_enhanced_images_dir

    enhanced_dir = get_enhanced_images_dir()
    file_path = enhanced_dir / f"{url_hash}.png"
    file_exists = file_path.exists()

    result = {
        "hash": url_hash,
        "file_exists": file_exists,
        "file_path": str(file_path) if file_exists else None,
        "file_size_kb": round(file_path.stat().st_size / 1024, 2) if file_exists else None,
        "url": f"/static/images/enhanced/{url_hash}.png" if file_exists else None
    }

    return result


@router.post("/debug-url-hash")
async def debug_url_hash(
    url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    """
    Debug endpoint: Show how a URL gets hashed and what files would be checked.

    Use this to diagnose cache misses.
    """
    from ospra_os.integrations.ai_image_generator import (
        get_enhanced_images_dir, get_image_url_hash, get_legacy_hash,
        normalize_image_url, check_enhanced_image_exists
    )

    enhanced_dir = get_enhanced_images_dir()

    # Normalized URL and hash
    normalized_url = normalize_image_url(url)
    normalized_hash = get_image_url_hash(url)  # Uses normalize internally
    normalized_path = enhanced_dir / f"{normalized_hash}.png"

    # Legacy hash (no normalization)
    legacy_hash = get_legacy_hash(url)
    legacy_path = enhanced_dir / f"{legacy_hash}.png"

    # Check what check_enhanced_image_exists returns
    cache_result = check_enhanced_image_exists(url)

    return {
        "original_url": url[:100] + "..." if len(url) > 100 else url,
        "normalized_url": normalized_url[:100] + "..." if len(normalized_url) > 100 else normalized_url,
        "url_was_normalized": url != normalized_url,
        "normalized_hash": normalized_hash,
        "normalized_file_exists": normalized_path.exists(),
        "legacy_hash": legacy_hash,
        "legacy_file_exists": legacy_path.exists(),
        "cache_lookup_result": cache_result,
        "diagnosis": (
            "✅ Found via normalized hash" if normalized_path.exists() else
            "✅ Found via legacy hash" if legacy_path.exists() else
            f"❌ No file found. Looking for: {normalized_hash}.png or {legacy_hash}.png"
        )
    }


@router.get("/list-cached-files")
async def list_cached_files(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """
    List all cached image files on disk.

    Returns hashes and URLs for cached files, useful for debugging.
    """
    from ospra_os.integrations.ai_image_generator import get_enhanced_images_dir

    enhanced_dir = get_enhanced_images_dir()
    if not enhanced_dir.exists():
        return {"success": False, "error": "Cache directory doesn't exist", "files": []}

    cached_files = sorted(enhanced_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)

    files = []
    for f in cached_files[:limit]:
        files.append({
            "hash": f.stem,
            "url": f"/static/images/enhanced/{f.stem}.png",
            "size_kb": round(f.stat().st_size / 1024, 2),
            "created": f.stat().st_mtime
        })

    return {
        "success": True,
        "total_files": len(cached_files),
        "showing": min(limit, len(cached_files)),
        "files": files
    }


@router.post("/smart-cache-recovery")
async def smart_cache_recovery(
    image_urls: List[str] = Body(..., embed=True),
    product_id: str = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Smart cache recovery: Try to match provided image URLs to existing cached files.

    This checks ALL possible hash variants (normalized, legacy, with/without params)
    and if a match is found, updates the database entries.

    Use this when you have products with images that might have been enhanced before
    but the cache lookup is failing due to URL changes.
    """
    from ospra_os.integrations.ai_image_generator import (
        get_enhanced_images_dir, get_image_url_hash, get_legacy_hash,
        normalize_image_url
    )
    import hashlib

    if not CACHE_AVAILABLE:
        return {"success": False, "error": "Cache not available"}

    enhanced_dir = get_enhanced_images_dir()
    existing_hashes = {f.stem for f in enhanced_dir.glob("*.png")}

    matches = []
    no_match = []

    for url in image_urls:
        matched = False
        matched_hash = None

        # Try different hash variants
        hash_variants = [
            get_image_url_hash(url),  # Normalized
            get_legacy_hash(url),      # Legacy (no normalization)
        ]

        # Also try without any query params
        base_url = url.split('?')[0]
        hash_variants.append(hashlib.sha256(base_url.encode()).hexdigest()[:16])

        # Try normalized base URL
        normalized_base = normalize_image_url(base_url)
        hash_variants.append(hashlib.sha256(normalized_base.encode()).hexdigest()[:16])

        for h in hash_variants:
            if h in existing_hashes:
                matched = True
                matched_hash = h
                break

        if matched and matched_hash:
            enhanced_url = f"/static/images/enhanced/{matched_hash}.png"
            matches.append({
                "original_url": url[:80] + "..." if len(url) > 80 else url,
                "matched_hash": matched_hash,
                "enhanced_url": enhanced_url
            })

            # Update/create DB entry
            try:
                url_hash = get_image_url_hash(url)
                existing = db.query(EnhancedImageCache).filter(
                    EnhancedImageCache.original_url_hash == url_hash
                ).first()

                if not existing:
                    # Create new entry with actual URL
                    cache_entry = EnhancedImageCache(
                        original_url_hash=url_hash,
                        original_url=url,
                        enhanced_url=enhanced_url,
                        product_id=product_id,
                        enhancement_type="background_removal"
                    )
                    db.add(cache_entry)
            except Exception as e:
                logger.warning(f"[CACHE-RECOVERY] Failed to update DB for {url[:50]}: {e}")
        else:
            no_match.append(url[:80] + "..." if len(url) > 80 else url)

    # Update ProductEnhancedImages if we have matches and a product_id
    if matches and product_id:
        try:
            enhanced_urls = [m["enhanced_url"] for m in matches]
            original_urls = image_urls[:len(matches)]
            update_product_enhanced_images(db, product_id, enhanced_urls, original_urls)
        except Exception as e:
            logger.warning(f"[CACHE-RECOVERY] Failed to update product cache: {e}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"[CACHE-RECOVERY] DB commit failed: {e}")

    return {
        "success": True,
        "total_urls": len(image_urls),
        "matches_found": len(matches),
        "no_match": len(no_match),
        "matches": matches,
        "unmatched_urls": no_match[:10]  # First 10 unmatched
    }


# ============================================================================
# LEGACY ENDPOINT REDIRECTS (for backwards compatibility)
# ============================================================================

@router.post("/generate")
async def legacy_generate(
    request: EnhanceRequest,
    current_user: User = Depends(get_current_user)
):
    """
    DEPRECATED: Use /enhance instead.
    This redirects to the new enhance endpoint for backwards compatibility.
    """
    return await enhance_image(request, current_user)


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
