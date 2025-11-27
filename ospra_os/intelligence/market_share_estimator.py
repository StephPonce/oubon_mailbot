"""
Market Share Estimator - Estimate competitor revenue and market positioning

Estimates based on:
- Product catalog size
- Review velocity
- Social following
- Price positioning
- Traffic estimates (where available)

Author: OspraOS
Date: November 2025
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
import statistics

logger = logging.getLogger(__name__)


class MarketShareEstimator:
    """Estimates market share and competitive positioning"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

        # Estimation assumptions (can be tuned)
        self.ASSUMED_CONVERSION_RATE = 0.02  # 2%
        self.ASSUMED_REVIEW_RATE = 0.05  # 5% of customers leave reviews
        self.AVG_ORDERS_PER_CUSTOMER = 1.5
        self.MONTHLY_ACTIVE_CUSTOMERS_PER_FOLLOWER = 0.10  # 10% of social followers buy monthly

    async def estimate_competitor_revenue(self, competitor_id: str) -> dict:
        """
        Estimate monthly revenue for a competitor

        Multiple methodologies used and combined:
        1. Review velocity (most reliable for e-commerce)
        2. Product catalog heuristics
        3. Social follower activity
        4. Price positioning and market segment

        Args:
            competitor_id: Competitor ID

        Returns:
            Revenue estimate dict with methodology breakdown
        """
        from ospra_os.models.competitor import Competitor, CompetitorProduct

        # Get competitor data
        comp_query = select(Competitor).where(Competitor.competitor_id == competitor_id)
        comp_result = await self.db.execute(comp_query)
        competitor = comp_result.scalar_one_or_none()

        if not competitor:
            return {'error': 'Competitor not found'}

        # Get products
        prod_query = select(CompetitorProduct).where(
            and_(
                CompetitorProduct.competitor_id == competitor_id,
                CompetitorProduct.is_removed == False
            )
        )
        prod_result = await self.db.execute(prod_query)
        products = prod_result.scalars().all()

        product_count = len(products)
        avg_price = statistics.mean([p.current_price for p in products if p.current_price]) if products else 0

        # Method 1: Review Velocity
        total_reviews = sum([p.reviews_count for p in products if p.reviews_count])
        if total_reviews > 0:
            # Assume recent reviews represent monthly sales
            estimated_monthly_orders = total_reviews / self.ASSUMED_REVIEW_RATE
            review_based_revenue = estimated_monthly_orders * avg_price
        else:
            review_based_revenue = None

        # Method 2: Product Catalog Size
        # Typical product productivity per month
        orders_per_product_per_month = {
            'small': 3,    # < 20 products
            'medium': 8,   # 20-100 products
            'large': 12    # > 100 products
        }

        if product_count < 20:
            catalog_size = 'small'
        elif product_count < 100:
            catalog_size = 'medium'
        else:
            catalog_size = 'large'

        productivity = orders_per_product_per_month[catalog_size]
        catalog_based_revenue = product_count * productivity * avg_price

        # Method 3: Social Following
        social_followers = competitor.social_followers or {}
        total_followers = sum(social_followers.values()) if isinstance(social_followers, dict) else 0

        if total_followers > 0:
            active_customers = total_followers * self.MONTHLY_ACTIVE_CUSTOMERS_PER_FOLLOWER
            social_based_revenue = active_customers * avg_price
        else:
            social_based_revenue = None

        # Combine estimates with weighted average
        estimates = []
        weights = []

        if review_based_revenue:
            estimates.append(review_based_revenue)
            weights.append(0.5)  # Highest weight - most reliable

        estimates.append(catalog_based_revenue)
        weights.append(0.3)

        if social_based_revenue:
            estimates.append(social_based_revenue)
            weights.append(0.2)

        # Weighted average
        if estimates:
            total_weight = sum(weights)
            weighted_revenue = sum(e * w for e, w in zip(estimates, weights)) / total_weight
        else:
            weighted_revenue = 0

        # Determine confidence level
        if len(estimates) >= 3:
            confidence = 'HIGH'
        elif len(estimates) == 2:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'

        # Primary methodology
        if review_based_revenue:
            methodology = 'review_velocity'
        elif social_based_revenue:
            methodology = 'social_following'
        else:
            methodology = 'catalog_size'

        return {
            'competitor_id': competitor_id,
            'competitor_name': competitor.name,
            'estimated_monthly_revenue': round(weighted_revenue, 2),
            'confidence': confidence,
            'methodology': methodology,
            'breakdown': {
                'review_based': round(review_based_revenue, 2) if review_based_revenue else None,
                'catalog_based': round(catalog_based_revenue, 2),
                'social_based': round(social_based_revenue, 2) if social_based_revenue else None,
                'weighted_average': round(weighted_revenue, 2)
            },
            'factors': {
                'product_count': product_count,
                'avg_price': round(avg_price, 2),
                'total_reviews': total_reviews,
                'total_social_followers': total_followers,
                'catalog_size': catalog_size
            },
            'estimated_at': datetime.utcnow().isoformat()
        }

    async def calculate_market_share(self, niche: str) -> dict:
        """
        Estimate market share distribution for a niche

        Args:
            niche: Product niche to analyze

        Returns:
            Market share breakdown
        """
        from ospra_os.models.competitor import Competitor

        # Get competitors in this niche
        query = select(Competitor).where(
            and_(
                Competitor.primary_niches.contains([niche]),
                Competitor.status == 'ACTIVE'
            )
        )

        result = await self.db.execute(query)
        competitors = result.scalars().all()

        if not competitors:
            return {
                'niche': niche,
                'error': 'No competitors found in this niche'
            }

        # Get revenue estimates for each
        competitor_revenues = []

        for comp in competitors:
            estimate = await self.estimate_competitor_revenue(comp.competitor_id)
            if 'estimated_monthly_revenue' in estimate:
                competitor_revenues.append({
                    'competitor_id': comp.competitor_id,
                    'name': comp.name,
                    'revenue': estimate['estimated_monthly_revenue'],
                    'threat_level': comp.threat_level
                })

        # Calculate total market
        total_market = sum([c['revenue'] for c in competitor_revenues])

        # Calculate shares and rank
        for comp in competitor_revenues:
            comp['share_percent'] = (comp['revenue'] / total_market * 100) if total_market > 0 else 0

        # Sort by revenue
        competitor_revenues.sort(key=lambda x: x['revenue'], reverse=True)

        # Add ranks
        for idx, comp in enumerate(competitor_revenues, 1):
            comp['rank'] = idx

        # Get our revenue (if we're tracking ourselves)
        # For now, we'll use a placeholder or configuration
        our_revenue = competitor_revenues[0]['revenue'] * 0.3 if competitor_revenues else 0  # Assume we're smaller
        our_share = (our_revenue / total_market * 100) if total_market > 0 else 0
        our_rank = len([c for c in competitor_revenues if c['revenue'] > our_revenue]) + 1

        return {
            'niche': niche,
            'total_estimated_market': round(total_market, 2),
            'competitor_count': len(competitor_revenues),
            'our_position': {
                'estimated_revenue': round(our_revenue, 2),
                'share_percent': round(our_share, 2),
                'rank': our_rank,
                'rank_suffix': self._get_rank_suffix(our_rank)
            },
            'competitors': [
                {
                    'rank': c['rank'],
                    'name': c['name'],
                    'revenue': round(c['revenue'], 2),
                    'share_percent': round(c['share_percent'], 2),
                    'threat_level': c['threat_level']
                }
                for c in competitor_revenues[:10]  # Top 10
            ],
            'calculated_at': datetime.utcnow().isoformat()
        }

    def _get_rank_suffix(self, rank: int) -> str:
        """Get ordinal suffix for rank (1st, 2nd, 3rd, etc.)"""
        if 10 <= rank % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(rank % 10, 'th')
        return f"{rank}{suffix}"

    async def get_market_positioning(self) -> dict:
        """
        Analyze our overall market positioning across all niches

        Returns:
            Market positioning analysis
        """
        from ospra_os.models.competitor import Competitor

        # Get all active competitors
        query = select(Competitor).where(Competitor.status == 'ACTIVE')
        result = await self.db.execute(query)
        competitors = result.scalars().all()

        if not competitors:
            return {'error': 'No competitors tracked'}

        # Analyze by threat level
        threat_distribution = {
            'HIGH': len([c for c in competitors if c.threat_level == 'HIGH']),
            'MEDIUM': len([c for c in competitors if c.threat_level == 'MEDIUM']),
            'LOW': len([c for c in competitors if c.threat_level == 'LOW'])
        }

        # Price positioning
        price_positioning = {
            'BUDGET': len([c for c in competitors if c.price_positioning == 'BUDGET']),
            'MID_MARKET': len([c for c in competitors if c.price_positioning == 'MID_MARKET']),
            'PREMIUM': len([c for c in competitors if c.price_positioning == 'PREMIUM'])
        }

        # Competitor types
        competitor_types = {
            'DIRECT': len([c for c in competitors if c.competitor_type == 'DIRECT']),
            'INDIRECT': len([c for c in competitors if c.competitor_type == 'INDIRECT']),
            'MARKET_LEADER': len([c for c in competitors if c.competitor_type == 'MARKET_LEADER']),
            'EMERGING': len([c for c in competitors if c.competitor_type == 'EMERGING'])
        }

        # Average metrics
        avg_revenue = statistics.mean(
            [c.estimated_revenue for c in competitors if c.estimated_revenue]
        ) if any(c.estimated_revenue for c in competitors) else 0

        avg_products = statistics.mean(
            [c.estimated_product_count for c in competitors if c.estimated_product_count]
        ) if any(c.estimated_product_count for c in competitors) else 0

        return {
            'total_competitors': len(competitors),
            'threat_distribution': threat_distribution,
            'price_positioning': price_positioning,
            'competitor_types': competitor_types,
            'market_averages': {
                'revenue': round(avg_revenue, 2),
                'product_count': round(avg_products, 0)
            },
            'competitive_pressure': 'HIGH' if threat_distribution['HIGH'] > 3 else 'MEDIUM' if threat_distribution['HIGH'] > 1 else 'LOW',
            'analyzed_at': datetime.utcnow().isoformat()
        }

    async def identify_market_leaders(self, niche: str, top_n: int = 5) -> List[dict]:
        """
        Identify top competitors in a niche by estimated revenue

        Args:
            niche: Product niche
            top_n: Number of leaders to return

        Returns:
            List of top competitors
        """
        market_share = await self.calculate_market_share(niche)

        if 'error' in market_share:
            return []

        leaders = market_share['competitors'][:top_n]

        return [
            {
                'rank': leader['rank'],
                'name': leader['name'],
                'estimated_revenue': leader['revenue'],
                'market_share': leader['share_percent'],
                'threat_level': leader['threat_level']
            }
            for leader in leaders
        ]

    async def track_share_changes(self, niche: str, months: int = 6) -> List[dict]:
        """
        Track market share changes over time

        Note: This requires historical snapshots. For MVP, we return current state.

        Args:
            niche: Product niche
            months: Lookback period

        Returns:
            List of monthly market share snapshots
        """
        # TODO: Implement historical tracking with competitor snapshots table
        # For now, return current state

        current_share = await self.calculate_market_share(niche)

        return [
            {
                'date': datetime.utcnow().isoformat(),
                'niche': niche,
                'total_market': current_share.get('total_estimated_market'),
                'our_share': current_share.get('our_position', {}).get('share_percent'),
                'top_competitors': current_share.get('competitors', [])[:3]
            }
        ]
