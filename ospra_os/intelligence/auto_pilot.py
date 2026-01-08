"""
OI AUTO-PILOT MODE
==================

Enables Oi to automatically execute high-confidence actions without
requiring manual approval.

Features:
- Per-action-type confidence thresholds
- Daily spending/action limits (safety)
- Undo capability for 24 hours
- Detailed audit logging
- Pause/resume controls

Example:
  User enables auto-pilot with:
    - Deploy products if score > 85 (max 5/day)
    - Pause ads if CTR < 1% (max 10/day)
    - Never auto-adjust budgets > $50

  Oi then runs autonomously, making decisions while user sleeps.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid

logger = logging.getLogger(__name__)


class AutoPilotStatus(str, Enum):
    """Auto-pilot operational status."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    PAUSED = "paused"  # Temporarily paused (user can resume)
    SAFETY_STOP = "safety_stop"  # Auto-stopped due to hitting limits


@dataclass
class ActionTypeConfig:
    """Configuration for a specific action type."""
    enabled: bool = False
    min_confidence: float = 0.85  # Must be at least this confident
    max_per_day: int = 5  # Maximum auto-executions per day
    max_value: Optional[float] = None  # Max $ value (for budgets/prices)
    require_review_above: Optional[float] = None  # Always ask if value > this
    cooldown_minutes: int = 30  # Minimum time between auto-actions of this type
    
    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "min_confidence": self.min_confidence,
            "max_per_day": self.max_per_day,
            "max_value": self.max_value,
            "require_review_above": self.require_review_above,
            "cooldown_minutes": self.cooldown_minutes
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ActionTypeConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AutoPilotConfig:
    """User's auto-pilot configuration."""
    user_id: int
    status: AutoPilotStatus = AutoPilotStatus.DISABLED
    
    # Global limits
    max_daily_spend: float = 100.0  # Total $ that can be auto-spent
    max_daily_actions: int = 20  # Total actions per day
    
    # Per-action-type configs
    action_configs: Dict[str, ActionTypeConfig] = field(default_factory=dict)
    
    # Undo settings
    undo_window_hours: int = 24  # How long actions can be undone
    
    # Notifications
    notify_on_action: bool = True  # Send notification when action taken
    notify_on_limit: bool = True  # Notify when limits approached
    daily_summary: bool = True  # Send daily summary
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_action_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "status": self.status.value,
            "max_daily_spend": self.max_daily_spend,
            "max_daily_actions": self.max_daily_actions,
            "action_configs": {k: v.to_dict() for k, v in self.action_configs.items()},
            "undo_window_hours": self.undo_window_hours,
            "notify_on_action": self.notify_on_action,
            "notify_on_limit": self.notify_on_limit,
            "daily_summary": self.daily_summary,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_action_at": self.last_action_at.isoformat() if self.last_action_at else None
        }


@dataclass
class AutoPilotAction:
    """Record of an auto-executed action."""
    action_id: str
    user_id: int
    action_type: str
    title: str
    description: str
    parameters: Dict[str, Any]
    confidence: float
    
    # Execution details
    executed_at: datetime = field(default_factory=datetime.utcnow)
    execution_result: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    
    # Undo tracking
    can_undo: bool = True
    undo_deadline: Optional[datetime] = None
    undone: bool = False
    undone_at: Optional[datetime] = None
    undo_reason: Optional[str] = None
    
    # Value tracking (for spend limits)
    monetary_value: float = 0.0  # $ impact of this action
    
    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "user_id": self.user_id,
            "action_type": self.action_type,
            "title": self.title,
            "description": self.description,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "executed_at": self.executed_at.isoformat(),
            "execution_result": self.execution_result,
            "success": self.success,
            "error_message": self.error_message,
            "can_undo": self.can_undo and not self.undone and self._within_undo_window(),
            "undo_deadline": self.undo_deadline.isoformat() if self.undo_deadline else None,
            "undone": self.undone,
            "undone_at": self.undone_at.isoformat() if self.undone_at else None,
            "monetary_value": self.monetary_value
        }
    
    def _within_undo_window(self) -> bool:
        if not self.undo_deadline:
            return False
        return datetime.utcnow() < self.undo_deadline


class AutoPilotEngine:
    """
    The Auto-Pilot Engine that makes Oi autonomous.
    
    Responsibilities:
    1. Evaluate pending actions against user's auto-pilot config
    2. Auto-execute actions that meet thresholds
    3. Track daily limits and spending
    4. Provide undo capability
    5. Generate audit logs and notifications
    """
    
    # Default configs for each action type
    DEFAULT_CONFIGS = {
        "deploy_product": ActionTypeConfig(
            enabled=False,
            min_confidence=0.85,
            max_per_day=5,
            cooldown_minutes=60
        ),
        "pause_ad": ActionTypeConfig(
            enabled=False,
            min_confidence=0.80,
            max_per_day=10,
            cooldown_minutes=30
        ),
        "resume_ad": ActionTypeConfig(
            enabled=False,
            min_confidence=0.80,
            max_per_day=10,
            cooldown_minutes=30
        ),
        "increase_ad_budget": ActionTypeConfig(
            enabled=False,
            min_confidence=0.90,
            max_per_day=3,
            max_value=50.0,  # Max $50 increase
            require_review_above=25.0,
            cooldown_minutes=120
        ),
        "decrease_ad_budget": ActionTypeConfig(
            enabled=False,
            min_confidence=0.85,
            max_per_day=5,
            cooldown_minutes=60
        ),
        "adjust_price": ActionTypeConfig(
            enabled=False,
            min_confidence=0.90,
            max_per_day=5,
            cooldown_minutes=60
        ),
        "drop_product": ActionTypeConfig(
            enabled=False,
            min_confidence=0.95,  # Very high - dropping is serious
            max_per_day=2,
            cooldown_minutes=240
        ),
        "reorder_inventory": ActionTypeConfig(
            enabled=False,
            min_confidence=0.90,
            max_per_day=3,
            max_value=500.0,  # Max $500 reorder
            require_review_above=200.0,
            cooldown_minutes=120
        ),
    }
    
    def __init__(self):
        # In-memory storage (replace with database in production)
        self._configs: Dict[int, AutoPilotConfig] = {}
        self._actions: Dict[str, AutoPilotAction] = {}
        self._daily_stats: Dict[int, Dict[str, Any]] = {}  # {user_id: {date: stats}}
    
    def get_config(self, user_id: int) -> AutoPilotConfig:
        """Get or create auto-pilot config for user."""
        if user_id not in self._configs:
            # Create default config
            config = AutoPilotConfig(
                user_id=user_id,
                action_configs={k: ActionTypeConfig(**v.__dict__) for k, v in self.DEFAULT_CONFIGS.items()}
            )
            self._configs[user_id] = config
        
        return self._configs[user_id]
    
    def update_config(self, user_id: int, updates: Dict[str, Any]) -> AutoPilotConfig:
        """Update user's auto-pilot configuration."""
        config = self.get_config(user_id)
        
        # Update top-level fields
        if "status" in updates:
            config.status = AutoPilotStatus(updates["status"])
        if "max_daily_spend" in updates:
            config.max_daily_spend = float(updates["max_daily_spend"])
        if "max_daily_actions" in updates:
            config.max_daily_actions = int(updates["max_daily_actions"])
        if "undo_window_hours" in updates:
            config.undo_window_hours = int(updates["undo_window_hours"])
        if "notify_on_action" in updates:
            config.notify_on_action = bool(updates["notify_on_action"])
        if "notify_on_limit" in updates:
            config.notify_on_limit = bool(updates["notify_on_limit"])
        if "daily_summary" in updates:
            config.daily_summary = bool(updates["daily_summary"])
        
        # Update action-specific configs
        if "action_configs" in updates:
            for action_type, action_updates in updates["action_configs"].items():
                if action_type not in config.action_configs:
                    config.action_configs[action_type] = ActionTypeConfig()
                
                action_config = config.action_configs[action_type]
                for key, value in action_updates.items():
                    if hasattr(action_config, key):
                        setattr(action_config, key, value)
        
        config.updated_at = datetime.utcnow()
        logger.info(f"[AI] Auto-pilot config updated for user {user_id}")
        
        return config
    
    def enable(self, user_id: int) -> AutoPilotConfig:
        """Enable auto-pilot for user."""
        config = self.get_config(user_id)
        config.status = AutoPilotStatus.ENABLED
        config.updated_at = datetime.utcnow()
        logger.info(f"[START] Auto-pilot ENABLED for user {user_id}")
        return config
    
    def disable(self, user_id: int) -> AutoPilotConfig:
        """Disable auto-pilot for user."""
        config = self.get_config(user_id)
        config.status = AutoPilotStatus.DISABLED
        config.updated_at = datetime.utcnow()
        logger.info(f"[STOP] Auto-pilot DISABLED for user {user_id}")
        return config
    
    def pause(self, user_id: int) -> AutoPilotConfig:
        """Temporarily pause auto-pilot."""
        config = self.get_config(user_id)
        config.status = AutoPilotStatus.PAUSED
        config.updated_at = datetime.utcnow()
        logger.info(f"[PAUSE] Auto-pilot PAUSED for user {user_id}")
        return config
    
    def can_auto_execute(
        self,
        user_id: int,
        action_type: str,
        confidence: float,
        monetary_value: float = 0.0
    ) -> tuple[bool, str]:
        """
        Check if an action can be auto-executed.
        
        Returns:
            (can_execute, reason)
        """
        config = self.get_config(user_id)
        
        # Check global status
        if config.status != AutoPilotStatus.ENABLED:
            return False, f"Auto-pilot is {config.status.value}"
        
        # Check action type is configured
        if action_type not in config.action_configs:
            return False, f"Action type '{action_type}' not configured"
        
        action_config = config.action_configs[action_type]
        
        # Check if action type is enabled
        if not action_config.enabled:
            return False, f"Auto-pilot disabled for {action_type}"
        
        # Check confidence threshold
        if confidence < action_config.min_confidence:
            return False, f"Confidence {confidence:.0%} below threshold {action_config.min_confidence:.0%}"
        
        # Check daily limits
        stats = self._get_daily_stats(user_id)
        
        if stats["total_actions"] >= config.max_daily_actions:
            return False, f"Daily action limit reached ({config.max_daily_actions})"
        
        if stats["total_spend"] + monetary_value > config.max_daily_spend:
            return False, f"Would exceed daily spend limit (${config.max_daily_spend})"
        
        # Check per-type daily limit
        type_count = stats["by_type"].get(action_type, 0)
        if type_count >= action_config.max_per_day:
            return False, f"Daily limit for {action_type} reached ({action_config.max_per_day})"
        
        # Check monetary value limits
        if action_config.max_value and monetary_value > action_config.max_value:
            return False, f"Value ${monetary_value} exceeds max ${action_config.max_value}"
        
        if action_config.require_review_above and monetary_value > action_config.require_review_above:
            return False, f"Value ${monetary_value} requires manual review"
        
        # Check cooldown
        last_of_type = stats["last_by_type"].get(action_type)
        if last_of_type:
            elapsed = (datetime.utcnow() - last_of_type).total_seconds() / 60
            if elapsed < action_config.cooldown_minutes:
                remaining = action_config.cooldown_minutes - elapsed
                return False, f"Cooldown: {remaining:.0f} minutes remaining"
        
        return True, "All checks passed"
    
    def execute_action(
        self,
        user_id: int,
        action_type: str,
        title: str,
        description: str,
        parameters: Dict[str, Any],
        confidence: float,
        monetary_value: float = 0.0,
        execute_func=None
    ) -> AutoPilotAction:
        """
        Auto-execute an action.
        
        Args:
            user_id: User ID
            action_type: Type of action
            title: Action title
            description: Action description
            parameters: Action parameters
            confidence: Confidence score
            monetary_value: $ impact
            execute_func: Optional function to actually execute the action
        
        Returns:
            AutoPilotAction record
        """
        config = self.get_config(user_id)
        
        # Create action record
        action = AutoPilotAction(
            action_id=str(uuid.uuid4()),
            user_id=user_id,
            action_type=action_type,
            title=title,
            description=description,
            parameters=parameters,
            confidence=confidence,
            monetary_value=monetary_value,
            undo_deadline=datetime.utcnow() + timedelta(hours=config.undo_window_hours)
        )
        
        # Execute the action
        try:
            if execute_func:
                result = execute_func(parameters)
                action.execution_result = str(result)
            else:
                action.execution_result = "Simulated execution (no execute_func provided)"
            
            action.success = True
            logger.info(f"[AI] AUTO-EXECUTED: {action_type} - {title}")
            
        except Exception as e:
            action.success = False
            action.error_message = str(e)
            action.can_undo = False
            logger.error(f"[ERROR] Auto-execution failed: {e}")
        
        # Store action
        self._actions[action.action_id] = action
        
        # Update stats
        self._update_daily_stats(user_id, action_type, monetary_value)
        
        # Update config timestamp
        config.last_action_at = datetime.utcnow()
        
        return action
    
    def undo_action(self, action_id: str, reason: str = None) -> tuple[bool, str]:
        """
        Undo an auto-executed action.
        
        Returns:
            (success, message)
        """
        if action_id not in self._actions:
            return False, "Action not found"
        
        action = self._actions[action_id]
        
        if action.undone:
            return False, "Action already undone"
        
        if not action.can_undo:
            return False, "Action cannot be undone"
        
        if action.undo_deadline and datetime.utcnow() > action.undo_deadline:
            return False, "Undo window has expired"
        
        # Mark as undone
        action.undone = True
        action.undone_at = datetime.utcnow()
        action.undo_reason = reason
        
        # TODO: Actually reverse the action (call appropriate undo function)
        
        logger.info(f"↩ Action {action_id} UNDONE: {reason or 'No reason provided'}")
        
        return True, f"Action '{action.title}' has been undone"
    
    def get_recent_actions(
        self,
        user_id: int,
        limit: int = 20,
        include_undone: bool = False
    ) -> List[AutoPilotAction]:
        """Get recent auto-executed actions for user."""
        actions = [
            a for a in self._actions.values()
            if a.user_id == user_id and (include_undone or not a.undone)
        ]
        
        # Sort by execution time, newest first
        actions.sort(key=lambda a: a.executed_at, reverse=True)
        
        return actions[:limit]
    
    def get_daily_summary(self, user_id: int) -> Dict[str, Any]:
        """Get daily auto-pilot summary."""
        config = self.get_config(user_id)
        stats = self._get_daily_stats(user_id)
        
        # Get today's actions
        today = datetime.utcnow().date()
        todays_actions = [
            a for a in self._actions.values()
            if a.user_id == user_id and a.executed_at.date() == today
        ]
        
        successful = [a for a in todays_actions if a.success]
        failed = [a for a in todays_actions if not a.success]
        undone = [a for a in todays_actions if a.undone]
        
        return {
            "date": today.isoformat(),
            "status": config.status.value,
            "actions_executed": len(todays_actions),
            "successful": len(successful),
            "failed": len(failed),
            "undone": len(undone),
            "total_spend": stats["total_spend"],
            "by_type": stats["by_type"],
            "limits": {
                "daily_actions": f"{stats['total_actions']}/{config.max_daily_actions}",
                "daily_spend": f"${stats['total_spend']:.2f}/${config.max_daily_spend:.2f}"
            },
            "remaining": {
                "actions": config.max_daily_actions - stats["total_actions"],
                "spend": config.max_daily_spend - stats["total_spend"]
            }
        }
    
    def _get_daily_stats(self, user_id: int) -> Dict[str, Any]:
        """Get or initialize daily stats for user."""
        today = datetime.utcnow().date().isoformat()
        
        if user_id not in self._daily_stats:
            self._daily_stats[user_id] = {}
        
        if today not in self._daily_stats[user_id]:
            self._daily_stats[user_id][today] = {
                "total_actions": 0,
                "total_spend": 0.0,
                "by_type": {},
                "last_by_type": {}
            }
        
        return self._daily_stats[user_id][today]
    
    def _update_daily_stats(
        self,
        user_id: int,
        action_type: str,
        monetary_value: float
    ):
        """Update daily stats after an action."""
        stats = self._get_daily_stats(user_id)
        
        stats["total_actions"] += 1
        stats["total_spend"] += monetary_value
        stats["by_type"][action_type] = stats["by_type"].get(action_type, 0) + 1
        stats["last_by_type"][action_type] = datetime.utcnow()


# Singleton instance
_auto_pilot: Optional[AutoPilotEngine] = None


def get_auto_pilot() -> AutoPilotEngine:
    """Get or create the auto-pilot engine singleton."""
    global _auto_pilot
    if _auto_pilot is None:
        _auto_pilot = AutoPilotEngine()
    return _auto_pilot


# === Convenience functions ===

def check_and_auto_execute(
    user_id: int,
    action_type: str,
    title: str,
    description: str,
    parameters: Dict[str, Any],
    confidence: float,
    monetary_value: float = 0.0,
    execute_func=None
) -> tuple[bool, Optional[AutoPilotAction], str]:
    """
    Check if action can be auto-executed and execute if so.
    
    Returns:
        (was_auto_executed, action_record, message)
    """
    engine = get_auto_pilot()
    
    can_execute, reason = engine.can_auto_execute(
        user_id=user_id,
        action_type=action_type,
        confidence=confidence,
        monetary_value=monetary_value
    )
    
    if not can_execute:
        return False, None, reason
    
    action = engine.execute_action(
        user_id=user_id,
        action_type=action_type,
        title=title,
        description=description,
        parameters=parameters,
        confidence=confidence,
        monetary_value=monetary_value,
        execute_func=execute_func
    )
    
    if action.success:
        return True, action, f"Auto-executed: {title}"
    else:
        return False, action, f"Execution failed: {action.error_message}"
