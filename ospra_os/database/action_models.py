"""
Action Queue Models for Ospra AI Decision System

Stores AI-generated actions (deploy product, adjust price, pause ad, etc.)
that require user approval before execution.
"""
import enum
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime,
    ForeignKey, JSON, Boolean, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship
from .base import Base


class AIActionType(str, enum.Enum):
    """Types of AI-generated actions"""
    DEPLOY_PRODUCT = "deploy_product"
    ADJUST_PRICE = "adjust_price"
    PAUSE_AD = "pause_ad"
    RESUME_AD = "resume_ad"
    DROP_PRODUCT = "drop_product"
    SEND_REFUND = "send_refund"
    REPLY_EMAIL = "reply_email"
    RESTOCK_ALERT = "restock_alert"


class AIActionStatus(str, enum.Enum):
    """Status of an action"""
    PENDING = "pending"           # Waiting for user approval
    APPROVED = "approved"         # User approved, queued for execution
    EXECUTING = "executing"       # Currently being executed
    EXECUTED = "executed"         # Successfully completed
    SKIPPED = "skipped"           # User dismissed/skipped
    FAILED = "failed"             # Execution failed
    EXPIRED = "expired"           # Action expired before approval
    UNDONE = "undone"             # Action was undone/rolled back


class Action(Base):
    """
    Represents an AI-generated action waiting for user approval.

    Each action is a specific recommendation (e.g., 'Deploy Premium Yoga Mat at $129.99')
    that the AI wants to perform. User can approve, edit, or skip.
    """
    __tablename__ = "actions"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Ownership
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True, index=True)

    # Action Type & Display
    action_type = Column(SQLEnum(AIActionType), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # AI Reasoning
    confidence = Column(Float, nullable=False)  # 0-100 score
    rationale = Column(Text, nullable=False)    # Why AI recommends this
    factors = Column(JSON, nullable=True)       # [{"label": "Velocity Score", "value": 18, "icon": "trend"}]

    # Action Payload
    payload = Column(JSON, nullable=False)      # Action-specific data (product_name, price, etc.)

    # Execution Details
    status = Column(SQLEnum(AIActionStatus), default=AIActionStatus.PENDING, nullable=False, index=True)
    executed_at = Column(DateTime, nullable=True)
    execution_result = Column(JSON, nullable=True)  # Result of execution (success, error, data)
    error_message = Column(Text, nullable=True)

    # Metadata
    estimated_impact = Column(String(255), nullable=True)  # "+$520 projected monthly profit"
    product_image = Column(String(500), nullable=True)

    # Expiration
    expires_at = Column(DateTime, nullable=True)  # Actions expire if not approved in time

    # Undo Support
    is_undoable = Column(Boolean, default=True)
    undo_deadline = Column(DateTime, nullable=True)  # Can only undo within X hours
    undone_at = Column(DateTime, nullable=True)
    undone_by = Column(String(50), nullable=True)  # "user", "system", "auto_pilot"
    previous_state = Column(JSON, nullable=True)  # State before execution for rollback
    undoes_action_id = Column(Integer, ForeignKey("actions.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="actions")
    store = relationship("Store", back_populates="actions")
    logs = relationship("ActionLog", back_populates="action", cascade="all, delete-orphan")

    # Composite indexes for frequently queried combinations
    __table_args__ = (
        Index('ix_actions_store_status', 'store_id', 'status'),
        Index('ix_actions_user_status', 'user_id', 'status'),
    )

    def __repr__(self):
        return f"<Action(id={self.id}, type={self.action_type}, status={self.status}, confidence={self.confidence})>"

    def is_expired(self) -> bool:
        """Check if action has expired"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def is_actionable(self) -> bool:
        """Check if action can be approved/skipped"""
        return self.status == AIActionStatus.PENDING and not self.is_expired()

    def set_default_expiration(self, hours: int = 72):
        """Set expiration time (default 72 hours from now)"""
        self.expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)


class ActionLog(Base):
    """
    Audit trail for action status changes.

    Tracks every state transition (pending → approved → executed)
    and who performed the action.
    """
    __tablename__ = "action_logs"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Keys
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null for system actions

    # Log Data
    old_status = Column(SQLEnum(AIActionStatus), nullable=True)
    new_status = Column(SQLEnum(AIActionStatus), nullable=False)
    reason = Column(Text, nullable=True)  # Why was it skipped/approved/failed?
    log_metadata = Column(JSON, nullable=True)  # Additional context

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    action = relationship("Action", back_populates="logs")
    user = relationship("User")

    def __repr__(self):
        return f"<ActionLog(action_id={self.action_id}, {self.old_status}→{self.new_status})>"


class AutoPilotLog(Base):
    """
    Logs for Auto-Pilot automatic action execution.

    Tracks when Auto-Pilot executes actions automatically,
    including the confidence threshold that triggered execution.
    """
    __tablename__ = "auto_pilot_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=True, index=True)

    # What happened
    action_type = Column(String(50), nullable=False)
    was_executed = Column(Boolean, default=False)
    confidence = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)

    # Outcome
    success = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadata
    execution_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User")
    action = relationship("Action")

    def __repr__(self):
        return f"<AutoPilotLog(id={self.id}, action_type={self.action_type}, executed={self.was_executed})>"
