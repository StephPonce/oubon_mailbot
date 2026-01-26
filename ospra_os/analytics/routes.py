"""
Analytics API Routes
FastAPI endpoints for revenue, profit, and performance analytics

SECURITY: All endpoints require JWT authentication. User ID is extracted
from the verified token, NOT from query parameters.
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import csv
import io
import logging

from ospra_os.analytics.analytics_engine import AnalyticsEngine
from ospra_os.database import get_multi_store_session, User
from ospra_os.auth.jwt_auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])
logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class AnalyticsOverviewResponse(BaseModel):
    """Complete analytics overview"""
    revenue: Dict[str, Any]
    profit: Dict[str, Any]
    orders: Dict[str, Any]
    ad_spend: Dict[str, Any]


class RevenueTimeSeriesResponse(BaseModel):
    """Revenue over time data"""
    data: List[Dict[str, Any]]
    granularity: str
    date_range: str


class ProductPerformanceResponse(BaseModel):
    """Product performance data"""
    products: List[Dict[str, Any]]
    total_count: int


class StoreComparisonResponse(BaseModel):
    """Store comparison data"""
    stores: List[Dict[str, Any]]


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(
    date_range: str = Query("last_30_days", description="Time range for analytics"),
    store_id: Optional[int] = Query(None, description="Filter by store ID"),
    session: Session = Depends(get_multi_store_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get complete analytics overview with all KPIs

    SECURITY: user_id extracted from JWT token, NOT from query params.

    **Date Range Options**:
    - `today` - Today only
    - `week` / `last_7_days` - Last 7 days
    - `month` / `last_30_days` - Last 30 days
    - `last_90_days` - Last 90 days
    - `year` - Last 365 days

    **Response includes**:
    - Revenue metrics (total, trend, change %)
    - Profit metrics (total, margin, costs breakdown)
    - Order metrics (count, AOV, conversion rate)
    - Ad spend metrics (total, ROI, ROAS, CPA)
    """
    try:
        user_id = current_user.id  # SECURITY: Use authenticated user's ID
        engine = AnalyticsEngine(session)
        kpis = engine.calculate_kpis(date_range, store_id, user_id)

        return {
            "revenue": kpis["revenue"],
            "profit": kpis["profit"],
            "orders": kpis["orders"],
            "ad_spend": kpis["ad_spend"]
        }
    except Exception as e:
        logger.error(f"Error getting analytics overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/revenue", response_model=RevenueTimeSeriesResponse)
async def get_revenue_over_time(
    date_range: str = Query("last_30_days"),
    granularity: str = Query("day", description="day, week, or month"),
    store_id: Optional[int] = Query(None),
    session: Session = Depends(get_multi_store_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get revenue time series data for charts

    SECURITY: user_id extracted from JWT token, NOT from query params.

    **Granularity Options**:
    - `day` - Daily breakdown
    - `week` - Weekly breakdown
    - `month` - Monthly breakdown

    **Returns**: Array of {date, revenue, orders} for charting
    """
    try:
        user_id = current_user.id  # SECURITY: Use authenticated user's ID
        engine = AnalyticsEngine(session)
        data = engine.get_revenue_over_time(date_range, granularity, store_id, user_id)

        return {
            "data": data,
            "granularity": granularity,
            "date_range": date_range
        }
    except Exception as e:
        logger.error(f"Error getting revenue over time: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profit")
async def get_profit_breakdown(
    date_range: str = Query("last_30_days"),
    store_id: Optional[int] = Query(None),
    session: Session = Depends(get_multi_store_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get profit and cost breakdown

    SECURITY: user_id extracted from JWT token, NOT from query params.

    **Returns**:
    - Total profit
    - Profit margin %
    - Cost breakdown (product costs, ad spend, platform fees)
    """
    try:
        user_id = current_user.id  # SECURITY: Use authenticated user's ID
        engine = AnalyticsEngine(session)
        return engine.get_profit_metrics(date_range, store_id, user_id)
    except Exception as e:
        logger.error(f"Error getting profit breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products", response_model=ProductPerformanceResponse)
async def get_product_performance(
    date_range: str = Query("last_30_days"),
    store_id: Optional[int] = Query(None),
    sort_by: str = Query("revenue", description="revenue, orders, conversion, profit_margin"),
    limit: int = Query(20, le=100),
    session: Session = Depends(get_multi_store_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get top performing products

    SECURITY: user_id extracted from JWT token, NOT from query params.

    **Sort Options**:
    - `revenue` - Sort by total revenue
    - `orders` - Sort by number of orders
    - `conversion` - Sort by conversion rate
    - `profit_margin` - Sort by profit margin

    **Returns**: List of products with performance metrics
    """
    try:
        user_id = current_user.id  # SECURITY: Use authenticated user's ID
        engine = AnalyticsEngine(session)
        products = engine.get_product_performance(
            date_range, store_id, user_id, limit, sort_by
        )

        return {
            "products": products,
            "total_count": len(products)
        }
    except Exception as e:
        logger.error(f"Error getting product performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores", response_model=StoreComparisonResponse)
async def get_store_comparison(
    date_range: str = Query("last_30_days"),
    session: Session = Depends(get_multi_store_session),
    current_user: User = Depends(get_current_user)
):
    """
    Compare performance across all stores

    SECURITY: user_id extracted from JWT token, NOT from query params.

    **Returns**: List of stores with:
    - Revenue, orders, conversion rate
    - Product count (total and active)
    - Rank position and change
    """
    try:
        user_id = current_user.id  # SECURITY: Use authenticated user's ID
        engine = AnalyticsEngine(session)
        stores = engine.get_store_comparison(date_range, user_id)

        return {
            "stores": stores
        }
    except Exception as e:
        logger.error(f"Error getting store comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_analytics(
    format: str = Query("csv", description="csv or pdf"),
    date_range: str = Query("last_30_days"),
    store_id: Optional[int] = Query(None),
    session: Session = Depends(get_multi_store_session),
    current_user: User = Depends(get_current_user)
):
    """
    Export analytics data

    SECURITY: user_id extracted from JWT token, NOT from query params.

    **Formats**:
    - `csv` - CSV file download
    - `pdf` - PDF report (TODO)

    **Returns**: Downloadable file
    """
    user_id = current_user.id  # SECURITY: Use authenticated user's ID
    if format == "csv":
        return await export_csv(date_range, store_id, user_id, session)
    elif format == "pdf":
        raise HTTPException(status_code=501, detail="PDF export coming soon")
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'csv' or 'pdf'")


async def export_csv(
    date_range: str,
    store_id: Optional[int],
    user_id: int,
    session: Session
):
    """Generate CSV export of analytics data"""
    try:
        engine = AnalyticsEngine(session)
        kpis = engine.calculate_kpis(date_range, store_id, user_id)
        products = engine.get_product_performance(date_range, store_id, user_id, limit=100)

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write KPIs section
        writer.writerow(['ANALYTICS REPORT'])
        writer.writerow(['Date Range:', date_range])
        writer.writerow(['Generated:', datetime.utcnow().isoformat()])
        writer.writerow([])

        writer.writerow(['REVENUE METRICS'])
        writer.writerow(['Total Revenue:', kpis['revenue']['total']])
        writer.writerow(['Monthly Revenue:', kpis['revenue']['month']])
        writer.writerow(['Change %:', kpis['revenue']['change_percentage']])
        writer.writerow(['Trend:', kpis['revenue']['trend']])
        writer.writerow([])

        writer.writerow(['PROFIT METRICS'])
        writer.writerow(['Total Profit:', kpis['profit']['total']])
        writer.writerow(['Profit Margin %:', kpis['profit']['margin_percentage']])
        writer.writerow(['Product Costs:', kpis['profit']['costs_breakdown']['product_costs']])
        writer.writerow(['Ad Spend:', kpis['profit']['costs_breakdown']['ad_spend']])
        writer.writerow(['Platform Fees:', kpis['profit']['costs_breakdown']['platform_fees']])
        writer.writerow([])

        writer.writerow(['ORDER METRICS'])
        writer.writerow(['Total Orders:', kpis['orders']['total']])
        writer.writerow(['Average Order Value:', kpis['orders']['average_order_value']])
        writer.writerow(['Conversion Rate %:', kpis['orders']['conversion_rate']])
        writer.writerow([])

        # Write products table
        writer.writerow(['TOP PRODUCTS'])
        writer.writerow([
            'Product Name', 'SKU', 'Revenue', 'Orders',
            'Conversion Rate %', 'Profit Margin %', 'Status'
        ])

        for product in products:
            writer.writerow([
                product['name'],
                product['sku'],
                product['revenue'],
                product['orders'],
                product['conversion_rate'],
                product['profit_margin'],
                product['status']
            ])

        # Return CSV file
        from fastapi.responses import StreamingResponse

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=analytics_{date_range}.csv"
            }
        )

    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))
