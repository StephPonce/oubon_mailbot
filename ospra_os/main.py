from fastapi import FastAPI, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from ospra_os.core.settings import Settings, get_settings
from pathlib import Path

# Gmail OAuth router (optional)
try:
    from ospra_os.gmail.routes import router as gmail_oauth_router  # type: ignore
    print("✅ Gmail OAuth router loaded successfully")
except Exception as e:
    print(f"⚠️  Gmail OAuth router not loaded: {e}")
    gmail_oauth_router = None

# TikTok router is optional — don't crash if it's not present
try:
    from ospra_os.tiktok.routes import router as tiktok_router  # type: ignore
    _HAS_TIKTOK = True
    print("✅ TikTok router loaded successfully")
except Exception as e:  # ImportError, etc.
    print(f"⚠️  TikTok router not loaded: {e}")
    print("   This is expected if TikTok integration is not yet enabled")
    tiktok_router = None
    _HAS_TIKTOK = False

# Product Research router
try:
    from ospra_os.product_research.routes import router as research_router  # type: ignore
    _HAS_RESEARCH = True
    print("✅ Product Research router loaded successfully")
except Exception as e:
    print(f"⚠️  Product Research router not loaded: {e}")
    research_router = None
    _HAS_RESEARCH = False

# Admin Dashboard router
try:
    from ospra_os.admin.routes import router as admin_router  # type: ignore
    _HAS_ADMIN = True
    print("✅ Admin Dashboard router loaded successfully")
except Exception as e:
    print(f"⚠️  Admin Dashboard router not loaded: {e}")
    admin_router = None
    _HAS_ADMIN = False

# AliExpress OAuth router
try:
    from ospra_os.aliexpress.routes import router as aliexpress_router  # type: ignore
    _HAS_ALIEXPRESS = True
    print("✅ AliExpress OAuth router loaded successfully")
except Exception as e:
    print(f"⚠️  AliExpress OAuth router not loaded: {e}")
    aliexpress_router = None
    _HAS_ALIEXPRESS = False

# Import GmailClient for the OAuth callback
try:
    from app.gmail_client import GmailClient
    print("✅ GmailClient loaded from app.gmail_client")
except Exception as e:
    print(f"⚠️  Could not import GmailClient: {e}")
    GmailClient = None

app = FastAPI(title="OspraOS API", version="0.1")

# Trust proxy headers from Render (for HTTPS URL generation)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# ---------------------------------------------------------------
# Startup Event - Initialize DBs and Scheduler
# ---------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    """Initialize databases and start background scheduler."""
    settings = get_settings()

    # Initialize follow-up tracking database
    try:
        from app.models import init_followup_db
        init_followup_db(settings.database_url)
        print("✅ Follow-up database initialized")
    except Exception as e:
        print(f"⚠️  Follow-up database initialization failed: {e}")

    # Initialize analytics database
    try:
        from app.analytics import init_analytics_db
        init_analytics_db(settings.database_url)
        print("✅ Analytics database initialized")
    except Exception as e:
        print(f"⚠️  Analytics database initialization failed: {e}")

    # Initialize AliExpress OAuth database
    try:
        from ospra_os.aliexpress.oauth import init_aliexpress_oauth_db
        init_aliexpress_oauth_db(settings.database_url)
        print("✅ AliExpress OAuth database initialized")
    except Exception as e:
        print(f"⚠️  AliExpress OAuth database initialization failed: {e}")

    # Start background email checker
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
        print("✅ Background scheduler started")
    except Exception as e:
        print(f"⚠️  Scheduler failed to start: {e}")

if gmail_oauth_router:
    app.include_router(gmail_oauth_router)  # exposes /gmail/auth/*

if _HAS_TIKTOK and tiktok_router:
    app.include_router(tiktok_router)

if _HAS_RESEARCH and research_router:
    app.include_router(research_router)  # exposes /research/*

if _HAS_ADMIN and admin_router:
    app.include_router(admin_router)  # exposes /admin/*

if _HAS_ALIEXPRESS and aliexpress_router:
    app.include_router(aliexpress_router)  # exposes /aliexpress/*

# keep a root-level callback because your Google OAuth client JSON often points here
@app.get("/oauth2callback", include_in_schema=False)
def oauth_cb_root(code: str, settings: Settings = Depends(get_settings)):
    if GmailClient is None:
        return {"error": "GmailClient not available"}
    gc = GmailClient(settings)
    gc.exchange_code_for_tokens(code)
    return RedirectResponse(url="/admin/dashboard")

# Health check endpoint for Render
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "OspraOS",
        "gmail_oauth_loaded": gmail_oauth_router is not None,
        "gmail_client_loaded": GmailClient is not None,
        "tiktok_loaded": _HAS_TIKTOK,
        "product_research_loaded": _HAS_RESEARCH,
        "aliexpress_oauth_loaded": _HAS_ALIEXPRESS
    }

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Analytics dashboard with charts and visualizations."""
    dashboard_path = Path(__file__).parent.parent / "static" / "dashboard.html"
    if not dashboard_path.exists():
        return HTMLResponse("<h1>Dashboard not found</h1><p>Please ensure static/dashboard.html exists</p>", status_code=404)
    with open(dashboard_path, "r") as f:
        return HTMLResponse(content=f.read())

# ---------------------------------------------------------------
# Dashboard API Endpoints (New Unified Dashboard)
# ---------------------------------------------------------------
@app.get("/api/dashboard/overview")
async def get_dashboard_overview(settings: Settings = Depends(get_settings)):
    """
    Dashboard overview with system stats.

    Returns:
    - Total products discovered
    - Total emails processed
    - Active API connections
    - System health
    """
    try:
        from app.analytics import Analytics

        analytics = Analytics(settings.database_url)

        # Get email stats
        daily_stats = analytics.get_daily_stats()
        weekly_stats = analytics.get_weekly_stats()

        # Count active API connections
        active_apis = {
            "gmail": GmailClient is not None,
            "openai": settings.OPENAI_API_KEY is not None,
            "anthropic": settings.ANTHROPIC_API_KEY is not None,
            "reddit": settings.REDDIT_CLIENT_ID is not None,
            "google_trends": True,  # No API key needed
            "shopify": settings.SHOPIFY_STORE_DOMAIN is not None,
            "aliexpress": settings.ALIEXPRESS_API_KEY is not None,
        }

        active_count = sum(1 for v in active_apis.values() if v)

        return {
            "system_health": "online",
            "email_stats": {
                "processed_today": daily_stats.get("total_processed", 0),
                "processed_week": weekly_stats.get("total_processed", 0),
                "auto_replied_today": daily_stats.get("auto_replied", 0),
            },
            "products_discovered": 0,  # TODO: Track in database
            "active_apis": active_count,
            "total_apis": len(active_apis),
            "api_details": active_apis,
            "timestamp": "2025-10-28",
        }
    except Exception as e:
        return {"error": str(e), "system_health": "degraded"}


@app.get("/api/dashboard/products")
async def get_dashboard_products(
    limit: int = 20,
    min_score: float = 0.0,
    settings: Settings = Depends(get_settings)
):
    """
    Get product discovery results with scores.

    Returns recent product research results from database or live search.
    """
    try:
        # For now, return empty list - will be populated when users run product discovery
        # TODO: Store discovered products in database and retrieve them here
        return {
            "total": 0,
            "products": [],
            "message": "Run product discovery to see results here"
        }
    except Exception as e:
        return {"error": str(e), "products": []}


@app.get("/api/dashboard/emails")
async def get_dashboard_emails(settings: Settings = Depends(get_settings)):
    """
    Email analytics dashboard.

    Returns:
    - Processed emails count
    - Category breakdown
    - Recent emails
    - Response stats
    """
    try:
        from app.analytics import Analytics

        analytics = Analytics(settings.database_url)

        # Get stats
        daily = analytics.get_daily_stats()
        weekly = analytics.get_weekly_stats()
        labels = analytics.get_top_labels(days=7)

        return {
            "summary": {
                "processed_today": daily.get("total_processed", 0),
                "processed_week": weekly.get("total_processed", 0),
                "auto_replied_today": daily.get("auto_replied", 0),
                "auto_replied_week": weekly.get("auto_replied", 0),
            },
            "categories": labels.get("labels", []),
            "response_rate": daily.get("auto_reply_rate", 0),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/dashboard/shopify")
async def get_dashboard_shopify(settings: Settings = Depends(get_settings)):
    """
    Shopify integration dashboard.

    Returns:
    - Store info
    - Recent orders
    - Revenue stats
    - Product count
    """
    try:
        # Check if Shopify is configured
        if not settings.SHOPIFY_STORE_DOMAIN:
            return {
                "connected": False,
                "message": "Shopify not configured. Set OUBONSHOP_SHOPIFY_STORE_DOMAIN and OUBONSHOP_SHOPIFY_ADMIN_TOKEN"
            }

        from app.shopify_client import ShopifyClient
        import requests

        # Get API token
        api_token = getattr(settings, "SHOPIFY_ADMIN_TOKEN", None) or getattr(settings, "SHOPIFY_API_TOKEN", None)

        if not api_token:
            return {
                "connected": False,
                "message": "Shopify API token not configured"
            }

        client = ShopifyClient(settings)

        # Get store info
        store_url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}/shop.json"
        store_response = requests.get(store_url, headers=client.headers, timeout=10)

        if store_response.status_code != 200:
            return {
                "connected": False,
                "error": f"Failed to connect: HTTP {store_response.status_code}"
            }

        shop = store_response.json()["shop"]

        # Get recent orders
        orders_url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}/orders.json?limit=10&status=any"
        orders_response = requests.get(orders_url, headers=client.headers, timeout=10)
        orders = orders_response.json().get("orders", []) if orders_response.status_code == 200 else []

        # Calculate revenue
        total_revenue = sum(float(order.get("total_price", 0)) for order in orders)

        return {
            "connected": True,
            "store": {
                "name": shop.get("name"),
                "email": shop.get("email"),
                "domain": shop.get("domain"),
                "currency": shop.get("currency"),
            },
            "orders": {
                "total_recent": len(orders),
                "total_revenue": round(total_revenue, 2),
                "recent_orders": [
                    {
                        "order_name": o.get("name"),
                        "total": float(o.get("total_price", 0)),
                        "status": o.get("financial_status"),
                        "created_at": o.get("created_at"),
                    }
                    for o in orders[:5]
                ]
            }
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


@app.get("/api/dashboard/api-status")
async def get_api_status(settings: Settings = Depends(get_settings)):
    """
    Check health of all API integrations.

    Returns status for:
    - Gmail
    - OpenAI/Anthropic
    - Reddit
    - Google Trends
    - Shopify
    - AliExpress
    """
    try:
        status_checks = []

        # Gmail
        gmail_configured = GmailClient is not None
        status_checks.append({
            "name": "Gmail API",
            "status": "connected" if gmail_configured else "not_configured",
            "health": "healthy" if gmail_configured else "unavailable",
        })

        # OpenAI
        openai_configured = settings.OPENAI_API_KEY is not None
        status_checks.append({
            "name": "OpenAI API",
            "status": "connected" if openai_configured else "not_configured",
            "health": "healthy" if openai_configured else "unavailable",
        })

        # Anthropic
        anthropic_configured = settings.ANTHROPIC_API_KEY is not None
        status_checks.append({
            "name": "Anthropic API",
            "status": "connected" if anthropic_configured else "not_configured",
            "health": "healthy" if anthropic_configured else "unavailable",
        })

        # Reddit
        reddit_configured = settings.REDDIT_CLIENT_ID is not None and settings.REDDIT_SECRET is not None
        status_checks.append({
            "name": "Reddit API",
            "status": "connected" if reddit_configured else "not_configured",
            "health": "healthy" if reddit_configured else "unavailable",
        })

        # Google Trends (always available)
        status_checks.append({
            "name": "Google Trends",
            "status": "connected",
            "health": "healthy",
        })

        # Shopify
        shopify_configured = settings.SHOPIFY_STORE_DOMAIN is not None
        status_checks.append({
            "name": "Shopify API",
            "status": "connected" if shopify_configured else "not_configured",
            "health": "healthy" if shopify_configured else "unavailable",
        })

        # AliExpress
        aliexpress_configured = settings.ALIEXPRESS_API_KEY is not None
        status_checks.append({
            "name": "AliExpress API",
            "status": "connected" if aliexpress_configured else "not_configured",
            "health": "healthy" if aliexpress_configured else "unavailable",
        })

        # Calculate overall health
        healthy_count = sum(1 for s in status_checks if s["health"] == "healthy")
        total_count = len(status_checks)

        return {
            "overall_health": "healthy" if healthy_count >= 4 else "degraded",
            "healthy_apis": healthy_count,
            "total_apis": total_count,
            "apis": status_checks,
        }
    except Exception as e:
        return {"error": str(e), "overall_health": "error"}


@app.post("/api/discover")
async def discover_products_api(
    niche: str,
    max_results: int = 15,
    min_score: float = 5.0,
    include_reddit: bool = True,
    include_trends: bool = True,
    include_aliexpress: bool = False,
    settings: Settings = Depends(get_settings)
):
    """
    Run product discovery engine for a niche.

    This is the main endpoint for the new ProductDiscoveryEngine.

    Example request body:
        {
            "niche": "smart home devices",
            "max_results": 15,
            "min_score": 5.0,
            "include_reddit": true,
            "include_trends": true,
            "include_aliexpress": false
        }

    Returns:
        {
            "niche": str,
            "total_found": int,
            "high_priority": int,
            "medium_priority": int,
            "low_priority": int,
            "products": [...],
            "search_time": str
        }
    """
    try:
        from ospra_os.product_research.discovery import ProductDiscoveryEngine

        # Initialize engine
        engine = ProductDiscoveryEngine(
            reddit_client_id=settings.REDDIT_CLIENT_ID,
            reddit_secret=settings.REDDIT_SECRET,
            aliexpress_api_key=settings.ALIEXPRESS_API_KEY,
            aliexpress_app_secret=settings.ALIEXPRESS_APP_SECRET,
        )

        # Run discovery
        results = await engine.discover(
            niche=niche,
            max_results=max_results,
            min_score=min_score,
            include_reddit=include_reddit,
            include_trends=include_trends,
            include_aliexpress=include_aliexpress,
        )

        return results

    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "niche": niche,
            "total_found": 0,
        }


@app.post("/api/validate-product")
async def validate_product_api(
    product_name: str,
    settings: Settings = Depends(get_settings)
):
    """
    Validate a specific product idea.

    Example request body:
        {
            "product_name": "wireless charging pad"
        }

    Returns validation report with Reddit mentions, trends data, and sourcing.
    """
    try:
        from ospra_os.product_research.discovery import ProductDiscoveryEngine

        engine = ProductDiscoveryEngine(
            reddit_client_id=settings.REDDIT_CLIENT_ID,
            reddit_secret=settings.REDDIT_SECRET,
            aliexpress_api_key=settings.ALIEXPRESS_API_KEY,
            aliexpress_app_secret=settings.ALIEXPRESS_APP_SECRET,
        )

        validation = await engine.validate_product(product_name)
        return validation

    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "product_name": product_name,
        }


@app.post("/api/discover-multi")
async def discover_multi_niche(
    min_score: float = 7.0,
    max_per_niche: int = 5,
    top_overall: int = 20,
    settings: Settings = Depends(get_settings)
):
    """
    🔥 Discover products across ALL niches in parallel.

    This endpoint searches 10+ profitable niches simultaneously:
    - Smart Lighting
    - Home Security
    - Cleaning Gadgets
    - Kitchen Tech
    - Fitness Gadgets
    - Phone Accessories
    - Car Accessories
    - Pet Products
    - Gaming Accessories
    - Outdoor Gear

    Returns top products from each niche + overall top products.

    Example request body:
    {
        "min_score": 7.0,
        "max_per_niche": 5,
        "top_overall": 20
    }

    Returns:
    {
        "success": true,
        "total_products": 50,
        "niches_discovered": 10,
        "top_overall": [...],  // Top 20 products across all niches
        "by_niche": {          // Products organized by niche
            "smart_lighting": [...],
            "home_security": [...],
            ...
        },
        "stats": {
            "niches_searched": 10,
            "high_priority": 15,
            "medium_priority": 20,
            "low_priority": 15
        }
    }
    """
    try:
        from ospra_os.product_research.niche_discovery import MultiNicheDiscovery

        # Initialize multi-niche discovery
        discovery = MultiNicheDiscovery(
            reddit_client_id=settings.REDDIT_CLIENT_ID,
            reddit_secret=settings.REDDIT_SECRET,
            aliexpress_api_key=settings.ALIEXPRESS_API_KEY,
            aliexpress_app_secret=settings.ALIEXPRESS_APP_SECRET,
        )

        # Run parallel discovery across all niches
        niche_products = await discovery.discover_all_niches(
            min_score=min_score,
            max_per_niche=max_per_niche
        )

        # Get top products overall
        top_products = discovery.get_top_products_overall(
            niche_products=niche_products,
            limit=top_overall
        )

        # Get statistics
        stats = discovery.get_stats(niche_products)

        return {
            "success": True,
            "total_products": stats["total_products"],
            "niches_discovered": stats["niches_with_products"],
            "top_overall": top_products,
            "by_niche": niche_products,
            "stats": {
                "niches_searched": stats["niches_searched"],
                "min_score": min_score,
                "products_per_niche": max_per_niche,
                "high_priority": stats["high_priority"],
                "medium_priority": stats["medium_priority"],
                "low_priority": stats["low_priority"],
            }
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "total_products": 0,
            "niches_discovered": 0,
        }


# ---------------------------------------------------------------
# Analytics API Endpoints (Legacy)
# ---------------------------------------------------------------
@app.get("/analytics/daily")
def analytics_daily(settings: Settings = Depends(get_settings)):
    """Get today's email processing statistics."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_daily_stats()

@app.get("/analytics/weekly")
def analytics_weekly(settings: Settings = Depends(get_settings)):
    """Get last 7 days of statistics."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_weekly_stats()

@app.get("/analytics/costs")
def analytics_costs(days: int = 30, settings: Settings = Depends(get_settings)):
    """Get AI cost breakdown for the last N days."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_cost_breakdown(days=days)

@app.get("/analytics/labels")
def analytics_labels(days: int = 7, settings: Settings = Depends(get_settings)):
    """Get most common email categories."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_top_labels(days=days)

@app.get("/analytics/cache-stats")
def cache_stats():
    """Get response cache statistics."""
    from app.response_cache import get_cache_stats
    return get_cache_stats()

# (optional) quick route list for sanity checks
@app.get("/debug/routes", include_in_schema=False)
def debug_routes():
    return sorted([r.path for r in app.routes])

@app.get("/debug/scheduler", include_in_schema=False)
def debug_scheduler():
    """Check scheduler status and run a manual email check."""
    try:
        from app.scheduler import check_emails_job
        # Try to run the job manually
        check_emails_job()
        return {"status": "ok", "message": "Email check job executed"}
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/debug/check-inbox", include_in_schema=False)
def debug_check_inbox(settings: Settings = Depends(get_settings)):
    """Show what emails are in inbox and would be processed."""
    try:
        from app.gmail_client import GmailClient
        gc = GmailClient(settings)
        svc = gc.service()

        # Same query as email processor
        query = 'in:inbox (is:unread OR "order" OR "package" OR "delivery" OR "tracking" OR "shipment" OR "refund" OR "return" OR "damaged" OR "broken")'

        result = svc.users().messages().list(
            userId="me",
            q=query,
            maxResults=10
        ).execute()

        messages = result.get("messages", [])

        email_list = []
        for msg in messages[:5]:  # Only process first 5 for debug
            full_msg = svc.users().messages().get(userId="me", id=msg["id"], format="full").execute()
            headers = {h["name"].lower(): h["value"] for h in full_msg.get("payload", {}).get("headers", [])}

            email_list.append({
                "id": msg["id"],
                "subject": headers.get("subject", ""),
                "from": headers.get("from", ""),
                "date": headers.get("date", ""),
            })

        return {
            "status": "ok",
            "query": query,
            "total_found": len(messages),
            "sample_emails": email_list
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

# Mount static files (must be last)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    print(f"⚠️  Static files not mounted: {e}")
