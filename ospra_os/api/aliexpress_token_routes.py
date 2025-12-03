"""
API routes for AliExpress token management
"""
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from datetime import datetime
from ospra_os.api.aliexpress_token_refresh import refresh_all_tokens, refresh_dropship_token, refresh_affiliate_token

router = APIRouter(prefix="/api/aliexpress/tokens", tags=["aliexpress-tokens"])


@router.post("/refresh/all")
async def refresh_all_tokens_endpoint(background_tasks: BackgroundTasks):
    """
    Manually trigger token refresh for all AliExpress APIs

    This will check both Dropshipping and Affiliate API tokens,
    and refresh them if they're expiring within 7 days.
    """
    # Run refresh in background
    background_tasks.add_task(refresh_all_tokens)

    return JSONResponse({
        "status": "started",
        "message": "Token refresh task started in background",
        "timestamp": datetime.now().isoformat()
    })


@router.post("/refresh/dropship")
async def refresh_dropship_token_endpoint(background_tasks: BackgroundTasks):
    """
    Manually trigger token refresh for Dropshipping API
    """
    background_tasks.add_task(refresh_dropship_token)

    return JSONResponse({
        "status": "started",
        "message": "Dropshipping API token refresh started",
        "timestamp": datetime.now().isoformat()
    })


@router.post("/refresh/affiliate")
async def refresh_affiliate_token_endpoint(background_tasks: BackgroundTasks):
    """
    Manually trigger token refresh for Affiliate API
    """
    background_tasks.add_task(refresh_affiliate_token)

    return JSONResponse({
        "status": "started",
        "message": "Affiliate API token refresh started",
        "timestamp": datetime.now().isoformat()
    })


@router.get("/status")
async def get_token_status():
    """
    Get status of all AliExpress tokens

    Returns information about when tokens were obtained,
    when they expire, and whether they need refresh.
    """
    from ospra_os.api.aliexpress_token_refresh import refresher
    from datetime import datetime, timedelta

    def get_token_info(tokens_file):
        tokens = refresher.load_tokens(tokens_file)
        if not tokens:
            return {"status": "not_authorized", "message": "No tokens found"}

        obtained_at_str = tokens.get("obtained_at") or tokens.get("refreshed_at")
        if not obtained_at_str:
            return {"status": "invalid", "message": "Token missing timestamp"}

        try:
            obtained_at = datetime.fromisoformat(obtained_at_str)
            expires_in = tokens.get("expires_in", 0)
            expires_at = obtained_at + timedelta(seconds=expires_in)
            time_until_expiry = (expires_at - datetime.now()).total_seconds()
            days_until_expiry = time_until_expiry / 86400

            needs_refresh = refresher.is_token_expiring_soon(tokens)

            return {
                "status": "valid" if not needs_refresh else "expiring_soon",
                "obtained_at": obtained_at_str,
                "expires_at": expires_at.isoformat(),
                "expires_in_seconds": int(time_until_expiry),
                "expires_in_days": round(days_until_expiry, 1),
                "needs_refresh": needs_refresh,
                "has_refresh_token": bool(tokens.get("refresh_token")),
                "access_token_preview": tokens.get("access_token", "")[:20] + "..."
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return JSONResponse({
        "timestamp": datetime.now().isoformat(),
        "dropship": get_token_info(refresher.dropship_tokens_file),
        "affiliate": get_token_info(refresher.affiliate_tokens_file)
    })
