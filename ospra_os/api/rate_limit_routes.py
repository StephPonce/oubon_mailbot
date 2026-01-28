"""
Rate Limit Status Routes
========================
Provides rate limit status for discovery and other features
"""

from fastapi import APIRouter, Query
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rate-limit", tags=["Rate Limits"])


# Discovery limits by tier
DISCOVERY_LIMITS = {
    "Nest": {"daily_limit": 10, "hourly_limit": 3},
    "Flight": {"daily_limit": 50, "hourly_limit": 15},
    "Soar": {"daily_limit": 200, "hourly_limit": 50},
    "Stratosphere": {"daily_limit": -1, "hourly_limit": -1}  # Unlimited
}


@router.get("/discovery/status")
async def get_discovery_rate_limit_status(
    tier: str = Query("Nest", description="User's subscription tier")
):
    """
    Get rate limit status for product discovery
    
    Returns remaining quota for the current period
    
    **Example:**
    ```
    GET /api/rate-limit/discovery/status?tier=Flight
    ```
    """
    try:
        tier_normalized = tier.capitalize() if tier else "Nest"
        limits = DISCOVERY_LIMITS.get(tier_normalized, DISCOVERY_LIMITS["Nest"])
        
        daily_limit = limits["daily_limit"]
        hourly_limit = limits["hourly_limit"]
        
        # For unlimited tiers
        if daily_limit == -1:
            return {
                "tier": tier_normalized,
                "daily_remaining": "∞",
                "daily_limit": "∞",
                "hourly_remaining": "∞",
                "hourly_limit": "∞",
                "is_unlimited": True
            }
        
        # TODO: In production, track actual usage in database
        # For now, return full quota (simulating fresh day)
        return {
            "tier": tier_normalized,
            "daily_remaining": daily_limit,
            "daily_limit": daily_limit,
            "hourly_remaining": hourly_limit,
            "hourly_limit": hourly_limit,
            "is_unlimited": False
        }
        
    except Exception as e:
        logger.error(f"Rate limit status error: {e}")
        # Return safe defaults on error
        return {
            "tier": "Unknown",
            "daily_remaining": 10,
            "daily_limit": 10,
            "hourly_remaining": 3,
            "hourly_limit": 3,
            "is_unlimited": False,
            "error": "Failed to get rate limit status"
        }


@router.get("/email/status")
async def get_email_rate_limit_status(
    tier: str = Query("Nest", description="User's subscription tier")
):
    """
    Get rate limit status for email automation
    """
    email_limits = {
        "Nest": {"daily_limit": 20, "monthly_limit": 200},
        "Flight": {"daily_limit": 100, "monthly_limit": 2000},
        "Soar": {"daily_limit": 500, "monthly_limit": 10000},
        "Stratosphere": {"daily_limit": -1, "monthly_limit": -1}
    }
    
    tier_normalized = tier.capitalize() if tier else "Nest"
    limits = email_limits.get(tier_normalized, email_limits["Nest"])
    
    if limits["daily_limit"] == -1:
        return {
            "tier": tier_normalized,
            "daily_remaining": "∞",
            "daily_limit": "∞",
            "monthly_remaining": "∞",
            "monthly_limit": "∞",
            "is_unlimited": True
        }
    
    return {
        "tier": tier_normalized,
        "daily_remaining": limits["daily_limit"],
        "daily_limit": limits["daily_limit"],
        "monthly_remaining": limits["monthly_limit"],
        "monthly_limit": limits["monthly_limit"],
        "is_unlimited": False
    }


@router.get("/ai/status")
async def get_ai_rate_limit_status(
    tier: str = Query("Nest", description="User's subscription tier")
):
    """
    Get rate limit status for AI requests (Oi chat, analysis, etc.)
    """
    ai_limits = {
        "Nest": {"daily_limit": 25, "context_window": 4000},
        "Flight": {"daily_limit": 100, "context_window": 8000},
        "Soar": {"daily_limit": 500, "context_window": 16000},
        "Stratosphere": {"daily_limit": -1, "context_window": 32000}
    }
    
    tier_normalized = tier.capitalize() if tier else "Nest"
    limits = ai_limits.get(tier_normalized, ai_limits["Nest"])
    
    if limits["daily_limit"] == -1:
        return {
            "tier": tier_normalized,
            "daily_remaining": "∞",
            "daily_limit": "∞",
            "context_window": limits["context_window"],
            "is_unlimited": True
        }
    
    return {
        "tier": tier_normalized,
        "daily_remaining": limits["daily_limit"],
        "daily_limit": limits["daily_limit"],
        "context_window": limits["context_window"],
        "is_unlimited": False
    }
