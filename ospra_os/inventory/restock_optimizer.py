"""
Restock Optimizer - Optimize restock timing and quantities

Calculates:
- Reorder point (when to reorder)
- Optimal order quantity (how much to order)
- Safety stock levels
- Total cost analysis
"""
from datetime import date, timedelta
from typing import Dict, List, Optional
import math


class RestockOptimizer:
    """Optimize restock timing and order quantities"""

    def __init__(self):
        # Typical holding cost as % of unit cost per year
        self.holding_cost_rate = 0.25  # 25% per year

        # Fixed cost per order (processing, shipping base)
        self.order_cost = 50.0

        # Z-score for service levels
        self.z_scores = {
            0.90: 1.28,
            0.95: 1.65,
            0.98: 1.96,
            0.99: 2.33
        }

    async def calculate_reorder_point(
        self,
        daily_velocity: float,
        lead_time_days: int,
        safety_stock: int
    ) -> Dict:
        """
        Calculate when to reorder

        Reorder Point = (Lead Time × Daily Velocity) + Safety Stock

        Args:
            daily_velocity: Average units sold per day
            lead_time_days: Days from order to arrival
            safety_stock: Buffer stock units

        Returns:
            {
                "reorder_point": 25,
                "components": {
                    "lead_time_demand": 15,
                    "safety_stock": 10
                },
                "explanation": "Reorder when stock falls to 25 units"
            }
        """
        lead_time_demand = daily_velocity * lead_time_days
        reorder_point = int(math.ceil(lead_time_demand + safety_stock))

        return {
            "reorder_point": reorder_point,
            "components": {
                "lead_time_demand": int(math.ceil(lead_time_demand)),
                "safety_stock": safety_stock
            },
            "explanation": f"Reorder when stock falls to {reorder_point} units"
        }

    async def calculate_safety_stock(
        self,
        daily_velocity: float,
        std_deviation: float,
        lead_time_days: int,
        service_level: float = 0.95
    ) -> Dict:
        """
        Calculate safety stock (buffer) using normal distribution

        Safety Stock = Z-score × StdDev × sqrt(Lead Time)

        Args:
            daily_velocity: Average units sold per day
            std_deviation: Standard deviation of daily sales
            lead_time_days: Supplier lead time in days
            service_level: Desired service level (0.90, 0.95, 0.98, 0.99)

        Returns:
            {
                "safety_stock": 15,
                "service_level": 0.95,
                "days_of_buffer": 4.7,
                "explanation": "15 units buffer for 95% service level"
            }
        """
        # Get Z-score for service level
        z_score = self.z_scores.get(service_level, 1.65)  # Default to 95%

        # Calculate safety stock
        safety_stock = z_score * std_deviation * math.sqrt(lead_time_days)
        safety_stock = int(math.ceil(safety_stock))

        # Calculate days of buffer
        days_of_buffer = safety_stock / daily_velocity if daily_velocity > 0 else 0

        return {
            "safety_stock": safety_stock,
            "service_level": service_level,
            "z_score": z_score,
            "days_of_buffer": round(days_of_buffer, 1),
            "explanation": f"{safety_stock} units buffer for {int(service_level*100)}% service level"
        }

    async def calculate_optimal_quantity(
        self,
        annual_demand: float,
        unit_cost: float,
        min_order_qty: int = 1,
        bulk_discounts: Optional[Dict[int, float]] = None
    ) -> Dict:
        """
        Calculate optimal order quantity using Economic Order Quantity (EOQ)

        EOQ = sqrt((2 × Annual Demand × Order Cost) / (Unit Cost × Holding Rate))

        Then adjust for:
        - Minimum order quantities
        - Bulk discounts
        - Storage constraints

        Args:
            annual_demand: Expected units per year
            unit_cost: Cost per unit
            min_order_qty: Minimum order quantity from supplier
            bulk_discounts: {100: 0.10, 200: 0.15} = 10% off at 100+, 15% off at 200+

        Returns:
            {
                "recommended_quantity": 100,
                "eoq": 85,
                "moq": 10,
                "bulk_discount_qty": 100,
                "discount_percentage": 10,
                "total_cost": 450,
                "reasoning": "Ordering 100 units for bulk discount (10% off)"
            }
        """
        if annual_demand <= 0 or unit_cost <= 0:
            return {
                "recommended_quantity": min_order_qty,
                "eoq": 0,
                "moq": min_order_qty,
                "reasoning": "Insufficient data for optimization"
            }

        # Calculate EOQ
        holding_cost_per_unit = unit_cost * self.holding_cost_rate
        eoq = math.sqrt(
            (2 * annual_demand * self.order_cost) / holding_cost_per_unit
        )
        eoq = int(math.ceil(eoq))

        # Start with EOQ
        recommended_qty = eoq
        reasoning = f"EOQ calculation suggests {eoq} units"

        # Adjust for minimum order quantity
        if recommended_qty < min_order_qty:
            recommended_qty = min_order_qty
            reasoning = f"Rounded up to MOQ of {min_order_qty} units"

        # Check bulk discounts
        best_discount = 0
        best_discount_qty = None
        best_total_cost = recommended_qty * unit_cost

        if bulk_discounts:
            for qty_threshold, discount_pct in sorted(bulk_discounts.items()):
                # Calculate cost at this discount level
                discounted_price = unit_cost * (1 - discount_pct)
                total_cost = qty_threshold * discounted_price

                # Only consider if it's actually cheaper per unit basis
                cost_per_unit_at_threshold = total_cost / qty_threshold
                current_cost_per_unit = best_total_cost / recommended_qty

                if cost_per_unit_at_threshold < current_cost_per_unit:
                    best_discount = discount_pct
                    best_discount_qty = qty_threshold
                    best_total_cost = total_cost
                    recommended_qty = qty_threshold
                    reasoning = f"Ordering {qty_threshold} units for bulk discount ({int(discount_pct*100)}% off)"

        return {
            "recommended_quantity": recommended_qty,
            "eoq": eoq,
            "moq": min_order_qty,
            "bulk_discount_qty": best_discount_qty,
            "discount_percentage": int(best_discount * 100) if best_discount > 0 else 0,
            "total_cost": round(best_total_cost, 2),
            "unit_cost": round(best_total_cost / recommended_qty, 2),
            "reasoning": reasoning
        }

    async def calculate_total_cost(
        self,
        quantity: int,
        unit_cost: float,
        shipping_cost: float = 0,
        customs_rate: float = 0,
        storage_cost_per_unit: float = 0
    ) -> Dict:
        """
        Calculate total cost breakdown for an order

        Args:
            quantity: Number of units
            unit_cost: Cost per unit
            shipping_cost: Total shipping cost
            customs_rate: Customs/duties as % of product cost
            storage_cost_per_unit: Monthly storage cost per unit

        Returns:
            {
                "product_cost": 450.00,
                "shipping_cost": 35.00,
                "customs_duties": 22.50,
                "storage_cost_projection": 12.00,
                "total_cost": 519.50,
                "cost_per_unit": 5.20,
                "breakdown": [...]
            }
        """
        product_cost = quantity * unit_cost
        customs_duties = product_cost * customs_rate

        # Estimate 2 months of storage
        storage_projection = quantity * storage_cost_per_unit * 2

        total_cost = product_cost + shipping_cost + customs_duties + storage_projection

        return {
            "product_cost": round(product_cost, 2),
            "shipping_cost": round(shipping_cost, 2),
            "customs_duties": round(customs_duties, 2),
            "storage_cost_projection": round(storage_projection, 2),
            "total_cost": round(total_cost, 2),
            "cost_per_unit": round(total_cost / quantity, 2) if quantity > 0 else 0,
            "breakdown": [
                {"item": "Product Cost", "amount": round(product_cost, 2)},
                {"item": "Shipping", "amount": round(shipping_cost, 2)},
                {"item": "Customs/Duties", "amount": round(customs_duties, 2)},
                {"item": "Storage (2 mo.)", "amount": round(storage_projection, 2)}
            ]
        }

    async def should_reorder_now(
        self,
        current_stock: int,
        reorder_point: int,
        incoming_stock: int = 0
    ) -> Dict:
        """
        Determine if we should reorder now

        Args:
            current_stock: Current available inventory
            reorder_point: Calculated reorder point
            incoming_stock: Stock already on order

        Returns:
            {
                "should_reorder": true,
                "urgency": "URGENT",  # NORMAL, SOON, URGENT, CRITICAL
                "days_until_reorder": -2,  # Negative = already below
                "reason": "Below reorder point by 5 units"
            }
        """
        # Effective stock = current + incoming
        effective_stock = current_stock + incoming_stock

        # Check if below reorder point
        if effective_stock <= reorder_point:
            units_below = reorder_point - effective_stock

            if effective_stock <= 0:
                urgency = "CRITICAL"
                reason = "OUT OF STOCK"
            elif units_below >= 20:
                urgency = "CRITICAL"
                reason = f"Below reorder point by {units_below} units"
            elif units_below >= 10:
                urgency = "URGENT"
                reason = f"Below reorder point by {units_below} units"
            else:
                urgency = "SOON"
                reason = f"At reorder point ({effective_stock} units)"

            return {
                "should_reorder": True,
                "urgency": urgency,
                "days_until_reorder": 0,
                "units_below_reorder": units_below,
                "reason": reason
            }

        # Calculate days until reorder point (estimate)
        units_above = effective_stock - reorder_point
        # Assume will need reorder in ~7-14 days
        if units_above < 10:
            urgency = "SOON"
            days = 3
        elif units_above < 30:
            urgency = "NORMAL"
            days = 7
        else:
            urgency = "NORMAL"
            days = 14

        return {
            "should_reorder": False,
            "urgency": urgency,
            "days_until_reorder": days,
            "units_above_reorder": units_above,
            "reason": f"Stock healthy ({units_above} units above reorder point)"
        }

    async def get_recommended_order_date(
        self,
        current_stock: int,
        daily_velocity: float,
        reorder_point: int,
        lead_time_days: int
    ) -> Dict:
        """
        Calculate when to place the order

        Args:
            current_stock: Current inventory level
            daily_velocity: Units sold per day
            reorder_point: When to reorder
            lead_time_days: Supplier lead time

        Returns:
            {
                "order_date": "2025-11-25",
                "days_from_now": 5,
                "arrival_date": "2025-12-02",
                "reasoning": "Order by Nov 25 to maintain buffer"
            }
        """
        if daily_velocity <= 0:
            return {
                "order_date": None,
                "days_from_now": None,
                "reasoning": "No velocity data available"
            }

        # Calculate days until we hit reorder point
        units_until_reorder = current_stock - reorder_point
        days_until_reorder = units_until_reorder / daily_velocity if daily_velocity > 0 else 999

        # We should order lead_time_days before we hit reorder point
        days_from_now = max(0, int(days_until_reorder - lead_time_days))

        today = date.today()
        order_date = today + timedelta(days=days_from_now)
        arrival_date = order_date + timedelta(days=lead_time_days)

        if days_from_now <= 0:
            reasoning = "ORDER NOW - At or below reorder point"
        elif days_from_now <= 3:
            reasoning = f"Order within {days_from_now} days to maintain buffer"
        else:
            reasoning = f"Order by {order_date.strftime('%b %d')} for on-time delivery"

        return {
            "order_date": order_date.isoformat(),
            "days_from_now": days_from_now,
            "arrival_date": arrival_date.isoformat(),
            "reasoning": reasoning
        }

    async def simulate_restock_scenarios(
        self,
        current_stock: int,
        daily_velocity: float,
        unit_cost: float,
        quantities: List[int]
    ) -> List[Dict]:
        """
        Compare different restock strategies

        Args:
            current_stock: Current inventory
            daily_velocity: Sales velocity
            unit_cost: Cost per unit
            quantities: List of quantities to compare [50, 100, 200]

        Returns:
            List of scenarios with cost analysis
        """
        scenarios = []

        for qty in quantities:
            # Calculate costs
            product_cost = qty * unit_cost
            shipping_est = 35 + (qty * 0.10)  # Base + per unit
            total_cost = product_cost + shipping_est

            # Calculate days of supply
            days_of_supply = (current_stock + qty) / daily_velocity if daily_velocity > 0 else 0

            # Calculate cost per day of supply
            cost_per_day = total_cost / days_of_supply if days_of_supply > 0 else 0

            scenarios.append({
                "quantity": qty,
                "total_cost": round(total_cost, 2),
                "cost_per_unit": round(total_cost / qty, 2),
                "days_of_supply": round(days_of_supply, 1),
                "cost_per_day": round(cost_per_day, 2),
                "new_stock_level": current_stock + qty
            })

        # Sort by cost efficiency (cost per day)
        scenarios.sort(key=lambda x: x["cost_per_day"])

        return scenarios
