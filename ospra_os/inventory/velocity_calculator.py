"""
Velocity Calculator - Calculate sales velocity with trend analysis

Calculates product sales velocity using multiple methods:
1. Simple Average: Total units / days
2. Weighted Average: Recent days weighted more heavily
3. Exponential Smoothing: Adaptive to trends
4. Linear Regression: Trend line analysis

Returns best estimate with confidence score.
"""
import statistics
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple
import math


class VelocityCalculator:
    """Calculate sales velocity with multiple methods and confidence scoring"""

    def __init__(self):
        self.alpha = 0.3  # Exponential smoothing factor

    async def calculate_velocity(
        self,
        orders: List[Dict],
        period_days: int = 30
    ) -> Dict:
        """
        Calculate sales velocity using multiple methods

        Args:
            orders: List of orders with 'created_at' and 'quantity' fields
            period_days: Number of days to analyze

        Returns:
            {
                "daily_velocity": 3.2,
                "weekly_velocity": 22.4,
                "monthly_velocity": 96.0,
                "trend": {
                    "direction": "increasing",
                    "percentage": 12.5,
                    "slope": 0.15,
                    "confidence": 0.85
                },
                "standard_deviation": 1.5,
                "confidence": 0.85,
                "sample_size": 30,
                "method_used": "weighted_average"
            }
        """
        if not orders:
            return {
                "daily_velocity": 0.0,
                "weekly_velocity": 0.0,
                "monthly_velocity": 0.0,
                "trend": {"direction": "stable", "percentage": 0, "slope": 0, "confidence": 0},
                "standard_deviation": 0.0,
                "confidence": 0.0,
                "sample_size": 0,
                "method_used": "none"
            }

        # Prepare daily sales data
        daily_sales = await self._aggregate_daily_sales(orders, period_days)

        # Calculate using multiple methods
        simple_velocity = await self.calculate_simple_velocity(daily_sales)
        weighted_velocity = await self.calculate_weighted_velocity(daily_sales)

        # Choose best method based on data characteristics
        if len(daily_sales) >= 14:
            # Use weighted average for sufficient data
            daily_velocity = weighted_velocity
            method_used = "weighted_average"
        else:
            # Use simple average for small samples
            daily_velocity = simple_velocity
            method_used = "simple_average"

        # Calculate trend
        trend = await self.calculate_trend(daily_sales)

        # Calculate standard deviation
        std_dev = await self.calculate_standard_deviation(daily_sales)

        # Calculate confidence
        confidence = await self.get_velocity_confidence(len(daily_sales), std_dev, daily_velocity)

        return {
            "daily_velocity": round(daily_velocity, 2),
            "weekly_velocity": round(daily_velocity * 7, 2),
            "monthly_velocity": round(daily_velocity * 30, 2),
            "trend": trend,
            "standard_deviation": round(std_dev, 2),
            "confidence": round(confidence, 2),
            "sample_size": len(daily_sales),
            "method_used": method_used
        }

    async def _aggregate_daily_sales(
        self,
        orders: List[Dict],
        period_days: int
    ) -> List[Tuple[date, int]]:
        """
        Aggregate orders into daily sales

        Returns list of (date, units_sold) tuples
        """
        # Get date range
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)

        # Initialize daily sales dict
        daily_sales_dict = {}
        current_date = start_date
        while current_date <= end_date:
            daily_sales_dict[current_date] = 0
            current_date += timedelta(days=1)

        # Aggregate orders by day
        for order in orders:
            order_date = order.get('created_at')
            if isinstance(order_date, str):
                order_date = datetime.fromisoformat(order_date.replace('Z', '+00:00')).date()
            elif isinstance(order_date, datetime):
                order_date = order_date.date()

            if start_date <= order_date <= end_date:
                quantity = order.get('quantity', 1)
                daily_sales_dict[order_date] = daily_sales_dict.get(order_date, 0) + quantity

        # Convert to sorted list of tuples
        daily_sales = sorted(daily_sales_dict.items())
        return daily_sales

    async def calculate_simple_velocity(self, daily_sales: List[Tuple[date, int]]) -> float:
        """
        Calculate simple average velocity

        Formula: Total units / Number of days
        """
        if not daily_sales:
            return 0.0

        total_units = sum(units for _, units in daily_sales)
        num_days = len(daily_sales)

        return total_units / num_days if num_days > 0 else 0.0

    async def calculate_weighted_velocity(self, daily_sales: List[Tuple[date, int]]) -> float:
        """
        Calculate weighted average velocity (recent days weighted 2x)

        More recent sales are weighted more heavily to capture current trends
        """
        if not daily_sales:
            return 0.0

        num_days = len(daily_sales)
        if num_days == 0:
            return 0.0

        # Split into recent (last 1/3) and older (first 2/3)
        split_point = max(1, num_days * 2 // 3)
        older_sales = daily_sales[:split_point]
        recent_sales = daily_sales[split_point:]

        # Weight: older = 1x, recent = 2x
        older_units = sum(units for _, units in older_sales)
        recent_units = sum(units for _, units in recent_sales)

        weighted_total = (older_units * 1.0) + (recent_units * 2.0)
        weighted_days = (len(older_sales) * 1.0) + (len(recent_sales) * 2.0)

        return weighted_total / weighted_days if weighted_days > 0 else 0.0

    async def calculate_exponential_smoothing(
        self,
        daily_sales: List[Tuple[date, int]]
    ) -> float:
        """
        Calculate exponentially smoothed velocity

        Formula: S_t = α * Y_t + (1 - α) * S_{t-1}
        where α = smoothing factor (0.3)
        """
        if not daily_sales:
            return 0.0

        # Start with first day's value
        smoothed = float(daily_sales[0][1])

        # Apply exponential smoothing
        for _, units in daily_sales[1:]:
            smoothed = self.alpha * units + (1 - self.alpha) * smoothed

        return smoothed

    async def calculate_trend(self, daily_sales: List[Tuple[date, int]]) -> Dict:
        """
        Determine if velocity is accelerating, stable, or decelerating

        Uses linear regression to find trend line

        Returns:
            {
                "direction": "increasing",  # or "stable", "decreasing"
                "percentage": 12.5,
                "slope": 0.15,
                "confidence": 0.85
            }
        """
        if len(daily_sales) < 7:
            return {
                "direction": "stable",
                "percentage": 0.0,
                "slope": 0.0,
                "confidence": 0.0
            }

        # Prepare data for linear regression
        n = len(daily_sales)
        x_values = list(range(n))  # Day numbers: 0, 1, 2, ...
        y_values = [units for _, units in daily_sales]

        # Calculate linear regression
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(y_values)

        # Calculate slope (m) and intercept (b)
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)

        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator

        intercept = y_mean - slope * x_mean

        # Determine trend direction
        if abs(slope) < 0.05:  # Small slope = stable
            direction = "stable"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"

        # Calculate percentage change from start to end of period
        if y_mean > 0:
            start_value = intercept
            end_value = slope * (n - 1) + intercept
            percentage_change = ((end_value - start_value) / start_value) * 100 if start_value > 0 else 0
        else:
            percentage_change = 0.0

        # Calculate R-squared for confidence
        y_pred = [slope * x + intercept for x in x_values]
        ss_res = sum((y - y_p) ** 2 for y, y_p in zip(y_values, y_pred))
        ss_tot = sum((y - y_mean) ** 2 for y in y_values)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "direction": direction,
            "percentage": round(percentage_change, 1),
            "slope": round(slope, 3),
            "confidence": round(max(0, r_squared), 2)
        }

    async def calculate_standard_deviation(self, daily_sales: List[Tuple[date, int]]) -> float:
        """
        Calculate standard deviation of daily sales

        Measures variability/consistency in sales
        """
        if len(daily_sales) < 2:
            return 0.0

        values = [units for _, units in daily_sales]
        return statistics.stdev(values)

    async def get_velocity_confidence(
        self,
        sample_size: int,
        std_dev: float,
        velocity: float
    ) -> float:
        """
        Calculate confidence in velocity estimate (0-1)

        Based on:
        - Sample size (more days = higher confidence)
        - Standard deviation (lower variance = higher confidence)
        - Coefficient of variation
        """
        # Sample size confidence (0-1)
        # Full confidence at 30+ days
        size_confidence = min(1.0, sample_size / 30)

        # Variability confidence (0-1)
        # Lower coefficient of variation = higher confidence
        if velocity > 0:
            cv = std_dev / velocity  # Coefficient of variation
            var_confidence = max(0, 1 - (cv / 2))  # Penalize high CV
        else:
            var_confidence = 0.5

        # Combined confidence (weighted average)
        confidence = (size_confidence * 0.6) + (var_confidence * 0.4)

        return max(0.0, min(1.0, confidence))

    async def get_day_of_week_pattern(
        self,
        orders: List[Dict]
    ) -> Dict[str, float]:
        """
        Analyze which days of the week sell more

        Returns multipliers for each day (1.0 = average)
        Example: {"Monday": 1.2, "Tuesday": 0.9, ...}
        """
        if not orders:
            return {
                "Monday": 1.0,
                "Tuesday": 1.0,
                "Wednesday": 1.0,
                "Thursday": 1.0,
                "Friday": 1.0,
                "Saturday": 1.0,
                "Sunday": 1.0
            }

        # Initialize day counts
        day_sales = {
            0: 0,  # Monday
            1: 0,  # Tuesday
            2: 0,  # Wednesday
            3: 0,  # Thursday
            4: 0,  # Friday
            5: 0,  # Saturday
            6: 0   # Sunday
        }

        # Aggregate by day of week
        for order in orders:
            order_date = order.get('created_at')
            if isinstance(order_date, str):
                order_date = datetime.fromisoformat(order_date.replace('Z', '+00:00'))

            day_of_week = order_date.weekday()  # 0 = Monday, 6 = Sunday
            quantity = order.get('quantity', 1)
            day_sales[day_of_week] += quantity

        # Calculate average
        total_sales = sum(day_sales.values())
        avg_per_day = total_sales / 7 if total_sales > 0 else 1

        # Calculate multipliers
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        patterns = {}
        for i, name in enumerate(day_names):
            if avg_per_day > 0:
                patterns[name] = round(day_sales[i] / avg_per_day, 2)
            else:
                patterns[name] = 1.0

        return patterns
