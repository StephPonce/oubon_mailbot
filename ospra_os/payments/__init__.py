"""
Ospra Intelligence - Payments Module
====================================
Sky/Flight themed subscription tiers: Nest → Flight → Soar → Stratosphere

Supports both:
- LemonSqueezy (recommended for MVP - simpler, handles taxes)
- Stripe (for when you need lower fees at scale)
"""
from .lemonsqueezy import (
    SubscriptionTier,
    TIER_DEFINITIONS,
    TIER_HIERARCHY,
    LemonSqueezyClient,
    get_pricing_table,
    get_tier_from_variant,
    get_variant_for_tier,
    compare_tiers,
    tier_has_feature,
    get_tier_limit,
    verify_webhook_signature,
    handle_webhook_event,
    get_setup_instructions
)

__all__ = [
    # Tier definitions
    "SubscriptionTier",
    "TIER_DEFINITIONS", 
    "TIER_HIERARCHY",
    
    # LemonSqueezy
    "LemonSqueezyClient",
    
    # Helpers
    "get_pricing_table",
    "get_tier_from_variant",
    "get_variant_for_tier",
    "compare_tiers",
    "tier_has_feature",
    "get_tier_limit",
    
    # Webhooks
    "verify_webhook_signature",
    "handle_webhook_event",
    
    # Setup
    "get_setup_instructions"
]
