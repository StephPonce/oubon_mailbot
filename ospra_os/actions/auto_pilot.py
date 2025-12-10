"""
Auto-Pilot Engine for Autonomous Action Execution

Automatically executes high-confidence AI actions based on user settings.
Implements GROK RECOMMENDATION #7: Auto-Pilot Mode Toggle.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from ospra_os.database.multi_store_models import (
    Action, UserSettings, AutoPilotLog, User
)
from ospra_os.database.action_models import AIActionStatus, AIActionType


class AutoPilotEngine:
    """Engine for automatic action execution based on user settings"""

    # Default confidence thresholds per action type
    DEFAULT_THRESHOLDS = {
        "deploy_product": 88,
        "adjust_price": 82,
        "pause_ad": 90,
        "resume_ad": 85,
        "drop_product": 95,  # High threshold - risky action
        "reply_email": 88,
        "send_refund": 100,  # Never auto (requires 100% which is impossible)
        "restock_alert": 75,  # Just alerts, low risk
    }

    # Actions that should NEVER auto-execute regardless of settings
    NEVER_AUTO_EXECUTE = ["send_refund"]

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.settings = self._get_settings()

    def _get_settings(self) -> UserSettings:
        """Get or create user settings"""
        settings = self.db.query(UserSettings).filter(
            UserSettings.user_id == self.user_id
        ).first()

        if not settings:
            # Create default settings
            settings = UserSettings(
                user_id=self.user_id,
                auto_pilot_enabled=False,
                auto_pilot_threshold=85.0,
                auto_pilot_rules={},
                daily_auto_execute_limit=20,
                max_auto_spend=500.0
            )
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)

        return settings

    def is_enabled(self) -> bool:
        """Check if auto-pilot is enabled for user"""
        return self.settings.auto_pilot_enabled

    def get_threshold_for_action(self, action_type: str) -> float:
        """Get confidence threshold for a specific action type"""

        rules = self.settings.auto_pilot_rules or {}

        if action_type in rules:
            rule = rules[action_type]
            if isinstance(rule, dict):
                if not rule.get("enabled", True):
                    return 101  # Impossible threshold = never auto-execute
                return rule.get("threshold", self.settings.auto_pilot_threshold)

        # Fall back to global threshold
        return self.settings.auto_pilot_threshold

    def can_auto_execute(self, action: Action) -> Tuple[bool, str]:
        """
        Check if an action can be auto-executed.
        Returns (can_execute, reason)
        """

        # Check if auto-pilot is enabled
        if not self.settings.auto_pilot_enabled:
            return False, "auto_pilot_disabled"

        # Check if action type is in never-auto list
        action_type_str = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
        if action_type_str in self.NEVER_AUTO_EXECUTE:
            return False, "action_type_blocked"

        # Check action-specific rules
        rules = self.settings.auto_pilot_rules or {}
        if action_type_str in rules:
            rule = rules[action_type_str]
            if isinstance(rule, dict) and not rule.get("enabled", True):
                return False, "action_type_disabled"

        # Check confidence threshold
        threshold = self.get_threshold_for_action(action_type_str)
        if action.confidence < threshold:
            return False, f"below_threshold_{threshold}"

        # Check daily limit
        if not self._check_daily_limit():
            return False, "daily_limit_reached"

        # Check spend limit (if action has monetary impact)
        if not self._check_spend_limit(action):
            return False, "spend_limit_reached"

        return True, "approved"

    def _check_daily_limit(self) -> bool:
        """Check if daily auto-execution limit has been reached"""

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        today_count = self.db.query(func.count(AutoPilotLog.id)).filter(
            AutoPilotLog.user_id == self.user_id,
            AutoPilotLog.executed == True,
            AutoPilotLog.created_at >= today_start
        ).scalar()

        return today_count < self.settings.daily_auto_execute_limit

    def _check_spend_limit(self, action: Action) -> bool:
        """Check if auto-executing this action would exceed daily spend limit"""

        # Calculate potential spend from this action
        action_spend = self._estimate_action_spend(action)

        if action_spend == 0:
            return True

        # Calculate today's auto-executed spend
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        today_actions = self.db.query(Action).join(AutoPilotLog).filter(
            AutoPilotLog.user_id == self.user_id,
            AutoPilotLog.executed == True,
            AutoPilotLog.created_at >= today_start
        ).all()

        today_spend = sum(self._estimate_action_spend(a) for a in today_actions)

        return (today_spend + action_spend) <= self.settings.max_auto_spend

    def _estimate_action_spend(self, action: Action) -> float:
        """Estimate monetary impact of an action"""

        payload = action.payload or {}
        action_type_str = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)

        if action_type_str == "deploy_product":
            # Cost to deploy (inventory, fees, etc.) - estimate
            return payload.get("source_price", 0) * 1.2  # 20% buffer

        elif action_type_str == "resume_ad":
            # Daily ad spend
            return payload.get("daily_budget", 0)

        elif action_type_str == "send_refund":
            return payload.get("amount", 0)

        return 0

    async def process_action(self, action: Action) -> Dict[str, Any]:
        """
        Process an action through auto-pilot logic.
        Returns dict with auto_executed status and result.
        """

        can_execute, reason = self.can_auto_execute(action)

        action_type_str = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)

        # Log the decision
        log = AutoPilotLog(
            user_id=self.user_id,
            action_id=action.id,
            confidence=action.confidence,
            threshold_used=self.get_threshold_for_action(action_type_str),
            executed=can_execute,
            skipped_reason=None if can_execute else reason
        )
        self.db.add(log)
        self.db.commit()

        if can_execute:
            return {
                "auto_executed": True,
                "action_id": action.id,
                "reason": "confidence_threshold_met",
                "message": f"Auto-executed action with {action.confidence}% confidence"
            }
        else:
            return {
                "auto_executed": False,
                "action_id": action.id,
                "reason": reason,
                "threshold": self.get_threshold_for_action(action_type_str),
                "confidence": action.confidence,
                "message": f"Action queued for manual review: {reason}"
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get auto-pilot statistics"""

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        # Today's stats
        today_executed = self.db.query(func.count(AutoPilotLog.id)).filter(
            AutoPilotLog.user_id == self.user_id,
            AutoPilotLog.executed == True,
            AutoPilotLog.created_at >= today_start
        ).scalar() or 0

        today_skipped = self.db.query(func.count(AutoPilotLog.id)).filter(
            AutoPilotLog.user_id == self.user_id,
            AutoPilotLog.executed == False,
            AutoPilotLog.created_at >= today_start
        ).scalar() or 0

        # Weekly stats
        week_executed = self.db.query(func.count(AutoPilotLog.id)).filter(
            AutoPilotLog.user_id == self.user_id,
            AutoPilotLog.executed == True,
            AutoPilotLog.created_at >= week_start
        ).scalar() or 0

        # Get breakdown by skip reason
        skip_reasons = self.db.query(
            AutoPilotLog.skipped_reason,
            func.count(AutoPilotLog.id)
        ).filter(
            AutoPilotLog.user_id == self.user_id,
            AutoPilotLog.executed == False,
            AutoPilotLog.created_at >= week_start
        ).group_by(AutoPilotLog.skipped_reason).all()

        return {
            "enabled": self.settings.auto_pilot_enabled,
            "threshold": self.settings.auto_pilot_threshold,
            "today": {
                "executed": today_executed,
                "skipped": today_skipped,
                "remaining_limit": max(0, self.settings.daily_auto_execute_limit - today_executed)
            },
            "week": {
                "executed": week_executed
            },
            "skip_breakdown": {reason: count for reason, count in skip_reasons if reason}
        }
