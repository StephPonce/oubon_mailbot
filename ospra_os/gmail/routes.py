from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from ospra_os.core.settings import Settings, get_settings

# Prefer new path, fall back to legacy class if your tree has it
try:
    from app.gmail_client import GmailClient  # legacy
except Exception:
    from ospra_os.gmail.util import GmailClient  # if you have a new layout

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.get("/auth/url")
def gmail_auth_url(settings: Settings = Depends(get_settings)):
    gc = GmailClient(settings)
    return {"auth_url": gc.build_auth_url()}


@router.get("/auth/start")
def gmail_auth_start(settings: Settings = Depends(get_settings)):
    gc = GmailClient(settings)
    return RedirectResponse(url=gc.build_auth_url())


@router.get("/oauth2callback")
def gmail_oauth_callback(code: str, settings: Settings = Depends(get_settings)):
    gc = GmailClient(settings)
    gc.exchange_code_for_tokens(code)
    return RedirectResponse(url="/admin/dashboard")
