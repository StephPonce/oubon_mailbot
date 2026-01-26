"""
Ospra Intelligence - Product Deployment API Routes

Unified deployment pipeline endpoints for deploying products to Shopify
with AI content generation and image enhancement.

Endpoints:
- POST /api/deploy/prepare - Prepare product without deploying
- POST /api/deploy/product - Deploy single product
- POST /api/deploy/bulk - Deploy multiple products
- POST /api/deploy/preview - Preview deployment
- GET /api/deploy/status/{job_id} - Check async deployment status
"""

import uuid
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field, HttpUrl

from ospra_os.services.product_deployer import ProductDeployer
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database.user_models import User

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(
    prefix="/api/deploy",
    tags=["Product Deployment"]
)

# Initialize deployer (singleton)
deployer = ProductDeployer()

# Background job storage (in production, use Redis/database)
deployment_jobs = {}


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AliExpressProduct(BaseModel):
    """AliExpress product data"""
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    features: List[str] = Field(default_factory=list, description="Product features")
    category: str = Field(..., description="Product category")
    price: float = Field(..., gt=0, description="Cost price from AliExpress")
    images: List[str] = Field(default_factory=list, description="Product image URLs")


class PrepareProductRequest(BaseModel):
    """Request to prepare product for deployment"""
    product: AliExpressProduct
    niche: str = Field(..., description="Product niche (smart_home, fitness, etc.)")
    auto_enhance_images: bool = Field(default=True, description="Enhance images with AI")
    auto_generate_content: bool = Field(default=True, description="Generate content with AI")


class DeployProductRequest(BaseModel):
    """Request to deploy product to Shopify"""
    product: AliExpressProduct
    niche: str = Field(..., description="Product niche")
    shopify_store_id: Optional[str] = Field(None, description="Specific Shopify store ID")
    options: Optional[Dict] = Field(
        default_factory=dict,
        description="Deployment options: enhance_images, generate_content, publish_immediately, etc."
    )


class BulkDeployRequest(BaseModel):
    """Request to deploy multiple products"""
    products: List[AliExpressProduct] = Field(..., min_items=1, max_items=20, description="Products to deploy (max 20)")
    niche: str = Field(..., description="Product niche")
    options: Optional[Dict] = Field(default_factory=dict, description="Deployment options")
    async_mode: bool = Field(default=False, description="Run in background (returns job_id)")


class PreviewRequest(BaseModel):
    """Request to preview deployment"""
    product: AliExpressProduct
    niche: str = Field(..., description="Product niche")


class PrepareResponse(BaseModel):
    """Response from prepare endpoint"""
    success: bool
    content: Dict
    images: List[str]
    pricing: Dict
    meta: Dict


class DeployResponse(BaseModel):
    """Response from deploy endpoint"""
    success: bool
    shopify_product_id: Optional[str] = None
    shopify_url: Optional[str] = None
    admin_url: Optional[str] = None
    content_generated: Optional[Dict] = None
    images_enhanced: Optional[int] = None
    pricing: Optional[Dict] = None
    processing_time_seconds: Optional[float] = None
    ai_costs: Optional[Dict] = None
    total_cost: Optional[float] = None
    published: Optional[bool] = None
    error: Optional[str] = None


class BulkDeployResponse(BaseModel):
    """Response from bulk deploy endpoint"""
    success: bool
    job_id: Optional[str] = None  # For async mode
    total: Optional[int] = None
    successful: Optional[int] = None
    failed: Optional[int] = None
    results: Optional[List[Dict]] = None
    total_cost: Optional[float] = None
    processing_time_seconds: Optional[float] = None


class PreviewResponse(BaseModel):
    """Response from preview endpoint"""
    title: str
    description_html: str
    short_description: str
    bullet_points: List[str]
    images: List[str]
    pricing: Dict
    seo: Dict
    tags: List[str]
    estimated_deployment_cost: float
    processing_time: float


class JobStatusResponse(BaseModel):
    """Response for job status check"""
    job_id: str
    status: str  # pending, running, completed, failed
    progress: Optional[Dict] = None
    result: Optional[Dict] = None
    error: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/prepare", response_model=PrepareResponse)
async def prepare_product(
    request: PrepareProductRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Prepare product for deployment WITHOUT deploying

    Good for preview/review before going live. Generates AI content
    and enhances images but doesn't push to Shopify.

    **Cost:** ~$0.02-0.06 (depends on options)

    **Processing time:** ~15-20 seconds

    **Requires authentication.**
    """
    try:
        logger.info(f"[PACKAGE] Preparing product: {request.product.title[:50]}")

        result = await deployer.prepare_product(
            aliexpress_product=request.product.dict(),
            niche=request.niche,
            auto_enhance_images=request.auto_enhance_images,
            auto_generate_content=request.auto_generate_content
        )

        return PrepareResponse(
            success=True,
            content=result["content"],
            images=result["images"],
            pricing=result["pricing"],
            meta=result["meta"]
        )

    except Exception as e:
        logger.error(f"Preparation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/product", response_model=DeployResponse)
async def deploy_product(
    request: DeployProductRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Deploy single product to Shopify with full AI pipeline

    **Pipeline:**
    1. Generate AI content (title, description, SEO)
    2. Enhance product images (DALL-E 3 + rembg)
    3. Create product on Shopify
    4. Upload enhanced images
    5. Set pricing and SEO metadata

    **Cost:** ~$0.02-0.06 per product

    **Processing time:** ~20-30 seconds

    **Requires authentication.**
            "title": "Smart LED Bulb WiFi RGB...",
            "category": "Smart Lighting",
            "price": 12.99,
            "features": ["WiFi connectivity", "RGB colors", "Alexa compatible"],
            "images": ["https://ae01.alicdn.com/..."]
        },
        "niche": "smart_home",
        "options": {
            "enhance_images": true,
            "generate_content": true,
            "publish_immediately": false,
            "target_margin": 0.4
        }
    }
    ```
    """
    try:
        logger.info(f"[START] Deploying product: {request.product.title[:50]}")

        result = await deployer.deploy_product(
            aliexpress_product=request.product.dict(),
            niche=request.niche,
            shopify_store_id=request.shopify_store_id,
            options=request.options
        )

        if result.get("success"):
            return DeployResponse(
                success=True,
                shopify_product_id=result["shopify_product_id"],
                shopify_url=result["shopify_url"],
                admin_url=result["admin_url"],
                content_generated=result["content_generated"],
                images_enhanced=result["images_enhanced"],
                pricing=result["pricing"],
                processing_time_seconds=result["processing_time_seconds"],
                ai_costs=result["ai_costs"],
                total_cost=result["total_cost"],
                published=result["published"]
            )
        else:
            return DeployResponse(
                success=False,
                error=result.get("error", "Unknown error"),
                processing_time_seconds=result.get("processing_time_seconds"),
                ai_costs=result.get("ai_costs")
            )

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk", response_model=BulkDeployResponse)
async def bulk_deploy(
    request: BulkDeployRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Deploy multiple products to Shopify

    **Limits:** Max 20 products per request

    **Cost:** ~$0.02-0.06 per product

    **Requires authentication.**
    """
    try:
        logger.info(f"[PACKAGE] Bulk deploy: {len(request.products)} products")

        if request.async_mode:
            # Run in background
            job_id = str(uuid.uuid4())

            # Initialize job status
            deployment_jobs[job_id] = {
                "status": "pending",
                "total": len(request.products),
                "completed": 0,
                "successful": 0,
                "failed": 0,
                "results": []
            }

            # Queue background task
            async def run_bulk_deployment():
                deployment_jobs[job_id]["status"] = "running"

                try:
                    result = await deployer.bulk_deploy(
                        products=[p.dict() for p in request.products],
                        niche=request.niche,
                        options=request.options
                    )

                    deployment_jobs[job_id].update({
                        "status": "completed",
                        "result": result
                    })

                except Exception as e:
                    deployment_jobs[job_id].update({
                        "status": "failed",
                        "error": str(e)
                    })

            background_tasks.add_task(run_bulk_deployment)

            return BulkDeployResponse(
                success=True,
                job_id=job_id,
                total=len(request.products)
            )

        else:
            # Run synchronously
            result = await deployer.bulk_deploy(
                products=[p.dict() for p in request.products],
                niche=request.niche,
                options=request.options
            )

            return BulkDeployResponse(
                success=True,
                total=result["total"],
                successful=result["successful"],
                failed=result["failed"],
                results=result["results"],
                total_cost=result["total_cost"],
                processing_time_seconds=result["processing_time_seconds"]
            )

    except Exception as e:
        logger.error(f"Bulk deployment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview", response_model=PreviewResponse)
async def preview_deployment(request: PreviewRequest):
    """
    Preview what product would look like when deployed

    Generates all content and enhanced images but doesn't deploy to Shopify.
    Good for admin review before going live.

    **Cost:** ~$0.02-0.06 (same as deployment)

    **Processing time:** ~15-20 seconds

    **Example:**
    ```json
    {
        "product": {
            "title": "Smart LED Bulb WiFi RGB...",
            "category": "Smart Lighting",
            "price": 12.99,
            "features": ["WiFi", "RGB colors", "Alexa"],
            "images": ["https://ae01.alicdn.com/..."]
        },
        "niche": "smart_home"
    }
    ```
    """
    try:
        logger.info(f"  Preview: {request.product.title[:50]}")

        result = await deployer.preview_deployment(
            aliexpress_product=request.product.dict(),
            niche=request.niche
        )

        return PreviewResponse(**result)

    except Exception as e:
        logger.error(f"Preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_deployment_status(job_id: str):
    """
    Check status of async bulk deployment

    Returns current status and progress of background deployment job.

    **Statuses:**
    - `pending` - Job queued, not started
    - `running` - Currently processing
    - `completed` - All products processed
    - `failed` - Job failed with error

    **Example:**
    ```
    GET /api/deploy/status/abc-123-def-456
    ```
    """
    if job_id not in deployment_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = deployment_jobs[job_id]

    response = JobStatusResponse(
        job_id=job_id,
        status=job["status"]
    )

    if job["status"] == "running":
        response.progress = {
            "total": job["total"],
            "completed": job["completed"],
            "successful": job["successful"],
            "failed": job["failed"]
        }
    elif job["status"] == "completed":
        response.result = job.get("result")
    elif job["status"] == "failed":
        response.error = job.get("error")

    return response


@router.get("/health")
async def deployment_health():
    """
    Check deployment service health

    Returns status of all integrated services:
    - Content generator (Claude)
    - Image processor (DALL-E 3 + rembg)
    - Shopify client
    """
    return {
        "status": "healthy",
        "services": {
            "content_generator": deployer.content_generator is not None,
            "image_processor": deployer.image_processor is not None,
            "shopify_client": deployer.shopify is not None
        },
        "capabilities": {
            "ai_content_generation": deployer.content_generator is not None,
            "ai_image_enhancement": deployer.image_processor is not None,
            "shopify_deployment": deployer.shopify is not None
        }
    }
