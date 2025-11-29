"""
TIER SYSTEM - SIMPLE PAID TIERS

Simple 3-tier system with clear feature gating.

Tiers:
- Starter ($29/mo): 10 products, basic features
- Pro ($99/mo): 50 products, full features + automation
- Enterprise ($299/mo): Unlimited, white-glove support

Features are enforced at API level, not frontend (frontend just hides unavailable features).
"""

import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class Tier(str, Enum):
    """Subscription tiers"""
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class TierSystem:
    """
    Manages subscription tiers and feature access.

    Features gated by tier:
    - Product limits
    - AI briefing frequency
    - Auto-actions
    - Priority support
    - API rate limits
    """

    # Tier pricing (monthly)
    PRICING = {
        Tier.STARTER: 29,
        Tier.PRO: 99,
        Tier.ENTERPRISE: 299
    }

    # Feature limits by tier
    LIMITS = {
        Tier.STARTER: {
            "max_products": 10,
            "ai_briefings_per_day": 1,
            "auto_actions_per_day": 0,
            "api_calls_per_hour": 100,
            "stores": 1,
            "ad_campaigns": 3,
            "email_automation_rules": 5,
            "competitor_tracking": 5
        },
        Tier.PRO: {
            "max_products": 50,
            "ai_briefings_per_day": 5,
            "auto_actions_per_day": 10,
            "api_calls_per_hour": 1000,
            "stores": 3,
            "ad_campaigns": 20,
            "email_automation_rules": 50,
            "competitor_tracking": 25
        },
        Tier.ENTERPRISE: {
            "max_products": -1,  # Unlimited
            "ai_briefings_per_day": -1,
            "auto_actions_per_day": -1,
            "api_calls_per_hour": -1,
            "stores": -1,
            "ad_campaigns": -1,
            "email_automation_rules": -1,
            "competitor_tracking": -1
        }
    }

    # Features available by tier (boolean)
    FEATURES = {
        Tier.STARTER: {
            "product_discovery": True,
            "ai_grading": True,
            "manual_deploy": True,
            "basic_analytics": True,
            "email_support": True,
            # Limited
            "ai_briefings": False,
            "auto_deploy": False,
            "ad_automation": False,
            "competitor_monitoring": False,
            "priority_support": False,
            "white_glove_onboarding": False,
            "custom_integrations": False
        },
        Tier.PRO: {
            "product_discovery": True,
            "ai_grading": True,
            "manual_deploy": True,
            "basic_analytics": True,
            "email_support": True,
            # PRO features
            "ai_briefings": True,
            "auto_deploy": True,
            "ad_automation": True,
            "competitor_monitoring": True,
            "priority_support": True,
            # Still limited
            "white_glove_onboarding": False,
            "custom_integrations": False
        },
        Tier.ENTERPRISE: {
            # ALL features
            "product_discovery": True,
            "ai_grading": True,
            "manual_deploy": True,
            "basic_analytics": True,
            "email_support": True,
            "ai_briefings": True,
            "auto_deploy": True,
            "ad_automation": True,
            "competitor_monitoring": True,
            "priority_support": True,
            "white_glove_onboarding": True,
            "custom_integrations": True
        }
    }

    def __init__(self, db: Session):
        self.db = db

    async def get_user_tier(self, user_id: int) -> Tier:
        """Get user's current subscription tier"""
        from ospra_os.database.multi_store_models import User, SubscriptionTier

        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Map enum to Tier
        tier_mapping = {
            SubscriptionTier.STARTER: Tier.STARTER,
            SubscriptionTier.PRO: Tier.PRO,
            SubscriptionTier.ENTERPRISE: Tier.ENTERPRISE,
            SubscriptionTier.FREE: Tier.STARTER  # FREE = STARTER
        }

        return tier_mapping.get(user.subscription_tier, Tier.STARTER)

    async def check_feature_access(
        self,
        user_id: int,
        feature: str
    ) -> bool:
        """
        Check if user has access to feature.

        Args:
            user_id: User ID
            feature: Feature name (e.g., "ai_briefings", "auto_deploy")

        Returns:
            True if user has access, False otherwise
        """
        tier = await self.get_user_tier(user_id)
        return self.FEATURES[tier].get(feature, False)

    async def check_limit(
        self,
        user_id: int,
        limit_type: str,
        current_usage: int
    ) -> Dict[str, Any]:
        """
        Check if user has exceeded limit.

        Args:
            user_id: User ID
            limit_type: Limit type (e.g., "max_products", "ai_briefings_per_day")
            current_usage: Current usage count

        Returns:
            {
                "allowed": true/false,
                "limit": 50,
                "current": 45,
                "remaining": 5,
                "exceeded": false
            }
        """
        tier = await self.get_user_tier(user_id)
        limit = self.LIMITS[tier].get(limit_type, 0)

        # -1 means unlimited
        if limit == -1:
            return {
                "allowed": True,
                "limit": -1,
                "current": current_usage,
                "remaining": -1,
                "exceeded": False
            }

        exceeded = current_usage >= limit
        remaining = max(0, limit - current_usage)

        return {
            "allowed": not exceeded,
            "limit": limit,
            "current": current_usage,
            "remaining": remaining,
            "exceeded": exceeded
        }

    async def get_tier_info(self, user_id: int) -> Dict[str, Any]:
        """
        Get complete tier information for user.

        Returns:
            {
                "tier": "pro",
                "price": 99,
                "features": {...},
                "limits": {...},
                "usage": {...}
            }
        """
        tier = await self.get_user_tier(user_id)

        # Get current usage
        usage = await self._get_current_usage(user_id)

        return {
            "tier": tier.value,
            "price": self.PRICING[tier],
            "features": self.FEATURES[tier],
            "limits": self.LIMITS[tier],
            "usage": usage,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _get_current_usage(self, user_id: int) -> Dict[str, int]:
        """Get current usage counts for user"""
        from ospra_os.database.multi_store_models import Product, Store, MetaAdCampaign

        # Count products
        product_count = self.db.query(Product).join(Store).filter(
            Store.user_id == user_id
        ).count()

        # Count stores
        store_count = self.db.query(Store).filter(Store.user_id == user_id).count()

        # Count ad campaigns
        campaign_count = self.db.query(MetaAdCampaign).join(Store).filter(
            Store.user_id == user_id
        ).count()

        return {
            "products": product_count,
            "stores": store_count,
            "ad_campaigns": campaign_count,
            "ai_briefings_today": 0,  # Would track in separate table
            "auto_actions_today": 0,   # Would track in separate table
            "api_calls_this_hour": 0  # Would track with rate limiter
        }

    async def upgrade_tier(
        self,
        user_id: int,
        new_tier: Tier,
        payment_method_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upgrade user to new tier.

        In production, this would:
        1. Charge payment method
        2. Update subscription in Stripe/payment provider
        3. Update user tier in database
        4. Send confirmation email

        For now, just updates tier.
        """
        from ospra_os.database.multi_store_models import User, SubscriptionTier

        logger.info(f"Upgrading user {user_id} to {new_tier.value}")

        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Map Tier to SubscriptionTier enum
        tier_mapping = {
            Tier.STARTER: SubscriptionTier.STARTER,
            Tier.PRO: SubscriptionTier.PRO,
            Tier.ENTERPRISE: SubscriptionTier.ENTERPRISE
        }

        user.subscription_tier = tier_mapping[new_tier]
        user.updated_at = datetime.utcnow()

        self.db.commit()

        logger.info(f"User {user_id} upgraded to {new_tier.value}")

        return {
            "success": True,
            "new_tier": new_tier.value,
            "price": self.PRICING[new_tier],
            "message": f"Successfully upgraded to {new_tier.value.title()}",
            "timestamp": datetime.utcnow().isoformat()
        }


# Singleton instance
_tier_system = None


def get_tier_system(db: Session) -> TierSystem:
    """Get or create tier system instance"""
    global _tier_system
    if _tier_system is None:
        _tier_system = TierSystem(db)
    return _tier_system
