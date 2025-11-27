"""
Velocity Detector - Track product trend momentum and lifecycle phases

Identifies product lifecycle phases to enable tier-based early access:
- Discovery: Just found, minimal data
- Early Spike: Rapid growth, trending up fast
- Growth: Sustained momentum, proven demand
- Maturity: Stable, high volume but slower growth
- Decline: Decreasing interest

Higher tier users get access to products in earlier phases.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import logging

from ospra_os.database.multi_store_models import (
    ProductVelocity,
    ProductSaturation
)

logger = logging.getLogger(__name__)


class VelocityDetector:
    """Detect and track product trend velocity and lifecycle phases"""

    # Lifecycle phase thresholds
    PHASE_THRESHOLDS = {
        'discovery': {'growth_rate': 0, 'age_days': 7},
        'early_spike': {'growth_rate': 50, 'age_days': 14},
        'growth': {'growth_rate': 20, 'age_days': 30},
        'maturity': {'growth_rate': 5, 'age_days': 60},
        'decline': {'growth_rate': -10, 'age_days': float('inf')}
    }

    def __init__(self, database_url: str):
        """Initialize VelocityDetector with database connection"""
        self.database_url = database_url

        # Convert to async URL
        if database_url.startswith("sqlite://"):
            async_url = database_url.replace("sqlite://", "sqlite+aiosqlite://")
        elif database_url.startswith("postgresql://"):
            async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        else:
            async_url = database_url

        self.engine = create_async_engine(async_url, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    def calculate_velocity_score(
        self,
        search_volume_current: int,
        search_volume_previous: int,
        reddit_mentions_current: int,
        reddit_mentions_previous: int,
        age_days: int
    ) -> float:
        """
        Calculate overall velocity score (0-100)

        Factors:
        - Search volume growth rate (40% weight)
        - Reddit mention growth rate (30% weight)
        - Recency bonus (30% weight - newer products score higher)

        Returns:
            Velocity score from 0-100
        """
        # Search growth rate
        search_growth = 0
        if search_volume_previous > 0:
            search_growth = ((search_volume_current - search_volume_previous) / search_volume_previous) * 100

        # Reddit growth rate
        reddit_growth = 0
        if reddit_mentions_previous > 0:
            reddit_growth = ((reddit_mentions_current - reddit_mentions_previous) / reddit_mentions_previous) * 100

        # Recency bonus (newer = better, decays over 90 days)
        recency_multiplier = max(0, 1 - (age_days / 90))

        # Weighted velocity score
        velocity = (
            (search_growth * 0.4) +
            (reddit_growth * 0.3) +
            (recency_multiplier * 0.3 * 100)  # Convert 0-1 range to 0-30 range
        )

        # Cap at 100, floor at 0
        return min(100, max(0, velocity))

    def determine_lifecycle_phase(
        self,
        growth_rate: float,
        age_days: int,
        velocity_score: float
    ) -> str:
        """
        Determine product lifecycle phase based on metrics

        Phases:
        - discovery: Just found, < 7 days old
        - early_spike: Rapid growth (50%+), < 21 days old
        - growth: Sustained growth (20%+), < 45 days old
        - maturity: Stable but slower growth
        - decline: Negative growth

        Args:
            growth_rate: Percentage growth rate
            age_days: Days since first discovered
            velocity_score: Overall velocity score

        Returns:
            Lifecycle phase string
        """
        # Discovery phase: first week
        if age_days <= 7:
            return 'discovery'

        # Early spike: rapid growth in first 3 weeks
        if growth_rate >= 50 and age_days <= 21:
            return 'early_spike'

        # Growth phase: sustained growth under 45 days
        if growth_rate >= 20 and age_days <= 45:
            return 'growth'

        # Decline: negative growth
        if growth_rate < 0:
            return 'decline'

        # Default: maturity
        return 'maturity'

    async def update_product_velocity(
        self,
        product_saturation_id: int,
        search_volume_7d: int,
        search_volume_30d: int,
        reddit_mentions_7d: int = 0,
        reddit_mentions_30d: int = 0
    ) -> ProductVelocity:
        """
        Update velocity tracking for a product

        Args:
            product_saturation_id: ID of product in product_saturation table
            search_volume_7d: Search volume last 7 days
            search_volume_30d: Search volume last 30 days
            reddit_mentions_7d: Reddit mentions last 7 days
            reddit_mentions_30d: Reddit mentions last 30 days

        Returns:
            Updated ProductVelocity object
        """
        async with self.async_session() as session:
            # Get or create velocity record
            stmt = select(ProductVelocity).where(
                ProductVelocity.product_saturation_id == product_saturation_id
            )
            result = await session.execute(stmt)
            velocity = result.scalar_one_or_none()

            if not velocity:
                velocity = ProductVelocity(
                    product_saturation_id=product_saturation_id
                )
                session.add(velocity)

            # Calculate growth rates
            search_growth = 0
            if velocity.search_volume_7d and velocity.search_volume_7d > 0:
                search_growth = ((search_volume_7d - velocity.search_volume_7d) / velocity.search_volume_7d) * 100
            elif search_volume_30d > 0:
                # Fallback to 30-day comparison if no 7-day history
                search_growth = ((search_volume_7d - search_volume_30d) / search_volume_30d) * 100

            reddit_growth = 0
            if velocity.reddit_mentions_7d and velocity.reddit_mentions_7d > 0:
                reddit_growth = ((reddit_mentions_7d - velocity.reddit_mentions_7d) / velocity.reddit_mentions_7d) * 100
            elif reddit_mentions_30d > 0:
                reddit_growth = ((reddit_mentions_7d - reddit_mentions_30d) / reddit_mentions_30d) * 100

            # Get product age
            stmt = select(ProductSaturation).where(ProductSaturation.id == product_saturation_id)
            result = await session.execute(stmt)
            saturation = result.scalar_one_or_none()

            if not saturation:
                logger.error(f"ProductSaturation {product_saturation_id} not found")
                return velocity

            age_days = (datetime.utcnow() - saturation.first_discovered_at).days

            # Calculate velocity score
            velocity_score = self.calculate_velocity_score(
                search_volume_7d,
                velocity.search_volume_7d or search_volume_30d,
                reddit_mentions_7d,
                velocity.reddit_mentions_7d or reddit_mentions_30d,
                age_days
            )

            # Determine lifecycle phase
            phase = self.determine_lifecycle_phase(
                search_growth,
                age_days,
                velocity_score
            )

            # Update velocity record
            velocity.search_volume_7d = search_volume_7d
            velocity.search_volume_30d = search_volume_30d
            velocity.search_growth_rate = search_growth
            velocity.reddit_mentions_7d = reddit_mentions_7d
            velocity.reddit_mentions_30d = reddit_mentions_30d
            velocity.reddit_growth_rate = reddit_growth
            velocity.viral_coefficient = velocity_score
            velocity.phase = phase
            velocity.phase_age_days = age_days
            velocity.last_analyzed_at = datetime.utcnow()

            await session.commit()
            await session.refresh(velocity)

            logger.info(f"Updated velocity for product {product_saturation_id}: phase={phase}, velocity={velocity_score:.1f}")
            return velocity

    async def get_products_by_phase(
        self,
        phase: str,
        niche: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get products in a specific lifecycle phase

        Args:
            phase: Lifecycle phase ('discovery', 'early_spike', 'growth', 'maturity', 'decline')
            niche: Optional niche filter
            limit: Maximum products to return

        Returns:
            List of product dictionaries with velocity metrics
        """
        async with self.async_session() as session:
            # Base query
            stmt = select(ProductVelocity, ProductSaturation).join(
                ProductSaturation,
                ProductVelocity.product_saturation_id == ProductSaturation.id
            ).where(ProductVelocity.phase == phase)

            # Apply niche filter if provided
            if niche:
                stmt = stmt.where(ProductSaturation.niche == niche)

            # Order by velocity score (highest first)
            stmt = stmt.order_by(ProductVelocity.viral_coefficient.desc()).limit(limit)

            result = await session.execute(stmt)
            rows = result.all()

            products = []
            for velocity, saturation in rows:
                products.append({
                    "product_saturation_id": velocity.product_saturation_id,
                    "product_name": saturation.product_name,
                    "niche": saturation.niche,
                    "phase": velocity.phase,
                    "velocity_score": velocity.viral_coefficient,
                    "growth_rate": velocity.search_growth_rate,
                    "age_days": velocity.phase_age_days,
                    "search_volume_7d": velocity.search_volume_7d,
                    "reddit_mentions_7d": velocity.reddit_mentions_7d,
                    "last_analyzed": velocity.last_analyzed_at.isoformat() if velocity.last_analyzed_at else None
                })

            return products

    async def get_tier_appropriate_products(
        self,
        user_tier: str,
        niche: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get products appropriate for user's subscription tier

        Tier Access Levels:
        - free: maturity only (30+ days old, proven but slower growth)
        - starter: growth + maturity (14+ days old)
        - pro: early_spike + growth (7+ days old, fast movers)
        - enterprise: discovery + early_spike (fresh products, first access)

        Args:
            user_tier: User's subscription tier
            niche: Optional niche filter
            limit: Maximum products to return

        Returns:
            List of products matching tier access level
        """
        # Define which phases each tier can access
        tier_phases = {
            'free': ['maturity'],
            'starter': ['growth', 'maturity'],
            'pro': ['early_spike', 'growth'],
            'enterprise': ['discovery', 'early_spike']
        }

        # Get allowed phases for this tier
        phases = tier_phases.get(user_tier.lower(), ['maturity'])

        async with self.async_session() as session:
            # Build query
            stmt = select(ProductVelocity, ProductSaturation).join(
                ProductSaturation,
                ProductVelocity.product_saturation_id == ProductSaturation.id
            ).where(ProductVelocity.phase.in_(phases))

            # Apply niche filter
            if niche:
                stmt = stmt.where(ProductSaturation.niche == niche)

            # Order by velocity score (highest first)
            stmt = stmt.order_by(ProductVelocity.viral_coefficient.desc()).limit(limit)

            result = await session.execute(stmt)
            rows = result.all()

            products = []
            for velocity, saturation in rows:
                products.append({
                    "product_saturation_id": velocity.product_saturation_id,
                    "product_name": saturation.product_name,
                    "niche": saturation.niche,
                    "phase": velocity.phase,
                    "velocity_score": velocity.viral_coefficient,
                    "tier_advantage": user_tier,
                    "growth_rate": velocity.search_growth_rate,
                    "age_days": velocity.phase_age_days,
                    "early_access": velocity.phase in ['discovery', 'early_spike']
                })

            logger.info(f"Found {len(products)} products for tier {user_tier} in phases {phases}")
            return products

    async def get_velocity_stats(
        self,
        niche: Optional[str] = None
    ) -> Dict:
        """
        Get velocity statistics across all phases

        Args:
            niche: Optional niche filter

        Returns:
            Dictionary with counts and metrics per phase
        """
        async with self.async_session() as session:
            # Base query
            stmt = select(ProductVelocity)

            # Apply niche filter if needed
            if niche:
                stmt = stmt.join(
                    ProductSaturation,
                    ProductVelocity.product_saturation_id == ProductSaturation.id
                ).where(ProductSaturation.niche == niche)

            result = await session.execute(stmt)
            velocities = result.scalars().all()

            # Calculate stats per phase
            stats = {
                "total_products": len(velocities),
                "niche": niche or "all",
                "phases": {}
            }

            for phase in ['discovery', 'early_spike', 'growth', 'maturity', 'decline']:
                phase_products = [v for v in velocities if v.phase == phase]

                if phase_products:
                    avg_velocity = sum(v.viral_coefficient for v in phase_products) / len(phase_products)
                    avg_growth = sum(v.search_growth_rate for v in phase_products) / len(phase_products)
                else:
                    avg_velocity = 0
                    avg_growth = 0

                stats["phases"][phase] = {
                    "count": len(phase_products),
                    "avg_velocity_score": round(avg_velocity, 2),
                    "avg_growth_rate": round(avg_growth, 2),
                    "tier_access": self._get_tiers_for_phase(phase)
                }

            return stats

    def _get_tiers_for_phase(self, phase: str) -> List[str]:
        """Get which tiers have access to this phase"""
        tier_phases = {
            'free': ['maturity'],
            'starter': ['growth', 'maturity'],
            'pro': ['early_spike', 'growth'],
            'enterprise': ['discovery', 'early_spike']
        }

        return [tier for tier, phases in tier_phases.items() if phase in phases]

    async def close(self):
        """Close database connections"""
        await self.engine.dispose()
