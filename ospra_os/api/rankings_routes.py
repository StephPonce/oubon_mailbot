"""
Product Rankings API Routes
===========================

Product ranking system with leaderboards, movers, and historical tracking.

Author: OspraOS
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from ospra_os.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rankings", tags=["Product Rankings"])


def get_tier(rank: int):
    """Determine tier based on rank."""
    if 1 <= rank <= 3:
        return {"name": "ELITE", "emoji": "[TOP]", "color": "#FFD700"}
    elif 4 <= rank <= 10:
        return {"name": "TOP", "emoji": "[FIRST]", "color": "#C0C0C0"}
    elif 11 <= rank <= 20:
        return {"name": "RISING", "emoji": "[SECOND]", "color": "#CD7F32"}
    else:
        return {"name": "UNRANKED", "emoji": "[STATS]", "color": "#808080"}


@router.get("/top")
async def get_top_rankings(
    limit: int = 20,
    store_id: Optional[int] = None,
    niche: Optional[str] = None,
    settings: Settings = Depends(get_settings)
):
    """
    Get current top ranked products from product_history database.

    Query params:
    - limit: Number of products to return (default: 20)
    - store_id: Filter by store (optional) - DEPRECATED
    - niche: Filter by niche (optional)

    Returns: Top products with rankings and scores
    """
    try:
        import sqlite3

        db_path = "data/product_history.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT
                id, name, niche, price, cost, score,
                profit_margin, estimated_profit, rating, orders,
                velocity_score, image_url, aliexpress_url, source,
                description, last_updated
            FROM products
        """

        params = []
        if niche:
            query += " WHERE niche = ?"
            params.append(niche)

        query += " ORDER BY score DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        rankings = []
        for idx, row in enumerate(rows, start=1):
            rankings.append({
                "rank": idx,
                "tier": get_tier(idx),
                "product_id": row["id"],
                "product_name": row["name"],
                "composite_score": float(row["score"]) if row["score"] else 0.0,
                "score_breakdown": {
                    "ai_score": float(row["score"]) if row["score"] else 0.0,
                    "velocity_score": float(row["velocity_score"]) if row["velocity_score"] else 0.0,
                    "profit_margin": float(row["profit_margin"]) if row["profit_margin"] else 0.0,
                    "rating": float(row["rating"]) if row["rating"] else 0.0,
                },
                "niche": row["niche"],
                "price": float(row["price"]) if row["price"] else 0.0,
                "cost": float(row["cost"]) if row["cost"] else 0.0,
                "profit_margin": float(row["profit_margin"]) if row["profit_margin"] else 0.0,
                "estimated_profit": float(row["estimated_profit"]) if row["estimated_profit"] else 0.0,
                "rating": float(row["rating"]) if row["rating"] else 0.0,
                "orders": int(row["orders"]) if row["orders"] else 0,
                "image_url": row["image_url"],
                "aliexpress_url": row["aliexpress_url"],
                "source": row["source"],
                "last_updated": row["last_updated"],
                "rank_change": 0,
                "rank_direction": "stable"
            })

        return {
            "success": True,
            "rankings": rankings,
            "total_count": len(rankings),
            "last_updated": datetime.utcnow().isoformat(),
            "next_update": (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }

    except Exception as e:
        logger.error(f"Rankings error: {e}")
        return {
            "success": False,
            "error": str(e),
            "rankings": []
        }


@router.get("/movers")
async def get_ranking_movers(
    direction: str = 'gainers',
    limit: int = 10,
    timeframe: str = '24h',
    settings: Settings = Depends(get_settings)
):
    """
    Get biggest rank changes (gainers or losers).

    Query params:
    - direction: 'gainers' or 'losers' (default: 'gainers')
    - limit: Number of products (default: 10)
    - timeframe: '24h', '7d', or '30d' (default: '24h')

    Returns: Products with biggest rank movements
    """
    try:
        from ospra_os.intelligence.ranking_engine import RankingEngine
        from ospra_os.database import get_multi_store_session

        db_url = settings.database_url or "sqlite:///./oubon_store.db"
        session = get_multi_store_session(db_url)
        engine = RankingEngine(session)

        if direction == 'gainers':
            movers = await engine.get_biggest_gainers(limit=limit, timeframe=timeframe)
        else:
            movers = await engine.get_biggest_losers(limit=limit, timeframe=timeframe)

        return {
            "success": True,
            "movers": movers,
            "direction": direction,
            "timeframe": timeframe
        }

    except Exception as e:
        logger.error(f"Movers error: {e}")
        return {
            "success": False,
            "error": str(e),
            "movers": []
        }


@router.get("/product/{product_id}")
async def get_product_ranking_details(
    product_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Get detailed ranking information for a single product.

    Returns: Complete ranking history and stats
    """
    try:
        from ospra_os.intelligence.ranking_engine import RankingEngine
        from ospra_os.database import get_multi_store_session

        db_url = settings.database_url or "sqlite:///./oubon_store.db"
        session = get_multi_store_session(db_url)
        engine = RankingEngine(session)

        details = await engine.get_product_rank_details(product_id)

        if not details:
            return {
                "success": False,
                "error": "Product not found"
            }

        return {
            "success": True,
            **details
        }

    except Exception as e:
        logger.error(f"Product ranking details error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/history/{product_id}")
async def get_product_rank_history(
    product_id: int,
    days: int = 30,
    settings: Settings = Depends(get_settings)
):
    """
    Get rank history for a product over time.

    Query params:
    - days: Number of days to look back (default: 30)

    Returns: Historical rankings with dates
    """
    try:
        from ospra_os.database import get_multi_store_session, RankingHistory

        db_url = settings.database_url or "sqlite:///./oubon_store.db"
        session = get_multi_store_session(db_url)

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        history = session.query(RankingHistory).filter(
            RankingHistory.product_id == product_id,
            RankingHistory.snapshot_date >= cutoff_date
        ).order_by(RankingHistory.snapshot_date.asc()).all()

        if not history:
            return {
                "success": True,
                "history": [],
                "message": "No history available for this product"
            }

        history_data = [
            {
                "date": h.snapshot_date.isoformat(),
                "rank": h.rank,
                "composite_score": h.composite_score,
                "rank_change": h.rank_change,
                "rank_direction": h.rank_direction,
                "tier_name": h.tier_name
            }
            for h in history
        ]

        return {
            "success": True,
            "product_id": product_id,
            "history": history_data,
            "days_tracked": days
        }

    except Exception as e:
        logger.error(f"Rank history error: {e}")
        return {
            "success": False,
            "error": str(e),
            "history": []
        }


@router.get("/new-entries")
async def get_new_entries(
    limit: int = 10,
    settings: Settings = Depends(get_settings)
):
    """
    Get products that recently entered the top 20 rankings.

    Returns: Products that are new to the top 20
    """
    try:
        from ospra_os.database import get_multi_store_session, RankingHistory
        from sqlalchemy import and_

        db_url = settings.database_url or "sqlite:///./oubon_store.db"
        session = get_multi_store_session(db_url)

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        new_entries = session.query(RankingHistory).filter(
            and_(
                RankingHistory.snapshot_date >= today,
                RankingHistory.rank <= 20,
                RankingHistory.rank_direction == 'new'
            )
        ).order_by(RankingHistory.rank.asc()).limit(limit).all()

        entries_data = [
            {
                "product_id": entry.product_id,
                "rank": entry.rank,
                "composite_score": entry.composite_score,
                "tier_name": entry.tier_name,
                "entered_date": entry.snapshot_date.isoformat()
            }
            for entry in new_entries
        ]

        return {
            "success": True,
            "new_entries": entries_data,
            "count": len(entries_data)
        }

    except Exception as e:
        logger.error(f"New entries error: {e}")
        return {
            "success": False,
            "error": str(e),
            "new_entries": []
        }


@router.get("/fallen")
async def get_fallen_products(
    limit: int = 10,
    settings: Settings = Depends(get_settings)
):
    """
    Get products that recently dropped out of the top 20 rankings.

    Returns: Products that were previously in top 20 but are no longer
    """
    try:
        from ospra_os.database import get_multi_store_session, RankingHistory
        from sqlalchemy import and_

        db_url = settings.database_url or "sqlite:///./oubon_store.db"
        session = get_multi_store_session(db_url)

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)

        yesterday_top_20 = session.query(RankingHistory.product_id).filter(
            and_(
                RankingHistory.snapshot_date >= yesterday,
                RankingHistory.snapshot_date < today,
                RankingHistory.rank <= 20
            )
        ).all()

        yesterday_product_ids = {p.product_id for p in yesterday_top_20}

        today_top_20 = session.query(RankingHistory.product_id).filter(
            and_(
                RankingHistory.snapshot_date >= today,
                RankingHistory.rank <= 20
            )
        ).all()

        today_product_ids = {p.product_id for p in today_top_20}
        fallen_product_ids = yesterday_product_ids - today_product_ids

        fallen_products = []
        for product_id in list(fallen_product_ids)[:limit]:
            last_rank = session.query(RankingHistory).filter(
                RankingHistory.product_id == product_id
            ).order_by(RankingHistory.snapshot_date.desc()).first()

            if last_rank:
                fallen_products.append({
                    "product_id": product_id,
                    "previous_rank": last_rank.previous_rank or last_rank.rank,
                    "last_score": last_rank.composite_score,
                    "fell_on": last_rank.snapshot_date.isoformat()
                })

        return {
            "success": True,
            "fallen_products": fallen_products,
            "count": len(fallen_products)
        }

    except Exception as e:
        logger.error(f"Fallen products error: {e}")
        return {
            "success": False,
            "error": str(e),
            "fallen_products": []
        }


logger.info("[SUCCESS] Rankings routes loaded")
