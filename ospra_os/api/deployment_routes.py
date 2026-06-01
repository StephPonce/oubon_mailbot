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

# Database-backed job storage (replaces in-memory dict for production reliability)
# Falls back to in-memory dict if database connection fails
try:
    from ospra_os.database.job_models import JobStorage, Job
    from ospra_os.database import get_db

    # Create job storage with database session factory
    deployment_jobs = JobStorage(get_db)
    logger.info("[SUCCESS] Using database-backed job storage for deployments")
except Exception as e:
    logger.warning(f"Database job storage unavailable, using in-memory: {e}")
    deployment_jobs = {}  # Fallback to in-memory


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SourceProduct(BaseModel):
    """
    Source product data (any supplier).

    Task #21: was previously named AliExpressProduct and required a
    `category` string, which CJ-sourced products don't always have. Renamed
    and relaxed so CJ-only products can be deployed without a validation
    error. AliExpressProduct alias is kept at the bottom of this file for
    back-compat with any external callers.

    Supplier-source metadata (source, cj_pid, warehouse, etc.) flows
    through via `model_config = extra='allow'` so downstream code can read it.
    """
    model_config = {"extra": "allow"}  # allow CJ-specific fields like cj_pid, warehouse

    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    features: List[str] = Field(default_factory=list, description="Product features")
    category: Optional[str] = Field(None, description="Product category (optional for CJ products)")
    price: float = Field(..., gt=0, description="Cost price from supplier")
    images: List[str] = Field(default_factory=list, description="Product image URLs")
    # Source tag so the deployer can build the right SKU prefix and supplier link.
    # When the winner-first sourcing path surfaced the product, this is
    # tagged like 'ae_via_meta_winner' / 'cj_via_tiktok_shop' so the
    # self-learning loop can attribute outcomes to the surfacing source.
    source: Optional[str] = Field(None, description="Supplier source ('aliexpress', 'cj_dropshipping', etc.)")
    # CJ's image field name — accept so the deployer can fall back to it.
    all_images: Optional[List[str]] = Field(None, description="Alternative images list (CJ uses this key)")
    # Self-learning hookup (added with the winner-first /quick restructure).
    # Frontend rounds these back from discovery so /api/deploy/product can
    # write a RecommendationOutcome row with full attribution.
    # `source` above is the supplier routing key ('aliexpress' /
    # 'cj_dropshipping'); winner_source + winner_provenance carry the
    # surfacing-source attribution separately to avoid breaking downstream
    # filters that check the literal source value.
    winner_source: Optional[str] = Field(
        None,
        description="Winner-source that surfaced the product (e.g. 'meta_ads', 'tiktok_shop', 'amazon_movers', 'etsy'). None when keyword-discovered.",
    )
    winner_provenance: Optional[Dict] = Field(
        None,
        description="Winner-source attribution: {source_winner, source_winner_name, source_winner_strength}",
    )
    product_id: Optional[str] = Field(None, description="Supplier product identifier (AE pid or CJ pid)")
    supplier_url: Optional[str] = Field(None, description="Direct link to the supplier product page")
    cost_price: Optional[float] = Field(None, description="Wholesale cost from supplier (alias of price)")
    suggested_price: Optional[float] = Field(None, description="Retail price suggestion from discovery scoring")


# Back-compat alias — old integrations may still import AliExpressProduct.
AliExpressProduct = SourceProduct


class PrepareProductRequest(BaseModel):
    """Request to prepare product for deployment"""
    product: SourceProduct
    niche: str = Field(..., description="Product niche (smart_home, fitness, etc.)")
    auto_enhance_images: bool = Field(default=True, description="Enhance images with AI")
    auto_generate_content: bool = Field(default=True, description="Generate content with AI")


class DeployProductRequest(BaseModel):
    """Request to deploy product to Shopify"""
    product: SourceProduct
    niche: str = Field(..., description="Product niche")
    shopify_store_id: Optional[str] = Field(None, description="Specific Shopify store ID")
    options: Optional[Dict] = Field(
        default_factory=dict,
        description="Deployment options: enhance_images, generate_content, publish_immediately, etc."
    )


class BulkDeployRequest(BaseModel):
    """Request to deploy multiple products"""
    products: List[SourceProduct] = Field(..., min_length=1, max_length=20, description="Products to deploy (max 20)")
    niche: str = Field(..., description="Product niche")
    options: Optional[Dict] = Field(default_factory=dict, description="Deployment options")
    async_mode: bool = Field(default=False, description="Run in background (returns job_id)")


class PreviewRequest(BaseModel):
    """Request to preview deployment"""
    product: SourceProduct
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

        # Task #21: use source_product= for consistency with deploy_product route.
        # The deployer accepts both kwargs for back-compat.
        result = await deployer.prepare_product(
            source_product=request.product.dict(),
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
        raise HTTPException(status_code=500, detail="Deployment operation failed. Please try again.")


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
            source_product=request.product.dict(),
            niche=request.niche,
            shopify_store_id=request.shopify_store_id,
            options=request.options
        )

        if result.get("success"):
            # Self-learning hookup: record the deploy in the feedback-loop
            # tables so daily_feedback_loop can classify it once ≥7 days of
            # ProductPerformance data accumulates. Wrapped in try/except so
            # a learning-tier failure never breaks the user's deploy — the
            # Shopify product is already live by this point.
            try:
                await _record_product_deploy_outcome(
                    user_id=int(current_user.id),
                    source_product=request.product.dict(),
                    niche=request.niche,
                    deploy_result=result,
                )
            except Exception as exc:
                logger.warning(
                    f"[self-learning] failed to record outcome for deploy "
                    f"(deploy itself succeeded): {exc}"
                )

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
        raise HTTPException(status_code=500, detail="Deployment operation failed. Please try again.")


async def _record_product_deploy_outcome(
    user_id: int,
    source_product: Dict,
    niche: str,
    deploy_result: Dict,
) -> None:
    """Self-learning hookup for /api/deploy/product.

    Mirrors the bookkeeping in /winners/{outcome_id}/deploy but for the
    Products-page deploy flow. Without this the feedback loop has zero
    visibility into which winner-source surfaced which product.

    Steps:
      1. Create a local Product row tied to the user's store. This is
         the FK target evaluate_outcomes() reads ProductPerformance from.
      2. Create a RecommendationOutcome row referencing that Product,
         with winner_provenance stashed in confidence_breakdown so the
         per-signal learning processor can credit the right source later.

    Pure best-effort: any failure here is swallowed by the caller's
    try/except. The Shopify deploy already happened — we don't want a
    learning-tier issue to surface to the user as a failed deploy.
    """
    from datetime import datetime as _dt
    from ospra_os.database import get_session
    from ospra_os.database.performance_models import RecommendationOutcome
    from ospra_os.database.product_models import Product, ProductStatus
    from ospra_os.database.store_models import Store

    provenance = source_product.get("winner_provenance") or {}
    winner_source = source_product.get("winner_source")  # e.g. "meta_ads", "tiktok_shop"
    source_tag = str(source_product.get("source") or "")
    # Detect winner-first path by the presence of attribution metadata.
    # `source` is now a stable routing key ('aliexpress' / 'cj_dropshipping')
    # so we look at winner_source/provenance instead of source prefix to
    # decide whether this was a winner-first pick.
    is_winner_first = bool(winner_source) or bool(provenance)
    supplier_type = "cj" if source_tag == "cj_dropshipping" else "ae"

    cost_price = float(source_product.get("cost_price") or source_product.get("price") or 0)
    suggested_price = float(
        source_product.get("suggested_price")
        or deploy_result.get("pricing", {}).get("selling_price")
        or 0
    )
    margin_pct = (
        ((suggested_price - cost_price) / cost_price * 100)
        if cost_price > 0 else 0
    )

    with next(get_session()) as db:
        # Resolve a store to attach the Product to. Use the user's first
        # store if no explicit store_id was passed through deploy options.
        store = (
            db.query(Store)
            .filter(Store.user_id == user_id)
            .order_by(Store.id.asc())
            .first()
        )
        if not store:
            logger.info(
                f"[self-learning] user {user_id} has no store row — "
                "skipping outcome recording (deploy itself succeeded)"
            )
            return

        product = Product(
            store_id=store.id,
            product_name=(source_product.get("title") or "Untitled")[:512],
            title=(source_product.get("title") or "Untitled")[:512],
            source_platform=(
                "cj_dropshipping" if supplier_type == "cj" else "aliexpress"
            ),
            source_url=source_product.get("supplier_url"),
            source_product_id=str(source_product.get("product_id") or ""),
            supplier_cost=cost_price,
            selling_price=suggested_price,
            price=suggested_price,
            profit_margin=margin_pct,
            ai_explanation=(
                f"Deployed from Products page. "
                f"Winner source: {provenance.get('source_winner', 'unknown')} / "
                f"{provenance.get('source_winner_name', 'n/a')}"
            )[:2000],
            status=ProductStatus.DISCOVERED,
            discovered_at=_dt.utcnow(),
        )
        db.add(product)
        db.flush()

        confidence_breakdown = {
            "discovery_flow": "winner_first" if is_winner_first else "keyword_search",
            "niche": niche,
            "supplier_type": supplier_type,
            "source_tag": source_tag,
            "winner_provenance": provenance,
            "shopify_product_id": deploy_result.get("shopify_product_id"),
            "shopify_url": deploy_result.get("shopify_url"),
            "captured_at": _dt.utcnow().isoformat(),
        }

        # Confidence score: prefer winner_provenance signal_strength when
        # available (0-1 from the source), else neutral 50.
        ws = provenance.get("source_winner_strength")
        confidence_score = (
            float(ws) * 100.0 if ws is not None else 50.0
        )

        outcome = RecommendationOutcome(
            user_id=user_id,
            action_id=None,
            product_id=product.id,
            recommendation_type=(
                "winner_first_pick" if is_winner_first else "product_deploy"
            ),
            confidence_score=confidence_score,
            confidence_breakdown=confidence_breakdown,
            ai_reasoning=(
                f"Deployed via /api/deploy/product. "
                + (
                    f"Surfaced by {provenance.get('source_winner')} winner "
                    f"'{provenance.get('source_winner_name')}'. "
                    if is_winner_first else
                    "Sourced via keyword-based discovery. "
                )
                + f"Niche: {niche}. Supplier: {supplier_type}."
            )[:2000],
            projected_daily_sales=1.0 if margin_pct > 0 else 0.0,
            projected_monthly_revenue=(
                30.0 * suggested_price if margin_pct > 0 else 0.0
            ),
            projected_margin=margin_pct,
            was_accepted=True,
            accepted_at=_dt.utcnow(),
            tracking_started_at=_dt.utcnow(),
        )
        db.add(outcome)
        db.commit()
        db.refresh(outcome)

        logger.info(
            f"[self-learning] recorded outcome #{outcome.id} → "
            f"product #{product.id} (flow={confidence_breakdown['discovery_flow']}, "
            f"winner_source={provenance.get('source_winner', 'n/a')})"
        )


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
                    logger.error(f"Bulk deployment {job_id} failed: {e}")
                    deployment_jobs[job_id].update({
                        "status": "failed",
                        "error": "Deployment failed. Please try again."
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
        raise HTTPException(status_code=500, detail="Deployment operation failed. Please try again.")


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
        raise HTTPException(status_code=500, detail="Deployment operation failed. Please try again.")


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
