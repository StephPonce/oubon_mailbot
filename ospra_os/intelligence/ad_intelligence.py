"""
Ad Intelligence - Track competitor advertising strategies

Monitors:
- Ad platforms used
- Ad creative analysis
- Selling angles
- Estimated ad spend
- Campaign insights

Data sources:
- Facebook Ad Library (public API)
- TikTok Creative Center
- Manual observation

Author: OspraOS
Date: November 2025
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from collections import Counter

logger = logging.getLogger(__name__)


class AdIntelligence:
    """Analyzes competitor advertising strategies"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_ad_platforms(self, competitor_id: str) -> List[str]:
        """
        Get platforms where competitor is advertising

        Args:
            competitor_id: Competitor ID

        Returns:
            List of platform names
        """
        from ospra_os.models.competitor import Competitor

        query = select(Competitor).where(Competitor.competitor_id == competitor_id)
        result = await self.db.execute(query)
        competitor = result.scalar_one_or_none()

        if not competitor:
            return []

        return competitor.ad_platforms or []

    async def get_ad_creative_analysis(self, competitor_id: str) -> dict:
        """
        Analyze competitor's ad creatives and campaigns

        Args:
            competitor_id: Competitor ID

        Returns:
            Ad creative analysis dict
        """
        from ospra_os.models.competitor import Competitor

        query = select(Competitor).where(Competitor.competitor_id == competitor_id)
        result = await self.db.execute(query)
        competitor = result.scalar_one_or_none()

        if not competitor:
            return {'error': 'Competitor not found'}

        # Get marketing angles
        marketing_angles = competitor.primary_marketing_angles or []

        # Estimate campaign count based on platforms
        platforms = competitor.ad_platforms or []
        estimated_campaigns = len(platforms) * 3  # Rough estimate

        return {
            'competitor_id': competitor_id,
            'competitor_name': competitor.name,
            'active_platforms': platforms,
            'platform_count': len(platforms),
            'primary_angles': marketing_angles,
            'estimated_monthly_spend': competitor.estimated_ad_spend,
            'estimated_campaigns': estimated_campaigns,
            'analysis_date': datetime.now(timezone.utc).isoformat()
        }

    async def estimate_ad_spend(self, competitor_id: str) -> dict:
        """
        Estimate competitor's monthly ad spend

        Based on:
        - Number of platforms
        - Ad presence/frequency
        - Store size
        - Revenue estimates

        Args:
            competitor_id: Competitor ID

        Returns:
            Ad spend estimate dict
        """
        from ospra_os.models.competitor import Competitor

        query = select(Competitor).where(Competitor.competitor_id == competitor_id)
        result = await self.db.execute(query)
        competitor = result.scalar_one_or_none()

        if not competitor:
            return {'error': 'Competitor not found'}

        # If we have a stored estimate, return it
        if competitor.estimated_ad_spend:
            return {
                'competitor_id': competitor_id,
                'competitor_name': competitor.name,
                'estimated_monthly_spend': competitor.estimated_ad_spend,
                'confidence': 'STORED',
                'methodology': 'previous_calculation'
            }

        # Otherwise, estimate based on heuristics
        platforms = competitor.ad_platforms or []
        revenue = competitor.estimated_revenue or 0

        # Typical ad spend is 10-30% of revenue for e-commerce
        # Assume 15% average
        spend_from_revenue = revenue * 0.15 if revenue > 0 else 0

        # Minimum spend per platform (rough estimate)
        min_spend_per_platform = {
            'facebook': 1000,
            'google': 1500,
            'tiktok': 800,
            'instagram': 500,
            'pinterest': 300
        }

        spend_from_platforms = sum(
            min_spend_per_platform.get(platform.lower(), 500)
            for platform in platforms
        )

        # Use the higher estimate
        estimated_spend = max(spend_from_revenue, spend_from_platforms)

        # Confidence level
        if revenue > 0 and platforms:
            confidence = 'MEDIUM'
        elif revenue > 0 or platforms:
            confidence = 'LOW'
        else:
            confidence = 'VERY_LOW'

        return {
            'competitor_id': competitor_id,
            'competitor_name': competitor.name,
            'estimated_monthly_spend': round(estimated_spend, 2),
            'confidence': confidence,
            'methodology': 'revenue_and_platform_heuristics',
            'factors': {
                'platforms': platforms,
                'platform_count': len(platforms),
                'estimated_revenue': revenue
            }
        }

    async def extract_selling_angles(self, competitor_id: str) -> List[str]:
        """
        Extract main selling angles from competitor

        Args:
            competitor_id: Competitor ID

        Returns:
            List of selling angles
        """
        from ospra_os.models.competitor import Competitor

        query = select(Competitor).where(Competitor.competitor_id == competitor_id)
        result = await self.db.execute(query)
        competitor = result.scalar_one_or_none()

        if not competitor:
            return []

        return competitor.primary_marketing_angles or []

    async def get_ad_insights(self) -> dict:
        """
        Analyze competitor ads to extract insights for our strategy

        Returns:
            Ad insights and recommendations
        """
        from ospra_os.models.competitor import Competitor

        # Get all active competitors
        query = select(Competitor).where(Competitor.status == 'ACTIVE')
        result = await self.db.execute(query)
        competitors = result.scalars().all()

        if not competitors:
            return {'insights': [], 'recommendations': []}

        # Aggregate data
        all_platforms = []
        all_angles = []

        for comp in competitors:
            if comp.ad_platforms:
                all_platforms.extend(comp.ad_platforms)
            if comp.primary_marketing_angles:
                all_angles.extend(comp.primary_marketing_angles)

        # Count platform usage
        platform_counts = Counter(all_platforms)
        angle_counts = Counter(all_angles)

        # Most popular platforms
        top_platforms = [
            {'platform': platform, 'competitor_count': count}
            for platform, count in platform_counts.most_common(5)
        ]

        # Most common selling angles
        top_angles = [
            {'angle': angle, 'usage_count': count}
            for angle, count in angle_counts.most_common(10)
        ]

        # Generate insights
        insights = []

        if top_platforms:
            top_platform = top_platforms[0]
            insights.append({
                'type': 'PLATFORM_TREND',
                'title': f"{top_platform['platform']} is most popular",
                'description': f"{top_platform['competitor_count']} competitors are advertising on {top_platform['platform']}",
                'recommendation': f"Consider allocating budget to {top_platform['platform']}"
            })

        if top_angles:
            top_angle = top_angles[0]
            insights.append({
                'type': 'MESSAGING_TREND',
                'title': f"'{top_angle['angle']}' is a common selling point",
                'description': f"{top_angle['usage_count']} competitors emphasize {top_angle['angle']}",
                'recommendation': f"Test messaging around {top_angle['angle']} or differentiate"
            })

        # Calculate average ad spend
        avg_spend = sum(
            [c.estimated_ad_spend for c in competitors if c.estimated_ad_spend]
        ) / len([c for c in competitors if c.estimated_ad_spend]) if any(c.estimated_ad_spend for c in competitors) else 0

        if avg_spend > 0:
            insights.append({
                'type': 'SPEND_BENCHMARK',
                'title': f"Average competitor ad spend: ${avg_spend:,.0f}/mo",
                'description': f"Based on {len([c for c in competitors if c.estimated_ad_spend])} competitors with estimates",
                'recommendation': f"Consider ad budget around ${avg_spend * 0.8:,.0f} to start"
            })

        recommendations = [
            {
                'priority': 'HIGH',
                'action': f"Test {top_platforms[0]['platform']} advertising" if top_platforms else "Research ad platforms",
                'rationale': 'Most competitors are active here' if top_platforms else 'Need more data'
            },
            {
                'priority': 'MEDIUM',
                'action': f"Incorporate '{top_angles[0]['angle']}' in messaging" if top_angles else "Research selling angles",
                'rationale': 'Proven angle in market' if top_angles else 'Need more data'
            },
            {
                'priority': 'MEDIUM',
                'action': "Monitor competitor ad creatives weekly",
                'rationale': "Stay current with market trends"
            }
        ]

        return {
            'total_competitors_analyzed': len(competitors),
            'top_platforms': top_platforms,
            'top_selling_angles': top_angles,
            'average_monthly_spend': round(avg_spend, 2),
            'insights': insights,
            'recommendations': recommendations,
            'analyzed_at': datetime.now(timezone.utc).isoformat()
        }

    async def search_facebook_ads(self, competitor_name: str) -> dict:
        """
        Search Facebook Ad Library for competitor ads

        Note: This would integrate with Facebook Ad Library API
        For MVP, returns placeholder structure

        Args:
            competitor_name: Competitor business name

        Returns:
            Ad search results
        """
        # TODO: Implement Facebook Ad Library API integration
        # https://www.facebook.com/ads/library/api/

        return {
            'competitor_name': competitor_name,
            'status': 'NOT_IMPLEMENTED',
            'message': 'Facebook Ad Library API integration pending',
            'manual_url': f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=US&q={competitor_name.replace(' ', '%20')}",
            'note': 'Visit the manual URL to view ads in browser'
        }

    async def update_competitor_ad_data(
        self,
        competitor_id: str,
        platforms: List[str],
        marketing_angles: List[str],
        estimated_spend: Optional[float] = None
    ) -> dict:
        """
        Update competitor's advertising data

        Args:
            competitor_id: Competitor ID
            platforms: List of ad platforms
            marketing_angles: List of selling angles
            estimated_spend: Monthly ad spend estimate

        Returns:
            Updated competitor data
        """
        from ospra_os.models.competitor import Competitor

        query = select(Competitor).where(Competitor.competitor_id == competitor_id)
        result = await self.db.execute(query)
        competitor = result.scalar_one_or_none()

        if not competitor:
            return {'error': 'Competitor not found'}

        # Update fields
        competitor.ad_platforms = platforms
        competitor.primary_marketing_angles = marketing_angles
        if estimated_spend:
            competitor.estimated_ad_spend = estimated_spend

        await self.db.commit()

        logger.info(f"Updated ad data for competitor {competitor_id}")

        return {
            'competitor_id': competitor_id,
            'competitor_name': competitor.name,
            'ad_platforms': platforms,
            'marketing_angles': marketing_angles,
            'estimated_spend': estimated_spend,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
