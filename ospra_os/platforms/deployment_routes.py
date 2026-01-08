"""
Unified Product Deployment API
Routes for deploying products to Shopify, Amazon, and WooCommerce

[SECURE] SECURED with JWT Authentication
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List, Dict
from ospra_os.core.settings import Settings, get_settings
import os

# JWT Authentication
from ospra_os.auth.dependencies import require_auth, require_tier, TokenPayload

# Import platform adapters (using unified adapter pattern)
try:
    from ospra_os.platforms.shopify import ShopifyAdapter
except ImportError:
    ShopifyAdapter = None

try:
    from ospra_os.platforms.amazon import AmazonAdapter
except ImportError:
    AmazonAdapter = None

try:
    from ospra_os.platforms.woocommerce import WooCommerceAdapter
except ImportError:
    WooCommerceAdapter = None

router = APIRouter(prefix="/api/deploy", tags=["Product Deployment"])


# ============================================================================
# Pydantic Models
# ============================================================================

class ProductDeployRequest(BaseModel):
    """Request to deploy a product to one or more platforms"""
    product_id: str
    product_data: Dict
    platforms: List[str]  # ["shopify", "amazon", "woocommerce"]
    generate_ai_description: bool = True
    optimize_seo: bool = True
    publish_immediately: bool = False


class BulkDeployRequest(BaseModel):
    """Bulk deploy multiple products"""
    products: List[Dict]
    platforms: List[str]
    generate_ai_description: bool = True
    optimize_seo: bool = True


class StoreConfig(BaseModel):
    """Store connection configuration"""
    platform: str  # "shopify", "amazon", "woocommerce"
    store_id: str
    credentials: Dict


# ============================================================================
# Helper Functions
# ============================================================================

def get_shopify_deployer(settings: Settings = Depends(get_settings)):
    """Get Shopify deployer instance"""
    from ospra_os.platforms.shopify_deployer import ShopifyProductDeployer
    
    shopify_token = os.getenv("SHOPIFY_API_TOKEN")
    shopify_store = os.getenv("SHOPIFY_STORE", "rxxj7d-1i.myshopify.com")

    if not shopify_token:
        return None

    return ShopifyProductDeployer(
        shop_domain=shopify_store,
        access_token=shopify_token
    )


def get_amazon_client(settings: Settings = Depends(get_settings)):
    """Get Amazon SP-API client instance"""
    try:
        from ospra_os.platforms.amazon_seller_api import AmazonSellerAPI
    except ImportError:
        return None
    
    refresh_token = os.getenv("AMAZON_REFRESH_TOKEN")
    client_id = os.getenv("AMAZON_CLIENT_ID")
    client_secret = os.getenv("AMAZON_CLIENT_SECRET")

    if not all([refresh_token, client_id, client_secret]):
        return None

    return AmazonSellerAPI(
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret
    )


def get_woocommerce_client(
    store_url: Optional[str] = None,
    settings: Settings = Depends(get_settings)
):
    """Get WooCommerce connector instance"""
    try:
        from ospra_os.platforms.woocommerce_connector import WooCommerceConnector
    except ImportError:
        return None
    
    store_url = store_url or os.getenv("WOOCOMMERCE_STORE_URL")
    consumer_key = os.getenv("WOOCOMMERCE_CONSUMER_KEY")
    consumer_secret = os.getenv("WOOCOMMERCE_CONSUMER_SECRET")

    if not all([store_url, consumer_key, consumer_secret]):
        return None

    return WooCommerceConnector(
        store_url=store_url,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret
    )


# ============================================================================
# Deployment Endpoints
# ============================================================================

@router.post("/product")
async def deploy_product(
    request: ProductDeployRequest,
    user: TokenPayload = Depends(require_auth),
    settings: Settings = Depends(get_settings)
):
    """
    Deploy a single product to one or more platforms

    Example:
    ```json
    {
        "product_id": "prod_12345",
        "product_data": {
            "name": "Smart LED Strip Lights",
            "description": "RGB color changing LED strips...",
            "price": 15.99,
            "image_url": "https://...",
            "category": "smart_home"
        },
        "platforms": ["shopify", "amazon"],
        "generate_ai_description": true,
        "optimize_seo": true
    }
    ```
    
    [SECURE] Requires authentication
    """
    results = {}

    # Deploy to Shopify
    if "shopify" in request.platforms:
        shopify = get_shopify_deployer(settings)
        if shopify:
            try:
                result = await shopify.deploy_product(
                    request.product_data,
                    generate_description=request.generate_ai_description,
                    optimize_seo=request.optimize_seo
                )
                results["shopify"] = result
            except Exception as e:
                results["shopify"] = {"success": False, "error": str(e)}
        else:
            results["shopify"] = {
                "success": False,
                "error": "Shopify credentials not configured"
            }

    # Deploy to Amazon
    if "amazon" in request.platforms:
        amazon = get_amazon_client(settings)
        if amazon:
            try:
                result = await amazon.create_product_listing(
                    request.product_data,
                    use_xml_feed=True
                )
                results["amazon"] = result
            except Exception as e:
                results["amazon"] = {"success": False, "error": str(e)}
        else:
            results["amazon"] = {
                "success": False,
                "error": "Amazon credentials not configured"
            }

    # Deploy to WooCommerce
    if "woocommerce" in request.platforms:
        woo = get_woocommerce_client(settings=settings)
        if woo:
            try:
                result = await woo.create_product(
                    request.product_data,
                    publish_immediately=request.publish_immediately
                )
                results["woocommerce"] = result
            except Exception as e:
                results["woocommerce"] = {"success": False, "error": str(e)}
        else:
            results["woocommerce"] = {
                "success": False,
                "error": "WooCommerce credentials not configured"
            }

    # Record learning event for successful deployments
    if len([p for p, r in results.items() if r.get("success", False)]) > 0:
        try:
            from datetime import datetime
            from ospra_os.database.multi_store_models import SessionLocal
            from ospra_os.learning.hybrid_learning_engine import LearningEvent

            # Extract product metadata
            product_data = request.product_data
            niche = product_data.get("category", "unknown")
            price = product_data.get("price", 0)
            product_name = product_data.get("name", "Unknown Product")

            # Create learning event
            db = SessionLocal()
            try:
                event = LearningEvent(
                    user_id=user.user_id,  # Use authenticated user ID
                    event_type="product_deployed",
                    details={
                        "product_id": request.product_id,
                        "product_name": product_name,
                        "niche": niche,
                        "price": float(price) if price else 0.0,
                        "platforms": list(results.keys()),
                        "successful_platforms": [p for p, r in results.items() if r.get("success", False)],
                        "source": "deployment_api",
                        "deployed_by": user.email,
                        # Store AI score if available
                        "predicted_score": product_data.get("ai_score", product_data.get("score", None)),
                        "deployment_timestamp": datetime.utcnow().isoformat()
                    }
                )
                db.add(event)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            # Don't fail deployment if learning recording fails
            import logging
            logging.getLogger(__name__).warning(f"Failed to record learning event: {e}")

    # Summary
    successful_platforms = [
        platform for platform, result in results.items()
        if result.get("success", False)
    ]

    return {
        "product_id": request.product_id,
        "requested_platforms": request.platforms,
        "successful_platforms": successful_platforms,
        "results": results,
        "success": len(successful_platforms) > 0,
        "deployed_by": user.email
    }


@router.post("/bulk")
async def bulk_deploy_products(
    request: BulkDeployRequest,
    user: TokenPayload = Depends(require_tier("flight")),  # Requires Flight tier+
    settings: Settings = Depends(get_settings)
):
    """
    Deploy multiple products to one or more platforms

    Example:
    ```json
    {
        "products": [
            {"name": "Product 1", "price": 29.99, ...},
            {"name": "Product 2", "price": 39.99, ...}
        ],
        "platforms": ["shopify", "woocommerce"]
    }
    ```
    
    [SECURE] Requires Flight tier or higher
    """
    deployment_results = []

    for product in request.products:
        product_request = ProductDeployRequest(
            product_id=product.get("id", product.get("name", "unknown")),
            product_data=product,
            platforms=request.platforms,
            generate_ai_description=request.generate_ai_description,
            optimize_seo=request.optimize_seo
        )

        result = await deploy_product(product_request, user, settings)
        deployment_results.append(result)

    # Summary statistics
    total_products = len(deployment_results)
    successful_deployments = sum(
        1 for r in deployment_results if r["success"]
    )

    return {
        "total_products": total_products,
        "successful_deployments": successful_deployments,
        "failed_deployments": total_products - successful_deployments,
        "results": deployment_results,
        "deployed_by": user.email
    }


@router.post("/stores/sync-orders")
async def sync_store_orders(
    store_id: str,
    platform: str,
    user: TokenPayload = Depends(require_auth),
    settings: Settings = Depends(get_settings)
):
    """
    Sync orders from a specific store

    Platforms: shopify, amazon, woocommerce
    
    [SECURE] Requires authentication
    """
    orders = []

    if platform == "amazon":
        amazon = get_amazon_client(settings)
        if amazon:
            result = await amazon.get_orders()
            if result.get("success"):
                orders = result.get("orders", [])
        else:
            raise HTTPException(status_code=400, detail="Amazon not configured")

    elif platform == "woocommerce":
        woo = get_woocommerce_client(settings=settings)
        if woo:
            result = await woo.get_orders(per_page=50)
            if result.get("success"):
                orders = result.get("orders", [])
        else:
            raise HTTPException(status_code=400, detail="WooCommerce not configured")

    elif platform == "shopify":
        # Shopify order syncing would go here
        # (requires additional Shopify API methods)
        raise HTTPException(status_code=501, detail="Shopify order sync not yet implemented")

    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    return {
        "store_id": store_id,
        "platform": platform,
        "orders_count": len(orders),
        "orders": orders
    }


@router.get("/platforms/status")
async def get_platform_status(
    user: TokenPayload = Depends(require_auth),
    settings: Settings = Depends(get_settings)
):
    """
    Check connection status for all platforms
    
    [SECURE] Requires authentication
    """
    status = {}

    # Shopify status
    shopify = get_shopify_deployer(settings)
    status["shopify"] = {
        "configured": shopify is not None,
        "store": os.getenv("SHOPIFY_STORE", "Not configured")
    }

    # Amazon status
    amazon = get_amazon_client(settings)
    status["amazon"] = {
        "configured": amazon is not None,
        "region": os.getenv("AMAZON_REGION", "us-east-1") if amazon else "Not configured"
    }

    # WooCommerce status
    woo = get_woocommerce_client(settings=settings)
    status["woocommerce"] = {
        "configured": woo is not None,
        "store_url": os.getenv("WOOCOMMERCE_STORE_URL", "Not configured")
    }

    # Test connections
    if shopify:
        try:
            # Simple check - if we can instantiate, credentials exist
            status["shopify"]["status"] = "ready"
        except Exception as e:
            status["shopify"]["status"] = f"error: {e}"

    if amazon:
        try:
            status["amazon"]["status"] = "ready"
        except Exception as e:
            status["amazon"]["status"] = f"error: {e}"

    if woo:
        try:
            test_result = woo.test_connection()
            status["woocommerce"]["status"] = "ready" if test_result.get("success") else "error"
        except Exception as e:
            status["woocommerce"]["status"] = f"error: {e}"

    return status


@router.post("/shopify/publish/{product_id}")
async def publish_shopify_product(
    product_id: int,
    user: TokenPayload = Depends(require_auth),
    settings: Settings = Depends(get_settings)
):
    """
    Publish a draft Shopify product (make it live)
    
    [SECURE] Requires authentication
    """
    shopify = get_shopify_deployer(settings)

    if not shopify:
        raise HTTPException(status_code=400, detail="Shopify not configured")

    result = await shopify.publish_product(product_id)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    return result


@router.put("/inventory/update")
async def update_inventory(
    platform: str,
    product_id: str,
    quantity: int,
    user: TokenPayload = Depends(require_auth),
    settings: Settings = Depends(get_settings)
):
    """
    Update inventory quantity across platforms

    Platforms: shopify, amazon, woocommerce
    
    [SECURE] Requires authentication
    """
    if platform == "shopify":
        shopify = get_shopify_deployer(settings)
        if not shopify:
            raise HTTPException(status_code=400, detail="Shopify not configured")

        await shopify.update_inventory(int(product_id), quantity)
        return {"success": True, "platform": "shopify", "product_id": product_id, "quantity": quantity}

    elif platform == "amazon":
        amazon = get_amazon_client(settings)
        if not amazon:
            raise HTTPException(status_code=400, detail="Amazon not configured")

        result = await amazon.update_inventory(product_id, quantity)
        return result

    elif platform == "woocommerce":
        woo = get_woocommerce_client(settings=settings)
        if not woo:
            raise HTTPException(status_code=400, detail="WooCommerce not configured")

        result = await woo.update_stock(int(product_id), quantity)
        return result

    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")


@router.get("/health")
async def deployment_health_check():
    """
    Health check for deployment service
    
    [WARNING] Public endpoint (no auth required)
    """
    return {
        "status": "healthy",
        "service": "Product Deployment API",
        "platforms": ["shopify", "amazon", "woocommerce"]
    }
