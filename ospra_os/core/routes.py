"""
TIER API ROUTES

Endpoints for subscription tier information, pricing, and feature access.

SECURITY NOTE: All authenticated endpoints extract user_id from JWT token,
never from query parameters. This prevents IDOR (Insecure Direct Object Reference)
vulnerabilities where attackers could access other users' data.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ospra_os.core.tiers import (
    SubscriptionTier,
    TIER_DEFINITIONS,
    get_tier_definition,
    get_tier_feature,
    tier_has_feature,
    get_tier_limit,
    get_pricing_table,
    get_tier_comparison_matrix,
    TierEnforcer,
    compare_tiers,
    get_upgrade_path,
)
from ospra_os.database import User
from ospra_os.database.connection import SessionLocal, get_db
from ospra_os.auth.jwt_auth import get_current_user

router = APIRouter(prefix="/api/tiers", tags=["Tiers"])


# ==================== PUBLIC ENDPOINTS ====================

@router.get("/pricing")
async def get_pricing():
    """
    Get pricing table for all tiers.
    
    Public endpoint - no authentication required.
    Used on marketing/pricing page.
    """
    return {
        "tiers": get_pricing_table(),
        "currency": "USD",
        "billing_period": "monthly",
        "trial_available": False,  # Set to True if you offer trials
    }


@router.get("/compare")
async def get_tier_comparison():
    """
    Get feature comparison matrix for all tiers.
    
    Public endpoint - no authentication required.
    Used on pricing comparison page.
    """
    return {
        "matrix": get_tier_comparison_matrix(),
        "tiers_order": ["nest", "flight", "soar", "stratosphere"],
    }


@router.get("/features/{tier}")
async def get_tier_features(tier: str):
    """
    Get detailed features for a specific tier.
    
    Args:
        tier: Tier name (nest, flight, soar, stratosphere)
    """
    try:
        tier_enum = SubscriptionTier(tier.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {tier}. Valid tiers: nest, flight, soar, stratosphere"
        )
    
    tier_def = get_tier_definition(tier_enum)
    
    return {
        "tier": tier_enum.value,
        "name": tier_def["name"],
        "emoji": tier_def["emoji"],
        "tagline": tier_def["tagline"],
        "description": tier_def.get("description", ""),
        "price": tier_def["price"],
        "price_display": tier_def["price_display"],
        "color": tier_def["color"],
        "features": tier_def["features"],
        "limitations": tier_def.get("limitations", []),
        "popular": tier_def.get("popular", False),
    }


# ==================== AUTHENTICATED ENDPOINTS ====================
# SECURITY: All endpoints below extract user_id from JWT token via get_current_user
# This prevents IDOR attacks where users could access other users' data

@router.get("/current")
async def get_current_tier(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's tier information.

    User ID is extracted from JWT token - no query parameter needed.
    """
    user = current_user  # User already validated by get_current_user
    user_id = user.id

    # Get tier value
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)

    # Handle legacy tier names
    tier_map = {
        'free': 'nest',
        'starter': 'flight',
        'pro': 'soar',
        'enterprise': 'stratosphere',
    }
    tier_value = tier_map.get(tier_value.lower(), tier_value.lower())

    try:
        tier_enum = SubscriptionTier(tier_value)
    except ValueError:
        tier_enum = SubscriptionTier.NEST

    tier_def = get_tier_definition(tier_enum)
    enforcer = TierEnforcer(tier_enum)

    # Get next tier for upgrade prompt
    next_tier = get_upgrade_path(tier_enum)
    next_tier_info = None
    if next_tier:
        next_def = get_tier_definition(next_tier)
        next_tier_info = {
            "tier": next_tier.value,
            "name": next_def["name"],
            "emoji": next_def["emoji"],
            "price": next_def["price"],
        }

    return {
        "user_id": user_id,
        "tier": tier_enum.value,
        "tier_name": tier_def["name"],
        "tier_emoji": tier_def["emoji"],
        "price": tier_def["price"],
        "subscription_started": user.subscription_started.isoformat() if user.subscription_started else None,
        "subscription_expires": user.subscription_expires.isoformat() if user.subscription_expires else None,
        "is_active": user.subscription_expires is None or user.subscription_expires > datetime.now(timezone.utc),
        "features": tier_def["features"],
        "limitations": tier_def.get("limitations", []),
        "next_tier": next_tier_info,
        "limits": {
            "stores": enforcer.get_limit("store_limit"),
            "products_per_week": enforcer.get_limit("products_per_week"),
            "aliexpress_searches_per_day": enforcer.get_limit("aliexpress_searches_per_day"),
            "team_seats": enforcer.get_limit("team_seats"),
        }
    }


@router.get("/check-access/{feature}")
async def check_feature_access(
    feature: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if user has access to a specific feature.

    Args:
        feature: Feature name (e.g., 'personal_learning', 'auto_ordering')

    User ID is extracted from JWT token - no query parameter needed.
    """
    user = current_user

    # Get tier
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    tier_map = {
        'free': 'nest',
        'starter': 'flight',
        'pro': 'soar',
        'enterprise': 'stratosphere',
    }
    tier_value = tier_map.get(tier_value.lower(), tier_value.lower())

    try:
        tier_enum = SubscriptionTier(tier_value)
    except ValueError:
        tier_enum = SubscriptionTier.NEST

    enforcer = TierEnforcer(tier_enum)
    has_access = enforcer.can_access(feature)

    response = {
        "feature": feature,
        "has_access": has_access,
        "current_tier": tier_enum.value,
    }

    if not has_access:
        upgrade_info = enforcer.get_upgrade_prompt(feature)
        if upgrade_info:
            response["upgrade"] = upgrade_info

    return response


@router.get("/check-limit/{limit_name}")
async def check_usage_limit(
    limit_name: str,
    current_usage: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if user is within a usage limit.

    Args:
        limit_name: Limit name (e.g., 'aliexpress_searches_per_day')
        current_usage: Current usage count

    User ID is extracted from JWT token - no query parameter needed.
    """
    user = current_user

    # Get tier
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    tier_map = {
        'free': 'nest',
        'starter': 'flight',
        'pro': 'soar',
        'enterprise': 'stratosphere',
    }
    tier_value = tier_map.get(tier_value.lower(), tier_value.lower())

    try:
        tier_enum = SubscriptionTier(tier_value)
    except ValueError:
        tier_enum = SubscriptionTier.NEST

    enforcer = TierEnforcer(tier_enum)
    limit = enforcer.get_limit(limit_name)
    within_limit = enforcer.within_limit(limit_name, current_usage)

    return {
        "limit_name": limit_name,
        "limit": limit,
        "limit_display": "Unlimited" if limit == -1 else limit,
        "current_usage": current_usage,
        "remaining": "Unlimited" if limit == -1 else max(0, limit - current_usage),
        "within_limit": within_limit,
        "current_tier": tier_enum.value,
    }


@router.get("/upgrade-options")
async def get_upgrade_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get available upgrade options for user.

    Returns tiers higher than user's current tier.
    User ID is extracted from JWT token - no query parameter needed.
    """
    user = current_user

    # Get current tier
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    tier_map = {
        'free': 'nest',
        'starter': 'flight',
        'pro': 'soar',
        'enterprise': 'stratosphere',
    }
    tier_value = tier_map.get(tier_value.lower(), tier_value.lower())

    try:
        current_tier = SubscriptionTier(tier_value)
    except ValueError:
        current_tier = SubscriptionTier.NEST

    # Get all tiers higher than current
    tier_order = [
        SubscriptionTier.NEST,
        SubscriptionTier.FLIGHT,
        SubscriptionTier.SOAR,
        SubscriptionTier.STRATOSPHERE,
    ]

    current_idx = tier_order.index(current_tier)
    upgrade_tiers = tier_order[current_idx + 1:]

    options = []
    for tier in upgrade_tiers:
        tier_def = get_tier_definition(tier)
        current_def = get_tier_definition(current_tier)

        options.append({
            "tier": tier.value,
            "name": tier_def["name"],
            "emoji": tier_def["emoji"],
            "tagline": tier_def["tagline"],
            "price": tier_def["price"],
            "price_display": tier_def["price_display"],
            "price_difference": tier_def["price"] - current_def["price"],
            "popular": tier_def.get("popular", False),
            "key_features": tier_def["features"][:5],  # Top 5 features
        })

    return {
        "current_tier": current_tier.value,
        "current_tier_name": get_tier_definition(current_tier)["name"],
        "upgrade_options": options,
    }


# ==================== ALIEXPRESS LIMITS ====================

@router.get("/aliexpress-limits")
async def get_aliexpress_limits():
    """
    Get AliExpress integration limits for all tiers.
    
    Returns:
        - Search results per query
        - Searches per day
        - Enrichment access (Dropshipping API)
        - Auto-ordering access
    """
    limits = {}
    
    for tier in SubscriptionTier:
        tier_def = get_tier_definition(tier)
        limits[tier.value] = {
            "name": tier_def["name"],
            "emoji": tier_def["emoji"],
            "price": tier_def["price"],
            "search_results_limit": "Unlimited" if tier_def["aliexpress_search_results_limit"] == -1 else tier_def["aliexpress_search_results_limit"],
            "searches_per_day": "Unlimited" if tier_def["aliexpress_searches_per_day"] == -1 else tier_def["aliexpress_searches_per_day"],
            "enrichment": tier_def["aliexpress_enrichment"],
            "auto_ordering": tier_def["aliexpress_auto_ordering"],
            "summary": _get_aliexpress_summary(tier_def)
        }
    
    return {
        "limits": limits,
        "tiers_order": ["nest", "flight", "soar", "stratosphere"],
        "notes": {
            "enrichment": "Access to Dropshipping API for real-time stock, shipping options, and SKU variants",
            "auto_ordering": "1-click order placement directly through AliExpress API"
        }
    }


def _get_aliexpress_summary(tier_def: Dict) -> str:
    """Generate a human-readable summary of AliExpress capabilities"""
    parts = []
    
    # Searches
    if tier_def["aliexpress_searches_per_day"] == -1:
        parts.append("Unlimited searches")
    else:
        parts.append(f"{tier_def['aliexpress_searches_per_day']} searches/day")
    
    # Results
    if tier_def["aliexpress_search_results_limit"] == -1:
        parts.append("unlimited results")
    else:
        parts.append(f"{tier_def['aliexpress_search_results_limit']} results/search")
    
    # Enrichment
    if tier_def["aliexpress_enrichment"]:
        parts.append("real-time stock & shipping data")
    
    # Auto-ordering
    if tier_def["aliexpress_auto_ordering"]:
        parts.append("1-click auto-ordering")
    
    return ", ".join(parts) if parts else "Basic access only"


# ==================== CHECKOUT HELPERS ====================

@router.get("/checkout-url/{tier}")
async def get_checkout_url(
    tier: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get checkout URL for a tier.

    Returns the LemonSqueezy checkout URL for the requested tier.
    User ID is extracted from JWT token - no query parameter needed.
    """
    from ospra_os.payments.lemonsqueezy import get_checkout_url_for_tier
    from urllib.parse import quote

    try:
        tier_enum = SubscriptionTier(tier.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {tier}"
        )

    if tier_enum == SubscriptionTier.NEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nest is the free tier - no checkout required"
        )

    checkout_url = get_checkout_url_for_tier(tier_enum)

    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Checkout URL not configured for this tier"
        )

    # Add user email/id to checkout for tracking (URL-encode email)
    user = current_user
    user_id = user.id
    encoded_email = quote(user.email, safe='')
    checkout_url = f"{checkout_url}?checkout[email]={encoded_email}&checkout[custom][user_id]={user_id}"

    return {
        "tier": tier_enum.value,
        "checkout_url": checkout_url,
    }


# ==================== USAGE TRACKING ENDPOINTS ====================
# SECURITY: All usage endpoints extract user_id from JWT token
# Users can only view/modify their own usage data

@router.get("/usage/me")
async def get_user_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete usage dashboard for the current user.

    Returns current usage across all tracked actions with limits.
    User ID is extracted from JWT token.
    """
    from ospra_os.core.usage_tracking import get_enforcer

    user_id = current_user.id
    enforcer = get_enforcer(db)
    dashboard = enforcer.get_usage_dashboard(user_id)
    return dashboard


@router.get("/usage/me/check/{action}")
async def check_usage_limit_action(
    action: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user can perform a specific action.

    Actions: product_discovery, aliexpress_search, aliexpress_enrichment,
             product_deploy, email_automation, ai_query, ai_briefing, inventory_check

    User ID is extracted from JWT token.
    """
    from ospra_os.core.usage_tracking import get_enforcer

    user_id = current_user.id
    enforcer = get_enforcer(db)
    result = enforcer.can_perform(user_id, action)
    return result


@router.post("/usage/me/record/{action}")
async def record_usage(
    action: str,
    count: int = 1,
    store_id: int = None,
    product_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record that current user performed an action.

    This increments usage counters for the user.
    User ID is extracted from JWT token.
    """
    from ospra_os.core.usage_tracking import get_enforcer

    user_id = current_user.id
    enforcer = get_enforcer(db)

    # First check if allowed
    check = enforcer.can_perform(user_id, action, count)
    if not check.get("allowed", True):
        return {
            "success": False,
            "reason": check.get("reason", "Limit reached"),
            "upgrade_suggestion": check.get("upgrade_suggestion")
        }

    # Record the action
    result = enforcer.record_action(
        user_id=user_id,
        action=action,
        count=count,
        store_id=store_id,
        product_id=product_id
    )
    return result


@router.get("/usage/me/history/{action}")
async def get_usage_history(
    action: str,
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get usage history for a specific action.

    Returns daily counts for the past N days.
    User ID is extracted from JWT token.
    """
    from ospra_os.core.usage_tracking import get_tracker, TierUsageEnforcer

    config = TierUsageEnforcer.ACTION_CONFIG.get(action)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action: {action}"
        )

    user_id = current_user.id
    tracker = get_tracker(db)
    history = tracker.get_usage_history(
        user_id=user_id,
        usage_type=config["usage_type"],
        days=days
    )
    return {
        "action": action,
        "days": days,
        "history": history
    }


@router.get("/usage/summary")
async def get_usage_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get platform-wide usage summary (admin endpoint).

    Returns aggregate usage stats across all users.
    SECURITY: Requires admin privileges.
    """
    # SECURITY: Check if user is admin
    if not getattr(current_user, 'is_admin', False) and not getattr(current_user, 'is_superuser', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    from sqlalchemy import func
    from ospra_os.core.usage_tracking import DailyUsage, WeeklyUsage
    from datetime import date

    today = date.today()

    # Daily totals by type
    daily_stats = db.query(
        DailyUsage.usage_type,
        func.sum(DailyUsage.count).label("total"),
        func.count(DailyUsage.user_id.distinct()).label("unique_users")
    ).filter(
        DailyUsage.usage_date == today
    ).group_by(DailyUsage.usage_type).all()

    return {
        "date": today.isoformat(),
        "daily_usage": [
            {
                "type": stat[0],
                "total_count": stat[1],
                "unique_users": stat[2]
            }
            for stat in daily_stats
        ]
    }
