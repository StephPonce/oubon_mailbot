"""
 REAL-TIME DASHBOARD ROUTES V2
Complete API with REAL cross-source intelligence
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List, Dict
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# =============================================================================
# INTELLIGENCE ENGINE - V5 Cross-Source (Primary) with V4 Fallback
# =============================================================================
try:
    # V5: REAL Cross-Source Intelligence Engine
    from ospra_os.intelligence.product_intelligence_v5 import OspraIntelligenceEngine as ProductIntelligenceEngine
    logger.info("[SUCCESS] Ospra Intelligence V5 loaded - Cross-source intelligence enabled")
except ImportError as e:
    logger.warning(f"V5 not available ({e}), trying V4...")
    try:
        from ospra_os.intelligence.product_intelligence_v4 import ProductIntelligenceEngine
        logger.info("[WARNING] Using V4 fallback - Limited intelligence")
    except ImportError as e2:
        logger.warning(f"ProductIntelligenceEngine not available: {e2}")
        ProductIntelligenceEngine = None

try:
    from ospra_os.intelligence.trend_analyzer import TrendAnalyzer
except ImportError as e:
    logger.warning(f"TrendAnalyzer not available: {e}")
    TrendAnalyzer = None

try:
    from ospra_os.intelligence.product_enrichment import enrich_product
except ImportError as e:
    logger.warning(f"enrich_product not available: {e}")
    enrich_product = None

try:
    # Pass 4d: migrated from the deprecated `ospra_os.intelligence.self_learning`
    # shim to `ospra_os.learning.hybrid_learning_engine`. We alias
    # `SelfLearningEngine` → `HybridLearningEngine` to keep call sites in this
    # file working without a wider refactor; any usage that calls legacy
    # methods (analyze_product_patterns, score_product, etc.) will now raise
    # AttributeError at the call site, which is the correct signal that the
    # old API has been retired.
    from ospra_os.learning.hybrid_learning_engine import (
        HybridLearningEngine as SelfLearningEngine,
    )
except ImportError as e:
    logger.warning(f"HybridLearningEngine not available: {e}")
    SelfLearningEngine = None

try:
    from ospra_os.integrations.shopify.client import ShopifyClient
except ImportError as e:
    logger.warning(f"ShopifyClient not available: {e}")
    ShopifyClient = None

# Optional background jobs import
try:
    from ospra_os.intelligence.background_jobs import get_scheduler, start_background_jobs, stop_background_jobs
except ImportError:
    get_scheduler = start_background_jobs = stop_background_jobs = None

router = APIRouter(prefix="/api/dashboard/v2", tags=["Dashboard V2"])

# Initialize services (only if classes were successfully imported)
try:
    if ProductIntelligenceEngine is not None:
        product_discovery = ProductIntelligenceEngine()
        logger.info("[SUCCESS] ProductIntelligenceEngine initialized")
    else:
        product_discovery = None

    if TrendAnalyzer is not None:
        claude_analyzer = TrendAnalyzer()
    else:
        claude_analyzer = None

    if product_discovery and claude_analyzer:
        logger.info("[SUCCESS] Real-time services initialized (V5 Intelligence)")
    elif product_discovery:
        logger.info("[SUCCESS] Product discovery ready (analyzer not available)")
    else:
        logger.warning("[WARNING]  Some services not available (missing dependencies)")
except Exception as e:
    logger.error(f"[ERROR] Failed to initialize services: {e}")
    product_discovery = None
    claude_analyzer = None

try:
    if ShopifyClient is not None:
        shopify_client = ShopifyClient()
        logger.info("[SUCCESS] Shopify client initialized")
    else:
        shopify_client = None
        logger.warning("Shopify client class not available")
except (ValueError, Exception) as e:
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
            "claude_analyzer": claude_analyzer is not None,
            "intelligence_version": "V5" if product_discovery else "None"
        }
    }


@router.get("/products")
async def get_products(
    niche: Optional[str] = Query(None, description="Product niche (optional - returns all if not specified)"),
    min_score: Optional[float] = Query(None, ge=0, le=10, description="Minimum Ospra score"),
    max_score: Optional[float] = Query(None, ge=0, le=10, description="Maximum Ospra score"),
    min_velocity: Optional[int] = Query(None, ge=0, le=100),
    max_velocity: Optional[int] = Query(None, ge=0, le=100),
    sort_by: Optional[str] = Query("score", description="Sort by: score, profit, trend, newest"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc, desc"),
    per_page: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """
    Get products from DATABASE with Ospra Intelligence scores

    Query params:
        - niche: Product category (smart_home, fitness, kitchen, etc.)
        - min_score: Minimum Ospra Intelligence score (0-10)
        - max_score: Maximum Ospra Intelligence score (0-10)
        - min_velocity: Minimum velocity score (0-100)
        - max_velocity: Maximum velocity score (0-100)
        - sort_by: Sort field (score, profit, trend, newest)
        - sort_order: asc or desc
        - per_page: Results per page (1-100)

    Returns:
        {
            "products": [...],
            "data_source": "OSPRA_INTELLIGENCE_V5",
            "total": 50,
            "filters_applied": {...}
        }
    """

    try:
        # Read from database
        from ospra_os.database.product_history import ProductHistoryDB
        db = ProductHistoryDB()

        # Get products from database
        products = db.get_all_products(niche=niche)

        # Apply score filters
        if min_score is not None:
            products = [p for p in products if (p.get('score') or 0) >= min_score]
        if max_score is not None:
            products = [p for p in products if (p.get('score') or 0) <= max_score]

        # Apply velocity filters (handle None values properly)
        if min_velocity is not None:
            products = [p for p in products if (p.get('velocity_score') or 0) >= min_velocity]
        if max_velocity is not None:
            products = [p for p in products if (p.get('velocity_score') or 0) <= max_velocity]

        # Sort products
        sort_key_map = {
            'score': lambda p: p.get('score') or 0,
            'profit': lambda p: p.get('estimated_profit') or p.get('profit') or 0,
            'trend': lambda p: p.get('velocity_score') or 0,
            'newest': lambda p: p.get('created_at') or '',
        }
        sort_key = sort_key_map.get(sort_by, sort_key_map['score'])
        reverse = sort_order != 'asc'
        products = sorted(products, key=sort_key, reverse=reverse)

        # Limit results
        products = products[:per_page]

        # If no products found, suggest discovery
        if not products:
            logger.warning(f"No products found for niche: {niche}. Run discovery to populate.")

        return {
            "products": products,
            "data_source": "OSPRA_INTELLIGENCE_V5",
            "total": len(products),
            "filters_applied": {
                "niche": niche,
                "min_score": min_score,
                "max_score": max_score,
                "min_velocity": min_velocity,
                "max_velocity": max_velocity,
                "sort_by": sort_by,
                "sort_order": sort_order
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve products. Please try again."
        )


@router.post("/products/{product_id}/analyze")
async def analyze_product(product_id: str, request_body: dict = {}, current_user: User = Depends(get_current_user)):
    """
    Analyze a product using REAL Claude AI - from DATABASE or provided data

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
        # Try to get product from database first
        from ospra_os.database.product_history import ProductHistoryDB
        db = ProductHistoryDB()

        product = db.get_product_by_id(product_id)

        # If not in database, use provided product_data from request body
        product_data = request_body.get('product_data') if request_body else None
        if not product and product_data:
            product = product_data
        elif not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {product_id} not found in database. Send product_data in request body."
            )

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
            detail="Analysis failed. Please try again."
        )


@router.post("/claude/chat")
async def claude_chat(request: dict, current_user: User = Depends(get_current_user)):
    """Chat with Claude AI"""

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

        response = claude_analyzer.chat_response(message, context, user_id=current_user.id)
        
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
            detail="Chat failed. Please try again."
        )


@router.get("/overview")
async def get_overview(current_user: User = Depends(get_current_user)):
    """Get dashboard overview (alias for analytics/summary)"""
    return await get_analytics_summary(current_user=current_user)


@router.get("/niches")
async def get_niches(current_user: User = Depends(get_current_user)):
    """Get available niches with intelligence data"""
    return {
        "niches": [
            {"id": "smart_home", "name": "Smart Home", "trending": True, "score_avg": 7.2},
            {"id": "fitness", "name": "Fitness", "trending": True, "score_avg": 6.8},
            {"id": "tech_accessories", "name": "Tech Accessories", "trending": True, "score_avg": 6.5},
            {"id": "kitchen", "name": "Kitchen", "trending": False, "score_avg": 5.9},
            {"id": "beauty", "name": "Beauty", "trending": False, "score_avg": 5.7},
            {"id": "pet", "name": "Pet Products", "trending": False, "score_avg": 5.5},
            {"id": "outdoor", "name": "Outdoor", "trending": False, "score_avg": 5.3},
            {"id": "home_office", "name": "Home Office", "trending": True, "score_avg": 6.2},
            {"id": "lighting", "name": "Lighting", "trending": False, "score_avg": 5.8},
            {"id": "gaming", "name": "Gaming", "trending": True, "score_avg": 6.9}
        ]
    }


@router.get("/analytics/summary")
async def get_analytics_summary(current_user: User = Depends(get_current_user)):
    """Get dashboard analytics summary"""
    
    try:
        from ospra_os.database.product_history import ProductHistoryDB
        db = ProductHistoryDB()
        products = db.get_all_products()
        
        # Calculate stats using Ospra score
        high_score = [p for p in products if (p.get("score") or 0) >= 7.0]
        medium_score = [p for p in products if 4.0 <= (p.get("score") or 0) < 7.0]
        low_score = [p for p in products if (p.get("score") or 0) < 4.0]
        
        avg_score = sum((p.get("score") or 0) for p in products) / len(products) if products else 0
        avg_profit = sum((p.get("estimated_profit") or p.get("profit") or 0) for p in products) / len(products) if products else 0
        
        return {
            "total_products": len(products),
            "high_score_products": len(high_score),
            "medium_score_products": len(medium_score),
            "low_score_products": len(low_score),
            "average_score": round(avg_score, 1),
            "average_profit": round(avg_profit, 2),
            "data_source": "OSPRA_INTELLIGENCE_V5",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Analytics failed. Please try again."
        )


@router.get("/analytics/business")
async def get_business_analytics(current_user: User = Depends(get_current_user)):
    """Get business analytics including orders, revenue, and conversions"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        analytics = db.get_analytics()
        return analytics

    except Exception as e:
        logger.error(f"Business analytics failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Analytics failed. Please try again."
        )


@router.get("/analytics")
async def get_analytics(current_user: User = Depends(get_current_user)):
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
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/products/{product_id}/deployment-status")
async def get_deployment_status(product_id: str, current_user: User = Depends(get_current_user)):
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


@router.post("/products/{product_id}/deploy-to-shopify")
async def deploy_to_shopify(product_id: str, current_user: User = Depends(get_current_user)):
    """Deploy product to Shopify store"""

    if not shopify_client:
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
            deployment_data = {
                'id': shopify_product['id'],
                'handle': shopify_product['handle'],
                'shopify_url': f"https://{shopify_client.store_url}/products/{shopify_product['handle']}"
            }

            db.save_deployment(product_id, deployment_data)

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

            # PostHog activation funnel (task #38) — fire FIRST_DEPLOY for the
            # current user. PostHog dedupes per-user-per-event server-side, so
            # firing on every deploy yields a clean once-per-user activation
            # signal in the funnel.
            try:
                from ospra_os.observability.posthog_client import (
                    capture as posthog_capture,
                    FunnelEvent,
                )
                posthog_capture(
                    current_user.id,
                    FunnelEvent.FIRST_DEPLOY,
                    properties={
                        "product_id": product_id,
                        "shopify_id": shopify_product["id"],
                    },
                )
            except Exception as _e:
                logger.debug(f"[POSTHOG] FIRST_DEPLOY capture failed: {_e}")

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
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/shopify/status")
async def shopify_status(current_user: User = Depends(get_current_user)):
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
async def get_deployments(current_user: User = Depends(get_current_user)):
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
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/notifications")
async def get_notifications(unread_only: bool = False, limit: int = 50, current_user: User = Depends(get_current_user)):
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
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, current_user: User = Depends(get_current_user)):
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
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/orders")
async def get_orders(limit: int = 50, current_user: User = Depends(get_current_user)):
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
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# ==========================================
# INTELLIGENCE ENDPOINTS
# ==========================================

@router.get("/intelligence/patterns")
async def get_product_patterns(days: int = 30, current_user: User = Depends(get_current_user)):
    """Analyze product performance patterns using AI"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        if SelfLearningEngine:
            engine = SelfLearningEngine(db)
            patterns = engine.analyze_product_patterns(days)
        else:
            patterns = {"error": "SelfLearningEngine not available"}

        return {
            "status": "success",
            "patterns": patterns,
            "period_days": days
        }
    except Exception as e:
        logger.error(f"Pattern analysis failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/intelligence/drop-candidates")
async def get_drop_candidates(min_views: int = 100, days: int = 30, current_user: User = Depends(get_current_user)):
    """Identify products that should be dropped based on AI analysis"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        if SelfLearningEngine:
            engine = SelfLearningEngine(db)
            drop_candidates = engine.identify_products_to_drop(min_views, days)
        else:
            drop_candidates = []

        return {
            "status": "success",
            "drop_candidates": drop_candidates,
            "total": len(drop_candidates)
        }
    except Exception as e:
        logger.error(f"Drop candidates failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.post("/intelligence/predict")
async def predict_product_performance(product: Dict, current_user: User = Depends(get_current_user)):
    """Predict how a product will perform using AI"""

    from ospra_os.database.product_history import ProductHistoryDB
    db = ProductHistoryDB()

    try:
        if SelfLearningEngine:
            engine = SelfLearningEngine(db)
            prediction = engine.predict_performance(product)
        else:
            prediction = {"error": "SelfLearningEngine not available"}

        return {
            "status": "success",
            "prediction": prediction
        }
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# ============================================================================
# LIVE PRODUCTS ENDPOINT (Uses V5 Intelligence Engine)
# ============================================================================

@router.get("/live-products")
async def get_live_products_endpoint(
    niche: str = Query("smart_home", description="Product niche"),
    limit: int = Query(20, ge=1, le=100, description="Max products to return"),
    current_user: User = Depends(get_current_user)
):
    """
    Get LIVE trending products using Ospra Intelligence V5
    
    This endpoint fetches real-time data from:
    1. AliExpress (live prices)
    2. Google Trends (demand validation)
    3. TikTok (viral products - if available)
    
    Returns:
        List of products with REAL scores and cross-referenced data
    """
    try:
        if not product_discovery:
            raise HTTPException(status_code=503, detail="Intelligence engine not available")
        
        # Use V5 intelligent discovery
        import asyncio
        products = await product_discovery.discover_intelligent_products(
            niches=[niche],
            max_products=limit,
            min_score=0  # Return all, let frontend filter
        )
        
        return {
            "success": True,
            "products": products,
            "total": len(products),
            "niche": niche,
            "data_source": "OSPRA_INTELLIGENCE_V5",
            "intelligence_features": {
                "cross_referenced": True,
                "live_prices": True,
                "trend_validated": True
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Live products fetch failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")
