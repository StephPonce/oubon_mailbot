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
        "product_research_loaded": _HAS_RESEARCH
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
# Analytics API Endpoints
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

# Mount static files (must be last)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    print(f"⚠️  Static files not mounted: {e}")
