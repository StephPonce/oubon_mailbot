"""
Gap Analyzer - Find competitive gaps and opportunities

Identifies:
- Product gaps (they have, we don't)
- Price gaps (significant price differences)
- Feature gaps (services/features we lack)
- Market gaps (underserved segments)
- Our unique advantages

Author: OspraOS
Date: November 2025
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import select, and_, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from collections import Counter
import statistics

logger = logging.getLogger(__name__)


class GapAnalyzer:
    """Analyzes competitive gaps and identifies opportunities"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def find_product_gaps(
        self,
        competitor_id: Optional[str] = None,
        min_competitors_carrying: int = 2
    ) -> List[dict]:
        """
        Find products competitors carry that we don't

        Args:
            competitor_id: Specific competitor to analyze (None = all)
            min_competitors_carrying: Minimum number of competitors needed

        Returns:
            List of product gap opportunities
        """
        from ospra_os.models.competitor import CompetitorProduct, Competitor

        # Get competitor products not matched to ours
        query = select(CompetitorProduct, Competitor).join(
            Competitor,
            CompetitorProduct.competitor_id == Competitor.competitor_id
        ).where(
            and_(
                CompetitorProduct.our_product_id.is_(None),  # No match to our products
                CompetitorProduct.is_removed == False,
                Competitor.status == 'ACTIVE'
            )
        )

        if competitor_id:
            query = query.where(CompetitorProduct.competitor_id == competitor_id)

        result = await self.db.execute(query)
        products = result.all()

        # Group similar products by name/category
        product_groups = {}

        for product_row in products:
            product = product_row[0]
            competitor = product_row[1]

            # Simple grouping by product type or name similarity
            key = product.product_type or product.category or product.name

            if key not in product_groups:
                product_groups[key] = {
                    'product_names': [],
                    'competitors': [],
                    'prices': [],
                    'product_ids': [],
                    'urls': []
                }

            product_groups[key]['product_names'].append(product.name)
            product_groups[key]['competitors'].append(competitor.name)
            product_groups[key]['prices'].append(product.current_price)
            product_groups[key]['product_ids'].append(product.product_id)
            product_groups[key]['urls'].append(product.url)

        # Build gap opportunities
        gaps = []

        for product_type, data in product_groups.items():
            competitor_count = len(set(data['competitors']))

            # Filter by minimum competitors carrying
            if competitor_count < min_competitors_carrying:
                continue

            avg_price = statistics.mean([p for p in data['prices'] if p]) if data['prices'] else 0
            min_price = min([p for p in data['prices'] if p]) if data['prices'] else 0
            max_price = max([p for p in data['prices'] if p]) if data['prices'] else 0

            # Estimate demand based on number of competitors carrying it
            if competitor_count >= 5:
                demand = 'HIGH'
            elif competitor_count >= 3:
                demand = 'MEDIUM'
            else:
                demand = 'LOW'

            # Calculate opportunity score (0-100)
            opportunity_score = self._calculate_product_gap_score(
                competitor_count=competitor_count,
                avg_price=avg_price,
                demand=demand
            )

            gaps.append({
                'product_type': product_type,
                'representative_name': data['product_names'][0],
                'competitors_carrying': list(set(data['competitors'])),
                'competitor_count': competitor_count,
                'avg_price': round(avg_price, 2),
                'price_range': {
                    'min': round(min_price, 2),
                    'max': round(max_price, 2)
                },
                'estimated_demand': demand,
                'opportunity_score': opportunity_score,
                'recommendation': self._get_product_gap_recommendation(opportunity_score, avg_price),
                'example_urls': data['urls'][:3]  # First 3 examples
            })

        # Sort by opportunity score
        gaps.sort(key=lambda x: x['opportunity_score'], reverse=True)

        return gaps

    def _calculate_product_gap_score(
        self,
        competitor_count: int,
        avg_price: float,
        demand: str
    ) -> int:
        """Calculate opportunity score for a product gap (0-100)"""

        score = 0

        # Competitor adoption (max 40 points)
        score += min(competitor_count * 8, 40)

        # Price potential (max 30 points)
        if 20 <= avg_price <= 100:  # Sweet spot for e-commerce
            score += 30
        elif 10 <= avg_price < 20:
            score += 20
        elif avg_price > 100:
            score += 15
        else:
            score += 10

        # Demand (max 30 points)
        demand_scores = {'HIGH': 30, 'MEDIUM': 20, 'LOW': 10}
        score += demand_scores.get(demand, 10)

        return min(score, 100)

    def _get_product_gap_recommendation(self, score: int, price: float) -> str:
        """Get recommendation text based on opportunity score"""

        if score >= 80:
            return f"STRONG OPPORTUNITY - High demand product at ${price:.2f} avg. Consider adding ASAP."
        elif score >= 60:
            return f"GOOD OPPORTUNITY - Multiple competitors carrying at ${price:.2f}. Worth researching."
        elif score >= 40:
            return f"MODERATE OPPORTUNITY - Some demand at ${price:.2f}. Consider for future expansion."
        else:
            return f"LOW PRIORITY - Limited adoption at ${price:.2f}. Monitor but don't prioritize."

    async def find_price_gaps(self, threshold_percent: float = 15.0) -> List[dict]:
        """
        Find significant price differences between us and competitors

        Args:
            threshold_percent: Minimum price difference percentage

        Returns:
            List of price gap opportunities
        """
        from ospra_os.models.competitor import CompetitorProduct, Competitor

        # Get matched products with significant price differences
        query = select(CompetitorProduct, Competitor).join(
            Competitor,
            CompetitorProduct.competitor_id == Competitor.competitor_id
        ).where(
            and_(
                CompetitorProduct.our_product_id.isnot(None),
                CompetitorProduct.our_price.isnot(None),
                CompetitorProduct.is_removed == False
            )
        )

        result = await self.db.execute(query)
        products = result.all()

        price_gaps = []

        for product_row in products:
            product = product_row[0]
            competitor = product_row[1]

            if not product.our_price or not product.current_price:
                continue

            price_diff = product.our_price - product.current_price
            price_diff_percent = abs((price_diff / product.current_price) * 100)

            # Filter by threshold
            if price_diff_percent < threshold_percent:
                continue

            gap_type = None
            recommendation = None

            if price_diff > 0:  # We're more expensive
                gap_type = 'WE_ARE_HIGHER'
                if price_diff_percent > 25:
                    recommendation = "URGENT: Consider price reduction or value differentiation"
                else:
                    recommendation = "Consider price match or emphasize our advantages"

            else:  # We're cheaper
                gap_type = 'WE_ARE_LOWER'
                if price_diff_percent > 25:
                    recommendation = "OPPORTUNITY: We're significantly cheaper - could raise price"
                else:
                    recommendation = "We're competitively priced - maintain or slight increase possible"

            price_gaps.append({
                'our_product_id': product.our_product_id,
                'our_product_name': product.our_product_name,
                'our_price': product.our_price,
                'competitor': competitor.name,
                'competitor_price': product.current_price,
                'gap_amount': round(price_diff, 2),
                'gap_percent': round(price_diff_percent, 2),
                'gap_type': gap_type,
                'recommendation': recommendation,
                'competitor_url': product.url
            })

        # Sort by gap percentage
        price_gaps.sort(key=lambda x: x['gap_percent'], reverse=True)

        return price_gaps

    async def find_feature_gaps(self) -> List[dict]:
        """
        Identify features/services competitors offer that we don't

        Analyzes:
        - Free shipping thresholds
        - Loyalty programs
        - Warranty policies
        - Subscription options
        - Return policies

        Returns:
            List of feature gap opportunities
        """
        from ospra_os.models.competitor import Competitor

        # Get all active competitors
        query = select(Competitor).where(Competitor.status == 'ACTIVE')
        result = await self.db.execute(query)
        competitors = result.scalars().all()

        # Analyze strengths to identify common features
        all_strengths = []
        for comp in competitors:
            if comp.strengths:
                all_strengths.extend(comp.strengths)

        # Count common strengths/features
        strength_counts = Counter(all_strengths)

        # Features commonly mentioned as strengths
        common_features = [
            {
                'feature': feature,
                'competitor_count': count,
                'prevalence': f"{(count / len(competitors) * 100):.1f}%" if competitors else "0%",
                'recommendation': f"Consider implementing - {count} competitors offer this"
            }
            for feature, count in strength_counts.most_common(10)
            if count >= 2  # At least 2 competitors
        ]

        return common_features

    async def find_market_gaps(self, niche: str) -> List[dict]:
        """
        Identify underserved market segments

        Args:
            niche: Product niche to analyze

        Returns:
            List of market gap opportunities
        """
        from ospra_os.models.competitor import CompetitorProduct, Competitor

        # Get all products in niche from all competitors
        query = select(CompetitorProduct, Competitor).join(
            Competitor,
            CompetitorProduct.competitor_id == Competitor.competitor_id
        ).where(
            and_(
                Competitor.primary_niches.contains([niche]),
                CompetitorProduct.is_removed == False
            )
        )

        result = await self.db.execute(query)
        products = result.all()

        # Analyze by price segments
        prices = [p[0].current_price for p in products if p[0].current_price]

        if not prices:
            return []

        # Define price segments
        min_price = min(prices)
        max_price = max(prices)
        range_size = (max_price - min_price) / 4

        segments = {
            'BUDGET': (min_price, min_price + range_size),
            'MID_LOW': (min_price + range_size, min_price + range_size * 2),
            'MID_HIGH': (min_price + range_size * 2, min_price + range_size * 3),
            'PREMIUM': (min_price + range_size * 3, max_price)
        }

        # Count products in each segment
        segment_counts = {seg: 0 for seg in segments}

        for price in prices:
            for seg_name, (seg_min, seg_max) in segments.items():
                if seg_min <= price <= seg_max:
                    segment_counts[seg_name] += 1
                    break

        # Identify underserved segments
        total_products = len(prices)
        gaps = []

        for seg_name, count in segment_counts.items():
            coverage_percent = (count / total_products * 100) if total_products > 0 else 0
            seg_range = segments[seg_name]

            if coverage_percent < 15:  # Less than 15% coverage
                gaps.append({
                    'segment': seg_name,
                    'price_range': {
                        'min': round(seg_range[0], 2),
                        'max': round(seg_range[1], 2)
                    },
                    'product_count': count,
                    'coverage_percent': round(coverage_percent, 2),
                    'opportunity_level': 'HIGH' if coverage_percent < 5 else 'MEDIUM',
                    'recommendation': f"Underserved segment - only {count} products in ${seg_range[0]:.0f}-${seg_range[1]:.0f} range"
                })

        return gaps

    async def find_our_unique_products(self, competitor_id: Optional[str] = None) -> List[dict]:
        """
        Find products that we carry but competitors don't

        These are our competitive advantages to highlight in marketing

        Args:
            competitor_id: Specific competitor (None = all competitors)

        Returns:
            List of our unique products
        """
        from ospra_os.models.competitor import CompetitorProduct

        # This would query our actual product catalog
        # For now, we'll identify products from matched competitor products

        # Get all matched products
        query = select(CompetitorProduct.our_product_id, CompetitorProduct.our_product_name).where(
            CompetitorProduct.our_product_id.isnot(None)
        ).distinct()

        if competitor_id:
            query = query.where(CompetitorProduct.competitor_id == competitor_id)

        result = await self.db.execute(query)
        matched_products = set(row[0] for row in result.all())

        # In a real implementation, we'd query our product catalog and exclude matched_products
        # For MVP, we return a structure

        return [
            {
                'our_product_id': 'placeholder',
                'product_name': 'Unique Product Example',
                'competitive_advantage': 'Only we carry this product',
                'recommendation': 'Highlight in marketing - exclusive offering'
            }
        ]

    async def get_strategic_opportunities(self, top_n: int = 10) -> List[dict]:
        """
        Combine all gap types into prioritized strategic opportunities

        Args:
            top_n: Number of top opportunities to return

        Returns:
            Prioritized list of opportunities
        """
        opportunities = []

        # Product gaps
        product_gaps = await self.find_product_gaps()
        for gap in product_gaps[:5]:  # Top 5 product gaps
            opportunities.append({
                'type': 'PRODUCT_GAP',
                'priority': 'HIGH' if gap['opportunity_score'] >= 80 else 'MEDIUM',
                'title': f"Add {gap['product_type']} to catalog",
                'description': gap['recommendation'],
                'score': gap['opportunity_score'],
                'details': gap
            })

        # Price gaps
        price_gaps = await self.find_price_gaps()
        for gap in price_gaps[:5]:  # Top 5 price gaps
            priority = 'HIGH' if gap['gap_percent'] > 25 else 'MEDIUM'
            opportunities.append({
                'type': 'PRICE_GAP',
                'priority': priority,
                'title': f"Price adjustment on {gap['our_product_name']}",
                'description': gap['recommendation'],
                'score': gap['gap_percent'],
                'details': gap
            })

        # Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)

        return opportunities[:top_n]
