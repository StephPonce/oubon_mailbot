"""
TikTok OAuth Router
Handles authorization flow for TikTok API access
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import RedirectResponse
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/tiktok", tags=["TikTok OAuth"])

@router.get("/authorize")
async def start_tiktok_oauth():
    """Redirect to TikTok authorization"""

    from ospra_os.integrations.tiktok_client import TikTokClient

    try:
        client = TikTokClient()

        if not client.enabled:
            raise HTTPException(
                status_code=500,
                detail="TikTok client not configured. Check TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env"
            )

        # Generate state for CSRF protection
        import secrets
        state = secrets.token_urlsafe(32)

        # Use environment redirect URI
        redirect_uri = os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:8001/auth/tiktok/callback")

        # Temporarily update client redirect URI for callback
        original_redirect = client.redirect_uri
        client.redirect_uri = redirect_uri

        auth_url = client.get_authorization_url(state=state)

        # Restore original redirect URI
        client.redirect_uri = original_redirect

        return {
            "authorization_url": auth_url,
            "message": "Visit this URL to authorize TikTok access",
            "redirect_uri": redirect_uri,
            "state": state
        }

    except Exception as e:
        logger.error(f"TikTok OAuth start failed: {e}")
        raise HTTPException(status_code=500, detail="TikTok operation failed. Please try again later.")


@router.get("/callback")
async def tiktok_oauth_callback(
    code: str = Query(...),
    state: str = Query(None)
):
    """
    Handle TikTok OAuth callback

    SECURITY: Tokens are stored server-side only, never exposed to client.
    The access token is securely stored using the same pattern as AliExpress tokens
    and NOT returned in the API response.
    """
    from ospra_os.integrations.tiktok_client import TikTokClient

    try:
        client = TikTokClient()

        if not client.enabled:
            raise HTTPException(
                status_code=500,
                detail="TikTok client not configured"
            )

        # Exchange code for token
        logger.info("Exchanging code for TikTok access token...")
        token_data = client.exchange_code_for_token(code)

        if not token_data:
            raise HTTPException(status_code=400, detail="Failed to get access token")

        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")
        expires_in = token_data.get("expires_in", 0)

        # SECURITY: Store token server-side using the tiktok_tokens module
        # Never return access token to client
        try:
            from ospra_os.database.tiktok_tokens import save_token as save_tiktok_token
            save_tiktok_token(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in
            )
            logger.info("TikTok access token stored securely in database")
            token_stored = True
        except ImportError:
            # If tiktok_tokens module doesn't exist, store in environment
            # This is a fallback - log a warning for manual configuration
            logger.warning("TikTok tokens module not found. Token must be stored manually.")
            logger.warning("Set TIKTOK_ACCESS_TOKEN environment variable manually.")
            token_stored = False
        except Exception as db_error:
            logger.error(f"Failed to store TikTok token: {db_error}")
            token_stored = False

        # SECURITY: Return success message WITHOUT the token
        return {
            "status": "success",
            "message": "TikTok authorized successfully!",
            "token_stored": token_stored,
            "expires_in_seconds": expires_in,
            "instructions": [
                "Your TikTok account has been connected successfully.",
                "The access token has been securely stored server-side." if token_stored else "Please configure TIKTOK_ACCESS_TOKEN manually.",
                "You can now use TikTok features in Ospra OS.",
                "",
                "Test the integration:",
                "  GET /api/dashboard/v2/products?niche=smart_home&per_page=10",
                "",
                "You should now see 'TIKTOK_TRENDING' as the data source!"
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TikTok OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail="TikTok operation failed. Please try again later.")


@router.get("/status")
async def tiktok_status():
    """Check TikTok API status"""

    from ospra_os.integrations.tiktok_client import TikTokClient

    try:
        client = TikTokClient()
        access_token = os.getenv("TIKTOK_ACCESS_TOKEN")

        return {
            "configured": bool(access_token),
            "client_enabled": client.enabled,
            "has_credentials": bool(client.client_key and client.client_secret),
            "has_access_token": bool(access_token),
            "message": "TikTok API ready" if access_token else "Authorization required",
            "next_steps": [
                "Visit /auth/tiktok/authorize to start OAuth flow"
            ] if not access_token else [
                "TikTok is configured and ready to use!"
            ]
        }
    except Exception as e:
        logger.error(f"TikTok status check failed: {e}")
        return {
            "configured": False,
            "error": "Failed to check TikTok status"
        }


@router.post("/test")
async def test_tiktok_search():
    """Test TikTok product search"""

    from ospra_os.integrations.tiktok_client import TikTokClient

    try:
        client = TikTokClient()

        if not client.enabled:
            raise HTTPException(
                status_code=500,
                detail="TikTok client not enabled"
            )

        # Test search
        products = client.search_trending_products(
            keywords=["smart home"],
            limit=5
        )

        return {
            "status": "success",
            "products_found": len(products),
            "sample_products": products[:3] if products else [],
            "message": f"Found {len(products)} trending products"
        }

    except Exception as e:
        logger.error(f"TikTok test search failed: {e}")
        raise HTTPException(status_code=500, detail="TikTok operation failed. Please try again later.")
