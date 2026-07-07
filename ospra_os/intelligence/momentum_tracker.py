"""
Stock Market-Style Live Momentum Tracker

Real-time product momentum tracking with velocity calculations,
rank changes, and breakout detection for live trends dashboard.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MomentumTracker:
    """
    Tracks product momentum in real-time by calculating velocity
    and comparing against historical baselines.

    Similar to stock market momentum indicators.
    """

    # Momentum indicators based on velocity score
    INDICATORS = {
        "EXPLOSIVE": {"emoji": "[START]", "threshold": 50.0, "color": "#00FF41"},
        "FAST": {"emoji": "[FAST]", "threshold": 30.0, "color": "#00FF00"},
        "HOT": {"emoji": "[HOT]", "threshold": 15.0, "color": "#7FFF00"},
        "RISING": {"emoji": "[TREND]", "threshold": 5.0, "color": "#ADFF2F"},
        "STABLE": {"emoji": "→", "threshold": -5.0, "color": "#808080"},
        "FALLING": {"emoji": "[DECLINE]", "threshold": -15.0, "color": "#FF8C00"},
        "SLOW": {"emoji": "", "threshold": float('-inf'), "color": "#FF0000"}
    }

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_update = None

    def calculate_velocity(
        self,
        current_value: float,
        baseline_value: float
    ) -> float:
        """
        Calculate velocity (rate of change) as percentage.

        Formula: ((current - baseline) / baseline) * 100

        Args:
            current_value: Current metric value
            baseline_value: Historical baseline value

        Returns:
            Velocity score as percentage
        """
        if baseline_value == 0:
            return 0.0 if current_value == 0 else 100.0

        velocity = ((current_value - baseline_value) / baseline_value) * 100
        return round(velocity, 2)

    def get_momentum_indicator(self, velocity_score: float) -> Dict[str, str]:
        """
        Assign momentum indicator based on velocity score.

        Args:
            velocity_score: Velocity percentage

        Returns:
            Dict with emoji, label, and color
        """
        for label, config in self.INDICATORS.items():
            if velocity_score >= config["threshold"]:
                return {
                    "emoji": config["emoji"],
                    "label": label,
                    "color": config["color"]
                }

        return {
            "emoji": self.INDICATORS["SLOW"]["emoji"],
            "label": "SLOW",
            "color": self.INDICATORS["SLOW"]["color"]
        }

    def calculate_product_momentum(
        self,
        product_id: str,
        product_name: str,
        current_metrics: Dict[str, float],
        baseline_metrics: Dict[str, float],
        current_rank: int,
        previous_rank: Optional[int] = None
    ) -> Dict:
        """
        Calculate complete momentum data for a product.

        Args:
            product_id: Unique product identifier
            product_name: Product name
            current_metrics: Current metric values
            baseline_metrics: Historical baseline values
            current_rank: Current ranking position
            previous_rank: Previous ranking position

        Returns:
            Complete momentum data structure
        """
        # Calculate velocity for each metric
        velocities = {}
        for metric_name, current_value in current_metrics.items():
            baseline_value = baseline_metrics.get(metric_name, current_value)
            velocity = self.calculate_velocity(current_value, baseline_value)
            velocities[metric_name] = velocity

        # Overall velocity is average of all metrics
        overall_velocity = sum(velocities.values()) / len(velocities) if velocities else 0.0

        # Get momentum indicator
        indicator = self.get_momentum_indicator(overall_velocity)

        # Calculate rank change
        rank_change = 0
        if previous_rank is not None:
            rank_change = previous_rank - current_rank  # Positive = moved up

        # Determine trend direction
        trend_direction = "up" if overall_velocity > 5 else "down" if overall_velocity < -5 else "stable"

        # Detect breakout (explosive growth)
        breakout_detected = overall_velocity >= 50.0

        # Build metric breakdown
        metrics_breakdown = {}
        for metric_name, velocity in velocities.items():
            current_val = current_metrics.get(metric_name, 0)
            baseline_val = baseline_metrics.get(metric_name, 0)

            metrics_breakdown[metric_name] = {
                "current": current_val,
                "baseline": baseline_val,
                "change": f"{'+' if velocity >= 0 else ''}{velocity:.1f}%",
                "velocity": velocity
            }

        return {
            "product_id": product_id,
            "name": product_name,
            "current_rank": current_rank,
            "previous_rank": previous_rank or current_rank,
            "rank_change": rank_change,
            "velocity_score": round(overall_velocity, 2),
            "momentum_indicator": indicator["emoji"],
            "momentum_label": indicator["label"],
            "momentum_color": indicator["color"],
            "trend_direction": trend_direction,
            "percentage_change": f"{'+' if overall_velocity >= 0 else ''}{overall_velocity:.1f}%",
            "metrics": metrics_breakdown,
            "breakout_detected": breakout_detected,
            "last_updated": datetime.now(timezone.utc).isoformat() + "Z"
        }

    async def get_trending_products(
        self,
        products_data: List[Dict],
        limit: int = 20,
        sort_by: str = 'velocity'
    ) -> List[Dict]:
        """
        Get top trending products sorted by momentum.

        Args:
            products_data: List of product dictionaries with metrics
            limit: Maximum number of products to return
            sort_by: Sort criterion ('velocity', 'rank', 'breakout')

        Returns:
            Sorted list of trending products with momentum data
        """
        trending = []

        for idx, product in enumerate(products_data[:limit]):
            # Extract current metrics
            current_metrics = {
                "google_trends": product.get("trend_score", 0),
                "velocity_score": product.get("velocity_score", 0),
                "final_score": product.get("final_score", 0),
            }

            # T55: real baseline ONLY — never fabricate. This used
            # baseline = current * 0.7, which forces velocity to
            # ((c - 0.7c) / 0.7c) * 100 ≈ +42.9% for EVERY product, making the
            # entire "trending / stock-market" view pure fiction. Use a real
            # prior-period baseline when the caller supplies one (the discovery /
            # moat pipeline populates baseline_metrics from product_timeseries);
            # otherwise the product has no measured history yet, so baseline ==
            # current → velocity 0, explicitly flagged insufficient_history
            # rather than a fabricated surge. previous_rank is likewise left
            # unknown (None) instead of a fake "idx + 5" that implied everything
            # jumped up the ranks.
            real_baseline = product.get("baseline_metrics") or product.get("previous_metrics")
            has_history = bool(real_baseline)
            baseline_metrics = dict(real_baseline) if has_history else dict(current_metrics)

            momentum = self.calculate_product_momentum(
                product_id=product.get("id", f"prod_{idx}"),
                product_name=product.get("name", "Unknown Product"),
                current_metrics=current_metrics,
                baseline_metrics=baseline_metrics,
                current_rank=idx + 1,
                previous_rank=product.get("previous_rank")
            )
            momentum["insufficient_history"] = not has_history

            trending.append(momentum)

        # Sort based on criterion
        if sort_by == 'velocity':
            trending.sort(key=lambda x: x['velocity_score'], reverse=True)
        elif sort_by == 'rank_change':
            trending.sort(key=lambda x: x['rank_change'], reverse=True)

        # Update ranks after sorting
        for idx, item in enumerate(trending):
            item['current_rank'] = idx + 1

        return trending[:limit]

    def get_biggest_movers(
        self,
        products: List[Dict],
        limit: int = 10,
        direction: str = "up"
    ) -> List[Dict]:
        """
        Get products with biggest rank changes.

        Args:
            products: List of products with momentum data
            limit: Number of movers to return
            direction: "up" or "down"

        Returns:
            Sorted list of biggest movers
        """
        if direction == "up":
            movers = sorted(products, key=lambda x: x.get('rank_change', 0), reverse=True)
        else:
            movers = sorted(products, key=lambda x: x.get('rank_change', 0))

        return [m for m in movers if m.get('rank_change', 0) != 0][:limit]

    def get_breakout_products(self, products: List[Dict]) -> List[Dict]:
        """
        Get products with explosive momentum (>50% velocity).

        Args:
            products: List of products with momentum data

        Returns:
            List of breakout products
        """
        breakouts = [
            p for p in products
            if p.get('velocity_score', 0) >= 50.0
        ]

        return sorted(breakouts, key=lambda x: x['velocity_score'], reverse=True)

    def get_falling_products(
        self,
        products: List[Dict],
        limit: int = 10
    ) -> List[Dict]:
        """
        Get products losing momentum.

        Args:
            products: List of products with momentum data
            limit: Number to return

        Returns:
            List of falling products
        """
        falling = [
            p for p in products
            if p.get('velocity_score', 0) <= -5.0
        ]

        return sorted(falling, key=lambda x: x['velocity_score'])[:limit]

    def generate_heatmap_data(
        self,
        products: List[Dict],
        grid_size: Tuple[int, int] = (10, 5)
    ) -> Dict:
        """
        Generate heat map data for visualization.

        Args:
            products: List of products with momentum data
            grid_size: (rows, columns) for grid

        Returns:
            Grid data structure for heat map
        """
        rows, cols = grid_size
        total_cells = rows * cols

        grid = []
        for i in range(min(len(products), total_cells)):
            product = products[i]
            velocity = product.get('velocity_score', 0)

            # Determine color based on velocity
            if velocity >= 50:
                color = "#00FF41"  # Neon green
            elif velocity >= 30:
                color = "#00FF00"  # Bright green
            elif velocity >= 15:
                color = "#7FFF00"  # Light green
            elif velocity >= 5:
                color = "#ADFF2F"  # Yellow-green
            elif velocity >= -5:
                color = "#808080"  # Gray
            elif velocity >= -15:
                color = "#FF8C00"  # Orange
            else:
                color = "#FF0000"  # Red

            grid.append({
                "row": i // cols,
                "col": i % cols,
                "product_id": product.get('product_id'),
                "name": product.get('name', ''),
                "velocity": velocity,
                "color": color,
                "indicator": product.get('momentum_indicator', '→')
            })

        return {
            "grid": grid,
            "rows": rows,
            "cols": cols,
            "last_updated": datetime.now(timezone.utc).isoformat() + "Z"
        }


# Singleton instance
_momentum_tracker = None

def get_momentum_tracker() -> MomentumTracker:
    """Get or create momentum tracker instance."""
    global _momentum_tracker
    if _momentum_tracker is None:
        _momentum_tracker = MomentumTracker()
    return _momentum_tracker
