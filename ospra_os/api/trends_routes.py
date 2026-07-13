"""
Live Trends Dashboard API Routes
================================

Real-time product momentum tracking with stock market-style indicators.

Author: OspraOS
"""

import logging
from fastapi import APIRouter, Depends
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# T41 — AUTH POSTURE DECISION (documented):
# The live-trends surface (momentum, movers, breakouts, heatmap) is the
# platform's premium market-intelligence feature and each call drives backend
# compute (discovery-cache reads + momentum math). The data is AGGREGATE
# (market-wide, not per-tenant), so there is no IDOR/ownership concern — the
# right control is authentication, NOT tenant-scoping. Decision: require a
# logged-in user (any tier); tier-gating is left as a separate PRODUCT call.
# The frontend already calls these via authService (JWT attached), so this is
# non-breaking. The duplicate inline @app.get("/api/trends/*") handlers in
# main.py carry the same gate for defense in depth.
router = APIRouter(
    prefix="/api/trends",
    tags=["Live Trends"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/live")
async def get_live_trending_products(
    limit: int = 20,
    sort_by: str = 'velocity',
    settings: Settings = Depends(get_settings)
):
    """
    Get top trending products with real-time momentum indicators.

    Stock market-style live trends with velocity scores, momentum indicators,
    and rank changes. Updates every 5 minutes via background jobs.

    Query params:
    - limit: Number of products to return (default: 20)
    - sort_by: Sort criterion ('velocity', 'rank', 'breakout')

    Returns: Top trending products with momentum data
    """
    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.database.product_history import ProductHistoryDB

        db = ProductHistoryDB()
        products_data = db.get_all_products(niche=None)
        products_data = products_data[:limit * 2]

        tracker = get_momentum_tracker()
        trending = await tracker.get_trending_products(
            products_data=products_data,
            limit=limit,
            sort_by=sort_by
        )

        return {
            'success': True,
            'count': len(trending),
            'products': trending,
            'last_updated': trending[0]['last_updated'] if trending else None
        }

    except Exception as e:
        logger.error(f"Live trends error: {e}")
        return {
            'success': False,
            'error': str(e),
            'products': []
        }


@router.get("/movers")
async def get_biggest_movers(
    direction: str = 'up',
    limit: int = 10,
    settings: Settings = Depends(get_settings)
):
    """
    Get products with biggest rank changes (movers & shakers).

    Query params:
    - direction: 'up' for gainers, 'down' for losers (default: 'up')
    - limit: Number to return (default: 10)

    Returns: Products with biggest rank movements
    """
    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.database.product_history import ProductHistoryDB

        db = ProductHistoryDB()
        products_data = db.get_all_products(niche=None)
        products_data = products_data[:50]
        tracker = get_momentum_tracker()

        trending = await tracker.get_trending_products(
            products_data=products_data,
            limit=50
        )

        movers = tracker.get_biggest_movers(
            products=trending,
            limit=limit,
            direction=direction
        )

        return {
            'success': True,
            'direction': direction,
            'count': len(movers),
            'movers': movers
        }

    except Exception as e:
        logger.error(f"Movers error: {e}")
        return {
            'success': False,
            'error': str(e),
            'movers': []
        }


@router.get("/breakouts")
async def get_breakout_products(settings: Settings = Depends(get_settings)):
    """
    Get products with explosive momentum (>50% velocity).

    Identifies breakout products showing rapid acceleration.
    Similar to stock market breakout detection.

    Returns: Products with breakout momentum
    """
    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.database.product_history import ProductHistoryDB

        db = ProductHistoryDB()
        products_data = db.get_all_products(niche=None)
        products_data = products_data[:100]
        tracker = get_momentum_tracker()

        trending = await tracker.get_trending_products(
            products_data=products_data,
            limit=100
        )

        breakouts = tracker.get_breakout_products(trending)

        return {
            'success': True,
            'count': len(breakouts),
            'breakouts': breakouts,
            'threshold': 50.0
        }

    except Exception as e:
        logger.error(f"Breakouts error: {e}")
        return {
            'success': False,
            'error': str(e),
            'breakouts': []
        }


@router.get("/product/{product_id}")
async def get_product_momentum(
    product_id: str,
    settings: Settings = Depends(get_settings)
):
    """
    Get detailed momentum data for a single product.

    Path params:
    - product_id: Product identifier

    Returns: Complete momentum breakdown with metrics
    """
    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.dashboard.routes import get_product_by_id

        product = await get_product_by_id(product_id)
        if not product:
            return {
                'success': False,
                'error': 'Product not found'
            }

        tracker = get_momentum_tracker()

        current_metrics = {
            "google_trends": product.get("trend_score", 0),
            "velocity_score": product.get("velocity_score", 0),
            "final_score": product.get("final_score", 0),
        }

        baseline_metrics = {k: v * 0.7 for k, v in current_metrics.items()}

        momentum = tracker.calculate_product_momentum(
            product_id=product_id,
            product_name=product.get("name", "Unknown"),
            current_metrics=current_metrics,
            baseline_metrics=baseline_metrics,
            current_rank=product.get("rank", 0),
            previous_rank=product.get("previous_rank")
        )

        return {
            'success': True,
            'product': momentum
        }

    except Exception as e:
        logger.error(f"Product momentum error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@router.get("/heatmap")
async def get_momentum_heatmap(
    rows: int = 10,
    cols: int = 5,
    settings: Settings = Depends(get_settings)
):
    """
    Get heat map visualization data.

    Query params:
    - rows: Number of rows in grid (default: 10)
    - cols: Number of columns in grid (default: 5)

    Returns: Grid data with color-coded momentum cells
    """
    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.database.product_history import ProductHistoryDB

        total_cells = rows * cols
        db = ProductHistoryDB()
        products_data = db.get_all_products(niche=None)
        products_data = products_data[:total_cells]

        tracker = get_momentum_tracker()
        trending = await tracker.get_trending_products(
            products_data=products_data,
            limit=total_cells
        )

        heatmap = tracker.generate_heatmap_data(
            products=trending,
            grid_size=(rows, cols)
        )

        return {
            'success': True,
            **heatmap
        }

    except Exception as e:
        logger.error(f"Heatmap error: {e}")
        return {
            'success': False,
            'error': str(e),
            'grid': []
        }


logger.info("[SUCCESS] Trends routes loaded")
