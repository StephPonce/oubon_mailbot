"""
Ospra Intelligence - Image Processing API Routes

AI-powered product image transformation endpoints.

Endpoints:
- POST /api/images/remove-background - Remove background from product image
- POST /api/images/generate-background - Generate AI lifestyle background
- POST /api/images/enhance-product - Complete transformation pipeline
- POST /api/images/batch-enhance - Batch process multiple products
- GET /api/images/style-presets - Get available niche style presets
"""

import time
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, HttpUrl

from ospra_os.services.image_processor import ProductImageProcessor, NICHE_STYLE_PRESETS

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(
    prefix="/api/images",
    tags=["Image Processing"]
)

# Initialize processor (singleton)
processor = ProductImageProcessor()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RemoveBackgroundRequest(BaseModel):
    """Request to remove background from an image."""
    image_url: HttpUrl = Field(..., description="URL of the product image")


class RemoveBackgroundResponse(BaseModel):
    """Response with background-removed image."""
    success: bool
    image_base64: Optional[str] = None
    error: Optional[str] = None
    processing_time_ms: int


class GenerateBackgroundRequest(BaseModel):
    """Request to generate AI lifestyle background."""
    product_name: str = Field(..., description="Name of the product", min_length=1, max_length=200)
    niche: str = Field(default="smart_home", description="Product niche/category")
    custom_prompt: Optional[str] = Field(None, description="Custom DALL-E prompt (overrides niche)")


class GenerateBackgroundResponse(BaseModel):
    """Response with generated background."""
    success: bool
    image_base64: Optional[str] = None
    image_url: Optional[str] = None  # DALL-E temporary URL
    cost_estimate: float
    processing_time_ms: int
    error: Optional[str] = None


class EnhanceProductRequest(BaseModel):
    """Request to enhance product image with full pipeline."""
    image_url: HttpUrl = Field(..., description="URL of the original product image")
    product_name: str = Field(..., description="Name of the product", min_length=1, max_length=200)
    niche: str = Field(default="smart_home", description="Product niche/category")
    add_branding: bool = Field(default=True, description="Add watermark/logo")
    position: str = Field(default="center", description="Product placement: center, left, right")
    scale: float = Field(default=0.6, ge=0.1, le=1.0, description="Product size relative to background")
    save_to_disk: bool = Field(default=True, description="Save result to disk")


class EnhanceProductResponse(BaseModel):
    """Response with enhanced product image."""
    success: bool
    original_url: str
    enhanced_base64: Optional[str] = None
    enhanced_url: Optional[str] = None  # If uploaded to storage
    image_path: Optional[str] = None
    processing_time_ms: int
    cost_estimate: float
    dimensions: Optional[dict] = None
    error: Optional[str] = None


class BatchProductItem(BaseModel):
    """Single product for batch processing."""
    image_url: HttpUrl
    product_name: str = Field(..., min_length=1, max_length=200)
    niche: str = "smart_home"


class BatchEnhanceRequest(BaseModel):
    """Request to batch enhance multiple products."""
    products: List[BatchProductItem] = Field(..., min_items=1, max_items=10, description="Products to enhance (max 10)")
    add_branding: bool = True
    position: str = "center"
    scale: float = Field(default=0.6, ge=0.1, le=1.0)


class BatchEnhanceResponse(BaseModel):
    """Response for batch enhancement."""
    success: bool
    results: List[dict]
    total_cost: float
    success_count: int
    failed_count: int
    total_processing_time_ms: int


class StylePreset(BaseModel):
    """Style preset for a niche."""
    niche: str
    description: str
    prompt: str


class StylePresetsResponse(BaseModel):
    """Response with all available style presets."""
    presets: List[StylePreset]
    count: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/remove-background", response_model=RemoveBackgroundResponse)
async def remove_background(request: RemoveBackgroundRequest):
    """
    Remove background from a product image using AI.

    Uses free local rembg model for background removal.

    **Cost:** FREE (local processing)

    **Processing time:** ~2-5 seconds depending on image size

    **Example:**
    ```json
    {
        "image_url": "https://ae01.alicdn.com/..."
    }
    ```
    """
    start_time = time.time()

    try:
        logger.info(f"Removing background from: {request.image_url}")

        # Remove background
        result_image = await processor.remove_background(str(request.image_url))

        # Convert to base64
        import io
        import base64
        from PIL import Image

        buffer = io.BytesIO()
        result_image.save(buffer, format="PNG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode()

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(f"Background removed successfully in {processing_time}ms")

        return RemoveBackgroundResponse(
            success=True,
            image_base64=image_base64,
            processing_time_ms=processing_time
        )

    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(f"Background removal failed: {e}")

        return RemoveBackgroundResponse(
            success=False,
            error=str(e),
            processing_time_ms=processing_time
        )


@router.post("/generate-background", response_model=GenerateBackgroundResponse)
async def generate_background(request: GenerateBackgroundRequest):
    """
    Generate a professional lifestyle background using DALL-E 3.

    **Cost:** ~$0.04 per image (DALL-E 3 standard quality)

    **Processing time:** ~10-15 seconds

    **Example:**
    ```json
    {
        "product_name": "Smart LED Strip Lights",
        "niche": "smart_home"
    }
    ```

    **Available niches:**
    - smart_home, tech_gadgets, home_security, kitchen, bedroom, outdoor, fitness, office
    """
    start_time = time.time()

    try:
        logger.info(f"Generating background for: {request.product_name} (niche: {request.niche})")

        # Generate background
        result_image = await processor.generate_lifestyle_background(
            product_name=request.product_name,
            niche=request.niche,
            custom_prompt=request.custom_prompt
        )

        # Convert to base64
        import io
        import base64

        buffer = io.BytesIO()
        result_image.save(buffer, format="PNG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode()

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(f"Background generated successfully in {processing_time}ms")

        return GenerateBackgroundResponse(
            success=True,
            image_base64=image_base64,
            image_url=None,  # DALL-E URLs are temporary
            cost_estimate=0.04,
            processing_time_ms=processing_time
        )

    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(f"Background generation failed: {e}")

        return GenerateBackgroundResponse(
            success=False,
            error=str(e),
            cost_estimate=0.04 if "OpenAI" in str(e) else 0.0,
            processing_time_ms=processing_time
        )


@router.post("/enhance-product", response_model=EnhanceProductResponse)
async def enhance_product(request: EnhanceProductRequest):
    """
    Complete AI pipeline: Transform AliExpress product image into professional lifestyle photo.

    **Pipeline:**
    1. Download original image
    2. Remove background (FREE - local AI)
    3. Generate lifestyle background (~$0.04 - DALL-E 3)
    4. Composite product onto background
    5. Add branding/watermark
    6. Return enhanced image

    **Cost:** ~$0.04 per image

    **Processing time:** ~15-20 seconds

    **Example:**
    ```json
    {
        "image_url": "https://ae01.alicdn.com/kf/...",
        "product_name": "Smart LED Strip Lights - RGB WiFi",
        "niche": "smart_home",
        "add_branding": true,
        "position": "center",
        "scale": 0.6
    }
    ```
    """
    start_time = time.time()

    try:
        logger.info(f"Enhancing product: {request.product_name}")

        # Process image
        result = await processor.process_product_image(
            aliexpress_image_url=str(request.image_url),
            product_name=request.product_name,
            niche=request.niche,
            add_branding=request.add_branding,
            save_to_disk=request.save_to_disk,
            position=request.position,
            scale=request.scale
        )

        processing_time = int((time.time() - start_time) * 1000)

        if result["success"]:
            logger.info(f"Product enhanced successfully in {processing_time}ms")

            return EnhanceProductResponse(
                success=True,
                original_url=str(request.image_url),
                enhanced_base64=result.get("image_base64"),
                enhanced_url=None,  # Could upload to CDN here
                image_path=result.get("image_path"),
                processing_time_ms=processing_time,
                cost_estimate=result.get("cost_estimate", 0.04),
                dimensions=result.get("dimensions")
            )
        else:
            return EnhanceProductResponse(
                success=False,
                original_url=str(request.image_url),
                error=result.get("error"),
                processing_time_ms=processing_time,
                cost_estimate=result.get("cost_estimate", 0.0)
            )

    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(f"Product enhancement failed: {e}")

        return EnhanceProductResponse(
            success=False,
            original_url=str(request.image_url),
            error=str(e),
            processing_time_ms=processing_time,
            cost_estimate=0.0
        )


@router.post("/batch-enhance", response_model=BatchEnhanceResponse)
async def batch_enhance(request: BatchEnhanceRequest, background_tasks: BackgroundTasks):
    """
    Batch process multiple product images.

    **Limits:** Max 10 products per request

    **Cost:** ~$0.04 per product

    **Processing time:** ~20 seconds per product (sequential processing)

    **Example:**
    ```json
    {
        "products": [
            {
                "image_url": "https://ae01.alicdn.com/...",
                "product_name": "Smart LED Lights",
                "niche": "smart_home"
            },
            {
                "image_url": "https://ae01.alicdn.com/...",
                "product_name": "Wireless Earbuds",
                "niche": "tech_gadgets"
            }
        ]
    }
    ```
    """
    start_time = time.time()

    try:
        logger.info(f"Batch processing {len(request.products)} products")

        results = []
        total_cost = 0.0
        success_count = 0
        failed_count = 0

        # Process each product
        for idx, product in enumerate(request.products):
            logger.info(f"Processing product {idx + 1}/{len(request.products)}: {product.product_name}")

            try:
                result = await processor.process_product_image(
                    aliexpress_image_url=str(product.image_url),
                    product_name=product.product_name,
                    niche=product.niche,
                    add_branding=request.add_branding,
                    save_to_disk=True,
                    position=request.position,
                    scale=request.scale
                )

                if result["success"]:
                    success_count += 1
                    total_cost += result.get("cost_estimate", 0.04)

                    results.append({
                        "success": True,
                        "product_name": product.product_name,
                        "image_base64": result.get("image_base64"),
                        "image_path": result.get("image_path"),
                        "cost": result.get("cost_estimate", 0.04)
                    })
                else:
                    failed_count += 1
                    results.append({
                        "success": False,
                        "product_name": product.product_name,
                        "error": result.get("error")
                    })

            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to process {product.product_name}: {e}")
                results.append({
                    "success": False,
                    "product_name": product.product_name,
                    "error": str(e)
                })

        total_time = int((time.time() - start_time) * 1000)

        logger.info(f"Batch processing complete: {success_count} succeeded, {failed_count} failed")

        return BatchEnhanceResponse(
            success=True,
            results=results,
            total_cost=total_cost,
            success_count=success_count,
            failed_count=failed_count,
            total_processing_time_ms=total_time
        )

    except Exception as e:
        total_time = int((time.time() - start_time) * 1000)
        logger.error(f"Batch processing failed: {e}")

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/style-presets", response_model=StylePresetsResponse)
async def get_style_presets():
    """
    Get all available niche style presets for lifestyle backgrounds.

    Returns a list of niches with their descriptions and DALL-E prompts.

    **Example response:**
    ```json
    {
        "presets": [
            {
                "niche": "smart_home",
                "description": "Modern minimalist living room",
                "prompt": "Professional product photography of..."
            }
        ],
        "count": 8
    }
    ```
    """
    try:
        presets = [
            StylePreset(
                niche=niche,
                description=data["description"],
                prompt=data["prompt"]
            )
            for niche, data in NICHE_STYLE_PRESETS.items()
        ]

        return StylePresetsResponse(
            presets=presets,
            count=len(presets)
        )

    except Exception as e:
        logger.error(f"Failed to get style presets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check for image processor
@router.get("/health")
async def image_processor_health():
    """Check if image processor is healthy and DALL-E is available."""
    try:
        has_openai = processor.client is not None

        available_niches = list(NICHE_STYLE_PRESETS.keys())

        return {
            "status": "healthy",
            "dall_e_available": has_openai,
            "background_removal_available": True,  # rembg is always available
            "available_niches": available_niches,
            "niche_count": len(available_niches),
            "cost_per_image": 0.04 if has_openai else None
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
