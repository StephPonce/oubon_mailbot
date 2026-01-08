"""
Subscription API Routes
=======================

Endpoints for subscription management:
- GET /api/subscription/plans - Get available plans
- GET /api/subscription/current - Get current subscription
- POST /api/subscription/upgrade - Upgrade subscription
- POST /api/subscription/cancel - Cancel subscription
"""

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ospra_os.auth.jwt_auth import get_current_user, get_db, user_to_dict
from ospra_os.database.multi_store_models import User, SubscriptionTier


router = APIRouter(prefix="/api/subscription", tags=["Subscription"])


# ============================================================================
# TIER CONFIGURATION
# ============================================================================

TIER_PLANS = {
    "nest": {
        "name": "Nest",
        "price": 0,
        "price_yearly": 0,
        "features": [
            "1 connected store",
            "50 products/month",
            "Basic trend discovery",
            "Email support",
        ],
        "limits": {
            "stores": 1,
            "products_per_month": 50,
            "early_access_days": 0,
            "ai_budget": 5.0,
            "auto_deploy": False,
            "api_access": False,
        }
    },
    "flight": {
        "name": "Flight",
        "price": 29,
        "price_yearly": 290,
        "features": [
            "3 connected stores",
            "500 products/month",
            "Advanced trend discovery",
            "24-hour early access to trends",
            "Priority support",
        ],
        "limits": {
            "stores": 3,
            "products_per_month": 500,
            "early_access_days": 1,
            "ai_budget": 25.0,
            "auto_deploy": True,
            "api_access": False,
        }
    },
    "soar": {
        "name": "Soar",
        "price": 79,
        "price_yearly": 790,
        "popular": True,
        "features": [
            "10 connected stores",
            "Unlimited products",
            "AI-powered automation",
            "7-day early access to trends",
            "Custom branding",
            "API access",
        ],
        "limits": {
            "stores": 10,
            "products_per_month": -1,  # Unlimited
            "early_access_days": 7,
            "ai_budget": 100.0,
            "auto_deploy": True,
            "api_access": True,
        }
    },
    "stratosphere": {
        "name": "Stratosphere",
        "price": 199,
        "price_yearly": 1990,
        "features": [
            "Unlimited stores",
            "Unlimited everything",
            "First access to trends (30+ days)",
            "White-label options",
            "Dedicated account manager",
            "Custom integrations",
        ],
        "limits": {
            "stores": -1,  # Unlimited
            "products_per_month": -1,
            "early_access_days": 30,
            "ai_budget": -1,  # Unlimited
            "auto_deploy": True,
            "api_access": True,
        }
    }
}


# ============================================================================
# REQUEST MODELS
# ============================================================================

class UpgradeRequest(BaseModel):
    """Subscription upgrade request"""
    tier: str
    billing_cycle: str = "monthly"  # monthly or yearly


class CancelRequest(BaseModel):
    """Subscription cancellation request"""
    reason: Optional[str] = None
    feedback: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/plans")
async def get_plans():
    """Get all available subscription plans"""
    return {
        "success": True,
        "plans": TIER_PLANS
    }


@router.get("/current")
async def get_current_subscription(user: User = Depends(get_current_user)):
    """Get current user's subscription details"""
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    tier_lower = tier_value.lower()
    
    plan = TIER_PLANS.get(tier_lower, TIER_PLANS["nest"])
    
    return {
        "success": True,
        "subscription": {
            "tier": tier_value,
            "tier_name": plan["name"],
            "price": plan["price"],
            "features": plan["features"],
            "limits": plan["limits"],
            "started": user.subscription_started.isoformat() if user.subscription_started else None,
            "expires": user.subscription_expires.isoformat() if user.subscription_expires else None,
        }
    }


@router.post("/upgrade")
async def upgrade_subscription(
    request: UpgradeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upgrade subscription to a new tier.
    
    In production, this would redirect to LemonSqueezy checkout.
    For development, it directly updates the tier.
    """
    tier_map = {
        "nest": SubscriptionTier.NEST,
        "flight": SubscriptionTier.FLIGHT,
        "soar": SubscriptionTier.SOAR,
        "stratosphere": SubscriptionTier.STRATOSPHERE,
    }
    
    tier_lower = request.tier.lower()
    if tier_lower not in tier_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {request.tier}. Valid tiers: nest, flight, soar, stratosphere"
        )
    
    # Get current tier for comparison
    current_tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    current_tier_lower = current_tier_value.lower()
    
    # Check if this is an upgrade or downgrade
    tier_order = ["nest", "flight", "soar", "stratosphere"]
    current_index = tier_order.index(current_tier_lower) if current_tier_lower in tier_order else 0
    new_index = tier_order.index(tier_lower)
    
    is_upgrade = new_index > current_index
    is_downgrade = new_index < current_index
    
    # Check for LemonSqueezy integration in production
    lemonsqueezy_api_key = os.getenv("LEMONSQUEEZY_API_KEY")
    
    if lemonsqueezy_api_key and is_upgrade and tier_lower != "nest":
        # In production, create LemonSqueezy checkout session
        # For now, just return a placeholder checkout URL
        return {
            "success": True,
            "action": "redirect",
            "checkout_url": f"https://ospra.lemonsqueezy.com/checkout?tier={tier_lower}",
            "message": f"Redirecting to checkout for {TIER_PLANS[tier_lower]['name']} plan"
        }
    
    # Direct tier update (for development or free tier)
    new_tier = tier_map[tier_lower]
    user.subscription_tier = new_tier
    user.subscription_started = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    
    return {
        "success": True,
        "action": "updated",
        "message": f"{'Upgraded' if is_upgrade else 'Changed'} to {TIER_PLANS[tier_lower]['name']} plan",
        "subscription": {
            "tier": tier_value,
            "tier_name": TIER_PLANS[tier_lower]["name"],
            "features": TIER_PLANS[tier_lower]["features"],
            "limits": TIER_PLANS[tier_lower]["limits"],
        },
        "user": user_to_dict(user)
    }


@router.post("/cancel")
async def cancel_subscription(
    request: CancelRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel subscription (downgrade to Nest/free tier).
    """
    user.subscription_tier = SubscriptionTier.NEST
    user.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "message": "Subscription cancelled. You've been moved to the Nest (free) plan.",
        "tier": "nest"
    }


@router.get("/limits")
async def get_tier_limits(user: User = Depends(get_current_user)):
    """Get current user's tier limits and usage"""
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    tier_lower = tier_value.lower()
    
    plan = TIER_PLANS.get(tier_lower, TIER_PLANS["nest"])
    limits = plan["limits"]
    
    return {
        "success": True,
        "tier": tier_value,
        "limits": limits,
        "usage": {
            "stores": user.total_stores,
            "products_this_month": user.total_products,  # Would need monthly tracking
        },
        "can": {
            "add_store": limits["stores"] == -1 or user.total_stores < limits["stores"],
            "add_product": limits["products_per_month"] == -1 or user.total_products < limits["products_per_month"],
            "auto_deploy": limits["auto_deploy"],
            "use_api": limits["api_access"],
        }
    }


@router.get("/features/{feature}")
async def check_feature_access(
    feature: str,
    user: User = Depends(get_current_user)
):
    """Check if user has access to a specific feature"""
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    tier_lower = tier_value.lower()
    
    plan = TIER_PLANS.get(tier_lower, TIER_PLANS["nest"])
    limits = plan["limits"]
    
    feature_map = {
        "auto_deploy": limits["auto_deploy"],
        "api_access": limits["api_access"],
        "early_access": limits["early_access_days"] > 0,
        "unlimited_products": limits["products_per_month"] == -1,
        "unlimited_stores": limits["stores"] == -1,
        "ai_automation": tier_lower in ["soar", "stratosphere"],
        "white_label": tier_lower == "stratosphere",
        "custom_integrations": tier_lower == "stratosphere",
    }
    
    has_access = feature_map.get(feature, False)
    
    if not has_access:
        # Find minimum tier that has this feature
        required_tier = None
        for tier_id in ["flight", "soar", "stratosphere"]:
            tier_plan = TIER_PLANS[tier_id]
            tier_limits = tier_plan["limits"]
            tier_feature_map = {
                "auto_deploy": tier_limits["auto_deploy"],
                "api_access": tier_limits["api_access"],
                "early_access": tier_limits["early_access_days"] > 0,
                "unlimited_products": tier_limits["products_per_month"] == -1,
                "unlimited_stores": tier_limits["stores"] == -1,
                "ai_automation": tier_id in ["soar", "stratosphere"],
                "white_label": tier_id == "stratosphere",
                "custom_integrations": tier_id == "stratosphere",
            }
            if tier_feature_map.get(feature, False):
                required_tier = tier_id
                break
    
    return {
        "feature": feature,
        "has_access": has_access,
        "current_tier": tier_value,
        "required_tier": None if has_access else required_tier,
        "upgrade_url": None if has_access else f"/settings?tab=subscription&upgrade={required_tier}"
    }
