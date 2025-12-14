"""
Testing Models for OspraOS
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


class ABTest(Base):
    """A/B test for products, prices, content, or ads"""
    __tablename__ = "ab_tests"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Test Identity
    name = Column(String(512), nullable=False)
    test_type = Column(String(50), nullable=False, index=True)  # price, product_title, product_description, product_image, ad_creative, ad_copy

    # Product/Store Association
    product_id = Column(String(255), nullable=False, index=True)
    store_id = Column(String(255), nullable=False, index=True)

    # Test Configuration
    status = Column(String(50), default="draft", nullable=False, index=True)  # draft, scheduled, running, paused, ended
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    # Statistical Settings
    min_sample_size = Column(Integer, default=100, nullable=False)  # Minimum conversions needed
    confidence_level = Column(Float, default=0.95, nullable=False)  # 95% confidence

    # Winner
    winner_variant_id = Column(Integer, ForeignKey("ab_test_variants.id"), nullable=True)

    # Additional Data
    test_metadata = Column(JSON, default=dict)  # Additional test configuration

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    variants = relationship("ABTestVariant", back_populates="test", foreign_keys="ABTestVariant.test_id", cascade="all, delete-orphan")
    events = relationship("ABTestEvent", back_populates="test", cascade="all, delete-orphan")
    assignments = relationship("ABTestAssignment", back_populates="test", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_test_product_store', 'product_id', 'store_id'),
        Index('idx_test_status', 'status'),
        Index('idx_test_type', 'test_type'),
    )

    def __repr__(self):
        return f"<ABTest(id={self.id}, name='{self.name}', type='{self.test_type}', status='{self.status}')>"

class ABTestEvent(Base):
    """Events (impressions, clicks, conversions) for A/B tests"""
    __tablename__ = "ab_test_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("ab_tests.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("ab_test_variants.id"), nullable=False, index=True)

    # Event Details
    visitor_id = Column(String(255), nullable=False, index=True)  # Session ID, IP hash, etc.
    event_type = Column(String(50), nullable=False, index=True)  # impression, click, add_to_cart, purchase

    # Event Data
    revenue = Column(Float, nullable=True)  # For purchase events
    event_metadata = Column(JSON, default=dict)  # Additional event data

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    test = relationship("ABTest", back_populates="events")
    variant = relationship("ABTestVariant", back_populates="events")

    __table_args__ = (
        Index('idx_event_test_variant', 'test_id', 'variant_id'),
        Index('idx_event_visitor', 'visitor_id'),
        Index('idx_event_type', 'event_type'),
        Index('idx_event_created', 'created_at'),
    )

    def __repr__(self):
        return f"<ABTestEvent(id={self.id}, test_id={self.test_id}, variant_id={self.variant_id}, type='{self.event_type}')>"

class ABTestAssignment(Base):
    """Track which variant each visitor was assigned to"""
    __tablename__ = "ab_test_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("ab_tests.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("ab_test_variants.id"), nullable=False, index=True)

    # Assignment Details
    visitor_id = Column(String(255), nullable=False, index=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    test = relationship("ABTest", back_populates="assignments")
    variant = relationship("ABTestVariant", back_populates="assignments")

    __table_args__ = (
        UniqueConstraint('test_id', 'visitor_id', name='unique_test_visitor'),
        Index('idx_assignment_test_variant', 'test_id', 'variant_id'),
        Index('idx_assignment_visitor', 'visitor_id'),
    )

    def __repr__(self):
        return f"<ABTestAssignment(test_id={self.test_id}, variant_id={self.variant_id}, visitor='{self.visitor_id}')>"


# ============================================================================
# AUTO-PILOT LOGS
# ============================================================================
