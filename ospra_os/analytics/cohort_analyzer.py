"""
Cohort Analyzer - Customer Retention Analysis

Analyzes customer retention by acquisition cohort:
- Monthly cohorts: Customers acquired in same month
- Weekly cohorts: Customers acquired in same week
- Campaign cohorts: Customers from same campaign
- Product cohorts: Customers who first bought same product

Generates cohort retention tables showing percentage of customers
who make repeat purchases in subsequent periods.
"""
from datetime import datetime, timedelta, date, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging
import calendar

logger = logging.getLogger(__name__)


class CohortAnalyzer:
    """Analyze customer retention by acquisition cohort"""

    def __init__(self, db_session=None):
        """
        Initialize Cohort Analyzer

        Args:
            db_session: Database session for queries
        """
        self.db = db_session

    # ==================== Cohort Table Generation ====================

    async def get_cohort_table(
        self,
        customers: List[Dict],
        cohort_type: str = 'monthly',
        periods: int = 12
    ) -> Dict:
        """
        Generate cohort retention table

        Args:
            customers: List of customer data with orders
            cohort_type: Type of cohort (monthly, weekly)
            periods: Number of periods to analyze

        Returns:
            Cohort retention table with percentages
        """
        logger.info(f"[STATS] Generating {cohort_type} cohort table for {periods} periods...")

        if cohort_type == 'monthly':
            cohorts = await self._build_monthly_cohorts(customers, periods)
        elif cohort_type == 'weekly':
            cohorts = await self._build_weekly_cohorts(customers, periods)
        else:
            raise ValueError(f"Unknown cohort type: {cohort_type}")

        # Calculate averages across all cohorts
        averages = self._calculate_cohort_averages(cohorts)

        # Identify best and worst cohorts
        best_cohort = self._find_best_cohort(cohorts)
        worst_cohort = self._find_worst_cohort(cohorts)

        result = {
            "cohort_type": cohort_type,
            "periods": periods,
            "cohorts": cohorts,
            "averages": averages,
            "best_cohort": best_cohort,
            "worst_cohort": worst_cohort,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"[SUCCESS] Generated {len(cohorts)} cohorts")

        return result

    async def _build_monthly_cohorts(
        self,
        customers: List[Dict],
        periods: int
    ) -> List[Dict]:
        """
        Build monthly cohorts

        Args:
            customers: List of customer data
            periods: Number of months to analyze

        Returns:
            List of cohort dictionaries
        """
        # Group customers by acquisition month
        cohort_groups = defaultdict(list)

        for customer in customers:
            acq_date = customer.get('acquisition_date')
            if not acq_date:
                continue

            if isinstance(acq_date, str):
                acq_date = datetime.fromisoformat(acq_date.replace('Z', '+00:00')).date()

            cohort_key = acq_date.strftime('%Y-%m')
            cohort_groups[cohort_key].append(customer)

        # Sort cohorts by date (oldest first)
        sorted_cohorts = sorted(cohort_groups.keys())

        # Take last N periods
        recent_cohorts = sorted_cohorts[-periods:] if len(sorted_cohorts) > periods else sorted_cohorts

        # Build retention data for each cohort
        cohort_data = []

        for cohort_key in recent_cohorts:
            customers_in_cohort = cohort_groups[cohort_key]
            cohort_size = len(customers_in_cohort)

            # Calculate retention for each period
            retention = await self._calculate_retention_by_period(
                customers_in_cohort,
                cohort_key,
                'monthly'
            )

            cohort_data.append({
                "cohort": cohort_key,
                "size": cohort_size,
                "retention": retention
            })

        return cohort_data

    async def _build_weekly_cohorts(
        self,
        customers: List[Dict],
        periods: int
    ) -> List[Dict]:
        """
        Build weekly cohorts

        Args:
            customers: List of customer data
            periods: Number of weeks to analyze

        Returns:
            List of cohort dictionaries
        """
        # Group customers by acquisition week
        cohort_groups = defaultdict(list)

        for customer in customers:
            acq_date = customer.get('acquisition_date')
            if not acq_date:
                continue

            if isinstance(acq_date, str):
                acq_date = datetime.fromisoformat(acq_date.replace('Z', '+00:00')).date()

            # Get ISO week number
            year, week, _ = acq_date.isocalendar()
            cohort_key = f"{year}-W{week:02d}"
            cohort_groups[cohort_key].append(customer)

        # Sort and take recent periods
        sorted_cohorts = sorted(cohort_groups.keys())
        recent_cohorts = sorted_cohorts[-periods:] if len(sorted_cohorts) > periods else sorted_cohorts

        # Build retention data
        cohort_data = []

        for cohort_key in recent_cohorts:
            customers_in_cohort = cohort_groups[cohort_key]
            cohort_size = len(customers_in_cohort)

            retention = await self._calculate_retention_by_period(
                customers_in_cohort,
                cohort_key,
                'weekly'
            )

            cohort_data.append({
                "cohort": cohort_key,
                "size": cohort_size,
                "retention": retention
            })

        return cohort_data

    async def _calculate_retention_by_period(
        self,
        customers: List[Dict],
        cohort_key: str,
        period_type: str
    ) -> List[float]:
        """
        Calculate retention percentage for each period

        Args:
            customers: Customers in this cohort
            cohort_key: Cohort identifier
            period_type: monthly or weekly

        Returns:
            List of retention percentages [100, 45, 32, 28, ...]
        """
        cohort_size = len(customers)
        if cohort_size == 0:
            return [100]

        # Parse cohort start date
        if period_type == 'monthly':
            cohort_start = datetime.strptime(cohort_key, '%Y-%m').date()
        else:  # weekly
            year, week = cohort_key.split('-W')
            cohort_start = datetime.strptime(f"{year} {week} 1", "%Y %W %w").date()

        # Calculate retention for each subsequent period
        retention = [100]  # Period 0 is always 100%
        max_periods = 12

        for period in range(1, max_periods + 1):
            # Calculate period end date
            if period_type == 'monthly':
                period_start = cohort_start + timedelta(days=30 * period)
                period_end = period_start + timedelta(days=30)
            else:  # weekly
                period_start = cohort_start + timedelta(weeks=period)
                period_end = period_start + timedelta(weeks=1)

            # Count customers who made purchase in this period
            active_customers = 0

            for customer in customers:
                orders = customer.get('orders', [])

                for order in orders:
                    order_date_str = order.get('date', '')
                    if order_date_str:
                        order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00')).date()

                        if period_start <= order_date < period_end:
                            active_customers += 1
                            break  # Count customer only once per period

            # Calculate retention percentage
            retention_pct = (active_customers / cohort_size) * 100
            retention.append(round(retention_pct))

            # Stop if period is in the future
            if period_end > datetime.now(timezone.utc).date():
                break

        return retention

    def _calculate_cohort_averages(self, cohorts: List[Dict]) -> List[float]:
        """
        Calculate average retention across all cohorts

        Args:
            cohorts: List of cohort data

        Returns:
            Average retention for each period
        """
        if not cohorts:
            return [100]

        # Find max period length
        max_length = max(len(c['retention']) for c in cohorts)

        # Calculate average for each period
        averages = []

        for period_idx in range(max_length):
            period_values = []

            for cohort in cohorts:
                if period_idx < len(cohort['retention']):
                    period_values.append(cohort['retention'][period_idx])

            if period_values:
                avg = sum(period_values) / len(period_values)
                averages.append(round(avg))
            else:
                averages.append(0)

        return averages

    def _find_best_cohort(self, cohorts: List[Dict]) -> Optional[str]:
        """Find cohort with best retention"""
        if not cohorts:
            return None

        # Calculate average retention (excluding period 0)
        best_cohort = None
        best_avg = 0

        for cohort in cohorts:
            if len(cohort['retention']) > 2:
                # Average of period 1 onwards
                avg = sum(cohort['retention'][1:]) / len(cohort['retention'][1:])

                if avg > best_avg:
                    best_avg = avg
                    best_cohort = cohort['cohort']

        return best_cohort

    def _find_worst_cohort(self, cohorts: List[Dict]) -> Optional[str]:
        """Find cohort with worst retention"""
        if not cohorts:
            return None

        worst_cohort = None
        worst_avg = 100

        for cohort in cohorts:
            if len(cohort['retention']) > 2:
                avg = sum(cohort['retention'][1:]) / len(cohort['retention'][1:])

                if avg < worst_avg:
                    worst_avg = avg
                    worst_cohort = cohort['cohort']

        return worst_cohort

    # ==================== Cohort LTV Analysis ====================

    async def get_cohort_ltv(
        self,
        customers: List[Dict],
        cohort_type: str = 'monthly'
    ) -> Dict:
        """
        LTV breakdown by cohort

        Args:
            customers: List of customer data
            cohort_type: Type of cohort

        Returns:
            LTV metrics per cohort
        """
        logger.info(f"[PRICE] Calculating LTV by {cohort_type} cohort...")

        # Group customers by cohort
        cohort_groups = defaultdict(list)

        for customer in customers:
            acq_date = customer.get('acquisition_date')
            if not acq_date:
                continue

            if isinstance(acq_date, str):
                acq_date = datetime.fromisoformat(acq_date.replace('Z', '+00:00')).date()

            if cohort_type == 'monthly':
                cohort_key = acq_date.strftime('%Y-%m')
            else:  # weekly
                year, week, _ = acq_date.isocalendar()
                cohort_key = f"{year}-W{week:02d}"

            cohort_groups[cohort_key].append(customer)

        # Calculate LTV metrics for each cohort
        cohort_ltv = {}

        for cohort_key, cohort_customers in cohort_groups.items():
            ltvs = [c.get('ltv', 0) for c in cohort_customers]

            if ltvs:
                import statistics
                cohort_ltv[cohort_key] = {
                    "size": len(ltvs),
                    "avg_ltv": round(statistics.mean(ltvs), 2),
                    "median_ltv": round(statistics.median(ltvs), 2),
                    "total_ltv": round(sum(ltvs), 2)
                }

        return cohort_ltv

    # ==================== Cohort Comparison ====================

    async def get_cohort_comparison(
        self,
        customers: List[Dict],
        cohort_a: str,
        cohort_b: str
    ) -> Dict:
        """
        Compare two specific cohorts

        Args:
            customers: List of customer data
            cohort_a: First cohort identifier
            cohort_b: Second cohort identifier

        Returns:
            Comparison metrics
        """
        logger.info(f"[STATS] Comparing cohorts: {cohort_a} vs {cohort_b}")

        # Filter customers for each cohort
        customers_a = [c for c in customers if self._get_customer_cohort(c) == cohort_a]
        customers_b = [c for c in customers if self._get_customer_cohort(c) == cohort_b]

        # Calculate metrics for each
        metrics_a = await self._calculate_cohort_metrics(customers_a)
        metrics_b = await self._calculate_cohort_metrics(customers_b)

        comparison = {
            "cohort_a": {
                "cohort": cohort_a,
                **metrics_a
            },
            "cohort_b": {
                "cohort": cohort_b,
                **metrics_b
            },
            "differences": {
                "size_diff": metrics_a['size'] - metrics_b['size'],
                "avg_ltv_diff": metrics_a['avg_ltv'] - metrics_b['avg_ltv'],
                "retention_diff": metrics_a['retention_30d'] - metrics_b['retention_30d']
            }
        }

        return comparison

    def _get_customer_cohort(self, customer: Dict) -> str:
        """Get cohort identifier for customer"""
        acq_date = customer.get('acquisition_date')
        if not acq_date:
            return 'unknown'

        if isinstance(acq_date, str):
            acq_date = datetime.fromisoformat(acq_date.replace('Z', '+00:00')).date()

        return acq_date.strftime('%Y-%m')

    async def _calculate_cohort_metrics(self, customers: List[Dict]) -> Dict:
        """Calculate aggregate metrics for a cohort"""
        if not customers:
            return {
                "size": 0,
                "avg_ltv": 0,
                "retention_30d": 0
            }

        import statistics
        ltvs = [c.get('ltv', 0) for c in customers]

        # Calculate 30-day retention (simplified)
        # Count customers with at least 2 orders
        repeat_customers = sum(1 for c in customers if c.get('total_orders', 0) >= 2)

        return {
            "size": len(customers),
            "avg_ltv": round(statistics.mean(ltvs), 2) if ltvs else 0,
            "retention_30d": round((repeat_customers / len(customers)) * 100) if customers else 0
        }

    # ==================== Acquisition Source Cohorts ====================

    async def get_acquisition_source_cohorts(self, customers: List[Dict]) -> Dict:
        """
        Retention by acquisition source

        Args:
            customers: List of customer data

        Returns:
            Retention metrics by source
        """
        logger.info("[STATS] Analyzing retention by acquisition source...")

        # Group by source
        source_groups = defaultdict(list)

        for customer in customers:
            source = customer.get('acquisition_source', 'unknown')
            source_groups[source].append(customer)

        # Calculate retention for each source
        source_retention = {}

        for source, source_customers in source_groups.items():
            # Calculate repeat purchase rate
            repeat_customers = sum(1 for c in source_customers if c.get('total_orders', 0) >= 2)
            retention_rate = (repeat_customers / len(source_customers)) * 100 if source_customers else 0

            # Calculate average LTV
            import statistics
            ltvs = [c.get('ltv', 0) for c in source_customers]
            avg_ltv = statistics.mean(ltvs) if ltvs else 0

            source_retention[source] = {
                "total_customers": len(source_customers),
                "repeat_customers": repeat_customers,
                "retention_rate": round(retention_rate, 1),
                "avg_ltv": round(avg_ltv, 2)
            }

        return source_retention

    # ==================== Best Cohorts ====================

    async def identify_best_cohorts(self, customers: List[Dict]) -> Dict:
        """
        Identify which cohorts have best retention and LTV

        Args:
            customers: List of customer data

        Returns:
            Top performing cohorts
        """
        logger.info("[TOP] Identifying best performing cohorts...")

        # Get cohort data
        cohort_table = await self.get_cohort_table(customers, 'monthly', 12)
        cohort_ltv = await self.get_cohort_ltv(customers, 'monthly')

        # Find best by retention
        best_retention = None
        best_retention_score = 0

        for cohort in cohort_table['cohorts']:
            if len(cohort['retention']) > 2:
                avg_retention = sum(cohort['retention'][1:]) / len(cohort['retention'][1:])

                if avg_retention > best_retention_score:
                    best_retention_score = avg_retention
                    best_retention = cohort['cohort']

        # Find best by LTV
        best_ltv = None
        best_ltv_value = 0

        for cohort_key, ltv_data in cohort_ltv.items():
            if ltv_data['avg_ltv'] > best_ltv_value:
                best_ltv_value = ltv_data['avg_ltv']
                best_ltv = cohort_key

        result = {
            "best_retention": {
                "cohort": best_retention,
                "avg_retention": round(best_retention_score, 1)
            },
            "best_ltv": {
                "cohort": best_ltv,
                "avg_ltv": best_ltv_value
            }
        }

        return result


# Export singleton instance
_cohort_analyzer = None

def get_cohort_analyzer(db_session=None):
    """Get or create cohort analyzer instance"""
    global _cohort_analyzer
    if _cohort_analyzer is None:
        _cohort_analyzer = CohortAnalyzer(db_session)
    return _cohort_analyzer


logger.info("[SUCCESS] Cohort Analyzer module loaded")
