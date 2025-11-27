"""
Optimized Analytics Database Queries
High-performance SQL queries with proper indexing
"""

from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime


class AnalyticsQueries:
    """
    Optimized database queries for analytics
    """

    @staticmethod
    def revenue_by_date_range(
        session: Session,
        start_date: datetime,
        end_date: datetime,
        store_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get revenue aggregated by date

        Uses indexed date columns for fast querying
        """
        query = text("""
            SELECT
                DATE(p.last_updated) as date,
                SUM(p.total_revenue) as revenue,
                SUM(p.total_sales) as orders,
                AVG(p.selling_price) as avg_price
            FROM products p
            WHERE p.last_updated BETWEEN :start_date AND :end_date
            """ + (" AND p.store_id = :store_id" if store_id else "") + """
            GROUP BY DATE(p.last_updated)
            ORDER BY date DESC
        """)

        params = {
            "start_date": start_date,
            "end_date": end_date
        }

        if store_id:
            params["store_id"] = store_id

        result = session.execute(query, params)

        return [
            {
                "date": row[0].isoformat() if row[0] else None,
                "revenue": float(row[1]) if row[1] else 0,
                "orders": int(row[2]) if row[2] else 0,
                "avg_price": float(row[3]) if row[3] else 0
            }
            for row in result
        ]

    @staticmethod
    def top_products_by_revenue(
        session: Session,
        limit: int = 20,
        store_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get top products by revenue with single query
        """
        query = text("""
            SELECT
                p.id,
                p.product_name,
                p.product_sku,
                p.total_revenue,
                p.total_sales,
                p.conversion_rate,
                p.profit_margin,
                p.status,
                s.store_name
            FROM products p
            LEFT JOIN stores s ON p.store_id = s.id
            """ + (" WHERE p.store_id = :store_id" if store_id else "") + """
            ORDER BY p.total_revenue DESC
            LIMIT :limit
        """)

        params = {"limit": limit}
        if store_id:
            params["store_id"] = store_id

        result = session.execute(query, params)

        return [
            {
                "id": row[0],
                "name": row[1],
                "sku": row[2],
                "revenue": float(row[3]) if row[3] else 0,
                "orders": int(row[4]) if row[4] else 0,
                "conversion_rate": float(row[5]) if row[5] else 0,
                "profit_margin": float(row[6]) if row[6] else 0,
                "status": row[7],
                "store_name": row[8]
            }
            for row in result
        ]

    @staticmethod
    def store_performance_summary(
        session: Session,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all stores with performance metrics in single query
        """
        query = text("""
            SELECT
                s.id,
                s.store_name,
                s.platform,
                s.total_revenue,
                s.monthly_revenue,
                s.total_orders,
                s.conversion_rate,
                s.rank_position,
                s.rank_change,
                COUNT(DISTINCT p.id) as product_count,
                COUNT(DISTINCT CASE WHEN p.status IN ('active', 'deployed') THEN p.id END) as active_products
            FROM stores s
            LEFT JOIN products p ON s.id = p.store_id
            """ + (" WHERE s.user_id = :user_id" if user_id else "") + """
            GROUP BY s.id
            ORDER BY s.total_revenue DESC
        """)

        params = {}
        if user_id:
            params["user_id"] = user_id

        result = session.execute(query, params)

        return [
            {
                "id": row[0],
                "name": row[1],
                "platform": row[2],
                "revenue": float(row[3]) if row[3] else 0,
                "monthly_revenue": float(row[4]) if row[4] else 0,
                "orders": int(row[5]) if row[5] else 0,
                "conversion_rate": float(row[6]) if row[6] else 0,
                "rank_position": row[7],
                "rank_change": row[8] or 0,
                "product_count": row[9] or 0,
                "active_products": row[10] or 0
            }
            for row in result
        ]

    @staticmethod
    def product_costs_summary(
        session: Session,
        store_id: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Calculate total product costs efficiently
        """
        query = text("""
            SELECT
                SUM(p.supplier_cost * p.total_sales) as total_cogs,
                COUNT(*) as product_count,
                SUM(p.total_sales) as total_units_sold
            FROM products p
            """ + (" WHERE p.store_id = :store_id" if store_id else ""))

        params = {}
        if store_id:
            params["store_id"] = store_id

        result = session.execute(query, params).first()

        return {
            "total_cogs": float(result[0]) if result and result[0] else 0,
            "product_count": int(result[1]) if result and result[1] else 0,
            "total_units_sold": int(result[2]) if result and result[2] else 0
        }
