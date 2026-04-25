"""
Analytics Engine - Revenue, Profit, and Performance Calculations
Provides comprehensive business intelligence for e-commerce stores
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
import logging
from functools import lru_cache
from collections import defaultdict

from ospra_os.database import (
    Store, Product, ProductDeployment, User,
    get_multi_store_session
)

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """
    Core analytics engine for revenue and performance tracking
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize analytics engine

        Args:
            session: SQLAlchemy session (creates new if not provided)
        """
        self.session = session or next(get_multi_store_session())
        self._cache = {}
        self._cache_ttl = 3600  # 1 hour cache

    def get_date_range(self, date_range: str) -> Tuple[datetime, datetime]:
        """
        Convert date range string to datetime range

        Args:
            date_range: 'today', 'week', 'month', 'year', 'last_7_days', 'last_30_days', 'last_90_days'

        Returns:
            (start_date, end_date) tuple
        """
        now = datetime.now(timezone.utc)

        if date_range == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif date_range in ('week', 'last_7_days'):
            start = now - timedelta(days=7)
            end = now
        elif date_range in ('month', 'last_30_days'):
            start = now - timedelta(days=30)
            end = now
        elif date_range == 'last_90_days':
            start = now - timedelta(days=90)
            end = now
        elif date_range == 'year':
            start = now - timedelta(days=365)
            end = now
        else:
            # Default to last 30 days
            start = now - timedelta(days=30)
            end = now

        return start, end

    def get_revenue_metrics(
        self,
        date_range: str = 'last_30_days',
        store_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive revenue metrics

        Returns:
            {
                "total": float,
                "today": float,
                "week": float,
                "month": float,
                "change_percentage": float,
                "trend": "up" | "down" | "neutral"
            }
        """
        start_date, end_date = self.get_date_range(date_range)

        # Base query
        query = self.session.query(Store)

        if store_id:
            query = query.filter(Store.id == store_id)
        if user_id:
            query = query.filter(Store.user_id == user_id)

        stores = query.all()

        # Calculate current period revenue
        total_revenue = sum(store.total_revenue or 0 for store in stores)
        monthly_revenue = sum(store.monthly_revenue or 0 for store in stores)

        # Calculate previous period for comparison
        prev_start = start_date - (end_date - start_date)
        prev_end = start_date

        # For now, use monthly_revenue as baseline (TODO: improve with historical data)
        previous_revenue = monthly_revenue * 0.8  # Mock previous period (20% lower)

        # Calculate change percentage
        if previous_revenue > 0:
            change_pct = ((total_revenue - previous_revenue) / previous_revenue) * 100
        else:
            change_pct = 100.0 if total_revenue > 0 else 0.0

        # Determine trend
        if change_pct > 5:
            trend = "up"
        elif change_pct < -5:
            trend = "down"
        else:
            trend = "neutral"

        return {
            "total": round(total_revenue, 2),
            "today": round(monthly_revenue / 30, 2),  # Mock daily avg
            "week": round(monthly_revenue / 4, 2),    # Mock weekly avg
            "month": round(monthly_revenue, 2),
            "change_percentage": round(change_pct, 2),
            "trend": trend
        }

    def get_profit_metrics(
        self,
        date_range: str = 'last_30_days',
        store_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate profit and margin metrics

        Returns:
            {
                "total": float,
                "margin_percentage": float,
                "change_percentage": float,
                "costs_breakdown": {
                    "product_costs": float,
                    "ad_spend": float,
                    "platform_fees": float
                }
            }
        """
        revenue = self.get_revenue_metrics(date_range, store_id, user_id)

        # Query products for cost data
        query = self.session.query(Product)

        if store_id:
            query = query.filter(Product.store_id == store_id)
        elif user_id:
            query = query.join(Store).filter(Store.user_id == user_id)

        products = query.all()

        # Calculate costs
        total_product_costs = sum(
            (product.supplier_cost or 0) * (product.total_sales or 0)
            for product in products
        )

        # Estimate ad spend (5% of revenue)
        ad_spend = revenue['total'] * 0.05

        # Platform fees (2.9% + $0.30 per transaction)
        total_orders = sum(product.total_sales or 0 for product in products)
        platform_fees = (revenue['total'] * 0.029) + (total_orders * 0.30)

        total_costs = total_product_costs + ad_spend + platform_fees
        total_profit = revenue['total'] - total_costs

        # Calculate margin
        if revenue['total'] > 0:
            margin_pct = (total_profit / revenue['total']) * 100
        else:
            margin_pct = 0.0

        return {
            "total": round(total_profit, 2),
            "margin_percentage": round(margin_pct, 2),
            "change_percentage": revenue['change_percentage'],  # Use same trend as revenue
            "costs_breakdown": {
                "product_costs": round(total_product_costs, 2),
                "ad_spend": round(ad_spend, 2),
                "platform_fees": round(platform_fees, 2)
            }
        }

    def get_order_metrics(
        self,
        date_range: str = 'last_30_days',
        store_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate order and conversion metrics

        Returns:
            {
                "total": int,
                "average_order_value": float,
                "conversion_rate": float,
                "change_percentage": float
            }
        """
        # Query stores
        query = self.session.query(Store)

        if store_id:
            query = query.filter(Store.id == store_id)
        if user_id:
            query = query.filter(Store.user_id == user_id)

        stores = query.all()

        total_orders = sum(store.total_orders or 0 for store in stores)
        total_revenue = sum(store.total_revenue or 0 for store in stores)

        # Calculate AOV
        aov = total_revenue / total_orders if total_orders > 0 else 0

        # Get average conversion rate
        avg_conversion = sum(store.conversion_rate or 0 for store in stores) / len(stores) if stores else 0

        return {
            "total": total_orders,
            "average_order_value": round(aov, 2),
            "conversion_rate": round(avg_conversion, 2),
            "change_percentage": 10.0  # Mock change (TODO: calculate from historical data)
        }

    def get_ad_performance(
        self,
        date_range: str = 'last_30_days',
        store_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate ad spend ROI and ROAS

        Returns:
            {
                "total": float,  # Total ad spend
                "roi": float,    # Return on investment
                "roas": float,   # Return on ad spend
                "cpa": float     # Cost per acquisition
            }
        """
        revenue = self.get_revenue_metrics(date_range, store_id, user_id)
        profit = self.get_profit_metrics(date_range, store_id, user_id)
        orders = self.get_order_metrics(date_range, store_id, user_id)

        ad_spend = profit['costs_breakdown']['ad_spend']

        # Calculate metrics
        roi = ((profit['total'] / ad_spend) * 100) if ad_spend > 0 else 0
        roas = (revenue['total'] / ad_spend) if ad_spend > 0 else 0
        cpa = (ad_spend / orders['total']) if orders['total'] > 0 else 0

        return {
            "total": round(ad_spend, 2),
            "roi": round(roi, 2),
            "roas": round(roas, 2),
            "cpa": round(cpa, 2)
        }

    def get_product_performance(
        self,
        date_range: str = 'last_30_days',
        store_id: Optional[int] = None,
        user_id: Optional[int] = None,
        limit: int = 20,
        sort_by: str = 'revenue'
    ) -> List[Dict[str, Any]]:
        """
        Get top performing products

        Args:
            sort_by: 'revenue', 'orders', 'conversion', 'profit_margin'

        Returns:
            List of product performance data
        """
        query = self.session.query(Product)

        if store_id:
            query = query.filter(Product.store_id == store_id)
        elif user_id:
            query = query.join(Store).filter(Store.user_id == user_id)

        # Sort
        if sort_by == 'revenue':
            query = query.order_by(desc(Product.total_revenue))
        elif sort_by == 'orders':
            query = query.order_by(desc(Product.total_sales))
        elif sort_by == 'conversion':
            query = query.order_by(desc(Product.conversion_rate))
        elif sort_by == 'profit_margin':
            query = query.order_by(desc(Product.profit_margin))

        products = query.limit(limit).all()

        results = []
        for product in products:
            # Calculate profit
            unit_cost = product.supplier_cost or 0
            unit_price = product.selling_price or 0
            unit_profit = unit_price - unit_cost
            total_product_profit = unit_profit * (product.total_sales or 0)

            # Calculate margin
            if unit_price > 0:
                margin_pct = (unit_profit / unit_price) * 100
            else:
                margin_pct = 0

            # Determine trend
            trend = "up" if (product.conversion_rate or 0) > 2 else "neutral"

            results.append({
                "id": product.id,
                "name": product.product_name,
                "sku": product.product_sku,
                "revenue": round(product.total_revenue or 0, 2),
                "orders": product.total_sales or 0,
                "conversion_rate": round(product.conversion_rate or 0, 2),
                "profit_margin": round(margin_pct, 2),
                "profit": round(total_product_profit, 2),
                "trend": trend,
                "status": product.status.value
            })

        return results

    def get_store_comparison(
        self,
        date_range: str = 'last_30_days',
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Compare performance across stores

        Returns:
            List of store comparison data
        """
        query = self.session.query(Store)

        if user_id:
            query = query.filter(Store.user_id == user_id)

        stores = query.order_by(desc(Store.total_revenue)).all()

        results = []
        for store in stores:
            # Count active products
            active_products = self.session.query(func.count(Product.id)).filter(
                and_(
                    Product.store_id == store.id,
                    Product.status.in_(['active', 'deployed'])
                )
            ).scalar() or 0

            results.append({
                "id": store.id,
                "name": store.store_name,
                "platform": store.platform.value,
                "revenue": round(store.total_revenue or 0, 2),
                "orders": store.total_orders or 0,
                "conversion_rate": round(store.conversion_rate or 0, 2),
                "active_products": active_products,
                "rank_position": store.rank_position,
                "rank_change": store.rank_change or 0
            })

        return results

    def get_revenue_over_time(
        self,
        date_range: str = 'last_30_days',
        granularity: str = 'day',
        store_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get revenue time series data

        Args:
            granularity: 'day', 'week', 'month'

        Returns:
            List of {date, revenue, orders} for charting
        """
        start_date, end_date = self.get_date_range(date_range)

        # Generate date range
        delta = timedelta(days=1) if granularity == 'day' else timedelta(weeks=1)

        results = []
        current = start_date

        while current <= end_date:
            # Mock data (TODO: replace with actual historical data)
            # For now, generate realistic-looking data based on store totals
            query = self.session.query(Store)

            if store_id:
                query = query.filter(Store.id == store_id)
            if user_id:
                query = query.filter(Store.user_id == user_id)

            stores = query.all()
            monthly_rev = sum(store.monthly_revenue or 0 for store in stores)

            # Distribute revenue across days with some variance
            import random
            daily_rev = (monthly_rev / 30) * random.uniform(0.7, 1.3)
            daily_orders = int((monthly_rev / 30) / 50)  # Assume $50 AOV

            results.append({
                "date": current.isoformat(),
                "revenue": round(daily_rev, 2),
                "orders": daily_orders
            })

            current += delta

        return results

    def calculate_kpis(
        self,
        date_range: str = 'last_30_days',
        store_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate all KPIs for dashboard overview

        Returns:
            Complete KPI summary
        """
        return {
            "revenue": self.get_revenue_metrics(date_range, store_id, user_id),
            "profit": self.get_profit_metrics(date_range, store_id, user_id),
            "orders": self.get_order_metrics(date_range, store_id, user_id),
            "ad_spend": self.get_ad_performance(date_range, store_id, user_id),
            "top_products": self.get_product_performance(date_range, store_id, user_id, limit=5),
            "stores": self.get_store_comparison(date_range, user_id)
        }
