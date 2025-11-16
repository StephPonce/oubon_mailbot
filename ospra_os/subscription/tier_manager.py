"""
Subscription Tier Management

Manages user subscription tiers and access control for differentiated product access.

Tier Structure:
- Free: Mature products only (30+ days old)
- Starter ($29): Growth products (14+ days)
- Pro ($79): Early spike products (7+ days)
- Elite ($199): Discovery products (fresh, 0+ days)
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import logging

from ospra_os.database.multi_store_models import (
    User,
    UserSettings,
    Store
)

logger = logging.getLogger(__name__)


class TierManager:
    """Manage user subscription tiers and access control"""

    TIER_FEATURES = {
        'free': {
            'name': 'Free',
            'price': 0,
            'max_stores': 1,
            'max_products_per_week': 5,
            'product_age_days': 30,  # Only see products 30+ days old
            'phases': ['maturity'],
            'features': [
                'Basic product discovery',
                '1 store connection',
                'AI analysis (limited)',
                'Email automation (basic)',
                'Mature products only'
            ],
            'limitations': [
                'No early access to trending products',
                'Products already 30+ days old',
                'Higher competition'
            ]
        },
        'starter': {
            'name': 'Starter',
            'price': 29,
            'max_stores': 3,
            'max_products_per_week': 25,
            'product_age_days': 14,
            'phases': ['growth', 'maturity'],
            'features': [
                'Growth-phase products (14+ days)',
                '3 store connections',
                'Full AI analysis',
                'Email automation',
                'Niche specialization',
                'Priority support'
            ],
            'advantages': [
                'Access to growth products',
                '2-week head start vs Free tier',
                'Lower competition'
            ]
        },
        'pro': {
            'name': 'Pro',
            'price': 79,
            'max_stores': 10,
            'max_products_per_week': -1,  # Unlimited
            'product_age_days': 7,
            'phases': ['early_spike', 'growth'],
            'features': [
                'Early spike products (7+ days)',
                '10 store connections',
                'Unlimited products per week',
                'Priority in saturation queue',
                'Custom marketing angles',
                'Advanced analytics',
                'Multi-platform support',
                'API access (basic)'
            ],
            'advantages': [
                'Access to early spike products',
                '1-week head start vs Starter',
                '3-week head start vs Free',
                'Catch products before peak'
            ]
        },
        'elite': {
            'name': 'Elite',
            'price': 199,
            'max_stores': -1,  # Unlimited
            'max_products_per_week': -1,
            'product_age_days': 0,  # Fresh products, any age
            'phases': ['discovery', 'early_spike'],
            'features': [
                'Discovery products (0+ days - FRESH)',
                'First 50 users get NEW products',
                'Unlimited stores',
                'Unlimited products',
                'Real-time trend alerts',
                'AI ad creation',
                'Dedicated support',
                'Full API access',
                'Custom integrations'
            ],
            'advantages': [
                'First access to brand new products',
                'Before anyone else knows about them',
                'Maximum profit potential',
                'Lowest competition'
            ]
        }
    }

    def __init__(self, database_url: str):
        """Initialize TierManager with database connection"""
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

    async def get_user_tier(self, user_id: int) -> str:
        """
        Get user's current tier

        Args:
            user_id: User ID

        Returns:
            Tier name ('free', 'starter', 'pro', 'elite')
        """
        async with self.async_session() as session:
            stmt = select(UserSettings).where(UserSettings.user_id == user_id)
            result = await session.execute(stmt)
            settings = result.scalar_one_or_none()

            if not settings:
                logger.info(f"No settings found for user {user_id}, defaulting to 'free'")
                return 'free'

            # Check if tier expired
            if settings.tier_expires_at and settings.tier_expires_at < datetime.utcnow():
                logger.info(f"Tier expired for user {user_id}, downgrading to 'free'")
                # Update to free tier
                settings.subscription_tier = 'free'
                settings.max_stores = 1
                settings.max_products_per_week = 5
                await session.commit()
                return 'free'

            return settings.subscription_tier or 'free'

    async def upgrade_tier(
        self,
        user_id: int,
        new_tier: str,
        duration_days: int = 30
    ) -> Dict:
        """
        Upgrade user to new tier

        Args:
            user_id: User ID
            new_tier: Target tier ('free', 'starter', 'pro', 'elite')
            duration_days: Subscription duration in days (default: 30)

        Returns:
            Dictionary with success status and tier info
        """
        if new_tier not in self.TIER_FEATURES:
            return {"success": False, "error": f"Invalid tier: {new_tier}"}

        async with self.async_session() as session:
            # Get or create settings
            stmt = select(UserSettings).where(UserSettings.user_id == user_id)
            result = await session.execute(stmt)
            settings = result.scalar_one_or_none()

            if not settings:
                settings = UserSettings(user_id=user_id)
                session.add(settings)

            # Set new tier
            old_tier = settings.subscription_tier or 'free'
            settings.subscription_tier = new_tier
            settings.tier_started_at = datetime.utcnow()
            settings.tier_expires_at = datetime.utcnow() + timedelta(days=duration_days)

            # Update limits
            tier_config = self.TIER_FEATURES[new_tier]
            settings.max_stores = tier_config['max_stores']
            settings.max_products_per_week = tier_config['max_products_per_week']

            await session.commit()

            logger.info(f"Upgraded user {user_id} from {old_tier} to {new_tier}")

            return {
                "success": True,
                "tier": new_tier,
                "old_tier": old_tier,
                "started_at": settings.tier_started_at.isoformat(),
                "expires_at": settings.tier_expires_at.isoformat(),
                "features": tier_config['features'],
                "max_stores": tier_config['max_stores'],
                "max_products_per_week": tier_config['max_products_per_week']
            }

    async def check_tier_limits(
        self,
        user_id: int,
        action: str
    ) -> Dict:
        """
        Check if user can perform action based on tier limits

        Args:
            user_id: User ID
            action: Action to check ('add_store', 'get_products', etc.)

        Returns:
            Dictionary with 'allowed' boolean and optional reason/upgrade_to
        """
        tier = await self.get_user_tier(user_id)
        tier_config = self.TIER_FEATURES[tier]

        async with self.async_session() as session:
            if action == 'add_store':
                # Check store count limit
                stmt = select(Store).where(Store.user_id == user_id)
                result = await session.execute(stmt)
                stores = result.scalars().all()
                store_count = len(stores)

                max_stores = tier_config['max_stores']
                if max_stores != -1 and store_count >= max_stores:
                    # Suggest next tier
                    upgrade_to = 'starter' if tier == 'free' else 'pro' if tier == 'starter' else 'elite'

                    return {
                        "allowed": False,
                        "reason": f"{tier.upper()} tier limited to {max_stores} store{'s' if max_stores != 1 else ''}",
                        "current_count": store_count,
                        "limit": max_stores,
                        "upgrade_to": upgrade_to,
                        "upgrade_benefits": f"{self.TIER_FEATURES[upgrade_to]['name']} allows {self.TIER_FEATURES[upgrade_to]['max_stores']} stores"
                    }

            elif action == 'get_products':
                # Check weekly product limit
                max_products = tier_config['max_products_per_week']

                if max_products != -1:
                    # TODO: Implement weekly product tracking
                    # For now, allow it
                    pass

        return {"allowed": True, "tier": tier}

    async def get_tier_info(self, user_id: int) -> Dict:
        """
        Get complete tier information for a user

        Args:
            user_id: User ID

        Returns:
            Dictionary with current tier, features, limits, and expiry
        """
        tier = await self.get_user_tier(user_id)
        tier_config = self.TIER_FEATURES[tier]

        async with self.async_session() as session:
            stmt = select(UserSettings).where(UserSettings.user_id == user_id)
            result = await session.execute(stmt)
            settings = result.scalar_one_or_none()

            # Get store count
            stmt = select(Store).where(Store.user_id == user_id)
            result = await session.execute(stmt)
            stores = result.scalars().all()
            store_count = len(stores)

            return {
                "tier": tier,
                "tier_name": tier_config['name'],
                "price": tier_config['price'],
                "features": tier_config['features'],
                "advantages": tier_config.get('advantages', []),
                "limitations": tier_config.get('limitations', []),
                "limits": {
                    "max_stores": tier_config['max_stores'],
                    "current_stores": store_count,
                    "max_products_per_week": tier_config['max_products_per_week'],
                    "product_age_days": tier_config['product_age_days'],
                    "allowed_phases": tier_config['phases']
                },
                "subscription": {
                    "started_at": settings.tier_started_at.isoformat() if settings and settings.tier_started_at else None,
                    "expires_at": settings.tier_expires_at.isoformat() if settings and settings.tier_expires_at else None,
                    "is_active": True if not settings or not settings.tier_expires_at or settings.tier_expires_at > datetime.utcnow() else False
                }
            }

    async def get_tier_comparison(self) -> Dict:
        """
        Get comparison of all tiers for upgrade decision

        Returns:
            Dictionary with all tier features for comparison
        """
        comparison = {}

        for tier_key, tier_config in self.TIER_FEATURES.items():
            comparison[tier_key] = {
                "name": tier_config['name'],
                "price": tier_config['price'],
                "price_display": f"${tier_config['price']}/mo" if tier_config['price'] > 0 else "Free",
                "max_stores": tier_config['max_stores'],
                "max_stores_display": "Unlimited" if tier_config['max_stores'] == -1 else str(tier_config['max_stores']),
                "max_products_per_week": tier_config['max_products_per_week'],
                "max_products_display": "Unlimited" if tier_config['max_products_per_week'] == -1 else str(tier_config['max_products_per_week']),
                "product_age_days": tier_config['product_age_days'],
                "product_age_display": f"{tier_config['product_age_days']}+ days old" if tier_config['product_age_days'] > 0 else "Fresh (0+ days)",
                "phases": tier_config['phases'],
                "features": tier_config['features'],
                "advantages": tier_config.get('advantages', []),
                "limitations": tier_config.get('limitations', [])
            }

        return {
            "tiers": comparison,
            "recommended": {
                "beginners": "starter",
                "serious_sellers": "pro",
                "power_users": "elite"
            }
        }

    async def downgrade_expired_tiers(self) -> List[int]:
        """
        Background job to downgrade users with expired tiers

        Returns:
            List of user IDs that were downgraded
        """
        downgraded_users = []

        async with self.async_session() as session:
            # Find users with expired tiers
            stmt = select(UserSettings).where(
                UserSettings.tier_expires_at < datetime.utcnow(),
                UserSettings.subscription_tier != 'free'
            )
            result = await session.execute(stmt)
            expired_settings = result.scalars().all()

            for settings in expired_settings:
                logger.info(f"Downgrading user {settings.user_id} from {settings.subscription_tier} to free (expired)")

                settings.subscription_tier = 'free'
                settings.max_stores = 1
                settings.max_products_per_week = 5

                downgraded_users.append(settings.user_id)

            await session.commit()

        logger.info(f"Downgraded {len(downgraded_users)} users with expired tiers")
        return downgraded_users

    async def close(self):
        """Close database connections"""
        await self.engine.dispose()
