"""
[WARNING] DEPRECATED - Use ospra_os.core.tiers instead

This file is maintained for backward compatibility only.
All tier logic has been unified in ospra_os.core.tiers.

Migration:
    # OLD (deprecated)
    from ospra_os.subscription.tier_manager import TierManager

    # NEW (use this)
    from ospra_os.core import SubscriptionTier, TierEnforcer, get_tier_feature
"""

import warnings
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import from new unified system
from ospra_os.core.tiers import (
    SubscriptionTier,
    TIER_DEFINITIONS,
    get_tier_definition,
    get_tier_feature,
    get_pricing_table,
)

logger = logging.getLogger(__name__)


# ==================== LEGACY TIER FEATURES (for compatibility) ====================

TIER_FEATURES = {
    'nest': {
        'name': 'Nest',
        'price': 0,
        'max_stores': 1,
        'max_products_per_week': 10,
        'product_age_days': None,
        'phases': ['all'],
        'features': TIER_DEFINITIONS[SubscriptionTier.NEST]['features'],
    },
    'flight': {
        'name': 'Flight',
        'price': 29,
        'max_stores': 1,
        'max_products_per_week': 50,
        'product_age_days': None,
        'phases': ['all'],
        'features': TIER_DEFINITIONS[SubscriptionTier.FLIGHT]['features'],
    },
    'soar': {
        'name': 'Soar',
        'price': 79,
        'max_stores': 5,
        'max_products_per_week': -1,  # Unlimited
        'product_age_days': None,
        'phases': ['all'],
        'features': TIER_DEFINITIONS[SubscriptionTier.SOAR]['features'],
    },
    'stratosphere': {
        'name': 'Stratosphere',
        'price': 199,
        'max_stores': -1,  # Unlimited
        'max_products_per_week': -1,
        'product_age_days': None,
        'phases': ['all'],
        'features': TIER_DEFINITIONS[SubscriptionTier.STRATOSPHERE]['features'],
    },
    # Legacy aliases
    'free': {
        'name': 'Nest',
        'price': 0,
        'max_stores': 1,
        'max_products_per_week': 10,
    },
    'starter': {
        'name': 'Flight',
        'price': 29,
        'max_stores': 1,
        'max_products_per_week': 50,
    },
    'pro': {
        'name': 'Soar',
        'price': 79,
        'max_stores': 5,
        'max_products_per_week': -1,
    },
    'elite': {
        'name': 'Stratosphere',
        'price': 199,
        'max_stores': -1,
        'max_products_per_week': -1,
    },
}


# ==================== LEGACY TIER MAPPING ====================

_LEGACY_TO_NEW = {
    'free': 'nest',
    'starter': 'flight',
    'pro': 'soar',
    'elite': 'stratosphere',
}


class TierManager:
    """
    [WARNING] DEPRECATED - Use TierEnforcer from ospra_os.core.tiers instead
    
    This class wraps the new tier system for backward compatibility.
    """
    
    TIER_FEATURES = TIER_FEATURES
    
    def __init__(self, database_url: str = None):
        warnings.warn(
            "TierManager is deprecated. Use TierEnforcer from ospra_os.core.tiers instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.database_url = database_url
        self.engine = None
        self.async_session = None
        
        if database_url:
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
    
    def _normalize_tier(self, tier: str) -> str:
        """Convert legacy tier names to new names"""
        return _LEGACY_TO_NEW.get(tier.lower(), tier.lower())
    
    async def get_user_tier(self, user_id: int) -> str:
        """Get user's current tier"""
        warnings.warn(
            "get_user_tier is deprecated. Access user.subscription_tier directly.",
            DeprecationWarning,
            stacklevel=2
        )
        
        if not self.async_session:
            return 'nest'
        
        from ospra_os.database import UserSettings
        
        async with self.async_session() as session:
            stmt = select(UserSettings).where(UserSettings.user_id == user_id)
            result = await session.execute(stmt)
            settings = result.scalar_one_or_none()
            
            if not settings:
                return 'nest'
            
            # Check expiration
            if settings.tier_expires_at and settings.tier_expires_at < datetime.now(timezone.utc):
                settings.subscription_tier = 'nest'
                settings.max_stores = 1
                settings.max_products_per_week = 10
                await session.commit()
                return 'nest'
            
            return self._normalize_tier(settings.subscription_tier or 'nest')
    
    # T44: upgrade_tier was DELETED. It was already deprecated, had zero
    # callers, and set any tier with no payment proof. Tier changes flow
    # exclusively through verified payment events:
    # /api/user/upgrade → LemonSqueezy checkout → webhook → dispatch_tier_change.

    async def check_tier_limits(self, user_id: int, action: str) -> Dict:
        """Check if user can perform action based on tier limits"""
        tier = await self.get_user_tier(user_id)
        tier_config = TIER_FEATURES.get(tier, TIER_FEATURES['nest'])
        
        if action == 'add_store':
            max_stores = tier_config['max_stores']
            if max_stores == -1:
                return {"allowed": True, "tier": tier}
            
            # Check current store count
            from ospra_os.database import Store
            
            if self.async_session:
                async with self.async_session() as session:
                    stmt = select(Store).where(Store.user_id == user_id)
                    result = await session.execute(stmt)
                    stores = result.scalars().all()
                    
                    if len(stores) >= max_stores:
                        next_tier = 'soar' if tier == 'flight' else 'stratosphere'
                        return {
                            "allowed": False,
                            "reason": f"{tier.upper()} tier limited to {max_stores} store(s)",
                            "current_count": len(stores),
                            "limit": max_stores,
                            "upgrade_to": next_tier,
                        }
        
        return {"allowed": True, "tier": tier}
    
    async def get_tier_info(self, user_id: int) -> Dict:
        """Get complete tier information for a user"""
        tier = await self.get_user_tier(user_id)
        tier_config = TIER_FEATURES.get(tier, TIER_FEATURES['nest'])
        
        return {
            "tier": tier,
            "tier_name": tier_config['name'],
            "price": tier_config['price'],
            "features": tier_config.get('features', []),
            "limits": {
                "max_stores": tier_config['max_stores'],
                "max_products_per_week": tier_config['max_products_per_week'],
            },
        }
    
    async def get_tier_comparison(self) -> Dict:
        """Get comparison of all tiers"""
        return {
            "tiers": {
                tier: {
                    "name": config["name"],
                    "price": config["price"],
                    "price_display": f"${config['price']}/mo" if config["price"] > 0 else "Free",
                    "max_stores": config["max_stores"],
                    "max_stores_display": "Unlimited" if config["max_stores"] == -1 else str(config["max_stores"]),
                    "features": config.get("features", []),
                }
                for tier, config in TIER_FEATURES.items()
                if tier in ['nest', 'flight', 'soar', 'stratosphere']
            }
        }
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()


# ==================== MIGRATION GUIDE ====================

MIGRATION_GUIDE = """

              TIER MANAGER MIGRATION GUIDE                        

                                                                  
  This file is DEPRECATED. Please migrate to the new system:     
                                                                  
  OLD (deprecated):                                               
    from ospra_os.subscription.tier_manager import TierManager    
    manager = TierManager(database_url)                           
    tier = await manager.get_user_tier(user_id)                   
                                                                  
  NEW (use this):                                                 
    from ospra_os.core import (                                   
        SubscriptionTier,                                         
        TierEnforcer,                                             
        get_tier_definition,                                      
    )                                                             
                                                                  
    # Get tier from user model directly                           
    user_tier = user.subscription_tier                            
                                                                  
    # Use enforcer for access control                             
    enforcer = TierEnforcer(user_tier)                            
    if enforcer.can_access('personal_learning'):                  
        # Enable personal learning                                
                                                                  
  Tier name mappings:                                             
    free    →  nest                                               
    starter →  flight                                             
    pro     →  soar                                               
    elite   →  stratosphere                                       
                                                                  

"""

if __name__ == "__main__":
    print(MIGRATION_GUIDE)
