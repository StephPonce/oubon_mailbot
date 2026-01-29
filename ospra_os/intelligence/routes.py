"""
Competitor Intelligence API Routes

Endpoints for competitive analysis, price tracking, and market intelligence.

Author: OspraOS
Date: November 2025
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from ospra_os.database import get_multi_store_session
from ospra_os.intelligence.competitor_engine import CompetitorIntelligenceEngine
from ospra_os.intelligence.price_tracker import PriceTracker
from ospra_os.intelligence.market_share_estimator import MarketShareEstimator
from ospra_os.intelligence.gap_analyzer import GapAnalyzer
from ospra_os.intelligence.ad_intelligence import AdIntelligence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/competitors", tags=["Competitor Intelligence"])


# ============================================================================
# AUTO-DISCOVERY
# ============================================================================

class AutoDiscoveryRequest(BaseModel):
    niche: str
    our_products: List[str]
    max_competitors: int = 5


@router.post("/auto-discover")
async def auto_discover_competitors(
    request: AutoDiscoveryRequest,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    [AI] AI AUTO-DISCOVERS COMPETITORS

    Tell AI your niche and products, it finds competitors automatically:
    - Google search for niche keywords
    - Shopify store directories
    - Who else sells your products
    - Auto-classifies threat level
    - Auto-adds to database

    Example:
    {
        "niche": "smart home",
        "our_products": ["LED Strip", "Smart Plug", "Motion Sensor"],
        "max_competitors": 5
    }
    """
    from ospra_os.intelligence.auto_competitor_discovery import auto_discover_and_add_competitors

    logger.info(f"[SEARCH] Auto-discovering competitors for niche: {request.niche}")

    try:
        competitors = await auto_discover_and_add_competitors(
            niche=request.niche,
            our_products=request.our_products,
            db_session=db,
            max_competitors=request.max_competitors
        )

        return {
            'success': True,
            'discovered_count': len(competitors),
            'competitors': competitors,
            'message': f'Successfully discovered and added {len(competitors)} competitors!'
        }

    except Exception as e:
        logger.error(f"Error in auto-discovery: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AddCompetitorRequest(BaseModel):
    url: str
    name: Optional[str] = None
    competitor_type: str = 'DIRECT'
    threat_level: str = 'MEDIUM'
    priority: int = 5
    primary_niches: Optional[List[str]] = None


class UpdateCompetitorRequest(BaseModel):
    name: Optional[str] = None
    competitor_type: Optional[str] = None
    threat_level: Optional[str] = None
    priority: Optional[int] = None
    primary_niches: Optional[List[str]] = None
    ad_platforms: Optional[List[str]] = None
    marketing_angles: Optional[List[str]] = None


# ============================================================================
# COMPETITOR MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/")
async def list_competitors(
    sort_by: str = Query('threat_level', description="Sort field"),
    competitor_type: Optional[str] = Query(None, description="Filter by type"),
    threat_level: Optional[str] = Query(None, description="Filter by threat level"),
    status: str = Query('ACTIVE', description="Filter by status"),
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    List all tracked competitors

    Query params:
    - sort_by: threat_level, name, revenue, priority
    - competitor_type: DIRECT, INDIRECT, MARKET_LEADER, EMERGING
    - threat_level: HIGH, MEDIUM, LOW
    - status: ACTIVE, PAUSED, REMOVED
    """
    engine = CompetitorIntelligenceEngine(db)
    competitors = await engine.list_competitors(
        sort_by=sort_by,
        competitor_type=competitor_type,
        threat_level=threat_level,
        status=status
    )

    return {
        'competitors': competitors,
        'count': len(competitors)
    }


@router.post("/")
async def add_competitor(
    request: AddCompetitorRequest,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Add new competitor to track

    Body:
    - url: Store URL (required)
    - name: Competitor name (optional, auto-detected)
    - competitor_type: DIRECT, INDIRECT, MARKET_LEADER, EMERGING
    - threat_level: HIGH, MEDIUM, LOW
    - priority: 1-10
    - primary_niches: List of niche tags
    """
    engine = CompetitorIntelligenceEngine(db)

    try:
        competitor = await engine.add_competitor(
            url=request.url,
            name=request.name,
            competitor_type=request.competitor_type,
            threat_level=request.threat_level,
            priority=request.priority,
            primary_niches=request.primary_niches
        )

        return {
            'success': True,
            'competitor': competitor,
            'message': f"Added competitor: {competitor['name']}"
        }

    except Exception as e:
        logger.error(f"Error adding competitor: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/{competitor_id}")
async def get_competitor(
    competitor_id: str,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get full competitor profile with analysis
    """
    engine = CompetitorIntelligenceEngine(db)
    competitor = await engine.get_competitor(competitor_id)

    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    return competitor


@router.put("/{competitor_id}")
async def update_competitor_info(
    competitor_id: str,
    request: UpdateCompetitorRequest,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Update competitor information
    """
    from ospra_os.models.competitor import Competitor
    from sqlalchemy import select

    query = select(Competitor).where(Competitor.competitor_id == competitor_id)
    result = await db.execute(query)
    competitor = result.scalar_one_or_none()

    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    # Update fields
    if request.name:
        competitor.name = request.name
    if request.competitor_type:
        competitor.competitor_type = request.competitor_type
    if request.threat_level:
        competitor.threat_level = request.threat_level
    if request.priority:
        competitor.priority = request.priority
    if request.primary_niches:
        competitor.primary_niches = request.primary_niches
    if request.ad_platforms:
        competitor.ad_platforms = request.ad_platforms
    if request.marketing_angles:
        competitor.primary_marketing_angles = request.marketing_angles

    await db.commit()

    return {'success': True, 'message': 'Competitor updated'}


@router.delete("/{competitor_id}")
async def delete_competitor(
    competitor_id: str,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Remove competitor from tracking (soft delete)
    """
    engine = CompetitorIntelligenceEngine(db)
    await engine.remove_competitor(competitor_id)

    return {'success': True, 'message': 'Competitor removed'}


@router.post("/{competitor_id}/refresh")
async def refresh_competitor(
    competitor_id: str,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Re-scrape competitor data
    """
    engine = CompetitorIntelligenceEngine(db)
    competitor = await engine.update_competitor(competitor_id)

    return {
        'success': True,
        'competitor': competitor,
        'message': 'Competitor data refreshed'
    }


# ============================================================================
# PRODUCT TRACKING ENDPOINTS
# ============================================================================

@router.get("/{competitor_id}/products")
async def get_competitor_products(
    competitor_id: str,
    category: Optional[str] = None,
    in_stock_only: bool = False,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get products from a competitor

    Query params:
    - category: Filter by category
    - in_stock_only: Show only in-stock products
    """
    engine = CompetitorIntelligenceEngine(db)
    products = await engine.get_competitor_products(
        competitor_id=competitor_id,
        category=category,
        in_stock_only=in_stock_only
    )

    return {
        'competitor_id': competitor_id,
        'products': products,
        'count': len(products)
    }


@router.get("/products/{product_id}")
async def get_competitor_product(
    product_id: str,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get competitor product details
    """
    from ospra_os.models.competitor import CompetitorProduct
    from sqlalchemy import select

    query = select(CompetitorProduct).where(CompetitorProduct.product_id == product_id)
    result = await db.execute(query)
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get price history
    tracker = PriceTracker(db)
    price_history = await tracker.get_price_history(product_id, days=90)
    price_trends = await tracker.get_price_trends(product_id)

    return {
        'product': {
            'product_id': product.product_id,
            'name': product.name,
            'url': product.url,
            'image_url': product.image_url,
            'current_price': product.current_price,
            'original_price': product.original_price,
            'discount_percent': product.discount_percent,
            'in_stock': product.in_stock,
            'our_product_id': product.our_product_id,
            'our_price': product.our_price,
            'price_difference': product.price_difference
        },
        'price_history': price_history,
        'price_trends': price_trends
    }


@router.get("/products/{product_id}/price-history")
async def get_price_history(
    product_id: str,
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get price history for a product

    Query params:
    - days: Number of days of history (1-365)
    """
    tracker = PriceTracker(db)
    history = await tracker.get_price_history(product_id, days)

    return {
        'product_id': product_id,
        'history': history,
        'data_points': len(history)
    }


@router.get("/products/overlapping")
async def get_overlapping_products(
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get products that we and competitors both sell
    """
    from ospra_os.models.competitor import CompetitorProduct
    from sqlalchemy import select

    query = select(CompetitorProduct).where(
        CompetitorProduct.our_product_id.isnot(None)
    ).limit(100)

    result = await db.execute(query)
    products = result.scalars().all()

    return {
        'overlapping_products': [
            {
                'our_product_id': p.our_product_id,
                'our_product_name': p.our_product_name,
                'our_price': p.our_price,
                'competitor_id': p.competitor_id,
                'competitor_price': p.current_price,
                'price_difference': p.price_difference,
                'we_are': p.we_are
            }
            for p in products
        ],
        'count': len(products)
    }


@router.get("/products/gaps")
async def get_product_gaps(
    min_competitors: int = Query(2, ge=1),
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get products competitors have that we don't

    Query params:
    - min_competitors: Minimum number of competitors carrying product
    """
    analyzer = GapAnalyzer(db)
    gaps = await analyzer.find_product_gaps(min_competitors_carrying=min_competitors)

    return {
        'product_gaps': gaps,
        'count': len(gaps)
    }


# ============================================================================
# PRICE INTELLIGENCE ENDPOINTS
# ============================================================================

@router.get("/price-changes")
async def get_price_changes(
    hours: int = Query(24, ge=1, le=168),
    min_change_percent: float = Query(5.0, ge=0),
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get recent price changes

    Query params:
    - hours: Look back period (1-168)
    - min_change_percent: Minimum change percentage
    """
    tracker = PriceTracker(db)
    changes = await tracker.get_all_price_changes(hours, min_change_percent)

    return {
        'price_changes': changes,
        'count': len(changes),
        'hours': hours
    }


@router.get("/price-comparison")
async def get_price_comparison(
    threshold_percent: float = Query(15.0, ge=0),
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Compare our prices vs competitors

    Query params:
    - threshold_percent: Minimum price difference to show
    """
    analyzer = GapAnalyzer(db)
    price_gaps = await analyzer.find_price_gaps(threshold_percent)

    return {
        'price_gaps': price_gaps,
        'count': len(price_gaps)
    }


@router.get("/pricing-opportunities")
async def get_pricing_opportunities(
    threshold_percent: float = Query(10.0, ge=0),
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get price adjustment recommendations

    Query params:
    - threshold_percent: Significant difference threshold
    """
    tracker = PriceTracker(db)
    opportunities = await tracker.get_pricing_opportunities(threshold_percent)

    return {
        'opportunities': opportunities,
        'count': len(opportunities)
    }


# ============================================================================
# MARKET ANALYSIS ENDPOINTS
# ============================================================================

@router.get("/market-share")
async def get_market_share(
    niche: str = Query(..., description="Product niche"),
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get market share estimates for a niche
    """
    estimator = MarketShareEstimator(db)
    market_share = await estimator.calculate_market_share(niche)

    return market_share


@router.get("/landscape")
async def get_competitive_landscape(
    niche: str = Query(..., description="Product niche"),
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get competitive landscape analysis
    """
    estimator = MarketShareEstimator(db)

    market_share = await estimator.calculate_market_share(niche)
    market_positioning = await estimator.get_market_positioning()
    market_leaders = await estimator.identify_market_leaders(niche, top_n=5)

    return {
        'niche': niche,
        'market_share': market_share,
        'market_positioning': market_positioning,
        'market_leaders': market_leaders
    }


@router.get("/gaps")
async def get_competitive_gaps(
    niche: Optional[str] = None,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get all competitive gaps and opportunities
    """
    analyzer = GapAnalyzer(db)

    product_gaps = await analyzer.find_product_gaps()
    price_gaps = await analyzer.find_price_gaps()
    feature_gaps = await analyzer.find_feature_gaps()

    if niche:
        market_gaps = await analyzer.find_market_gaps(niche)
    else:
        market_gaps = []

    return {
        'product_gaps': product_gaps[:10],  # Top 10
        'price_gaps': price_gaps[:10],
        'feature_gaps': feature_gaps,
        'market_gaps': market_gaps
    }


# ============================================================================
# ACTIVITY & ALERTS ENDPOINTS
# ============================================================================

@router.get("/activity")
async def get_activity(
    days: int = Query(7, ge=1, le=90),
    competitor_id: Optional[str] = None,
    activity_type: Optional[str] = None,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get recent competitor activity

    Query params:
    - days: Look back period (1-90)
    - competitor_id: Filter by specific competitor
    - activity_type: Filter by activity type
    """
    engine = CompetitorIntelligenceEngine(db)
    activities = await engine.get_recent_activity(days, competitor_id, activity_type)

    return {
        'activities': activities,
        'count': len(activities),
        'days': days
    }


@router.get("/alerts")
async def get_alerts(
    unviewed_only: bool = Query(True),
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get competitive alerts

    Query params:
    - unviewed_only: Show only unviewed alerts
    """
    engine = CompetitorIntelligenceEngine(db)
    alerts = await engine.get_competitive_alerts(unviewed_only)

    # Also get price drop alerts
    tracker = PriceTracker(db)
    price_alerts = await tracker.get_price_drop_alerts()

    all_alerts = alerts + [
        {
            **alert,
            'activity_id': f"price_{alert['product_id']}",
            'activity_type': alert['alert_type'],
            'activity_date': alert['changed_at']
        }
        for alert in price_alerts
    ]

    # Sort by severity and date
    severity_order = {'HIGH': 0, 'CRITICAL': 0, 'MEDIUM': 1, 'LOW': 2}
    all_alerts.sort(key=lambda x: (severity_order.get(x.get('severity', 'LOW'), 3), x.get('activity_date', '')), reverse=True)

    return {
        'alerts': all_alerts,
        'count': len(all_alerts)
    }


@router.get("/insights")
async def get_insights(
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get AI-generated competitive insights
    """
    analyzer = GapAnalyzer(db)
    ad_intel = AdIntelligence(db)

    strategic_opportunities = await analyzer.get_strategic_opportunities(top_n=10)
    ad_insights = await ad_intel.get_ad_insights()

    return {
        'strategic_opportunities': strategic_opportunities,
        'ad_insights': ad_insights,
        'generated_at': ad_insights.get('analyzed_at')
    }


# ============================================================================
# AD INTELLIGENCE ENDPOINTS
# ============================================================================

@router.get("/{competitor_id}/ads")
async def get_competitor_ads(
    competitor_id: str,
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get competitor's ad intelligence
    """
    ad_intel = AdIntelligence(db)

    ad_analysis = await ad_intel.get_ad_creative_analysis(competitor_id)
    ad_spend = await ad_intel.estimate_ad_spend(competitor_id)

    return {
        'ad_analysis': ad_analysis,
        'ad_spend': ad_spend
    }


@router.get("/ad-insights")
async def get_ad_insights(
    db: AsyncSession = Depends(get_multi_store_session)
):
    """
    Get market-wide ad insights
    """
    ad_intel = AdIntelligence(db)
    insights = await ad_intel.get_ad_insights()

    return insights


# ============================================================================
# BACKGROUND JOBS STATUS
# ============================================================================

@router.get("/jobs/status")
async def get_intelligence_jobs_status():
    """
    Get Intelligence background jobs status

    Shows status of Level 3 AI autonomous monitoring:
    - Product analysis (every 6hr)
    - Competitor monitoring (every 12hr)
    - Trend tracking (daily)
    - Auto-discovery (daily at 3am)
    - Weekly reports (Sunday 6pm)
    """
    try:
        from ospra_os.intelligence.background_jobs import get_scheduler

        scheduler = get_scheduler()

        if not scheduler.running:
            return {
                'is_running': False,
                'message': 'Intelligence scheduler not started'
            }

        # Get job history
        job_list = []
        for job_name, job_info in scheduler.job_history.items():
            job_list.append({
                'id': job_name,
                'name': job_name.replace('_', ' ').title(),
                'last_run': job_info.get('last_run'),
                'status': job_info.get('status', 'pending'),
                'duration': job_info.get('duration', 0)
            })

        # Get recent alerts
        recent_alerts = [alert.to_dict() for alert in list(scheduler.alerts)[-10:]]  # Last 10 alerts

        return {
            'is_running': True,
            'total_jobs': len(job_list),
            'jobs': job_list,
            'recent_alerts': recent_alerts,
            'schedule': {
                'analyze_products': 'Every 6 hours',
                'monitor_competitors': 'Every 12 hours',
                'track_trends': 'Daily at 9:00 AM',
                'auto_discover': 'Daily at 3:00 AM',
                'weekly_report': 'Sundays at 6:00 PM'
            }
        }

    except Exception as e:
        logger.error(f"Failed to get intelligence jobs status: {e}")
        return {
            'is_running': False,
            'error': str(e)
        }


logger.info("[SUCCESS] Competitor Intelligence routes initialized")
