from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/aliexpress", tags=["AliExpress OAuth"])

@router.get("/callback")
async def aliexpress_callback(
    code: str = Query(...),
    state: str = Query(None)
):
    """Handle AliExpress OAuth callback"""
    try:
        logger.info(f"AliExpress OAuth callback received with code: {code[:10]}...")

        # TODO: Exchange code for access token
        # Will implement after getting app credentials

        return JSONResponse({
            "status": "success",
            "message": "AliExpress authorization received",
            "code": code,
            "next_steps": [
                "Authorization code received successfully",
                "Will exchange for access token once app credentials are available"
            ]
        })

    except Exception as e:
        logger.error(f"AliExpress OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def aliexpress_status():
    """Check AliExpress API status"""
    app_key = os.getenv("ALIEXPRESS_APP_KEY")
    app_secret = os.getenv("ALIEXPRESS_APP_SECRET")

    return {
        "configured": bool(app_key and app_secret),
        "has_app_key": bool(app_key),
        "has_app_secret": bool(app_secret),
        "message": "AliExpress API ready" if (app_key and app_secret) else "Awaiting credentials"
    }
