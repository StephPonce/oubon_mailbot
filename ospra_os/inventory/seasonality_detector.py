"""
Seasonality Detector - Detect and account for seasonal demand patterns

Identifies seasonal patterns in product sales and provides adjustment factors
for more accurate inventory forecasting.
"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import statistics


class SeasonalityDetector:
    """Detect seasonal patterns and provide adjustment factors"""

    # Known seasonal events with typical demand multipliers
    SEASONAL_EVENTS = {
        "black_friday": {
            "month": 11,
            "day_range": (20, 30),
            "multiplier": 2.5,
            "description": "Black Friday sales surge"
        },
        "cyber_monday": {
            "month": 12,
            "day_range": (1, 3),
            "multiplier": 2.0,
            "description": "Cyber Monday online shopping"
        },
        "christmas": {
            "month": 12,
            "day_range": (10, 25),
            "multiplier": 1.8,
            "description": "Christmas shopping season"
        },
        "new_year": {
            "month": 1,
            "day_range": (1, 7),
            "multiplier": 1.3,
            "description": "New Year resolutions and sales"
        },
        "valentines": {
            "month": 2,
            "day_range": (7, 14),
            "multiplier": 1.4,
            "description": "Valentine's Day gifts"
        },
        "mothers_day": {
            "month": 5,
            "day_range": (1, 15),
            "multiplier": 1.5,
            "description": "Mother's Day gifts"
        },
        "fathers_day": {
            "month": 6,
            "day_range": (10, 20),
            "multiplier": 1.3,
            "description": "Father's Day gifts"
        },
        "back_to_school": {
            "month": 8,
            "day_range": (15, 31),
            "multiplier": 1.6,
            "description": "Back to school shopping"
        },
        "halloween": {
            "month": 10,
            "day_range": (15, 31),
            "multiplier": 1.4,
            "description": "Halloween season"
        },
        "summer_slow": {
            "month": 7,
            "day_range": (1, 31),
            "multiplier": 0.8,
            "description": "Summer vacation slowdown"
        }
    }

    def __init__(self):
        pass

    async def detect_seasonality(
        self,
        product_id: str,
        sales_history: List[Dict]
    ) -> Dict:
        """
        Analyze historical sales data for seasonal patterns

        Args:
            product_id: Product identifier
            sales_history: List of sales records with 'created_at' and 'quantity'

        Returns:
            {
                "is_seasonal": true,
                "pattern_type": "holiday_surge",
                "peak_months": [11, 12],
                "low_months": [6, 7],
                "monthly_indices": {
                    "1": 0.9,
                    "2": 0.95,
                    ...
                    "11": 1.35,
                    "12": 1.5
                },
                "confidence": 0.78,
                "notes": "Strong holiday seasonality detected"
            }
        """
        if not sales_history or len(sales_history) < 90:
            return {
                "is_seasonal": False,
                "pattern_type": "insufficient_data",
                "peak_months": [],
                "low_months": [],
                "monthly_indices": {},
                "confidence": 0.0,
                "notes": "Insufficient data for seasonality analysis (need 90+ days)"
            }

        # Calculate monthly indices
        monthly_indices = await self._calculate_monthly_indices(sales_history)

        # Determine if product is seasonal
        is_seasonal, confidence = await self._is_seasonal(monthly_indices)

        if not is_seasonal:
            return {
                "is_seasonal": False,
                "pattern_type": "not_seasonal",
                "peak_months": [],
                "low_months": [],
                "monthly_indices": monthly_indices,
                "confidence": confidence,
                "notes": "No significant seasonal pattern detected"
            }

        # Identify peak and low months
        peak_months = await self._identify_peak_months(monthly_indices)
        low_months = await self._identify_low_months(monthly_indices)

        # Determine pattern type
        pattern_type = await self._determine_pattern_type(peak_months, low_months)

        return {
            "is_seasonal": True,
            "pattern_type": pattern_type,
            "peak_months": peak_months,
            "low_months": low_months,
            "monthly_indices": monthly_indices,
            "confidence": round(confidence, 2),
            "notes": f"{pattern_type.replace('_', ' ').title()} pattern detected"
        }

    async def _calculate_monthly_indices(
        self,
        sales_history: List[Dict]
    ) -> Dict[str, float]:
        """
        Calculate demand index for each month (1.0 = average)

        Returns: {"1": 0.9, "2": 0.95, ..., "12": 1.5}
        """
        # Initialize monthly sales
        monthly_sales = {str(m): [] for m in range(1, 13)}

        # Aggregate sales by month
        for sale in sales_history:
            sale_date = sale.get('created_at')
            if isinstance(sale_date, str):
                sale_date = datetime.fromisoformat(sale_date.replace('Z', '+00:00'))

            month = str(sale_date.month)
            quantity = sale.get('quantity', 1)
            monthly_sales[month].append(quantity)

        # Calculate average for each month
        monthly_averages = {}
        for month, sales in monthly_sales.items():
            if sales:
                monthly_averages[month] = sum(sales) / len(sales)
            else:
                monthly_averages[month] = 0

        # Calculate overall average
        all_sales = [avg for avg in monthly_averages.values() if avg > 0]
        overall_avg = sum(all_sales) / len(all_sales) if all_sales else 1

        # Calculate indices (month average / overall average)
        monthly_indices = {}
        for month, avg in monthly_averages.items():
            if overall_avg > 0:
                monthly_indices[month] = round(avg / overall_avg, 2)
            else:
                monthly_indices[month] = 1.0

        return monthly_indices

    async def _is_seasonal(self, monthly_indices: Dict[str, float]) -> tuple[bool, float]:
        """
        Determine if the data shows significant seasonality

        Uses coefficient of variation to detect seasonality

        Returns: (is_seasonal, confidence)
        """
        values = list(monthly_indices.values())

        if not values or all(v == 0 for v in values):
            return False, 0.0

        # Calculate coefficient of variation
        mean = statistics.mean(values)
        if mean == 0:
            return False, 0.0

        std_dev = statistics.stdev(values) if len(values) > 1 else 0
        cv = std_dev / mean

        # Threshold: CV > 0.15 indicates seasonality
        # Higher CV = stronger seasonality
        is_seasonal = cv > 0.15
        confidence = min(1.0, cv / 0.5)  # Max confidence at CV = 0.5

        return is_seasonal, confidence

    async def _identify_peak_months(self, monthly_indices: Dict[str, float]) -> List[int]:
        """Identify months with above-average demand (index > 1.2)"""
        peak_months = [
            int(month)
            for month, index in monthly_indices.items()
            if index >= 1.2
        ]
        return sorted(peak_months)

    async def _identify_low_months(self, monthly_indices: Dict[str, float]) -> List[int]:
        """Identify months with below-average demand (index < 0.8)"""
        low_months = [
            int(month)
            for month, index in monthly_indices.items()
            if index <= 0.8
        ]
        return sorted(low_months)

    async def _determine_pattern_type(
        self,
        peak_months: List[int],
        low_months: List[int]
    ) -> str:
        """
        Determine the type of seasonal pattern

        Returns: holiday_surge, summer_slow, back_to_school, etc.
        """
        # Check for holiday surge (Nov-Dec peak)
        if any(m in peak_months for m in [11, 12]):
            return "holiday_surge"

        # Check for back-to-school (Aug-Sep peak)
        if any(m in peak_months for m in [8, 9]):
            return "back_to_school"

        # Check for summer slow (Jun-Jul low)
        if any(m in low_months for m in [6, 7]):
            return "summer_slow"

        # Check for Valentine's/Mother's Day (Feb/May peak)
        if any(m in peak_months for m in [2, 5]):
            return "gift_season"

        # Generic pattern
        return "seasonal"

    async def get_adjustment_factor(
        self,
        target_date: date,
        monthly_indices: Dict[str, float]
    ) -> float:
        """
        Get seasonal adjustment multiplier for a specific date

        Args:
            target_date: Date to get adjustment for
            monthly_indices: Monthly seasonality indices

        Returns:
            Multiplier (e.g., 1.35 for 35% increase)
        """
        month = str(target_date.month)
        return monthly_indices.get(month, 1.0)

    async def get_upcoming_events(self, days: int = 60) -> List[Dict]:
        """
        List upcoming seasonal events within the next X days

        Returns:
            [
                {
                    "event": "black_friday",
                    "date": "2025-11-28",
                    "days_away": 15,
                    "multiplier": 2.5,
                    "description": "Black Friday sales surge"
                },
                ...
            ]
        """
        today = date.today()
        end_date = today + timedelta(days=days)

        upcoming = []

        for event_name, event_data in self.SEASONAL_EVENTS.items():
            # Handle single month events
            if "month" in event_data:
                month = event_data["month"]
                day_start, day_end = event_data["day_range"]

                # Check current year
                for day in range(day_start, day_end + 1):
                    try:
                        event_date = date(today.year, month, day)
                        if today <= event_date <= end_date:
                            upcoming.append({
                                "event": event_name,
                                "date": event_date.isoformat(),
                                "days_away": (event_date - today).days,
                                "multiplier": event_data["multiplier"],
                                "description": event_data["description"]
                            })
                            break  # Only add once per event
                    except ValueError:
                        continue

                # Check next year if event is in next 60 days
                for day in range(day_start, day_end + 1):
                    try:
                        event_date = date(today.year + 1, month, day)
                        if today <= event_date <= end_date:
                            upcoming.append({
                                "event": event_name,
                                "date": event_date.isoformat(),
                                "days_away": (event_date - today).days,
                                "multiplier": event_data["multiplier"],
                                "description": event_data["description"]
                            })
                            break
                    except ValueError:
                        continue

        # Sort by date
        upcoming.sort(key=lambda x: x["days_away"])

        return upcoming

    async def apply_seasonal_adjustment(
        self,
        base_forecast: float,
        target_date: date,
        monthly_indices: Dict[str, float]
    ) -> float:
        """
        Apply seasonal adjustment to a forecast value

        Args:
            base_forecast: Base forecast value (e.g., daily velocity)
            target_date: Date being forecasted
            monthly_indices: Seasonal indices for each month

        Returns:
            Adjusted forecast value
        """
        adjustment_factor = await self.get_adjustment_factor(target_date, monthly_indices)
        return base_forecast * adjustment_factor
