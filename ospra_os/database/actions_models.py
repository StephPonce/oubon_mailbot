"""
Actions Models for OspraOS
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Index, JSON, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import (
    Base,
    SubscriptionTier, Platform, StoreStatus, ProductStatus, DeploymentStatus,
    AIProvider, TaskType, TriggerType, ActionType, LifecycleStage,
    EntryTiming, RiskLevel
)


class AutoPilotLog(Base):
    """Log of auto-pilot decisions and executions"""
    __tablename__ = "auto_pilot_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=False)

    # Decision details
    confidence = Column(Float)
    threshold_used = Column(Float)

    # Execution result
    executed = Column(Boolean, default=False)
    skipped_reason = Column(String(255), nullable=True)  # "below_threshold", "daily_limit", etc.

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User")
    action = relationship("Action")

    __table_args__ = (
        Index('idx_autopilot_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f"<AutoPilotLog(action_id={self.action_id}, executed={self.executed})>"


print("✅ Intelligence models added")
print("✅ A/B Testing models added")
print("✅ Auto-Pilot models added")


# ============================================================================
# EMAIL AUTOMATION MODELS
# ============================================================================
