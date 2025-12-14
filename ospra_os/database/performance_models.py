"""
Performance Tracking Models - G4: Complete Feedback Loop
=========================================================

Database models for tracking real-world performance and feeding back to AI.
This is the CORE of making Ospra's AI actually intelligent - it learns from
what ACTUALLY sells, not just what it thinks will sell.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date,
    ForeignKey, Text, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime, date
from enum import Enum as PyEnum

from ospra_os.database.base import Base


class PerformanceOutcome(str, PyEnum):
    """Outcome classification for AI recommendations."""
    exceptional = "exceptional"    # Far exceeded expectations (>150% projected)
    success = "success"            # Met or exceeded expectations (100-150%)
    moderate = "moderate"          # Underperformed but profitable (50-100%)
    poor = "poor"                  # Significantly underperformed (25-50%)
    failure = "failure"            # Failed (<25% or loss)
    pending = "pending"            # Not enough data yet


class ProductPerformance(Base):
    """
    Daily performance snapshot for deployed products.
    Tracks actual sales, revenue, and key metrics.

    This is synced from Shopify/Amazon every 6 hours to provide
    real-time feedback on how AI recommendations are performing.
    """
    __tablename__ = "product_performance"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Date of this snapshot
    date = Column(Date, nullable=False)

    # Sales metrics
    orders = Column(Integer, default=0)
    units_sold = Column(Integer, default=0)
    gross_revenue = Column(Float, default=0)
    refunds = Column(Float, default=0)
    net_revenue = Column(Float, default=0)

    # Cost metrics
    product_cost = Column(Float, default=0)          # COGS
    shipping_cost = Column(Float, default=0)
    platform_fees = Column(Float, default=0)         # Shopify/Amazon fees
    ad_spend = Column(Float, default=0)
    total_cost = Column(Float, default=0)

    # Profit
    gross_profit = Column(Float, default=0)
    net_profit = Column(Float, default=0)
    profit_margin = Column(Float, default=0)         # As percentage

    # Traffic metrics
    views = Column(Integer, default=0)
    add_to_carts = Column(Integer, default=0)
    checkout_initiated = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0)       # orders/views * 100

    # Ad metrics (if running ads)
    ad_impressions = Column(Integer, default=0)
    ad_clicks = Column(Integer, default=0)
    ad_ctr = Column(Float, default=0)
    ad_cpc = Column(Float, default=0)
    ad_roas = Column(Float, default=0)               # Return on ad spend

    # Inventory
    inventory_level = Column(Integer, default=0)

    # Sync info
    synced_at = Column(DateTime, default=datetime.utcnow)
    sync_source = Column(String(50))                 # shopify, amazon, manual

    __table_args__ = (
        UniqueConstraint('product_id', 'date', name='uq_product_date'),
        Index('idx_performance_product_date', 'product_id', 'date'),
        Index('idx_performance_user_date', 'user_id', 'date'),
        Index('idx_performance_store_date', 'store_id', 'date'),
    )


class RecommendationOutcome(Base):
    """
    Tracks the outcome of AI recommendations.
    This is the KEY feedback mechanism for AI learning.

    When AI recommends a product, we record:
    - What it predicted (revenue, sales, margin)
    - What actually happened (real revenue, sales, margin)
    - How accurate the prediction was

    This feeds back into the AI to improve future recommendations.
    """
    __tablename__ = "recommendation_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # What was recommended
    action_id = Column(Integer, nullable=True)  # FK to pending_actions.id (will add when table exists)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    campaign_id = Column(Integer, nullable=True)  # For ad campaigns when implemented

    # Recommendation details at time of recommendation
    recommendation_type = Column(String(50), nullable=False)  # product_deploy, price_adjust, ad_deploy
    confidence_score = Column(Float, nullable=False)          # AI's confidence at time
    confidence_breakdown = Column(JSON, default=dict)
    ai_reasoning = Column(Text, nullable=True)

    # Projections at time of recommendation
    projected_daily_sales = Column(Float, nullable=True)
    projected_monthly_revenue = Column(Float, nullable=True)
    projected_margin = Column(Float, nullable=True)
    projected_roi = Column(Float, nullable=True)

    # User decision
    was_accepted = Column(Boolean, default=False)
    accepted_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Actual performance (updated over time)
    actual_daily_sales_avg = Column(Float, nullable=True)
    actual_total_revenue = Column(Float, nullable=True)
    actual_total_profit = Column(Float, nullable=True)
    actual_margin = Column(Float, nullable=True)
    actual_roi = Column(Float, nullable=True)

    # Outcome assessment
    outcome = Column(String(20), default="pending")
    outcome_score = Column(Float, nullable=True)              # 0-100 score
    accuracy_score = Column(Float, nullable=True)             # How accurate was prediction

    # Tracking period
    tracking_started_at = Column(DateTime, nullable=True)
    tracking_ended_at = Column(DateTime, nullable=True)
    tracking_days = Column(Integer, default=0)

    # Learning processed
    learning_processed = Column(Boolean, default=False)
    learning_processed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_outcomes_user', 'user_id'),
        Index('idx_outcomes_product', 'product_id'),
        Index('idx_outcomes_outcome', 'outcome'),
        Index('idx_outcomes_learning', 'learning_processed'),
    )


class AILearningEvent(Base):
    """
    Individual learning events derived from outcomes.
    These feed into the AI model weight adjustments.

    Example: If AI predicted 85% confidence and product succeeded,
    we create a positive learning event validating the factors
    that led to that high confidence score.
    """
    __tablename__ = "ai_learning_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    outcome_id = Column(Integer, ForeignKey("recommendation_outcomes.id"), nullable=True)

    # Event type
    event_type = Column(String(50), nullable=False)  # product_success, product_failure, price_optimal, etc.

    # Context at time of event
    context = Column(JSON, nullable=False)           # All relevant factors

    # What we learned
    lesson_type = Column(String(50), nullable=False) # positive_signal, negative_signal, neutral
    lesson_strength = Column(Float, default=1.0)     # How strongly to weight this lesson

    # Specific learnings
    factors_validated = Column(JSON, default=list)   # Factors that proved correct
    factors_invalidated = Column(JSON, default=list) # Factors that proved wrong

    # Weight adjustments applied
    weight_adjustments = Column(JSON, default=dict)  # {factor: adjustment}

    # Processing
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_learning_user', 'user_id'),
        Index('idx_learning_type', 'event_type'),
        Index('idx_learning_processed', 'processed'),
    )


class ConfidenceCalibration(Base):
    """
    Tracks how well AI confidence scores predict actual outcomes.
    Used to calibrate and improve confidence scoring.

    Example: If AI says 80% confidence, does product actually
    succeed 80% of the time? If not, we adjust.
    """
    __tablename__ = "confidence_calibration"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL = global

    # Confidence bucket (e.g., 80-85%)
    confidence_bucket_min = Column(Float, nullable=False)
    confidence_bucket_max = Column(Float, nullable=False)

    # Recommendation type
    recommendation_type = Column(String(50), nullable=False)

    # Statistics
    total_recommendations = Column(Integer, default=0)
    successful_outcomes = Column(Integer, default=0)
    actual_success_rate = Column(Float, default=0)        # successful/total * 100

    # Calibration
    expected_success_rate = Column(Float, default=0)      # Middle of bucket
    calibration_error = Column(Float, default=0)          # actual - expected

    # Trend
    recent_success_rate = Column(Float, default=0)        # Last 30 days
    trend_direction = Column(String(20), default="stable") # improving, stable, declining

    # Last updated
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'confidence_bucket_min', 'recommendation_type',
                        name='uq_calibration_bucket'),
        Index('idx_calibration_user_type', 'user_id', 'recommendation_type'),
    )


class NicheLearning(Base):
    """
    Aggregated learnings per niche/category.
    Helps AI understand which niches work for which users.

    Example: User deploys 5 fitness products, 4 succeed.
    AI learns to boost fitness recommendations for this user.
    """
    __tablename__ = "niche_learning"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL = global

    # Niche
    niche = Column(String(100), nullable=False)

    # Performance stats
    total_products_deployed = Column(Integer, default=0)
    successful_products = Column(Integer, default=0)
    failed_products = Column(Integer, default=0)
    success_rate = Column(Float, default=0)

    # Revenue stats
    total_revenue = Column(Float, default=0)
    total_profit = Column(Float, default=0)
    average_margin = Column(Float, default=0)
    average_daily_sales = Column(Float, default=0)

    # Best performing product info
    best_product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    best_product_revenue = Column(Float, default=0)

    # AI adjustments
    niche_score_adjustment = Column(Float, default=0)  # +/- adjustment to apply

    # Timestamps
    first_product_at = Column(DateTime, nullable=True)
    last_product_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'niche', name='uq_niche_user'),
        Index('idx_niche_learning_user', 'user_id'),
        Index('idx_niche_learning_success', 'success_rate'),
    )


class GlobalLearningWeights(Base):
    """
    Global AI model weights learned from all users.
    These are the baseline weights before personalization.
    """
    __tablename__ = "global_learning_weights"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False, unique=True)  # confidence, pricing, etc.
    weights = Column(JSON, nullable=False)  # {factor: weight}
    version = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_global_weights_category', 'category'),
    )


class PersonalLearningWeights(Base):
    """
    User-specific AI model weights.
    These personalize the AI based on what works for THIS specific user.
    """
    __tablename__ = "personal_learning_weights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(50), nullable=False)  # confidence, pricing, etc.
    weights = Column(JSON, nullable=False)  # {factor: weight}
    version = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'category', name='uq_user_category'),
        Index('idx_personal_weights_user', 'user_id'),
    )
