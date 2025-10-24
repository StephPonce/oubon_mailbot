from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from ospra_os.core.settings import Settings, get_settings
from ospra_os.gmail.util import GmailClient

from .worker import get_worker

router = APIRouter(prefix="/gmail", tags=["Gmail"])

_settings = get_settings()
_worker = get_worker(_settings)


@router.get("/auth/url")
def gmail_auth_url(settings: Settings = Depends(get_settings)):
    """Return the Google OAuth consent URL."""
    gc = GmailClient(settings)
    return {"auth_url": gc.build_auth_url()}


@router.get("/auth/start")
def gmail_auth_start(settings: Settings = Depends(get_settings)):
    """Convenience endpoint: redirect the browser directly to consent."""
    gc = GmailClient(settings)
    return RedirectResponse(url=gc.build_auth_url())


@router.get("/oauth2callback")
def gmail_oauth_callback(code: str, settings: Settings = Depends(get_settings)):
    """OAuth redirect target. Exchanges code for tokens, then sends you to the admin dashboard."""
    gc = GmailClient(settings)
    gc.exchange_code_for_tokens(code)
    return RedirectResponse(url="/admin/dashboard")


@router.get("/worker/status")
async def status():
    return _worker.status()


@router.post("/worker/start")
async def start():
    await _worker.start()
    return _worker.status()


@router.post("/worker/stop")
async def stop():
    await _worker.stop()
    return _worker.status()


@router.post("/worker/run-once")
async def run_once():
    await _worker.run_once()
    return _worker.status()
