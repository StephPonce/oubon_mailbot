from fastapi import FastAPI, Depends, Body
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from ospra_os.core.settings import Settings, get_settings
from pathlib import Path
from typing import Optional, List, Dict
from pydantic import BaseModel
import logging

# Initialize logger
logger = logging.getLogger(__name__)

# New integrations - Platform Adapters, AI, Deployment, Auto-Discovery
try:
    from ospra_os.platforms.factory import PlatformFactory
    _HAS_PLATFORM_FACTORY = True
    print("✅ Platform Factory loaded successfully")
except Exception as e:
    print(f"⚠️  Platform Factory not loaded: {e}")
    PlatformFactory = None
    _HAS_PLATFORM_FACTORY = False

try:
    from ospra_os.deployment import UnifiedProductDeployer
    _HAS_UNIFIED_DEPLOYER = True
    print("✅ Unified Product Deployer loaded successfully")
except Exception as e:
    print(f"⚠️  Unified Product Deployer not loaded: {e}")
    UnifiedProductDeployer = None
    _HAS_UNIFIED_DEPLOYER = False

try:
    from ospra_os.ai.factory import AIFactory
    _HAS_AI_FACTORY = True
    print("✅ AI Factory loaded successfully")
except Exception as e:
    print(f"⚠️  AI Factory not loaded: {e}")
    AIFactory = None
    _HAS_AI_FACTORY = False

try:
    from ospra_os.background_jobs import start_auto_discovery_scheduler
    _HAS_AUTO_DISCOVERY = True
    print("✅ Auto-Discovery system loaded successfully")
except Exception as e:
    print(f"⚠️  Auto-Discovery not loaded: {e}")
    start_auto_discovery_scheduler = None
    _HAS_AUTO_DISCOVERY = False

try:
    from ospra_os.utils.health_monitor import HealthMonitor
    _HAS_HEALTH_MONITOR = True
    print("✅ Health Monitor loaded successfully")
except Exception as e:
    print(f"⚠️  Health Monitor not loaded: {e}")
    HealthMonitor = None
    _HAS_HEALTH_MONITOR = False

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

# Advertising Automation router
try:
    from ospra_os.advertising.routes import router as advertising_router  # type: ignore
    _HAS_ADVERTISING = True
    print("✅ Advertising Automation router loaded successfully")
except Exception as e:
    print(f"⚠️  Advertising router not loaded: {e}")
    advertising_router = None
    _HAS_ADVERTISING = False

# Email OAuth router (Multi-Provider Email OAuth)
try:
    from ospra_os.email_automation.oauth.routes import router as email_oauth_router  # type: ignore
    _HAS_EMAIL_OAUTH = True
    print("✅ Email OAuth router loaded successfully")
except Exception as e:
    print(f"⚠️  Email OAuth router not loaded: {e}")
    email_oauth_router = None
    _HAS_EMAIL_OAUTH = False

# Dashboard V2 router (Intelligence Platform) - REAL-TIME with Google Trends + Claude AI
try:
    from ospra_os.dashboard.routes import router as dashboard_v2_router  # type: ignore
    _HAS_DASHBOARD_V2 = True
    print("✅ Dashboard V2 REAL-TIME router loaded successfully")
except Exception as e:
    print(f"⚠️  Dashboard V2 REAL-TIME router not loaded: {e}")
    import traceback
    traceback.print_exc()
    dashboard_v2_router = None
    _HAS_DASHBOARD_V2 = False

# Multi-Store Portfolio router
try:
    from ospra_os.dashboard.routes_multi_store import router as multi_store_router  # type: ignore
    _HAS_MULTI_STORE = True
    print("✅ Multi-Store Portfolio router loaded successfully")
except Exception as e:
    print(f"⚠️  Multi-Store Portfolio router not loaded: {e}")
    multi_store_router = None
    _HAS_MULTI_STORE = False

# AliExpress OAuth router
try:
    from ospra_os.auth.aliexpress_oauth import router as aliexpress_router  # type: ignore
    _HAS_ALIEXPRESS = True
    print("✅ AliExpress OAuth router loaded successfully")
except Exception as e:
    print(f"⚠️  AliExpress OAuth router not loaded: {e}")
    aliexpress_router = None
    _HAS_ALIEXPRESS = False

# TikTok OAuth router
try:
    from ospra_os.auth.tiktok_oauth import router as tiktok_oauth_router  # type: ignore
    _HAS_TIKTOK_OAUTH = True
    print("✅ TikTok OAuth router loaded successfully")
except Exception as e:
    print(f"⚠️  TikTok OAuth router not loaded: {e}")
    tiktok_oauth_router = None
    _HAS_TIKTOK_OAUTH = False

# Shopify webhooks router
try:
    from ospra_os.webhooks.shopify_webhooks import router as shopify_webhooks_router  # type: ignore
    _HAS_SHOPIFY_WEBHOOKS = True
    print("✅ Shopify webhooks router loaded successfully")
except Exception as e:
    print(f"⚠️  Shopify webhooks router not loaded: {e}")
    shopify_webhooks_router = None
    _HAS_SHOPIFY_WEBHOOKS = False

# Shopify OAuth router
try:
    from ospra_os.platforms.shopify.oauth import router as shopify_oauth_router  # type: ignore
    _HAS_SHOPIFY_OAUTH = True
    print("✅ Shopify OAuth router loaded successfully")
except Exception as e:
    print(f"⚠️  Shopify OAuth router not loaded: {e}")
    shopify_oauth_router = None
    _HAS_SHOPIFY_OAUTH = False

# Deployment router (Unified Product Deployment)
try:
    from ospra_os.platforms.deployment_routes import router as deployment_router  # type: ignore
    _HAS_DEPLOYMENT = True
    print("✅ Deployment router loaded successfully")
except Exception as e:
    print(f"⚠️  Deployment router not loaded: {e}")
    deployment_router = None
    _HAS_DEPLOYMENT = False

# Import GmailClient for the OAuth callback
try:
    from app.gmail_client import GmailClient
    print("✅ GmailClient loaded from app.gmail_client")
except Exception as e:
    print(f"⚠️  Could not import GmailClient: {e}")
    GmailClient = None

app = FastAPI(title="OspraOS API", version="0.1")

# CORS middleware - Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",  # Alternative localhost
        "http://localhost:3000",  # Alternative dev server
        "https://policies.oubonshop.com",  # Production demo page
        "https://blond-ross-ticket-duplicate.trycloudflare.com",  # Cloudflare tunnel
        "https://app.oubonshop.com",  # Production app
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

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

    # Initialize Multi-Store database
    try:
        from ospra_os.database import init_multi_store_db
        init_multi_store_db(settings.database_url)
        print("✅ Multi-Store database initialized")
    except Exception as e:
        print(f"⚠️  Multi-Store database initialization failed: {e}")

    # Start background email checker
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
        print("✅ Background scheduler started")
    except Exception as e:
        print(f"⚠️  Scheduler failed to start: {e}")

    # Start product monitoring in background thread
    try:
        from ospra_os.background_jobs.product_monitor import ProductMonitor
        from threading import Thread
        import time
        import logging

        logger = logging.getLogger(__name__)
        monitor = ProductMonitor()

        def monitoring_task():
            """Background task to monitor product changes every 6 hours"""
            while True:
                try:
                    logger.info("🔍 Running product change detection...")
                    changes = monitor.check_all_products()

                    if changes:
                        logger.info(f"✅ Detected {len(changes)} product changes")
                        notification = monitor.format_notification(changes)
                        print(notification)

                        # Mark as notified
                        monitor.db.mark_all_notified()

                    # Show stats
                    stats = monitor.get_stats()
                    logger.info(f"📊 Monitor stats: {stats['tracked_products']} products tracked")

                except Exception as e:
                    logger.error(f"Product monitoring error: {e}")

                # Wait 6 hours
                time.sleep(6 * 60 * 60)

        # Start monitoring thread
        monitor_thread = Thread(target=monitoring_task, daemon=True)
        monitor_thread.start()
        print("✅ Product monitoring started (6-hour intervals)")

    except Exception as e:
        print(f"⚠️  Product monitoring failed to start: {e}")

    # Start Level 3 AI background jobs
    try:
        from ospra_os.intelligence.background_jobs import start_background_jobs
        import logging

        logger = logging.getLogger(__name__)

        start_background_jobs()
        logger.info("✅ Level 3 AI activated - background monitoring enabled")
        print("✅ Level 3 AI activated - background monitoring enabled")
    except Exception as e:
        print(f"⚠️  Level 3 AI not available - continuing without background monitoring: {e}")

    # Start auto-discovery background scheduler
    if _HAS_AUTO_DISCOVERY and start_auto_discovery_scheduler:
        try:
            import os
            # Check if auto-discovery is enabled in environment
            auto_discovery_enabled = os.getenv('AUTO_DISCOVERY_ENABLED', 'true').lower() == 'true'

            if auto_discovery_enabled and settings.database_url:
                discovery_hour = int(os.getenv('DISCOVERY_HOUR', '3'))  # Default: 3 AM
                discovery_interval = os.getenv('DISCOVERY_INTERVAL_HOURS')

                if discovery_interval:
                    # Interval-based scheduling
                    start_auto_discovery_scheduler(
                        database_url=settings.database_url,
                        interval_hours=int(discovery_interval)
                    )
                    print(f"✅ Auto-discovery scheduler started (every {discovery_interval} hours)")
                else:
                    # Daily scheduling
                    start_auto_discovery_scheduler(
                        database_url=settings.database_url,
                        hour=discovery_hour
                    )
                    print(f"✅ Auto-discovery scheduler started (daily at {discovery_hour:02d}:00)")
            else:
                print("⚠️  Auto-discovery disabled in environment or no database URL")
        except Exception as e:
            print(f"⚠️  Auto-discovery scheduler failed to start: {e}")
            import traceback
            traceback.print_exc()


# ---------------------------------------------------------------
# Shutdown Event - Stop Background Jobs
# ---------------------------------------------------------------
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    import logging

    logger = logging.getLogger(__name__)
    logger.info("⏸️  Shutting down Ospra Intelligence...")
    print("⏸️  Shutting down Ospra Intelligence...")

    # Stop Level 3 AI background jobs
    try:
        from ospra_os.intelligence.background_jobs import stop_background_jobs
        stop_background_jobs()
        logger.info("✅ Background jobs stopped")
        print("✅ Background jobs stopped")
    except Exception as e:
        logger.error(f"Error stopping background jobs: {e}")
        print(f"⚠️  Error stopping background jobs: {e}")


if gmail_oauth_router:
    app.include_router(gmail_oauth_router)  # exposes /gmail/auth/*

if _HAS_TIKTOK and tiktok_router:
    app.include_router(tiktok_router)

if _HAS_RESEARCH and research_router:
    app.include_router(research_router)  # exposes /research/*

if _HAS_ADMIN and admin_router:
    app.include_router(admin_router)  # exposes /admin/*

if _HAS_DASHBOARD_V2 and dashboard_v2_router:
    app.include_router(dashboard_v2_router)  # exposes /api/dashboard/v2/* (REAL-TIME)

if _HAS_MULTI_STORE and multi_store_router:
    app.include_router(multi_store_router)  # exposes /api/portfolio/*

if _HAS_ALIEXPRESS and aliexpress_router:
    app.include_router(aliexpress_router)  # exposes /api/aliexpress/*

if _HAS_TIKTOK_OAUTH and tiktok_oauth_router:
    app.include_router(tiktok_oauth_router)  # exposes /auth/tiktok/*

if _HAS_SHOPIFY_WEBHOOKS and shopify_webhooks_router:
    app.include_router(shopify_webhooks_router)  # exposes /webhooks/shopify/*

if _HAS_SHOPIFY_OAUTH and shopify_oauth_router:
    app.include_router(shopify_oauth_router)  # exposes /oauth/shopify/*

if _HAS_ADVERTISING and advertising_router:
    app.include_router(advertising_router)  # exposes /api/ads/*

if _HAS_EMAIL_OAUTH and email_oauth_router:
    app.include_router(email_oauth_router)  # exposes /api/email-oauth/*

if _HAS_DEPLOYMENT and deployment_router:
    app.include_router(deployment_router)  # exposes /api/deploy/*

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
        "service": "Ospra Intelligence Platform",
        "version": "2.0.0",
        "features": {
            "multi_store": _HAS_MULTI_STORE,
            "ai_abstraction": _HAS_AI_FACTORY,
            "platform_adapters": _HAS_PLATFORM_FACTORY,
            "auto_discovery": _HAS_AUTO_DISCOVERY,
            "unified_deployment": _HAS_UNIFIED_DEPLOYER,
            "product_research": _HAS_RESEARCH,
            "admin_dashboard": _HAS_ADMIN,
            "dashboard_v2": _HAS_DASHBOARD_V2
        },
        "integrations": {
            "gmail": gmail_oauth_router is not None,
            "shopify": _HAS_MULTI_STORE or _HAS_SHOPIFY_WEBHOOKS,
            "amazon": _HAS_PLATFORM_FACTORY,
            "woocommerce": _HAS_PLATFORM_FACTORY,
            "tiktok": _HAS_TIKTOK or _HAS_TIKTOK_OAUTH,
            "aliexpress": _HAS_ALIEXPRESS,
            "claude": _HAS_AI_FACTORY,
            "openai": _HAS_AI_FACTORY,
            "gemini": _HAS_AI_FACTORY
        },
        "legacy_status": {
            "gmail_oauth_loaded": gmail_oauth_router is not None,
            "gmail_client_loaded": GmailClient is not None,
            "tiktok_loaded": _HAS_TIKTOK,
            "tiktok_oauth_loaded": _HAS_TIKTOK_OAUTH,
            "product_research_loaded": _HAS_RESEARCH,
            "aliexpress_oauth_loaded": _HAS_ALIEXPRESS,
            "multi_store_loaded": _HAS_MULTI_STORE
        }
    }


@app.get("/api/health/detailed")
async def detailed_health_check(settings: Settings = Depends(get_settings)):
    """
    Comprehensive health check with detailed system monitoring.

    Returns:
    - Database connectivity status
    - AI provider availability
    - Platform adapter status
    - Background job status
    - System resource usage (CPU, memory, disk)
    """
    if not _HAS_HEALTH_MONITOR or not HealthMonitor:
        return {
            "success": False,
            "error": "Health Monitor not available",
            "basic_status": "ok" if True else "error"
        }

    try:
        monitor = HealthMonitor(settings.database_url)
        health_status = await monitor.check_system_health()
        return health_status
    except Exception as e:
        import traceback
        return {
            "success": False,
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# Admin & Testing Endpoints
# ---------------------------------------------------------------
@app.post("/api/admin/run-discovery-now")
async def run_discovery_now(settings: Settings = Depends(get_settings)):
    """
    Manual trigger for auto-discovery (for testing).

    Runs product discovery immediately for all active users.
    Useful for testing without waiting for the scheduled job.

    Returns:
        dict: Discovery results with products found, saved, deployed
    """
    if not _HAS_AUTO_DISCOVERY:
        return {
            "success": False,
            "error": "Auto-discovery system not available"
        }

    try:
        from ospra_os.background_jobs.auto_discovery import AutoDiscoveryJob

        # Create discovery job instance
        job = AutoDiscoveryJob(database_url=settings.database_url)

        # Run discovery for all users
        result = await job.run_discovery_for_all_users()

        return {
            "success": True,
            "message": "Discovery completed successfully",
            "results": result
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# Self-Learning System API Endpoints
# ---------------------------------------------------------------
@app.post("/api/learning/train")
async def train_learning_engine(
    sales_data: Optional[List[Dict]] = None,
    settings: Settings = Depends(get_settings)
):
    """
    Train self-learning engine with sales data

    Use this endpoint to:
    - Feed real Shopify sales data
    - Adjust AI confidence weights
    - Improve product predictions

    Returns: Learning cycle report
    """
    try:
        from ospra_os.learning.self_learning_engine import SelfLearningEngine
        from ospra_os.learning.performance_tracker import PerformanceTracker

        engine = SelfLearningEngine()

        # If no sales data provided, fetch from Shopify
        if not sales_data:
            tracker = PerformanceTracker()
            # TODO: Connect to real Shopify client
            sales_data = await tracker.get_learning_dataset()

        if not sales_data:
            # No data? Run demo
            report = await engine.simulate_learning_cycle()
        else:
            # Real data! Learn from it
            await engine.learn_from_sales(sales_data)
            report = await engine.get_learning_report()

        return {
            "success": True,
            "message": f"Learning cycle #{engine.weights['total_learning_cycles']} complete",
            "report": report
        }

    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/learning/report")
async def get_learning_report():
    """Get current learning engine status"""
    try:
        from ospra_os.learning.self_learning_engine import SelfLearningEngine

        engine = SelfLearningEngine()
        report = await engine.get_learning_report()

        return {"success": True, "report": report}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e)}


@app.get("/api/learning/velocity")
async def get_velocity_report():
    """
    Get trend velocity report

    Shows:
    - Early spike opportunities (catch products early!)
    - Declining products (remove from store)
    - Sustained growth products (keep selling)
    """
    try:
        from ospra_os.learning.trend_velocity_detector import TrendVelocityDetector

        detector = TrendVelocityDetector()
        report = await detector.get_velocity_report()

        return {"success": True, "report": report}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e)}


@app.post("/api/learning/demo")
async def run_learning_demo():
    """
    DEMO: Test learning system with sample data

    Run this BEFORE you have real sales to see how it works!
    """
    try:
        from ospra_os.learning.self_learning_engine import SelfLearningEngine

        # Run demo learning cycle
        engine = SelfLearningEngine()
        learning_report = await engine.simulate_learning_cycle()

        return {
            "success": True,
            "learning_report": learning_report,
            "message": "Demo complete! AI learned from sample data."
        }
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}

# ---------------------------------------------------------------
# NEW: Unified Deployment API Endpoints
# ---------------------------------------------------------------
@app.post("/api/deploy/product/{product_id}/to-store/{store_id}")
async def deploy_product_endpoint(
    product_id: int,
    store_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Deploy product to specific store using Unified Deployer.

    Features:
    - AI-powered content generation
    - Platform-specific optimization
    - Automatic deployment tracking
    """
    if not _HAS_UNIFIED_DEPLOYER or not UnifiedProductDeployer:
        return {"success": False, "error": "Unified Deployer not available"}

    try:
        deployer = UnifiedProductDeployer(database_url=settings.database_url)
        result = await deployer.deploy_to_store(
            product_id=product_id,
            store_id=store_id
        )
        return result
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/deploy/product/{product_id}/to-all-stores")
async def deploy_product_to_all(
    product_id: int,
    user_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Deploy product to all user's stores concurrently.

    Features:
    - Concurrent multi-store deployment
    - AI content generation for each platform
    - Comprehensive deployment tracking
    """
    if not _HAS_UNIFIED_DEPLOYER or not UnifiedProductDeployer:
        return {"success": False, "error": "Unified Deployer not available"}

    try:
        deployer = UnifiedProductDeployer(database_url=settings.database_url)
        result = await deployer.deploy_to_all_stores(
            product_id=product_id,
            user_id=user_id
        )
        return result
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# NEW: AI Provider Management API Endpoints
# ---------------------------------------------------------------
@app.get("/api/ai/providers")
async def get_ai_providers():
    """
    Get available AI providers (OpenAI, Claude, Gemini).

    Returns:
        {
            "success": true,
            "providers": ["openai", "claude", "gemini"],
            "default": "openai"
        }
    """
    if not _HAS_AI_FACTORY or not AIFactory:
        return {
            "success": False,
            "error": "AI Factory not available"
        }

    try:
        return {
            "success": True,
            "providers": AIFactory.get_available_providers(),
            "default": AIFactory.get_default_provider()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/ai/test/{provider}")
async def test_ai_provider(
    provider: str,
    api_key: str = Body(...),
    settings: Settings = Depends(get_settings)
):
    """
    Test AI provider credentials.

    Args:
        provider: Provider name (openai, claude, gemini)
        api_key: API key to test

    Returns:
        {
            "success": true,
            "provider": "openai",
            "message": "Connection successful"
        }
    """
    if not _HAS_AI_FACTORY or not AIFactory:
        return {"success": False, "error": "AI Factory not available"}

    try:
        ai = AIFactory.get_provider(provider, {"api_key": api_key})
        result = await ai.test_connection()

        return {
            "success": result.get("success", False),
            "provider": provider,
            "message": "Connection successful" if result.get("success") else result.get("error", "Connection failed")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ---------------------------------------------------------------
# NEW: Platform Management API Endpoints
# ---------------------------------------------------------------
@app.get("/api/platforms")
async def get_platforms():
    """
    Get available e-commerce platforms.

    Returns:
        {
            "success": true,
            "platforms": [
                {
                    "name": "shopify",
                    "display_name": "Shopify",
                    "complexity": "medium",
                    "credentials_count": 2,
                    "features": {...}
                },
                ...
            ]
        }
    """
    if not _HAS_PLATFORM_FACTORY or not PlatformFactory:
        return {
            "success": False,
            "error": "Platform Factory not available"
        }

    try:
        platforms = PlatformFactory.get_available_platforms()
        return {
            "success": True,
            "platforms": platforms
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/platforms/{platform}/test")
async def test_platform_credentials(
    platform: str,
    credentials: Dict = Body(...),
    settings: Settings = Depends(get_settings)
):
    """
    Test platform credentials.

    Args:
        platform: Platform name (shopify, amazon, woocommerce)
        credentials: Platform credentials

    Returns:
        {
            "success": true,
            "store_name": "My Store",
            "store_url": "https://mystore.myshopify.com",
            "platform_version": "2024-01"
        }
    """
    if not _HAS_PLATFORM_FACTORY or not PlatformFactory:
        return {"success": False, "error": "Platform Factory not available"}

    try:
        adapter = PlatformFactory.get_adapter(platform, credentials)
        result = await adapter.test_connection()
        return result
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Analytics dashboard with charts and visualizations."""
    dashboard_path = Path(__file__).parent.parent / "static" / "dashboard.html"
    if not dashboard_path.exists():
        return HTMLResponse("<h1>Dashboard not found</h1><p>Please ensure static/dashboard.html exists</p>", status_code=404)
    with open(dashboard_path, "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/dashboard/ospra", response_class=HTMLResponse)
async def ospra_dashboard():
    """Ospra OS Product Intelligence Dashboard with multi-niche discovery."""
    dashboard_path = Path(__file__).parent.parent / "static" / "ospra_dashboard.html"
    if not dashboard_path.exists():
        return HTMLResponse("<h1>Ospra Dashboard not found</h1><p>Please ensure static/ospra_dashboard.html exists</p>", status_code=404)
    with open(dashboard_path, "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/premium", response_class=HTMLResponse)
async def premium_dashboard():
    """Premium AI Intelligence Dashboard - Black/Electric Blue Theme"""
    dashboard_path = Path(__file__).parent.parent / "static" / "premium_dashboard.html"
    if not dashboard_path.exists():
        return HTMLResponse(
            "<h1>Premium Dashboard Not Found</h1>"
            "<p>Please ensure static/premium_dashboard.html exists</p>",
            status_code=404
        )
    with open(dashboard_path, "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/premium/v2", response_class=HTMLResponse)
async def premium_dashboard_v2():
    """Premium AI Intelligence Dashboard V2 - Enhanced with Real Data Integration"""
    dashboard_path = Path(__file__).parent.parent / "static" / "premium_dashboard_v2.html"
    if not dashboard_path.exists():
        return HTMLResponse(
            "<h1>Premium Dashboard V2 Not Found</h1>"
            "<p>Please ensure static/premium_dashboard_v2.html exists</p>",
            status_code=404
        )
    with open(dashboard_path, "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/premium/v3", response_class=HTMLResponse)
async def premium_dashboard_v3():
    """Premium AI Intelligence Dashboard V3 - Complete Enhancement Package

    Features:
    - Tabbed navigation (Products, Emails, Business, Settings)
    - Enhanced product cards with expandable analysis
    - Score breakdown visualizations
    - Email dashboard with recent emails
    - Business analytics with Shopify integration
    - Settings panel with API connection status
    - Non-blocking loading states
    - Claude AI chat integration
    """
    dashboard_path = Path(__file__).parent.parent / "static" / "premium_dashboard_v3.html"
    if not dashboard_path.exists():
        return HTMLResponse(
            "<h1>Premium Dashboard V3 Not Found</h1>"
            "<p>Please ensure static/premium_dashboard_v3.html exists</p>",
            status_code=404
        )
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
    - Total potential revenue
    - Average profit margin
    - Top performing category
    """
    try:
        from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine

        # Get products from intelligence engine
        engine = ProductIntelligenceEngine()
        products_data = await engine.discover_winning_products(
            niches=["smart home", "tech gadgets"],
            max_per_niche=3
        )

        if not products_data:
            return {
                "total_products": 0,
                "total_revenue": 0.0,
                "avg_profit_margin": 0.0,
                "top_performing_category": "N/A"
            }

        # Calculate metrics
        total_products = len(products_data)
        total_revenue = sum(p.get("display_data", {}).get("market_price", 0) * 10 for p in products_data)  # Assuming 10 units each
        avg_profit_margin = sum(p.get("display_data", {}).get("profit_margin", 0) for p in products_data) / total_products if total_products > 0 else 0

        # Find top category by average score
        category_scores = {}
        for p in products_data:
            niche = p.get("niche", "General")
            if niche not in category_scores:
                category_scores[niche] = []
            category_scores[niche].append(p.get("score", 0))

        top_category = max(category_scores.items(), key=lambda x: sum(x[1])/len(x[1]) if x[1] else 0)[0] if category_scores else "N/A"

        return {
            "total_products": total_products,
            "total_revenue": round(total_revenue, 2),
            "avg_profit_margin": round(avg_profit_margin, 1),
            "top_performing_category": top_category
        }
    except Exception as e:
        import traceback
        print(f"Error in dashboard overview: {e}")
        print(traceback.format_exc())
        return {
            "total_products": 0,
            "total_revenue": 0.0,
            "avg_profit_margin": 0.0,
            "top_performing_category": "Error"
        }


@app.get("/api/dashboard/products")
async def get_dashboard_products(
    limit: int = 6,
    min_score: float = 7.0,
    settings: Settings = Depends(get_settings)
):
    """
    Get product discovery results with scores.

    Returns recent product research results from intelligence engine.
    """
    try:
        from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine

        # Discover products using intelligence engine
        engine = ProductIntelligenceEngine()
        products_data = await engine.discover_winning_products(
            niches=["smart home", "tech gadgets"],
            max_per_niche=limit // 2
        )

        # Transform to dashboard format
        products = []
        for idx, p in enumerate(products_data[:limit]):
            display = p.get("display_data", {})
            products.append({
                "id": str(idx + 1),
                "name": display.get("name", "Unknown Product"),
                "category": p.get("niche", "General"),
                "price": display.get("market_price", 0),
                "cost": display.get("supplier_cost", 0),
                "profit_margin": display.get("profit_margin", 0),
                "score": p.get("score", 0),
                "description": p.get("ai_explanation", "")[:200] + "..." if p.get("ai_explanation") else "No description",
                "features": [
                    f"Supplier: {display.get('supplier_orders', 0):,} orders",
                    f"Rating: {display.get('supplier_rating', 0)}★",
                    f"Profit: ${display.get('estimated_profit', 0):.2f} per sale"
                ],
                "supplier_url": display.get("supplier_url", ""),
                "created_at": "2025-11-02T00:00:00Z"
            })

        return products
    except Exception as e:
        import traceback
        print(f"Error fetching products: {e}")
        print(traceback.format_exc())
        return []


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
        weekly = analytics.get_weekly_stats()  # Returns list of daily stats
        labels = analytics.get_top_labels(days=7)

        # Calculate weekly totals from list of daily stats
        weekly_total = sum(day.get("total_emails", 0) for day in weekly) if weekly else 0
        weekly_auto_replies = sum(day.get("auto_replies", 0) for day in weekly) if weekly else 0

        return {
            "summary": {
                "processed_today": daily.get("total_emails", 0),
                "processed_week": weekly_total,
                "auto_replied_today": daily.get("auto_replies", 0),
                "auto_replied_week": weekly_auto_replies,
            },
            "categories": labels if isinstance(labels, list) else [],
            "response_rate": daily.get("success_rate", 0),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/emails/recent")
async def get_recent_emails(limit: int = 20, settings: Settings = Depends(get_settings)):
    """
    Get recent processed emails for the email dashboard tab.

    Returns list of recent emails with:
    - From address
    - Subject
    - Category/label
    - Date processed
    - Auto-reply status
    - Preview text
    """
    try:
        from app.analytics import Analytics
        from datetime import datetime

        analytics = Analytics(settings.database_url)

        # Query recent email metrics from database
        from app.analytics import EmailMetric

        recent = analytics.session.query(EmailMetric)\
            .order_by(EmailMetric.timestamp.desc())\
            .limit(limit)\
            .all()

        emails = []
        for email in recent:
            emails.append({
                "from": email.customer_email,
                "subject": email.subject,
                "category": email.label,
                "date": email.timestamp.isoformat() if email.timestamp else None,
                "auto_replied": email.auto_reply_sent,
                "ai_provider": email.ai_provider,
                "response_mode": email.response_mode,
                "processing_time_ms": email.processing_time_ms,
                "success": email.success,
                "error": email.error_message if not email.success else None
            })

        return {
            "success": True,
            "emails": emails,
            "total": len(emails)
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "emails": []
        }


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

        client = ShopifyClient(
            store_domain=settings.SHOPIFY_STORE_DOMAIN,
            api_token=api_token,
            api_version=settings.SHOPIFY_API_VERSION
        )

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
        import os
        status_checks = []

        # Gmail
        gmail_configured = GmailClient is not None
        status_checks.append({
            "name": "Gmail API",
            "status": "connected" if gmail_configured else "not_configured",
            "health": "healthy" if gmail_configured else "unavailable",
        })

        # OpenAI - check both settings and env
        openai_configured = bool(settings.OPENAI_API_KEY) or bool(os.getenv('OPENAI_API_KEY'))
        status_checks.append({
            "name": "OpenAI API",
            "status": "connected" if openai_configured else "not_configured",
            "health": "healthy" if openai_configured else "unavailable",
        })

        # Claude (Anthropic) - check both CLAUDE_API_KEY and ANTHROPIC_API_KEY
        claude_configured = bool(settings.CLAUDE_API_KEY) or bool(os.getenv('ANTHROPIC_API_KEY')) or bool(os.getenv('CLAUDE_API_KEY'))
        status_checks.append({
            "name": "Claude API",
            "status": "connected" if claude_configured else "not_configured",
            "health": "healthy" if claude_configured else "unavailable",
        })

        # Reddit
        reddit_configured = bool(settings.REDDIT_CLIENT_ID) and bool(settings.REDDIT_SECRET)
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

        # Shopify - check multiple possible attribute names
        shopify_configured = bool(settings.SHOPIFY_STORE_DOMAIN) or bool(settings.SHOPIFY_STORE) or bool(settings.SHOPIFY_DOMAIN)
        status_checks.append({
            "name": "Shopify API",
            "status": "connected" if shopify_configured else "not_configured",
            "health": "healthy" if shopify_configured else "unavailable",
        })

        # AliExpress - check APP_KEY not API_KEY
        aliexpress_configured = bool(getattr(settings, 'ALIEXPRESS_API_KEY', None)) or bool(os.getenv('ALIEXPRESS_APP_KEY'))
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
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "overall_health": "error"
        }


@app.get("/admin/dashboard/data")
async def get_admin_dashboard_data(settings: Settings = Depends(get_settings)):
    """
    Unified endpoint for the premium dashboard v2.

    Returns complete dashboard data including:
    - Overview stats (products, emails, API connections)
    - Email analytics
    - Product discoveries
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
            "anthropic": settings.ANTHROPIC_API_KEY is not None,
            "aliexpress": settings.ALIEXPRESS_APP_KEY is not None,
            "shopify": settings.SHOPIFY_STORE is not None,
        }

        active_count = sum(1 for v in active_apis.values() if v)

        # Calculate system health
        system_health = "healthy" if active_count >= 2 else "degraded"

        return {
            "success": True,
            "overview": {
                "total_products": 0,  # Will be updated when products are discovered
                "avg_score": 0.0,
                "avg_profit": 0.0,
                "high_priority": 0,
                "emails_processed_today": daily_stats.get("total_processed", 0),
                "emails_processed_week": weekly_stats.get("total_processed", 0),
                "active_apis": active_count,
                "total_apis": len(active_apis),
                "system_health": system_health,
            },
            "email_stats": {
                "processed_today": daily_stats.get("total_processed", 0),
                "processed_week": weekly_stats.get("total_processed", 0),
                "auto_replied_today": daily_stats.get("auto_replied", 0),
                "auto_replied_week": weekly_stats.get("auto_replied", 0),
                "response_rate": daily_stats.get("auto_reply_rate", 0),
            },
            "products": [],  # Products will come from /api/intelligence/discover
            "api_status": active_apis,
            "timestamp": "2025-10-29",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "overview": {
                "total_products": 0,
                "system_health": "error"
            }
        }


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


@app.get("/api/debug/reddit")
async def debug_reddit(settings: Settings = Depends(get_settings)):
    """Debug endpoint to check Reddit API configuration - matches production flow exactly."""
    from ospra_os.product_research.connectors.social.reddit import RedditConnector
    import traceback

    reddit = RedditConnector(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_SECRET
    )

    result = {
        "reddit_configured": reddit.is_available(),
        "client_id": settings.REDDIT_CLIENT_ID[:10] + "..." if settings.REDDIT_CLIENT_ID else None,
        "client_secret_configured": bool(settings.REDDIT_SECRET),
        "tests": []
    }

    # Test 1: Try "week" time filter (matches production)
    try:
        products_week = await reddit.get_subreddit_products(
            subreddit="smarthome",
            time_filter="week",  # MATCHES PRODUCTION
            limit=25  # MATCHES PRODUCTION
        )
        result["tests"].append({
            "test": "smarthome (week, limit=25)",
            "success": True,
            "products_found": len(products_week),
            "sample_product": products_week[0].to_dict() if products_week else None
        })
    except Exception as e:
        result["tests"].append({
            "test": "smarthome (week, limit=25)",
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        })

    # Test 2: Try "month" time filter
    try:
        products_month = await reddit.get_subreddit_products(
            subreddit="smarthome",
            time_filter="month",
            limit=25
        )
        result["tests"].append({
            "test": "smarthome (month, limit=25)",
            "success": True,
            "products_found": len(products_month),
            "sample_product": products_month[0].to_dict() if products_month else None
        })
    except Exception as e:
        result["tests"].append({
            "test": "smarthome (month, limit=25)",
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        })

    # Test 3: Try different subreddit
    try:
        products_shutup = await reddit.get_subreddit_products(
            subreddit="shutupandtakemymoney",
            time_filter="week",
            limit=25
        )
        result["tests"].append({
            "test": "shutupandtakemymoney (week, limit=25)",
            "success": True,
            "products_found": len(products_shutup),
            "sample_product": products_shutup[0].to_dict() if products_shutup else None
        })
    except Exception as e:
        result["tests"].append({
            "test": "shutupandtakemymoney (week, limit=25)",
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        })

    return result


@app.get("/api/debug/trends-test")
async def debug_trends_test():
    """Simple test of Google Trends discovery."""
    from ospra_os.product_research.multi_source_discovery import MultiSourceDiscovery

    try:
        discovery = MultiSourceDiscovery()

        # Test single niche with low threshold
        niche_products = await discovery.discover_all_niches(min_score=40, max_per_niche=2)

        # Get stats
        stats = discovery.get_stats(niche_products)
        top = discovery.get_top_products_overall(niche_products, limit=5)

        return {
            "success": True,
            "test": "Google Trends Discovery",
            "products_found": stats["total_products"],
            "niches_with_products": stats["niches_with_products"],
            "top_5": [
                {
                    "name": p["name"],
                    "score": p["score"],
                    "trend_score": p["trend_score"],
                    "priority": p["priority"]
                }
                for p in top
            ],
            "stats": stats
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/debug/reddit-connector-logs")
async def debug_reddit_connector_logs(settings: Settings = Depends(get_settings)):
    """Test Reddit connector and capture logs."""
    import io
    import sys
    from ospra_os.product_research.connectors.social.reddit import RedditConnector

    # Capture stdout
    captured_output = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured_output

    try:
        reddit = RedditConnector()
        products = await reddit.get_subreddit_products("smarthome", "week", 5)

        # Restore stdout
        sys.stdout = old_stdout
        logs = captured_output.getvalue()

        return {
            "success": True,
            "products_found": len(products),
            "sample_products": [
                {
                    "name": p.name,
                    "score": p.social_mentions,
                    "comments": p.social_engagement,
                    "url": p.url
                }
                for p in products[:3]
            ],
            "logs": logs
        }
    except Exception as e:
        sys.stdout = old_stdout
        logs = captured_output.getvalue()
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "logs": logs
        }


@app.get("/api/debug/reddit-json")
async def debug_reddit_json():
    """Test Reddit JSON API directly (no credentials needed)."""
    import aiohttp

    url = "https://www.reddit.com/r/smarthome/top.json"
    params = {"t": "week", "limit": 5}
    headers = {"User-Agent": "web:OspraOS:v1.0 (by /u/OspraBot)"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status != 200:
                return {"error": f"HTTP {response.status}"}

            data = await response.json()
            posts = data.get("data", {}).get("children", [])

            results = []
            for post_wrapper in posts:
                post = post_wrapper.get("data", {})
                results.append({
                    "title": post.get("title", ""),
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "stickied": post.get("stickied", False),
                    "removed_by_category": post.get("removed_by_category"),
                    "selftext": post.get("selftext", "")[:100] if post.get("selftext") else None
                })

            return {
                "total_posts": len(posts),
                "posts": results
            }


@app.get("/api/debug/reddit-raw")
async def debug_reddit_raw(settings: Settings = Depends(get_settings)):
    """Debug endpoint to see raw Reddit posts BEFORE filtering."""
    try:
        import praw
        import asyncio
    except ImportError:
        return {"error": "praw not installed"}

    if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_SECRET:
        return {"error": "Reddit credentials not configured"}

    # Initialize Reddit in read-only mode (no user auth needed)
    reddit = praw.Reddit(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_SECRET,
        user_agent="web:OspraOS:v1.0 (by /u/OspraBot)",
        check_for_async=False
    )
    reddit.read_only = True

    result = {
        "reddit_auth": "success",
        "subreddit_tests": []
    }

    # Test r/smarthome
    try:
        subreddit = reddit.subreddit("smarthome")

        # Get raw top posts
        loop = asyncio.get_event_loop()
        top_posts = await loop.run_in_executor(
            None,
            lambda: list(subreddit.top(time_filter="week", limit=10))
        )

        raw_posts = []
        for post in top_posts:
            raw_posts.append({
                "title": post.title,
                "score": post.score,
                "num_comments": post.num_comments,
                "upvote_ratio": post.upvote_ratio,
                "stickied": post.stickied,
                "removed_by_category": post.removed_by_category,
                "selftext_preview": post.selftext[:100] if post.selftext else None,
                "url": f"https://reddit.com{post.permalink}"
            })

        result["subreddit_tests"].append({
            "subreddit": "smarthome",
            "time_filter": "week",
            "total_posts_fetched": len(top_posts),
            "posts": raw_posts,
            "filtered_count": {
                "stickied": sum(1 for p in top_posts if p.stickied),
                "removed": sum(1 for p in top_posts if p.removed_by_category),
                "after_filters": len([p for p in top_posts if not p.stickied and not p.removed_by_category])
            }
        })
    except Exception as e:
        import traceback
        result["subreddit_tests"].append({
            "subreddit": "smarthome",
            "error": str(e),
            "traceback": traceback.format_exc()
        })

    # Test r/shutupandtakemymoney
    try:
        subreddit = reddit.subreddit("shutupandtakemymoney")

        loop = asyncio.get_event_loop()
        top_posts = await loop.run_in_executor(
            None,
            lambda: list(subreddit.top(time_filter="week", limit=10))
        )

        raw_posts = []
        for post in top_posts:
            raw_posts.append({
                "title": post.title,
                "score": post.score,
                "num_comments": post.num_comments,
                "stickied": post.stickied,
                "removed_by_category": post.removed_by_category
            })

        result["subreddit_tests"].append({
            "subreddit": "shutupandtakemymoney",
            "time_filter": "week",
            "total_posts_fetched": len(top_posts),
            "posts": raw_posts,
            "filtered_count": {
                "stickied": sum(1 for p in top_posts if p.stickied),
                "removed": sum(1 for p in top_posts if p.removed_by_category),
                "after_filters": len([p for p in top_posts if not p.stickied and not p.removed_by_category])
            }
        })
    except Exception as e:
        import traceback
        result["subreddit_tests"].append({
            "subreddit": "shutupandtakemymoney",
            "error": str(e),
            "traceback": traceback.format_exc()
        })

    return result


class DiscoverRequest(BaseModel):
    min_score: float = 0.0  # Changed default from 7.0 to 0.0
    max_per_niche: int = 3
    top_overall: int = 15

@app.post("/api/discover-multi")
async def discover_multi_niche(
    request: DiscoverRequest,
    settings: Settings = Depends(get_settings)
):
    """
    🔥 Discover trending products using Google Trends (NO REDDIT REQUIRED).

    **WORKS ON RENDER** - uses Google Trends instead of Reddit!

    This endpoint searches 10 profitable niches:
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

    **Data Source:** Google Trends (shows REAL buying intent)

    **Why this is better than Reddit:**
    - ✅ Works on Render (no IP blocking)
    - ✅ Shows real search behavior (not just discussions)
    - ✅ Millions of data points
    - ✅ No rate limits
    - ✅ Free forever

    Example request body:
    {
        "min_score": 7.0,       // 0-10 scale (converted to 0-100 for Trends)
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
        },
        "source": "Google Trends (Reddit-free)",
        "data_quality": "High - based on real search behavior"
    }
    """
    try:
        from ospra_os.product_research.multi_source_discovery import MultiSourceDiscovery

        # Initialize Google Trends-based discovery (NO REDDIT!)
        discovery = MultiSourceDiscovery()

        # Run discovery using Google Trends
        # Note: min_score is now 0-100 (Google Trends scale) instead of 0-10
        trends_min_score = request.min_score * 10  # Convert 0-10 to 0-100
        niche_products = await discovery.discover_all_niches(
            min_score=trends_min_score,
            max_per_niche=request.max_per_niche
        )

        # Get top products overall
        top_products = discovery.get_top_products_overall(
            niche_products=niche_products,
            limit=request.top_overall
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
                "min_score": request.min_score,
                "products_per_niche": request.max_per_niche,
                "high_priority": stats["high_priority"],
                "medium_priority": stats["medium_priority"],
                "low_priority": stats["low_priority"],
            },
            "source": "Google Trends (Reddit-free)",
            "data_quality": "High - based on real search behavior"
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


# ---------------------------------------------------------------
# AI Automation Endpoints (Shopify Deploy, Content, Pricing)
# ---------------------------------------------------------------

@app.post("/api/deploy-to-shopify")
async def deploy_to_shopify(
    product_name: str,
    niche: str,
    score: float,
    trend_score: float = 50,
    aliexpress_cost: Optional[float] = None,
    product_images: Optional[List[str]] = None,
    settings: Settings = Depends(get_settings)
):
    """
    🚀 ONE-CLICK SHOPIFY DEPLOYMENT

    Complete automated pipeline:
    1. Generate AI-powered product content
    2. Optimize pricing with competitor analysis
    3. Deploy to Shopify store

    Args:
        product_name: Product name
        niche: Product category
        score: Discovery score (0-10)
        trend_score: Google Trends score (0-100)
        aliexpress_cost: Cost from supplier (optional - will be estimated)
        product_images: List of image URLs (optional)

    Returns:
        {
            "success": True,
            "shopify_product_id": "8234567890",
            "shopify_admin_url": "https://admin.shopify.com/...",
            "price": 29.99,
            "profit_margin": 65.5
        }
    """
    try:
        from ospra_os.integrations.shopify_auto_deploy import ShopifyAutoDeployer

        deployer = ShopifyAutoDeployer()

        result = await deployer.deploy_product(
            product_name=product_name,
            niche=niche,
            score=score,
            trend_score=trend_score,
            aliexpress_cost=aliexpress_cost,
            product_images=product_images or []
        )

        return result

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/generate-content")
async def generate_product_content(
    product_name: str,
    niche: str,
    trend_score: float = 50,
    settings: Settings = Depends(get_settings)
):
    """
    📝 AI PRODUCT CONTENT GENERATOR

    Generate SEO-optimized product content using AI:
    - Product title (SEO-optimized)
    - Product description (HTML)
    - Bullet points (benefit-focused)
    - Meta description
    - Tags
    - Marketing headline

    Args:
        product_name: Product name
        niche: Product category
        trend_score: Google Trends score (0-100)

    Returns:
        {
            "title": "LED Strip Lights - Transform Any Room",
            "description": "<p>Discover...</p>",
            "bullet_points": ["Feature 1", ...],
            "meta_description": "SEO description",
            "tags": ["led", "smart-home", ...],
            "headline": "Transform Your Home Today"
        }
    """
    try:
        from ospra_os.product_research.ai_content import AIContentGenerator

        generator = AIContentGenerator()

        content = await generator.generate_product_content(
            product_name=product_name,
            niche=niche,
            trend_score=trend_score
        )

        return {
            "success": True,
            "content": content
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/scrape-aliexpress-product")
async def scrape_aliexpress_product(url: str):
    """
    Scrape product details from AliExpress URL.

    Temporary solution until OAuth is approved.
    Currently returns error asking for manual entry.

    Args:
        url: AliExpress product URL

    Returns:
        {
            "success": False,
            "error": "Manual entry required",
            "message": "Auto-import coming when AliExpress OAuth approved"
        }
    """
    try:
        from ospra_os.integrations.aliexpress_scraper import AliExpressScraper

        scraper = AliExpressScraper()
        result = scraper.scrape_product(url)
        return result

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/optimize-price")
async def optimize_product_price(
    product_name: str,
    aliexpress_cost: float,
    niche: str,
    trend_score: float = 50,
    settings: Settings = Depends(get_settings)
):
    """
    💰 AI PRICE OPTIMIZER

    Optimize pricing with AI-powered competitor analysis:
    - Suggested price (with .99 endings)
    - Compare-at price (for perceived value)
    - Profit margin calculation
    - Profit per sale
    - Pricing strategy (premium/competitive/value)

    Args:
        product_name: Product name
        aliexpress_cost: Cost from supplier
        niche: Product category
        trend_score: Google Trends score (0-100)

    Returns:
        {
            "suggested_price": 29.99,
            "compare_at_price": 49.99,
            "profit_margin": 65.5,
            "profit_per_sale": 19.49,
            "pricing_strategy": "competitive",
            "reasoning": "AI explanation..."
        }
    """
    try:
        from ospra_os.product_research.price_optimizer import PriceOptimizer

        optimizer = PriceOptimizer()

        pricing = await optimizer.analyze_pricing(
            product_name=product_name,
            aliexpress_cost=aliexpress_cost,
            niche=niche,
            trend_score=trend_score
        )

        return {
            "success": True,
            "pricing": pricing
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# Product Intelligence API Endpoints
# ---------------------------------------------------------------
class DiscoverRequest(BaseModel):
    niches: Optional[List[str]] = None
    max_per_niche: int = 5


@app.post("/api/intelligence/discover")
async def discover_winning_products(request: DiscoverRequest):
    """
    Discover winning products using REAL Google Trends + AliExpress data

    Returns products with:
    - Real Google Trends search volume (live data)
    - Real AliExpress supplier data and pricing
    - AI-generated analysis from Claude
    - Unique scores for each product
    - Exact supplier links with SKUs
    - Real profit calculations
    """
    try:
        import asyncio
        import hashlib
        from datetime import datetime
        from ospra_os.product_research.multi_source_discovery import MultiSourceDiscovery  # REAL-TIME DISCOVERY!

        discovery = MultiSourceDiscovery()

        # Determine niches to search
        niches_to_search = request.niches or ["smart_lighting", "home_security", "cleaning_gadgets"]

        # Add timeout protection (120 seconds max)
        try:
            niche_products = await asyncio.wait_for(
                discovery.discover_all_niches(
                    min_score=70,
                    max_per_niche=request.max_per_niche
                ),
                timeout=120.0
            )
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': 'Discovery timeout after 120 seconds. Google Trends API may be slow.',
                'timeout': True
            }

        # Transform format from {niche: [products]} to flat list with frontend-expected fields
        all_products = []
        for niche, products in niche_products.items():
            # Only include requested niches if specified
            if request.niches and niche not in request.niches:
                continue

            for product in products:
                # Generate unique ID from name + niche
                product_id = hashlib.md5(f"{product['name']}{niche}".encode()).hexdigest()[:12]

                # Calculate pricing (use AliExpress if available, otherwise estimate)
                base_price = product.get('aliexpress_price') or (15.0 + (product['score'] * 3))
                cost_price = base_price * 0.4  # 60% markup
                selling_price = base_price * 1.5
                profit = selling_price - cost_price
                profit_margin = (profit / selling_price) * 100

                # Transform to frontend format
                transformed = {
                    "id": product_id,
                    "name": product['name'],
                    "price": round(selling_price, 2),
                    "cost": round(cost_price, 2),
                    "score": round(product['score'] * 10, 1),  # Scale to 0-100
                    "profit_margin": round(profit_margin, 1),
                    "estimated_profit": round(profit, 2),
                    "rating": product.get('supplier_rating', 4.5),
                    "orders": int(product.get('search_volume', 0) * 10),  # Estimate orders from search volume
                    "velocity_score": round(product['trend_score'], 1),
                    "image_url": product.get('aliexpress_image', f"https://via.placeholder.com/300x300?text={product['name']}"),
                    "category": niche,
                    "niche": niche,
                    "aliexpress_url": product.get('aliexpress_url'),
                    "source": "REAL_TIME_GOOGLE_TRENDS" if product['source'] == 'google_trends' else product['source'].upper(),
                    "priority": product.get('priority', 'MEDIUM'),
                    "search_volume": product.get('search_volume', 0),
                    "trend_score": product['trend_score'],
                    "tags": product.get('tags', [])
                }
                all_products.append(transformed)

        # Sort by velocity_score (highest first)
        all_products.sort(key=lambda x: x['velocity_score'], reverse=True)

        return {
            'success': True,
            'products': all_products,
            'count': len(all_products),
            'data_source': 'REAL_TIME_GOOGLE_TRENDS + AliExpress API',
            'niches_searched': list(niche_products.keys()),
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Intelligence discovery failed: {e}\n{traceback.format_exc()}")

        # Fallback to V3 engine if real-time discovery fails
        try:
            from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine
            logger.warning("Falling back to V3 engine due to error")

            engine = ProductIntelligenceEngine()
            products = await engine.discover_winning_products(
                niches=request.niches,
                max_per_niche=request.max_per_niche
            )

            return {
                'success': True,
                'products': products,
                'count': len(products),
                'data_source': 'FALLBACK_MODE',
                'warning': f'Real-time discovery failed: {str(e)}',
                'niches_searched': request.niches or engine.trending_niches[:3]
            }
        except Exception as fallback_error:
            return {
                'success': False,
                'error': str(e),
                'fallback_error': str(fallback_error),
                'traceback': traceback.format_exc()
            }


@app.get("/api/products/test-discovery")
async def test_product_discovery(
    niche: str = "smart_home",
    max_products: int = 10
):
    """Test endpoint to verify product discovery works"""
    try:
        from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine
        from datetime import datetime

        print(f"🧪 Testing discovery for niche: {niche}")

        engine = ProductIntelligenceEngine()
        products = await engine.discover_winning_products(
            niches=[niche],
            max_per_niche=max_products
        )

        print(f"✅ Found {len(products)} products")

        return {
            "success": True,
            "products": products,
            "count": len(products),
            "niche": niche,
            "debug": {
                "timestamp": datetime.utcnow().isoformat(),
                "engine_type": str(type(engine))
            }
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Discovery error: {e}")
        print(error_trace)

        return {
            "success": False,
            "error": str(e),
            "traceback": error_trace,
            "products": [],
            "count": 0
        }


@app.get("/api/intelligence/stats")
async def get_intelligence_stats():
    """Get intelligence engine statistics"""
    import os
    try:
        from ospra_os.scraping.proxy_manager import proxy_manager

        proxy_stats = proxy_manager.get_stats()

        return {
            'success': True,
            'stats': {
                'proxy_manager': proxy_stats,
                'apis_configured': {
                    'amazon': bool(os.getenv('AMAZON_ACCESS_KEY')),
                    'aliexpress': bool(os.getenv('ALIEXPRESS_APP_KEY')),
                    'instagram': bool(os.getenv('INSTAGRAM_ACCESS_TOKEN')),
                    'tiktok': bool(os.getenv('TIKTOK_API_KEY')),
                    'twitter': bool(os.getenv('TWITTER_BEARER_TOKEN')),
                    'claude': bool(os.getenv('ANTHROPIC_API_KEY')),
                    'scraper_api': bool(os.getenv('SCRAPERAPI_KEY'))
                }
            }
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# ---------------------------------------------------------------
# Velocity Detection API Endpoints
# ---------------------------------------------------------------

@app.get("/api/velocity/stats")
async def get_velocity_stats(
    niche: Optional[str] = None,
    settings: Settings = Depends(get_settings)
):
    """
    Get velocity statistics by lifecycle phase

    Returns product counts and metrics for each phase:
    - discovery: Just found, minimal data
    - early_spike: Rapid growth, trending up
    - growth: Sustained momentum
    - maturity: Stable, high volume
    - decline: Decreasing interest
    """
    try:
        from ospra_os.intelligence.velocity_detector import VelocityDetector

        detector = VelocityDetector(settings.database_url)

        # Get products by phase
        stats = {
            "discovery": await detector.get_products_by_phase('discovery', niche, 5),
            "early_spike": await detector.get_products_by_phase('early_spike', niche, 5),
            "growth": await detector.get_products_by_phase('growth', niche, 5),
            "maturity": await detector.get_products_by_phase('maturity', niche, 5),
            "decline": await detector.get_products_by_phase('decline', niche, 5)
        }

        # Get overall velocity statistics
        velocity_stats = await detector.get_velocity_stats(niche)

        await detector.close()

        return {
            "success": True,
            "stats": stats,
            "velocity_overview": velocity_stats
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/velocity/tier-products")
async def get_tier_products(
    tier: str,
    niche: Optional[str] = None,
    limit: int = 20,
    settings: Settings = Depends(get_settings)
):
    """
    Get products appropriate for a specific subscription tier

    Tier Access Levels:
    - free: maturity only (proven products, 30+ days old)
    - starter: growth + maturity (14+ days old)
    - pro: early_spike + growth (7+ days old, fast movers)
    - enterprise: discovery + early_spike (fresh products, first access)
    """
    try:
        from ospra_os.intelligence.velocity_detector import VelocityDetector

        detector = VelocityDetector(settings.database_url)

        products = await detector.get_tier_appropriate_products(
            user_tier=tier,
            niche=niche,
            limit=limit
        )

        await detector.close()

        return {
            "success": True,
            "tier": tier,
            "niche": niche or "all",
            "count": len(products),
            "products": products,
            "tier_info": {
                "free": "Maturity phase only - proven products",
                "starter": "Growth + Maturity - established products",
                "pro": "Early Spike + Growth - fast movers",
                "enterprise": "Discovery + Early Spike - first access to new trends"
            }.get(tier.lower(), "Unknown tier")
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/velocity/phase/{phase}")
async def get_products_in_phase(
    phase: str,
    niche: Optional[str] = None,
    limit: int = 20,
    settings: Settings = Depends(get_settings)
):
    """
    Get products in a specific lifecycle phase

    Valid phases:
    - discovery: < 7 days old
    - early_spike: Rapid growth, < 21 days old
    - growth: Sustained growth, < 45 days old
    - maturity: Stable, proven products
    - decline: Decreasing interest
    """
    valid_phases = ['discovery', 'early_spike', 'growth', 'maturity', 'decline']

    if phase not in valid_phases:
        return {
            "success": False,
            "error": f"Invalid phase. Valid phases: {', '.join(valid_phases)}"
        }

    try:
        from ospra_os.intelligence.velocity_detector import VelocityDetector

        detector = VelocityDetector(settings.database_url)

        products = await detector.get_products_by_phase(phase, niche, limit)

        await detector.close()

        return {
            "success": True,
            "phase": phase,
            "niche": niche or "all",
            "count": len(products),
            "products": products
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# Subscription Tier Management API
# ---------------------------------------------------------------

@app.get("/api/user/tier")
async def get_user_tier_info(
    user_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Get user's tier info and limits

    Returns current tier, features, limits, and expiry information
    """
    try:
        from ospra_os.subscription.tier_manager import TierManager

        manager = TierManager(settings.database_url)
        tier_info = await manager.get_tier_info(user_id)
        await manager.close()

        return {
            "success": True,
            **tier_info
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/user/upgrade-tier")
async def upgrade_user_tier(
    user_id: int,
    new_tier: str,
    duration_days: int = 30,
    settings: Settings = Depends(get_settings)
):
    """
    Upgrade user tier

    For testing - would connect to payment processor in production

    Args:
        user_id: User ID to upgrade
        new_tier: Target tier ('free', 'starter', 'pro', 'elite')
        duration_days: Subscription duration in days (default: 30)
    """
    try:
        from ospra_os.subscription.tier_manager import TierManager

        manager = TierManager(settings.database_url)
        result = await manager.upgrade_tier(user_id, new_tier, duration_days)
        await manager.close()

        return result
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/tiers/comparison")
async def get_tier_comparison(settings: Settings = Depends(get_settings)):
    """
    Get comparison of all subscription tiers

    Returns features, pricing, and limits for all tiers
    """
    try:
        from ospra_os.subscription.tier_manager import TierManager

        manager = TierManager(settings.database_url)
        comparison = await manager.get_tier_comparison()
        await manager.close()

        return {
            "success": True,
            **comparison
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/user/check-limit")
async def check_tier_limit(
    user_id: int,
    action: str,
    settings: Settings = Depends(get_settings)
):
    """
    Check if user can perform action based on tier limits

    Args:
        user_id: User ID
        action: Action to check ('add_store', 'get_products', etc.)

    Returns:
        allowed: boolean
        reason: string (if not allowed)
        upgrade_to: suggested tier (if not allowed)
    """
    try:
        from ospra_os.subscription.tier_manager import TierManager

        manager = TierManager(settings.database_url)
        result = await manager.check_tier_limits(user_id, action)
        await manager.close()

        return {
            "success": True,
            **result
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# Claude AI Chat API for Dashboard Insights
# ---------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    dashboard_context: Optional[Dict] = None
    conversation_history: Optional[List[Dict]] = None


@app.post("/api/claude/chat")
async def claude_chat(request: ChatRequest):
    """
    Chat with Claude AI with full dashboard context and conversation history

    Features:
    - Comprehensive dashboard data (portfolio, products, emails, tier)
    - Conversation history for context-aware responses
    - Real-time metric analysis
    - Actionable business insights
    """
    import os
    from anthropic import Anthropic

    try:
        # Check for API key
        api_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
        if not api_key:
            return {
                'success': True,
                'message': "I'm running in demo mode. To enable full AI capabilities, add ANTHROPIC_API_KEY to your environment variables.\n\nI can still help with basic questions about your dashboard!",
                'demo_mode': True
            }

        claude = Anthropic(api_key=api_key)

        # Build comprehensive context summary
        context_summary = ""
        if request.dashboard_context and request.dashboard_context.get('data'):
            data = request.dashboard_context['data']
            current_page = request.dashboard_context.get('current_page', '/')

            context_summary += f"**Current Page:** {current_page}\n\n"

            # Portfolio summary
            if 'portfolio' in data:
                portfolio = data['portfolio']
                context_summary += f"""**Portfolio Status:**
- Total Revenue: ${portfolio.get('totalRevenue', 0):,.2f}
- Active Stores: {portfolio.get('activeStores', 0)}
- Total Products: {portfolio.get('totalProducts', 0)}
- Avg Conversion Rate: {portfolio.get('avgConversion', 0):.2f}%
- Growth Rate: {portfolio.get('growthRate', 0):.1f}%

"""

            # Store rankings
            if 'rankings' in data:
                rankings = data['rankings'].get('stores', [])
                if rankings:
                    context_summary += f"**Top Performing Stores:**\n"
                    for i, store in enumerate(rankings[:3], 1):
                        context_summary += f"{i}. {store.get('name', 'Unknown')}: ${store.get('revenue', 0):,.2f}\n"
                    context_summary += "\n"

            # Products summary
            if 'products' in data and data['products'].get('count', 0) > 0:
                products_info = data['products']
                context_summary += f"""**Product Discovery:**
- Found: {products_info['count']} products
- Data Source: {products_info.get('data_source', 'Unknown')}
- Top Products: {', '.join([p.get('name', 'Unknown')[:30] for p in products_info.get('samples', [])[:3]])}

"""

            # Email automation summary
            if 'emails' in data:
                emails = data['emails'].get('summary', {})
                context_summary += f"""**Email Automation:**
- Processed Today: {emails.get('processed_today', 0)}
- Auto-Replied: {emails.get('auto_replied_today', 0)}
- Response Rate: {emails.get('response_rate', 0):.1f}%

"""

            # Subscription tier
            if 'tier' in data:
                tier = data['tier']
                tier_name = tier.get('tier', 'free').upper()
                context_summary += f"**Subscription:** {tier_name} Tier\n\n"

        # Build conversation context
        conversation_context = ""
        if request.conversation_history and len(request.conversation_history) > 0:
            conversation_context = "\n**Recent Conversation:**\n"
            for msg in request.conversation_history[-5:]:  # Last 5 messages
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                # Truncate long messages
                content_preview = content[:100] + "..." if len(content) > 100 else content
                conversation_context += f"- {role.upper()}: {content_preview}\n"
            conversation_context += "\n"

        # Build system prompt with all context
        system_prompt = f"""You are an AI assistant for Ospra Intelligence, an e-commerce automation platform.

Your expertise:
- E-commerce strategy and optimization
- Product research and selection
- Marketing and conversion optimization
- Business metrics analysis
- Shopify store management

{context_summary}

{conversation_context}

Provide helpful, actionable advice based on the actual dashboard data shown above. Be specific and reference real numbers when relevant. Use bullet points and emojis for readability."""

        # Call Claude API
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",  # Latest Sonnet 4
            max_tokens=800,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": request.message
            }]
        )

        return {
            'success': True,
            'message': response.content[0].text,
            'model': 'claude-sonnet-4-20250514',
            'demo_mode': False
        }

    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'message': f"Error communicating with Claude AI: {str(e)}"
        }


# ---------------------------------------------------------------
# Marketing Angle Generator API
# ---------------------------------------------------------------
@app.post("/api/marketing/generate-angle")
async def generate_marketing_angle(
    product_name: str,
    product_description: str,
    niche: str = 'smart_home',
    user_brand_voice: str = 'professional',
    user_target_audience: str = 'general',
    avoid_angles: Optional[List[str]] = None
):
    """
    Generate unique marketing angle for a product

    Creates AI-powered marketing positioning to differentiate users
    selling the same products. Each user gets a unique angle.

    Query Parameters:
        product_name: Name of the product
        product_description: Product description
        niche: Product niche (smart_home, fitness, kitchen, etc.)
        user_brand_voice: Brand voice (professional, casual, luxury, etc.)
        user_target_audience: Target demographic
        avoid_angles: List of angles to avoid (already used)

    Returns:
        Marketing angle with title, description, target audience,
        pain points, benefits, CTA, ad copy, and hashtags
    """
    try:
        from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

        # Initialize generator
        generator = MarketingAngleGenerator(ai_provider='claude')

        # Generate unique angle
        angle = await generator.generate_unique_angle(
            product_name=product_name,
            product_description=product_description,
            user_brand_voice=user_brand_voice,
            user_target_audience=user_target_audience,
            niche=niche,
            avoid_angles=avoid_angles or []
        )

        return {
            "success": True,
            "angle": angle
        }

    except Exception as e:
        import traceback
        logger.error(f"Marketing angle generation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/marketing/generate-multiple-angles")
async def generate_multiple_angles(
    product_name: str,
    product_description: str,
    niche: str = 'smart_home',
    num_angles: int = 3,
    user_brand_voice: str = 'professional',
    user_target_audience: str = 'general'
):
    """
    Generate multiple marketing angles for A/B testing

    Creates several different marketing angles for the same product
    to test which resonates best with the audience.

    Query Parameters:
        product_name: Name of the product
        product_description: Product description
        niche: Product niche
        num_angles: Number of angles to generate (default: 3, max: 5)
        user_brand_voice: Brand voice
        user_target_audience: Target demographic

    Returns:
        List of marketing angles for A/B testing
    """
    try:
        from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

        # Limit num_angles to reasonable range
        num_angles = min(max(num_angles, 1), 5)

        # Initialize generator
        generator = MarketingAngleGenerator(ai_provider='claude')

        # Generate multiple angles
        angles = await generator.generate_multiple_angles(
            product_name=product_name,
            product_description=product_description,
            niche=niche,
            num_angles=num_angles,
            user_brand_voice=user_brand_voice,
            user_target_audience=user_target_audience
        )

        return {
            "success": True,
            "count": len(angles),
            "angles": angles,
            "recommendation": "Test each angle with a small audience to see which performs best"
        }

    except Exception as e:
        import traceback
        logger.error(f"Multiple angles generation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/marketing/available-angles")
async def get_available_angles(niche: str = 'smart_home'):
    """
    Get list of available marketing angles for a niche

    Returns all possible marketing angles that can be used
    for products in the specified niche.

    Query Parameters:
        niche: Product niche

    Returns:
        List of available angles and their descriptions
    """
    try:
        from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

        generator = MarketingAngleGenerator(ai_provider='claude')

        # Get available angles
        angles = generator.get_available_angles(niche)

        # Get descriptions for each angle
        angle_details = []
        for angle in angles:
            details = generator.get_angle_description(angle)
            angle_details.append(details)

        return {
            "success": True,
            "niche": niche,
            "count": len(angles),
            "angles": angle_details
        }

    except Exception as e:
        import traceback
        logger.error(f"Failed to get available angles: {e}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# =============================================================================
# SMART RECOMMENDATIONS - The Complete Anti-AutoDS System
# =============================================================================

@app.post("/api/recommendations/smart")
async def get_smart_recommendations(
    user_id: int,
    niches: Optional[List[str]] = None,
    max_products: int = 10,
    include_angles: bool = True,
    settings: Settings = Depends(get_settings)
):
    """
    Get personalized, anti-AutoDS product recommendations

    This endpoint brings together ALL differentiation features:
    - Tier-based access (early access to trending products)
    - Saturation protection (no oversaturated products)
    - Velocity-based timing (lifecycle phase filtering)
    - Unique marketing angles (prevent direct competition)

    Query Parameters:
        user_id: User ID to get recommendations for
        niches: List of niches to search (uses user preferences if None)
        max_products: Maximum number of products to return (default: 10)
        include_angles: Whether to generate unique marketing angles (default: True)

    Returns:
        Personalized product recommendations with metadata:
        - User tier and access level
        - Filtered products based on all systems
        - Unique marketing angles per product
        - Analytics on filtering applied
    """
    try:
        from ospra_os.intelligence.smart_recommendations import SmartRecommendationEngine

        logger.info(f"Getting smart recommendations for user {user_id}")

        # Initialize recommendation engine
        engine = SmartRecommendationEngine(database_url=settings.database_url)

        # Get personalized recommendations
        recommendations = await engine.get_personalized_recommendations(
            user_id=user_id,
            niches=niches,
            max_products=max_products,
            include_angles=include_angles
        )

        # Close engine
        await engine.close()

        logger.info(f"✅ Smart recommendations complete: {recommendations.get('count', 0)} products")

        return recommendations

    except Exception as e:
        import traceback
        logger.error(f"Smart recommendations failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/recommendations/analytics/{user_id}")
async def get_recommendation_analytics(
    user_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Get analytics on user's recommendation performance

    This endpoint provides insights into:
    - Total recommendations received
    - Products deployed vs recommended
    - Success rate of deployed products
    - Top performing niches
    - Most effective marketing angles

    Path Parameters:
        user_id: User ID to get analytics for

    Returns:
        Analytics dictionary with:
        - Overall statistics (total, deployed, successful, success_rate)
        - Product diversity (unique niches, unique angles)
        - Recent recommendations (latest 10)
        - Top performing niches (top 5 by success rate)
        - Most effective angles (top 5 by success rate)
    """
    try:
        from ospra_os.intelligence.smart_recommendations import SmartRecommendationEngine

        logger.info(f"Getting recommendation analytics for user {user_id}")

        # Initialize recommendation engine
        engine = SmartRecommendationEngine(database_url=settings.database_url)

        # Get analytics
        analytics = await engine.get_recommendation_analytics(user_id)

        # Close engine
        await engine.close()

        logger.info(f"✅ Analytics retrieved: {analytics.get('total_recommendations', 0)} total recommendations")

        return analytics

    except Exception as e:
        import traceback
        logger.error(f"Failed to get analytics: {e}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# Mount static files (must be last)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    print(f"⚠️  Static files not mounted: {e}")
