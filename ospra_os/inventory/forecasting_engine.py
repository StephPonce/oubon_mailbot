"""
Main Inventory Forecasting Engine - Orchestrates all inventory calculations

This is the primary interface for inventory forecasting functionality.
"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import logging

from ospra_os.inventory.velocity_calculator import VelocityCalculator
from ospra_os.inventory.seasonality_detector import SeasonalityDetector
from ospra_os.inventory.restock_optimizer import RestockOptimizer
from ospra_os.inventory.stockout_analyzer import StockoutAnalyzer

logger = logging.getLogger(__name__)


class InventoryForecastingEngine:
    """Main forecasting engine that orchestrates all inventory calculations"""

    def __init__(self):
        self.velocity_calc = VelocityCalculator()
        self.seasonality_detector = SeasonalityDetector()
        self.restock_optimizer = RestockOptimizer()
        self.stockout_analyzer = StockoutAnalyzer()

    async def get_product_forecast(
        self,
        product_id: str,
        product_data: Dict,
        sales_history: List[Dict],
        period_days: int = 30
    ) -> Dict:
        """
        Generate complete inventory forecast for a product

        Args:
            product_id: Product identifier
            product_data: Current product/inventory data
            sales_history: Historical sales records
            period_days: Days of history to analyze

        Returns:
            Complete forecast with all metrics
        """
        try:
            # Extract current data
            current_stock = product_data.get('current_stock', 0)
            unit_cost = product_data.get('unit_cost', 0)
            unit_price = product_data.get('unit_price', 0)
            lead_time_days = product_data.get('lead_time_days', 7)
            min_order_qty = product_data.get('min_order_qty', 10)
            incoming_stock = product_data.get('incoming_stock', 0)

            # 1. Calculate velocity
            velocity = await self.velocity_calc.calculate_velocity(sales_history, period_days)

            # 2. Detect seasonality (if enough history)
            seasonality = await self.seasonality_detector.detect_seasonality(
                product_id, sales_history
            )

            # Get seasonal adjustment for next 30 days
            future_date = date.today() + timedelta(days=15)
            seasonal_factor = 1.0
            if seasonality['is_seasonal'] and seasonality['monthly_indices']:
                seasonal_factor = await self.seasonality_detector.get_adjustment_factor(
                    future_date, seasonality['monthly_indices']
                )

            # 3. Calculate safety stock
            safety_stock_calc = await self.restock_optimizer.calculate_safety_stock(
                velocity['daily_velocity'],
                velocity['standard_deviation'],
                lead_time_days,
                service_level=0.95
            )

            # 4. Calculate reorder point
            reorder_point_calc = await self.restock_optimizer.calculate_reorder_point(
                velocity['daily_velocity'],
                lead_time_days,
                safety_stock_calc['safety_stock']
            )

            # 5. Check if should reorder
            should_reorder = await self.restock_optimizer.should_reorder_now(
                current_stock,
                reorder_point_calc['reorder_point'],
                incoming_stock
            )

            # 6. Calculate optimal order quantity
            annual_demand = velocity['daily_velocity'] * 365
            optimal_qty = await self.restock_optimizer.calculate_optimal_quantity(
                annual_demand,
                unit_cost,
                min_order_qty
            )

            # 7. Get recommended order date
            recommended_date = await self.restock_optimizer.get_recommended_order_date(
                current_stock,
                velocity['daily_velocity'],
                reorder_point_calc['reorder_point'],
                lead_time_days
            )

            # 8. Calculate stockout risk
            stockout_risk = await self.stockout_analyzer.calculate_stockout_risk(
                current_stock,
                velocity['daily_velocity'],
                velocity['standard_deviation'],
                lead_time_days,
                supplier_reliability=0.95,
                seasonal_adjustment=seasonal_factor,
                pending_orders=incoming_stock
            )

            # 9. Calculate revenue at risk
            revenue_risk = await self.stockout_analyzer.calculate_revenue_at_risk(
                velocity['daily_velocity'],
                unit_price,
                stockout_risk['stockout_probability_30d']
            )

            # 10. Calculate days of stock and stockout date
            days_of_stock = current_stock / velocity['daily_velocity'] if velocity['daily_velocity'] > 0 else 999
            stockout_date = date.today() + timedelta(days=int(days_of_stock)) if days_of_stock < 999 else None

            # 11. Determine status
            status, status_icon = self._determine_status(days_of_stock)

            # Build complete forecast
            forecast = {
                "product_id": product_id,
                "product_name": product_data.get('product_name', 'Unknown'),
                "sku": product_data.get('sku', ''),

                "current_status": {
                    "stock_level": current_stock,
                    "reserved": product_data.get('reserved', 0),
                    "available": current_stock - product_data.get('reserved', 0),
                    "incoming": incoming_stock,
                    "status": status,
                    "status_icon": status_icon
                },

                "velocity": {
                    "daily_average": velocity['daily_velocity'],
                    "weekly_average": velocity['weekly_velocity'],
                    "monthly_average": velocity['monthly_velocity'],
                    "trend": velocity['trend']['direction'],
                    "trend_percentage": velocity['trend']['percentage'],
                    "confidence": velocity['confidence']
                },

                "forecast": {
                    "days_of_stock": round(days_of_stock, 1),
                    "stockout_date": stockout_date.isoformat() if stockout_date else None,
                    "units_needed_30d": int(velocity['daily_velocity'] * 30),
                    "units_needed_60d": int(velocity['daily_velocity'] * 60),
                    "units_needed_90d": int(velocity['daily_velocity'] * 90)
                },

                "reorder": {
                    "reorder_point": reorder_point_calc['reorder_point'],
                    "should_reorder": should_reorder['should_reorder'],
                    "reorder_urgency": should_reorder['urgency'],
                    "recommended_quantity": optimal_qty['recommended_quantity'],
                    "recommended_order_date": recommended_date.get('order_date'),
                    "estimated_cost": optimal_qty.get('total_cost', 0),
                    "supplier_lead_time_days": lead_time_days
                },

                "safety_stock": {
                    "recommended": safety_stock_calc['safety_stock'],
                    "current_buffer_days": safety_stock_calc['days_of_buffer'],
                    "service_level": safety_stock_calc['service_level']
                },

                "risk_assessment": {
                    "stockout_risk": stockout_risk['risk_level'],
                    "risk_score": stockout_risk['risk_score'],
                    "risk_factors": stockout_risk['risk_factors'],
                    "probability_30d": stockout_risk['stockout_probability_30d'],
                    "revenue_at_risk": revenue_risk['revenue_at_risk_30d'],
                    "recommended_actions": stockout_risk['recommended_actions']
                },

                "seasonality": {
                    "is_seasonal": seasonality['is_seasonal'],
                    "adjustment_factor": seasonal_factor,
                    "pattern_type": seasonality.get('pattern_type'),
                    "peak_months": seasonality.get('peak_months', []),
                    "notes": seasonality.get('notes', '')
                },

                "last_updated": datetime.now().isoformat()
            }

            return forecast

        except Exception as e:
            logger.error(f"Error generating forecast for {product_id}: {e}")
            return self._get_error_forecast(product_id, str(e))

    def _determine_status(self, days_of_stock: float) -> tuple[str, str]:
        """Determine inventory status level"""
        if days_of_stock <= 0:
            return "OUT_OF_STOCK", ""
        elif days_of_stock < 7:
            return "CRITICAL", ""
        elif days_of_stock < 21:
            return "LOW", ""
        else:
            return "HEALTHY", ""

    def _get_error_forecast(self, product_id: str, error: str) -> Dict:
        """Return error forecast structure"""
        return {
            "product_id": product_id,
            "error": error,
            "current_status": {
                "status": "ERROR",
                "status_icon": "[WARNING]"
            }
        }

    async def get_inventory_health_summary(self, all_forecasts: List[Dict]) -> Dict:
        """
        Calculate overall inventory health across all products

        Returns:
            {
                "total_products": 45,
                "status_breakdown": {"HEALTHY": 32, "LOW": 8, "CRITICAL": 4, "OUT": 1},
                "products_needing_restock": 12,
                "total_revenue_at_risk": 12500.00,
                "average_days_of_stock": 28.5,
                "service_level": 0.96
            }
        """
        if not all_forecasts:
            return {
                "total_products": 0,
                "status_breakdown": {},
                "products_needing_restock": 0
            }

        # Status breakdown
        status_counts = {}
        for forecast in all_forecasts:
            status = forecast.get('current_status', {}).get('status', 'UNKNOWN')
            status_counts[status] = status_counts.get(status, 0) + 1

        # Products needing restock
        need_restock = sum(
            1 for f in all_forecasts
            if f.get('reorder', {}).get('should_reorder', False)
        )

        # Total revenue at risk
        total_risk = sum(
            f.get('risk_assessment', {}).get('revenue_at_risk', 0)
            for f in all_forecasts
        )

        # Average days of stock
        days_values = [
            f.get('forecast', {}).get('days_of_stock', 0)
            for f in all_forecasts
            if f.get('forecast', {}).get('days_of_stock', 0) < 999
        ]
        avg_days = sum(days_values) / len(days_values) if days_values else 0

        return {
            "total_products": len(all_forecasts),
            "status_breakdown": status_counts,
            "products_needing_restock": need_restock,
            "total_revenue_at_risk": round(total_risk, 2),
            "average_days_of_stock": round(avg_days, 1),
            "high_risk_products": sum(
                1 for f in all_forecasts
                if f.get('risk_assessment', {}).get('risk_score', 0) >= 0.5
            )
        }
