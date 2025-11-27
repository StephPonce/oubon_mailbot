"""
Churn Predictor - Identify customers at risk of churning

Predicts which customers are likely to stop buying based on:
- Recency: Days since last purchase
- Frequency: Order rate decline
- Engagement: Email opens, site visits
- Trends: Declining behavior patterns
"""
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
import logging
import statistics

logger = logging.getLogger(__name__)


class ChurnPredictor:
    """Predict customer churn probability and identify at-risk customers"""

    def __init__(self, db_session=None):
        """
        Initialize Churn Predictor

        Args:
            db_session: Database session for queries
        """
        self.db = db_session

    # ==================== Churn Probability ====================

    async def calculate_churn_probability(self, customer_id: str, customer_data: Dict) -> float:
        """
        Calculate probability of customer churning (0.0 to 1.0)

        Weighted scoring:
        - Recency factor (40%): Days since last order vs average
        - Frequency factor (30%): Recent orders vs historical average
        - Engagement factor (20%): Email opens, site activity
        - Trend factor (10%): Is behavior trending down?

        Args:
            customer_id: Unique customer ID
            customer_data: Customer profile data

        Returns:
            Churn probability (0.0 = will stay, 1.0 = will churn)
        """
        logger.info(f"🔮 Calculating churn probability for: {customer_id}")

        # Extract metrics
        days_since_last_order = customer_data.get('days_since_last_order', 0)
        purchase_frequency_days = customer_data.get('purchase_frequency_days', 30)
        total_orders = customer_data.get('total_orders', 0)
        segment = customer_data.get('segment', 'NEW_CUSTOMER')
        orders = customer_data.get('orders', [])

        # Calculate individual risk factors
        recency_score = self._calculate_recency_risk(
            days_since_last_order,
            purchase_frequency_days
        )

        frequency_score = self._calculate_frequency_risk(
            orders,
            total_orders
        )

        engagement_score = self._calculate_engagement_risk(
            customer_data.get('email_engagement', {})
        )

        trend_score = self._calculate_trend_risk(orders)

        # Weighted average
        churn_probability = (
            recency_score * 0.40 +
            frequency_score * 0.30 +
            engagement_score * 0.20 +
            trend_score * 0.10
        )

        # Adjust based on segment
        segment_adjustments = {
            'CHAMPION': -0.15,
            'LOYAL': -0.10,
            'POTENTIAL_LOYALIST': 0.0,
            'NEW_CUSTOMER': +0.05,
            'AT_RISK': +0.20,
            'HIBERNATING': +0.25,
            'LOST': +0.40
        }

        churn_probability += segment_adjustments.get(segment, 0.0)

        # Clamp to 0.0-1.0
        churn_probability = max(0.0, min(1.0, churn_probability))

        logger.info(f"📊 Churn probability: {churn_probability:.0%} (recency: {recency_score:.2f}, freq: {frequency_score:.2f}, engagement: {engagement_score:.2f}, trend: {trend_score:.2f})")

        return round(churn_probability, 2)

    def _calculate_recency_risk(self, days_since_last_order: int, avg_purchase_frequency: float) -> float:
        """
        Calculate risk based on recency

        Args:
            days_since_last_order: Days since last purchase
            avg_purchase_frequency: Average days between purchases

        Returns:
            Risk score (0.0 to 1.0)
        """
        if avg_purchase_frequency == 0:
            avg_purchase_frequency = 30  # Default

        # Ratio of actual vs expected
        ratio = days_since_last_order / avg_purchase_frequency

        if ratio < 0.5:
            return 0.0  # Very recent purchase
        elif ratio < 1.0:
            return 0.2  # Within expected timeframe
        elif ratio < 1.5:
            return 0.4  # Slightly overdue
        elif ratio < 2.0:
            return 0.6  # Overdue
        elif ratio < 3.0:
            return 0.8  # Very overdue
        else:
            return 1.0  # Extremely overdue

    def _calculate_frequency_risk(self, orders: List[Dict], total_orders: int) -> float:
        """
        Calculate risk based on order frequency decline

        Args:
            orders: List of recent orders
            total_orders: Total order count

        Returns:
            Risk score (0.0 to 1.0)
        """
        if total_orders < 3:
            return 0.3  # Not enough data, assume medium risk

        # Compare recent frequency vs overall frequency
        recent_orders = orders[-5:] if len(orders) >= 5 else orders  # Last 5 orders

        if len(recent_orders) < 2:
            return 0.5  # Not enough recent data

        # Calculate days between recent orders
        recent_dates = [datetime.fromisoformat(o['date'].replace('Z', '+00:00')) for o in recent_orders]
        recent_dates.sort()
        recent_gaps = [(recent_dates[i+1] - recent_dates[i]).days for i in range(len(recent_dates)-1)]
        avg_recent_gap = statistics.mean(recent_gaps) if recent_gaps else 30

        # Calculate days between all orders
        all_dates = [datetime.fromisoformat(o['date'].replace('Z', '+00:00')) for o in orders]
        all_dates.sort()
        if len(all_dates) >= 2:
            total_span = (all_dates[-1] - all_dates[0]).days
            avg_overall_gap = total_span / (len(all_dates) - 1) if len(all_dates) > 1 else 30
        else:
            avg_overall_gap = 30

        # Compare recent vs overall
        if avg_recent_gap > avg_overall_gap * 2:
            return 0.9  # Frequency dropped significantly
        elif avg_recent_gap > avg_overall_gap * 1.5:
            return 0.7  # Frequency declining
        elif avg_recent_gap > avg_overall_gap * 1.2:
            return 0.5  # Slight decline
        else:
            return 0.2  # Frequency stable or increasing

    def _calculate_engagement_risk(self, email_engagement: Dict) -> float:
        """
        Calculate risk based on email engagement

        Args:
            email_engagement: Email metrics (opens, clicks)

        Returns:
            Risk score (0.0 to 1.0)
        """
        # TODO: Integrate with email analytics when available
        # For now, return neutral score
        return 0.5

    def _calculate_trend_risk(self, orders: List[Dict]) -> float:
        """
        Calculate risk based on overall behavior trends

        Args:
            orders: List of orders

        Returns:
            Risk score (0.0 to 1.0)
        """
        if len(orders) < 4:
            return 0.5  # Not enough data

        # Analyze order value trend
        order_values = [o.get('total', 0) for o in orders]

        # Compare first half vs second half
        mid = len(order_values) // 2
        first_half_avg = statistics.mean(order_values[:mid])
        second_half_avg = statistics.mean(order_values[mid:])

        if second_half_avg < first_half_avg * 0.7:
            return 0.8  # Order values declining significantly
        elif second_half_avg < first_half_avg * 0.85:
            return 0.6  # Order values declining
        elif second_half_avg > first_half_avg * 1.15:
            return 0.2  # Order values increasing
        else:
            return 0.4  # Order values stable

    # ==================== Churn Factors Analysis ====================

    async def get_churn_factors(self, customer_id: str, customer_data: Dict) -> Dict:
        """
        Explain why customer is at risk of churning

        Args:
            customer_id: Customer ID
            customer_data: Customer profile data

        Returns:
            Detailed churn analysis with factors and recommendations
        """
        logger.info(f"📋 Analyzing churn factors for: {customer_id}")

        churn_probability = await self.calculate_churn_probability(customer_id, customer_data)

        # Determine risk level
        if churn_probability < 0.3:
            risk_level = "LOW"
        elif churn_probability < 0.6:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        # Identify specific factors
        factors = []

        # Recency factor
        days_since = customer_data.get('days_since_last_order', 0)
        avg_freq = customer_data.get('purchase_frequency_days', 30)

        if days_since > avg_freq * 2:
            factors.append({
                "factor": "recency",
                "status": "danger",
                "detail": f"{days_since} days since last order (avg: {avg_freq:.0f})"
            })
        elif days_since > avg_freq * 1.5:
            factors.append({
                "factor": "recency",
                "status": "warning",
                "detail": f"{days_since} days since last order (avg: {avg_freq:.0f})"
            })
        else:
            factors.append({
                "factor": "recency",
                "status": "ok",
                "detail": f"{days_since} days since last order"
            })

        # Frequency factor
        orders = customer_data.get('orders', [])
        if len(orders) >= 3:
            recent = orders[-3:]
            if len(recent) >= 2:
                recent_dates = [datetime.fromisoformat(o['date'].replace('Z', '+00:00')) for o in recent]
                recent_dates.sort()
                gaps = [(recent_dates[i+1] - recent_dates[i]).days for i in range(len(recent_dates)-1)]
                avg_recent = statistics.mean(gaps) if gaps else 30

                if avg_recent > avg_freq * 1.5:
                    factors.append({
                        "factor": "frequency",
                        "status": "danger",
                        "detail": f"Order frequency down {((avg_recent / avg_freq - 1) * 100):.0f}%"
                    })
                elif avg_recent > avg_freq * 1.2:
                    factors.append({
                        "factor": "frequency",
                        "status": "warning",
                        "detail": "Order frequency declining"
                    })

        # LTV factor
        ltv = customer_data.get('ltv', 0)
        if ltv > 200:
            factors.append({
                "factor": "value",
                "status": "info",
                "detail": f"High LTV customer (${ltv:.2f})"
            })

        # Generate recommendations
        recommendations = self._generate_churn_recommendations(
            churn_probability,
            risk_level,
            ltv,
            customer_data.get('segment', 'NEW_CUSTOMER')
        )

        result = {
            "churn_probability": churn_probability,
            "risk_level": risk_level,
            "factors": factors,
            "recommended_actions": recommendations,
            "analyzed_at": datetime.utcnow().isoformat()
        }

        return result

    def _generate_churn_recommendations(
        self,
        churn_prob: float,
        risk_level: str,
        ltv: float,
        segment: str
    ) -> List[str]:
        """Generate action recommendations based on churn risk"""

        recommendations = []

        if risk_level == "HIGH":
            if ltv > 300:
                recommendations.append("🎯 Personal outreach - high LTV customer at risk")
                recommendations.append("📞 Phone call or personalized email from account manager")

            recommendations.append("💰 Send win-back email with 15-20% discount")
            recommendations.append("🎁 Exclusive offer based on purchase history")

        elif risk_level == "MEDIUM":
            recommendations.append("📧 Re-engagement campaign")
            recommendations.append("🛍️ Feature products from favorite category")
            recommendations.append("⭐ Showcase new arrivals they might like")

        if segment in ['AT_RISK', 'HIBERNATING']:
            recommendations.append("📊 Add to win-back automation sequence")

        if ltv > 200:
            recommendations.append("🏆 VIP perks: early access, free shipping")

        return recommendations

    # ==================== At-Risk Customers ====================

    async def get_at_risk_customers(
        self,
        customers: List[Dict],
        threshold: float = 0.5,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get customers above churn threshold

        Args:
            customers: List of customer data
            threshold: Minimum churn probability (0.0 to 1.0)
            limit: Maximum number to return

        Returns:
            List of at-risk customers with details
        """
        logger.info(f"⚠️  Finding at-risk customers (threshold: {threshold:.0%})...")

        at_risk = []

        for customer in customers:
            churn_prob = await self.calculate_churn_probability(
                customer['customer_id'],
                customer
            )

            if churn_prob >= threshold:
                factors = await self.get_churn_factors(
                    customer['customer_id'],
                    customer
                )

                at_risk.append({
                    **customer,
                    "churn_probability": churn_prob,
                    "churn_factors": factors
                })

        # Sort by churn probability (highest first)
        at_risk.sort(key=lambda x: x['churn_probability'], reverse=True)

        # Prioritize high LTV customers
        high_ltv_risk = [c for c in at_risk if c.get('ltv', 0) > 200]
        other_risk = [c for c in at_risk if c.get('ltv', 0) <= 200]

        # Combine: high LTV first
        combined = high_ltv_risk + other_risk

        logger.info(f"✅ Found {len(combined)} at-risk customers ({len(high_ltv_risk)} high LTV)")

        return combined[:limit]

    # ==================== Churn Rate Analysis ====================

    async def get_churn_rate_trend(self, periods: int = 12) -> List[Dict]:
        """
        Historical churn rate over time

        Args:
            periods: Number of months to analyze

        Returns:
            List of period churn rates
        """
        logger.info(f"📊 Calculating churn rate trend for {periods} periods...")

        # TODO: Calculate from database
        # For now, return mock data

        trend = []
        base_rate = 0.08

        for i in range(periods):
            month_date = datetime.utcnow() - timedelta(days=30 * (periods - i - 1))

            # Add some variance
            import random
            rate = base_rate + random.uniform(-0.03, 0.03)
            rate = max(0.0, min(1.0, rate))

            trend.append({
                "period": month_date.strftime("%Y-%m"),
                "churn_rate": round(rate, 3),
                "churned_customers": int(rate * 100),  # Mock count
                "total_customers": 1250 + (i * 50)  # Growing customer base
            })

        return trend

    async def get_save_rate(self) -> float:
        """
        Percentage of at-risk customers successfully saved

        Returns:
            Save rate as decimal (0.0 to 1.0)
        """
        logger.info("📊 Calculating win-back save rate...")

        # TODO: Calculate from campaign results
        # For now, return mock rate

        return 0.32  # 32% save rate


# Export singleton instance
_churn_predictor = None

def get_churn_predictor(db_session=None):
    """Get or create churn predictor instance"""
    global _churn_predictor
    if _churn_predictor is None:
        _churn_predictor = ChurnPredictor(db_session)
    return _churn_predictor


logger.info("✅ Churn Predictor module loaded")
