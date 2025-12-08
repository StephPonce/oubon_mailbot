"""
Shopify One-Click Deployment API Routes - Enhanced with Unified AI Pipeline

Endpoints for deploying products directly from the Ospra Intelligence dashboard
with full AI-powered content generation, image enhancement, and SEO optimization.

Author: OspraOS
Date: December 2025
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shopify", tags=["shopify"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ProductDeployRequest(BaseModel):
    """Request to deploy a single product with AI-powered enhancements."""
    product_id: str = Field(..., description="Internal product ID from discovery")
    name: str = Field(..., description="Product name")
    niche: str = Field(default="general", description="Product niche/category")
    supplier_cost: float = Field(default=0, description="Supplier cost")
    supplier_url: Optional[str] = Field(None, description="AliExpress/supplier URL")
    images: List[str] = Field(default=[], description="Product image URLs")
    description: Optional[str] = Field(None, description="Optional description (AI generates if empty)")
    trend_score: float = Field(default=0, description="Trend score 0-100")
    features: List[str] = Field(default=[], description="Product features for AI content generation")

    # AI Control Flags
    ai_content: bool = Field(default=True, description="Auto-generate title/description with AI")
    ai_images: bool = Field(default=True, description="Auto-enhance images with AI (bg removal + lifestyle)")
    ai_pricing: bool = Field(default=True, description="Auto-suggest competitive price with AI")
    ai_seo: bool = Field(default=True, description="Auto-generate SEO metadata with AI")
    publish: bool = Field(default=False, description="Publish immediately (False = save as draft)")

    # Deployment Options
    target_margin: float = Field(default=0.4, description="Target profit margin (0.4 = 40%)")
    add_branding: bool = Field(default=True, description="Add branding/watermark to images")
    max_images: int = Field(default=5, description="Maximum number of images to process")


class BulkDeployRequest(BaseModel):
    """Request to deploy multiple products."""
    products: List[ProductDeployRequest]
    max_concurrent: int = Field(default=3, description="Max concurrent deployments")


class DeploymentResult(BaseModel):
    """Result of a deployment with AI metrics."""
    success: bool
    product_id: str
    shopify_product_id: Optional[int] = None
    shopify_url: Optional[str] = None
    admin_url: Optional[str] = None
    price: Optional[float] = None
    error: Optional[str] = None
    deployed_at: Optional[datetime] = None

    # AI Enhancement Metrics
    content_generated: Optional[Dict] = None  # AI-generated title, description, SEO
    images_enhanced: Optional[int] = None  # Number of images enhanced
    ai_costs: Optional[Dict] = None  # Cost breakdown (content, images)
    total_cost: Optional[float] = None  # Total AI cost
    processing_time_seconds: Optional[float] = None  # Time to deploy
    published: Optional[bool] = None  # Whether product was published


class PreviewResult(BaseModel):
    """Result of a deployment preview."""
    title: str
    description_html: str
    short_description: str
    bullet_points: List[str]
    images: List[str]
    pricing: Dict
    seo: Dict
    tags: List[str]
    estimated_cost: float
    processing_time: float


class ShopifyProduct(BaseModel):
    """Shopify product summary."""
    id: int
    title: str
    handle: str
    status: str
    price: float
    inventory_quantity: int
    created_at: str
    image_url: Optional[str] = None
    ospra_tracked: bool = False


# ============================================================================
# SHOPIFY CLIENT INITIALIZATION
# ============================================================================

_shopify_client = None
_deployment_service = None
_unified_deployer = None  # New unified AI deployer


def get_shopify_client():
    """Get or create Shopify client."""
    global _shopify_client
    if _shopify_client is None:
        try:
            from ospra_os.integrations.shopify.client import ShopifyClient
            _shopify_client = ShopifyClient()
            logger.info("✅ Shopify client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Shopify client: {e}")
            raise HTTPException(status_code=500, detail=f"Shopify not configured: {e}")
    return _shopify_client


def get_deployment_service():
    """Get or create legacy deployment service (for backwards compatibility)."""
    global _deployment_service
    if _deployment_service is None:
        try:
            from ospra_os.integrations.shopify.deployment import ProductDeploymentService
            _deployment_service = ProductDeploymentService(get_shopify_client())
            logger.info("✅ Legacy deployment service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize deployment service: {e}")
            raise HTTPException(status_code=500, detail=f"Deployment service error: {e}")
    return _deployment_service


def get_unified_deployer():
    """Get or create unified AI-powered deployer (NEW)."""
    global _unified_deployer
    if _unified_deployer is None:
        try:
            from ospra_os.services.product_deployer import ProductDeployer
            _unified_deployer = ProductDeployer()
            logger.info("✅ Unified AI deployer initialized (Claude + DALL-E + rembg)")
        except Exception as e:
            logger.error(f"Failed to initialize unified deployer: {e}")
            raise HTTPException(status_code=500, detail=f"Unified deployer error: {e}")
    return _unified_deployer


# ============================================================================
# API ROUTES
# ============================================================================

@router.get("/status")
async def shopify_status():
    """Check Shopify connection status and fetch real shop info."""
    import os
    
    store_name = os.getenv("SHOPIFY_STORE_NAME")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
    
    configured = bool(store_name and access_token)
    
    result = {
        "configured": configured,
        "store_name": "Not configured",
        "store_domain": f"{store_name}.myshopify.com" if store_name else None,
        "api_version": os.getenv("SHOPIFY_API_VERSION", "2024-10"),
        "mode": os.getenv("SHOPIFY_MODE", "safe"),
    }
    
    # Test connection and fetch real shop name if configured
    if configured:
        try:
            import httpx
            base_url = f"https://{store_name}.myshopify.com/admin/api/2024-10"
            headers = {
                'X-Shopify-Access-Token': access_token,
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                # Fetch shop info to get real name
                shop_response = await http_client.get(
                    f"{base_url}/shop.json",
                    headers=headers
                )
                
                if shop_response.status_code == 200:
                    shop_data = shop_response.json().get("shop", {})
                    result["store_name"] = shop_data.get("name", store_name)
                    result["shop_owner"] = shop_data.get("shop_owner")
                    result["email"] = shop_data.get("email")
                    result["currency"] = shop_data.get("currency", "USD")
                    result["country"] = shop_data.get("country_name")
                    result["plan_name"] = shop_data.get("plan_display_name")
                    result["connection"] = "active"
                    
                    # Also get product count
                    count_response = await http_client.get(
                        f"{base_url}/products/count.json",
                        headers=headers
                    )
                    if count_response.status_code == 200:
                        result["product_count"] = count_response.json().get("count", 0)
                else:
                    result["connection"] = "error"
                    result["error"] = f"API returned {shop_response.status_code}"
                    
        except Exception as e:
            result["connection"] = "error"
            result["error"] = str(e)
    else:
        result["connection"] = "not_configured"
    
    return result


@router.get("/products", response_model=List[ShopifyProduct])
async def list_shopify_products(limit: int = 50):
    """List products from Shopify store."""
    try:
        client = get_shopify_client()
        products = await client.list_products(limit=limit)
        
        result = []
        for p in products:
            variant = p.get("variants", [{}])[0]
            images = p.get("images", [])
            
            result.append(ShopifyProduct(
                id=p["id"],
                title=p["title"],
                handle=p.get("handle", ""),
                status=p.get("status", "draft"),
                price=float(variant.get("price", 0)),
                inventory_quantity=variant.get("inventory_quantity", 0),
                created_at=p.get("created_at", ""),
                image_url=images[0]["src"] if images else None,
                ospra_tracked="ospra" in str(p.get("tags", "")).lower()
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to list products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deploy", response_model=DeploymentResult)
async def deploy_product(request: ProductDeployRequest, background_tasks: BackgroundTasks):
    """
    🚀 ONE-CLICK DEPLOY with Full AI Pipeline

    Deploy a single product to Shopify with AI-powered enhancements:
    - Content generation (Claude Sonnet 4.5)
    - Image enhancement (DALL-E 3 + rembg)
    - SEO optimization
    - Competitive pricing

    AI features can be controlled via flags:
    - ai_content: Generate title/description
    - ai_images: Enhance images
    - ai_pricing: Suggest competitive price
    - ai_seo: Generate SEO metadata
    - publish: Publish immediately (vs draft)

    Cost: ~$0.02-0.06 per product (depending on AI features enabled)
    Time: ~20-30 seconds
    """
    try:
        logger.info(f"🚀 Deploying product: {request.name}")
        logger.info(f"   AI Flags: content={request.ai_content}, images={request.ai_images}, pricing={request.ai_pricing}, seo={request.ai_seo}")

        deployer = get_unified_deployer()

        # Build AliExpress product data for unified deployer
        aliexpress_product = {
            "title": request.name,
            "description": request.description,
            "features": request.features,
            "category": request.niche,
            "price": request.supplier_cost,
            "images": request.images
        }

        # Build deployment options based on AI flags
        options = {
            "enhance_images": request.ai_images,
            "generate_content": request.ai_content,
            "generate_seo": request.ai_seo,
            "generate_pricing": request.ai_pricing,
            "publish_immediately": request.publish,
            "add_branding": request.add_branding,
            "target_margin": request.target_margin,
            "max_images": request.max_images
        }

        # Deploy with unified AI pipeline
        result = await deployer.deploy_product(
            aliexpress_product=aliexpress_product,
            niche=request.niche,
            shopify_store_id=None,  # Use default store
            options=options
        )

        if result.get("success"):
            return DeploymentResult(
                success=True,
                product_id=request.product_id,
                shopify_product_id=result.get("shopify_product_id"),
                shopify_url=result.get("shopify_url"),
                admin_url=result.get("admin_url"),
                price=result.get("pricing", {}).get("retail_price"),
                deployed_at=datetime.now(),
                content_generated=result.get("content_generated"),
                images_enhanced=result.get("images_enhanced"),
                ai_costs=result.get("ai_costs"),
                total_cost=result.get("total_cost"),
                processing_time_seconds=result.get("processing_time_seconds"),
                published=result.get("published")
            )
        else:
            return DeploymentResult(
                success=False,
                product_id=request.product_id,
                error=result.get("error", "Unknown error"),
                ai_costs=result.get("ai_costs"),
                total_cost=result.get("total_cost"),
                processing_time_seconds=result.get("processing_time_seconds")
            )

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        return DeploymentResult(
            success=False,
            product_id=request.product_id,
            error=str(e)
        )


@router.post("/deploy/preview", response_model=PreviewResult)
async def preview_deployment(request: ProductDeployRequest):
    """
    👁️ PREVIEW DEPLOYMENT

    Generate AI content and enhanced images WITHOUT deploying to Shopify.
    Use this to preview what the product will look like before going live.

    Returns:
    - AI-generated title, description, bullet points
    - Enhanced product images (with background removal + lifestyle bg)
    - SEO metadata (meta title, description, keywords)
    - Competitive pricing suggestion
    - Estimated deployment cost

    Cost: ~$0.02-0.06 (same as deployment)
    Time: ~15-20 seconds
    """
    try:
        logger.info(f"👁️ Previewing product: {request.name}")

        deployer = get_unified_deployer()

        # Build AliExpress product data
        aliexpress_product = {
            "title": request.name,
            "description": request.description,
            "features": request.features,
            "category": request.niche,
            "price": request.supplier_cost,
            "images": request.images
        }

        # Generate preview
        result = await deployer.preview_deployment(
            aliexpress_product=aliexpress_product,
            niche=request.niche
        )

        return PreviewResult(
            title=result["title"],
            description_html=result["description_html"],
            short_description=result["short_description"],
            bullet_points=result["bullet_points"],
            images=result["images"],
            pricing=result["pricing"],
            seo=result["seo"],
            tags=result["tags"],
            estimated_cost=result["estimated_deployment_cost"],
            processing_time=result["processing_time"]
        )

    except Exception as e:
        logger.error(f"Preview failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deploy/bulk", response_model=List[DeploymentResult])
async def bulk_deploy_products(request: BulkDeployRequest):
    """
    🚀 BULK DEPLOY
    
    Deploy multiple products to Shopify.
    """
    try:
        service = get_deployment_service()
        
        # Convert to deployment format
        products = []
        for p in request.products:
            products.append({
                "id": p.product_id,
                "name": p.name,
                "niche": p.niche,
                "cost": p.supplier_cost,
                "fulfillment_url": p.supplier_url,
                "images": p.images,
                "description": p.description,
                "trend_score": p.trend_score,
                "discovery_source": "ospra_bulk_deploy",
                "created_at": datetime.now().isoformat()
            })
        
        # Bulk deploy
        results = await service.bulk_deploy(products, max_concurrent=request.max_concurrent)
        
        # Convert to response format
        return [
            DeploymentResult(
                success=r.get("success", False),
                product_id=products[i]["id"],
                shopify_product_id=r.get("shopify_product_id"),
                shopify_url=r.get("shopify_url"),
                admin_url=r.get("admin_url"),
                price=r.get("price"),
                error=r.get("error"),
                deployed_at=datetime.now() if r.get("success") else None
            )
            for i, r in enumerate(results)
        ]
        
    except Exception as e:
        logger.error(f"Bulk deployment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products/{product_id}")
async def delete_product(product_id: int):
    """Delete a product from Shopify."""
    try:
        client = get_shopify_client()
        success = await client.delete_product(product_id)
        
        if success:
            return {"success": True, "message": f"Product {product_id} deleted"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete product")
            
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/products/{product_id}/inventory")
async def update_inventory(product_id: int, quantity: int):
    """Update product inventory."""
    try:
        client = get_shopify_client()
        
        # Get product to find variant ID
        product = await client.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        variant_id = product.get("variants", [{}])[0].get("id")
        if not variant_id:
            raise HTTPException(status_code=400, detail="No variant found")
        
        success = await client.update_inventory(variant_id, quantity)
        
        if success:
            return {"success": True, "variant_id": variant_id, "quantity": quantity}
        else:
            raise HTTPException(status_code=500, detail="Failed to update inventory")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Inventory update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def shopify_analytics():
    """Get Shopify store analytics."""
    try:
        client = get_shopify_client()
        products = await client.list_products(limit=100)
        
        total_products = len(products)
        total_inventory = 0
        total_value = 0
        ospra_tracked = 0
        
        for p in products:
            variant = p.get("variants", [{}])[0]
            qty = variant.get("inventory_quantity", 0)
            price = float(variant.get("price", 0))
            
            total_inventory += qty
            total_value += qty * price
            
            if "ospra" in str(p.get("tags", "")).lower():
                ospra_tracked += 1
        
        return {
            "total_products": total_products,
            "total_inventory": total_inventory,
            "estimated_value": round(total_value, 2),
            "ospra_tracked": ospra_tracked,
            "non_ospra": total_products - ospra_tracked
        }
        
    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
