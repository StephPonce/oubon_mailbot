"""
Subscription API Routes
=======================

Endpoints for subscription management:
- GET /api/subscription/plans - Get available plans
- GET /api/subscription/current - Get current subscription
- POST /api/subscription/upgrade - Upgrade subscription
- POST /api/subscription/cancel - Cancel subscription

Shopify-native billing path (Partner App approval requirement):
- POST /api/subscription/shopify/create-charge — open an appSubscription
- GET  /api/subscription/shopify/activate     — Shopify post-approval callback
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ospra_os.auth.jwt_auth import get_current_user, get_db, user_to_dict
from ospra_os.database import User, SubscriptionTier
from ospra_os.database.store_models import Store
from ospra_os.payments.shopify_billing import (
    BILLING_PLANS,
    ShopifyBillingError,
    create_app_subscription,
    get_app_subscription,
)


logger = logging.getLogger(__name__)


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
    
    Paid tiers REQUIRE payment via LemonSqueezy checkout.
    Only downgrades to Nest (free) are processed directly.
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
    is_same = new_index == current_index
    
    # Already on this tier
    if is_same:
        return {
            "success": True,
            "action": "none",
            "message": f"You're already on the {TIER_PLANS[tier_lower]['name']} plan"
        }
    
    # DOWNGRADE to free tier - process directly
    if tier_lower == "nest":
        user.subscription_tier = SubscriptionTier.NEST
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
        
        return {
            "success": True,
            "action": "downgraded",
            "message": "Downgraded to Nest (free) plan",
            "subscription": {
                "tier": "nest",
                "tier_name": "Nest",
                "features": TIER_PLANS["nest"]["features"],
                "limits": TIER_PLANS["nest"]["limits"],
            }
        }
    
    # UPGRADE to paid tier - REQUIRE LemonSqueezy checkout
    # LemonSqueezy Product/Variant IDs (set these to your actual IDs)
    lemonsqueezy_store_id = os.getenv("LEMONSQUEEZY_STORE_ID")
    lemonsqueezy_products = {
        "flight": {
            "monthly": os.getenv("LEMONSQUEEZY_FLIGHT_MONTHLY_VARIANT"),
            "yearly": os.getenv("LEMONSQUEEZY_FLIGHT_YEARLY_VARIANT"),
        },
        "soar": {
            "monthly": os.getenv("LEMONSQUEEZY_SOAR_MONTHLY_VARIANT"),
            "yearly": os.getenv("LEMONSQUEEZY_SOAR_YEARLY_VARIANT"),
        },
        "stratosphere": {
            "monthly": os.getenv("LEMONSQUEEZY_STRATOSPHERE_MONTHLY_VARIANT"),
            "yearly": os.getenv("LEMONSQUEEZY_STRATOSPHERE_YEARLY_VARIANT"),
        },
    }
    
    # Get the correct variant ID
    billing_cycle = request.billing_cycle.lower() if request.billing_cycle else "monthly"
    variant_id = lemonsqueezy_products.get(tier_lower, {}).get(billing_cycle)
    
    if not variant_id or not lemonsqueezy_store_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment system not configured. Please contact support."
        )
    
    # Build LemonSqueezy checkout URL with user data for webhook
    checkout_url = (
        f"https://{lemonsqueezy_store_id}.lemonsqueezy.com/checkout/buy/{variant_id}"
        f"?checkout[email]={user.email}"
        f"&checkout[custom][user_id]={user.id}"
        f"&checkout[custom][tier]={tier_lower}"
    )
    
    return {
        "success": True,
        "action": "redirect",
        "checkout_url": checkout_url,
        "message": f"Complete payment to upgrade to {TIER_PLANS[tier_lower]['name']}",
        "tier": tier_lower,
        "price": TIER_PLANS[tier_lower]["price"] if billing_cycle == "monthly" else TIER_PLANS[tier_lower]["price_yearly"],
        "billing_cycle": billing_cycle
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
    user.updated_at = datetime.now(timezone.utc)
    
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


# ============================================================================
# SHOPIFY-NATIVE BILLING (Partner App approval requirement)
# ============================================================================
#
# When a merchant installs Ospra from the Shopify App Store, paid plans
# MUST be charged through Shopify's own Billing API — that's a Partner
# App-store rule, not a preference. The two endpoints below are the
# Shopify-native parallel to /upgrade (which uses LemonSqueezy).
#
# Flow:
#   1. Frontend POSTs to /shopify/create-charge with {tier, billing_cycle}.
#   2. We pull the user's primary Shopify Store row, call
#      ``create_app_subscription`` against the Admin GraphQL API, get back
#      a confirmation_url, and stash the pending charge_id on the Store
#      credentials JSON.
#   3. Frontend redirects the merchant to confirmation_url. They click
#      "Approve charge" inside their Shopify admin.
#   4. Shopify redirects them to /shopify/activate?charge_id=... — we
#      verify the charge is ACTIVE, flip the user's tier, and bounce
#      them back to /settings.
#
# Cancellation is handled in two places:
#   - /api/subscription/cancel — explicit user-initiated downgrade
#     (currently LemonSqueezy-only; not strictly required for Partner
#     approval since uninstall covers it).
#   - app/uninstalled webhook — Shopify auto-cancels the charge; our
#     handler downgrades the user's local tier.
#

class ShopifyChargeRequest(BaseModel):
    """Body for POST /shopify/create-charge."""

    tier: str  # flight | soar | stratosphere
    billing_cycle: str = "monthly"  # monthly | yearly
    store_id: Optional[int] = None  # Disambiguate when user has multiple
    test: bool = False  # Only honored if OSPRA_SHOPIFY_BILLING_TEST=1
    return_path: str = "/settings?billing=shopify"  # Where to land post-approval


def _resolve_shop_credentials(
    user: User,
    db: Session,
    *,
    store_id: Optional[int] = None,
) -> tuple[Store, str, str]:
    """
    Pick the Shopify store we'll bill against and return ``(store, shop_domain, access_token)``.

    Raises HTTPException(400) when the user has no Shopify store, or
    HTTPException(404) when ``store_id`` is supplied but doesn't belong to
    the user — we never want to bill someone else's store by guessing.
    """
    if store_id is not None:
        store = (
            db.query(Store)
            .filter(
                Store.user_id == user.id,
                Store.is_active.is_(True),
                Store.id == store_id,
            )
            .first()
        )
        if not store:
            raise HTTPException(
                status_code=404,
                detail=f"Store {store_id} not found or not owned by current user.",
            )
    else:
        # No store_id — pick the user's first active Shopify store. We
        # filter in Python rather than SQL so this works regardless of
        # how Platform is stored (string, native enum, custom Enum type).
        candidates = (
            db.query(Store)
            .filter(Store.user_id == user.id, Store.is_active.is_(True))
            .all()
        )
        store = next(
            (
                s for s in candidates
                if getattr(s.platform, "value", str(s.platform)).lower() == "shopify"
            ),
            None,
        )

    if not store:
        raise HTTPException(
            status_code=400,
            detail=(
                "No active Shopify store on this account. Connect a Shopify "
                "store before starting a Shopify-native subscription."
            ),
        )

    creds = store.get_credentials() if hasattr(store, "get_credentials") else (store.credentials or {})
    if not isinstance(creds, dict):
        creds = {}
    shop_domain = creds.get("shop_url") or store.store_url or ""
    access_token = creds.get("access_token")
    if not (shop_domain and access_token):
        raise HTTPException(
            status_code=400,
            detail="Shopify store is missing OAuth credentials — reconnect the store and retry.",
        )

    return store, shop_domain, access_token


@router.post("/shopify/create-charge")
async def shopify_create_charge(
    body: ShopifyChargeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Open a Shopify recurring app charge. Returns the confirmation URL the
    merchant must visit to approve.
    """
    if body.tier.lower() not in BILLING_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Tier {body.tier!r} is not a paid plan eligible for Shopify billing.",
        )

    store, shop_domain, access_token = _resolve_shop_credentials(
        user, db, store_id=body.store_id
    )

    # Build a HTTPS return URL Shopify will append ?charge_id=... onto. The
    # public app base URL is configured per environment. Localhost-only
    # dev gets a clear error — Shopify rejects non-HTTPS return URLs.
    app_base = (os.getenv("OSPRA_APP_PUBLIC_URL") or "").rstrip("/")
    if not app_base.startswith("https://"):
        raise HTTPException(
            status_code=503,
            detail="OSPRA_APP_PUBLIC_URL must be set to an https:// origin to use Shopify Billing.",
        )
    return_url = f"{app_base}/api/subscription/shopify/activate?store_id={store.id}&return_path={body.return_path}"

    # ``test`` is only honored when the env flag is on — otherwise we'd
    # silently issue free charges in production if a malicious client
    # passed test=true.
    test_flag = bool(body.test) and os.getenv("OSPRA_SHOPIFY_BILLING_TEST") == "1"

    try:
        result = await create_app_subscription(
            shop_domain=shop_domain,
            access_token=access_token,
            tier=body.tier,
            billing_cycle=body.billing_cycle,
            return_url=return_url,
            test=test_flag,
        )
    except ShopifyBillingError as exc:
        logger.warning("Shopify Billing create-charge failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Persist the pending charge id on Store credentials so the activate
    # callback can match it and downgrades can revoke the right charge.
    creds = store.get_credentials() if hasattr(store, "get_credentials") else dict(store.credentials or {})
    creds["pending_app_subscription_id"] = result.charge_id
    creds["pending_app_subscription_tier"] = body.tier.lower()
    creds["pending_app_subscription_cycle"] = (body.billing_cycle or "monthly").lower()
    if hasattr(store, "set_credentials"):
        store.set_credentials(creds)
    else:
        store.credentials = creds
    db.commit()

    return {
        "success": True,
        "confirmation_url": result.confirmation_url,
        "charge_id": result.charge_id,
        "status": result.status,
        "tier": body.tier.lower(),
        "billing_cycle": (body.billing_cycle or "monthly").lower(),
    }


@router.get("/shopify/activate")
async def shopify_activate_charge(
    charge_id: str = Query(..., description="GID returned by Shopify after merchant approval"),
    store_id: int = Query(..., description="Store row the charge was created against"),
    return_path: str = Query("/settings?billing=shopify"),
    db: Session = Depends(get_db),
):
    """
    Shopify redirects here AFTER the merchant approves a charge.

    Note: this endpoint is NOT JWT-authenticated — Shopify does the redirect
    inside the embedded admin and the merchant won't have an Ospra session
    cookie at that point. We re-establish trust by:

      1. Looking up the Store by ``store_id``.
      2. Calling Shopify back with the store's access token to verify the
         charge is genuinely ACTIVE.
      3. Cross-checking that the ``charge_id`` matches the
         ``pending_app_subscription_id`` we stashed when the charge was
         created — that prevents a replay where someone forges a charge_id
         from a different shop.

    Only after all three checks do we flip the user's tier.
    """
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found.")

    creds = store.get_credentials() if hasattr(store, "get_credentials") else (store.credentials or {})
    if not isinstance(creds, dict):
        creds = {}
    pending_id = creds.get("pending_app_subscription_id")
    if not pending_id or pending_id != charge_id:
        raise HTTPException(
            status_code=400,
            detail="charge_id does not match the pending charge stored for this shop.",
        )

    shop_domain = creds.get("shop_url") or store.store_url
    access_token = creds.get("access_token")
    if not (shop_domain and access_token):
        raise HTTPException(status_code=400, detail="Store is missing credentials.")

    # Verify with Shopify — never trust the redirect alone.
    try:
        sub = await get_app_subscription(
            shop_domain=shop_domain,
            access_token=access_token,
            charge_id=charge_id,
        )
    except ShopifyBillingError as exc:
        logger.exception("Shopify Billing activate verification failed")
        raise HTTPException(status_code=502, detail=str(exc))

    if sub is None or sub.status not in {"ACTIVE", "ACCEPTED"}:
        # Merchant declined or the charge has lapsed. Clear the pending
        # state so the next attempt starts clean.
        for k in (
            "pending_app_subscription_id",
            "pending_app_subscription_tier",
            "pending_app_subscription_cycle",
        ):
            creds.pop(k, None)
        if hasattr(store, "set_credentials"):
            store.set_credentials(creds)
        else:
            store.credentials = creds
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Charge is not active (status={sub.status if sub else 'NOT_FOUND'}).",
        )

    # Promote pending -> active and flip the user's tier.
    target_tier = (creds.get("pending_app_subscription_tier") or "flight").lower()
    tier_map = {
        "flight": SubscriptionTier.FLIGHT,
        "soar": SubscriptionTier.SOAR,
        "stratosphere": SubscriptionTier.STRATOSPHERE,
    }
    user = db.query(User).filter(User.id == store.user_id).first()
    if user and target_tier in tier_map:
        user.subscription_tier = tier_map[target_tier]
        user.subscription_started = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)

    creds["app_subscription_id"] = charge_id
    creds["app_subscription_tier"] = target_tier
    creds["app_subscription_cycle"] = (creds.get("pending_app_subscription_cycle") or "monthly")
    creds["app_subscription_status"] = sub.status
    for k in (
        "pending_app_subscription_id",
        "pending_app_subscription_tier",
        "pending_app_subscription_cycle",
    ):
        creds.pop(k, None)
    if hasattr(store, "set_credentials"):
        store.set_credentials(creds)
    else:
        store.credentials = creds
    db.commit()

    # Bounce the merchant back into the app. ``return_path`` is restricted
    # to internal paths (must start with /) so this can't be turned into
    # an open-redirect by a malicious caller.
    if not return_path.startswith("/"):
        return_path = "/settings?billing=shopify"
    return RedirectResponse(url=return_path, status_code=302)
