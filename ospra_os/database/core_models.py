"""
Core Models for OspraOS
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


class AIUsage(Base):
    """Track AI usage and costs per user"""
    __tablename__ = "ai_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # AI Provider Info
    provider = Column(SQLEnum(AIProvider), nullable=False, index=True)
    model = Column(String(100), nullable=False)  # claude-sonnet-4, gpt-4o, gemini-pro
    task_type = Column(SQLEnum(TaskType), nullable=False, index=True)

    # Usage Metrics
    tokens_used = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)  # USD

    # Context
    product_id = Column(Integer, nullable=True)  # Link to product if applicable
    store_id = Column(Integer, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="ai_usage")

    def __repr__(self):
        return f"<AIUsage(id={self.id}, provider='{self.provider}', cost=${self.estimated_cost:.4f})>"


# ============================================================================
# USER SETTINGS MODEL
# ============================================================================

class RankingHistory(Base):
    """Historical ranking snapshots for trend analysis"""
    __tablename__ = "ranking_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    # Ranking data
    rank = Column(Integer, nullable=False, index=True)
    composite_score = Column(Float, nullable=False)
    score_breakdown = Column(JSON)  # Store component scores

    # Rank changes
    previous_rank = Column(Integer)
    rank_change = Column(Integer, default=0)  # Positive = moved up, negative = moved down
    rank_direction = Column(String(10))  # "up", "down", "stable"

    # Tier info
    tier_name = Column(String(20))  # ELITE, TOP, RISING, etc.

    # Metadata
    snapshot_date = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    product = relationship("Product")

    # Composite index for efficient queries
    __table_args__ = (
        Index('idx_product_snapshot_date', 'product_id', 'snapshot_date'),
    )

    def __repr__(self):
        return f"<RankingHistory product_id={self.product_id} rank={self.rank} date={self.snapshot_date}>"

class Niche(Base):
    """Niche/category tracking for market analysis"""
    __tablename__ = "niches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    niche_id = Column(String, unique=True, index=True, nullable=False)  # e.g., "smart_home"
    name = Column(String, nullable=False)  # e.g., "Smart Home Devices"
    description = Column(Text)

    # Hierarchy
    parent_niche_id = Column(String, ForeignKey("niches.niche_id"), nullable=True)

    # SEO & Keywords
    keywords = Column(JSON)  # List of related search terms

    # Tracking metadata
    is_active = Column(Boolean, default=True, index=True)
    tracked_since = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Current metrics (cached from latest snapshot)
    current_health_score = Column(Float)
    current_lifecycle_stage = Column(SQLEnum(LifecycleStage))
    current_entry_timing = Column(SQLEnum(EntryTiming))

    # Relationships
    snapshots = relationship("NicheSnapshot", back_populates="niche", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Niche {self.niche_id}: {self.name} ({self.current_lifecycle_stage})>"

class NicheSnapshot(Base):
    """Daily/weekly snapshots of niche health and metrics"""
    __tablename__ = "niche_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    niche_id = Column(String, ForeignKey("niches.niche_id"), index=True, nullable=False)

    # Core scores
    health_score = Column(Float, nullable=False)  # 0-100 composite health score
    lifecycle_stage = Column(SQLEnum(LifecycleStage), nullable=False)

    # Metric components
    search_volume = Column(Integer)  # Current search volume
    search_volume_change_30d = Column(Float)  # % change in 30 days
    search_volume_change_90d = Column(Float)  # % change in 90 days
    trend_momentum = Column(Float)  # 0-100 score for demand growth

    # Competition metrics
    seller_count = Column(Integer)  # Number of active sellers
    new_sellers_30d = Column(Integer)  # New sellers in last 30 days
    saturation_score = Column(Float)  # 0-100 (100 = oversaturated)
    saturation_level = Column(String)  # LOW/MODERATE/HIGH/CRITICAL

    # Profitability metrics
    average_margin = Column(Float)  # Average profit margin %
    margin_trend = Column(String)  # "up", "down", "stable"
    price_pressure = Column(String)  # LOW/MEDIUM/HIGH

    # Longevity metrics
    is_seasonal = Column(Boolean, default=False)
    trend_stability = Column(Float)  # 0-1.0 (1.0 = very stable)
    predicted_lifespan = Column(String)  # e.g., "18+ months"
    longevity_score = Column(Float)  # 0-100

    # Entry recommendation
    entry_timing_score = Column(Float)  # 0-100
    entry_timing = Column(SQLEnum(EntryTiming))
    should_enter = Column(Boolean)
    risk_level = Column(SQLEnum(RiskLevel))
    estimated_roi_min = Column(Float)  # Min % ROI estimate
    estimated_roi_max = Column(Float)  # Max % ROI estimate
    entry_reasoning = Column(Text)  # Why this timing/recommendation

    # Competitor analysis
    top_competitors = Column(JSON)  # List of top brands/sellers
    barrier_to_entry = Column(String)  # LOW/MEDIUM/HIGH
    average_reviews = Column(Integer)

    # Week-over-week changes
    health_score_change = Column(Float)  # Change from previous snapshot
    stage_changed = Column(Boolean, default=False)  # Did lifecycle stage change?
    notable_events = Column(JSON)  # List of notable events this week

    # Top products in niche
    top_products = Column(JSON)  # Top 5 products with IDs and scores

    # Strategic recommendations
    recommendations = Column(JSON)  # List of actionable recommendations

    # Full analysis JSON (for flexibility)
    full_analysis = Column(JSON)

    # Temporal
    snapshot_date = Column(DateTime, index=True, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    niche = relationship("Niche", back_populates="snapshots")

    # Composite indexes for efficient queries
    __table_args__ = (
        Index('idx_niche_snapshot_date', 'niche_id', 'snapshot_date'),
        Index('idx_health_score', 'health_score'),
        Index('idx_lifecycle_stage', 'lifecycle_stage'),
        Index('idx_entry_timing', 'entry_timing'),
    )

    def __repr__(self):
        return f"<NicheSnapshot {self.niche_id} health={self.health_score} stage={self.lifecycle_stage} date={self.snapshot_date}>"


# ============================================================================
# A/B TESTING MODELS
# ============================================================================
