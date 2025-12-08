"""
Ospra Core Module
=================

Central definitions for the entire application.
Single source of truth for tiers, configurations, and shared utilities.
"""

# Tier system exports
from ospra_os.core.tiers import (
    SubscriptionTier,
    TIER_HIERARCHY,
    TIER_DEFINITIONS,
    get_tier_definition,
    get_tier_feature,
    tier_has_feature,
    get_tier_limit,
    compare_tiers,
    tier_at_least,
    get_upgrade_path,
    get_pricing_table,
    get_tier_comparison_matrix,
    TierEnforcer,
    log_tier_access,
)

# Usage tracking exports
from ospra_os.core.usage_tracking import (
    UsageTracker,
    TierUsageEnforcer,
    UsageType,
    get_tracker,
    get_enforcer,
)

__all__ = [
    # Tier enum
    "SubscriptionTier",
    
    # Tier definitions
    "TIER_HIERARCHY",
    "TIER_DEFINITIONS",
    
    # Tier helpers
    "get_tier_definition",
    "get_tier_feature",
    "tier_has_feature",
    "get_tier_limit",
    "compare_tiers",
    "tier_at_least",
    "get_upgrade_path",
    "get_pricing_table",
    "get_tier_comparison_matrix",
    
    # Tier enforcement
    "TierEnforcer",
    "log_tier_access",
    
    # Usage tracking
    "UsageTracker",
    "TierUsageEnforcer",
    "UsageType",
    "get_tracker",
    "get_enforcer",
]


# ==================== VERSION ====================

__version__ = "2.1.0"  # Added usage tracking


# ==================== QUICK REFERENCE ====================

TIER_QUICK_REF = """
╔══════════════════════════════════════════════════════════════════╗
║                    OSPRA TIER QUICK REFERENCE                    ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  🪺 NEST (Free)       - See what's possible                      ║
║  ✈️ FLIGHT ($29/mo)   - Start selling smarter                   ║
║  🦅 SOAR ($79/mo)     - Run your business, not just a store     ║
║  🌌 STRATOSPHERE ($199) - Your AI-powered operations team       ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Usage Examples:                                                 ║
║                                                                  ║
║  from ospra_os.core import (                                     ║
║      SubscriptionTier,                                           ║
║      TierEnforcer,                                               ║
║      get_tier_feature,                                           ║
║      TierUsageEnforcer,                                          ║
║      get_enforcer,                                               ║
║  )                                                               ║
║                                                                  ║
║  # Check if user can perform action (with usage tracking)        ║
║  enforcer = get_enforcer(db_session)                             ║
║  result = enforcer.can_perform(user_id=1, action="aliexpress_search")
║  if result["allowed"]:                                           ║
║      enforcer.record_action(user_id=1, action="aliexpress_search")
║      perform_search()                                            ║
║  else:                                                           ║
║      show_upgrade_prompt(result["upgrade_suggestion"])           ║
║                                                                  ║
║  # Get usage dashboard                                           ║
║  dashboard = enforcer.get_usage_dashboard(user_id=1)             ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""
