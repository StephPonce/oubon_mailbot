"""
Usage Tracking System for Ospra OS
===================================
Tracks all user actions for tier enforcement and analytics.

Tracks:
- Product discoveries (per week)
- AliExpress searches (per day)
- Deploys (per week)
- Email automations (per day)
- AI queries (per day)
- Ad campaigns created (per month)

Resets:
- Daily counters reset at midnight UTC
- Weekly counters reset Sunday midnight UTC
- Monthly counters reset 1st of month UTC
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Index, JSON, Date, UniqueConstraint
)
from sqlalchemy.orm import relationship, Session
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import logging

# Import base from existing models
from ospra_os.database.multi_store_models import Base, engine, SessionLocal

logger = logging.getLogger(__name__)


# ============================================================================
# USAGE TRACKING MODELS
# ============================================================================

class UsageType(str, Enum):
    """Types of tracked usage"""
    PRODUCT_DISCOVERY = "product_discovery"
    ALIEXPRESS_SEARCH = "aliexpress_search"
    ALIEXPRESS_ENRICHMENT = "aliexpress_enrichment"
    PRODUCT_DEPLOY = "product_deploy"
    EMAIL_AUTOMATION = "email_automation"
    AI_QUERY = "ai_query"
    AI_BRIEFING = "ai_briefing"
    AD_CAMPAIGN = "ad_campaign"
    INVENTORY_CHECK = "inventory_check"


class ResetPeriod(str, Enum):
    """How often usage counters reset"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class DailyUsage(Base):
    """Track daily usage per user per action type"""
    __tablename__ = "daily_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # What's being tracked
    usage_type = Column(String(50), nullable=False, index=True)
    usage_date = Column(Date, nullable=False, index=True)
    
    # Counts
    count = Column(Integer, default=0, nullable=False)

    # Metadata (optional details)
    extra_metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'usage_type', 'usage_date', name='unique_daily_usage'),
        Index('idx_daily_usage_lookup', 'user_id', 'usage_type', 'usage_date'),
    )
    
    def __repr__(self):
        return f"<DailyUsage user={self.user_id} type={self.usage_type} date={self.usage_date} count={self.count}>"


class WeeklyUsage(Base):
    """Track weekly usage per user per action type"""
    __tablename__ = "weekly_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # What's being tracked
    usage_type = Column(String(50), nullable=False, index=True)
    week_start = Column(Date, nullable=False, index=True)  # Always a Sunday
    
    # Counts
    count = Column(Integer, default=0, nullable=False)
    
    # Metadata
    extra_metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'usage_type', 'week_start', name='unique_weekly_usage'),
        Index('idx_weekly_usage_lookup', 'user_id', 'usage_type', 'week_start'),
    )
    
    def __repr__(self):
        return f"<WeeklyUsage user={self.user_id} type={self.usage_type} week={self.week_start} count={self.count}>"


class MonthlyUsage(Base):
    """Track monthly usage per user per action type"""
    __tablename__ = "monthly_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # What's being tracked
    usage_type = Column(String(50), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)  # 1-12
    
    # Counts
    count = Column(Integer, default=0, nullable=False)
    
    # Metadata
    extra_metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'usage_type', 'year', 'month', name='unique_monthly_usage'),
        Index('idx_monthly_usage_lookup', 'user_id', 'usage_type', 'year', 'month'),
    )
    
    def __repr__(self):
        return f"<MonthlyUsage user={self.user_id} type={self.usage_type} {self.year}-{self.month} count={self.count}>"


class UsageEvent(Base):
    """
    Individual usage events for detailed analytics.
    This is the raw log - DailyUsage/WeeklyUsage are aggregates.
    """
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Event details
    usage_type = Column(String(50), nullable=False, index=True)
    event_time = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Context
    store_id = Column(Integer, nullable=True)
    product_id = Column(Integer, nullable=True)
    
    # Event-specific data
    event_data = Column(JSON, default=dict)
    
    # Cost tracking (for AI queries, API calls)
    cost_usd = Column(Float, default=0.0)
    
    __table_args__ = (
        Index('idx_usage_event_user_time', 'user_id', 'event_time'),
        Index('idx_usage_event_type_time', 'usage_type', 'event_time'),
    )
    
    def __repr__(self):
        return f"<UsageEvent user={self.user_id} type={self.usage_type} time={self.event_time}>"


# ============================================================================
# USAGE TRACKER CLASS
# ============================================================================

class UsageTracker:
    """
    Main interface for tracking and querying usage.
    
    Usage:
        tracker = UsageTracker(db_session)
        
        # Record usage
        tracker.record(user_id=1, usage_type=UsageType.PRODUCT_DISCOVERY)
        
        # Check limits
        can_search = tracker.check_limit(user_id=1, usage_type=UsageType.ALIEXPRESS_SEARCH, limit=50)
        
        # Get current usage
        usage = tracker.get_usage(user_id=1, usage_type=UsageType.PRODUCT_DISCOVERY, period="weekly")
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    @staticmethod
    def get_week_start(d: date = None) -> date:
        """Get Sunday of the current week"""
        if d is None:
            d = date.today()
        # Monday is 0, Sunday is 6
        days_since_sunday = (d.weekday() + 1) % 7
        return d - timedelta(days=days_since_sunday)
    
    def record(
        self,
        user_id: int,
        usage_type: UsageType,
        count: int = 1,
        store_id: int = None,
        product_id: int = None,
        event_data: dict = None,
        cost_usd: float = 0.0
    ) -> Dict[str, Any]:
        """
        Record a usage event and update aggregates.
        
        Returns dict with current usage counts.
        """
        today = date.today()
        now = datetime.utcnow()
        week_start = self.get_week_start(today)
        
        try:
            # 1. Log the raw event
            event = UsageEvent(
                user_id=user_id,
                usage_type=usage_type.value if isinstance(usage_type, UsageType) else usage_type,
                event_time=now,
                store_id=store_id,
                product_id=product_id,
                event_data=event_data or {},
                cost_usd=cost_usd
            )
            self.session.add(event)
            
            # 2. Update daily aggregate
            daily = self._get_or_create_daily(user_id, usage_type, today)
            daily.count += count
            
            # 3. Update weekly aggregate
            weekly = self._get_or_create_weekly(user_id, usage_type, week_start)
            weekly.count += count
            
            # 4. Update monthly aggregate
            monthly = self._get_or_create_monthly(user_id, usage_type, today.year, today.month)
            monthly.count += count
            
            self.session.commit()
            
            return {
                "success": True,
                "daily_count": daily.count,
                "weekly_count": weekly.count,
                "monthly_count": monthly.count
            }
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to record usage: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_or_create_daily(self, user_id: int, usage_type: UsageType, usage_date: date) -> DailyUsage:
        """Get or create daily usage record"""
        usage_type_str = usage_type.value if isinstance(usage_type, UsageType) else usage_type
        
        record = self.session.query(DailyUsage).filter(
            DailyUsage.user_id == user_id,
            DailyUsage.usage_type == usage_type_str,
            DailyUsage.usage_date == usage_date
        ).first()
        
        if not record:
            record = DailyUsage(
                user_id=user_id,
                usage_type=usage_type_str,
                usage_date=usage_date,
                count=0
            )
            self.session.add(record)
            self.session.flush()
        
        return record
    
    def _get_or_create_weekly(self, user_id: int, usage_type: UsageType, week_start: date) -> WeeklyUsage:
        """Get or create weekly usage record"""
        usage_type_str = usage_type.value if isinstance(usage_type, UsageType) else usage_type
        
        record = self.session.query(WeeklyUsage).filter(
            WeeklyUsage.user_id == user_id,
            WeeklyUsage.usage_type == usage_type_str,
            WeeklyUsage.week_start == week_start
        ).first()
        
        if not record:
            record = WeeklyUsage(
                user_id=user_id,
                usage_type=usage_type_str,
                week_start=week_start,
                count=0
            )
            self.session.add(record)
            self.session.flush()
        
        return record
    
    def _get_or_create_monthly(self, user_id: int, usage_type: UsageType, year: int, month: int) -> MonthlyUsage:
        """Get or create monthly usage record"""
        usage_type_str = usage_type.value if isinstance(usage_type, UsageType) else usage_type
        
        record = self.session.query(MonthlyUsage).filter(
            MonthlyUsage.user_id == user_id,
            MonthlyUsage.usage_type == usage_type_str,
            MonthlyUsage.year == year,
            MonthlyUsage.month == month
        ).first()
        
        if not record:
            record = MonthlyUsage(
                user_id=user_id,
                usage_type=usage_type_str,
                year=year,
                month=month,
                count=0
            )
            self.session.add(record)
            self.session.flush()
        
        return record
    
    def get_usage(
        self,
        user_id: int,
        usage_type: UsageType,
        period: str = "daily"  # "daily", "weekly", "monthly"
    ) -> int:
        """Get current usage count for a specific period"""
        usage_type_str = usage_type.value if isinstance(usage_type, UsageType) else usage_type
        today = date.today()
        
        if period == "daily":
            record = self.session.query(DailyUsage).filter(
                DailyUsage.user_id == user_id,
                DailyUsage.usage_type == usage_type_str,
                DailyUsage.usage_date == today
            ).first()
            
        elif period == "weekly":
            week_start = self.get_week_start(today)
            record = self.session.query(WeeklyUsage).filter(
                WeeklyUsage.user_id == user_id,
                WeeklyUsage.usage_type == usage_type_str,
                WeeklyUsage.week_start == week_start
            ).first()
            
        elif period == "monthly":
            record = self.session.query(MonthlyUsage).filter(
                MonthlyUsage.user_id == user_id,
                MonthlyUsage.usage_type == usage_type_str,
                MonthlyUsage.year == today.year,
                MonthlyUsage.month == today.month
            ).first()
        else:
            return 0
        
        return record.count if record else 0
    
    def check_limit(
        self,
        user_id: int,
        usage_type: UsageType,
        limit: int,
        period: str = "daily"
    ) -> Dict[str, Any]:
        """
        Check if user is within their usage limit.
        
        Returns:
            {
                "allowed": bool,
                "current": int,
                "limit": int,
                "remaining": int
            }
        """
        if limit == -1:  # -1 means unlimited
            return {
                "allowed": True,
                "current": self.get_usage(user_id, usage_type, period),
                "limit": -1,
                "remaining": -1,
                "unlimited": True
            }
        
        current = self.get_usage(user_id, usage_type, period)
        remaining = max(0, limit - current)
        
        return {
            "allowed": current < limit,
            "current": current,
            "limit": limit,
            "remaining": remaining,
            "unlimited": False
        }
    
    def get_all_usage(self, user_id: int) -> Dict[str, Dict[str, int]]:
        """Get all usage stats for a user"""
        today = date.today()
        week_start = self.get_week_start(today)
        
        result = {}
        
        for usage_type in UsageType:
            result[usage_type.value] = {
                "daily": self.get_usage(user_id, usage_type, "daily"),
                "weekly": self.get_usage(user_id, usage_type, "weekly"),
                "monthly": self.get_usage(user_id, usage_type, "monthly")
            }
        
        return result
    
    def get_usage_history(
        self,
        user_id: int,
        usage_type: UsageType,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get daily usage history for the past N days"""
        usage_type_str = usage_type.value if isinstance(usage_type, UsageType) else usage_type
        cutoff = date.today() - timedelta(days=days)
        
        records = self.session.query(DailyUsage).filter(
            DailyUsage.user_id == user_id,
            DailyUsage.usage_type == usage_type_str,
            DailyUsage.usage_date >= cutoff
        ).order_by(DailyUsage.usage_date.desc()).all()
        
        return [
            {
                "date": r.usage_date.isoformat(),
                "count": r.count
            }
            for r in records
        ]


# ============================================================================
# TIER-AWARE USAGE ENFORCER
# ============================================================================

class TierUsageEnforcer:
    """
    Combines usage tracking with tier limits.
    
    Usage:
        enforcer = TierUsageEnforcer(db_session)
        
        # Check if user can perform action
        result = enforcer.can_perform(user_id=1, action="aliexpress_search")
        if result["allowed"]:
            # Do the action
            enforcer.record_action(user_id=1, action="aliexpress_search")
    """
    
    # Map actions to usage types and their period
    ACTION_CONFIG = {
        "product_discovery": {
            "usage_type": UsageType.PRODUCT_DISCOVERY,
            "period": "weekly",
            "tier_limit_key": "products_per_week"
        },
        "aliexpress_search": {
            "usage_type": UsageType.ALIEXPRESS_SEARCH,
            "period": "daily",
            "tier_limit_key": "aliexpress_searches_per_day"
        },
        "aliexpress_enrichment": {
            "usage_type": UsageType.ALIEXPRESS_ENRICHMENT,
            "period": "daily",
            "tier_limit_key": "aliexpress_enrichment"  # Boolean check
        },
        "product_deploy": {
            "usage_type": UsageType.PRODUCT_DEPLOY,
            "period": "weekly",
            "tier_limit_key": "one_click_deploy"  # Boolean check
        },
        "email_automation": {
            "usage_type": UsageType.EMAIL_AUTOMATION,
            "period": "daily",
            "tier_limit_key": "email_templates"  # Count limit
        },
        "ai_query": {
            "usage_type": UsageType.AI_QUERY,
            "period": "daily",
            "tier_limit_key": None  # No limit, just tracking
        },
        "ai_briefing": {
            "usage_type": UsageType.AI_BRIEFING,
            "period": "weekly",
            "tier_limit_key": "ai_briefings"  # e.g., "weekly", "daily", None
        },
        "inventory_check": {
            "usage_type": UsageType.INVENTORY_CHECK,
            "period": "daily",
            "tier_limit_key": "prophecizer_enabled"  # Boolean check
        }
    }
    
    def __init__(self, session: Session):
        self.session = session
        self.tracker = UsageTracker(session)
    
    def get_user_tier(self, user_id: int) -> str:
        """Get user's subscription tier"""
        from ospra_os.database.multi_store_models import User
        
        user = self.session.query(User).filter(User.id == user_id).first()
        if not user:
            return "nest"  # Default to free tier
        
        # Handle enum or string
        tier = user.subscription_tier
        if hasattr(tier, 'value'):
            return tier.value
        return str(tier)
    
    def get_tier_limit(self, tier: str, limit_key: str) -> Any:
        """Get limit value from tier definition"""
        from ospra_os.core.tiers import get_tier_definition
        
        tier_def = get_tier_definition(tier)
        if not tier_def:
            return None
        
        # Navigate nested keys (e.g., "limits.stores")
        limits = tier_def.get("limits", {})
        features = tier_def.get("features", {})
        aliexpress = tier_def.get("aliexpress", {})
        
        # Check in order: limits, aliexpress, features
        if limit_key in limits:
            return limits[limit_key]
        if limit_key in aliexpress:
            return aliexpress[limit_key]
        if limit_key in features:
            return features[limit_key]
        
        return None
    
    def can_perform(
        self,
        user_id: int,
        action: str,
        count: int = 1
    ) -> Dict[str, Any]:
        """
        Check if user can perform an action based on their tier limits.
        
        Returns:
            {
                "allowed": bool,
                "reason": str or None,
                "current": int,
                "limit": int or str,
                "remaining": int or None,
                "upgrade_suggestion": str or None
            }
        """
        config = self.ACTION_CONFIG.get(action)
        if not config:
            return {"allowed": True, "reason": "Unknown action, allowing"}
        
        tier = self.get_user_tier(user_id)
        limit_key = config["tier_limit_key"]
        
        # No limit configured = allow
        if not limit_key:
            return {"allowed": True, "reason": "No limit configured"}
        
        limit_value = self.get_tier_limit(tier, limit_key)
        
        # Boolean features (e.g., prophecizer_enabled)
        if isinstance(limit_value, bool):
            if not limit_value:
                return {
                    "allowed": False,
                    "reason": f"Feature '{action}' not available on {tier} tier",
                    "upgrade_suggestion": self._get_upgrade_suggestion(tier, action)
                }
            return {"allowed": True, "reason": "Feature enabled"}
        
        # String values (e.g., "weekly", "daily" for briefings)
        if isinstance(limit_value, str):
            # For briefings, check if they've already had one this period
            current = self.tracker.get_usage(user_id, config["usage_type"], config["period"])
            allowed_count = 1 if limit_value else 0
            return {
                "allowed": current < allowed_count,
                "current": current,
                "limit": allowed_count,
                "remaining": max(0, allowed_count - current)
            }
        
        # Numeric limits
        if isinstance(limit_value, (int, float)):
            if limit_value == -1:  # Unlimited
                return {
                    "allowed": True,
                    "current": self.tracker.get_usage(user_id, config["usage_type"], config["period"]),
                    "limit": -1,
                    "remaining": -1,
                    "unlimited": True
                }
            
            check = self.tracker.check_limit(
                user_id=user_id,
                usage_type=config["usage_type"],
                limit=int(limit_value),
                period=config["period"]
            )
            
            if not check["allowed"]:
                check["reason"] = f"Limit reached: {check['current']}/{check['limit']} {config['period']}"
                check["upgrade_suggestion"] = self._get_upgrade_suggestion(tier, action)
            
            return check
        
        # Default allow if we can't determine
        return {"allowed": True, "reason": "Could not determine limit"}
    
    def record_action(
        self,
        user_id: int,
        action: str,
        count: int = 1,
        **kwargs
    ) -> Dict[str, Any]:
        """Record that user performed an action"""
        config = self.ACTION_CONFIG.get(action)
        if not config:
            return {"success": False, "error": "Unknown action"}
        
        return self.tracker.record(
            user_id=user_id,
            usage_type=config["usage_type"],
            count=count,
            **kwargs
        )
    
    def _get_upgrade_suggestion(self, current_tier: str, action: str) -> str:
        """Suggest which tier to upgrade to for this action"""
        tier_order = ["nest", "flight", "soar", "stratosphere"]
        current_idx = tier_order.index(current_tier) if current_tier in tier_order else 0
        
        # Check each higher tier
        for tier in tier_order[current_idx + 1:]:
            config = self.ACTION_CONFIG.get(action)
            if config:
                limit = self.get_tier_limit(tier, config["tier_limit_key"])
                if limit and (limit == True or limit == -1 or (isinstance(limit, int) and limit > 0)):
                    return f"Upgrade to {tier.title()} to unlock this feature"
        
        return "Contact support for enterprise options"
    
    def get_usage_dashboard(self, user_id: int) -> Dict[str, Any]:
        """Get complete usage dashboard for user"""
        tier = self.get_user_tier(user_id)
        
        dashboard = {
            "tier": tier,
            "usage": {},
            "limits": {}
        }
        
        for action, config in self.ACTION_CONFIG.items():
            usage = self.tracker.get_usage(user_id, config["usage_type"], config["period"])
            limit = self.get_tier_limit(tier, config["tier_limit_key"]) if config["tier_limit_key"] else None
            
            dashboard["usage"][action] = {
                "current": usage,
                "period": config["period"],
                "limit": limit if limit is not None else "unlimited",
                "percentage": (usage / limit * 100) if isinstance(limit, int) and limit > 0 else 0
            }
        
        return dashboard


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_usage_tracking():
    """Create usage tracking tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("[SUCCESS] Usage tracking tables created")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_tracker(session: Session = None) -> UsageTracker:
    """Get a UsageTracker instance"""
    if session is None:
        session = SessionLocal()
    return UsageTracker(session)


def get_enforcer(session: Session = None) -> TierUsageEnforcer:
    """Get a TierUsageEnforcer instance"""
    if session is None:
        session = SessionLocal()
    return TierUsageEnforcer(session)


# Initialize tables on import
if __name__ == "__main__":
    init_usage_tracking()
    print("[SUCCESS] Usage tracking system initialized")
