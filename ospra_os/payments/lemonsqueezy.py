"""
OSPRA INTELLIGENCE - LemonSqueezy Payment Integration
=====================================================
Sky/Flight themed subscription tiers: Nest → Flight → Soar → Stratosphere

Theme: Journey from grounded to the stars
- 🪺 Nest: Grounded, watching, learning (Free)
- ✈️ Flight: Taken off, building momentum ($29)
- 🦅 Soar: High altitude, seeing what others can't ($79)
- 🌌 Stratosphere: Edge of space, first to everything ($199)
"""
import os
import hmac
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import httpx

logger = logging.getLogger(__name__)


# ==================== CONFIGURATION ====================

LEMONSQUEEZY_API_KEY = os.getenv("LEMONSQUEEZY_API_KEY")
LEMONSQUEEZY_STORE_ID = os.getenv("LEMONSQUEEZY_STORE_ID")
LEMONSQUEEZY_WEBHOOK_SECRET = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET")

# Product variant IDs (set these after creating products in LemonSqueezy)
LS_VARIANT_FLIGHT = os.getenv("LS_VARIANT_FLIGHT")  # $29/mo
LS_VARIANT_SOAR = os.getenv("LS_VARIANT_SOAR")      # $79/mo
LS_VARIANT_STRATOSPHERE = os.getenv("LS_VARIANT_STRATOSPHERE")  # $199/mo

# Legacy support
LS_VARIANT_STARTER = os.getenv("LS_VARIANT_STARTER") or LS_VARIANT_FLIGHT
LS_VARIANT_PRO = os.getenv("LS_VARIANT_PRO") or LS_VARIANT_SOAR
LS_VARIANT_ELITE = os.getenv("LS_VARIANT_ELITE") or LS_VARIANT_STRATOSPHERE

API_BASE = "https://api.lemonsqueezy.com/v1"


# ==================== TIER DEFINITIONS ====================

class SubscriptionTier(str, Enum):
    """
    Ospra tier naming: Sky/flight theme - grounded to stars
    
    The journey of an Osprey:
    🪺 Nest → Just hatched, learning the world
    ✈️ Flight → First flight, building confidence  
    🦅 Soar → Mastery, riding thermals effortlessly
    🌌 Stratosphere → Beyond limits, touching the stars
    """
    NEST = "nest"                    # Free - Grounded, learning
    FLIGHT = "flight"                # $29 - Taken off, momentum
    SOAR = "soar"                    # $79 - High altitude, seeing far
    STRATOSPHERE = "stratosphere"    # $199 - Edge of space, first to see


# Tier hierarchy for comparison (higher = better)
TIER_HIERARCHY = {
    SubscriptionTier.NEST: 0,
    SubscriptionTier.FLIGHT: 1,
    SubscriptionTier.SOAR: 2,
    SubscriptionTier.STRATOSPHERE: 3,
}


# Complete tier definitions with features and limits
TIER_DEFINITIONS = {
    SubscriptionTier.NEST: {
        "name": "Nest",
        "tagline": "Start grounded. Learn the landscape.",
        "emoji": "🪺",
        "price": 0,
        "color": "#8B7355",  # Earthy brown
        "product_freshness_days": 30,  # Only see 30+ day old products
        "store_limit": 1,
        "products_per_week": 5,
        "ai_analysis": "basic",  # Basic scoring only
        "email_automation": False,
        "saturation_visibility": False,
        "api_access": False,
        "team_members": 1,
        "support": "community",
        "features": [
            "Mature products (30+ days trending)",
            "1 e-commerce store",
            "5 product discoveries per week",
            "Basic AI scoring",
            "Community support"
        ],
        "limitations": [
            "Products already well-known",
            "No email automation",
            "No saturation data",
            "No API access"
        ]
    },
    
    SubscriptionTier.FLIGHT: {
        "name": "Flight",
        "tagline": "You've taken off. Momentum is building.",
        "emoji": "✈️",
        "price": 29,
        "color": "#87CEEB",  # Sky blue
        "product_freshness_days": 14,  # See 14+ day products
        "store_limit": 3,
        "products_per_week": 25,
        "ai_analysis": "full",  # Full Claude insights
        "email_automation": "templates",  # Smart templates only
        "saturation_visibility": "basic",  # See if >50 users have it
        "api_access": False,
        "team_members": 1,
        "support": "email_48hr",
        "features": [
            "Growth-phase products (14+ days)",
            "3 e-commerce stores",
            "25 product discoveries per week",
            "Full AI analysis & insights",
            "Smart email templates",
            "Basic saturation alerts",
            "Email support (48hr)"
        ],
        "limitations": [
            "No early-spike products",
            "No full email automation",
            "No API access"
        ]
    },
    
    SubscriptionTier.SOAR: {
        "name": "Soar",
        "tagline": "Rise above the noise. See what others can't.",
        "emoji": "🦅",
        "price": 79,
        "color": "#0EA5E9",  # Bright blue
        "product_freshness_days": 7,  # See 7+ day products (early spike!)
        "store_limit": 10,
        "products_per_week": -1,  # Unlimited
        "ai_analysis": "deep",  # Deep analysis + competitor intel
        "email_automation": "full",  # Full AI-powered
        "saturation_visibility": "full",  # Exact user counts
        "api_access": True,
        "team_members": 1,
        "support": "priority_24hr",
        "popular": True,  # Mark as most popular
        "features": [
            "Early-spike products (7+ days) 🔥",
            "10 e-commerce stores",
            "Unlimited product discoveries",
            "Deep AI analysis + competitor intel",
            "Full AI-powered email automation",
            "Full saturation visibility",
            "API access",
            "Priority support (24hr)"
        ],
        "limitations": [
            "No day-0 discovery access",
            "No team features"
        ]
    },
    
    SubscriptionTier.STRATOSPHERE: {
        "name": "Stratosphere",
        "tagline": "Beyond the clouds. First to see. First to sell.",
        "emoji": "🌌",
        "price": 199,
        "color": "#7C3AED",  # Purple (space)
        "product_freshness_days": 0,  # See products IMMEDIATELY
        "store_limit": -1,  # Unlimited
        "products_per_week": -1,  # Unlimited
        "ai_analysis": "custom",  # Custom AI training
        "email_automation": "custom",  # Full + custom workflows
        "saturation_visibility": "predictive",  # Predictive alerts
        "api_access": True,
        "api_rate_limit": -1,  # Unlimited
        "team_members": 5,
        "support": "dedicated",
        "first_access": True,  # First 50 to see new products
        "features": [
            "Discovery products (0+ days) - FIRST ACCESS 🚀",
            "Among first 50 to see emerging products",
            "Unlimited e-commerce stores",
            "Unlimited product discoveries",
            "Custom AI trained on YOUR niche",
            "Full email automation + custom workflows",
            "Predictive saturation alerts",
            "Unlimited API + webhooks",
            "Up to 5 team members",
            "Dedicated success manager",
            "White-glove onboarding"
        ],
        "limitations": []
    }
}


# Map variant IDs to tiers
VARIANT_TO_TIER = {}
if LS_VARIANT_FLIGHT:
    VARIANT_TO_TIER[LS_VARIANT_FLIGHT] = SubscriptionTier.FLIGHT
if LS_VARIANT_SOAR:
    VARIANT_TO_TIER[LS_VARIANT_SOAR] = SubscriptionTier.SOAR
if LS_VARIANT_STRATOSPHERE:
    VARIANT_TO_TIER[LS_VARIANT_STRATOSPHERE] = SubscriptionTier.STRATOSPHERE


# ==================== HELPER FUNCTIONS ====================

def get_tier_from_variant(variant_id: str) -> SubscriptionTier:
    """Convert LemonSqueezy variant ID to tier"""
    return VARIANT_TO_TIER.get(variant_id, SubscriptionTier.NEST)


def get_variant_for_tier(tier: SubscriptionTier) -> Optional[str]:
    """Get LemonSqueezy variant ID for a tier"""
    variant_map = {
        SubscriptionTier.FLIGHT: LS_VARIANT_FLIGHT,
        SubscriptionTier.SOAR: LS_VARIANT_SOAR,
        SubscriptionTier.STRATOSPHERE: LS_VARIANT_STRATOSPHERE,
    }
    return variant_map.get(tier)


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


def tier_has_feature(tier: SubscriptionTier, feature: str) -> bool:
    """Check if a tier has a specific feature"""
    tier_def = TIER_DEFINITIONS.get(tier, {})
    return tier_def.get(feature, False)


def get_tier_limit(tier: SubscriptionTier, limit_name: str) -> int:
    """Get a specific limit for a tier (-1 = unlimited)"""
    tier_def = TIER_DEFINITIONS.get(tier, {})
    return tier_def.get(limit_name, 0)


# ==================== LEMONSQUEEZY CLIENT ====================

class LemonSqueezyClient:
    """LemonSqueezy API client for subscription management"""
    
    def __init__(self):
        if not LEMONSQUEEZY_API_KEY:
            raise RuntimeError("LEMONSQUEEZY_API_KEY not configured")
        
        self.headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {LEMONSQUEEZY_API_KEY}"
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """Make API request to LemonSqueezy"""
        url = f"{API_BASE}/{endpoint}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=data,
                    timeout=30.0
                )
                
                if response.status_code >= 400:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get("errors", [{}])[0].get("detail", response.text)
                    return None, f"API error {response.status_code}: {error_msg}"
                
                return response.json(), None
                
        except httpx.TimeoutException:
            return None, "Request timed out"
        except Exception as e:
            logger.error(f"LemonSqueezy API error: {e}")
            return None, str(e)
    
    # ==================== CHECKOUT ====================
    
    async def create_checkout(
        self,
        tier: SubscriptionTier,
        user_email: str,
        user_id: str,
        success_url: str = "https://app.ospra.io/billing/success",
        cancel_url: str = "https://app.ospra.io/billing"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a checkout session for a subscription tier
        
        Args:
            tier: The subscription tier to purchase
            user_email: Customer email
            user_id: Your internal user ID
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
        
        Returns:
            Tuple of (checkout_url, error)
        """
        variant_id = get_variant_for_tier(tier)
        if not variant_id:
            return None, f"No variant configured for tier: {tier}"
        
        if not LEMONSQUEEZY_STORE_ID:
            return None, "LEMONSQUEEZY_STORE_ID not configured"
        
        tier_info = TIER_DEFINITIONS[tier]
        
        data = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "checkout_options": {
                        "embed": False,
                        "media": True,
                        "button_color": tier_info["color"]
                    },
                    "checkout_data": {
                        "email": user_email,
                        "custom": {
                            "user_id": user_id,
                            "tier": tier.value
                        }
                    },
                    "product_options": {
                        "redirect_url": success_url,
                        "receipt_button_text": "Launch Dashboard",
                        "receipt_thank_you_note": f"Welcome to Ospra {tier_info['name']}! {tier_info['emoji']} Your journey to the stars begins now. 🚀"
                    }
                },
                "relationships": {
                    "store": {
                        "data": {
                            "type": "stores",
                            "id": LEMONSQUEEZY_STORE_ID
                        }
                    },
                    "variant": {
                        "data": {
                            "type": "variants",
                            "id": variant_id
                        }
                    }
                }
            }
        }
        
        result, error = await self._request("POST", "checkouts", data)
        
        if error:
            return None, error
        
        checkout_url = result.get("data", {}).get("attributes", {}).get("url")
        return checkout_url, None
    
    # ==================== SUBSCRIPTION MANAGEMENT ====================
    
    async def get_subscription(
        self,
        subscription_id: str
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """Get subscription details"""
        result, error = await self._request("GET", f"subscriptions/{subscription_id}")
        
        if error:
            return None, error
        
        attrs = result.get("data", {}).get("attributes", {})
        tier = get_tier_from_variant(str(attrs.get("variant_id")))
        tier_info = TIER_DEFINITIONS.get(tier, {})
        
        return {
            "id": result.get("data", {}).get("id"),
            "status": attrs.get("status"),
            "tier": tier.value,
            "tier_name": tier_info.get("name", "Unknown"),
            "tier_emoji": tier_info.get("emoji", ""),
            "current_period_end": attrs.get("renews_at"),
            "cancelled": attrs.get("cancelled"),
            "ends_at": attrs.get("ends_at"),
            "customer_id": attrs.get("customer_id")
        }, None
    
    async def cancel_subscription(
        self,
        subscription_id: str
    ) -> Tuple[bool, Optional[str]]:
        """Cancel subscription at end of billing period"""
        data = {
            "data": {
                "type": "subscriptions",
                "id": subscription_id,
                "attributes": {
                    "cancelled": True
                }
            }
        }
        
        result, error = await self._request("PATCH", f"subscriptions/{subscription_id}", data)
        
        if error:
            return False, error
        
        logger.info(f"✅ Cancelled subscription: {subscription_id}")
        return True, None
    
    async def resume_subscription(
        self,
        subscription_id: str
    ) -> Tuple[bool, Optional[str]]:
        """Resume a cancelled subscription"""
        data = {
            "data": {
                "type": "subscriptions",
                "id": subscription_id,
                "attributes": {
                    "cancelled": False
                }
            }
        }
        
        result, error = await self._request("PATCH", f"subscriptions/{subscription_id}", data)
        
        if error:
            return False, error
        
        return True, None
    
    async def change_subscription_tier(
        self,
        subscription_id: str,
        new_tier: SubscriptionTier
    ) -> Tuple[bool, Optional[str]]:
        """Change subscription to a different tier"""
        variant_id = get_variant_for_tier(new_tier)
        if not variant_id:
            return False, f"No variant configured for tier: {new_tier}"
        
        data = {
            "data": {
                "type": "subscriptions",
                "id": subscription_id,
                "attributes": {
                    "variant_id": int(variant_id)
                }
            }
        }
        
        result, error = await self._request("PATCH", f"subscriptions/{subscription_id}", data)
        
        if error:
            return False, error
        
        logger.info(f"✅ Changed subscription {subscription_id} to {new_tier}")
        return True, None
    
    async def get_customer_portal_url(
        self,
        customer_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get customer portal URL for self-service billing management"""
        result, error = await self._request("GET", f"customers/{customer_id}")
        
        if error:
            return None, error
        
        urls = result.get("data", {}).get("attributes", {}).get("urls", {})
        portal_url = urls.get("customer_portal")
        
        return portal_url, None


# ==================== WEBHOOK HANDLING ====================

def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str = None
) -> bool:
    """Verify LemonSqueezy webhook signature"""
    secret = secret or LEMONSQUEEZY_WEBHOOK_SECRET
    if not secret:
        logger.warning("Webhook secret not configured")
        return False
    
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


async def handle_webhook_event(event: Dict) -> Dict:
    """
    Handle LemonSqueezy webhook events
    
    Events:
    - subscription_created: New subscription
    - subscription_updated: Plan change, renewal
    - subscription_cancelled: User cancelled
    - subscription_expired: Subscription ended
    - subscription_payment_failed: Payment failed
    """
    event_name = event.get("meta", {}).get("event_name", "unknown")
    data = event.get("data", {}).get("attributes", {})
    custom_data = event.get("meta", {}).get("custom_data", {})
    
    logger.info(f"📥 LemonSqueezy webhook: {event_name}")
    
    result = {
        "event": event_name,
        "handled": True
    }
    
    if event_name == "subscription_created":
        user_id = custom_data.get("user_id")
        tier = custom_data.get("tier", "flight")
        subscription_id = event.get("data", {}).get("id")
        customer_id = data.get("customer_id")
        
        result.update({
            "action": "activate_subscription",
            "user_id": user_id,
            "tier": tier,
            "subscription_id": subscription_id,
            "customer_id": customer_id
        })
        
        # TODO: Update user in database
        # await update_user_subscription(user_id, tier, subscription_id, customer_id)
        
    elif event_name == "subscription_updated":
        subscription_id = event.get("data", {}).get("id")
        variant_id = str(data.get("variant_id"))
        tier = get_tier_from_variant(variant_id)
        
        result.update({
            "action": "update_tier",
            "subscription_id": subscription_id,
            "tier": tier.value
        })
        
    elif event_name in ["subscription_cancelled", "subscription_expired"]:
        subscription_id = event.get("data", {}).get("id")
        
        result.update({
            "action": "downgrade_to_nest",
            "subscription_id": subscription_id,
            "tier": SubscriptionTier.NEST.value
        })
        
        # TODO: Downgrade user to Nest (free)
        
    elif event_name == "subscription_payment_failed":
        subscription_id = event.get("data", {}).get("id")
        customer_id = data.get("customer_id")
        
        result.update({
            "action": "payment_failed",
            "subscription_id": subscription_id,
            "customer_id": customer_id
        })
        
        # TODO: Send payment failed notification
        
    else:
        result["handled"] = False
    
    return result


# ==================== PRICING TABLE ====================

def get_pricing_table() -> List[Dict]:
    """Get formatted pricing table for display"""
    return [
        {
            "tier": tier.value,
            "name": info["name"],
            "emoji": info["emoji"],
            "tagline": info["tagline"],
            "price": info["price"],
            "price_display": f"${info['price']}/month" if info["price"] > 0 else "Free",
            "color": info["color"],
            "features": info["features"],
            "limitations": info.get("limitations", []),
            "popular": info.get("popular", False),
            "product_freshness": f"{info['product_freshness_days']}+ days",
            "stores": "Unlimited" if info["store_limit"] == -1 else info["store_limit"],
            "products_per_week": "Unlimited" if info["products_per_week"] == -1 else info["products_per_week"]
        }
        for tier, info in TIER_DEFINITIONS.items()
    ]


def get_setup_instructions() -> str:
    return """
╔══════════════════════════════════════════════════════════════════╗
║              OSPRA LEMONSQUEEZY SETUP INSTRUCTIONS               ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  1. Log into LemonSqueezy: https://app.lemonsqueezy.com         ║
║                                                                  ║
║  2. Create 3 Products:                                          ║
║     ✈️  Flight       - $29/month                                 ║
║     🦅  Soar         - $79/month (mark as featured)             ║
║     🌌  Stratosphere - $199/month                               ║
║                                                                  ║
║  3. Copy Variant IDs from each product                          ║
║                                                                  ║
║  4. Create API Key: Settings → API                              ║
║                                                                  ║
║  5. Set up Webhook: Settings → Webhooks                         ║
║     URL: https://your-domain.com/api/payments/webhook           ║
║     Events: All subscription events                             ║
║                                                                  ║
║  6. Add to .env:                                                ║
║     LEMONSQUEEZY_API_KEY=ls_xxxxxxxx                            ║
║     LEMONSQUEEZY_STORE_ID=xxxxx                                 ║
║     LEMONSQUEEZY_WEBHOOK_SECRET=xxxxx                           ║
║     LS_VARIANT_FLIGHT=xxxxx                                     ║
║     LS_VARIANT_SOAR=xxxxx                                       ║
║     LS_VARIANT_STRATOSPHERE=xxxxx                               ║
║                                                                  ║
║  🪺 NEST (Free) - No product needed, it's the default           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""


if __name__ == "__main__":
    print(get_setup_instructions())
    print("\n📊 Ospra Pricing Tiers:\n")
    for plan in get_pricing_table():
        print(f"{plan['emoji']} {plan['name']} - {plan['price_display']}")
        print(f"   \"{plan['tagline']}\"")
        for feature in plan['features'][:3]:
            print(f"   ✓ {feature}")
        print()
