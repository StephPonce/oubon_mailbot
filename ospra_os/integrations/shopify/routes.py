"""
Shopify One-Click Deployment API Routes

Endpoints for deploying products directly from the Ospra Intelligence dashboard.

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
    """Request to deploy a single product."""
    product_id: str = Field(..., description="Internal product ID from discovery")
    name: str = Field(..., description="Product name")
    niche: str = Field(default="general", description="Product niche/category")
    supplier_cost: float = Field(default=0, description="Supplier cost")
    supplier_url: Optional[str] = Field(None, description="AliExpress/supplier URL")
    images: List[str] = Field(default=[], description="Product image URLs")
    description: Optional[str] = Field(None, description="Optional description (AI generates if empty)")
    trend_score: float = Field(default=0, description="Trend score 0-100")
    generate_ai_description: bool = Field(default=True, description="Use AI to generate description")
    auto_publish: bool = Field(default=True, description="Publish immediately")


class BulkDeployRequest(BaseModel):
    """Request to deploy multiple products."""
    products: List[ProductDeployRequest]
    max_concurrent: int = Field(default=3, description="Max concurrent deployments")


class DeploymentResult(BaseModel):
    """Result of a deployment."""
    success: bool
    product_id: str
    shopify_product_id: Optional[int] = None
    shopify_url: Optional[str] = None
    admin_url: Optional[str] = None
    price: Optional[float] = None
    error: Optional[str] = None
    deployed_at: Optional[datetime] = None


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
    """Get or create deployment service."""
    global _deployment_service
    if _deployment_service is None:
        try:
            from ospra_os.integrations.shopify.deployment import ProductDeploymentService
            _deployment_service = ProductDeploymentService(get_shopify_client())
            logger.info("✅ Deployment service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize deployment service: {e}")
            raise HTTPException(status_code=500, detail=f"Deployment service error: {e}")
    return _deployment_service


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
    🚀 ONE-CLICK DEPLOY
    
    Deploy a single product to Shopify with AI-generated content.
    """
    try:
        logger.info(f"🚀 Deploying product: {request.name}")
        
        service = get_deployment_service()
        
        # Build product data for deployment service
        product_data = {
            "id": request.product_id,
            "name": request.name,
            "niche": request.niche,
            "cost": request.supplier_cost,
            "fulfillment_url": request.supplier_url,
            "images": request.images,
            "description": request.description,
            "trend_score": request.trend_score,
            "discovery_source": "ospra_dashboard",
            "created_at": datetime.now().isoformat()
        }
        
        # Deploy
        result = await service.deploy_product(
            product_data,
            generate_description=request.generate_ai_description
        )
        
        if result.get("success"):
            return DeploymentResult(
                success=True,
                product_id=request.product_id,
                shopify_product_id=result.get("shopify_product_id"),
                shopify_url=result.get("shopify_url"),
                admin_url=result.get("admin_url"),
                price=result.get("price"),
                deployed_at=datetime.now()
            )
        else:
            return DeploymentResult(
                success=False,
                product_id=request.product_id,
                error=result.get("error", "Unknown error")
            )
            
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return DeploymentResult(
            success=False,
            product_id=request.product_id,
            error=str(e)
        )


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
