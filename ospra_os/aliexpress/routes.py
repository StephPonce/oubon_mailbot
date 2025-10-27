"""AliExpress OAuth routes for authentication."""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Optional
from ospra_os.core.settings import Settings, get_settings
from ospra_os.aliexpress.oauth import AliExpressOAuth

router = APIRouter(prefix="/aliexpress", tags=["aliexpress"])


def get_oauth_client(settings: Settings = Depends(get_settings)) -> AliExpressOAuth:
    """Get configured OAuth client."""
    redirect_uri = f"{settings.base_url}/aliexpress/callback"

    return AliExpressOAuth(
        app_key=settings.aliexpress_api_key,
        app_secret=settings.aliexpress_app_secret,
        redirect_uri=redirect_uri,
        database_url=settings.database_url
    )


@router.get("/auth/start")
async def start_oauth(oauth: AliExpressOAuth = Depends(get_oauth_client)):
    """
    Start OAuth flow by redirecting to AliExpress authorization page.

    User clicks "Connect AliExpress" button → redirects here → redirects to AliExpress
    """
    try:
        auth_url = oauth.get_authorization_url()
        return RedirectResponse(url=auth_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start OAuth: {str(e)}")


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
                "error": "Missing authorization code"
            }
        )

    # Exchange code for token
    try:
        result = oauth.exchange_code_for_token(code)

        if result.get("success"):
            # Success! Redirect to dashboard or success page
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "AliExpress connected successfully!",
                    "expires_at": result.get("expires_at"),
                    "expires_in": result.get("expires_in")
                }
            )
        else:
            # Token exchange failed
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": result.get("error"),
                    "details": result.get("details", result.get("error_description", ""))
                }
            )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Failed to process callback: {str(e)}"
            }
        )


@router.get("/auth/status")
async def check_auth_status(oauth: AliExpressOAuth = Depends(get_oauth_client)):
    """
    Check if AliExpress is connected and token is valid.

    Returns connection status, expiry time, etc.
    """
    try:
        status = oauth.get_token_status()
        return JSONResponse(status_code=200, content=status)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "connected": False,
                "status": "Error",
                "error": str(e)
            }
        )


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
