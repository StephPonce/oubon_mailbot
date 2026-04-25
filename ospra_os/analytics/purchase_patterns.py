"""
Purchase Pattern Analyzer - Customer Buying Behavior Analysis

Analyzes customer purchase patterns to identify:
- Timing patterns: Day of week, hour of day, seasonal trends
- Product preferences: Categories, brands, price ranges
- Purchase frequency patterns
- Cart behavior: Average items, add-ons
- Discount sensitivity
- Cross-sell opportunities
- Product affinity (what products are bought together)
"""
from datetime import datetime, timedelta, date, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
import logging
import statistics
import calendar

logger = logging.getLogger(__name__)


class PurchasePatternAnalyzer:
    """Analyze customer purchase patterns and behaviors"""

    def __init__(self, db_session=None):
        """
        Initialize Purchase Pattern Analyzer

        Args:
            db_session: Database session for queries
        """
        self.db = db_session

    # ==================== Timing Patterns ====================

    async def analyze_timing_patterns(self, customer_id: str, orders: List[Dict]) -> Dict:
        """
        Analyze when customer prefers to shop

        Args:
            customer_id: Customer ID
            orders: List of order dictionaries

        Returns:
            Timing pattern analysis
        """
        logger.info(f"[ALARM] Analyzing timing patterns for: {customer_id}")

        if not orders:
            return {
                "preferred_day": None,
                "preferred_hour": None,
                "day_distribution": {},
                "hour_distribution": {},
                "seasonal_pattern": None
            }

        # Extract dates from orders
        order_dates = []
        for order in orders:
            order_date_str = order.get('date', '')
            if order_date_str:
                order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                order_dates.append(order_date)

        if not order_dates:
            return {
                "preferred_day": None,
                "preferred_hour": None,
                "day_distribution": {},
                "hour_distribution": {},
                "seasonal_pattern": None
            }

        # Day of week analysis (0=Monday, 6=Sunday)
        day_counts = Counter([d.weekday() for d in order_dates])
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_distribution = {day_names[day]: count for day, count in day_counts.items()}
        preferred_day = day_names[day_counts.most_common(1)[0][0]] if day_counts else None

        # Hour of day analysis
        hour_counts = Counter([d.hour for d in order_dates])
        hour_distribution = {f"{hour:02d}:00": count for hour, count in hour_counts.items()}
        preferred_hour = f"{hour_counts.most_common(1)[0][0]:02d}:00" if hour_counts else None

        # Seasonal analysis (Q1, Q2, Q3, Q4)
        quarter_counts = Counter([f"Q{(d.month - 1) // 3 + 1}" for d in order_dates])
        seasonal_pattern = quarter_counts.most_common(1)[0][0] if quarter_counts else None

        result = {
            "preferred_day": preferred_day,
            "preferred_hour": preferred_hour,
            "day_distribution": day_distribution,
            "hour_distribution": hour_distribution,
            "seasonal_pattern": seasonal_pattern,
            "total_orders": len(orders)
        }

        logger.info(f"[SUCCESS] Timing patterns: {preferred_day} at {preferred_hour}")

        return result

    async def get_global_timing_patterns(self, all_orders: List[Dict]) -> Dict:
        """
        Analyze global timing patterns across all customers

        Args:
            all_orders: All orders from all customers

        Returns:
            Global timing insights
        """
        logger.info("[STATS] Analyzing global timing patterns...")

        if not all_orders:
            return {"peak_days": [], "peak_hours": [], "seasonal_trends": {}}

        order_dates = []
        for order in all_orders:
            order_date_str = order.get('date', '')
            if order_date_str:
                order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                order_dates.append(order_date)

        if not order_dates:
            return {"peak_days": [], "peak_hours": [], "seasonal_trends": {}}

        # Peak days
        day_counts = Counter([d.weekday() for d in order_dates])
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        peak_days = [
            {"day": day_names[day], "orders": count}
            for day, count in day_counts.most_common(3)
        ]

        # Peak hours
        hour_counts = Counter([d.hour for d in order_dates])
        peak_hours = [
            {"hour": f"{hour:02d}:00", "orders": count}
            for hour, count in hour_counts.most_common(3)
        ]

        # Seasonal trends
        month_counts = Counter([d.strftime('%Y-%m') for d in order_dates])
        seasonal_trends = dict(month_counts.most_common(12))

        result = {
            "peak_days": peak_days,
            "peak_hours": peak_hours,
            "seasonal_trends": seasonal_trends
        }

        logger.info(f"[SUCCESS] Peak day: {peak_days[0]['day']}, Peak hour: {peak_hours[0]['hour']}")

        return result

    # ==================== Product Preferences ====================

    async def analyze_product_preferences(
        self,
        customer_id: str,
        orders: List[Dict]
    ) -> Dict:
        """
        Analyze customer's product preferences

        Args:
            customer_id: Customer ID
            orders: List of orders with line items

        Returns:
            Product preference analysis
        """
        logger.info(f"[SHOP] Analyzing product preferences for: {customer_id}")

        if not orders:
            return {
                "favorite_categories": [],
                "favorite_products": [],
                "price_range_preference": None,
                "brand_preferences": []
            }

        # Extract products from orders
        all_products = []
        all_categories = []
        all_prices = []
        all_brands = []

        for order in orders:
            items = order.get('items', [])
            for item in items:
                product_name = item.get('product_name', '')
                category = item.get('category', 'Uncategorized')
                price = item.get('price', 0)
                brand = item.get('brand', 'Unknown')

                if product_name:
                    all_products.append(product_name)
                    all_categories.append(category)
                    all_prices.append(price)
                    all_brands.append(brand)

        # Analyze categories
        category_counts = Counter(all_categories)
        favorite_categories = [
            {"category": cat, "purchases": count}
            for cat, count in category_counts.most_common(5)
        ]

        # Analyze products
        product_counts = Counter(all_products)
        favorite_products = [
            {"product": prod, "purchases": count}
            for prod, count in product_counts.most_common(5)
        ]

        # Analyze price range
        if all_prices:
            avg_price = statistics.mean(all_prices)
            if avg_price < 25:
                price_range = "Budget ($0-$25)"
            elif avg_price < 50:
                price_range = "Mid-range ($25-$50)"
            elif avg_price < 100:
                price_range = "Premium ($50-$100)"
            else:
                price_range = "Luxury ($100+)"
        else:
            price_range = None

        # Analyze brands
        brand_counts = Counter(all_brands)
        brand_preferences = [
            {"brand": brand, "purchases": count}
            for brand, count in brand_counts.most_common(5)
        ]

        result = {
            "favorite_categories": favorite_categories,
            "favorite_products": favorite_products,
            "price_range_preference": price_range,
            "brand_preferences": brand_preferences,
            "avg_item_price": round(statistics.mean(all_prices), 2) if all_prices else 0
        }

        logger.info(f"[SUCCESS] Top category: {favorite_categories[0]['category'] if favorite_categories else 'None'}")

        return result

    # ==================== Purchase Frequency Analysis ====================

    async def analyze_purchase_frequency(
        self,
        customer_id: str,
        orders: List[Dict]
    ) -> Dict:
        """
        Analyze how frequently customer purchases

        Args:
            customer_id: Customer ID
            orders: List of orders

        Returns:
            Frequency analysis
        """
        logger.info(f" Analyzing purchase frequency for: {customer_id}")

        if len(orders) < 2:
            return {
                "avg_days_between_orders": None,
                "frequency_trend": "insufficient_data",
                "predicted_next_order": None,
                "is_regular_buyer": False
            }

        # Sort orders by date
        sorted_orders = sorted(
            orders,
            key=lambda x: datetime.fromisoformat(x['date'].replace('Z', '+00:00'))
        )

        # Calculate days between orders
        order_dates = [
            datetime.fromisoformat(o['date'].replace('Z', '+00:00'))
            for o in sorted_orders
        ]
        gaps = [(order_dates[i+1] - order_dates[i]).days for i in range(len(order_dates)-1)]

        if not gaps:
            return {
                "avg_days_between_orders": None,
                "frequency_trend": "insufficient_data",
                "predicted_next_order": None,
                "is_regular_buyer": False
            }

        avg_gap = statistics.mean(gaps)

        # Determine trend (comparing recent vs overall)
        if len(gaps) >= 4:
            mid = len(gaps) // 2
            recent_avg = statistics.mean(gaps[mid:])
            overall_avg = statistics.mean(gaps[:mid])

            if recent_avg < overall_avg * 0.8:
                trend = "increasing"
            elif recent_avg > overall_avg * 1.2:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Predict next order
        last_order_date = order_dates[-1]
        predicted_next = last_order_date + timedelta(days=int(avg_gap))

        # Determine if regular buyer (consistent frequency)
        if len(gaps) >= 3:
            std_dev = statistics.stdev(gaps)
            coefficient_of_variation = std_dev / avg_gap
            is_regular = coefficient_of_variation < 0.5  # Low variation = regular
        else:
            is_regular = False

        result = {
            "avg_days_between_orders": round(avg_gap, 1),
            "frequency_trend": trend,
            "predicted_next_order": predicted_next.date().isoformat(),
            "is_regular_buyer": is_regular,
            "total_orders": len(orders),
            "order_gaps": [round(g, 1) for g in gaps]
        }

        logger.info(f"[SUCCESS] Avg frequency: {avg_gap:.1f} days, Trend: {trend}")

        return result

    # ==================== Cart Behavior ====================

    async def analyze_cart_behavior(
        self,
        customer_id: str,
        orders: List[Dict]
    ) -> Dict:
        """
        Analyze shopping cart patterns

        Args:
            customer_id: Customer ID
            orders: List of orders

        Returns:
            Cart behavior analysis
        """
        logger.info(f"[CART] Analyzing cart behavior for: {customer_id}")

        if not orders:
            return {
                "avg_items_per_order": 0,
                "avg_order_value": 0,
                "prefers_bulk_buying": False,
                "cart_value_trend": "stable"
            }

        # Calculate items per order
        items_per_order = []
        order_values = []

        for order in orders:
            items = order.get('items', [])
            total = order.get('total', 0)

            items_per_order.append(len(items))
            order_values.append(total)

        avg_items = statistics.mean(items_per_order) if items_per_order else 0
        avg_value = statistics.mean(order_values) if order_values else 0

        # Determine bulk buying preference
        prefers_bulk = avg_items >= 5

        # Analyze cart value trend
        if len(order_values) >= 4:
            mid = len(order_values) // 2
            recent_avg = statistics.mean(order_values[mid:])
            earlier_avg = statistics.mean(order_values[:mid])

            if recent_avg > earlier_avg * 1.15:
                trend = "increasing"
            elif recent_avg < earlier_avg * 0.85:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        result = {
            "avg_items_per_order": round(avg_items, 1),
            "avg_order_value": round(avg_value, 2),
            "prefers_bulk_buying": prefers_bulk,
            "cart_value_trend": trend,
            "min_order_value": round(min(order_values), 2) if order_values else 0,
            "max_order_value": round(max(order_values), 2) if order_values else 0
        }

        logger.info(f"[SUCCESS] Avg items: {avg_items:.1f}, Avg value: ${avg_value:.2f}")

        return result

    # ==================== Discount Sensitivity ====================

    async def analyze_discount_sensitivity(
        self,
        customer_id: str,
        orders: List[Dict]
    ) -> Dict:
        """
        Analyze customer's response to discounts

        Args:
            customer_id: Customer ID
            orders: List of orders

        Returns:
            Discount sensitivity analysis
        """
        logger.info(f"[PRICE] Analyzing discount sensitivity for: {customer_id}")

        if not orders:
            return {
                "discount_usage_rate": 0,
                "avg_discount_value": 0,
                "sensitivity_level": "unknown"
            }

        # Analyze discount usage
        orders_with_discount = 0
        discount_values = []

        for order in orders:
            discount = order.get('discount_amount', 0)
            if discount > 0:
                orders_with_discount += 1
                discount_values.append(discount)

        usage_rate = (orders_with_discount / len(orders)) * 100 if orders else 0
        avg_discount = statistics.mean(discount_values) if discount_values else 0

        # Determine sensitivity level
        if usage_rate >= 70:
            sensitivity = "high"
        elif usage_rate >= 40:
            sensitivity = "medium"
        elif usage_rate >= 10:
            sensitivity = "low"
        else:
            sensitivity = "very_low"

        result = {
            "discount_usage_rate": round(usage_rate, 1),
            "avg_discount_value": round(avg_discount, 2),
            "sensitivity_level": sensitivity,
            "total_discount_orders": orders_with_discount,
            "total_orders": len(orders)
        }

        logger.info(f"[SUCCESS] Discount usage: {usage_rate:.1f}%, Sensitivity: {sensitivity}")

        return result

    # ==================== Cross-Sell Opportunities ====================

    async def identify_cross_sell_opportunities(
        self,
        customer_id: str,
        orders: List[Dict],
        all_customers: List[Dict]
    ) -> List[Dict]:
        """
        Identify products this customer might be interested in
        based on similar customers' purchases

        Args:
            customer_id: Customer ID
            orders: Customer's orders
            all_customers: All customer data for comparison

        Returns:
            List of recommended products
        """
        logger.info(f"[TARGET] Identifying cross-sell opportunities for: {customer_id}")

        # Extract customer's purchased products
        purchased_products = set()
        purchased_categories = set()

        for order in orders:
            items = order.get('items', [])
            for item in items:
                product_name = item.get('product_name', '')
                category = item.get('category', '')
                if product_name:
                    purchased_products.add(product_name)
                if category:
                    purchased_categories.add(category)

        # Find similar customers (same categories)
        similar_customer_products = Counter()

        for other_customer in all_customers:
            if other_customer.get('customer_id') == customer_id:
                continue

            other_orders = other_customer.get('orders', [])
            other_categories = set()

            for order in other_orders:
                items = order.get('items', [])
                for item in items:
                    cat = item.get('category', '')
                    if cat:
                        other_categories.add(cat)

            # If customer shares categories, count their products
            overlap = purchased_categories & other_categories
            if len(overlap) >= 1:  # At least 1 shared category
                for order in other_orders:
                    items = order.get('items', [])
                    for item in items:
                        product = item.get('product_name', '')
                        if product and product not in purchased_products:
                            similar_customer_products[product] += 1

        # Return top recommendations
        recommendations = [
            {
                "product": product,
                "purchased_by_similar_customers": count,
                "recommendation_score": count  # Simple scoring
            }
            for product, count in similar_customer_products.most_common(10)
        ]

        logger.info(f"[SUCCESS] Found {len(recommendations)} cross-sell opportunities")

        return recommendations

    # ==================== Product Affinity Analysis ====================

    async def analyze_product_affinity(self, all_orders: List[Dict]) -> Dict:
        """
        Analyze which products are frequently bought together

        Args:
            all_orders: All orders from all customers

        Returns:
            Product affinity matrix
        """
        logger.info("[LINK] Analyzing product affinity...")

        # Build co-purchase matrix
        product_pairs = Counter()

        for order in all_orders:
            items = order.get('items', [])
            products = [item.get('product_name', '') for item in items if item.get('product_name')]

            # Count all pairs in this order
            for i, prod1 in enumerate(products):
                for prod2 in products[i+1:]:
                    pair = tuple(sorted([prod1, prod2]))
                    product_pairs[pair] += 1

        # Convert to readable format
        affinity_pairs = [
            {
                "product_a": pair[0],
                "product_b": pair[1],
                "times_bought_together": count,
                "affinity_score": count  # Could be enhanced with more sophisticated scoring
            }
            for pair, count in product_pairs.most_common(20)
        ]

        logger.info(f"[SUCCESS] Found {len(affinity_pairs)} product affinity pairs")

        return {
            "top_pairs": affinity_pairs,
            "total_pairs_analyzed": len(product_pairs)
        }

    # ==================== Category Flow Analysis ====================

    async def analyze_category_flow(
        self,
        customer_id: str,
        orders: List[Dict]
    ) -> Dict:
        """
        Analyze how customer moves between product categories over time

        Args:
            customer_id: Customer ID
            orders: List of orders

        Returns:
            Category flow analysis
        """
        logger.info(f"[STATS] Analyzing category flow for: {customer_id}")

        if len(orders) < 2:
            return {
                "category_journey": [],
                "category_loyalty": None,
                "exploration_rate": 0
            }

        # Sort orders by date
        sorted_orders = sorted(
            orders,
            key=lambda x: datetime.fromisoformat(x['date'].replace('Z', '+00:00'))
        )

        # Track categories per order
        category_journey = []
        all_categories = set()

        for order in sorted_orders:
            items = order.get('items', [])
            categories = set()

            for item in items:
                cat = item.get('category', 'Uncategorized')
                categories.add(cat)
                all_categories.add(cat)

            if categories:
                category_journey.append({
                    "order_date": order.get('date', ''),
                    "categories": list(categories)
                })

        # Calculate category loyalty (same category repeat rate)
        if len(category_journey) >= 2:
            repeat_category_orders = 0
            for i in range(len(category_journey) - 1):
                current_cats = set(category_journey[i]['categories'])
                next_cats = set(category_journey[i + 1]['categories'])

                if current_cats & next_cats:  # Any overlap
                    repeat_category_orders += 1

            loyalty_rate = (repeat_category_orders / (len(category_journey) - 1)) * 100
        else:
            loyalty_rate = 0

        # Calculate exploration rate (new categories per order)
        exploration_rate = len(all_categories) / len(orders) if orders else 0

        result = {
            "category_journey": category_journey,
            "category_loyalty": round(loyalty_rate, 1),
            "exploration_rate": round(exploration_rate, 2),
            "total_unique_categories": len(all_categories)
        }

        logger.info(f"[SUCCESS] Category loyalty: {loyalty_rate:.1f}%, Exploration: {exploration_rate:.2f}")

        return result

    # ==================== Complete Pattern Profile ====================

    async def get_complete_pattern_profile(
        self,
        customer_id: str,
        customer_data: Dict,
        all_customers: List[Dict] = None
    ) -> Dict:
        """
        Get complete purchase pattern profile for customer

        Args:
            customer_id: Customer ID
            customer_data: Customer profile with orders
            all_customers: All customers for cross-sell analysis

        Returns:
            Complete pattern analysis
        """
        logger.info(f"[STATS] Building complete pattern profile for: {customer_id}")

        orders = customer_data.get('orders', [])

        # Run all analyses
        timing = await self.analyze_timing_patterns(customer_id, orders)
        products = await self.analyze_product_preferences(customer_id, orders)
        frequency = await self.analyze_purchase_frequency(customer_id, orders)
        cart = await self.analyze_cart_behavior(customer_id, orders)
        discounts = await self.analyze_discount_sensitivity(customer_id, orders)
        category_flow = await self.analyze_category_flow(customer_id, orders)

        # Cross-sell only if all customers data provided
        cross_sell = []
        if all_customers:
            cross_sell = await self.identify_cross_sell_opportunities(
                customer_id,
                orders,
                all_customers
            )

        result = {
            "customer_id": customer_id,
            "timing_patterns": timing,
            "product_preferences": products,
            "purchase_frequency": frequency,
            "cart_behavior": cart,
            "discount_sensitivity": discounts,
            "category_flow": category_flow,
            "cross_sell_opportunities": cross_sell,
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"[SUCCESS] Complete pattern profile generated")

        return result


# Export singleton instance
_purchase_pattern_analyzer = None

def get_purchase_pattern_analyzer(db_session=None):
    """Get or create purchase pattern analyzer instance"""
    global _purchase_pattern_analyzer
    if _purchase_pattern_analyzer is None:
        _purchase_pattern_analyzer = PurchasePatternAnalyzer(db_session)
    return _purchase_pattern_analyzer


logger.info("[SUCCESS] Purchase Pattern Analyzer module loaded")
