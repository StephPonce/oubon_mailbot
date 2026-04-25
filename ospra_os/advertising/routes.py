"""
Advertising API Routes

Unified API endpoints for managing ad campaigns across Meta, TikTok, and Google Ads.

Author: OspraOS
Date: November 2025

Audit fixes (2026-04):
  - All endpoints now require ``Depends(get_current_user)``.
  - ``user_id`` is derived from the JWT, never accepted as a query param.
    The previous ``?user_id=N`` form let any caller read any tenant's
    campaigns and analytics — that's now impossible.
  - ``POST /create`` no longer hard-codes ``user_id=1``; it uses the
    authenticated user's id.
  - Per-campaign endpoints (``pause``, ``activate``, ``detail``) check
    that the campaign actually belongs to the calling user before acting,
    so a leaked campaign_id from another tenant can't be used to mutate
    or read someone else's campaign.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime, timezone

from ospra_os.advertising.scheduler import AdScheduler
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import AdCampaign, User, get_multi_store_session
from ospra_os.core.settings import get_settings

# Create router
router = APIRouter(prefix="/api/ads", tags=["Advertising"])

# Global scheduler instance
ad_scheduler: Optional[AdScheduler] = None


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateCampaignRequest(BaseModel):
    """Request to create multi-platform campaigns"""
    product_id: int
    product_name: str
    product_description: str
    product_url: str
    image_url: Optional[str] = None
    video_id: Optional[str] = None
    platforms: List[str] = ['meta', 'tiktok', 'google']
    daily_budget: float = 15.0
    target_audience: Optional[dict] = None
    auto_launch: bool = False


class CampaignResponse(BaseModel):
    """Campaign information response"""
    campaign_id: str
    platform: str
    status: str
    daily_budget: float
    total_spend: float
    impressions: int
    clicks: int
    conversions: int
    revenue: float
    ctr: float
    cpc: float
    roas: float
    created_at: str
    activated_at: Optional[str] = None


class AnalyticsResponse(BaseModel):
    """Aggregate analytics across all platforms"""
    total_campaigns: int
    active_campaigns: int
    paused_campaigns: int
    total_spend: float
    total_impressions: int
    total_clicks: int
    total_conversions: int
    total_revenue: float
    average_ctr: float
    average_cpc: float
    average_roas: float
    by_platform: dict


# ============================================================================
# LIFECYCLE MANAGEMENT
# ============================================================================

async def startup_advertising():
    """Initialize advertising scheduler on app startup"""
    global ad_scheduler

    try:
        ad_scheduler = AdScheduler()
        await ad_scheduler.start()
        print("[SUCCESS] Ad Automation Scheduler started")
    except Exception as e:
        print(f"[WARNING]  Ad Scheduler failed to start: {e}")
        ad_scheduler = None


async def shutdown_advertising():
    """Shutdown advertising scheduler"""
    global ad_scheduler

    if ad_scheduler:
        await ad_scheduler.stop()
        print("[STOP]  Ad Automation Scheduler stopped")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/create", response_model=dict)
async def create_campaign(
    request: CreateCampaignRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Create multi-platform ad campaigns for a product.

    This endpoint:
    - Generates AI-powered ad copy for each platform
    - Creates campaigns on Meta, TikTok, and/or Google Ads
    - Tracks campaigns in database (owned by the authenticated user)
    - Optionally auto-launches campaigns
    """
    if not ad_scheduler:
        raise HTTPException(status_code=503, detail="Ad scheduler not available")

    try:
        # Create campaigns across platforms
        result = await ad_scheduler.create_multi_platform_campaign(
            product_id=request.product_id,
            product_name=request.product_name,
            product_description=request.product_description,
            product_url=request.product_url,
            image_url=request.image_url,
            video_id=request.video_id,
            platforms=request.platforms,
            daily_budget=request.daily_budget,
            target_audience=request.target_audience,
            auto_launch=request.auto_launch
        )

        # Save campaigns to database — ownership comes from the JWT, not
        # from anything in the request body. Audit fix: this used to write
        # ``user_id=1`` for every tenant.
        session = get_multi_store_session()

        try:
            for platform, campaign_data in result['campaigns'].items():
                if campaign_data.get('success'):
                    db_campaign = AdCampaign(
                        user_id=current_user.id,
                        product_id=request.product_id,
                        campaign_id=campaign_data['campaign_id'],
                        platform=platform,
                        campaign_name=f"{request.product_name} - {platform.upper()}",
                        daily_budget=request.daily_budget,
                        status='active' if request.auto_launch else 'paused',
                        ad_copy=request.product_description,
                        image_url=request.image_url,
                        video_id=request.video_id
                    )
                    session.add(db_campaign)

            session.commit()
        finally:
            session.close()

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail="Campaign creation failed. Please try again.")


@router.get("/campaigns", response_model=List[CampaignResponse])
async def get_campaigns(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """
    List the calling user's ad campaigns.

    Audit fix: the previous form accepted ``?user_id=N`` as a query
    parameter and had no auth dependency, so anyone could read any
    tenant's campaigns. ``user_id`` is now derived from the JWT and is
    not overridable.

    Query Parameters:
    - platform: Filter by platform (meta, tiktok, google)
    - status: Filter by status (active, paused, ended)
    - limit: Maximum number of results (default: 50)
    """
    session = get_multi_store_session()

    try:
        query = session.query(AdCampaign).filter(AdCampaign.user_id == current_user.id)
        if platform:
            query = query.filter(AdCampaign.platform == platform)
        if status:
            query = query.filter(AdCampaign.status == status)

        campaigns = query.order_by(AdCampaign.created_at.desc()).limit(limit).all()

        return [CampaignResponse(
            campaign_id=c.campaign_id,
            platform=c.platform,
            status=c.status,
            daily_budget=c.daily_budget,
            total_spend=c.total_spend,
            impressions=c.impressions,
            clicks=c.clicks,
            conversions=c.conversions,
            revenue=c.revenue,
            ctr=c.ctr,
            cpc=c.cpc,
            roas=c.roas,
            created_at=c.created_at.isoformat() if c.created_at else '',
            activated_at=c.activated_at.isoformat() if c.activated_at else None
        ) for c in campaigns]

    finally:
        session.close()


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Pause a specific campaign owned by the calling user.

    Audit fix: now requires JWT and verifies the campaign belongs to the
    caller. Previously any caller could pause any tenant's campaign by
    knowing the campaign_id.
    """
    if not ad_scheduler:
        raise HTTPException(status_code=503, detail="Ad scheduler not available")

    session = get_multi_store_session()

    try:
        # Find campaign — scoped to the calling user. A 404 here covers
        # both "doesn't exist" and "exists but belongs to another tenant"
        # so we don't leak campaign-id existence across tenants.
        campaign = session.query(AdCampaign).filter(
            AdCampaign.campaign_id == campaign_id,
            AdCampaign.user_id == current_user.id,
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Pause on platform
        success = await ad_scheduler._pause_campaign(campaign.platform, campaign_id)

        if success:
            # Update database
            campaign.status = 'paused'
            campaign.paused_at = datetime.now(timezone.utc)
            session.commit()

            return {
                'success': True,
                'campaign_id': campaign_id,
                'platform': campaign.platform,
                'status': 'paused'
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to pause campaign on platform")

    finally:
        session.close()


@router.post("/campaigns/{campaign_id}/activate")
async def activate_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Activate a paused campaign owned by the calling user.

    See ``pause_campaign`` for the rationale on the user_id filter.
    """
    if not ad_scheduler:
        raise HTTPException(status_code=503, detail="Ad scheduler not available")

    session = get_multi_store_session()

    try:
        campaign = session.query(AdCampaign).filter(
            AdCampaign.campaign_id == campaign_id,
            AdCampaign.user_id == current_user.id,
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Activate on platform
        success = await ad_scheduler.activate_campaign(campaign.platform, campaign_id)

        if success:
            # Update database
            campaign.status = 'active'
            campaign.activated_at = datetime.now(timezone.utc)
            session.commit()

            return {
                'success': True,
                'campaign_id': campaign_id,
                'platform': campaign.platform,
                'status': 'active'
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to activate campaign on platform")

    finally:
        session.close()


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = 30,
    platform: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Get aggregate analytics for the calling user's campaigns.

    Audit fix: previously accepted ``?user_id=N`` and had no auth, so any
    caller could read any tenant's spend / revenue / ROAS by guessing
    user_ids. ``user_id`` is now derived from the JWT.

    Query Parameters:
    - days: Number of days to include (default: 30)
    - platform: Filter by specific platform
    """
    session = get_multi_store_session()

    try:
        from datetime import timedelta
        from sqlalchemy import func

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = session.query(AdCampaign).filter(
            AdCampaign.user_id == current_user.id,
            AdCampaign.created_at >= cutoff_date,
        )
        if platform:
            query = query.filter(AdCampaign.platform == platform)

        campaigns = query.all()

        # Calculate aggregates
        total_campaigns = len(campaigns)
        active_campaigns = sum(1 for c in campaigns if c.status == 'active')
        paused_campaigns = sum(1 for c in campaigns if c.status == 'paused')

        total_spend = sum(c.total_spend for c in campaigns)
        total_impressions = sum(c.impressions for c in campaigns)
        total_clicks = sum(c.clicks for c in campaigns)
        total_conversions = sum(c.conversions for c in campaigns)
        total_revenue = sum(c.revenue for c in campaigns)

        average_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        average_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
        average_roas = (total_revenue / total_spend) if total_spend > 0 else 0

        # By platform breakdown
        by_platform = {}
        for platform_name in ['meta', 'tiktok', 'google']:
            platform_campaigns = [c for c in campaigns if c.platform == platform_name]
            if platform_campaigns:
                by_platform[platform_name] = {
                    'campaigns': len(platform_campaigns),
                    'spend': sum(c.total_spend for c in platform_campaigns),
                    'clicks': sum(c.clicks for c in platform_campaigns),
                    'conversions': sum(c.conversions for c in platform_campaigns),
                    'revenue': sum(c.revenue for c in platform_campaigns)
                }

        return AnalyticsResponse(
            total_campaigns=total_campaigns,
            active_campaigns=active_campaigns,
            paused_campaigns=paused_campaigns,
            total_spend=round(total_spend, 2),
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_conversions=total_conversions,
            total_revenue=round(total_revenue, 2),
            average_ctr=round(average_ctr, 2),
            average_cpc=round(average_cpc, 2),
            average_roas=round(average_roas, 2),
            by_platform=by_platform
        )

    finally:
        session.close()


@router.get("/campaigns/{campaign_id}")
async def get_campaign_detail(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a campaign owned by the calling user.

    Audit fix: previously had no auth and no tenant scoping. Anyone with
    a campaign_id could read the campaign's full performance numbers.
    """
    session = get_multi_store_session()

    try:
        campaign = session.query(AdCampaign).filter(
            AdCampaign.campaign_id == campaign_id,
            AdCampaign.user_id == current_user.id,
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return campaign.get_performance_summary()

    finally:
        session.close()


@router.get("/scheduler/status")
async def get_scheduler_status(current_user: User = Depends(get_current_user)):
    """
    Get status of the ad automation scheduler. JWT-protected to avoid
    leaking how many campaigns the platform is managing in aggregate.
    """
    if not ad_scheduler:
        return {
            'status': 'offline',
            'message': 'Scheduler not initialized'
        }

    campaign_status = ad_scheduler.get_all_campaigns()

    return {
        'status': 'running',
        'scheduler_active': True,
        'tracked_campaigns': campaign_status['total_campaigns'],
        'active_campaigns': campaign_status['active'],
        'paused_campaigns': campaign_status['paused']
    }


class GenerateAdCopyRequest(BaseModel):
    """Request to generate AI-powered ad copy"""
    product_id: int
    product_name: str
    product_description: str
    platform: str = 'meta'
    tone: Optional[str] = None
    variations: int = 1


@router.post("/generate-copy")
async def generate_ad_copy(
    request: GenerateAdCopyRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate AI-powered ad copy for a product. JWT-protected so anonymous
    callers can't burn the platform's AI quota.

    Parameters:
    - product_id: Product ID
    - product_name: Name of the product
    - product_description: Product description
    - platform: Platform to generate for (meta, tiktok, google)
    - tone: Optional tone override
    - variations: Number of variations to generate (1-3)

    Example:
        POST /api/ads/generate-copy
        {
            "product_id": 123,
            "product_name": "Smart LED Bulbs",
            "product_description": "WiFi-enabled color changing bulbs with app control",
            "platform": "meta",
            "variations": 2
        }
    """
    try:
        from ospra_os.advertising.creative_generator import AdCreativeGenerator

        # Initialize generator
        generator = AdCreativeGenerator()

        try:
            # Generate ad copy
            creative = await generator.generate_ad_copy(
                platform=request.platform,
                product_name=request.product_name,
                product_description=request.product_description,
                variations=request.variations
            )
        except Exception as ai_error:
            # Fallback to demo mode if AI provider is not available
            if "API key not found" in str(ai_error):
                # Generate demo creative based on product info
                platform_emojis = {
                    'meta': '[MOBILE]',
                    'tiktok': '',
                    'google': '[SEARCH]'
                }

                creative = {
                    'variations': []
                }

                for i in range(request.variations):
                    variation = {
                        'headline': f"{platform_emojis.get(request.platform, '[NEW]')} {request.product_name[:35]}",
                        'primary_text': request.product_description[:120] + "..." if len(request.product_description) > 120 else request.product_description,
                        'description': f"Discover amazing deals on {request.product_name}. Limited time offer!",
                        'cta': "Shop Now",
                        'selling_angle': f"Transform your lifestyle with {request.product_name}"
                    }
                    creative['variations'].append(variation)

                creative['demo_mode'] = True
                creative['note'] = "Demo mode: Add AI_PROVIDER and API keys to .env for AI-generated copy"
            else:
                raise ai_error

        return {
            'success': True,
            'product_id': request.product_id,
            'platform': request.platform,
            'creative': creative
        }

    except Exception as e:
        # Check if this is an API key error - if so, return demo mode
        if "API key not found" in str(e):
            # Generate demo creative
            platform_emojis = {
                'meta': '[MOBILE]',
                'tiktok': '',
                'google': '[SEARCH]'
            }

            creative = {
                'variations': [],
                'demo_mode': True,
                'note': "Demo mode: Add AI_PROVIDER and API keys to .env for AI-generated copy"
            }

            for i in range(request.variations):
                variation = {
                    'headline': f"{platform_emojis.get(request.platform, '[NEW]')} {request.product_name[:35]}",
                    'primary_text': request.product_description[:120] + "..." if len(request.product_description) > 120 else request.product_description,
                    'description': f"Discover amazing deals on {request.product_name}. Limited time offer!",
                    'cta': "Shop Now",
                    'selling_angle': f"Transform your lifestyle with {request.product_name}"
                }
                creative['variations'].append(variation)

            return {
                'success': True,
                'product_id': request.product_id,
                'platform': request.platform,
                'creative': creative
            }
        else:
            raise HTTPException(status_code=500, detail="Ad copy generation failed. Please try again.")
