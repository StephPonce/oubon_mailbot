"""
Historical Tracking for Inventory Forecasts

Stores snapshots of inventory forecasts over time to track trends
and analyze forecast accuracy
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class InventoryHistoricalTracking:
    """Manage historical inventory forecast snapshots"""

    def __init__(self, db_path: str = "data/inventory_history.db"):
        """Initialize historical tracking with SQLite database"""
        self.db_path = db_path

        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        logger.info(f"[SUCCESS] Historical tracking initialized: {db_path}")

    def _init_database(self):
        """Create database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forecast_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                sku TEXT,
                snapshot_date TIMESTAMP NOT NULL,
                stock_level INTEGER,
                days_of_stock REAL,
                daily_velocity REAL,
                risk_score REAL,
                risk_level TEXT,
                should_reorder BOOLEAN,
                reorder_urgency TEXT,
                recommended_quantity INTEGER,
                estimated_cost REAL,
                forecast_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_date
            ON forecast_snapshots(product_id, snapshot_date)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshot_date
            ON forecast_snapshots(snapshot_date)
        """)

        conn.commit()
        conn.close()

    def save_snapshot(self, forecast: Dict) -> Dict:
        """
        Save a forecast snapshot to the database

        Args:
            forecast: Complete forecast dictionary

        Returns:
            Result dictionary with snapshot ID
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            snapshot_date = datetime.now()

            cursor.execute("""
                INSERT INTO forecast_snapshots (
                    product_id, product_name, sku, snapshot_date,
                    stock_level, days_of_stock, daily_velocity,
                    risk_score, risk_level, should_reorder,
                    reorder_urgency, recommended_quantity, estimated_cost,
                    forecast_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                forecast.get('product_id'),
                forecast.get('product_name'),
                forecast.get('sku'),
                snapshot_date,
                forecast.get('current_status', {}).get('stock_level'),
                forecast.get('forecast', {}).get('days_of_stock'),
                forecast.get('velocity', {}).get('daily_average'),
                forecast.get('risk_assessment', {}).get('risk_score'),
                forecast.get('risk_assessment', {}).get('stockout_risk'),
                forecast.get('reorder', {}).get('should_reorder'),
                forecast.get('reorder', {}).get('reorder_urgency'),
                forecast.get('reorder', {}).get('recommended_quantity'),
                forecast.get('reorder', {}).get('estimated_cost'),
                json.dumps(forecast)
            ))

            snapshot_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.debug(f"[SUCCESS] Saved snapshot {snapshot_id} for {forecast.get('product_name')}")

            return {
                "success": True,
                "snapshot_id": snapshot_id,
                "product_id": forecast.get('product_id'),
                "snapshot_date": snapshot_date.isoformat()
            }

        except Exception as e:
            logger.error(f"[ERROR] Failed to save snapshot: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def save_multiple_snapshots(self, forecasts: List[Dict]) -> Dict:
        """
        Save multiple forecast snapshots at once

        Args:
            forecasts: List of forecast dictionaries

        Returns:
            Summary of saved snapshots
        """
        results = []
        for forecast in forecasts:
            result = self.save_snapshot(forecast)
            results.append(result)

        successful = [r for r in results if r.get('success')]

        logger.info(f"[SUCCESS] Saved {len(successful)}/{len(forecasts)} snapshots")

        return {
            "success": True,
            "total": len(forecasts),
            "saved": len(successful),
            "failed": len(forecasts) - len(successful),
            "results": results
        }

    def get_product_history(
        self,
        product_id: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Get historical snapshots for a specific product

        Args:
            product_id: Product ID to fetch history for
            days: Number of days of history to retrieve

        Returns:
            List of historical snapshots
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            since_date = datetime.now() - timedelta(days=days)

            cursor.execute("""
                SELECT
                    id, product_id, product_name, sku, snapshot_date,
                    stock_level, days_of_stock, daily_velocity,
                    risk_score, risk_level, should_reorder,
                    reorder_urgency, recommended_quantity, estimated_cost,
                    created_at
                FROM forecast_snapshots
                WHERE product_id = ? AND snapshot_date >= ?
                ORDER BY snapshot_date ASC
            """, (product_id, since_date))

            rows = cursor.fetchall()
            conn.close()

            history = [dict(row) for row in rows]

            logger.debug(f"[STATS] Retrieved {len(history)} snapshots for {product_id}")

            return history

        except Exception as e:
            logger.error(f"[ERROR] Failed to get product history: {e}")
            return []

    def get_all_recent_snapshots(self, hours: int = 24) -> List[Dict]:
        """
        Get all recent snapshots across all products

        Args:
            hours: Number of hours to look back

        Returns:
            List of recent snapshots
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            since_date = datetime.now() - timedelta(hours=hours)

            cursor.execute("""
                SELECT
                    id, product_id, product_name, sku, snapshot_date,
                    stock_level, days_of_stock, daily_velocity,
                    risk_score, risk_level, should_reorder,
                    reorder_urgency, recommended_quantity, estimated_cost,
                    created_at
                FROM forecast_snapshots
                WHERE snapshot_date >= ?
                ORDER BY snapshot_date DESC
            """, (since_date,))

            rows = cursor.fetchall()
            conn.close()

            snapshots = [dict(row) for row in rows]

            logger.debug(f"[STATS] Retrieved {len(snapshots)} recent snapshots")

            return snapshots

        except Exception as e:
            logger.error(f"[ERROR] Failed to get recent snapshots: {e}")
            return []

    def get_trend_analysis(self, product_id: str, days: int = 30) -> Dict:
        """
        Analyze trends for a product over time

        Args:
            product_id: Product ID to analyze
            days: Number of days to analyze

        Returns:
            Trend analysis dictionary
        """
        history = self.get_product_history(product_id, days)

        if len(history) < 2:
            return {
                "success": False,
                "message": "Not enough historical data for trend analysis",
                "data_points": len(history)
            }

        # Calculate trends
        first = history[0]
        last = history[-1]

        stock_change = last['stock_level'] - first['stock_level']
        velocity_change = last['daily_velocity'] - first['daily_velocity']
        risk_change = last['risk_score'] - first['risk_score']

        # Calculate average values
        avg_stock = sum(h['stock_level'] for h in history) / len(history)
        avg_velocity = sum(h['daily_velocity'] for h in history) / len(history)
        avg_risk = sum(h['risk_score'] for h in history) / len(history)

        # Determine trends
        stock_trend = "increasing" if stock_change > 0 else "decreasing" if stock_change < 0 else "stable"
        velocity_trend = "increasing" if velocity_change > 0 else "decreasing" if velocity_change < 0 else "stable"
        risk_trend = "increasing" if risk_change > 0 else "decreasing" if risk_change < 0 else "stable"

        return {
            "success": True,
            "product_id": product_id,
            "product_name": last['product_name'],
            "period_days": days,
            "data_points": len(history),
            "stock_analysis": {
                "current": last['stock_level'],
                "change": stock_change,
                "trend": stock_trend,
                "average": round(avg_stock, 2)
            },
            "velocity_analysis": {
                "current": round(last['daily_velocity'], 2),
                "change": round(velocity_change, 2),
                "trend": velocity_trend,
                "average": round(avg_velocity, 2)
            },
            "risk_analysis": {
                "current": round(last['risk_score'], 2),
                "change": round(risk_change, 2),
                "trend": risk_trend,
                "average": round(avg_risk, 2),
                "current_level": last['risk_level']
            },
            "reorder_history": {
                "times_triggered": sum(1 for h in history if h['should_reorder']),
                "current_urgency": last['reorder_urgency']
            }
        }

    def cleanup_old_snapshots(self, days: int = 90) -> Dict:
        """
        Remove snapshots older than specified days

        Args:
            days: Keep snapshots newer than this many days

        Returns:
            Cleanup summary
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cutoff_date = datetime.now() - timedelta(days=days)

            cursor.execute("""
                DELETE FROM forecast_snapshots
                WHERE snapshot_date < ?
            """, (cutoff_date,))

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"  Cleaned up {deleted_count} old snapshots (older than {days} days)")

            return {
                "success": True,
                "deleted_count": deleted_count,
                "cutoff_date": cutoff_date.isoformat()
            }

        except Exception as e:
            logger.error(f"[ERROR] Failed to cleanup snapshots: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Global instance
_historical_tracking = None


def get_historical_tracking() -> InventoryHistoricalTracking:
    """Get or create global historical tracking instance"""
    global _historical_tracking
    if _historical_tracking is None:
        _historical_tracking = InventoryHistoricalTracking()
    return _historical_tracking
