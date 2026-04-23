"""
Real-Time Product Momentum Updater

Background service that updates product momentum data every 5 minutes.
Fetches latest product data, calculates momentum, and caches results.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)


class RealtimeUpdater:
    """
    Background service for updating product momentum in real-time.

    Runs scheduled updates every 5 minutes to:
    - Fetch latest product data
    - Calculate momentum indicators
    - Update rankings and rank changes
    - Cache results for fast API responses
    """

    def __init__(self, update_interval: int = 300):
        """
        Initialize realtime updater.

        Args:
            update_interval: Update frequency in seconds (default: 300 = 5 minutes)
        """
        self.update_interval = update_interval
        self.is_running = False
        self.last_update = None
        self.cache = {
            'trending': [],
            'movers': [],
            'breakouts': [],
            'last_updated': None
        }
        self.previous_rankings = {}  # Track rank changes

    async def start(self):
        """Start the background updater task."""
        if self.is_running:
            logger.warning("Realtime updater already running")
            return

        self.is_running = True
        logger.info(f"[START] Starting realtime momentum updater (interval: {self.update_interval}s)")

        # Run initial update
        await self.update_momentum()

        # Schedule recurring updates
        while self.is_running:
            await asyncio.sleep(self.update_interval)
            await self.update_momentum()

    async def stop(self):
        """Stop the background updater task."""
        logger.info("Stopping realtime momentum updater")
        self.is_running = False

    async def update_momentum(self):
        """
        Fetch latest products and calculate momentum.

        This is the core update function that:
        1. Fetches latest product data
        2. Calculates momentum for each product
        3. Tracks rank changes from previous update
        4. Updates cache with new data
        """
        try:
            logger.info("[STATS] Updating product momentum...")

            from ospra_os.intelligence.momentum_tracker import get_momentum_tracker

            # Get product data from dashboard
            products_data = await self._fetch_products()

            if not products_data:
                logger.warning("No products data available for momentum update")
                return

            # Calculate momentum
            tracker = get_momentum_tracker()
            trending = await tracker.get_trending_products(
                products_data=products_data,
                limit=100,
                sort_by='velocity'
            )

            # Update rank changes based on previous rankings
            trending = self._update_rank_changes(trending)

            # Get insights
            movers_up = tracker.get_biggest_movers(trending, limit=10, direction='up')
            movers_down = tracker.get_biggest_movers(trending, limit=10, direction='down')
            breakouts = tracker.get_breakout_products(trending)
            falling = tracker.get_falling_products(trending, limit=10)

            # Update cache
            self.cache = {
                'trending': trending[:50],  # Top 50
                'movers_up': movers_up,
                'movers_down': movers_down,
                'breakouts': breakouts,
                'falling': falling,
                'last_updated': datetime.utcnow().isoformat() + 'Z',
                'total_products': len(trending)
            }

            self.last_update = datetime.utcnow()

            logger.info(
                f"[SUCCESS] Momentum updated: {len(trending)} products, "
                f"{len(breakouts)} breakouts, {len(movers_up)} movers up"
            )

        except Exception as e:
            logger.error(f"[ERROR] Momentum update failed: {e}")
            import traceback
            traceback.print_exc()

    async def _fetch_products(self) -> List[Dict]:
        """
        Fetch latest product data from discovery engine.

        Returns:
            List of product dictionaries
        """
        try:
            # Use the new unified discovery engine
            from ospra_os.intelligence.product_discovery import get_live_products

            products = await get_live_products(niche="smart_home", limit=100)
            logger.info(f"Fetched {len(products)} products from discovery engine")
            return products

        except Exception as e:
            logger.warning(f"Could not fetch from discovery engine: {e}")

            # Fallback: Generate mock data for testing
            logger.info("Using mock product data for momentum calculation")
            return self._generate_mock_products()

    def _generate_mock_products(self, count: int = 50) -> List[Dict]:
        """
        Generate mock product data for testing.

        Args:
            count: Number of mock products to generate

        Returns:
            List of mock product dictionaries
        """
        import random

        products = []
        niches = ['smart_home', 'fitness', 'beauty', 'tech', 'kitchen']

        for i in range(count):
            product = {
                'id': f'mock_prod_{i}',
                'name': f'Mock Product {i}',
                'niche': random.choice(niches),
                'trend_score': random.uniform(30, 95),
                'velocity_score': random.uniform(10, 90),
                'final_score': random.uniform(40, 98),
                'orders': random.randint(100, 10000),
                'price': round(random.uniform(9.99, 99.99), 2),
                'rating': round(random.uniform(3.5, 5.0), 1),
                'rank': i + 1
            }
            products.append(product)

        return products

    def _update_rank_changes(self, trending: List[Dict]) -> List[Dict]:
        """
        Update rank changes by comparing with previous rankings.

        Args:
            trending: List of products with current rankings

        Returns:
            Updated trending list with rank changes
        """
        current_rankings = {}

        for product in trending:
            product_id = product.get('product_id')
            current_rank = product.get('current_rank', 0)

            # Get previous rank
            previous_rank = self.previous_rankings.get(product_id, current_rank)

            # Calculate rank change (positive = moved up)
            rank_change = previous_rank - current_rank

            # Update product with previous rank and change
            product['previous_rank'] = previous_rank
            product['rank_change'] = rank_change

            # Store current rank for next update
            current_rankings[product_id] = current_rank

        # Update stored rankings
        self.previous_rankings = current_rankings

        return trending

    def get_cached_data(self, data_type: str = 'trending') -> Optional[Dict]:
        """
        Get cached momentum data.

        Args:
            data_type: Type of data to retrieve
                      ('trending', 'movers_up', 'movers_down', 'breakouts', 'falling')

        Returns:
            Cached data dictionary or None
        """
        if data_type == 'all':
            return self.cache

        return self.cache.get(data_type, [])

    def get_cache_age(self) -> Optional[int]:
        """
        Get age of cached data in seconds.

        Returns:
            Cache age in seconds, or None if no data cached
        """
        if not self.last_update:
            return None

        age = (datetime.utcnow() - self.last_update).total_seconds()
        return int(age)

    def is_cache_fresh(self, max_age: int = 300) -> bool:
        """
        Check if cache is still fresh.

        Args:
            max_age: Maximum acceptable cache age in seconds (default: 300 = 5 minutes)

        Returns:
            True if cache is fresh, False otherwise
        """
        age = self.get_cache_age()
        if age is None:
            return False

        return age < max_age


# Singleton instance
_realtime_updater = None

def get_realtime_updater() -> RealtimeUpdater:
    """Get or create realtime updater instance."""
    global _realtime_updater
    if _realtime_updater is None:
        _realtime_updater = RealtimeUpdater(update_interval=300)  # 5 minutes
    return _realtime_updater


async def start_realtime_updates():
    """
    Start the realtime momentum updater.

    Call this from your app startup event to begin background updates.
    """
    updater = get_realtime_updater()
    # Start as background task
    asyncio.create_task(updater.start())
    logger.info("[SUCCESS] Realtime momentum updater started")


async def stop_realtime_updates():
    """
    Stop the realtime momentum updater.

    Call this from your app shutdown event to cleanly stop updates.
    """
    updater = get_realtime_updater()
    await updater.stop()
    logger.info("[SUCCESS] Realtime momentum updater stopped")
