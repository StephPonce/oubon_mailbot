"""
OSPRA INTELLIGENCE - Unified Tier System
========================================

Single source of truth for ALL tier definitions, features, and limits.

Sky/Flight themed subscription tiers: Nest → Flight → Soar → Stratosphere

Theme: Journey from grounded to the stars
-  Nest: Grounded, watching, learning (Free)
-  Flight: Taken off, building momentum ($29)
-  Soar: High altitude, seeing what others can't ($79)
-  Stratosphere: Edge of space, first to everything ($199)

IMPORT THIS FILE - Don't define tiers anywhere else!
"""

from enum import Enum
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


# ==================== TIER ENUM ====================

class SubscriptionTier(str, Enum):
    """
    Ospra subscription tiers - Sky/flight theme
    
    The journey of an Osprey:
     Nest → Just hatched, learning the world (Free)
     Flight → First flight, building confidence ($29)
     Soar → Mastery, riding thermals effortlessly ($79)
     Stratosphere → Beyond limits, touching the stars ($199)
    """
    NEST = "nest"
    FLIGHT = "flight"
    SOAR = "soar"
    STRATOSPHERE = "stratosphere"


# Tier hierarchy for comparison (higher = better)
TIER_HIERARCHY = {
    SubscriptionTier.NEST: 0,
    SubscriptionTier.FLIGHT: 1,
    SubscriptionTier.SOAR: 2,
    SubscriptionTier.STRATOSPHERE: 3,
}


# ==================== COMPLETE TIER DEFINITIONS ====================

TIER_DEFINITIONS: Dict[SubscriptionTier, Dict[str, Any]] = {
    
    # 
    #  NEST (FREE) - "See What's Possible"
    # 
    SubscriptionTier.NEST: {
        "name": "Nest",
        "tagline": "See what's possible.",
        "description": "Get a taste of Ospra's product intelligence. Perfect for exploring.",
        "emoji": "",
        "price": 0,
        "price_display": "Free",
        "color": "#8B7355",  # Earthy brown
        
        #  Product Discovery 
        "products_per_week": 10,
        "search_filters": "basic",  # Basic only
        "ai_score": False,
        "ai_score_reasoning": False,
        "saturation_indicator": False,
        "trend_velocity": False,
        "niche_analysis": False,
        
        #  Intelligence & Learning 
        "global_brain": "basic",  # Basic global insights
        "anonymized_success_rates": False,
        "personal_learning": False,
        "accelerated_learning": False,
        "custom_weights": False,
        "ai_briefings": False,
        "ai_briefing_frequency": None,
        "drop_product_alerts": False,
        "competitor_monitoring": False,
        
        #  Store Operations 
        "store_limit": 1,
        "one_click_deploy": False,
        "bulk_deploy": False,
        "ai_listing_copy": False,
        "ai_pricing_suggestions": False,
        
        #  Order Fulfillment 
        "fulfillment_method": "manual",  # manual, affiliate, auto
        "affiliate_links": False,
        "affiliate_commission": False,
        "order_tracking_sync": False,
        "auto_ordering": False,
        
        #  Prophecizer (Inventory) 
        "real_time_stock": False,
        "days_until_stockout": False,
        "low_stock_alerts": False,
        "low_stock_alert_channels": [],
        "restock_recommendations": False,
        "auto_restock_request": False,
        "seasonality_adjustments": False,
        "revenue_at_risk": False,
        "supplier_quality_monitoring": False,
        
        #  Email Automation 
        "email_templates": 0,
        "ai_draft_replies": False,
        "quiet_hours_routing": False,
        "order_lookup_in_replies": False,
        "auto_classification": False,
        
        #  Advertising 
        "ai_ad_copy": False,
        "ad_platform_connections": False,
        "ad_scheduling": False,
        "ad_budget_management": False,
        "cross_platform_analytics": False,
        
        #  AliExpress Integration 
        "aliexpress_search_results_limit": 50,
        "aliexpress_searches_per_day": 10,
        "aliexpress_enrichment": False,  # Dropshipping API enrichment
        "aliexpress_auto_ordering": False,
        
        #  Support & Team 
        "support_type": "community",
        "support_response_time": None,
        "team_seats": 1,
        "dedicated_manager": False,
        
        #  Feature Lists for UI 
        "features": [
            "10 curated products per week",
            "Basic search filters",
            "1 Shopify store",
            "Global Brain basic insights",
            "Community support"
        ],
        "limitations": [
            "No AI scoring or analysis",
            "No saturation data",
            "No one-click deploy",
            "No email automation",
            "No ad features",
            "No inventory monitoring"
        ]
    },
    
    # 
    #  FLIGHT ($29) - "Start Selling Smarter"
    # 
    SubscriptionTier.FLIGHT: {
        "name": "Flight",
        "tagline": "Start selling smarter.",
        "description": "Everything you need to launch your first store with intelligence.",
        "emoji": "",
        "price": 29,
        "price_display": "$29/month",
        "color": "#87CEEB",  # Sky blue
        
        #  Product Discovery 
        "products_per_week": 50,
        "search_filters": "full",
        "ai_score": True,
        "ai_score_reasoning": False,  # Just the number, no explanation
        "saturation_indicator": "basic",  #  only
        "trend_velocity": False,
        "niche_analysis": False,
        
        #  Intelligence & Learning 
        "global_brain": "full",
        "anonymized_success_rates": True,  # "73% of sellers succeeded"
        "personal_learning": False,
        "accelerated_learning": False,
        "custom_weights": False,
        "ai_briefings": False,
        "ai_briefing_frequency": None,
        "drop_product_alerts": False,
        "competitor_monitoring": False,
        
        #  Store Operations 
        "store_limit": 1,
        "one_click_deploy": True,
        "bulk_deploy": False,
        "ai_listing_copy": "basic",
        "ai_pricing_suggestions": False,
        
        #  Order Fulfillment 
        "fulfillment_method": "affiliate",
        "affiliate_links": True,
        "affiliate_commission": "5-10%",
        "order_tracking_sync": False,
        "auto_ordering": False,
        
        #  Prophecizer (Inventory) 
        "real_time_stock": False,
        "days_until_stockout": False,
        "low_stock_alerts": False,
        "low_stock_alert_channels": [],
        "restock_recommendations": False,
        "auto_restock_request": False,
        "seasonality_adjustments": False,
        "revenue_at_risk": False,
        "supplier_quality_monitoring": False,
        
        #  Email Automation 
        "email_templates": 5,
        "ai_draft_replies": False,
        "quiet_hours_routing": False,
        "order_lookup_in_replies": False,
        "auto_classification": False,
        
        #  Advertising 
        "ai_ad_copy": "basic",
        "ad_platform_connections": False,
        "ad_scheduling": False,
        "ad_budget_management": False,
        "cross_platform_analytics": False,
        
        #  AliExpress Integration 
        "aliexpress_search_results_limit": 100,
        "aliexpress_searches_per_day": 50,
        "aliexpress_enrichment": False,
        "aliexpress_auto_ordering": False,
        
        #  Support & Team 
        "support_type": "email",
        "support_response_time": "48hr",
        "team_seats": 1,
        "dedicated_manager": False,
        
        #  Feature Lists for UI 
        "features": [
            "50 curated products per week",
            "Full search & filters",
            "AI Score (1-10) for each product",
            "Basic saturation indicator ()",
            "1 Shopify store",
            "One-click deploy to Shopify",
            "Basic AI listing copy",
            "Global Brain full insights",
            "Success rate data from all Ospra users",
            "Affiliate links (earn 5-10% commission)",
            "5 email templates",
            "Basic AI ad copy generator",
            "48hr email support"
        ],
        "limitations": [
            "No AI score reasoning",
            "No trend velocity alerts",
            "No personal AI learning",
            "No inventory monitoring",
            "No full email automation",
            "No ad platform control"
        ]
    },
    
    # 
    #  SOAR ($79) - "Run Your Business, Not Just a Store" [STAR] POPULAR
    # 
    SubscriptionTier.SOAR: {
        "name": "Soar",
        "tagline": "Run your business, not just a store.",
        "description": "Full automation suite for serious sellers. This is where businesses scale.",
        "emoji": "",
        "price": 79,
        "price_display": "$79/month",
        "color": "#0EA5E9",  # Bright blue
        "popular": True,  # Mark as most popular
        
        #  Product Discovery 
        "products_per_week": -1,  # Unlimited
        "search_filters": "full_saved",  # Full + saved searches
        "ai_score": True,
        "ai_score_reasoning": True,  # Full reasoning
        "saturation_indicator": "exact",  # Exact count
        "trend_velocity": True,
        "niche_analysis": "weekly",
        
        #  Intelligence & Learning 
        "global_brain": "full",
        "anonymized_success_rates": True,
        "personal_learning": True,  # [HOT] AI learns from YOUR sales
        "accelerated_learning": False,
        "custom_weights": False,
        "ai_briefings": True,
        "ai_briefing_frequency": "weekly",
        "drop_product_alerts": True,
        "competitor_monitoring": False,
        
        #  Store Operations 
        "store_limit": 5,
        "one_click_deploy": True,
        "bulk_deploy": False,
        "ai_listing_copy": "full_seo",
        "ai_pricing_suggestions": True,
        
        #  Order Fulfillment 
        "fulfillment_method": "affiliate",
        "affiliate_links": True,
        "affiliate_commission": "5-10%",
        "order_tracking_sync": True,
        "auto_ordering": False,
        
        #  Prophecizer (Inventory) [HOT] 
        "real_time_stock": True,
        "days_until_stockout": True,
        "low_stock_alerts": True,
        "low_stock_alert_channels": ["email"],
        "restock_recommendations": True,
        "auto_restock_request": False,
        "seasonality_adjustments": False,
        "revenue_at_risk": False,
        "supplier_quality_monitoring": False,
        
        #  Email Automation [HOT] 
        "email_templates": -1,  # Unlimited
        "ai_draft_replies": True,
        "quiet_hours_routing": True,
        "order_lookup_in_replies": True,
        "auto_classification": True,
        
        #  Advertising 
        "ai_ad_copy": "full",
        "ad_platform_connections": "view",  # View metrics only
        "ad_scheduling": False,
        "ad_budget_management": False,
        "cross_platform_analytics": True,
        
        #  AliExpress Integration 
        "aliexpress_search_results_limit": 500,
        "aliexpress_searches_per_day": 200,
        "aliexpress_enrichment": True,  # [HOT] Real-time stock, shipping, variants
        "aliexpress_auto_ordering": False,
        
        #  Support & Team 
        "support_type": "priority",
        "support_response_time": "24hr",
        "team_seats": 2,
        "dedicated_manager": False,
        
        #  Feature Lists for UI 
        "features": [
            "Unlimited product discovery",
            "Full search + saved searches",
            "AI Score with full reasoning",
            "Exact saturation counts",
            "Trend velocity detection",
            "Weekly niche analysis",
            "5 Shopify stores",
            "One-click deploy with SEO captions",
            "AI pricing suggestions",
            "[BRAIN] Personal AI learning (learns YOUR patterns)",
            "Weekly AI business briefings",
            "\"Drop this product\" alerts",
            "[STATS] Real-time inventory monitoring",
            "Days-until-stockout predictions",
            "Low stock email alerts",
            "Restock recommendations",
            "Full email automation",
            "AI draft replies + quiet hours",
            "Order lookup in email replies",
            "Full AI ad copy generator",
            "Cross-platform ad analytics",
            "Affiliate links (5-10% commission)",
            "Order tracking sync",
            "24hr priority support",
            "2 team seats"
        ],
        "limitations": [
            "No auto-ordering",
            "No ad scheduling/budgeting",
            "No daily AI briefings",
            "No Ospra internal saturation data",
            "No competitor monitoring"
        ]
    },
    
    # 
    #  STRATOSPHERE ($199) - "Your AI Operations Team"
    # 
    SubscriptionTier.STRATOSPHERE: {
        "name": "Stratosphere",
        "tagline": "Your AI-powered operations team.",
        "description": "Hands-off automation. Ospra becomes your virtual COO.",
        "emoji": "",
        "price": 199,
        "price_display": "$199/month",
        "color": "#7C3AED",  # Purple (space)
        
        #  Product Discovery 
        "products_per_week": -1,  # Unlimited
        "search_filters": "full_saved_api",  # Full + saved + API access
        "ai_score": True,
        "ai_score_reasoning": True,
        "ai_score_custom_weights": True,  # [HOT] Customize what matters
        "saturation_indicator": "ospra_internal",  # [HOT] "47 Ospra users have this"
        "trend_velocity": True,
        "trend_velocity_early_alerts": True,  # [HOT] Early alerts
        "niche_analysis": "daily",
        
        #  Intelligence & Learning 
        "global_brain": "full",
        "anonymized_success_rates": True,
        "personal_learning": True,
        "accelerated_learning": True,  # [HOT] Faster adaptation
        "custom_weights": True,  # [HOT] "I care more about margin than volume"
        "ai_briefings": True,
        "ai_briefing_frequency": "daily",  # [HOT] Daily briefings
        "revenue_projections": True,
        "revenue_projection_scenarios": True,  # [HOT] What-if scenarios
        "drop_product_alerts": True,
        "drop_product_alternatives": True,  # [HOT] Suggests replacements
        "competitor_monitoring": True,
        
        #  Store Operations 
        "store_limit": -1,  # Unlimited
        "one_click_deploy": True,
        "bulk_deploy": True,  # [HOT] Deploy multiple at once
        "ai_listing_copy": "full_seo_ab",  # [HOT] + A/B test variants
        "ai_pricing_suggestions": True,
        "ai_pricing_competitor_aware": True,  # [HOT] Knows competitor prices
        
        #  Order Fulfillment [HOT] 
        "fulfillment_method": "auto",
        "affiliate_links": True,
        "affiliate_commission": "5-10%",
        "order_tracking_sync": True,
        "auto_ordering": True,  # [HOT] 1-Click auto-order to AliExpress
        
        #  Prophecizer (Inventory) [HOT] Full Suite 
        "real_time_stock": True,
        "days_until_stockout": True,
        "low_stock_alerts": True,
        "low_stock_alert_channels": ["email", "sms"],  # [HOT] + SMS
        "restock_recommendations": True,
        "auto_restock_request": True,  # [HOT] Auto-request restocks
        "seasonality_adjustments": True,  # [HOT] Q4 spike awareness
        "revenue_at_risk": True,  # [HOT] "$1,234 at risk if stockout"
        "supplier_quality_monitoring": True,  # [HOT] Monitor seller ratings
        
        #  Email Automation 
        "email_templates": -1,  # Unlimited
        "ai_draft_replies": True,
        "quiet_hours_routing": True,
        "order_lookup_in_replies": True,
        "auto_classification": True,
        
        #  Advertising [HOT] Full Control 
        "ai_ad_copy": "full_angles",  # [HOT] Multiple marketing angles
        "ad_platform_connections": "full",  # [HOT] Full control
        "ad_scheduling": True,  # [HOT]
        "ad_budget_management": True,  # [HOT]
        "cross_platform_analytics": True,
        "cross_platform_analytics_realtime": True,  # [HOT] Real-time
        
        #  AliExpress Integration 
        "aliexpress_search_results_limit": -1,  # Unlimited
        "aliexpress_searches_per_day": -1,  # Unlimited
        "aliexpress_enrichment": True,
        "aliexpress_auto_ordering": True,  # [HOT]
        
        #  Support & Team 
        "support_type": "dedicated",
        "support_response_time": "priority",
        "team_seats": 5,
        "dedicated_manager": True,  # [HOT] Dedicated success manager
        
        #  Feature Lists for UI 
        "features": [
            "[START] Everything in Soar, plus:",
            "Unlimited Shopify stores",
            "API access for custom integrations",
            "AI Score with custom weights",
            "[HOT] Internal Ospra saturation data",
            "\"47 Ospra users have this product\"",
            "Early trend velocity alerts",
            "Daily niche analysis",
            "[BRAIN] Accelerated personal AI learning",
            "Custom AI weight adjustments",
            "Daily AI business briefings",
            "Revenue projections + scenarios",
            "Product alternatives when dropping",
            "Competitor monitoring",
            "Bulk deploy to all stores",
            "A/B test listing variants",
            "Competitor-aware pricing",
            "[CART] 1-Click auto-ordering fulfillment",
            "Direct API order placement",
            "[STATS] Full Prophecizer suite",
            "SMS + email low stock alerts",
            "Auto-restock requests",
            "Seasonality adjustments",
            "Revenue-at-risk calculations",
            "Supplier quality monitoring",
            " Full ad control",
            "Ad scheduling & budgeting",
            "Real-time cross-platform analytics",
            "Dedicated success manager",
            "5 team seats"
        ],
        "limitations": []  # No limitations!
    }
}


# ==================== HELPER FUNCTIONS ====================

def get_tier_definition(tier: SubscriptionTier) -> Dict[str, Any]:
    """Get complete definition for a tier"""
    return TIER_DEFINITIONS.get(tier, TIER_DEFINITIONS[SubscriptionTier.NEST])


def get_tier_feature(tier: SubscriptionTier, feature: str, default: Any = None) -> Any:
    """Get a specific feature value for a tier"""
    tier_def = TIER_DEFINITIONS.get(tier, {})
    return tier_def.get(feature, default)


def tier_has_feature(tier: SubscriptionTier, feature: str) -> bool:
    """Check if a tier has a specific feature enabled"""
    value = get_tier_feature(tier, feature, False)
    
    # Handle different truthy values
    if value is None or value is False or value == 0 or value == "":
        return False
    if isinstance(value, str) and value.lower() in ["none", "false", "no"]:
        return False
    
    return True


def get_tier_limit(tier: SubscriptionTier, limit_name: str) -> int:
    """Get a specific limit for a tier (-1 = unlimited)"""
    return get_tier_feature(tier, limit_name, 0)


# ==================== PER-REQUEST CEILINGS ====================
# The weekly `products_per_week` quota is enforced by middleware. In addition,
# each individual discovery call is capped so a Nest user can't burn their
# entire weekly budget in a single request. Formula: min(weekly_quota,
# PER_REQUEST_CAP) — with unlimited tiers getting the PER_REQUEST_CAP.

_PER_REQUEST_CEILINGS = {
    SubscriptionTier.NEST: 10,           # Same as weekly — one-shot budget
    SubscriptionTier.FLIGHT: 25,         # Half the weekly allowance per call
    SubscriptionTier.SOAR: 50,           # Generous but bounded (pagination beyond)
    SubscriptionTier.STRATOSPHERE: 100,  # Power users; unlimited weekly, but
                                         # one call can't exceed 100 (prevents
                                         # accidental API cost blow-ups).
}


def get_products_per_request_ceiling(tier: SubscriptionTier) -> int:
    """Upper bound on `count` for a single discovery call, per tier.

    This is orthogonal to the weekly quota: even a Stratosphere user with
    unlimited weekly discovery is capped at 100 products per HTTP request so
    one runaway call can't exhaust an entire day's supplier API budget.
    """
    return _PER_REQUEST_CEILINGS.get(tier, 10)


def clamp_request_count(requested: int, tier: SubscriptionTier) -> tuple[int, bool]:
    """Clamp a user's `count` request to the tier's per-request ceiling.

    Returns (effective_count, was_clamped). Callers should surface
    was_clamped=True in the API response so the frontend can prompt an upgrade.
    """
    ceiling = get_products_per_request_ceiling(tier)
    effective = min(max(requested, 1), ceiling)
    return effective, effective < requested


def compare_tiers(tier_a: SubscriptionTier, tier_b: SubscriptionTier) -> int:
    """
    Compare two tiers.
    Returns: -1 if a < b, 0 if equal, 1 if a > b
    """
    a_level = TIER_HIERARCHY.get(tier_a, 0)
    b_level = TIER_HIERARCHY.get(tier_b, 0)
    
    if a_level < b_level:
        return -1
    elif a_level > b_level:
        return 1
    return 0


def tier_at_least(user_tier: SubscriptionTier, required_tier: SubscriptionTier) -> bool:
    """Check if user's tier is at least the required tier"""
    return compare_tiers(user_tier, required_tier) >= 0


def get_upgrade_path(current_tier: SubscriptionTier) -> Optional[SubscriptionTier]:
    """Get the next tier up from current tier"""
    tier_order = [
        SubscriptionTier.NEST,
        SubscriptionTier.FLIGHT,
        SubscriptionTier.SOAR,
        SubscriptionTier.STRATOSPHERE
    ]
    
    try:
        current_idx = tier_order.index(current_tier)
        if current_idx < len(tier_order) - 1:
            return tier_order[current_idx + 1]
    except ValueError:
        pass
    
    return None


def get_pricing_table() -> List[Dict]:
    """Get formatted pricing table for display"""
    return [
        {
            "tier": tier.value,
            "name": info["name"],
            "emoji": info["emoji"],
            "tagline": info["tagline"],
            "description": info.get("description", ""),
            "price": info["price"],
            "price_display": info["price_display"],
            "color": info["color"],
            "features": info["features"],
            "limitations": info.get("limitations", []),
            "popular": info.get("popular", False),
            
            # Core limits
            "stores": "Unlimited" if info["store_limit"] == -1 else info["store_limit"],
            "products_per_week": "Unlimited" if info["products_per_week"] == -1 else info["products_per_week"],
            "team_seats": info["team_seats"],
            
            # AliExpress Integration limits
            "aliexpress": {
                "search_results_limit": "Unlimited" if info["aliexpress_search_results_limit"] == -1 else info["aliexpress_search_results_limit"],
                "searches_per_day": "Unlimited" if info["aliexpress_searches_per_day"] == -1 else info["aliexpress_searches_per_day"],
                "enrichment": info["aliexpress_enrichment"],
                "auto_ordering": info["aliexpress_auto_ordering"],
            },
            
            # Key feature flags for quick reference
            "key_features": {
                "ai_score": info["ai_score"],
                "personal_learning": info["personal_learning"],
                "one_click_deploy": info["one_click_deploy"],
                "real_time_stock": info["real_time_stock"],
                "auto_ordering": info["auto_ordering"],
                "ai_briefings": info["ai_briefings"],
                "email_automation": info["ai_draft_replies"],
            }
        }
        for tier, info in TIER_DEFINITIONS.items()
    ]


def get_tier_comparison_matrix() -> Dict[str, Dict]:
    """Get feature comparison matrix for all tiers"""
    features_to_compare = [
        # Core Discovery
        ("Products/week", "products_per_week"),
        ("Shopify stores", "store_limit"),
        ("AI Score", "ai_score"),
        ("AI Score reasoning", "ai_score_reasoning"),
        ("Saturation data", "saturation_indicator"),
        
        # Intelligence
        ("Global Brain", "global_brain"),
        ("Personal learning", "personal_learning"),
        ("AI briefings", "ai_briefings"),
        
        # Operations
        ("One-click deploy", "one_click_deploy"),
        ("Real-time stock", "real_time_stock"),
        ("Prophecizer alerts", "low_stock_alerts"),
        ("Auto-ordering", "auto_ordering"),
        
        # Automation
        ("Email automation", "ai_draft_replies"),
        ("Ad control", "ad_platform_connections"),
        
        # AliExpress
        ("AliExpress searches/day", "aliexpress_searches_per_day"),
        ("AliExpress results/search", "aliexpress_search_results_limit"),
        ("AliExpress enrichment", "aliexpress_enrichment"),
        ("AliExpress auto-order", "aliexpress_auto_ordering"),
        
        # Support
        ("Team seats", "team_seats"),
    ]
    
    matrix = {}
    for tier in SubscriptionTier:
        tier_data = {}
        for display_name, feature_key in features_to_compare:
            value = get_tier_feature(tier, feature_key, False)
            
            # Format for display
            if value == -1:
                tier_data[display_name] = "Unlimited"
            elif value is True:
                tier_data[display_name] = "[SUCCESS]"
            elif value is False:
                tier_data[display_name] = "[ERROR]"
            elif isinstance(value, str) and value:
                tier_data[display_name] = value.replace("_", " ").title()
            else:
                tier_data[display_name] = str(value)
        
        matrix[tier.value] = tier_data
    
    return matrix


# ==================== TIER ENFORCEMENT ====================

class TierEnforcer:
    """
    Enforces tier limits and feature access.
    
    Usage:
        enforcer = TierEnforcer(user_tier=SubscriptionTier.SOAR)
        
        if enforcer.can_access("personal_learning"):
            # Enable personal learning
        
        if not enforcer.within_limit("products_per_week", current_count=45):
            # Show upgrade prompt
    """
    
    def __init__(self, user_tier: SubscriptionTier):
        self.tier = user_tier
        self.tier_def = TIER_DEFINITIONS.get(user_tier, TIER_DEFINITIONS[SubscriptionTier.NEST])
    
    def can_access(self, feature: str) -> bool:
        """Check if user can access a feature"""
        return tier_has_feature(self.tier, feature)
    
    def within_limit(self, limit_name: str, current_count: int) -> bool:
        """Check if user is within a usage limit"""
        limit = get_tier_limit(self.tier, limit_name)
        
        # -1 means unlimited
        if limit == -1:
            return True
        
        return current_count < limit
    
    def get_limit(self, limit_name: str) -> int:
        """Get a specific limit (-1 = unlimited)"""
        return get_tier_limit(self.tier, limit_name)
    
    def get_feature(self, feature: str, default: Any = None) -> Any:
        """Get a feature value"""
        return get_tier_feature(self.tier, feature, default)
    
    def requires_upgrade_for(self, feature: str) -> Optional[SubscriptionTier]:
        """
        Check which tier is required for a feature.
        Returns None if current tier has access, otherwise returns minimum required tier.
        """
        if self.can_access(feature):
            return None
        
        # Find minimum tier that has this feature
        for tier in [SubscriptionTier.FLIGHT, SubscriptionTier.SOAR, SubscriptionTier.STRATOSPHERE]:
            if tier_has_feature(tier, feature):
                return tier
        
        return None
    
    def get_upgrade_prompt(self, feature: str) -> Optional[Dict]:
        """Get upgrade prompt for a feature user doesn't have access to"""
        required_tier = self.requires_upgrade_for(feature)
        
        if not required_tier:
            return None
        
        required_def = TIER_DEFINITIONS[required_tier]
        
        return {
            "feature": feature,
            "required_tier": required_tier.value,
            "required_tier_name": required_def["name"],
            "required_tier_emoji": required_def["emoji"],
            "price": required_def["price"],
            "message": f"Upgrade to {required_def['name']} to unlock {feature.replace('_', ' ')}"
        }


# ==================== LOGGING ====================

def log_tier_access(user_id: int, tier: SubscriptionTier, feature: str, allowed: bool):
    """Log tier access attempts for analytics"""
    if allowed:
        logger.debug(f"[SUCCESS] User {user_id} ({tier.value}) accessed {feature}")
    else:
        logger.info(f"[LOCKED] User {user_id} ({tier.value}) blocked from {feature}")


# ==================== EXPORT ====================

__all__ = [
    "SubscriptionTier",
    "TIER_HIERARCHY",
    "TIER_DEFINITIONS",
    "get_tier_definition",
    "get_tier_feature",
    "tier_has_feature",
    "get_tier_limit",
    "get_products_per_request_ceiling",
    "clamp_request_count",
    "compare_tiers",
    "tier_at_least",
    "get_upgrade_path",
    "get_pricing_table",
    "get_tier_comparison_matrix",
    "TierEnforcer",
    "log_tier_access",
]
