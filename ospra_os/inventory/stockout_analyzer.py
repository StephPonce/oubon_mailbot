"""
Stockout Risk Analyzer - Assess and prevent stockout risks

Analyzes multiple risk factors to predict stockout probability and
provides actionable recommendations.
"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import math


class StockoutAnalyzer:
    """Assess stockout risk and provide mitigation strategies"""

    def __init__(self):
        pass

    async def calculate_stockout_risk(
        self,
        current_stock: int,
        daily_velocity: float,
        velocity_std_dev: float,
        lead_time_days: int,
        supplier_reliability: float = 0.95,
        seasonal_adjustment: float = 1.0,
        pending_orders: int = 0
    ) -> Dict:
        """
        Calculate comprehensive stockout risk

        Args:
            current_stock: Current inventory level
            daily_velocity: Average units sold per day
            velocity_std_dev: Standard deviation of daily sales
            lead_time_days: Supplier lead time
            supplier_reliability: Supplier on-time delivery rate (0-1)
            seasonal_adjustment: Seasonal demand multiplier
            pending_orders: Units on order

        Returns:
            {
                "risk_score": 0.35,  # 0-1
                "risk_level": "MEDIUM",
                "stockout_probability_7d": 0.05,
                "stockout_probability_14d": 0.15,
                "stockout_probability_30d": 0.35,
                "risk_factors": [...],
                "recommended_actions": [...]
            }
        """
        # Adjust velocity for seasonality
        adjusted_velocity = daily_velocity * seasonal_adjustment

        # Calculate effective stock (current + pending)
        effective_stock = current_stock + pending_orders

        # Calculate days of stock remaining
        days_of_stock = effective_stock / adjusted_velocity if adjusted_velocity > 0 else 999

        # Calculate stockout probabilities for different time horizons
        prob_7d = await self._calculate_stockout_probability(
            effective_stock, adjusted_velocity, velocity_std_dev, 7
        )
        prob_14d = await self._calculate_stockout_probability(
            effective_stock, adjusted_velocity, velocity_std_dev, 14
        )
        prob_30d = await self._calculate_stockout_probability(
            effective_stock, adjusted_velocity, velocity_std_dev, 30
        )

        # Identify risk factors
        risk_factors = await self._identify_risk_factors(
            current_stock,
            adjusted_velocity,
            days_of_stock,
            lead_time_days,
            supplier_reliability,
            seasonal_adjustment,
            pending_orders
        )

        # Calculate overall risk score (0-1)
        risk_score = await self._calculate_risk_score(
            days_of_stock,
            lead_time_days,
            prob_30d,
            len([f for f in risk_factors if f["impact"] in ["HIGH", "CRITICAL"]])
        )

        # Determine risk level
        risk_level = await self._determine_risk_level(risk_score)

        # Generate recommendations
        recommendations = await self._generate_recommendations(
            risk_level,
            risk_factors,
            days_of_stock,
            lead_time_days,
            seasonal_adjustment
        )

        return {
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "days_of_stock": round(days_of_stock, 1),
            "stockout_probability_7d": round(prob_7d, 2),
            "stockout_probability_14d": round(prob_14d, 2),
            "stockout_probability_30d": round(prob_30d, 2),
            "risk_factors": risk_factors,
            "recommended_actions": recommendations
        }

    async def _calculate_stockout_probability(
        self,
        stock: int,
        velocity: float,
        std_dev: float,
        days: int
    ) -> float:
        """
        Calculate probability of stockout within X days using normal distribution

        P(stockout) = P(demand > stock)
        """
        if velocity <= 0:
            return 0.0

        # Expected demand over period
        expected_demand = velocity * days

        # Standard deviation of demand over period
        demand_std = std_dev * math.sqrt(days)

        if demand_std == 0:
            # Deterministic case
            return 1.0 if expected_demand > stock else 0.0

        # Z-score: how many standard deviations is stock from expected demand
        z = (stock - expected_demand) / demand_std

        # Convert Z-score to probability using approximation
        # P(Z > z) = stockout probability
        if z > 3:
            probability = 0.0
        elif z < -3:
            probability = 1.0
        else:
            # Normal CDF approximation
            probability = 0.5 * (1 - math.erf(z / math.sqrt(2)))

        return max(0.0, min(1.0, probability))

    async def _identify_risk_factors(
        self,
        stock: int,
        velocity: float,
        days_of_stock: float,
        lead_time_days: int,
        supplier_reliability: float,
        seasonal_adjustment: float,
        pending_orders: int
    ) -> List[Dict]:
        """
        Identify specific risk factors

        Returns list of: {"factor": "Low stock", "impact": "HIGH", "detail": "..."}
        """
        factors = []

        # Stock level risk
        if days_of_stock <= 0:
            factors.append({
                "factor": "Out of stock",
                "impact": "CRITICAL",
                "detail": "No inventory available"
            })
        elif days_of_stock < 7:
            factors.append({
                "factor": "Critical stock level",
                "impact": "CRITICAL",
                "detail": f"Only {days_of_stock:.1f} days of stock remaining"
            })
        elif days_of_stock < 14:
            factors.append({
                "factor": "Low stock",
                "impact": "HIGH",
                "detail": f"{days_of_stock:.1f} days of stock remaining"
            })
        elif days_of_stock < lead_time_days:
            factors.append({
                "factor": "Below lead time",
                "impact": "MEDIUM",
                "detail": f"Stock less than {lead_time_days} day lead time"
            })

        # Seasonal risk
        if seasonal_adjustment > 1.2:
            factors.append({
                "factor": "Seasonal surge",
                "impact": "MEDIUM" if seasonal_adjustment < 1.5 else "HIGH",
                "detail": f"Demand {int((seasonal_adjustment-1)*100)}% above normal"
            })

        # Supplier risk
        if supplier_reliability < 0.90:
            factors.append({
                "factor": "Supplier reliability",
                "impact": "MEDIUM",
                "detail": f"Supplier on-time rate: {int(supplier_reliability*100)}%"
            })

        # Lead time risk
        if lead_time_days > 14:
            factors.append({
                "factor": "Long lead time",
                "impact": "LOW",
                "detail": f"{lead_time_days} days from order to delivery"
            })

        # No pending orders risk
        if pending_orders == 0 and days_of_stock < lead_time_days:
            factors.append({
                "factor": "No pending restock",
                "impact": "HIGH",
                "detail": "No orders placed despite low stock"
            })

        return factors

    async def _calculate_risk_score(
        self,
        days_of_stock: float,
        lead_time_days: int,
        prob_30d: float,
        high_risk_factor_count: int
    ) -> float:
        """
        Calculate overall risk score (0-1)

        Weighted combination of:
        - Days of stock vs lead time
        - 30-day stockout probability
        - Number of high-impact risk factors
        """
        # Days of stock score (0-1, higher = more risk)
        if days_of_stock <= 0:
            days_score = 1.0
        elif days_of_stock < lead_time_days:
            days_score = 0.8
        elif days_of_stock < lead_time_days * 2:
            days_score = 0.4
        else:
            days_score = max(0, 0.2 - (days_of_stock - lead_time_days * 2) * 0.01)

        # Probability score
        prob_score = prob_30d

        # Risk factor score
        factor_score = min(1.0, high_risk_factor_count * 0.25)

        # Weighted average
        risk_score = (days_score * 0.5) + (prob_score * 0.3) + (factor_score * 0.2)

        return max(0.0, min(1.0, risk_score))

    async def _determine_risk_level(self, risk_score: float) -> str:
        """Convert risk score to level"""
        if risk_score >= 0.75:
            return "CRITICAL"
        elif risk_score >= 0.50:
            return "HIGH"
        elif risk_score >= 0.25:
            return "MEDIUM"
        else:
            return "LOW"

    async def _generate_recommendations(
        self,
        risk_level: str,
        risk_factors: List[Dict],
        days_of_stock: float,
        lead_time_days: int,
        seasonal_adjustment: float
    ) -> List[str]:
        """Generate actionable recommendations based on risk assessment"""
        recommendations = []

        if risk_level == "CRITICAL":
            recommendations.append(" URGENT: Place restock order immediately")
            recommendations.append("Consider expedited shipping to reduce lead time")
            recommendations.append("Review sales channels - may need to pause sales")

        elif risk_level == "HIGH":
            recommendations.append("[WARNING]  Place restock order within 1-2 days")
            if seasonal_adjustment > 1.2:
                recommendations.append(f"Order {int((seasonal_adjustment-1)*100)}% extra for seasonal surge")

        elif risk_level == "MEDIUM":
            recommendations.append("[LIST] Schedule restock order for next week")
            recommendations.append("Monitor stock levels daily")

        # Specific factor-based recommendations
        for factor in risk_factors:
            if factor["factor"] == "Seasonal surge" and factor["impact"] == "HIGH":
                recommendations.append("Consider ordering buffer stock for holiday season")

            if factor["factor"] == "Supplier reliability" and factor["impact"] == "MEDIUM":
                recommendations.append("Add extra buffer due to supplier delays")

            if factor["factor"] == "No pending restock" and factor["impact"] == "HIGH":
                recommendations.append("No orders in pipeline - place order now")

        # General recommendations
        if days_of_stock < lead_time_days * 1.5:
            recommendations.append(f"Maintain at least {int(lead_time_days * 1.5)} days of stock")

        return recommendations

    async def get_at_risk_products(
        self,
        products: List[Dict],
        threshold: float = 0.3
    ) -> List[Dict]:
        """
        Filter products with risk score above threshold

        Args:
            products: List of product inventory data
            threshold: Risk score threshold (0-1)

        Returns:
            List of at-risk products sorted by risk score (descending)
        """
        at_risk = []

        for product in products:
            risk_score = product.get('stockout_risk', 0)
            if risk_score >= threshold:
                at_risk.append(product)

        # Sort by risk score (highest first)
        at_risk.sort(key=lambda p: p.get('stockout_risk', 0), reverse=True)

        return at_risk

    async def calculate_revenue_at_risk(
        self,
        daily_velocity: float,
        unit_price: float,
        stockout_probability_30d: float
    ) -> Dict:
        """
        Calculate potential lost revenue from stockout

        Args:
            daily_velocity: Units sold per day
            unit_price: Selling price per unit
            stockout_probability_30d: Probability of stockout in 30 days

        Returns:
            {
                "daily_revenue": 125.50,
                "revenue_at_risk_7d": 878.50,
                "revenue_at_risk_30d": 3765.00,
                "expected_loss": 1318.00  # Probability-weighted
            }
        """
        daily_revenue = daily_velocity * unit_price

        # Potential revenue over different time horizons
        revenue_7d = daily_revenue * 7
        revenue_30d = daily_revenue * 30

        # Expected loss = Probability × Potential loss
        expected_loss = revenue_30d * stockout_probability_30d

        return {
            "daily_revenue": round(daily_revenue, 2),
            "revenue_at_risk_7d": round(revenue_7d, 2),
            "revenue_at_risk_30d": round(revenue_30d, 2),
            "expected_loss": round(expected_loss, 2),
            "probability": round(stockout_probability_30d, 2)
        }

    async def calculate_service_level(
        self,
        orders_fulfilled: int,
        total_orders: int
    ) -> float:
        """
        Calculate service level (order fill rate)

        Service Level = Orders Fulfilled / Total Orders

        Returns: 0-1 (e.g., 0.96 = 96% of orders fulfilled)
        """
        if total_orders == 0:
            return 1.0

        service_level = orders_fulfilled / total_orders
        return round(service_level, 3)

    async def get_stockout_history(
        self,
        stockout_events: List[Dict]
    ) -> Dict:
        """
        Analyze historical stockout events

        Args:
            stockout_events: List of past stockout records

        Returns:
            {
                "total_stockouts": 3,
                "total_duration_hours": 72,
                "average_duration_hours": 24,
                "total_lost_revenue": 1250.00,
                "most_common_cause": "supplier_delay",
                "last_stockout": "2025-10-15"
            }
        """
        if not stockout_events:
            return {
                "total_stockouts": 0,
                "total_duration_hours": 0,
                "average_duration_hours": 0,
                "total_lost_revenue": 0.0,
                "most_common_cause": None,
                "last_stockout": None
            }

        total_stockouts = len(stockout_events)
        total_duration = sum(e.get('duration_hours', 0) for e in stockout_events)
        total_lost_revenue = sum(e.get('estimated_lost_revenue', 0) for e in stockout_events)

        # Find most common cause
        causes = [e.get('cause') for e in stockout_events if e.get('cause')]
        most_common_cause = max(set(causes), key=causes.count) if causes else None

        # Get most recent stockout
        sorted_events = sorted(stockout_events, key=lambda e: e.get('stockout_start', ''), reverse=True)
        last_stockout = sorted_events[0].get('stockout_start') if sorted_events else None

        return {
            "total_stockouts": total_stockouts,
            "total_duration_hours": round(total_duration, 1),
            "average_duration_hours": round(total_duration / total_stockouts, 1),
            "total_lost_revenue": round(total_lost_revenue, 2),
            "most_common_cause": most_common_cause,
            "last_stockout": last_stockout
        }
