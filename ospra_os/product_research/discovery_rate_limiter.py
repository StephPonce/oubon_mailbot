"""
DISCOVERY RATE LIMITER
======================

Prevents tier abuse by limiting discovery requests per tier.
Nest users can't spam refresh and cost more than paying users.

Rate Limits:
- Nest: 3/day, 1 per 4 hours
- Flight: 10/day, 1 per 2 hours  
- Soar: Unlimited, 1 per 30 min
- Stratosphere: Unlimited, 1 per 5 min + on-demand
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from enum import Enum
import logging

from ospra_os.core.tiers import SubscriptionTier

logger = logging.getLogger(__name__)


# Rate limit configuration per tier
TIER_RATE_LIMITS: Dict[SubscriptionTier, Dict] = {
    SubscriptionTier.NEST: {
        "daily_limit": 3,
        "cooldown_minutes": 240,  # 4 hours
        "on_demand": False,
        "message": "Free tier allows 3 discoveries per day. Upgrade to Flight for more."
    },
    SubscriptionTier.FLIGHT: {
        "daily_limit": 10,
        "cooldown_minutes": 120,  # 2 hours
        "on_demand": False,
        "message": "Flight tier allows 10 discoveries per day. Upgrade to Soar for unlimited."
    },
    SubscriptionTier.SOAR: {
        "daily_limit": -1,  # Unlimited
        "cooldown_minutes": 30,
        "on_demand": False,
        "message": "Please wait 30 minutes between discoveries."
    },
    SubscriptionTier.STRATOSPHERE: {
        "daily_limit": -1,  # Unlimited
        "cooldown_minutes": 5,
        "on_demand": True,  # Can bypass cooldown
        "message": "Stratosphere tier - minimal cooldown."
    },
}


class RateLimitResult:
    """Result of a rate limit check."""
    
    def __init__(
        self,
        allowed: bool,
        reason: Optional[str] = None,
        retry_after_seconds: Optional[int] = None,
        daily_remaining: Optional[int] = None,
        upgrade_tier: Optional[SubscriptionTier] = None
    ):
        self.allowed = allowed
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds
        self.daily_remaining = daily_remaining
        self.upgrade_tier = upgrade_tier
    
    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "retry_after_seconds": self.retry_after_seconds,
            "retry_after_display": self._format_time(self.retry_after_seconds) if self.retry_after_seconds else None,
            "daily_remaining": self.daily_remaining,
            "upgrade_tier": self.upgrade_tier.value if self.upgrade_tier else None
        }
    
    def _format_time(self, seconds: int) -> str:
        """Format seconds as human-readable time."""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes:
                return f"{hours}h {minutes}m"
            return f"{hours} hour{'s' if hours != 1 else ''}"


class DiscoveryRateLimiter:
    """
    Rate limiter for product discovery.
    
    Tracks:
    - Daily usage count per user
    - Last discovery timestamp per user
    - Enforces tier-specific limits
    """
    
    def __init__(self):
        # In-memory storage (replace with Redis in production)
        self._daily_counts: Dict[int, Dict] = {}  # {user_id: {"date": date, "count": int}}
        self._last_discovery: Dict[int, datetime] = {}  # {user_id: datetime}
    
    def _get_today(self) -> str:
        """Get today's date string for daily tracking."""
        return datetime.utcnow().strftime("%Y-%m-%d")
    
    def _get_daily_count(self, user_id: int) -> int:
        """Get user's discovery count for today."""
        today = self._get_today()
        user_data = self._daily_counts.get(user_id, {})
        
        if user_data.get("date") != today:
            # New day, reset count
            return 0
        
        return user_data.get("count", 0)
    
    def _increment_daily_count(self, user_id: int):
        """Increment user's daily discovery count."""
        today = self._get_today()
        user_data = self._daily_counts.get(user_id, {})
        
        if user_data.get("date") != today:
            # New day, reset
            self._daily_counts[user_id] = {"date": today, "count": 1}
        else:
            self._daily_counts[user_id]["count"] = user_data.get("count", 0) + 1
    
    def _get_seconds_since_last(self, user_id: int) -> Optional[int]:
        """Get seconds since user's last discovery."""
        last = self._last_discovery.get(user_id)
        if not last:
            return None
        
        delta = datetime.utcnow() - last
        return int(delta.total_seconds())
    
    def _update_last_discovery(self, user_id: int):
        """Update user's last discovery timestamp."""
        self._last_discovery[user_id] = datetime.utcnow()
    
    def check_rate_limit(
        self,
        user_id: int,
        tier: SubscriptionTier,
        force: bool = False
    ) -> RateLimitResult:
        """
        Check if user can perform a discovery.
        
        Args:
            user_id: User's ID
            tier: User's subscription tier
            force: If True and tier allows, bypass cooldown (Stratosphere only)
        
        Returns:
            RateLimitResult with allowed status and details
        """
        limits = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS[SubscriptionTier.NEST])
        
        daily_limit = limits["daily_limit"]
        cooldown_minutes = limits["cooldown_minutes"]
        on_demand = limits["on_demand"]
        
        # Check daily limit (if not unlimited)
        daily_count = self._get_daily_count(user_id)
        
        if daily_limit != -1 and daily_count >= daily_limit:
            # Daily limit reached
            next_tier = self._get_upgrade_tier(tier)
            
            return RateLimitResult(
                allowed=False,
                reason=f"Daily limit reached ({daily_count}/{daily_limit}). {limits['message']}",
                retry_after_seconds=self._seconds_until_midnight(),
                daily_remaining=0,
                upgrade_tier=next_tier
            )
        
        # Check cooldown
        seconds_since = self._get_seconds_since_last(user_id)
        cooldown_seconds = cooldown_minutes * 60
        
        if seconds_since is not None and seconds_since < cooldown_seconds:
            # In cooldown period
            
            # Stratosphere can force bypass
            if force and on_demand:
                logger.info(f"[START] User {user_id} (Stratosphere) using on-demand discovery")
                return RateLimitResult(
                    allowed=True,
                    daily_remaining=daily_limit - daily_count - 1 if daily_limit != -1 else -1
                )
            
            retry_after = cooldown_seconds - seconds_since
            next_tier = self._get_upgrade_tier(tier)
            
            return RateLimitResult(
                allowed=False,
                reason=f"Please wait before next discovery. {limits['message']}",
                retry_after_seconds=retry_after,
                daily_remaining=daily_limit - daily_count if daily_limit != -1 else -1,
                upgrade_tier=next_tier if not on_demand else None
            )
        
        # Allowed!
        remaining = daily_limit - daily_count - 1 if daily_limit != -1 else -1
        
        return RateLimitResult(
            allowed=True,
            daily_remaining=remaining
        )
    
    def record_discovery(self, user_id: int):
        """Record that a discovery was performed."""
        self._increment_daily_count(user_id)
        self._update_last_discovery(user_id)
        
        count = self._get_daily_count(user_id)
        logger.info(f"[STATS] User {user_id} discovery recorded (today: {count})")
    
    def get_user_status(self, user_id: int, tier: SubscriptionTier) -> dict:
        """Get user's current rate limit status."""
        limits = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS[SubscriptionTier.NEST])
        daily_limit = limits["daily_limit"]
        cooldown_minutes = limits["cooldown_minutes"]
        
        daily_count = self._get_daily_count(user_id)
        seconds_since = self._get_seconds_since_last(user_id)
        
        cooldown_remaining = 0
        if seconds_since is not None:
            cooldown_remaining = max(0, (cooldown_minutes * 60) - seconds_since)
        
        return {
            "tier": tier.value,
            "daily_limit": "Unlimited" if daily_limit == -1 else daily_limit,
            "daily_used": daily_count,
            "daily_remaining": "Unlimited" if daily_limit == -1 else max(0, daily_limit - daily_count),
            "cooldown_minutes": cooldown_minutes,
            "cooldown_remaining_seconds": cooldown_remaining,
            "cooldown_remaining_display": self._format_cooldown(cooldown_remaining),
            "can_discover_now": cooldown_remaining == 0 and (daily_limit == -1 or daily_count < daily_limit),
            "on_demand_available": limits["on_demand"]
        }
    
    def _get_upgrade_tier(self, current: SubscriptionTier) -> Optional[SubscriptionTier]:
        """Get the next tier up for upgrade prompt."""
        order = [
            SubscriptionTier.NEST,
            SubscriptionTier.FLIGHT,
            SubscriptionTier.SOAR,
            SubscriptionTier.STRATOSPHERE
        ]
        
        try:
            idx = order.index(current)
            if idx < len(order) - 1:
                return order[idx + 1]
        except ValueError:
            pass
        
        return None
    
    def _seconds_until_midnight(self) -> int:
        """Get seconds until midnight UTC (daily reset)."""
        now = datetime.utcnow()
        midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
        return int((midnight - now).total_seconds())
    
    def _format_cooldown(self, seconds: int) -> str:
        """Format cooldown as human-readable string."""
        if seconds <= 0:
            return "Ready"
        elif seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"


# Singleton instance
_rate_limiter: Optional[DiscoveryRateLimiter] = None


def get_discovery_rate_limiter() -> DiscoveryRateLimiter:
    """Get or create the singleton rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = DiscoveryRateLimiter()
    return _rate_limiter
