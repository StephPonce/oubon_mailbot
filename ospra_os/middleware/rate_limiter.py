"""
TIER-AWARE RATE LIMITING
=========================

Prevents Nest (free) users from abusing discovery and costing more
than paying subscribers.

Rate limits:
- Nest: 3 discoveries/day, min 4 hours between
- Flight: 10 discoveries/day, min 2 hours between  
- Soar: Unlimited, min 30 min between
- Stratosphere: Unlimited, min 5 min between (+ on-demand override)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from collections import defaultdict
import json

from ospra_os.core.tiers import SubscriptionTier, get_tier_feature

logger = logging.getLogger(__name__)


# Rate limit configuration by tier
TIER_RATE_LIMITS = {
    SubscriptionTier.NEST: {
        "max_per_day": 3,
        "min_interval_minutes": 240,  # 4 hours
        "allow_on_demand": False,
    },
    SubscriptionTier.FLIGHT: {
        "max_per_day": 10,
        "min_interval_minutes": 120,  # 2 hours
        "allow_on_demand": False,
    },
    SubscriptionTier.SOAR: {
        "max_per_day": -1,  # Unlimited
        "min_interval_minutes": 30,
        "allow_on_demand": False,
    },
    SubscriptionTier.STRATOSPHERE: {
        "max_per_day": -1,  # Unlimited
        "min_interval_minutes": 5,
        "allow_on_demand": True,  # Can bypass with on-demand flag
    },
}


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after_minutes: int, tier: str):
        self.message = message
        self.retry_after_minutes = retry_after_minutes
        self.tier = tier
        super().__init__(message)


class TierRateLimiter:
    """
    Rate limiter that respects subscription tiers.
    
    Tracks:
    - Last request time per user
    - Daily request count per user
    - Resets daily counts at midnight UTC
    """
    
    def __init__(self):
        # In-memory storage (replace with Redis in production)
        self._last_request: Dict[int, datetime] = {}
        self._daily_counts: Dict[int, Dict[str, int]] = defaultdict(lambda: {"count": 0, "date": None})
        
    def _get_today(self) -> str:
        """Get today's date string for daily reset tracking."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def _reset_if_new_day(self, user_id: int):
        """Reset daily count if it's a new day."""
        today = self._get_today()
        if self._daily_counts[user_id]["date"] != today:
            self._daily_counts[user_id] = {"count": 0, "date": today}
    
    def check_rate_limit(
        self,
        user_id: int,
        tier: SubscriptionTier,
        action: str = "discovery",
        on_demand: bool = False
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if user can perform action.
        
        Returns:
            (allowed, error_message, retry_after_minutes)
        """
        limits = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS[SubscriptionTier.NEST])
        
        # Stratosphere with on-demand can bypass
        if on_demand and limits["allow_on_demand"]:
            logger.info(f"[START] User {user_id} using on-demand {action} (Stratosphere)")
            return True, None, None
        
        # Check daily limit
        self._reset_if_new_day(user_id)
        daily_count = self._daily_counts[user_id]["count"]
        max_per_day = limits["max_per_day"]
        
        if max_per_day != -1 and daily_count >= max_per_day:
            hours_until_reset = 24 - datetime.now(timezone.utc).hour
            return False, f"Daily limit reached ({max_per_day}/{max_per_day}). Resets in {hours_until_reset} hours.", hours_until_reset * 60
        
        # Check interval limit
        last_request = self._last_request.get(user_id)
        min_interval = timedelta(minutes=limits["min_interval_minutes"])
        
        if last_request:
            time_since_last = datetime.now(timezone.utc) - last_request
            if time_since_last < min_interval:
                remaining = min_interval - time_since_last
                remaining_minutes = int(remaining.total_seconds() / 60) + 1
                return False, f"Please wait {remaining_minutes} minutes before next {action}.", remaining_minutes
        
        return True, None, None
    
    def record_request(self, user_id: int, action: str = "discovery"):
        """Record that a request was made."""
        self._reset_if_new_day(user_id)
        self._last_request[user_id] = datetime.now(timezone.utc)
        self._daily_counts[user_id]["count"] += 1
        
        logger.info(f"[STATS] User {user_id} {action}: {self._daily_counts[user_id]['count']} today")
    
    def get_user_status(self, user_id: int, tier: SubscriptionTier) -> Dict:
        """Get rate limit status for a user."""
        limits = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS[SubscriptionTier.NEST])
        self._reset_if_new_day(user_id)
        
        daily_count = self._daily_counts[user_id]["count"]
        max_per_day = limits["max_per_day"]
        last_request = self._last_request.get(user_id)
        
        # Calculate next available time
        next_available = None
        if last_request:
            min_interval = timedelta(minutes=limits["min_interval_minutes"])
            next_time = last_request + min_interval
            if next_time > datetime.now(timezone.utc):
                next_available = next_time.isoformat()
        
        return {
            "tier": tier.value,
            "daily_limit": "Unlimited" if max_per_day == -1 else max_per_day,
            "daily_used": daily_count,
            "daily_remaining": "Unlimited" if max_per_day == -1 else max(0, max_per_day - daily_count),
            "min_interval_minutes": limits["min_interval_minutes"],
            "last_request": last_request.isoformat() if last_request else None,
            "next_available": next_available,
            "can_on_demand": limits["allow_on_demand"],
        }
    
    def get_upgrade_message(self, tier: SubscriptionTier) -> Optional[str]:
        """Get upgrade suggestion based on current tier."""
        if tier == SubscriptionTier.NEST:
            return "Upgrade to Flight ($29/mo) for 10 discoveries/day and 2-hour intervals"
        elif tier == SubscriptionTier.FLIGHT:
            return "Upgrade to Soar ($79/mo) for unlimited discoveries with 30-minute intervals"
        elif tier == SubscriptionTier.SOAR:
            return "Upgrade to Stratosphere ($199/mo) for 5-minute intervals and on-demand discovery"
        return None


# Singleton instance
_rate_limiter: Optional[TierRateLimiter] = None


def get_rate_limiter() -> TierRateLimiter:
    """Get or create the rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = TierRateLimiter()
    return _rate_limiter


async def check_discovery_rate_limit(
    user_id: int,
    tier: SubscriptionTier,
    on_demand: bool = False
) -> Dict:
    """
    Check if user can run discovery.
    
    Returns dict with:
    - allowed: bool
    - error: optional error message
    - retry_after_minutes: optional wait time
    - status: current rate limit status
    - upgrade_message: optional upgrade suggestion
    """
    limiter = get_rate_limiter()
    
    allowed, error, retry_after = limiter.check_rate_limit(
        user_id=user_id,
        tier=tier,
        action="discovery",
        on_demand=on_demand
    )
    
    result = {
        "allowed": allowed,
        "error": error,
        "retry_after_minutes": retry_after,
        "status": limiter.get_user_status(user_id, tier),
    }
    
    if not allowed:
        result["upgrade_message"] = limiter.get_upgrade_message(tier)
    
    return result


def record_discovery(user_id: int):
    """Record that discovery was performed."""
    limiter = get_rate_limiter()
    limiter.record_request(user_id, "discovery")
