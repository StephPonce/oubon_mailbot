"""
Trend Velocity Detector - Catch Rising Products EARLY

This detector identifies products that are:
1. Rising FAST (early spike detection)
2. Sustained growth (not just a flash in the pan)
3. About to decay (warnings before trends die)

WHY THIS MATTERS:
- Catch products at 20% trend growth = early mover advantage
- Avoid saturated products at 100% = too late
- Get warnings when trends start declining
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class TrendVelocityDetector:
    """
    Detects how FAST a product is trending (not just how much)

    Velocity = Rate of change over time
    """

    def __init__(self):
        self.trend_history = defaultdict(list)  # product_id -> [(date, score)]

    async def track_product(self, product_id: str, trend_score: float, timestamp: Optional[datetime] = None):
        """
        Track a product's trend score over time

        Args:
            product_id: Unique product identifier
            trend_score: Current trend score (0-100)
            timestamp: When this score was recorded
        """
        if timestamp is None:
            timestamp = datetime.now()

        self.trend_history[product_id].append({
            'timestamp': timestamp,
            'score': trend_score
        })

        # Keep only last 30 days
        cutoff = datetime.now() - timedelta(days=30)
        self.trend_history[product_id] = [
            entry for entry in self.trend_history[product_id]
            if entry['timestamp'] > cutoff
        ]

    async def calculate_velocity(self, product_id: str) -> Dict:
        """
        Calculate trend velocity for a product

        Returns:
            {
                'current_score': float,
                'velocity': float,  # Rate of change per day
                'acceleration': float,  # Is velocity increasing?
                'status': str,  # 'early_spike', 'sustained_growth', 'peak', 'declining'
                'days_tracked': int,
                'confidence': float  # How confident we are (more data = higher)
            }
        """
        history = self.trend_history.get(product_id, [])

        if len(history) < 2:
            return {
                'current_score': history[0]['score'] if history else 0,
                'velocity': 0.0,
                'acceleration': 0.0,
                'status': 'insufficient_data',
                'days_tracked': len(history),
                'confidence': 0.0
            }

        # Sort by timestamp
        history = sorted(history, key=lambda x: x['timestamp'])

        # Calculate velocity (change per day)
        first = history[0]
        last = history[-1]
        days_elapsed = (last['timestamp'] - first['timestamp']).days

        if days_elapsed == 0:
            days_elapsed = 1  # Prevent division by zero

        score_change = last['score'] - first['score']
        velocity = score_change / days_elapsed

        # Calculate acceleration (is velocity increasing?)
        if len(history) >= 4:
            # Compare first half vs second half velocity
            mid = len(history) // 2
            first_half = history[:mid]
            second_half = history[mid:]

            first_velocity = (first_half[-1]['score'] - first_half[0]['score']) / max(1, (first_half[-1]['timestamp'] - first_half[0]['timestamp']).days)
            second_velocity = (second_half[-1]['score'] - second_half[0]['score']) / max(1, (second_half[-1]['timestamp'] - second_half[0]['timestamp']).days)

            acceleration = second_velocity - first_velocity
        else:
            acceleration = 0.0

        # Determine status
        status = self._determine_status(velocity, acceleration, last['score'])

        # Confidence based on data points
        confidence = min(1.0, len(history) / 7.0)  # Full confidence after 7 days

        return {
            'current_score': last['score'],
            'velocity': round(velocity, 2),
            'acceleration': round(acceleration, 2),
            'status': status,
            'days_tracked': days_elapsed,
            'confidence': round(confidence, 2)
        }

    def _determine_status(self, velocity: float, acceleration: float, current_score: float) -> str:
        """
        Determine product trend status

        Statuses:
        - early_spike: Rising fast, still low score (CATCH THIS!)
        - sustained_growth: Steady positive velocity
        - peak: High score, slowing velocity
        - declining: Negative velocity
        - stable: Near-zero velocity
        """
        # EARLY SPIKE: Fast rise, not yet saturated
        if velocity > 3.0 and current_score < 60:
            return 'early_spike'  # [TARGET] PRIME TIME TO SELL

        # SUSTAINED GROWTH: Steady rise
        if velocity > 1.0 and acceleration >= 0:
            return 'sustained_growth'  # [SUCCESS] Still good

        # PEAK: High score but slowing
        if current_score > 80 and velocity < 1.0:
            return 'peak'  # [WARNING] Might be too late

        # DECLINING: Negative velocity
        if velocity < -1.0:
            return 'declining'  # [ERROR] Trend is dying

        # STABLE: Not much change
        return 'stable'  #  Watch and wait

    async def get_early_opportunities(self, min_velocity: float = 3.0, max_score: float = 60) -> List[Dict]:
        """
        Get products showing EARLY SPIKE signals

        These are products rising fast but not yet saturated
        = Best opportunity for early movers

        Args:
            min_velocity: Minimum rate of change per day
            max_score: Maximum current score (avoid saturated products)

        Returns:
            List of products sorted by opportunity score
        """
        opportunities = []

        for product_id, history in self.trend_history.items():
            if len(history) < 2:
                continue

            velocity_data = await self.calculate_velocity(product_id)

            if (velocity_data['velocity'] >= min_velocity and
                velocity_data['current_score'] <= max_score and
                velocity_data['confidence'] >= 0.5):

                # Calculate opportunity score
                # Higher velocity + lower current score = better opportunity
                opportunity_score = (
                    velocity_data['velocity'] * 10 +  # Fast rise is good
                    (100 - velocity_data['current_score']) * 0.5 +  # Lower saturation is good
                    velocity_data['acceleration'] * 5  # Accelerating is very good
                )

                opportunities.append({
                    'product_id': product_id,
                    'opportunity_score': round(opportunity_score, 1),
                    **velocity_data
                })

        # Sort by opportunity score
        opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)

        logger.info(f"[TARGET] Found {len(opportunities)} early spike opportunities")

        return opportunities

    async def get_declining_products(self, min_velocity: float = -2.0) -> List[Dict]:
        """
        Get products with declining trends

        These should be removed from store or given lower priority

        Args:
            min_velocity: Maximum negative velocity (more negative = faster decline)

        Returns:
            List of declining products
        """
        declining = []

        for product_id, history in self.trend_history.items():
            if len(history) < 2:
                continue

            velocity_data = await self.calculate_velocity(product_id)

            if velocity_data['velocity'] <= min_velocity:
                declining.append({
                    'product_id': product_id,
                    **velocity_data
                })

        # Sort by velocity (most negative first)
        declining.sort(key=lambda x: x['velocity'])

        logger.warning(f"[WARNING] Found {len(declining)} declining products")

        return declining

    async def get_velocity_report(self) -> Dict:
        """
        Generate complete velocity report for dashboard

        Returns:
            {
                'summary': {...},
                'early_opportunities': [...],
                'declining_products': [...],
                'sustained_growth': [...],
                'peaked_products': [...]
            }
        """
        all_products = []

        for product_id in self.trend_history.keys():
            velocity_data = await self.calculate_velocity(product_id)
            if velocity_data['status'] != 'insufficient_data':
                all_products.append({
                    'product_id': product_id,
                    **velocity_data
                })

        # Categorize by status
        categorized = defaultdict(list)
        for product in all_products:
            categorized[product['status']].append(product)

        return {
            'summary': {
                'total_tracked': len(self.trend_history),
                'with_velocity_data': len(all_products),
                'early_opportunities': len(categorized['early_spike']),
                'sustained_growth': len(categorized['sustained_growth']),
                'declining': len(categorized['declining']),
                'peaked': len(categorized['peak'])
            },
            'early_opportunities': sorted(
                categorized['early_spike'],
                key=lambda x: x['velocity'],
                reverse=True
            )[:10],  # Top 10
            'declining_products': sorted(
                categorized['declining'],
                key=lambda x: x['velocity']
            )[:10],  # Most declining
            'sustained_growth': categorized['sustained_growth'][:10],
            'peaked_products': categorized['peak'][:10]
        }


async def demo_velocity_tracking():
    """
    DEMO: Show how velocity detection works
    """
    detector = TrendVelocityDetector()

    # Simulate product rising over 7 days
    product_id = "smart-led-strip"

    logger.info("[STATS] Simulating 7-day trend growth...")

    # Day 1-3: Slow start
    await detector.track_product(product_id, 20, datetime.now() - timedelta(days=7))
    await detector.track_product(product_id, 25, datetime.now() - timedelta(days=6))
    await detector.track_product(product_id, 28, datetime.now() - timedelta(days=5))

    # Day 4-6: SPIKE (this is the signal!)
    await detector.track_product(product_id, 35, datetime.now() - timedelta(days=4))
    await detector.track_product(product_id, 48, datetime.now() - timedelta(days=3))
    await detector.track_product(product_id, 55, datetime.now() - timedelta(days=2))

    # Day 7: Current
    await detector.track_product(product_id, 58, datetime.now())

    # Calculate velocity
    velocity = await detector.calculate_velocity(product_id)

    logger.info(f"[SUCCESS] Velocity Analysis:")
    logger.info(f"   Current Score: {velocity['current_score']}")
    logger.info(f"   Velocity: {velocity['velocity']}/day")
    logger.info(f"   Status: {velocity['status']}")
    logger.info(f"   Confidence: {velocity['confidence']:.0%}")

    # Get opportunities
    opportunities = await detector.get_early_opportunities()

    if opportunities:
        logger.info(f"\n[TARGET] Early Opportunity Detected!")
        logger.info(f"   Opportunity Score: {opportunities[0]['opportunity_score']}")

    return velocity
