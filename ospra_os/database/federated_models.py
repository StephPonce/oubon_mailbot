"""
Federated Learning Database Models - GROK RECOMMENDATION #18

Privacy-preserving collective intelligence models.
Stores ONLY aggregated, anonymized data - never raw user data.
"""

from sqlalchemy import Column, Integer, String, Float, Text, JSON, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from ospra_os.database.multi_store_models import Base


class AggregateInsight(Base):
    """
    Aggregated insights derived from all users.
    Contains NO individual user data — only statistical patterns.

    Example:
    "Products in smart_home niche with price $10-20 and 4.5+ stars
     have 73% success rate (based on 247 samples from 45 users)"
    """
    __tablename__ = "aggregate_insights"

    id = Column(Integer, primary_key=True, index=True)

    # Insight classification
    insight_type = Column(String(50), nullable=False, index=True)
    # product_performance, pricing_pattern, ad_effectiveness,
    # seasonal_trend, supplier_quality, niche_velocity

    category = Column(String(100), nullable=True, index=True)  # Niche/category

    # The insight itself
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Statistical data (aggregated, anonymized)
    data = Column(JSON, nullable=False)
    # Example for product_performance:
    # {
    #   "sample_size": 1247,
    #   "confidence": 0.89,
    #   "pattern": {
    #     "optimal_price_bucket": "10_20",
    #     "optimal_margin_bucket": "40_50",
    #     "optimal_rating_bucket": "4.5_plus",
    #     "success_rate": 0.73
    #   }
    # }

    # Quality metrics
    sample_size = Column(Integer, default=0)  # Number of data points
    confidence = Column(Float, default=0)  # Statistical confidence (0-1)
    min_sample_threshold = Column(Integer, default=50)  # Min samples needed

    # Applicability
    applicable_niches = Column(JSON, default=list)
    applicable_tiers = Column(JSON, default=list)  # Subscription tiers

    # Lifecycle
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)  # Time-sensitive insights

    # Tracking
    times_applied = Column(Integer, default=0)  # Usage count
    success_when_applied = Column(Float, default=0)  # Success rate when applied

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_computed_at = Column(DateTime, default=datetime.utcnow)


class UserContribution(Base):
    """
    Tracks what each user contributes to federated learning.
    Stores ONLY metadata, not actual data.

    Privacy: All values are bucketed/anonymized before storage.
    """
    __tablename__ = "user_contributions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Contribution type
    contribution_type = Column(String(50), nullable=False)
    # product_outcome, pricing_result, ad_performance

    # Contribution data (bucketed, no exact values)
    contribution_data = Column(JSON, default=dict)
    # {
    #   "niche": "smart_home",
    #   "outcome": "success",  # success/failure only
    #   "price_bucket": "10_20",  # NOT exact price
    #   "margin_bucket": "40_50",  # NOT exact margin
    #   "rating_bucket": "4.5_plus",  # NOT exact rating
    #   "contributed_at": "2024-01"  # Month only
    # }

    # Quality score for this contribution
    quality_score = Column(Float, default=1.0)

    # Aggregation tracking
    included_in_aggregation = Column(Boolean, default=False)
    aggregation_batch_id = Column(String(50), nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)


class InsightApplication(Base):
    """
    Tracks when users apply aggregate insights.
    Used to measure insight effectiveness (anonymized feedback loop).
    """
    __tablename__ = "insight_applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    insight_id = Column(Integer, ForeignKey("aggregate_insights.id"), nullable=False)

    # Application context (no sensitive data)
    context = Column(JSON, default=dict)
    # {
    #   "action_type": "deploy_product",
    #   "niche": "smart_home"
    # }

    # Outcome (delayed, anonymized)
    outcome = Column(String(20), nullable=True)  # success, partial, failure, unknown
    outcome_recorded_at = Column(DateTime, nullable=True)

    # Timestamp
    applied_at = Column(DateTime, default=datetime.utcnow)


class PrivacyConsent(Base):
    """
    User consent for federated learning participation.
    GDPR/CCPA compliant opt-in tracking.
    """
    __tablename__ = "privacy_consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Consent flags
    federated_learning_enabled = Column(Boolean, default=False)
    aggregate_insights_enabled = Column(Boolean, default=True)  # Receive insights
    contribution_enabled = Column(Boolean, default=False)  # Contribute data

    # Granular controls
    contribute_product_data = Column(Boolean, default=False)
    contribute_pricing_data = Column(Boolean, default=False)
    contribute_ad_data = Column(Boolean, default=False)

    # Consent history
    consent_history = Column(JSON, default=list)
    # [{"action": "opted_in", "scope": "all", "timestamp": "..."}]

    # Legal
    consent_version = Column(String(20), default="1.0")
    consented_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Indexes for efficient querying
Index('idx_insights_type_category', AggregateInsight.insight_type, AggregateInsight.category)
Index('idx_contributions_user_type', UserContribution.user_id, UserContribution.contribution_type)
Index('idx_applications_user', InsightApplication.user_id)
