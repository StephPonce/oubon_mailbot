"""
LTV Calculator - Customer Lifetime Value Prediction

Calculates historical and predicted LTV using multiple methods:
1. Historical LTV: Sum of all revenue from customer
2. Average LTV: AOV × Frequency × Lifespan
3. Predictive LTV: ML-based future value prediction
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import logging
import statistics

logger = logging.getLogger(__name__)


class LTVCalculator:
    """Calculate and predict customer lifetime value"""

    def __init__(self, db_session=None):
        """
        Initialize LTV Calculator

        Args:
            db_session: Database session for queries
        """
        self.db = db_session

    # ==================== Historical LTV ====================

    def calculate_historical_ltv(self, customer_id: str, orders: List[Dict]) -> float:
        """
        Calculate historical LTV (simple sum of all orders)

        Args:
            customer_id: Customer ID
            orders: List of order dictionaries with 'total' field

        Returns:
            Total revenue from customer
        """
        if not orders:
            return 0.0

        total = sum(order.get('total', 0) for order in orders)
        logger.info(f"[PRICE] Historical LTV for {customer_id}: ${total:.2f}")

        return round(total, 2)

    # ==================== Average LTV ====================

    def calculate_average_ltv(
        self,
        average_order_value: float,
        purchase_frequency: float,
        customer_lifespan_months: float = 24
    ) -> float:
        """
        Calculate average LTV using traditional formula

        LTV = AOV × Purchase Frequency × Customer Lifespan

        Args:
            average_order_value: Average value per order
            purchase_frequency: Orders per month
            customer_lifespan_months: Expected customer lifetime in months

        Returns:
            Calculated LTV
        """
        ltv = average_order_value * purchase_frequency * customer_lifespan_months
        logger.info(f"[STATS] Average LTV: ${ltv:.2f} (AOV: ${average_order_value}, Freq: {purchase_frequency}/mo, Lifespan: {customer_lifespan_months}mo)")

        return round(ltv, 2)

    # ==================== Predictive LTV ====================

    async def calculate_predictive_ltv(self, customer_id: str, customer_data: Dict) -> Dict:
        """
        Predict future LTV using historical patterns and trends

        Factors considered:
        - Historical purchase pattern
        - Purchase frequency trend (stable, increasing, decreasing)
        - AOV trend
        - Churn probability
        - Segment average
        - Time since acquisition

        Args:
            customer_id: Customer ID
            customer_data: Customer profile data

        Returns:
            Predictive LTV breakdown
        """
        logger.info(f" Predicting LTV for: {customer_id}")

        # Extract customer metrics
        historical_ltv = customer_data.get('ltv', 0)
        total_orders = customer_data.get('total_orders', 0)
        avg_order_value = customer_data.get('average_order_value', 0)
        days_since_acquisition = self._calculate_days_since_acquisition(
            customer_data.get('acquisition_date')
        )
        purchase_frequency_days = customer_data.get('purchase_frequency_days', 30)
        segment = customer_data.get('segment', 'NEW_CUSTOMER')
        churn_probability = customer_data.get('churn_probability', 0.2)

        # Calculate trends
        purchase_trend = self._analyze_purchase_trend(customer_data.get('orders', []))
        aov_trend = self._analyze_aov_trend(customer_data.get('orders', []))

        # Calculate purchase frequency per month
        if days_since_acquisition > 0 and total_orders > 0:
            orders_per_month = (total_orders / days_since_acquisition) * 30
        else:
            orders_per_month = 1

        # Predict 12-month LTV
        # Base prediction: orders per month × avg order value × 12 months
        base_12m_ltv = orders_per_month * avg_order_value * 12

        # Adjust for churn probability
        retention_factor = 1 - churn_probability
        adjusted_12m_ltv = base_12m_ltv * retention_factor

        # Adjust for trends
        if purchase_trend == 'increasing':
            adjusted_12m_ltv *= 1.15  # 15% boost
        elif purchase_trend == 'decreasing':
            adjusted_12m_ltv *= 0.85  # 15% penalty

        if aov_trend == 'increasing':
            adjusted_12m_ltv *= 1.10  # 10% boost
        elif aov_trend == 'decreasing':
            adjusted_12m_ltv *= 0.90  # 10% penalty

        # Predict total LTV (historical + predicted future)
        # Assume average customer lifespan of 24 months
        months_remaining = max(0, 24 - (days_since_acquisition / 30))
        future_ltv = (adjusted_12m_ltv / 12) * months_remaining
        predicted_total_ltv = historical_ltv + future_ltv

        # Calculate confidence score (0-1)
        confidence = self._calculate_prediction_confidence(
            total_orders,
            days_since_acquisition,
            purchase_trend,
            aov_trend
        )

        result = {
            "historical_ltv": round(historical_ltv, 2),
            "predicted_12m_ltv": round(adjusted_12m_ltv, 2),
            "predicted_total_ltv": round(predicted_total_ltv, 2),
            "confidence": round(confidence, 2),
            "factors": {
                "purchase_frequency_trend": purchase_trend,
                "aov_trend": aov_trend,
                "churn_risk": "low" if churn_probability < 0.3 else "medium" if churn_probability < 0.6 else "high",
                "segment": segment
            },
            "calculated_at": datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"[SUCCESS] Predicted LTV: ${predicted_total_ltv:.2f} (confidence: {confidence:.0%})")

        return result

    # ==================== Segment Analysis ====================

    def calculate_ltv_by_segment(self, customers: List[Dict]) -> Dict:
        """
        Calculate average LTV per customer segment

        Args:
            customers: List of customer dictionaries

        Returns:
            Segment breakdown with average LTV
        """
        logger.info("[STATS] Calculating LTV by segment...")

        segment_data = {}

        for customer in customers:
            segment = customer.get('segment', 'UNKNOWN')
            ltv = customer.get('ltv', 0)

            if segment not in segment_data:
                segment_data[segment] = []

            segment_data[segment].append(ltv)

        # Calculate averages
        result = {}
        for segment, ltvs in segment_data.items():
            if ltvs:
                result[segment] = {
                    "count": len(ltvs),
                    "avg_ltv": round(statistics.mean(ltvs), 2),
                    "median_ltv": round(statistics.median(ltvs), 2),
                    "min_ltv": round(min(ltvs), 2),
                    "max_ltv": round(max(ltvs), 2)
                }

        return result

    def calculate_ltv_by_acquisition_source(self, customers: List[Dict]) -> Dict:
        """
        Calculate average LTV by how customer was acquired

        Args:
            customers: List of customer dictionaries

        Returns:
            Source breakdown with average LTV
        """
        logger.info("[STATS] Calculating LTV by acquisition source...")

        source_data = {}

        for customer in customers:
            source = customer.get('acquisition_source', 'unknown')
            ltv = customer.get('ltv', 0)

            if source not in source_data:
                source_data[source] = []

            source_data[source].append(ltv)

        # Calculate averages
        result = {}
        for source, ltvs in source_data.items():
            if ltvs:
                result[source] = {
                    "count": len(ltvs),
                    "avg_ltv": round(statistics.mean(ltvs), 2),
                    "median_ltv": round(statistics.median(ltvs), 2),
                    "total_ltv": round(sum(ltvs), 2)
                }

        return result

    def calculate_ltv_percentile(self, customer_ltv: float, all_ltvs: List[float]) -> int:
        """
        Calculate what percentile this customer's LTV falls into

        Args:
            customer_ltv: This customer's LTV
            all_ltvs: List of all customer LTVs

        Returns:
            Percentile (0-100)
        """
        if not all_ltvs:
            return 50

        sorted_ltvs = sorted(all_ltvs)
        position = sum(1 for ltv in sorted_ltvs if ltv <= customer_ltv)
        percentile = int((position / len(sorted_ltvs)) * 100)

        return percentile

    # ==================== Helper Methods ====================

    def _calculate_days_since_acquisition(self, acquisition_date) -> int:
        """Calculate days since customer was acquired"""
        if not acquisition_date:
            return 0

        if isinstance(acquisition_date, str):
            acquisition_date = datetime.fromisoformat(acquisition_date.replace('Z', '+00:00')).date()

        today = datetime.now(timezone.utc).date()
        delta = today - acquisition_date

        return delta.days

    def _analyze_purchase_trend(self, orders: List[Dict]) -> str:
        """
        Analyze if purchase frequency is increasing, decreasing, or stable

        Args:
            orders: List of orders (sorted by date)

        Returns:
            'increasing', 'decreasing', or 'stable'
        """
        if len(orders) < 3:
            return 'stable'

        # Compare first half vs second half
        mid = len(orders) // 2
        first_half = orders[:mid]
        second_half = orders[mid:]

        # Calculate average days between orders
        def avg_days_between(order_list):
            if len(order_list) < 2:
                return 30  # Default

            dates = [datetime.fromisoformat(o['date'].replace('Z', '+00:00')) for o in order_list]
            dates.sort()
            gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            return statistics.mean(gaps) if gaps else 30

        first_gap = avg_days_between(first_half)
        second_gap = avg_days_between(second_half)

        # Shorter gap = higher frequency = increasing
        if second_gap < first_gap * 0.8:
            return 'increasing'
        elif second_gap > first_gap * 1.2:
            return 'decreasing'
        else:
            return 'stable'

    def _analyze_aov_trend(self, orders: List[Dict]) -> str:
        """
        Analyze if average order value is increasing, decreasing, or stable

        Args:
            orders: List of orders

        Returns:
            'increasing', 'decreasing', or 'stable'
        """
        if len(orders) < 3:
            return 'stable'

        # Compare first half vs second half
        mid = len(orders) // 2
        first_half_avg = statistics.mean([o.get('total', 0) for o in orders[:mid]])
        second_half_avg = statistics.mean([o.get('total', 0) for o in orders[mid:]])

        if second_half_avg > first_half_avg * 1.15:
            return 'increasing'
        elif second_half_avg < first_half_avg * 0.85:
            return 'decreasing'
        else:
            return 'stable'

    def _calculate_prediction_confidence(
        self,
        total_orders: int,
        days_since_acquisition: int,
        purchase_trend: str,
        aov_trend: str
    ) -> float:
        """
        Calculate confidence in LTV prediction (0.0 to 1.0)

        More orders and longer history = higher confidence
        Stable trends = higher confidence

        Args:
            total_orders: Number of orders
            days_since_acquisition: Days since first order
            purchase_trend: Purchase frequency trend
            aov_trend: AOV trend

        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.5  # Base confidence

        # More orders = more confidence
        if total_orders >= 10:
            confidence += 0.25
        elif total_orders >= 5:
            confidence += 0.15
        elif total_orders >= 3:
            confidence += 0.05

        # Longer history = more confidence
        if days_since_acquisition >= 180:  # 6 months
            confidence += 0.15
        elif days_since_acquisition >= 90:  # 3 months
            confidence += 0.10
        elif days_since_acquisition >= 30:  # 1 month
            confidence += 0.05

        # Stable trends = more confidence
        if purchase_trend == 'stable' and aov_trend == 'stable':
            confidence += 0.10

        return min(confidence, 1.0)  # Cap at 1.0


# Export singleton instance
_ltv_calculator = None

def get_ltv_calculator(db_session=None):
    """Get or create LTV calculator instance"""
    global _ltv_calculator
    if _ltv_calculator is None:
        _ltv_calculator = LTVCalculator(db_session)
    return _ltv_calculator


logger.info("[SUCCESS] LTV Calculator module loaded")
