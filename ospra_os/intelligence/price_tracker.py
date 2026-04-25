"""
Price Tracker - Monitor competitor prices over time

Tracks historical prices, detects changes, identifies trends,
and finds pricing opportunities.

Author: OspraOS
Date: November 2025
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
import statistics

logger = logging.getLogger(__name__)


class PriceTracker:
    """Tracks competitor prices and detects changes and opportunities"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def record_price(
        self,
        product_id: str,
        price: float,
        competitor_id: str,
        original_price: Optional[float] = None,
        in_stock: bool = True
    ) -> dict:
        """
        Record current price snapshot for a competitor product

        Args:
            product_id: Competitor product ID
            price: Current price
            competitor_id: Competitor ID
            original_price: Compare-at price (if on sale)
            in_stock: Stock status

        Returns:
            Price snapshot dict
        """
        from ospra_os.models.competitor import CompetitorPriceHistory

        # Calculate discount if applicable
        discount_percent = 0
        if original_price and original_price > price:
            discount_percent = ((original_price - price) / original_price) * 100

        # Create price history record
        price_snapshot = CompetitorPriceHistory(
            product_id=product_id,
            competitor_id=competitor_id,
            price=price,
            original_price=original_price,
            discount_percent=round(discount_percent, 2),
            in_stock=in_stock,
            recorded_at=datetime.now(timezone.utc)
        )

        self.db.add(price_snapshot)
        await self.db.commit()

        logger.info(f"Recorded price for {product_id}: ${price}")

        return {
            'product_id': product_id,
            'price': price,
            'original_price': original_price,
            'discount_percent': discount_percent,
            'in_stock': in_stock,
            'recorded_at': price_snapshot.recorded_at.isoformat()
        }

    async def get_price_history(
        self,
        product_id: str,
        days: int = 90
    ) -> List[dict]:
        """
        Get historical prices for a product

        Args:
            product_id: Competitor product ID
            days: Number of days of history

        Returns:
            List of price snapshots ordered by date
        """
        from ospra_os.models.competitor import CompetitorPriceHistory

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = select(CompetitorPriceHistory).where(
            and_(
                CompetitorPriceHistory.product_id == product_id,
                CompetitorPriceHistory.recorded_at >= cutoff_date
            )
        ).order_by(CompetitorPriceHistory.recorded_at)

        result = await self.db.execute(query)
        history = result.scalars().all()

        return [
            {
                'price': record.price,
                'original_price': record.original_price,
                'discount_percent': record.discount_percent,
                'in_stock': record.in_stock,
                'recorded_at': record.recorded_at.isoformat()
            }
            for record in history
        ]

    async def detect_price_change(self, product_id: str) -> Optional[dict]:
        """
        Compare current price to last recorded price

        Args:
            product_id: Competitor product ID

        Returns:
            Price change dict or None if no change/no history
        """
        from ospra_os.models.competitor import CompetitorPriceHistory, CompetitorProduct

        # Get last two price records
        query = select(CompetitorPriceHistory).where(
            CompetitorPriceHistory.product_id == product_id
        ).order_by(desc(CompetitorPriceHistory.recorded_at)).limit(2)

        result = await self.db.execute(query)
        records = result.scalars().all()

        if len(records) < 2:
            return None

        current = records[0]
        previous = records[1]

        if current.price == previous.price:
            return None  # No change

        change_amount = current.price - previous.price
        change_percent = (change_amount / previous.price) * 100
        direction = 'increased' if change_amount > 0 else 'decreased'

        # Get product name
        product_query = select(CompetitorProduct).where(
            CompetitorProduct.product_id == product_id
        )
        product_result = await self.db.execute(product_query)
        product = product_result.scalar_one_or_none()

        return {
            'product_id': product_id,
            'product_name': product.name if product else None,
            'changed': True,
            'direction': direction,
            'old_price': previous.price,
            'new_price': current.price,
            'change_amount': round(change_amount, 2),
            'change_percent': round(change_percent, 2),
            'changed_at': current.recorded_at.isoformat()
        }

    async def get_all_price_changes(
        self,
        hours: int = 24,
        min_change_percent: float = 5.0
    ) -> List[dict]:
        """
        Get all significant price changes in time period

        Args:
            hours: Look back period in hours
            min_change_percent: Minimum change percentage to report

        Returns:
            List of price change dicts
        """
        from ospra_os.models.competitor import CompetitorProduct

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Get products with recent price changes
        query = select(CompetitorProduct).where(
            and_(
                CompetitorProduct.last_price_change >= cutoff_time,
                CompetitorProduct.price_drop_percent >= min_change_percent
            )
        ).order_by(desc(CompetitorProduct.price_drop_percent))

        result = await self.db.execute(query)
        products = result.scalars().all()

        changes = []
        for product in products:
            # Get the actual price change details
            change = await self.detect_price_change(product.product_id)
            if change and abs(change['change_percent']) >= min_change_percent:
                changes.append(change)

        return changes

    async def get_price_trends(self, product_id: str, days: int = 30) -> dict:
        """
        Analyze price trends for a product

        Args:
            product_id: Competitor product ID
            days: Analysis period in days

        Returns:
            Trend analysis dict
        """
        history = await self.get_price_history(product_id, days)

        if len(history) < 2:
            return {
                'product_id': product_id,
                'trend': 'insufficient_data',
                'data_points': len(history)
            }

        prices = [h['price'] for h in history]

        # Calculate statistics
        avg_price = statistics.mean(prices)
        min_price = min(prices)
        max_price = max(prices)
        current_price = prices[-1]
        first_price = prices[0]

        # Determine trend
        price_change = current_price - first_price
        price_change_percent = (price_change / first_price) * 100

        if price_change_percent > 5:
            trend = 'increasing'
        elif price_change_percent < -5:
            trend = 'decreasing'
        else:
            trend = 'stable'

        # Calculate volatility (standard deviation as percentage of mean)
        std_dev = statistics.stdev(prices) if len(prices) > 1 else 0
        volatility_percent = (std_dev / avg_price) * 100

        if volatility_percent > 15:
            volatility = 'HIGH'
        elif volatility_percent > 5:
            volatility = 'MEDIUM'
        else:
            volatility = 'LOW'

        return {
            'product_id': product_id,
            'trend': trend,
            'current_price': current_price,
            'avg_price': round(avg_price, 2),
            'min_price': min_price,
            'max_price': max_price,
            'price_range': max_price - min_price,
            'volatility': volatility,
            'volatility_percent': round(volatility_percent, 2),
            'change_percent': round(price_change_percent, 2),
            'data_points': len(history),
            'analysis_days': days
        }

    async def compare_to_our_price(self, competitor_product_id: str) -> Optional[dict]:
        """
        Compare competitor price to our matching product price

        Args:
            competitor_product_id: Competitor product ID

        Returns:
            Price comparison dict or None if no match
        """
        from ospra_os.models.competitor import CompetitorProduct

        query = select(CompetitorProduct).where(
            CompetitorProduct.product_id == competitor_product_id
        )

        result = await self.db.execute(query)
        product = result.scalar_one_or_none()

        if not product or not product.our_product_id or not product.our_price:
            return None

        price_diff = product.our_price - product.current_price
        price_diff_percent = (price_diff / product.current_price) * 100

        if price_diff > 0:
            we_are = 'HIGHER'
            recommendation = 'Consider price reduction to match competitor'
        elif price_diff < 0:
            we_are = 'LOWER'
            recommendation = 'We are competitively priced - could potentially raise'
        else:
            we_are = 'SAME'
            recommendation = 'Prices are matched'

        return {
            'our_product_id': product.our_product_id,
            'our_product_name': product.our_product_name,
            'our_price': product.our_price,
            'competitor_product_id': product.product_id,
            'competitor_product_name': product.name,
            'competitor_price': product.current_price,
            'competitor_id': product.competitor_id,
            'price_difference': round(price_diff, 2),
            'difference_percent': round(price_diff_percent, 2),
            'we_are': we_are,
            'recommendation': recommendation
        }

    async def get_pricing_opportunities(self, threshold_percent: float = 10.0) -> List[dict]:
        """
        Find products where price adjustments could be beneficial

        Args:
            threshold_percent: Significant price difference threshold

        Returns:
            List of pricing opportunities
        """
        from ospra_os.models.competitor import CompetitorProduct

        # Get products with our product matches
        query = select(CompetitorProduct).where(
            CompetitorProduct.our_product_id.isnot(None)
        )

        result = await self.db.execute(query)
        products = result.scalars().all()

        opportunities = []

        for product in products:
            if not product.our_price or not product.current_price:
                continue

            comparison = await self.compare_to_our_price(product.product_id)
            if not comparison:
                continue

            diff_percent = abs(comparison['difference_percent'])

            # Significant price difference
            if diff_percent >= threshold_percent:
                opportunity_type = None
                action = None

                if comparison['we_are'] == 'HIGHER':
                    opportunity_type = 'PRICE_REDUCTION'
                    action = 'Consider lowering price to match competitor'
                elif comparison['we_are'] == 'LOWER':
                    opportunity_type = 'PRICE_INCREASE'
                    action = 'We are significantly cheaper - could raise price'

                if opportunity_type:
                    opportunities.append({
                        **comparison,
                        'opportunity_type': opportunity_type,
                        'action': action,
                        'potential_impact': diff_percent
                    })

        # Sort by potential impact
        opportunities.sort(key=lambda x: x['potential_impact'], reverse=True)

        return opportunities

    async def calculate_price_index(self, niche: str) -> float:
        """
        Calculate our price positioning vs market average

        Args:
            niche: Product niche to analyze

        Returns:
            Price index (1.0 = at market, <1.0 = below, >1.0 = above)
        """
        from ospra_os.models.competitor import CompetitorProduct, Competitor

        # Get competitor products in this niche with our matches
        query = select(CompetitorProduct, Competitor).join(
            Competitor,
            CompetitorProduct.competitor_id == Competitor.competitor_id
        ).where(
            and_(
                CompetitorProduct.our_product_id.isnot(None),
                Competitor.primary_niches.contains([niche])
            )
        )

        result = await self.db.execute(query)
        products = result.all()

        if not products:
            return 1.0

        our_prices = []
        market_prices = []

        for product_row in products:
            product = product_row[0]
            if product.our_price and product.current_price:
                our_prices.append(product.our_price)
                market_prices.append(product.current_price)

        if not our_prices or not market_prices:
            return 1.0

        avg_our_price = statistics.mean(our_prices)
        avg_market_price = statistics.mean(market_prices)

        # Price index: our_avg / market_avg
        price_index = avg_our_price / avg_market_price

        return round(price_index, 3)

    async def get_price_drop_alerts(
        self,
        min_drop_percent: float = 15.0,
        hours: int = 24
    ) -> List[dict]:
        """
        Get alerts for significant competitor price drops

        Args:
            min_drop_percent: Minimum price drop percentage to alert
            hours: Look back period

        Returns:
            List of price drop alerts
        """
        from ospra_os.models.competitor import CompetitorProduct, Competitor

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = select(CompetitorProduct, Competitor).join(
            Competitor,
            CompetitorProduct.competitor_id == Competitor.competitor_id
        ).where(
            and_(
                CompetitorProduct.last_price_change >= cutoff_time,
                CompetitorProduct.price_dropped == True,
                CompetitorProduct.price_drop_percent >= min_drop_percent
            )
        ).order_by(desc(CompetitorProduct.price_drop_percent))

        result = await self.db.execute(query)
        products = result.all()

        alerts = []
        for product_row in products:
            product = product_row[0]
            competitor = product_row[1]

            alerts.append({
                'alert_type': 'PRICE_DROP',
                'severity': 'HIGH' if product.price_drop_percent >= 25 else 'MEDIUM',
                'competitor_id': competitor.competitor_id,
                'competitor_name': competitor.name,
                'product_id': product.product_id,
                'product_name': product.name,
                'product_url': product.url,
                'drop_percent': product.price_drop_percent,
                'new_price': product.current_price,
                'our_product_id': product.our_product_id,
                'we_are_higher': product.we_are == 'HIGHER' if product.we_are else None,
                'changed_at': product.last_price_change.isoformat()
            })

        return alerts
