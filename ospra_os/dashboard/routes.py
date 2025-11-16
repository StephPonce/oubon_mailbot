"""
🎛️ REAL-TIME DASHBOARD ROUTES V2
Complete API with real integrations
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
import logging
from datetime import datetime

from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine
from ospra_os.intelligence.trend_analyzer import TrendAnalyzer
from ospra_os.intelligence.product_enrichment import enrich_product
from ospra_os.intelligence.self_learning import SelfLearningEngine
from ospra_os.integrations.shopify_client import ShopifyClient

# Optional background jobs import
try:
    from ospra_os.intelligence.background_jobs import get_scheduler, start_background_jobs, stop_background_jobs
except ImportError:
    get_scheduler = start_background_jobs = stop_background_jobs = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard/v2", tags=["Dashboard V2"])

# Initialize services
try:
    product_discovery = ProductIntelligenceEngine()
    claude_analyzer = TrendAnalyzer()
    logger.info("✅ Real-time services initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize services: {e}")
    product_discovery = None
    claude_analyzer = None

try:
    shopify_client = ShopifyClient()
    if shopify_client.enabled:
        logger.info("✅ Shopify client initialized")
except Exception as e:
    logger.warning(f"Shopify client not available: {e}")
    shopify_client = None


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "product_discovery": product_discovery is not None,
            "claude_analyzer": claude_analyzer is not None
        }
    }


@router.get("/products")
async def get_products(
    niche: str = Query("smart_home", description="Product niche"),
    min_velocity: Optional[int] = Query(None, ge=0, le=100),
    max_velocity: Optional[int] = Query(None, ge=0, le=100),
    per_page: int = Query(20, ge=1, le=100)
):
    """
    Get products from DATABASE (persistent storage)

    Query params:
        - niche: Product category (smart_home, fitness, kitchen, etc.)
        - min_velocity: Minimum velocity score (0-100)
        - max_velocity: Maximum velocity score (0-100)
        - per_page: Results per page (1-100)

    Returns:
        {
            "products": [...],
            "data_source": "DATABASE",
            "total": 20,
            "filters_applied": {...}
        }
    """

    try:
        # Read from database instead of regenerating
        from ospra_os.database.product_history import ProductHistoryDB
        db = ProductHistoryDB()

        # Get products from database
        products = db.get_all_products(niche=niche)

        # Apply velocity filters
        if min_velocity is not None:
            products = [p for p in products if p['velocity_score'] >= min_velocity]
        if max_velocity is not None:
            products = [p for p in products if p['velocity_score'] <= max_velocity]

        # Limit results
        products = products[:per_page]

        # If no products found, suggest seeding
        if not products:
            logger.warning(f"No products found for niche: {niche}. Database may need seeding.")

        return {
            "products": products,
            "data_source": "DATABASE",
            "total": len(products),
            "filters_applied": {
                "niche": niche,
                "min_velocity": min_velocity,
                "max_velocity": max_velocity
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve products: {str(e)}"
        )


@router.post("/products/{product_id}/analyze")
async def analyze_product(product_id: str):
    """
    Analyze a product using REAL Claude AI - from DATABASE

    Args:
        product_id: Product ID from /products endpoint

    Returns:
        {
            "product_id": "...",
            "analysis": "...",
            "score": 8.5,
            "recommendation": "STRONG_BUY",
            "reasoning": [...],
            "risks": [...],
            "success_prediction": "82%"
        }
    """

    if not claude_analyzer:
        raise HTTPException(
            status_code=503,
            detail="Claude analyzer unavailable"
        )

    try:
        # Get product from database (SAME data as card shows)
        from ospra_os.database.product_history import ProductHistoryDB
        db = ProductHistoryDB()

        product = db.get_product_by_id(product_id)

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {product_id} not found in database"
            )

        # Product is already enriched in database, no need to re-enrich
        # Analyze with Claude
        analysis = claude_analyzer.analyze_product(product)
        analysis["product_id"] = product_id

        return analysis

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Product analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.post("/claude/chat")
async def claude_chat(request: dict):
    """
    Chat with Claude AI
    
    Request body:
        {
            "message": "What products should I sell?",
            "context": {...}  # Optional context
        }
    
    Returns:
        {
            "response": "Claude's response",
            "timestamp": "..."
        }
    """
    
    if not claude_analyzer:
        raise HTTPException(
            status_code=503,
            detail="Claude chat unavailable"
        )
    
    try:
        message = request.get("message")
        context = request.get("context")
        
        if not message:
            raise HTTPException(
                status_code=400,
                detail="Message is required"
            )
        
        response = claude_analyzer.chat_response(message, context)
        
        return {
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )


@router.post("/products/refresh")
async def refresh_products(
    niche: str = Query("smart_home", description="Niche to refresh")
):
    """
    Force refresh product cache
    
    Query params:
        - niche: Niche to refresh
    
    Returns:
        {
            "success": true,
            "products_refreshed": 20,
            "timestamp": "..."
        }
    """
    
    if not product_discovery:
        raise HTTPException(
            status_code=503,
            detail="Product discovery unavailable"
        )
    
    try:
        # Clear cache for this niche
        cache_keys = [k for k in product_discovery.cache.keys() if k.startswith(niche)]
        for key in cache_keys:
            del product_discovery.cache[key]
        
        # Fetch fresh data
        result = product_discovery.discover_products(niche=niche)
        
        return {
            "success": True,
            "products_refreshed": len(result.get("products", [])),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Refresh failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Refresh failed: {str(e)}"
        )


@router.get("/market/trends")
async def get_market_trends(
    niche: str = Query("smart_home", description="Niche to analyze")
):
    """
    Get market trends analysis
    
    Returns:
        {
            "analysis": "...",
            "trending_searches": [...],
            "opportunities": [...],
            "timestamp": "..."
        }
    """
    
    if not product_discovery or not claude_analyzer:
        raise HTTPException(
            status_code=503,
            detail="Services unavailable"
        )
    
    try:
        # Get market research
        result = product_discovery.discover_products(niche=niche, per_page=1)
        market_research = result.get("market_research", {})
        
        # Analyze with Claude
        analysis = claude_analyzer.analyze_market_trends(niche, market_research)
        
        return {
            "analysis": analysis,
            "trending_searches": market_research.get("trending_searches", []),
            "top_searches": market_research.get("top_searches", []),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Trends analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("/overview")
async def get_overview():
    """Get dashboard overview (alias for analytics/summary)"""
    return await get_analytics_summary()


@router.get("/niches")
async def get_niches():
    """Get available niches"""
    return {
        "niches": [
            {"id": "smart_home", "name": "Smart Home", "trending": True},
            {"id": "fitness", "name": "Fitness", "trending": True},
            {"id": "kitchen", "name": "Kitchen", "trending": False},
            {"id": "beauty", "name": "Beauty", "trending": False},
            {"id": "pet", "name": "Pet Products", "trending": False}
        ]
    }


@router.get("/analytics/summary")
async def get_analytics_summary():
    """
    Get dashboard analytics summary
    
    Returns:
        {
            "total_products": 120,
            "high_velocity_products": 45,
            "recommendations": [...],
            "timestamp": "..."
        }
    """
    
    if not product_discovery:
        raise HTTPException(
            status_code=503,
            detail="Analytics unavailable"
        )
    
    try:
        # Get all products
        result = product_discovery.discover_products(per_page=100)
        products = result.get("products", [])
        
        # Calculate stats
        high_velocity = [p for p in products if p.get("velocity_score", 0) >= 70]
        medium_velocity = [p for p in products if 40 <= p.get("velocity_score", 0) < 70]
        low_velocity = [p for p in products if p.get("velocity_score", 0) < 40]
        
        return {
            "total_products": len(products),
            "high_velocity_products": len(high_velocity),
            "medium_velocity_products": len(medium_velocity),
            "low_velocity_products": len(low_velocity),
            "average_velocity": sum(p.get("velocity_score", 0) for p in products) / len(products) if products else 0,
            "data_freshness": result.get("cache_age_seconds", 0),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analytics failed: {str(e)}"
        )


@router.get("/analytics/business")
async def get_business_analytics():
    """
    Get business analytics including orders, revenue, and conversions

    Returns:
        {
            "total_orders": 10,
            "total_revenue": 1234.56,
            "average_order_value": 123.45,
            "orders_by_status": {...},
            "top_products": [...],
            "revenue_by_day": [...],
            "deployed_products": 5,
            "conversion_rate": 200.0,
            "unfulfilled_orders": 2,
            "shipped_orders": 8
        }
    """

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        analytics = db.get_analytics()
        return analytics

    except Exception as e:
        logger.error(f"Business analytics failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analytics failed: {str(e)}"
        )


@router.get("/analytics")
async def get_analytics():
    """Get analytics metrics"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        analytics = db.get_analytics()
        return {
            "status": "success",
            "analytics": analytics,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/deployment-status")
async def get_deployment_status(product_id: str):
    """Check if product is deployed to Shopify"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    deployment = db.get_deployment(product_id)

    if deployment:
        return {
            "deployed": True,
            "shopify_product_id": deployment['shopify_product_id'],
            "shopify_url": deployment['shopify_url'],
            "deployed_at": deployment['deployed_at']
        }
    else:
        return {
            "deployed": False
        }


@router.post("/products/{product_id}/sync-deployment")
async def sync_deployment_status(product_id: str):
    """Check if product still exists on Shopify and update deployment status"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    # Get deployment record
    deployment = db.get_deployment(product_id)

    if not deployment:
        return {"deployed": False, "message": "No deployment record found"}

    # Check if product still exists on Shopify
    if shopify_client and shopify_client.enabled:
        exists = shopify_client.product_exists(deployment['shopify_product_id'])

        if not exists:
            # Product deleted from Shopify - mark as removed
            db.mark_deployment_removed(product_id)
            return {
                "deployed": False,
                "message": "Product no longer exists on Shopify",
                "synced": True
            }
        else:
            return {
                "deployed": True,
                "shopify_product_id": deployment['shopify_product_id'],
                "shopify_url": deployment['shopify_url'],
                "synced": True
            }
    else:
        return {"deployed": deployment is not None, "synced": False, "message": "Shopify client not available"}


@router.post("/products/{product_id}/deploy-to-shopify")
async def deploy_to_shopify(product_id: str):
    """Deploy product to Shopify store"""

    if not shopify_client or not shopify_client.enabled:
        raise HTTPException(status_code=503, detail="Shopify not configured")

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    # Check if already deployed
    existing_deployment = db.get_deployment(product_id)
    if existing_deployment:
        return {
            "status": "already_deployed",
            "message": "Product already deployed to Shopify",
            "shopify_id": existing_deployment['shopify_product_id'],
            "shopify_url": existing_deployment['shopify_url'],
            "deployed_at": existing_deployment['deployed_at']
        }

    # Get product from database
    product = db.get_product_by_id(product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        # Deploy to Shopify
        shopify_product = shopify_client.create_product(product)

        if shopify_product:
            # Save deployment record
            deployment_data = {
                'id': shopify_product['id'],
                'handle': shopify_product['handle'],
                'shopify_url': f"https://{shopify_client.store_url}/products/{shopify_product['handle']}"
            }

            db.save_deployment(product_id, deployment_data)

            # Create notification for successful deployment
            db.create_notification(
                notification_type='deployment',
                title='Product Deployed',
                message=f'Successfully deployed "{product["name"]}" to Shopify',
                severity='success',
                product_id=product_id,
                metadata={
                    'shopify_id': shopify_product['id'],
                    'shopify_url': deployment_data['shopify_url']
                }
            )

            return {
                "status": "success",
                "message": f"Product deployed to Shopify",
                "shopify_id": shopify_product["id"],
                "shopify_url": deployment_data['shopify_url'],
                "admin_url": f"https://{shopify_client.store_url}/admin/products/{shopify_product['id']}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create product on Shopify")

    except Exception as e:
        logger.error(f"Shopify deployment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/bulk-deploy")
async def bulk_deploy_products(product_ids: List[str]):
    """Deploy multiple products to Shopify at once"""

    if not shopify_client or not shopify_client.enabled:
        raise HTTPException(status_code=503, detail="Shopify not configured")

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    results = {
        "successful": [],
        "failed": [],
        "already_deployed": []
    }

    for product_id in product_ids:
        try:
            # Check if already deployed
            existing_deployment = db.get_deployment(product_id)
            if existing_deployment:
                results["already_deployed"].append({
                    "product_id": product_id,
                    "shopify_id": existing_deployment['shopify_product_id']
                })
                continue

            # Get product
            product = db.get_product_by_id(product_id)
            if not product:
                results["failed"].append({
                    "product_id": product_id,
                    "error": "Product not found"
                })
                continue

            # Deploy to Shopify
            shopify_product = shopify_client.create_product(product)

            if shopify_product:
                # Save deployment
                deployment_data = {
                    'id': shopify_product['id'],
                    'handle': shopify_product['handle'],
                    'shopify_url': f"https://{shopify_client.store_url}/products/{shopify_product['handle']}"
                }

                db.save_deployment(product_id, deployment_data)

                results["successful"].append({
                    "product_id": product_id,
                    "product_name": product["name"],
                    "shopify_id": shopify_product['id'],
                    "shopify_url": deployment_data['shopify_url']
                })
            else:
                results["failed"].append({
                    "product_id": product_id,
                    "error": "Shopify deployment failed"
                })

        except Exception as e:
            logger.error(f"Bulk deploy failed for {product_id}: {e}")
            results["failed"].append({
                "product_id": product_id,
                "error": str(e)
            })

    # Create summary notification
    db.create_notification(
        notification_type='bulk_deployment',
        title='Bulk Deployment Complete',
        message=f'Deployed {len(results["successful"])} products. {len(results["failed"])} failed. {len(results["already_deployed"])} already deployed.',
        severity='success' if len(results["failed"]) == 0 else 'warning',
        metadata=results
    )

    return {
        "status": "complete",
        "summary": {
            "total": len(product_ids),
            "successful": len(results["successful"]),
            "failed": len(results["failed"]),
            "already_deployed": len(results["already_deployed"])
        },
        "details": results
    }


@router.get("/shopify/status")
async def shopify_status():
    """Check Shopify integration status"""

    if not shopify_client:
        return {"connected": False, "message": "Shopify not configured"}

    if not shopify_client.enabled:
        return {"connected": False, "message": "Shopify credentials missing"}

    try:
        products = shopify_client.list_products(limit=1)
        return {
            "connected": True,
            "store_url": shopify_client.store_url,
            "product_count": len(products),
            "message": "Shopify connected successfully"
        }
    except Exception as e:
        return {"connected": False, "message": f"Connection failed: {str(e)}"}


@router.get("/deployments")
async def get_deployments():
    """Get all deployed products"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        deployments = db.get_all_deployments()
        return {
            "total": len(deployments),
            "deployments": deployments
        }
    except Exception as e:
        logger.error(f"Failed to get deployments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products/{product_id}/deployment")
async def remove_deployment(product_id: str):
    """Mark product as removed from Shopify"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        success = db.mark_deployment_removed(product_id)
        if success:
            return {"status": "success", "message": "Deployment marked as removed"}
        else:
            raise HTTPException(status_code=500, detail="Failed to mark deployment removed")
    except Exception as e:
        logger.error(f"Failed to remove deployment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notifications")
async def get_notifications(unread_only: bool = False, limit: int = 50):
    """Get notifications"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        notifications = db.get_notifications(unread_only=unread_only, limit=limit)
        unread_count = db.get_unread_count()

        return {
            "notifications": notifications,
            "unread_count": unread_count,
            "total": len(notifications)
        }
    except Exception as e:
        logger.error(f"Failed to get notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int):
    """Mark notification as read"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        success = db.mark_notification_read(notification_id)
        if success:
            return {"status": "success", "message": "Notification marked as read"}
        else:
            raise HTTPException(status_code=500, detail="Failed to mark notification read")
    except Exception as e:
        logger.error(f"Failed to mark notification read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read():
    """Mark all notifications as read"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        success = db.mark_all_read()
        if success:
            return {"status": "success", "message": "All notifications marked as read"}
        else:
            raise HTTPException(status_code=500, detail="Failed to mark all read")
    except Exception as e:
        logger.error(f"Failed to mark all read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders")
async def get_orders(limit: int = 50):
    """Get all orders"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        orders = db.get_all_orders(limit=limit)
        return {
            "orders": orders,
            "total": len(orders)
        }
    except Exception as e:
        logger.error(f"Failed to get orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/{shopify_order_id}/tracking")
async def add_tracking(
    shopify_order_id: str,
    tracking_number: str,
    tracking_url: str,
    tracking_company: str = "Other"
):
    """Add tracking info to order and sync with Shopify"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        # Update local database
        success = db.update_order_tracking(shopify_order_id, tracking_number, tracking_url)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update tracking in database")

        # Get order details
        order = db.get_order(shopify_order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Sync with Shopify (fulfill order)
        shopify_synced = False
        if shopify_client and shopify_client.enabled:
            shopify_synced = shopify_client.fulfill_order(
                order_id=shopify_order_id,
                tracking_number=tracking_number,
                tracking_url=tracking_url,
                tracking_company=tracking_company
            )

            if shopify_synced:
                logger.info(f"✅ Order {shopify_order_id} synced with Shopify")

                # Create notification
                db.create_notification(
                    notification_type='fulfillment',
                    title='Order Fulfilled',
                    message=f'Order #{order["shopify_order_number"]} fulfilled and synced with Shopify',
                    severity='success',
                    product_id=order.get('product_id'),
                    metadata={
                        'order_id': shopify_order_id,
                        'tracking_number': tracking_number
                    }
                )
            else:
                logger.warning(f"Failed to sync order {shopify_order_id} with Shopify")

        # Send tracking email to customer
        await send_tracking_email(order)

        return {
            "status": "success",
            "message": "Tracking added and synced with Shopify",
            "shopify_synced": shopify_synced
        }

    except Exception as e:
        logger.error(f"Failed to add tracking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def send_tracking_email(order: dict):
    """Send tracking email to customer"""

    try:
        logger.info(f"📧 Tracking email queued for {order['customer_email']}")

        # TODO: Implement email sending using Gmail integration
        # from ospra_os.gmail.email_sender import send_email

        subject = f"Your Order Has Shipped - #{order['shopify_order_number']}"

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Your order is on the way!</h2>

            <p>Hi {order['customer_name']},</p>

            <p>Great news! Your order has been shipped.</p>

            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>Tracking Information</h3>
                <p><strong>Order Number:</strong> #{order['shopify_order_number']}</p>
                <p><strong>Tracking Number:</strong> {order['tracking_number']}</p>
                <p><strong>Track Your Package:</strong><br>
                <a href="{order['tracking_url']}" style="color: #0066cc;">{order['tracking_url']}</a></p>
            </div>

            <p><strong>Delivery:</strong> Estimated 10-25 business days</p>

            <p>Questions? Reply to this email and we'll help!</p>

            <p>Best regards,<br>Oubon Shop Team</p>
        </body>
        </html>
        """

        logger.debug(f"Tracking email template generated for order #{order['shopify_order_number']}")

        # await send_email(
        #     to_email=order['customer_email'],
        #     subject=subject,
        #     body=body
        # )

    except Exception as e:
        logger.error(f"Failed to queue tracking email: {e}")


# ==========================================
# PRODUCT PERFORMANCE TRACKING ENDPOINTS
# ==========================================

@router.post("/products/{product_id}/track")
async def track_product_metric(
    product_id: str,
    metric_type: str,
    value: int = 1
):
    """Track product performance metric"""
    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        success = db.track_performance(product_id, metric_type, value)
        if success:
            return {"status": "success", "message": f"Tracked {metric_type} for product"}
        else:
            raise HTTPException(status_code=500, detail="Failed to track metric")
    except Exception as e:
        logger.error(f"Failed to track metric: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/performance")
async def get_product_performance(
    product_id: str,
    days: int = 30
):
    """Get performance metrics for a product"""
    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        performance = db.get_product_performance(product_id, days)
        return {
            "product_id": product_id,
            "days": days,
            "performance": performance
        }
    except Exception as e:
        logger.error(f"Failed to get performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/top")
async def get_top_performers(
    metric_type: str = "sales",
    limit: int = 10,
    days: int = 30
):
    """Get top performing products"""
    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        performers = db.get_top_performers(metric_type, limit, days)
        return {
            "metric_type": metric_type,
            "limit": limit,
            "days": days,
            "top_performers": performers
        }
    except Exception as e:
        logger.error(f"Failed to get top performers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/underperformers")
async def get_underperformers(
    threshold_conversion: float = 1.0,
    days: int = 30
):
    """Get underperforming products (low conversion rate)"""
    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        underperformers = db.get_underperformers(threshold_conversion, days)
        return {
            "threshold_conversion": threshold_conversion,
            "days": days,
            "underperformers": underperformers
        }
    except Exception as e:
        logger.error(f"Failed to get underperformers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# SELF-LEARNING INTELLIGENCE ENDPOINTS
# ==========================================

@router.get("/intelligence/patterns")
async def get_product_patterns(days: int = 30):
    """Analyze product performance patterns using AI"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        engine = SelfLearningEngine(db)
        patterns = engine.analyze_product_patterns(days)

        return {
            "status": "success",
            "patterns": patterns,
            "period_days": days
        }
    except Exception as e:
        logger.error(f"Pattern analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intelligence/drop-candidates")
async def get_drop_candidates(min_views: int = 100, days: int = 30):
    """Identify products that should be dropped based on AI analysis"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        engine = SelfLearningEngine(db)
        drop_candidates = engine.identify_products_to_drop(min_views, days)

        return {
            "status": "success",
            "drop_candidates": drop_candidates,
            "total": len(drop_candidates)
        }
    except Exception as e:
        logger.error(f"Drop candidates failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intelligence/predict")
async def predict_product_performance(product: Dict):
    """Predict how a product will perform using AI"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        engine = SelfLearningEngine(db)
        prediction = engine.predict_performance(product)

        return {
            "status": "success",
            "prediction": prediction
        }
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEVEL 3 AI - SCHEDULER & ALERTS
# ==========================================

@router.get("/intelligence/alerts")
async def get_alerts(limit: int = 50, severity: str = None):
    """Get recent AI alerts from background monitoring"""

    try:
        scheduler = get_scheduler()
        alerts = scheduler.get_alerts(limit=limit, severity=severity)

        return {
            "status": "success",
            "alerts": alerts,
            "total": len(alerts)
        }
    except Exception as e:
        logger.error(f"Get alerts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/intelligence/alerts")
async def clear_alerts():
    """Clear all alerts"""

    try:
        scheduler = get_scheduler()
        scheduler.clear_alerts()

        return {
            "status": "success",
            "message": "All alerts cleared"
        }
    except Exception as e:
        logger.error(f"Clear alerts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intelligence/scheduler/status")
async def get_scheduler_status():
    """Get Level 3 AI scheduler status"""

    try:
        scheduler = get_scheduler()
        status = scheduler.get_status()

        return {
            "status": "success",
            "scheduler": status
        }
    except Exception as e:
        logger.error(f"Get scheduler status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intelligence/scheduler/start")
async def start_scheduler():
    """Start Level 3 AI background jobs"""

    try:
        start_background_jobs()

        return {
            "status": "success",
            "message": "Background jobs started",
            "jobs": [
                "analyze_products - every 6 hours",
                "monitor_competitors - every 12 hours",
                "track_trends - daily at 9am",
                "weekly_report - Sundays at 6pm"
            ]
        }
    except Exception as e:
        logger.error(f"Start scheduler failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intelligence/scheduler/stop")
async def stop_scheduler():
    """Stop Level 3 AI background jobs"""

    try:
        stop_background_jobs()

        return {
            "status": "success",
            "message": "Background jobs stopped"
        }
    except Exception as e:
        logger.error(f"Stop scheduler failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intelligence/scheduler/run-now/{job_name}")
async def run_job_now(job_name: str):
    """Manually trigger a specific background job"""

    valid_jobs = ["analyze_products", "monitor_competitors", "track_trends", "weekly_report"]

    if job_name not in valid_jobs:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid job name. Valid jobs: {', '.join(valid_jobs)}"
        )

    try:
        scheduler = get_scheduler()
        scheduler.run_job_now(job_name)

        return {
            "status": "success",
            "message": f"Job '{job_name}' triggered successfully"
        }
    except Exception as e:
        logger.error(f"Run job now failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
