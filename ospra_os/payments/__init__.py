"""
Ospra Intelligence - Payments Module
====================================

LemonSqueezy integration for subscription management.

Tier definitions are imported from ospra_os.core.tiers (single source of truth).

Sky/Flight themed subscription tiers: Nest → Flight → Soar → Stratosphere
"""

# Import tier system from core (single source of truth)
from ospra_os.core.tiers import (
    SubscriptionTier,
    TIER_DEFINITIONS,
    TIER_HIERARCHY,
    get_pricing_table,
    compare_tiers,
    tier_has_feature,
    get_tier_limit,
)

# LemonSqueezy specific
from .lemonsqueezy import (
    LemonSqueezyClient,
    get_tier_from_variant,
    get_variant_for_tier,
    get_checkout_url_for_tier,
    verify_webhook_signature,
    handle_webhook_event,
    get_setup_instructions,
)

# Routes
from .routes import router as payments_router

__all__ = [
    # Tier definitions (from core)
    "SubscriptionTier",
    "TIER_DEFINITIONS", 
    "TIER_HIERARCHY",
    "get_pricing_table",
    "compare_tiers",
    "tier_has_feature",
    "get_tier_limit",
    
    # LemonSqueezy
    "LemonSqueezyClient",
    "get_tier_from_variant",
    "get_variant_for_tier",
    "get_checkout_url_for_tier",
    
    # Webhooks
    "verify_webhook_signature",
    "handle_webhook_event",
    
    # Setup
    "get_setup_instructions",
    
    # FastAPI Router
    "payments_router",
]
