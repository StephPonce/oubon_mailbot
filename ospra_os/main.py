from fastapi import FastAPI, Depends
from fastapi.responses import RedirectResponse
from ospra_os.core.settings import Settings, get_settings

# add this (Gmail OAuth router)
from ospra_os.gmail.routes import router as gmail_oauth_router  # noqa: E402

# TikTok router is optional — don’t crash if it’s not present
try:
    from ospra_os.tiktok.routes import router as tiktok_router  # type: ignore
    _HAS_TIKTOK = True
except Exception as e:  # ImportError, etc.
    print("TikTok router not loaded:", e)
    _HAS_TIKTOK = False

# If your code needs GmailClient directly for the top-level callback:
try:
    from app.gmail_client import GmailClient
except Exception:
    from ospra_os.gmail.util import GmailClient

app = FastAPI(title="OspraOS API", version="0.1")
app.include_router(gmail_oauth_router)  # exposes /gmail/auth/*

if _HAS_TIKTOK:
    app.include_router(tiktok_router, prefix="/tiktok")

# keep a root-level callback because your Google OAuth client JSON often points here
@app.get("/oauth2callback", include_in_schema=False)
def oauth_cb_root(code: str, settings: Settings = Depends(get_settings)):
    gc = GmailClient(settings)
    gc.exchange_code_for_tokens(code)
    return RedirectResponse(url="/admin/dashboard")

# (optional) quick route list for sanity checks
@app.get("/debug/routes", include_in_schema=False)
def debug_routes():
    return sorted([r.path for r in app.routes])
