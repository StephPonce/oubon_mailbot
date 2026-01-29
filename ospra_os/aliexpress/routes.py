"""AliExpress OAuth routes for authentication."""
import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Optional
from ospra_os.core.settings import Settings, get_settings
from ospra_os.aliexpress.oauth import AliExpressOAuth
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User
import time

logger = logging.getLogger(__name__)
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
    STEP 1 & 2: Start OAuth flow and guide user to authorize.

    Returns an HTML page with instructions and authorization button.
    """
    global _oauth_state

    try:
        auth_url = oauth.get_authorization_url()

        # Store state for CSRF protection
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query)
        _oauth_state = params.get("state", [None])[0]

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
            _user_info = {
                "user_id": result.get("user_id"),
                "seller_id": result.get("seller_id"),
                "account": result.get("account")
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
            Account: {_user_info.get('account', 'N/A')}<br>
            Token expires: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(_token_expires_at))}<br>
            Time remaining: {int((_token_expires_at - time.time()) / 3600)} hours ({int((_token_expires_at - time.time()) / 86400)} days)
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
async def get_access_token(current_user: User = Depends(get_current_user)):
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
async def disconnect_aliexpress(
    current_user: User = Depends(get_current_user),
    oauth: AliExpressOAuth = Depends(get_oauth_client)
):
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
