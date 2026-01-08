"""
OSPRA INTELLIGENCE - LemonSqueezy Payment Integration
=====================================================

Handles payment processing via LemonSqueezy.
Tier definitions imported from ospra_os.core.tiers (single source of truth).
"""
import os
import hmac
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import httpx

# Import tiers from single source of truth
from ospra_os.core.tiers import (
    SubscriptionTier,
    TIER_DEFINITIONS,
    TIER_HIERARCHY,
    get_tier_definition,
    get_tier_feature,
    get_pricing_table,
    compare_tiers,
)

logger = logging.getLogger(__name__)


# ==================== CONFIGURATION ====================

LEMONSQUEEZY_API_KEY = os.getenv("LEMONSQUEEZY_API_KEY")
LEMONSQUEEZY_STORE_ID = os.getenv("LEMONSQUEEZY_STORE_ID")
LEMONSQUEEZY_WEBHOOK_SECRET = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET")

# Product variant IDs (set these after creating products in LemonSqueezy)
LS_VARIANT_FLIGHT = os.getenv("LS_VARIANT_FLIGHT")  # $29/mo
LS_VARIANT_SOAR = os.getenv("LS_VARIANT_SOAR")      # $79/mo
LS_VARIANT_STRATOSPHERE = os.getenv("LS_VARIANT_STRATOSPHERE")  # $199/mo

# LemonSqueezy Checkout URLs (direct links)
LS_CHECKOUT_FLIGHT = os.getenv("LS_CHECKOUT_FLIGHT", "https://ospra.lemonsqueezy.com/buy/7f817d94-cf31-4ab6-9ff4-54de583f7920")
LS_CHECKOUT_SOAR = os.getenv("LS_CHECKOUT_SOAR", "https://ospra.lemonsqueezy.com/buy/e1f7dd88-9c08-4486-ac77-be77af8bf976")
LS_CHECKOUT_STRATOSPHERE = os.getenv("LS_CHECKOUT_STRATOSPHERE", "https://ospra.lemonsqueezy.com/buy/5d7d273d-f3df-470a-8827-40c3cd975cfc")

API_BASE = "https://api.lemonsqueezy.com/v1"


# ==================== VARIANT MAPPING ====================

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


def get_checkout_url_for_tier(tier: SubscriptionTier) -> Optional[str]:
    """Get direct checkout URL for a tier"""
    checkout_map = {
        SubscriptionTier.FLIGHT: LS_CHECKOUT_FLIGHT,
        SubscriptionTier.SOAR: LS_CHECKOUT_SOAR,
        SubscriptionTier.STRATOSPHERE: LS_CHECKOUT_STRATOSPHERE,
    }
    return checkout_map.get(tier)


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
        
        tier_info = get_tier_definition(tier)
        
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
                        "receipt_thank_you_note": f"Welcome to Ospra {tier_info['name']}! {tier_info['emoji']} Your journey to the stars begins now. [START]"
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
        tier_info = get_tier_definition(tier)
        
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
        
        logger.info(f"[SUCCESS] Cancelled subscription: {subscription_id}")
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
        
        logger.info(f"[SUCCESS] Changed subscription {subscription_id} to {new_tier}")
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
    
    logger.info(f" LemonSqueezy webhook: {event_name}")
    
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


# ==================== DISPLAY HELPERS ====================

def get_setup_instructions() -> str:
    return """

              OSPRA LEMONSQUEEZY SETUP INSTRUCTIONS               

                                                                  
  1. Log into LemonSqueezy: https://app.lemonsqueezy.com         
                                                                  
  2. Create 3 Products:                                          
       Flight       - $29/month                                 
       Soar         - $79/month (mark as featured)             
       Stratosphere - $199/month                               
                                                                  
  3. Copy Variant IDs from each product                          
                                                                  
  4. Create API Key: Settings → API                              
                                                                  
  5. Set up Webhook: Settings → Webhooks                         
     URL: https://your-domain.com/api/payments/webhook           
     Events: All subscription events                             
                                                                  
  6. Add to .env:                                                
     LEMONSQUEEZY_API_KEY=ls_xxxxxxxx                            
     LEMONSQUEEZY_STORE_ID=xxxxx                                 
     LEMONSQUEEZY_WEBHOOK_SECRET=xxxxx                           
     LS_VARIANT_FLIGHT=xxxxx                                     
     LS_VARIANT_SOAR=xxxxx                                       
     LS_VARIANT_STRATOSPHERE=xxxxx                               
                                                                  
   NEST (Free) - No product needed, it's the default           
                                                                  

"""


if __name__ == "__main__":
    print(get_setup_instructions())
    print("\n[STATS] Ospra Pricing Tiers:\n")
    for plan in get_pricing_table():
        print(f"{plan['emoji']} {plan['name']} - {plan['price_display']}")
        print(f"   \"{plan['tagline']}\"")
        for feature in plan['features'][:3]:
            print(f"   [OK] {feature}")
        print()
