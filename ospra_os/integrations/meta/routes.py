"""
Meta Ads Integration Routes
REAL API calls only - No mock/demo data
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os

router = APIRouter(prefix="/api/meta", tags=["Meta Ads"])


def get_meta_credentials():
    """Get Meta Ads credentials from environment"""
    return {
        "access_token": os.getenv("META_ACCESS_TOKEN"),
        "ad_account_id": os.getenv("META_AD_ACCOUNT_ID"),
        "app_id": os.getenv("META_APP_ID"),
        "app_secret": os.getenv("META_APP_SECRET")
    }


def is_meta_configured():
    """Check if Meta Ads is properly configured"""
    creds = get_meta_credentials()
    return bool(creds["access_token"] and creds["ad_account_id"])


@router.get("/status")
async def meta_status():
    """
    GET /api/meta/status
    Returns connection status (no demo data)
    """
    configured = is_meta_configured()
    return {
        "connected": configured,
        "message": "Meta Ads connected" if configured else "Meta Ads not configured. Add credentials in Settings → Integrations."
    }


@router.get("/campaigns")
async def get_campaigns():
    """
    GET /api/meta/campaigns
    Returns real campaigns from Meta Ads API
    Returns empty list if not configured
    """
    if not is_meta_configured():
        return {
            "connected": False,
            "campaigns": [],
            "message": "Connect your Meta Ads account to see campaigns."
        }

    # REAL Meta API call
    try:
        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.adaccount import AdAccount

        creds = get_meta_credentials()
        FacebookAdsApi.init(
            app_id=creds["app_id"],
            app_secret=creds["app_secret"],
            access_token=creds["access_token"]
        )

        account = AdAccount(f'act_{creds["ad_account_id"]}')
        campaigns = account.get_campaigns(fields=[
            'name', 'status', 'objective',
            'daily_budget', 'lifetime_budget',
            'created_time', 'updated_time'
        ])

        # Get insights for each campaign
        results = []
        for campaign in campaigns:
            insights = campaign.get_insights(fields=[
                'spend', 'impressions', 'clicks',
                'actions', 'cost_per_action_type',
                'purchase_roas'
            ], params={'date_preset': 'last_30d'})

            insight_data = insights[0] if insights else {}

            results.append({
                "id": campaign["id"],
                "name": campaign["name"],
                "status": campaign["status"],
                "objective": campaign.get("objective", "UNKNOWN"),
                "daily_budget": float(campaign.get("daily_budget", 0)) / 100 if campaign.get("daily_budget") else None,
                "spend": float(insight_data.get("spend", 0)) if insight_data else 0,
                "impressions": int(insight_data.get("impressions", 0)) if insight_data else 0,
                "clicks": int(insight_data.get("clicks", 0)) if insight_data else 0,
                "roas": float(insight_data.get("purchase_roas", [{}])[0].get("value", 0)) if insight_data.get("purchase_roas") else 0
            })

        return {"connected": True, "campaigns": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Meta API error: {str(e)}")


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    """
    POST /api/meta/campaigns/{campaign_id}/pause
    Pause a Meta Ads campaign
    """
    if not is_meta_configured():
        raise HTTPException(status_code=400, detail="Meta Ads not configured")

    try:
        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.campaign import Campaign

        creds = get_meta_credentials()
        FacebookAdsApi.init(
            app_id=creds["app_id"],
            app_secret=creds["app_secret"],
            access_token=creds["access_token"]
        )

        campaign = Campaign(campaign_id)
        campaign.api_update(params={'status': 'PAUSED'})
        return {"status": "paused", "campaign_id": campaign_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(campaign_id: str):
    """
    POST /api/meta/campaigns/{campaign_id}/resume
    Resume a paused Meta Ads campaign
    """
    if not is_meta_configured():
        raise HTTPException(status_code=400, detail="Meta Ads not configured")

    try:
        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.campaign import Campaign

        creds = get_meta_credentials()
        FacebookAdsApi.init(
            app_id=creds["app_id"],
            app_secret=creds["app_secret"],
            access_token=creds["access_token"]
        )

        campaign = Campaign(campaign_id)
        campaign.api_update(params={'status': 'ACTIVE'})
        return {"status": "active", "campaign_id": campaign_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance():
    """
    GET /api/meta/performance
    Returns real performance data for last 30 days
    """
    if not is_meta_configured():
        return {
            "connected": False,
            "message": "Connect Meta Ads to see performance data"
        }

    try:
        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.adaccount import AdAccount

        creds = get_meta_credentials()
        FacebookAdsApi.init(
            app_id=creds["app_id"],
            app_secret=creds["app_secret"],
            access_token=creds["access_token"]
        )

        account = AdAccount(f'act_{creds["ad_account_id"]}')
        insights = account.get_insights(fields=[
            'spend', 'impressions', 'clicks',
            'actions', 'purchase_roas', 'cpc', 'cpm'
        ], params={'date_preset': 'last_30d'})

        if not insights:
            return {"connected": True, "data": None, "message": "No ad data for last 30 days"}

        data = insights[0]

        # Extract purchase ROAS
        roas = 0
        if data.get("purchase_roas"):
            roas_data = data.get("purchase_roas", [])
            if isinstance(roas_data, list) and len(roas_data) > 0:
                roas = float(roas_data[0].get("value", 0))

        return {
            "connected": True,
            "period": "last_30d",
            "spend": float(data.get("spend", 0)),
            "impressions": int(data.get("impressions", 0)),
            "clicks": int(data.get("clicks", 0)),
            "cpc": float(data.get("cpc", 0)),
            "cpm": float(data.get("cpm", 0)),
            "roas": roas
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
