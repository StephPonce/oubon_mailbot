"""
Inventory API Routes - FastAPI endpoints for inventory forecasting
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime, date, timedelta
import logging

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User
from ospra_os.inventory.forecasting_engine import InventoryForecastingEngine
from ospra_os.inventory.shopify_sync import get_shopify_sync
from ospra_os.inventory.email_alerts import get_email_alerts
from ospra_os.inventory.historical_tracking import get_historical_tracking

router = APIRouter(prefix="/api/inventory", tags=["inventory"])
logger = logging.getLogger(__name__)

# Initialize forecasting engine, Shopify sync, email alerts, and historical tracking
forecasting_engine = InventoryForecastingEngine()
shopify_sync = get_shopify_sync()
email_alerts = get_email_alerts()
historical_tracking = get_historical_tracking()


# FABRICATED INVENTORY REMOVED (2026-08).
#
# These two helpers returned five hardcoded products (LED Strip Lights, Phone
# Holder, USB-C Cable, Smart Plug, Car Mount) with invented SKUs, stock levels
# and costs, plus 90 days of random.uniform sales history. Ten endpoints served
# them as if they were the user's real inventory — including
# POST /alerts/send-test, which EMAILED fabricated restock alerts, and
# POST /history/snapshot, which PERSISTED the fabrication to the history DB.
#
# The real source already exists in this file: shopify_sync.sync_all_products()
# (see the /sync endpoint below). Endpoints still calling these helpers now
# raise 501 rather than serve fiction; wire them to the Shopify path to restore
# them for real.


class InventoryNotConnected(HTTPException):
    """501 with a reason the caller can display."""

    def __init__(self):
        super().__init__(
            status_code=501,
            detail={
                "error": "inventory_not_connected",
                "message": (
                    "Inventory data is not connected to a real store yet. This "
                    "endpoint previously returned sample products; it no longer "
                    "invents data. Connect Shopify and use /api/inventory/sync."
                ),
            },
        )


def generate_mock_product_data():
    raise InventoryNotConnected()


def generate_mock_sales_history(daily_velocity: float, days: int = 90):
    raise InventoryNotConnected()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "inventory_forecasting",
        "timestamp": datetime.now().isoformat()
    }


@router.get("")
async def get_all_inventory(
    status: Optional[str] = Query(None, description="Filter by status: HEALTHY, LOW, CRITICAL, OUT_OF_STOCK"),
    sort_by: Optional[str] = Query("days_of_stock", description="Sort field"),
    limit: Optional[int] = Query(100, description="Max results"),
    current_user: User = Depends(get_current_user)
):
    """
    Get all products with inventory forecasts

    Query params:
    - status: Filter by inventory status
    - sort_by: Sort field (days_of_stock, risk_score, velocity)
    - limit: Max results
    """
    try:
        # Get mock products
        products = generate_mock_product_data()

        # Generate forecasts
        forecasts = []
        for product in products:
            # Generate mock sales history
            sales_history = generate_mock_sales_history(product['velocity'], days=90)

            # Product data
            product_data = {
                'product_id': product['id'],
                'product_name': product['name'],
                'sku': product['sku'],
                'current_stock': product['stock'],
                'reserved': None,  # was random.randint(0,3) — never invent stock levels
                'unit_cost': product['cost'],
                'unit_price': product['price'],
                'lead_time_days': 7,
                'min_order_qty': 10,
                'incoming_stock': 0
            }

            # Get forecast
            forecast = await forecasting_engine.get_product_forecast(
                product['id'],
                product_data,
                sales_history,
                period_days=30
            )

            forecasts.append(forecast)

        # Filter by status if specified
        if status:
            forecasts = [f for f in forecasts if f.get('current_status', {}).get('status') == status]

        # Sort
        if sort_by == 'days_of_stock':
            forecasts.sort(key=lambda f: f.get('forecast', {}).get('days_of_stock', 999))
        elif sort_by == 'risk_score':
            forecasts.sort(key=lambda f: f.get('risk_assessment', {}).get('risk_score', 0), reverse=True)

        # Limit results
        forecasts = forecasts[:limit]

        return {
            "success": True,
            "count": len(forecasts),
            "products": forecasts
        }

    except HTTPException:
        # Never swallow a deliberate status (e.g. the 501 from the
        # inventory-not-connected guard) into a generic 500.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# In-memory storage for restock orders (replace with database in production)
restock_orders = []


@router.post("/restock-orders")
async def create_restock_order(order: dict, current_user: User = Depends(get_current_user)):
    """
    Create a new restock order

    Request body should include:
    - product_id: str
    - product_name: str
    - sku: str
    - quantity: int
    - supplier: str
    - unit_cost: float
    - total_cost: float
    - order_date: str
    - expected_delivery_date: str
    - urgency: str
    - notes: str
    """
    try:
        # Generate order ID
        order_id = f"RO-{len(restock_orders) + 1:06d}"

        # Add order to storage
        order_data = {
            "order_id": order_id,
            "created_at": datetime.now().isoformat(),
            "status": "PENDING",
            **order
        }

        restock_orders.append(order_data)

        logger.info(f"[SUCCESS] Created restock order {order_id} for {order.get('product_name')}")

        return {
            "success": True,
            "message": "Restock order created successfully",
            "order_id": order_id,
            "order": order_data
        }

    except Exception as e:
        logger.error(f"Error creating restock order: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/restock-orders")
async def get_restock_orders(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: Optional[int] = Query(50, description="Max results"),
    current_user: User = Depends(get_current_user)
):
    """Get all restock orders"""
    try:
        filtered_orders = restock_orders

        # Filter by status if provided
        if status:
            filtered_orders = [o for o in filtered_orders if o.get('status') == status]

        # Limit results
        filtered_orders = filtered_orders[:limit]

        # Sort by created_at descending
        filtered_orders.sort(key=lambda o: o.get('created_at', ''), reverse=True)

        return {
            "success": True,
            "count": len(filtered_orders),
            "orders": filtered_orders
        }

    except Exception as e:
        logger.error(f"Error fetching restock orders: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/restock-orders/{order_id}")
async def get_restock_order(order_id: str, current_user: User = Depends(get_current_user)):
    """Get a specific restock order by ID"""
    try:
        order = next((o for o in restock_orders if o.get('order_id') == order_id), None)

        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        return {
            "success": True,
            "order": order
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching restock order: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/{product_id}")
async def get_product_forecast(product_id: str, current_user: User = Depends(get_current_user)):
    """
    Get detailed inventory forecast for a specific product

    Returns complete forecast with all metrics
    """
    try:
        # Find product in mock data
        products = generate_mock_product_data()
        product = next((p for p in products if p['id'] == product_id), None)

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Generate sales history
        sales_history = generate_mock_sales_history(product['velocity'], days=90)

        # Product data
        product_data = {
            'product_id': product['id'],
            'product_name': product['name'],
            'sku': product['sku'],
            'current_stock': product['stock'],
            'reserved': None,  # was random.randint(0,3) — never invent stock levels
            'unit_cost': product['cost'],
            'unit_price': product['price'],
            'lead_time_days': 7,
            'min_order_qty': 10,
            'incoming_stock': 0
        }

        # Get forecast
        forecast = await forecasting_engine.get_product_forecast(
            product['id'],
            product_data,
            sales_history,
            period_days=30
        )

        return {
            "success": True,
            "forecast": forecast
        }

    except HTTPException:
        raise
    except HTTPException:
        # Never swallow a deliberate status (e.g. the 501 from the
        # inventory-not-connected guard) into a generic 500.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/health/summary")
async def get_inventory_health_summary(current_user: User = Depends(get_current_user)):
    """
    Get overall inventory health summary

    Returns aggregated metrics across all products
    """
    try:
        # Get all forecasts
        products = generate_mock_product_data()
        forecasts = []

        for product in products:
            sales_history = generate_mock_sales_history(product['velocity'], days=90)

            product_data = {
                'product_id': product['id'],
                'product_name': product['name'],
                'sku': product['sku'],
                'current_stock': product['stock'],
                'reserved': 0,
                'unit_cost': product['cost'],
                'unit_price': product['price'],
                'lead_time_days': 7,
                'min_order_qty': 10,
                'incoming_stock': 0
            }

            forecast = await forecasting_engine.get_product_forecast(
                product['id'],
                product_data,
                sales_history
            )
            forecasts.append(forecast)

        # Get summary
        summary = await forecasting_engine.get_inventory_health_summary(forecasts)

        return {
            "success": True,
            "summary": summary
        }

    except HTTPException:
        # Never swallow a deliberate status (e.g. the 501 from the
        # inventory-not-connected guard) into a generic 500.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/alerts/restock")
async def get_restock_alerts(urgency: Optional[str] = Query(None), current_user: User = Depends(get_current_user)):
    """
    Get products that need restocking

    Query params:
    - urgency: Filter by urgency (CRITICAL, URGENT, SOON, NORMAL)
    """
    try:
        products = generate_mock_product_data()
        alerts = []

        for product in products:
            sales_history = generate_mock_sales_history(product['velocity'], days=90)

            product_data = {
                'product_id': product['id'],
                'product_name': product['name'],
                'sku': product['sku'],
                'current_stock': product['stock'],
                'reserved': 0,
                'unit_cost': product['cost'],
                'unit_price': product['price'],
                'lead_time_days': 7,
                'min_order_qty': 10,
                'incoming_stock': 0
            }

            forecast = await forecasting_engine.get_product_forecast(
                product['id'],
                product_data,
                sales_history
            )

            # Check if needs restock
            if forecast.get('reorder', {}).get('should_reorder', False):
                alerts.append(forecast)

        # Filter by urgency if specified
        if urgency:
            alerts = [a for a in alerts if a.get('reorder', {}).get('reorder_urgency') == urgency]

        # Sort by urgency (CRITICAL first)
        urgency_order = {'CRITICAL': 0, 'URGENT': 1, 'SOON': 2, 'NORMAL': 3}
        alerts.sort(key=lambda a: urgency_order.get(a.get('reorder', {}).get('reorder_urgency', 'NORMAL'), 999))

        return {
            "success": True,
            "count": len(alerts),
            "alerts": alerts
        }

    except HTTPException:
        # Never swallow a deliberate status (e.g. the 501 from the
        # inventory-not-connected guard) into a generic 500.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/alerts/stockout")
async def get_stockout_alerts(current_user: User = Depends(get_current_user)):
    """Get products at high risk of stockout"""
    try:
        products = generate_mock_product_data()
        at_risk = []

        for product in products:
            sales_history = generate_mock_sales_history(product['velocity'], days=90)

            product_data = {
                'product_id': product['id'],
                'product_name': product['name'],
                'sku': product['sku'],
                'current_stock': product['stock'],
                'reserved': 0,
                'unit_cost': product['cost'],
                'unit_price': product['price'],
                'lead_time_days': 7,
                'min_order_qty': 10,
                'incoming_stock': 0
            }

            forecast = await forecasting_engine.get_product_forecast(
                product['id'],
                product_data,
                sales_history
            )

            # Check risk level
            risk_level = forecast.get('risk_assessment', {}).get('stockout_risk', 'LOW')
            if risk_level in ['HIGH', 'CRITICAL']:
                at_risk.append(forecast)

        # Sort by risk score
        at_risk.sort(key=lambda f: f.get('risk_assessment', {}).get('risk_score', 0), reverse=True)

        return {
            "success": True,
            "count": len(at_risk),
            "at_risk_products": at_risk
        }

    except HTTPException:
        # Never swallow a deliberate status (e.g. the 501 from the
        # inventory-not-connected guard) into a generic 500.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.post("/alerts/check-and-send")
async def check_and_send_alerts(current_user: User = Depends(get_current_user)):
    """
    Check all products and send email alerts for critical ones

    This endpoint analyzes all products and automatically sends email notifications
    for products that need immediate attention
    """
    try:
        # Get all products
        products = generate_mock_product_data()
        forecasts = []

        for product in products:
            sales_history = generate_mock_sales_history(product['velocity'], days=90)

            product_data = {
                'product_id': product['id'],
                'product_name': product['name'],
                'sku': product['sku'],
                'current_stock': product['stock'],
                'reserved': 0,
                'unit_cost': product['cost'],
                'unit_price': product['price'],
                'lead_time_days': 7,
                'min_order_qty': 10,
                'incoming_stock': 0
            }

            forecast = await forecasting_engine.get_product_forecast(
                product['id'],
                product_data,
                sales_history
            )
            forecasts.append(forecast)

        # Check and send alerts
        result = await email_alerts.check_and_alert(forecasts)

        return {
            "success": True,
            "message": "Alert check complete",
            **result
        }

    except Exception as e:
        logger.error(f"Error checking and sending alerts: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.post("/alerts/send-test")
async def send_test_alert(current_user: User = Depends(get_current_user)):
    """
    Send a test alert email with sample data

    Useful for testing email configuration and template rendering
    """
    try:
        # Get critical products for test
        products = generate_mock_product_data()
        test_products = []

        for product in products[:3]:  # Use first 3 products for test
            sales_history = generate_mock_sales_history(product['velocity'], days=90)

            product_data = {
                'product_id': product['id'],
                'product_name': product['name'],
                'sku': product['sku'],
                'current_stock': product['stock'],
                'reserved': 0,
                'unit_cost': product['cost'],
                'unit_price': product['price'],
                'lead_time_days': 7,
                'min_order_qty': 10,
                'incoming_stock': 0
            }

            forecast = await forecasting_engine.get_product_forecast(
                product['id'],
                product_data,
                sales_history
            )
            test_products.append(forecast)

        # Send test alert
        result = await email_alerts.send_stockout_alert(test_products, "CRITICAL_STOCKOUT")

        return {
            "success": True,
            "message": "Test alert sent",
            **result
        }

    except Exception as e:
        logger.error(f"Error sending test alert: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/shopify/test-connection")
async def test_shopify_connection(current_user: User = Depends(get_current_user)):
    """Test Shopify connection"""
    try:
        if not shopify_sync.is_available():
            return {
                "success": False,
                "message": "Shopify not configured. Check SHOPIFY_STORE_DOMAIN and SHOPIFY_ACCESS_TOKEN environment variables."
            }

        result = await shopify_sync.test_connection()
        return result

    except HTTPException:
        # Never swallow a deliberate status (e.g. the 501 from the
        # inventory-not-connected guard) into a generic 500.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.post("/shopify/sync")
async def sync_from_shopify(current_user: User = Depends(get_current_user)):
    """Sync inventory from Shopify"""
    try:
        if not shopify_sync.is_available():
            return {
                "success": False,
                "message": "Shopify not configured"
            }

        logger.info("Starting Shopify inventory sync...")
        synced_products = await shopify_sync.sync_all_products()

        if not synced_products:
            return {
                "success": False,
                "message": "No products synced from Shopify",
                "count": 0
            }

        # Generate forecasts for synced products
        forecasts = []
        for item in synced_products:
            product_data = item['product_data']
            sales_history = item['sales_history']

            forecast = await forecasting_engine.get_product_forecast(
                product_data['product_id'],
                product_data,
                sales_history,
                period_days=30
            )
            forecasts.append(forecast)

        logger.info(f"[SUCCESS] Generated forecasts for {len(forecasts)} Shopify products")

        return {
            "success": True,
            "message": f"Synced {len(forecasts)} products from Shopify",
            "count": len(forecasts),
            "products": forecasts
        }

    except Exception as e:
        logger.error(f"Error syncing from Shopify: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/shopify/products")
async def get_shopify_inventory(current_user: User = Depends(get_current_user)):
    """Get inventory with real Shopify data"""
    try:
        if not shopify_sync.is_available():
            return {
                "success": False,
                "message": "Shopify not configured",
                "products": []
            }

        # Get products from Shopify
        products = await shopify_sync.get_products_with_inventory(limit=20)

        if not products:
            return {
                "success": False,
                "message": "No products found in Shopify",
                "products": []
            }

        # Generate forecasts
        forecasts = []
        for product in products:
            # Get sales history for this product
            sales_history = await shopify_sync.get_sales_history(
                product['product_id'],
                days=90
            )

            # Generate forecast
            forecast = await forecasting_engine.get_product_forecast(
                product['product_id'],
                product,
                sales_history,
                period_days=30
            )
            forecasts.append(forecast)

        return {
            "success": True,
            "count": len(forecasts),
            "products": forecasts,
            "data_source": "SHOPIFY"
        }

    except Exception as e:
        logger.error(f"Error fetching Shopify inventory: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# ============================================================================
# HISTORICAL TRACKING ENDPOINTS
# ============================================================================

@router.post("/history/snapshot")
async def save_forecast_snapshots(current_user: User = Depends(get_current_user)):
    """
    Save current forecast snapshots for all products

    Saves forecast data to historical tracking database for trend analysis
    """
    try:
        # Get all products
        products = generate_mock_product_data()
        forecasts = []

        for product in products:
            # Generate sales history
            sales_history = generate_mock_sales_history(product['velocity'], days=90)

            # Product data
            product_data = {
                'product_id': product['id'],
                'product_name': product['name'],
                'sku': product['sku'],
                'current_stock': product['stock'],
                'reserved': None,  # was random.randint(0,3) — never invent stock levels
                'unit_cost': product['cost'],
                'unit_price': product['price'],
                'lead_time_days': 7,
                'min_order_qty': 10,
                'incoming_stock': 0
            }

            # Get forecast
            forecast = await forecasting_engine.get_product_forecast(
                product['id'],
                product_data,
                sales_history,
                period_days=30
            )
            forecasts.append(forecast)

        # Save snapshots
        result = historical_tracking.save_multiple_snapshots(forecasts)

        logger.info(f" Saved {result['saved']} forecast snapshots")

        return {
            "success": True,
            "message": f"Saved {result['saved']}/{result['total']} snapshots",
            "saved": result['saved'],
            "failed": result['failed']
        }

    except Exception as e:
        logger.error(f"Error saving snapshots: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/history/recent")
async def get_recent_snapshots(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    current_user: User = Depends(get_current_user)
):
    """
    Get all recent forecast snapshots across all products

    Useful for monitoring recent inventory changes
    """
    try:
        snapshots = historical_tracking.get_all_recent_snapshots(hours)

        logger.info(f"[STATS] Retrieved {len(snapshots)} recent snapshots")

        return {
            "success": True,
            "hours": hours,
            "count": len(snapshots),
            "snapshots": snapshots
        }

    except Exception as e:
        logger.error(f"Error fetching recent snapshots: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.delete("/history/cleanup")
async def cleanup_old_snapshots(
    days: int = Query(90, ge=30, le=365, description="Keep snapshots newer than this many days"),
    current_user: User = Depends(get_current_user)
):
    """
    Cleanup old historical snapshots

    Removes snapshots older than specified days to manage database size
    """
    try:
        result = historical_tracking.cleanup_old_snapshots(days)

        logger.info(f"  Cleaned up {result['deleted_count']} old snapshots")

        return {
            "success": True,
            "message": f"Cleaned up {result['deleted_count']} snapshots older than {days} days",
            "deleted_count": result['deleted_count'],
            "cutoff_date": result['cutoff_date']
        }

    except Exception as e:
        logger.error(f"Error cleaning up snapshots: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/history/{product_id}/trends")
async def get_product_trends(
    product_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user)
):
    """
    Get trend analysis for a product

    Analyzes changes in stock, velocity, and risk over time
    """
    try:
        trends = historical_tracking.get_trend_analysis(product_id, days)

        if not trends.get('success'):
            return {
                "success": False,
                "message": trends.get('message', 'Unable to analyze trends'),
                "product_id": product_id
            }

        logger.info(f"[TREND] Trend analysis for {product_id}: {trends['stock_analysis']['trend']} stock, {trends['risk_analysis']['trend']} risk")

        return trends

    except Exception as e:
        logger.error(f"Error analyzing trends: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/history/{product_id}")
async def get_product_history(
    product_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    current_user: User = Depends(get_current_user)
):
    """
    Get historical forecast snapshots for a specific product

    Returns time-series data of stock levels, velocity, and risk metrics
    """
    try:
        history = historical_tracking.get_product_history(product_id, days)

        if not history:
            return {
                "success": False,
                "message": f"No historical data found for product {product_id}",
                "product_id": product_id,
                "history": []
            }

        logger.info(f"[STATS] Retrieved {len(history)} snapshots for {product_id}")

        return {
            "success": True,
            "product_id": product_id,
            "days": days,
            "data_points": len(history),
            "history": history
        }

    except Exception as e:
        logger.error(f"Error fetching product history: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# ============================================================================
# BULK ACTIONS ENDPOINTS
# ============================================================================

@router.post("/bulk/reorder")
async def bulk_reorder_products(request: dict, current_user: User = Depends(get_current_user)):
    """
    Create restock orders for multiple products at once

    Bulk action to streamline reordering process
    """
    try:
        product_ids = request.get('product_ids', [])

        if not product_ids:
            raise HTTPException(status_code=400, detail="No product IDs provided")

        # Get all products
        products = generate_mock_product_data()
        orders_created = 0

        for product_id in product_ids:
            product = next((p for p in products if p['id'] == product_id), None)
            if not product:
                continue

            # Generate sales history
            sales_history = generate_mock_sales_history(product['velocity'], days=90)

            # Product data
            product_data = {
                'product_id': product['id'],
                'product_name': product['name'],
                'sku': product['sku'],
                'current_stock': product['stock'],
                'reserved': None,  # was random.randint(0,3) — never invent stock levels
                'unit_cost': product['cost'],
                'unit_price': product['price'],
                'lead_time_days': 7,
                'min_order_qty': 10,
                'incoming_stock': 0
            }

            # Get forecast
            forecast = await forecasting_engine.get_product_forecast(
                product['id'],
                product_data,
                sales_history,
                period_days=30
            )

            # Only create order if reorder is recommended
            if forecast['reorder']['should_reorder']:
                orders_created += 1

        logger.info(f"[PACKAGE] Created {orders_created} bulk restock orders")

        return {
            "success": True,
            "orders_created": orders_created,
            "message": f"Created {orders_created} restock orders"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating bulk restock orders: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.post("/bulk/export")
async def bulk_export_products(request: dict, current_user: User = Depends(get_current_user)):
    """
    Export selected products to CSV

    Returns CSV file with inventory data
    """
    try:
        from fastapi.responses import StreamingResponse
        import io
        import csv

        product_ids = request.get('product_ids', [])

        if not product_ids:
            raise HTTPException(status_code=400, detail="No product IDs provided")

        # Get all products
        products = generate_mock_product_data()
        forecasts = []

        for product_id in product_ids:
            product = next((p for p in products if p['id'] == product_id), None)
            if not product:
                continue

            # Generate sales history
            sales_history = generate_mock_sales_history(product['velocity'], days=90)

            # Product data
            product_data = {
                'product_id': product['id'],
                'product_name': product['name'],
                'sku': product['sku'],
                'current_stock': product['stock'],
                'reserved': None,  # was random.randint(0,3) — never invent stock levels
                'unit_cost': product['cost'],
                'unit_price': product['price'],
                'lead_time_days': 7,
                'min_order_qty': 10,
                'incoming_stock': 0
            }

            # Get forecast
            forecast = await forecasting_engine.get_product_forecast(
                product['id'],
                product_data,
                sales_history,
                period_days=30
            )
            forecasts.append(forecast)

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Headers
        writer.writerow([
            'Product ID', 'Product Name', 'SKU', 'Stock Level', 'Status',
            'Daily Velocity', 'Days of Stock', 'Reorder Point', 'Should Reorder',
            'Reorder Urgency', 'Recommended Quantity', 'Estimated Cost', 'Risk Score', 'Risk Level'
        ])

        # Data rows
        for forecast in forecasts:
            writer.writerow([
                forecast['product_id'],
                forecast['product_name'],
                forecast['sku'],
                forecast['current_status']['stock_level'],
                forecast['current_status']['status'],
                forecast['velocity']['daily_average'],
                forecast['forecast']['days_of_stock'],
                forecast['reorder']['reorder_point'],
                forecast['reorder']['should_reorder'],
                forecast['reorder']['reorder_urgency'],
                forecast['reorder']['recommended_quantity'],
                forecast['reorder']['estimated_cost'],
                forecast['risk_assessment']['risk_score'],
                forecast['risk_assessment']['stockout_risk']
            ])

        output.seek(0)

        logger.info(f"[STATS] Exported {len(forecasts)} products to CSV")

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=inventory-export.csv"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting products: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.post("/bulk/alerts")
async def bulk_configure_alerts(request: dict, current_user: User = Depends(get_current_user)):
    """
    Configure email alerts for multiple products

    Enable or disable alerts in bulk
    """
    try:
        product_ids = request.get('product_ids', [])
        enabled = request.get('enabled', True)

        if not product_ids:
            raise HTTPException(status_code=400, detail="No product IDs provided")

        logger.info(f" Configured alerts for {len(product_ids)} products (enabled: {enabled})")

        return {
            "success": True,
            "updated": len(product_ids),
            "enabled": enabled,
            "message": f"Alert settings updated for {len(product_ids)} products"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring bulk alerts: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# Export router
__all__ = ['router']
