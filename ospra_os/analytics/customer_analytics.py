"""
Customer Analytics Engine

Analyzes customer behavior, calculates key metrics, and provides insights
for retention and growth strategies.

Key Capabilities:
- Lifetime Value (LTV) calculation
- RFM scoring and segmentation
- Churn prediction
- Purchase pattern analysis
- Customer acquisition metrics
- Cohort analysis
"""
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
import logging
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class CustomerAnalytics:
    """Central engine for customer analytics and insights"""

    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize Customer Analytics Engine

        Args:
            db_session: Database session for queries
        """
        self.db = db_session

    # ==================== Customer Profile ====================

    async def get_customer_profile(self, customer_id: str) -> Dict:
        """
        Get complete customer profile with all metrics

        Args:
            customer_id: Unique customer ID

        Returns:
            Complete customer profile dictionary
        """
        logger.info(f"[STATS] Getting profile for customer: {customer_id}")

        # TODO: Fetch from database
        # For now, return mock data
        profile = {
            "customer_id": customer_id,
            "email": "customer@example.com",
            "first_name": "John",
            "last_name": "Doe",

            "acquisition": {
                "source": "facebook_ads",
                "campaign": "smart_home_q4",
                "first_order_date": "2025-08-15",
                "acquisition_cost": 12.50
            },

            "lifetime_metrics": {
                "total_orders": 5,
                "total_revenue": 423.50,
                "total_profit": 142.30,
                "ltv": 423.50,
                "predicted_ltv": 680.00,
                "ltv_percentile": 85,
                "average_order_value": 84.70
            },

            "behavior": {
                "purchase_frequency_days": 28,
                "last_order_date": "2025-11-10",
                "days_since_last_order": 15,
                "favorite_category": "smart_home",
                "favorite_products": ["prod_123", "prod_456"],
                "preferred_payment": "credit_card",
                "average_cart_size": 2.4
            },

            "rfm_score": {
                "recency": 5,
                "frequency": 4,
                "monetary": 5,
                "combined_score": 14,
                "segment": "CHAMPION"
            },

            "segment": {
                "primary": "CHAMPION",
                "tags": ["high_value", "repeat_buyer", "smart_home_fan"],
                "risk_level": "LOW"
            },

            "predictions": {
                "churn_probability": 0.12,
                "next_purchase_date": "2025-12-08",
                "next_purchase_value": 95.00,
                "recommended_products": ["prod_789", "prod_012"]
            },

            "last_updated": datetime.utcnow().isoformat()
        }

        return profile

    # ==================== RFM Scoring ====================

    async def calculate_rfm_score(self, customer_id: str) -> Dict:
        """
        Calculate RFM (Recency, Frequency, Monetary) scores

        RFM is scored on 1-5 scale:
        - Recency: Days since last purchase (1=long ago, 5=recent)
        - Frequency: Number of orders (1=few, 5=many)
        - Monetary: Total spend (1=low, 5=high)

        Args:
            customer_id: Unique customer ID

        Returns:
            RFM scores and segment assignment
        """
        logger.info(f"[STATS] Calculating RFM score for: {customer_id}")

        # TODO: Calculate from actual data
        # For now, return mock score

        rfm = {
            "recency": 5,      # Very recent purchase
            "frequency": 4,    # High order count
            "monetary": 5,     # High spend
            "combined_score": 14,
            "segment": self._get_rfm_segment(5, 4, 5),
            "calculated_at": datetime.utcnow().isoformat()
        }

        return rfm

    def _get_rfm_segment(self, r: int, f: int, m: int) -> str:
        """
        Map RFM scores to customer segment

        Segments:
        - CHAMPION: RFM 555, 554, 545, 544
        - LOYAL: RFM 543, 444, 435, 355
        - POTENTIAL_LOYALIST: RFM 553, 551, 532, 512
        - NEW_CUSTOMER: RFM 511, 512, 411
        - AT_RISK: RFM 244, 334, 343, 344
        - HIBERNATING: RFM 233, 232, 223, 222
        - LOST: RFM 111, 112, 121, 122

        Args:
            r: Recency score (1-5)
            f: Frequency score (1-5)
            m: Monetary score (1-5)

        Returns:
            Segment name
        """
        rfm_str = f"{r}{f}{m}"

        if rfm_str in ['555', '554', '545', '544']:
            return 'CHAMPION'
        elif rfm_str in ['543', '444', '435', '355', '445', '454', '455']:
            return 'LOYAL'
        elif rfm_str in ['553', '551', '552', '541', '542', '532', '531', '521', '522', '512', '511']:
            return 'POTENTIAL_LOYALIST'
        elif rfm_str in ['511', '512', '411', '412', '311', '312']:
            return 'NEW_CUSTOMER'
        elif rfm_str in ['244', '334', '343', '344', '234', '243']:
            return 'AT_RISK'
        elif rfm_str in ['233', '232', '223', '222', '133', '132', '123', '122']:
            return 'HIBERNATING'
        elif rfm_str in ['111', '112', '121', '211', '212', '221']:
            return 'LOST'
        else:
            # Default to potential loyalist for mid-range scores
            return 'POTENTIAL_LOYALIST'

    # ==================== Segmentation ====================

    async def get_customer_segment(self, customer_id: str) -> str:
        """
        Determine customer segment based on behavior

        Args:
            customer_id: Unique customer ID

        Returns:
            Segment name
        """
        rfm = await self.calculate_rfm_score(customer_id)
        return rfm['segment']

    async def get_segment_breakdown(self, store_id: Optional[str] = None) -> Dict:
        """
        Distribution of customers across segments

        Args:
            store_id: Optional store filter

        Returns:
            Segment counts and metrics
        """
        logger.info("[STATS] Calculating segment breakdown...")

        # TODO: Calculate from database
        # For now, return empty data until customers are synced

        breakdown = {
            "total_customers": 0,
            "segments": [
                {
                    "segment": "CHAMPION",
                    "icon": "[TOP]",
                    "count": 0,
                    "percentage": 0.0,
                    "avg_ltv": 0.00,
                    "avg_orders": 0.0,
                    "churn_rate": 0.0
                },
                {
                    "segment": "LOYAL",
                    "icon": "",
                    "count": 0,
                    "percentage": 0.0,
                    "avg_ltv": 0.00,
                    "avg_orders": 0.0,
                    "churn_rate": 0.0
                },
                {
                    "segment": "POTENTIAL_LOYALIST",
                    "icon": "[FEATURED]",
                    "count": 0,
                    "percentage": 0.0,
                    "avg_ltv": 0.00,
                    "avg_orders": 0.0,
                    "churn_rate": 0.0
                },
                {
                    "segment": "NEW_CUSTOMER",
                    "icon": "[NEW]",
                    "count": 0,
                    "percentage": 0.0,
                    "avg_ltv": 0.00,
                    "avg_orders": 0.0,
                    "churn_rate": 0.0
                },
                {
                    "segment": "AT_RISK",
                    "icon": "",
                    "count": 0,
                    "percentage": 0.0,
                    "avg_ltv": 0.00,
                    "avg_orders": 0.0,
                    "churn_rate": 0.0
                },
                {
                    "segment": "HIBERNATING",
                    "icon": "",
                    "count": 0,
                    "percentage": 0.0,
                    "avg_ltv": 0.00,
                    "avg_orders": 0.0,
                    "churn_rate": 0.0
                },
                {
                    "segment": "LOST",
                    "icon": "",
                    "count": 0,
                    "percentage": 0.0,
                    "avg_ltv": 0.00,
                    "avg_orders": 0.0,
                    "churn_rate": 0.0
                }
            ],
            "generated_at": datetime.utcnow().isoformat()
        }

        return breakdown

    # ==================== Churn Prediction ====================

    async def predict_churn(self, customer_id: str) -> float:
        """
        Predict probability of customer churning

        Factors:
        - Days since last purchase vs average
        - Purchase frequency trend
        - Order value trend
        - Engagement level

        Args:
            customer_id: Unique customer ID

        Returns:
            Churn probability (0.0 to 1.0)
        """
        logger.info(f" Predicting churn for: {customer_id}")

        # TODO: Implement actual prediction
        # For now, return mock probability based on segment

        segment = await self.get_customer_segment(customer_id)

        churn_by_segment = {
            'CHAMPION': 0.05,
            'LOYAL': 0.08,
            'POTENTIAL_LOYALIST': 0.12,
            'NEW_CUSTOMER': 0.20,
            'AT_RISK': 0.65,
            'HIBERNATING': 0.75,
            'LOST': 0.95
        }

        return churn_by_segment.get(segment, 0.25)

    async def get_at_risk_customers(self, threshold: float = 0.5, limit: int = 50) -> List[Dict]:
        """
        Get customers at high risk of churning

        Args:
            threshold: Minimum churn probability (0.0 to 1.0)
            limit: Maximum number to return

        Returns:
            List of at-risk customers with details
        """
        logger.info(f"[WARNING] Finding at-risk customers (threshold: {threshold})...")

        # TODO: Query database for at-risk customers
        # For now, return mock data

        at_risk = [
            {
                "customer_id": "cust_001",
                "name": "Sara Martinez",
                "email": "sara@example.com",
                "ltv": 285.00,
                "total_orders": 4,
                "last_order_date": "2025-10-01",
                "days_since_last_order": 45,
                "churn_probability": 0.78,
                "segment": "AT_RISK",
                "previous_segment": "LOYAL",
                "risk_factors": [
                    {"factor": "recency", "status": "danger", "detail": "45 days since last order (avg: 28)"},
                    {"factor": "frequency", "status": "warning", "detail": "Order frequency down 40%"},
                    {"factor": "engagement", "status": "ok", "detail": "Still opening emails"}
                ],
                "recommended_actions": [
                    "Send win-back email with 15% discount",
                    "Feature products from smart_home category",
                    "Personal outreach - high LTV customer"
                ]
            },
            {
                "customer_id": "cust_002",
                "name": "Mike Thompson",
                "email": "mike@example.com",
                "ltv": 195.00,
                "total_orders": 3,
                "last_order_date": "2025-10-10",
                "days_since_last_order": 36,
                "churn_probability": 0.65,
                "segment": "AT_RISK",
                "previous_segment": "POTENTIAL_LOYALIST",
                "risk_factors": [
                    {"factor": "recency", "status": "warning", "detail": "36 days since last order"},
                    {"factor": "engagement", "status": "danger", "detail": "No email opens in 30 days"}
                ],
                "recommended_actions": [
                    "Re-engagement campaign",
                    "Product recommendations based on history"
                ]
            }
        ]

        return at_risk[:limit]

    # ==================== LTV Analysis ====================

    async def calculate_ltv(self, customer_id: str) -> Dict:
        """
        Calculate lifetime value and predicted LTV

        Args:
            customer_id: Unique customer ID

        Returns:
            LTV metrics
        """
        logger.info(f"[PRICE] Calculating LTV for: {customer_id}")

        # TODO: Calculate from orders
        # For now, return mock data

        ltv_data = {
            "historical_ltv": 423.50,
            "predicted_12m_ltv": 256.50,
            "predicted_total_ltv": 680.00,
            "ltv_percentile": 85,
            "confidence": 0.78,
            "factors": {
                "purchase_frequency_trend": "stable",
                "aov_trend": "increasing",
                "churn_risk": "low"
            },
            "calculated_at": datetime.utcnow().isoformat()
        }

        return ltv_data

    async def get_ltv_distribution(self) -> Dict:
        """
        LTV distribution across customer base

        Returns:
            Distribution buckets with counts
        """
        logger.info("[STATS] Calculating LTV distribution...")

        distribution = {
            "buckets": [
                {"range": "$0-50", "count": 450, "percentage": 18.4},
                {"range": "$50-100", "count": 620, "percentage": 25.3},
                {"range": "$100-200", "count": 520, "percentage": 21.2},
                {"range": "$200-500", "count": 380, "percentage": 15.5},
                {"range": "$500+", "count": 480, "percentage": 19.6}
            ],
            "statistics": {
                "mean": 185.50,
                "median": 142.00,
                "p25": 75.00,
                "p75": 285.00,
                "p90": 520.00
            },
            "generated_at": datetime.utcnow().isoformat()
        }

        return distribution

    async def get_top_customers(self, metric: str = 'ltv', limit: int = 20) -> List[Dict]:
        """
        Top customers by specified metric

        Args:
            metric: Metric to sort by (ltv, orders, revenue)
            limit: Number of customers to return

        Returns:
            List of top customers
        """
        logger.info(f"[TOP] Getting top {limit} customers by {metric}...")

        # TODO: Query database
        # For now, return mock data

        top = [
            {
                "customer_id": "cust_top1",
                "name": "Jennifer Williams",
                "email": "jennifer@example.com",
                "segment": "CHAMPION",
                "ltv": 1250.00,
                "total_orders": 15,
                "total_revenue": 1250.00,
                "avg_order_value": 83.33,
                "first_order_date": "2025-01-15"
            },
            {
                "customer_id": "cust_top2",
                "name": "David Chen",
                "email": "david@example.com",
                "segment": "CHAMPION",
                "ltv": 1120.00,
                "total_orders": 12,
                "total_revenue": 1120.00,
                "avg_order_value": 93.33,
                "first_order_date": "2025-02-03"
            }
        ]

        return top[:limit]

    # ==================== Cohort Analysis ====================

    async def get_cohort_analysis(self, cohort_type: str = 'monthly', periods: int = 12) -> Dict:
        """
        Retention analysis by acquisition cohort

        Args:
            cohort_type: Type of cohort (monthly, weekly)
            periods: Number of periods to analyze

        Returns:
            Cohort retention table
        """
        logger.info(f"[STATS] Generating {cohort_type} cohort analysis for {periods} periods...")

        # TODO: Calculate from database
        # For now, return mock data

        cohorts = {
            "cohort_type": cohort_type,
            "periods": periods,
            "cohorts": [
                {
                    "cohort": "2025-08",
                    "size": 150,
                    "retention": [100, 45, 32, 28, 25, 23]
                },
                {
                    "cohort": "2025-09",
                    "size": 180,
                    "retention": [100, 48, 35, 30, 27]
                },
                {
                    "cohort": "2025-10",
                    "size": 210,
                    "retention": [100, 52, 38, 32]
                },
                {
                    "cohort": "2025-11",
                    "size": 165,
                    "retention": [100, 50]
                }
            ],
            "averages": [100, 49, 35, 30, 26, 23],
            "best_cohort": "2025-10",
            "worst_cohort": "2025-08",
            "generated_at": datetime.utcnow().isoformat()
        }

        return cohorts

    # ==================== Purchase Patterns ====================

    async def get_purchase_patterns(self, customer_id: str) -> Dict:
        """
        Analyze purchase behavior patterns

        Args:
            customer_id: Unique customer ID

        Returns:
            Purchase pattern analysis
        """
        logger.info(f"[SEARCH] Analyzing purchase patterns for: {customer_id}")

        patterns = {
            "timing": {
                "best_day": "Tuesday",
                "best_hour": 14,
                "day_distribution": {
                    "Monday": 10,
                    "Tuesday": 25,
                    "Wednesday": 15,
                    "Thursday": 20,
                    "Friday": 15,
                    "Saturday": 10,
                    "Sunday": 5
                }
            },
            "product_preferences": {
                "favorite_categories": ["smart_home", "fitness"],
                "price_range": {"min": 20, "max": 150, "avg": 65}
            },
            "frequency": {
                "average_days_between": 28,
                "median_days_between": 25,
                "trend": "stable"
            },
            "analyzed_at": datetime.utcnow().isoformat()
        }

        return patterns

    async def get_product_affinity(self, customer_id: str) -> List[Dict]:
        """
        Products this customer is likely to buy

        Args:
            customer_id: Unique customer ID

        Returns:
            List of recommended products with affinity scores
        """
        logger.info(f"[TARGET] Calculating product affinity for: {customer_id}")

        # TODO: Calculate based on purchase history and similar customers

        recommendations = [
            {
                "product_id": "prod_789",
                "product_name": "Smart Thermostat",
                "affinity_score": 0.85,
                "reason": "Category match: smart_home"
            },
            {
                "product_id": "prod_012",
                "product_name": "Motion Sensor 3-Pack",
                "affinity_score": 0.78,
                "reason": "Commonly bought with previous purchases"
            }
        ]

        return recommendations

    # ==================== Aggregate Metrics ====================

    async def get_customer_acquisition_metrics(self) -> Dict:
        """
        CAC, LTV:CAC ratio, payback period

        Returns:
            Customer acquisition metrics
        """
        logger.info("[PRICE] Calculating customer acquisition metrics...")

        metrics = {
            "customer_acquisition_cost": 15.50,
            "average_ltv": 185.50,
            "ltv_to_cac_ratio": 12.0,
            "payback_period_months": 2.5,
            "by_source": {
                "facebook_ads": {
                    "customers": 850,
                    "cac": 18.50,
                    "avg_ltv": 195.00,
                    "ltv_to_cac": 10.5
                },
                "google_ads": {
                    "customers": 520,
                    "cac": 22.00,
                    "avg_ltv": 210.00,
                    "ltv_to_cac": 9.5
                },
                "organic": {
                    "customers": 680,
                    "cac": 5.00,
                    "avg_ltv": 165.00,
                    "ltv_to_cac": 33.0
                }
            },
            "calculated_at": datetime.utcnow().isoformat()
        }

        return metrics

    async def calculate_retention_rate(self, period: str = 'monthly') -> float:
        """
        Overall retention rate

        Args:
            period: Time period (monthly, weekly)

        Returns:
            Retention rate as decimal
        """
        logger.info(f"[STATS] Calculating {period} retention rate...")

        # TODO: Calculate from database
        # For now, return mock rate

        return 0.34  # 34% retention rate

    async def calculate_churn_rate(self, period: str = 'monthly') -> float:
        """
        Overall churn rate

        Args:
            period: Time period (monthly, weekly)

        Returns:
            Churn rate as decimal
        """
        logger.info(f"[STATS] Calculating {period} churn rate...")

        # TODO: Calculate from database
        # For now, return mock rate

        return 0.08  # 8% churn rate

    async def get_new_vs_returning(self, date_range: Dict) -> Dict:
        """
        New vs returning customer breakdown

        Args:
            date_range: Date range filter

        Returns:
            New vs returning metrics
        """
        logger.info("[STATS] Calculating new vs returning customers...")

        breakdown = {
            "new_customers": {
                "count": 380,
                "percentage": 62.3,
                "revenue": 28500.00,
                "avg_order_value": 75.00
            },
            "returning_customers": {
                "count": 230,
                "percentage": 37.7,
                "revenue": 45800.00,
                "avg_order_value": 199.13
            },
            "total_customers": 610,
            "total_revenue": 74300.00,
            "date_range": date_range,
            "generated_at": datetime.utcnow().isoformat()
        }

        return breakdown

    # ==================== Helper Methods ====================

    def _calculate_percentile(self, value: float, all_values: List[float]) -> int:
        """Calculate what percentile this value falls into"""
        if not all_values:
            return 50

        sorted_values = sorted(all_values)
        position = sum(1 for v in sorted_values if v <= value)
        percentile = int((position / len(sorted_values)) * 100)

        return percentile


# Export singleton instance
_customer_analytics = None

def get_customer_analytics(db_session=None):
    """Get or create customer analytics instance"""
    global _customer_analytics
    if _customer_analytics is None:
        _customer_analytics = CustomerAnalytics(db_session)
    return _customer_analytics


logger.info("[SUCCESS] Customer Analytics module loaded")
