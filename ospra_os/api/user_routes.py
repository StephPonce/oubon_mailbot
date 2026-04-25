"""
User API Routes
===============

Endpoints for user profile and subscription management:
- GET /api/user/profile - Get user profile
- PATCH /api/user/profile - Update user profile
- POST /api/user/set-tier - Set user tier (admin/dev)
- GET /api/user/api-key - Get API key
- POST /api/user/api-key - Generate new API key
"""

import os
import secrets
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from ospra_os.auth.jwt_auth import get_current_user, get_db, user_to_dict
from ospra_os.database import User, SubscriptionTier, UserSettings


router = APIRouter(prefix="/api/user", tags=["User"])


# ============================================================================
# REQUEST MODELS
# ============================================================================

class ProfileUpdate(BaseModel):
    """Profile update request

    SECURITY: Name field has length limits.
    """
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="User's display name"
    )


class TierUpdate(BaseModel):
    """Tier update request (for admin/dev)

    SECURITY: Tier restricted to valid enum values.
    """
    tier: Literal["nest", "flight", "soar", "stratosphere"] = Field(
        ...,
        description="Subscription tier"
    )


class SubscriptionUpgrade(BaseModel):
    """Subscription upgrade request

    SECURITY: Tier restricted to valid enum values.
    """
    tier: Literal["nest", "flight", "soar", "stratosphere"] = Field(
        ...,
        description="Target subscription tier"
    )


# ============================================================================
# PROFILE ENDPOINTS
# ============================================================================

@router.get("/profile")
async def get_profile(user: User = Depends(get_current_user)):
    """Get current user's full profile"""
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    
    return {
        "success": True,
        "profile": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "tier": tier_value,
            "subscription_tier": tier_value,
            "subscription_started": user.subscription_started.isoformat() if user.subscription_started else None,
            "subscription_expires": user.subscription_expires.isoformat() if user.subscription_expires else None,
            "total_stores": user.total_stores,
            "total_products": user.total_products,
            "total_revenue": user.total_revenue,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }
    }


@router.patch("/profile")
async def update_profile(
    update: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile"""
    if update.name is not None:
        if not update.name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name cannot be empty"
            )
        user.name = update.name.strip()
    
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    
    return {
        "success": True,
        "message": "Profile updated successfully",
        "user": user_to_dict(user)
    }


# ============================================================================
# TIER MANAGEMENT
# ============================================================================

@router.post("/set-tier")
async def set_tier(
    update: TierUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set user subscription tier.
    
    This is for development/testing. In production, tier changes
    would go through the payment system (LemonSqueezy webhooks).
    """
    # Validate tier
    tier_map = {
        "nest": SubscriptionTier.NEST,
        "flight": SubscriptionTier.FLIGHT,
        "soar": SubscriptionTier.SOAR,
        "stratosphere": SubscriptionTier.STRATOSPHERE,
        # Legacy aliases
        "free": SubscriptionTier.NEST,
        "starter": SubscriptionTier.FLIGHT,
        "pro": SubscriptionTier.SOAR,
        "enterprise": SubscriptionTier.STRATOSPHERE,
    }
    
    tier_lower = update.tier.lower()
    if tier_lower not in tier_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier. Must be one of: {list(tier_map.keys())}"
        )
    
    new_tier = tier_map[tier_lower]
    user.subscription_tier = new_tier
    user.subscription_started = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(user)
    
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    
    return {
        "success": True,
        "message": f"Tier updated to {tier_value}",
        "user": {
            **user_to_dict(user),
            "tier": tier_value,
        }
    }


@router.get("/tier")
async def get_tier(user: User = Depends(get_current_user)):
    """Get current user's subscription tier and limits"""
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    
    # Tier limits
    tier_limits = {
        "nest": {
            "stores": 1,
            "products_per_month": 50,
            "early_access_days": 0,
            "ai_budget": 5.0,
        },
        "flight": {
            "stores": 3,
            "products_per_month": 500,
            "early_access_days": 1,
            "ai_budget": 25.0,
        },
        "soar": {
            "stores": 10,
            "products_per_month": -1,  # Unlimited
            "early_access_days": 7,
            "ai_budget": 100.0,
        },
        "stratosphere": {
            "stores": -1,  # Unlimited
            "products_per_month": -1,
            "early_access_days": 30,
            "ai_budget": -1,  # Unlimited
        },
    }
    
    limits = tier_limits.get(tier_value.lower(), tier_limits["nest"])
    
    return {
        "success": True,
        "tier": tier_value,
        "limits": limits,
        "started": user.subscription_started.isoformat() if user.subscription_started else None,
        "expires": user.subscription_expires.isoformat() if user.subscription_expires else None,
    }


# ============================================================================
# SUBSCRIPTION UPGRADE
# ============================================================================

@router.post("/upgrade")
async def upgrade_subscription(
    request: SubscriptionUpgrade,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiate subscription upgrade.
    
    In production, this would redirect to LemonSqueezy checkout.
    For now, it directly updates the tier (for testing).
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
            detail=f"Invalid tier: {request.tier}"
        )
    
    # In production, this would create a LemonSqueezy checkout session
    # For now, directly update the tier
    
    new_tier = tier_map[tier_lower]
    user.subscription_tier = new_tier
    user.subscription_started = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(user)
    
    tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
    
    return {
        "success": True,
        "message": f"Upgraded to {tier_value}",
        # In production: "checkout_url": "https://lemonsqueezy.com/checkout/..."
    }


# ============================================================================
# API KEY MANAGEMENT
# ============================================================================

@router.get("/api-key")
async def get_api_key_info(user: User = Depends(get_current_user)):
    """Get API key info (not the actual key)"""
    # Check if user has an API key stored
    has_key = False
    if hasattr(user, 'custom_ai_keys') and user.custom_ai_keys:
        has_key = 'ospra_api_key' in user.custom_ai_keys
    
    return {
        "success": True,
        "has_key": has_key,
        "message": "Use POST to generate a new API key" if not has_key else "API key exists"
    }


@router.post("/api-key")
async def generate_api_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a new API key for the user"""
    # Generate secure random key
    api_key = f"ospra_{secrets.token_urlsafe(32)}"
    
    # Store hashed version (in production, we'd hash this)
    if not user.custom_ai_keys:
        user.custom_ai_keys = {}
    
    user.custom_ai_keys['ospra_api_key'] = api_key[:10] + "..." # Store only prefix for reference
    user.custom_ai_keys['ospra_api_key_created'] = datetime.now(timezone.utc).isoformat()
    
    db.commit()
    
    return {
        "success": True,
        "api_key": api_key,
        "message": "API key generated. Save it now - it won't be shown again.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }


# ============================================================================
# SETTINGS ENDPOINTS
# ============================================================================

@router.get("/settings")
async def get_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user settings"""
    # Get or create settings
    settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return {
        "success": True,
        "settings": {
            "auto_discover_products": settings.auto_discover_products,
            "min_discovery_score": settings.min_discovery_score,
            "max_supplier_cost": settings.max_supplier_cost,
            "preferred_niches": settings.preferred_niches or [],
            "auto_deploy_to_shopify": settings.auto_deploy_to_shopify,
            "auto_generate_content": settings.auto_generate_content,
            "email_notifications": settings.email_notifications,
            "notify_new_products": settings.notify_new_products,
            "notify_price_drops": settings.notify_price_drops,
            "notify_trend_spikes": settings.notify_trend_spikes,
            "default_currency": settings.default_currency,
            "default_timezone": settings.default_timezone,
        }
    }


@router.patch("/settings")
async def update_settings(
    updates: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user settings"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
    
    # Update allowed fields
    allowed_fields = [
        'auto_discover_products', 'min_discovery_score', 'max_supplier_cost',
        'preferred_niches', 'auto_deploy_to_shopify', 'auto_generate_content',
        'email_notifications', 'notify_new_products', 'notify_price_drops',
        'notify_trend_spikes', 'default_currency', 'default_timezone'
    ]
    
    for field in allowed_fields:
        if field in updates:
            setattr(settings, field, updates[field])
    
    settings.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    return {
        "success": True,
        "message": "Settings updated"
    }
