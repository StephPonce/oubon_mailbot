"""
AliExpress OAuth routes — *platform-level* credential.

Important context: AliExpress is a **sourcing-side** relationship for Ospra
(we read product/supplier data from AliExpress to feed the discovery
engine), NOT a per-tenant selling-side relationship like Shopify. There is
exactly one AliExpress credential active at a time, and it belongs to the
platform — every tenant benefits from the same upstream catalogue.

Persistence path (audit fix, was: module-level globals):
  - ``ospra_os.database.aliexpress_tokens.save_token("dropship", ...)``
  - ``ospra_os.database.aliexpress_tokens.load_token("dropship")``

Five other modules already store/read the platform credential through that
table (``api/aliexpress_oauth.py``, ``api/aliexpress_token_routes.py``,
``api/aliexpress_product_routes.py``, ``api/aliexpress_affiliate_oauth.py``,
``api/aliexpress_token_scheduler.py``); we just have to plug into it.

Audit blocker addressed: the previous module-level globals
``_access_token`` / ``_refresh_token`` / ``_token_expires_at`` meant that
in a multi-worker deployment, whichever worker handled the callback held
the credential and the others read ``None``. Worse, on a single worker the
globals were lost on every restart and every read returned None until the
next manual reauth.
"""
import asyncio
import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Optional
from datetime import datetime
from ospra_os.core.settings import Settings, get_settings
from ospra_os.aliexpress.oauth import AliExpressOAuth
from ospra_os.auth.jwt_auth import get_current_user, require_admin_user
from ospra_os.database import User
from ospra_os.database.aliexpress_tokens import (
    save_token as save_platform_token,
    load_token as load_platform_token,
)
import time

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/aliexpress", tags=["aliexpress"])

# ---------------------------------------------------------------------------
# OAuth CSRF state — re-audit S1 fix.
#
# The old design stored one state string in-process and SKIPPED verification
# when the callback arrived without a state param. That allowed an attacker to
# authorize THEIR AliExpress account and hit /callback with their code —
# overwriting the platform-wide supplier credential (token-planting). It also
# broke on multi-worker deploys (each worker had its own _oauth_state).
#
# New design — stateless + owner-bound, works on any number of workers:
#   * /auth/start requires proof of ownership (the AE_OAUTH_SETUP_KEY env
#     value passed as ?key=...), then mints an
#     HMAC-signed state: "<nonce>.<expiry>.<sig>" (10-min TTL).
#   * /callback REQUIRES a state that verifies against the same secret.
#     No valid state → 400, unconditionally. Only /auth/start can mint one,
#     and only the owner can reach /auth/start — closing the planting hole.
# ---------------------------------------------------------------------------
import hashlib
import hmac as _hmac
import secrets as _secrets

_OAUTH_STATE_TTL_SECONDS = 600


def _state_secret() -> bytes:
    from ospra_os.auth.jwt_auth import SECRET_KEY
    return f"ae-oauth-state:{SECRET_KEY}".encode()


def _make_oauth_state() -> str:
    nonce = _secrets.token_urlsafe(16)
    expiry = int(time.time()) + _OAUTH_STATE_TTL_SECONDS
    payload = f"{nonce}.{expiry}"
    sig = _hmac.new(_state_secret(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def _verify_oauth_state(state: Optional[str]) -> bool:
    if not state:
        return False
    parts = state.split(".")
    if len(parts) != 3:
        return False
    nonce, expiry_raw, sig = parts
    try:
        if int(expiry_raw) < time.time():
            return False  # expired
    except ValueError:
        return False
    expected = _hmac.new(
        _state_secret(), f"{nonce}.{expiry_raw}".encode(), hashlib.sha256
    ).hexdigest()[:32]
    return _hmac.compare_digest(expected, sig)


def _setup_key_ok(key: Optional[str]) -> bool:
    """True when the caller presented the AE_OAUTH_SETUP_KEY env value."""
    configured = os.getenv("AE_OAUTH_SETUP_KEY", "").strip()
    return bool(configured) and bool(key) and _hmac.compare_digest(configured, key)

# Platform credential cache. Source of truth is the DB; this is a cheap
# memo so /auth/status and /auth/token don't round-trip Postgres on every
# call. ``_load_platform_token_from_db`` rehydrates it on demand.
_PLATFORM_API_TYPE = "dropship"


def _load_platform_credential() -> Optional[dict]:
    """
    Read the active platform credential from the persistent store.

    Returns a dict with ``access_token``, ``refresh_token``, ``expires_at``
    (epoch float), and ``is_expired``. Returns None if no credential is
    stored.
    """
    record = load_platform_token(_PLATFORM_API_TYPE)
    if not record:
        return None
    try:
        expires_at_dt = datetime.fromisoformat(record["expires_at"])
    except (KeyError, ValueError):
        return None
    return {
        "access_token": record["access_token"],
        "refresh_token": record.get("refresh_token"),
        "expires_at": expires_at_dt.timestamp(),
        "is_expired": bool(record.get("is_expired")),
    }


def get_oauth_client(settings: Settings = Depends(get_settings)) -> AliExpressOAuth:
    """Get configured OAuth client."""
    # Validate required settings
    if not settings.ALIEXPRESS_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="AliExpress API Key not configured. Set OUBONSHOP_ALIEXPRESS_API_KEY environment variable."
        )
    if not settings.ALIEXPRESS_APP_SECRET:
        raise HTTPException(
            status_code=500,
            detail="AliExpress App Secret not configured. Set OUBONSHOP_ALIEXPRESS_APP_SECRET environment variable."
        )

    redirect_uri = f"{settings.base_url}/aliexpress/callback"

    return AliExpressOAuth(
        app_key=settings.ALIEXPRESS_API_KEY,
        app_secret=settings.ALIEXPRESS_APP_SECRET,
        redirect_uri=redirect_uri,
        database_url=None  # Use in-memory storage for testing
    )


@router.get("/auth/start")
async def start_oauth(
    key: Optional[str] = Query(None, description="AE_OAUTH_SETUP_KEY value"),
    oauth: AliExpressOAuth = Depends(get_oauth_client),
):
    """
    STEP 1 & 2: Start OAuth flow and guide user to authorize.

    SECURITY (re-audit S1): only the owner may mint an OAuth state — pass
    ?key=<AE_OAUTH_SETUP_KEY> (set that env var on the API service first).
    Without it, an attacker could mint a state and plant their own AliExpress
    token as the platform credential.

    Returns an HTML page with instructions and authorization button.
    """
    if not _setup_key_ok(key):
        configured = bool(os.getenv("AE_OAUTH_SETUP_KEY", "").strip())
        raise HTTPException(
            status_code=403,
            detail=(
                "OAuth setup requires ?key=<AE_OAUTH_SETUP_KEY>."
                if configured else
                "Set AE_OAUTH_SETUP_KEY on the API service, then open "
                "/aliexpress/auth/start?key=<that value>."
            ),
        )

    try:
        # Mint the HMAC-signed CSRF state and bake it into the authorize URL.
        auth_url = oauth.get_authorization_url(state=_make_oauth_state())

        # Return HTML page with authorization button
        from fastapi.responses import HTMLResponse
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Connect AliExpress</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .card {{
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        p {{ color: #666; line-height: 1.6; }}
        .btn {{
            display: inline-block;
            background: #FF6A00;
            color: white;
            padding: 16px 32px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin-top: 20px;
            transition: background 0.2s;
        }}
        .btn:hover {{ background: #E65A00; }}
        .steps {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
        }}
        .steps li {{ margin: 8px 0; color: #666; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>[LINK] Connect AliExpress</h1>
        <p>Click the button below to authorize Ospra to access your AliExpress seller account.</p>

        <div class="steps">
            <strong>What happens next:</strong>
            <ol>
                <li>You'll be redirected to AliExpress</li>
                <li>Log in with your seller account</li>
                <li>Review and approve permissions</li>
                <li>You'll be redirected back automatically</li>
            </ol>
        </div>

        <a href="{auth_url}" class="btn">
            Connect AliExpress Account →
        </a>
    </div>
</body>
</html>
        """

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"OAuth initialization failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "OAuth initialization failed. Please try again."
            }
        )


@router.get("/callback")
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    oauth: AliExpressOAuth = Depends(get_oauth_client)
):
    """
    Handle OAuth callback from AliExpress.

    AliExpress redirects here after user approves → exchange code for token
    """
    # Check for errors
    if error:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": error,
                "error_description": error_description or "OAuth authorization failed"
            }
        )

    if not code:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Missing authorization code",
                "hint": "The URL should contain ?code=... parameter"
            }
        )

    # SECURITY (re-audit S1): state is MANDATORY and must verify. The old code
    # skipped the check when state was absent, which allowed token-planting —
    # an attacker authorizing their own AE account into our platform slot.
    # (Never echo the expected value back.)
    if not _verify_oauth_state(state):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Missing or invalid state parameter (CSRF protection)",
                "hint": "Restart the flow at /aliexpress/auth/start",
            }
        )

    # Exchange code for token — oauth.exchange_code_for_token() is
    # synchronous and calls requests.post() against AE's token endpoint
    # (15s timeout). Wrap in asyncio.to_thread so the OAuth callback
    # handler doesn't block the event loop while AE responds. Task #30.
    try:
        result = await asyncio.to_thread(oauth.exchange_code_for_token, code)

        if result.get("success"):
            # Persist the platform credential. Other modules read it via
            # ``aliexpress_tokens.load_token("dropship")`` and the token
            # refresh scheduler keeps it alive — both depend on this row
            # existing, so writing here is the single source of truth.
            access_token = result.get("access_token")
            refresh_token = result.get("refresh_token")
            expires_in = int(result.get("expires_in", 2592000))
            saved = save_platform_token(
                api_type=_PLATFORM_API_TYPE,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
            )
            if not saved:
                logger.error("AliExpress callback: failed to persist token")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": "Token exchange succeeded but persistence failed.",
                    },
                )
            token_expires_at = time.time() + expires_in
            user_info = {
                "user_id": result.get("user_id"),
                "seller_id": result.get("seller_id"),
                "account": result.get("account"),
            }

            # Return success HTML page
            from fastapi.responses import HTMLResponse
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Connected!</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .card {{
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            text-align: center;
        }}
        .success {{ font-size: 48px; margin-bottom: 20px; }}
        h1 {{ color: #00A86B; margin-bottom: 10px; }}
        p {{ color: #666; line-height: 1.6; }}
        .info {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
            text-align: left;
        }}
        .btn {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="success">[SUCCESS]</div>
        <h1>Successfully Connected!</h1>
        <p>Your AliExpress account is now connected to Ospra.</p>

        <div class="info">
            <strong>Connection Details:</strong><br>
            Account: {user_info.get('account', 'N/A')}<br>
            Token expires: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(token_expires_at))}<br>
            Time remaining: {int((token_expires_at - time.time()) / 3600)} hours ({int((token_expires_at - time.time()) / 86400)} days)
        </div>

        <a href="/admin/dashboard/v2" class="btn">
            → Go to Dashboard
        </a>
    </div>
</body>
</html>
            """

            return HTMLResponse(content=html_content)
        else:
            # Token exchange failed
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": result.get("error"),
                    "error_description": result.get("error_description"),
                    "details": result.get("details", "")
                }
            )

    except Exception as e:
        logger.error(f"OAuth callback processing failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Failed to process OAuth callback. Please try again."
            }
        )


@router.get("/auth/status")
async def check_auth_status(current_user: User = Depends(get_current_user)):
    """
    Check if the platform AliExpress credential is connected and not expired.

    Reads from the persistent ``aliexpress_tokens`` table — same row the
    refresh scheduler maintains and other modules query. JWT-protected:
    we never expose token state to anonymous callers, even just metadata.
    """
    cred = _load_platform_credential()
    if not cred:
        return JSONResponse(
            status_code=200,
            content={
                "connected": False,
                "status": "Not connected",
                "message": "Visit /aliexpress/auth/start to connect",
            },
        )

    if cred["is_expired"] or time.time() > cred["expires_at"]:
        return JSONResponse(
            status_code=200,
            content={
                "connected": False,
                "status": "Token expired",
                "message": "Re-authenticate at /aliexpress/auth/start",
            },
        )

    time_remaining = int(cred["expires_at"] - time.time())
    return JSONResponse(
        status_code=200,
        content={
            "connected": True,
            "status": "Connected",
            # T48: do NOT echo any of the shared platform token — connection
            # status doesn't need it, and even a 20-char prefix leaks part of a
            # secret to every tenant that can hit this status endpoint.
            "time_remaining_seconds": time_remaining,
            "time_remaining_hours": round(time_remaining / 3600, 1),
            "time_remaining_days": round(time_remaining / 86400, 1),
        },
    )


@router.get("/auth/token")
async def get_access_token(current_user: User = Depends(require_admin_user)):
    """
    Get the current access token.

    T48: this is the ONE shared PLATFORM AliExpress credential for the whole
    deployment. It used to be returned to ANY authenticated tenant
    (get_current_user) — a full-secret leak that would let one customer act as
    our AliExpress account. No server code calls this over HTTP (the connector
    reads _load_platform_credential() directly), so it is now admin-only for
    the rare ops/debug case.
    """
    cred = _load_platform_credential()
    if not cred or cred["is_expired"] or time.time() > cred["expires_at"]:
        raise HTTPException(
            status_code=401,
            detail="No valid access token. Authenticate at /aliexpress/auth/start",
        )
    return {"access_token": cred["access_token"]}


@router.post("/auth/disconnect")
async def disconnect_aliexpress(
    current_user: User = Depends(get_current_user),
):
    """
    Disconnect AliExpress by deleting the stored platform credential.

    The previous implementation called a noop SQL update that never
    actually invalidated anything (``oauth.session.query(...).update(...)``
    on a non-existent column). We now delete the row directly from the
    persistent store the rest of the codebase reads.
    """
    try:
        from ospra_os.database.aliexpress_tokens import (
            SessionLocal as TokenSessionLocal,
            AliExpressToken,
        )

        db = TokenSessionLocal()
        try:
            row = db.query(AliExpressToken).filter_by(
                api_type=_PLATFORM_API_TYPE
            ).first()
            if row is not None:
                db.delete(row)
                db.commit()
        finally:
            db.close()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "AliExpress disconnected successfully"
            }
        )
    except Exception as e:
        logger.error(f"AliExpress disconnect failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Failed to disconnect AliExpress. Please try again."
            }
        )


# =============================================================================
# DEBUG ENDPOINTS REMOVED FOR SECURITY
# =============================================================================
# The following debug endpoints were removed for security:
# - /debug/config: Exposed partial API keys and configuration
# - /debug/auth-url: Exposed OAuth credentials
#
# SECURITY NOTE: Checking environment variables is not reliable for security.
# These endpoints are blocked by DebugEndpointProtectionMiddleware in production,
# but for defense-in-depth, they have been removed entirely.
#
# For debugging AliExpress integration, use admin tools or server logs.
# =============================================================================
