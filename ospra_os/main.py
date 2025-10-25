from fastapi import FastAPI, Depends
from fastapi.responses import RedirectResponse
from ospra_os.core.settings import Settings, get_settings

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

# Import GmailClient for the OAuth callback
try:
    from app.gmail_client import GmailClient
    print("✅ GmailClient loaded from app.gmail_client")
except Exception as e:
    print(f"⚠️  Could not import GmailClient: {e}")
    GmailClient = None

app = FastAPI(title="OspraOS API", version="0.1")

if gmail_oauth_router:
    app.include_router(gmail_oauth_router)  # exposes /gmail/auth/*

if _HAS_TIKTOK and tiktok_router:
    app.include_router(tiktok_router)

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
        "tiktok_loaded": _HAS_TIKTOK
    }

# (optional) quick route list for sanity checks
@app.get("/debug/routes", include_in_schema=False)
def debug_routes():
    return sorted([r.path for r in app.routes])
