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
    Get status of all AliExpress tokens (from database)

    Returns information about when tokens were obtained,
    when they expire, and whether they need refresh.
    """
    from ospra_os.database.aliexpress_tokens import get_token_status as db_get_status

    # Load status from database (survives deployments!)
    return JSONResponse(db_get_status())
