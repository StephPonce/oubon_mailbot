"""
[WARNING] DEPRECATED - Use ospra_os.core.tiers instead

This file is maintained for backward compatibility only.
All tier logic has been unified in ospra_os.core.tiers.

Migration:
    # OLD (deprecated)
    from ospra_os.intelligence.tier_system import Tier, TierSystem

    # NEW (use this)
    from ospra_os.core import SubscriptionTier, TierEnforcer, get_tier_feature
"""

import warnings
import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
from sqlalchemy.orm import Session

# Import from new unified system
from ospra_os.core.tiers import (
    SubscriptionTier,
    TIER_DEFINITIONS,
    TIER_HIERARCHY,
    get_tier_definition,
    get_tier_feature,
    tier_has_feature,
    get_tier_limit,
    TierEnforcer,
)

logger = logging.getLogger(__name__)


# ==================== DEPRECATED ALIASES ====================

class Tier(str, Enum):
    """
    [WARNING] DEPRECATED - Use SubscriptionTier from ospra_os.core.tiers
    
    Legacy tier enum kept for backward compatibility.
    """
    STARTER = "flight"      # Maps to FLIGHT
    PRO = "soar"            # Maps to SOAR
    ENTERPRISE = "stratosphere"  # Maps to STRATOSPHERE


# Map old tier names to new
_OLD_TO_NEW_TIER = {
    Tier.STARTER: SubscriptionTier.FLIGHT,
    Tier.PRO: SubscriptionTier.SOAR,
    Tier.ENTERPRISE: SubscriptionTier.STRATOSPHERE,
    "starter": SubscriptionTier.FLIGHT,
    "pro": SubscriptionTier.SOAR,
    "enterprise": SubscriptionTier.STRATOSPHERE,
    "free": SubscriptionTier.NEST,
}


def _convert_tier(old_tier) -> SubscriptionTier:
    """Convert old tier to new tier"""
    if isinstance(old_tier, SubscriptionTier):
        return old_tier
    return _OLD_TO_NEW_TIER.get(old_tier, SubscriptionTier.NEST)


class TierSystem:
    """
    [WARNING] DEPRECATED - Use TierEnforcer from ospra_os.core.tiers
    
    This class wraps the new TierEnforcer for backward compatibility.
    """
    
    # Legacy pricing (kept for compatibility)
    PRICING = {
        Tier.STARTER: 29,
        Tier.PRO: 79,
        Tier.ENTERPRISE: 199
    }
    
    def __init__(self, db: Session = None):
        warnings.warn(
            "TierSystem is deprecated. Use TierEnforcer from ospra_os.core.tiers instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.db = db
    
    async def get_user_tier(self, user_id: int) -> Tier:
        """Get user's current subscription tier"""
        warnings.warn(
            "get_user_tier is deprecated. Access user.subscription_tier directly.",
            DeprecationWarning,
            stacklevel=2
        )
        
        if not self.db:
            return Tier.STARTER
        
        from ospra_os.database import User
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Map new tier to old tier enum
        tier_mapping = {
            "nest": Tier.STARTER,  # Free maps to starter in old system
            "flight": Tier.STARTER,
            "soar": Tier.PRO,
            "stratosphere": Tier.ENTERPRISE,
        }
        
        tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
        return tier_mapping.get(tier_value, Tier.STARTER)
    
    async def check_feature_access(self, user_id: int, feature: str) -> bool:
        """Check if user has access to feature"""
        warnings.warn(
            "check_feature_access is deprecated. Use TierEnforcer.can_access() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        tier = await self.get_user_tier(user_id)
        new_tier = _convert_tier(tier)
        return tier_has_feature(new_tier, feature)
    
    async def check_limit(self, user_id: int, limit_type: str, current_usage: int) -> Dict[str, Any]:
        """Check if user has exceeded limit"""
        warnings.warn(
            "check_limit is deprecated. Use TierEnforcer.within_limit() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        tier = await self.get_user_tier(user_id)
        new_tier = _convert_tier(tier)
        limit = get_tier_limit(new_tier, limit_type)
        
        if limit == -1:
            return {"allowed": True, "limit": -1, "current": current_usage, "remaining": -1, "exceeded": False}
        
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
        """Get complete tier information for user"""
        tier = await self.get_user_tier(user_id)
        new_tier = _convert_tier(tier)
        tier_def = get_tier_definition(new_tier)
        
        return {
            "tier": new_tier.value,
            "tier_name": tier_def.get("name"),
            "price": tier_def.get("price"),
            "features": tier_def.get("features", []),
            "timestamp": datetime.utcnow().isoformat()
        }


# ==================== BACKWARD COMPATIBLE EXPORTS ====================

# Legacy singleton pattern
_tier_system = None


def get_tier_system(db: Session = None) -> TierSystem:
    """
    [WARNING] DEPRECATED - Use TierEnforcer from ospra_os.core.tiers instead
    """
    warnings.warn(
        "get_tier_system is deprecated. Use TierEnforcer from ospra_os.core.tiers instead.",
        DeprecationWarning,
        stacklevel=2
    )
    global _tier_system
    if _tier_system is None:
        _tier_system = TierSystem(db)
    return _tier_system


# ==================== MIGRATION GUIDE ====================

MIGRATION_GUIDE = """

              TIER SYSTEM MIGRATION GUIDE                         

                                                                  
  This file is DEPRECATED. Please migrate to the new system:     
                                                                  
  OLD (deprecated):                                               
    from ospra_os.intelligence.tier_system import Tier, TierSystem
    tier_system = TierSystem(db)                                  
    await tier_system.check_feature_access(user_id, 'feature')    
                                                                  
  NEW (use this):                                                 
    from ospra_os.core import (                                   
        SubscriptionTier,                                         
        TierEnforcer,                                             
        get_tier_feature,                                         
        tier_has_feature,                                         
    )                                                             
                                                                  
    enforcer = TierEnforcer(user_tier=SubscriptionTier.SOAR)     
    if enforcer.can_access('feature'):                            
        # do something                                            
                                                                  
  Tier name mappings:                                             
    STARTER    →  FLIGHT ($29)                                   
    PRO        →  SOAR ($79)                                     
    ENTERPRISE →  STRATOSPHERE ($199)                            
    FREE       →  NEST ($0)                                      
                                                                  

"""

if __name__ == "__main__":
    print(MIGRATION_GUIDE)
