"""AliExpress OAuth routes for authentication."""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Optional
from ospra_os.core.settings import Settings, get_settings
from ospra_os.aliexpress.oauth import AliExpressOAuth
import time

router = APIRouter(prefix="/aliexpress", tags=["aliexpress"])

# In-memory storage for testing (replace with database later)
_oauth_state: Optional[str] = None
_access_token: Optional[str] = None
_refresh_token: Optional[str] = None
_token_expires_at: float = 0


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
async def start_oauth(oauth: AliExpressOAuth = Depends(get_oauth_client)):
    """
    Start OAuth flow.

    Returns the authorization URL for testing.
    In production, this would redirect automatically.
    """
    global _oauth_state

    try:
        auth_url = oauth.get_authorization_url()

        # Store state for verification
        _oauth_state = auth_url.split("state=")[1] if "state=" in auth_url else None

        return JSONResponse(
            status_code=200,
            content={
                "auth_url": auth_url,
                "instructions": [
                    "1. Copy the auth_url above",
                    "2. Paste it in your browser",
                    "3. Click 'Authorize' on AliExpress page",
                    "4. You'll be redirected back to /aliexpress/callback automatically"
                ],
                "state": _oauth_state
            }
        )
    except Exception as e:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
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
    global _oauth_state, _access_token, _refresh_token, _token_expires_at

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

    # Verify state (optional for now)
    if state and _oauth_state and state != _oauth_state:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Invalid state parameter (CSRF protection)",
                "expected": _oauth_state,
                "received": state
            }
        )

    # Exchange code for token
    try:
        result = oauth.exchange_code_for_token(code)

        if result.get("success"):
            # Store token in memory
            _access_token = result.get("access_token")
            _refresh_token = result.get("refresh_token")
            _token_expires_at = time.time() + result.get("expires_in", 2592000)

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "✅ AliExpress connected successfully!",
                    "access_token": _access_token[:20] + "..." if _access_token else None,
                    "expires_in": result.get("expires_in"),
                    "expires_in_days": result.get("expires_in", 0) // 86400,
                    "expires_at": result.get("expires_at")
                }
            )
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
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Failed to process callback: {str(e)}",
                "traceback": traceback.format_exc()
            }
        )


@router.get("/auth/status")
async def check_auth_status():
    """
    Check if AliExpress is connected and token is valid.

    Returns connection status, expiry time, etc.
    """
    global _access_token, _token_expires_at

    if not _access_token:
        return JSONResponse(
            status_code=200,
            content={
                "connected": False,
                "status": "Not connected",
                "message": "Visit /aliexpress/auth/start to connect"
            }
        )

    # Check if token expired
    if time.time() > _token_expires_at:
        return JSONResponse(
            status_code=200,
            content={
                "connected": False,
                "status": "Token expired",
                "message": "Re-authenticate at /aliexpress/auth/start"
            }
        )

    time_remaining = int(_token_expires_at - time.time())

    return JSONResponse(
        status_code=200,
        content={
            "connected": True,
            "status": "Connected",
            "token": _access_token[:20] + "...",
            "time_remaining_seconds": time_remaining,
            "time_remaining_hours": round(time_remaining / 3600, 1),
            "time_remaining_days": round(time_remaining / 86400, 1)
        }
    )


@router.get("/auth/token")
async def get_access_token():
    """
    Get the current access token (for internal use by AliExpress connector).

    Returns the token if valid, otherwise raises 401.
    """
    global _access_token, _token_expires_at

    if not _access_token or time.time() > _token_expires_at:
        raise HTTPException(
            status_code=401,
            detail="No valid access token. Authenticate at /aliexpress/auth/start"
        )

    return {"access_token": _access_token}


@router.post("/auth/disconnect")
async def disconnect_aliexpress(oauth: AliExpressOAuth = Depends(get_oauth_client)):
    """
    Disconnect AliExpress by invalidating stored tokens.
    """
    try:
        # Invalidate all tokens
        oauth.session.query(oauth.session.query(oauth.session.bind.dialect.name).statement).update(
            {"is_valid": False}
        )
        oauth.session.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "AliExpress disconnected successfully"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )


@router.get("/debug/config")
async def debug_config(settings: Settings = Depends(get_settings)):
    """Debug endpoint to check AliExpress configuration."""
    try:
        return {
            "app_key_set": settings.ALIEXPRESS_API_KEY is not None,
            "app_key_value": settings.ALIEXPRESS_API_KEY[:3] + "..." if settings.ALIEXPRESS_API_KEY else None,
            "app_secret_set": settings.ALIEXPRESS_APP_SECRET is not None,
            "base_url": settings.base_url,
            "redirect_uri": f"{settings.base_url}/aliexpress/callback",
            "database_url_set": settings.database_url is not None
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "type": type(e).__name__
            }
        )


@router.get("/debug/auth-url")
async def debug_auth_url(oauth: AliExpressOAuth = Depends(get_oauth_client)):
    """Debug endpoint to see the OAuth URL without redirecting."""
    try:
        from urllib.parse import urlparse, parse_qs

        auth_url = oauth.get_authorization_url()

        # Parse the URL to show components
        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query)

        return {
            "auth_url": auth_url,
            "parsed": {
                "base_url": f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
                "parameters": {k: v[0] if len(v) == 1 else v for k, v in params.items()}
            },
            "credentials": {
                "app_key": oauth.app_key,
                "redirect_uri": oauth.redirect_uri
            },
            "message": "Copy auth_url and paste in browser to test",
            "note": "If this fails, AliExpress might not support OAuth for your app type"
        }
    except Exception as e:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        )
