"""
Advertising API Routes

Unified API endpoints for managing ad campaigns across Meta, TikTok, and Google Ads.

Author: OspraOS
Date: November 2025
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

from ospra_os.advertising.scheduler import AdScheduler
from ospra_os.database import AdCampaign, get_multi_store_session
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
async def create_campaign(request: CreateCampaignRequest, background_tasks: BackgroundTasks):
    """
    Create multi-platform ad campaigns for a product.

    This endpoint:
    - Generates AI-powered ad copy for each platform
    - Creates campaigns on Meta, TikTok, and/or Google Ads
    - Tracks campaigns in database
    - Optionally auto-launches campaigns

    Example:
        POST /api/ads/create
        {
            "product_id": 123,
            "product_name": "Smart LED Bulbs",
            "product_description": "WiFi-enabled color changing bulbs",
            "product_url": "https://shop.example.com/led-bulbs",
            "platforms": ["meta", "tiktok"],
            "daily_budget": 20.0,
            "auto_launch": false
        }
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

        # Save campaigns to database
        session = get_multi_store_session()

        try:
            for platform, campaign_data in result['campaigns'].items():
                if campaign_data.get('success'):
                    db_campaign = AdCampaign(
                        user_id=1,  # TODO: Get from auth
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
        raise HTTPException(status_code=500, detail=f"Campaign creation failed: {str(e)}")


@router.get("/campaigns", response_model=List[CampaignResponse])
async def get_campaigns(
    user_id: Optional[int] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """
    List all ad campaigns with optional filters.

    Query Parameters:
    - user_id: Filter by user ID
    - platform: Filter by platform (meta, tiktok, google)
    - status: Filter by status (active, paused, ended)
    - limit: Maximum number of results (default: 50)

    Example:
        GET /api/ads/campaigns?platform=meta&status=active
    """
    session = get_multi_store_session()

    try:
        query = session.query(AdCampaign)

        if user_id:
            query = query.filter(AdCampaign.user_id == user_id)
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
async def pause_campaign(campaign_id: str):
    """
    Pause a specific campaign.

    Example:
        POST /api/ads/campaigns/123456789/pause
    """
    if not ad_scheduler:
        raise HTTPException(status_code=503, detail="Ad scheduler not available")

    session = get_multi_store_session()

    try:
        # Find campaign in database
        campaign = session.query(AdCampaign).filter(
            AdCampaign.campaign_id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Pause on platform
        success = await ad_scheduler._pause_campaign(campaign.platform, campaign_id)

        if success:
            # Update database
            campaign.status = 'paused'
            campaign.paused_at = datetime.utcnow()
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
async def activate_campaign(campaign_id: str):
    """
    Activate a paused campaign.

    Example:
        POST /api/ads/campaigns/123456789/activate
    """
    if not ad_scheduler:
        raise HTTPException(status_code=503, detail="Ad scheduler not available")

    session = get_multi_store_session()

    try:
        # Find campaign in database
        campaign = session.query(AdCampaign).filter(
            AdCampaign.campaign_id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Activate on platform
        success = await ad_scheduler.activate_campaign(campaign.platform, campaign_id)

        if success:
            # Update database
            campaign.status = 'active'
            campaign.activated_at = datetime.utcnow()
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
    user_id: Optional[int] = None,
    days: int = 30,
    platform: Optional[str] = None
):
    """
    Get aggregate analytics across all campaigns.

    Query Parameters:
    - user_id: Filter by user ID
    - days: Number of days to include (default: 30)
    - platform: Filter by specific platform

    Example:
        GET /api/ads/analytics?user_id=1&days=7
    """
    session = get_multi_store_session()

    try:
        from datetime import timedelta
        from sqlalchemy import func

        # Date filter
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Base query
        query = session.query(AdCampaign).filter(
            AdCampaign.created_at >= cutoff_date
        )

        if user_id:
            query = query.filter(AdCampaign.user_id == user_id)
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
async def get_campaign_detail(campaign_id: str):
    """
    Get detailed information about a specific campaign.

    Example:
        GET /api/ads/campaigns/123456789
    """
    session = get_multi_store_session()

    try:
        campaign = session.query(AdCampaign).filter(
            AdCampaign.campaign_id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return campaign.get_performance_summary()

    finally:
        session.close()


@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    Get status of the ad automation scheduler.

    Example:
        GET /api/ads/scheduler/status
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
async def generate_ad_copy(request: GenerateAdCopyRequest):
    """
    Generate AI-powered ad copy for a product.

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
            raise HTTPException(status_code=500, detail=f"Ad copy generation failed: {str(e)}")
