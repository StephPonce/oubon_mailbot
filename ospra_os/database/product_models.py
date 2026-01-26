"""
Product Models for OspraOS
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


class Product(Base):
    """Discovered or managed products"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)

    # Product Identity
    product_name = Column(String(512), nullable=False)
    title = Column(String(512), nullable=True)  # Alias for product_name (used by intelligence)
    product_sku = Column(String(255), nullable=True, index=True)

    # Source Information
    source_platform = Column(String(100), nullable=True)  # aliexpress, alibaba, dhgate
    source_url = Column(String(1024), nullable=True)
    source_product_id = Column(String(255), nullable=True)

    # Pricing
    supplier_cost = Column(Float, nullable=True)
    selling_price = Column(Float, nullable=True)
    price = Column(Float, nullable=True)  # Alias for selling_price (used by intelligence)
    profit_margin = Column(Float, nullable=True)  # Percentage

    # Intelligence Scores
    discovery_score = Column(Float, default=0.0)  # 0-10 scale
    trend_score = Column(Float, default=0.0)      # 0-100 Google Trends scale
    ai_explanation = Column(Text, nullable=True)   # Why this product was recommended
    grade = Column(String(3), nullable=True)  # A+, A, B+, B, C+, C, D, F

    # Intelligence - Profit Potential (Grade Factor 1)
    expected_monthly_sales = Column(Integer, default=0)

    # Intelligence - Trend Score (Grade Factor 2)
    velocity_score = Column(Float, default=0.0)  # 0-10 from velocity detector
    social_score = Column(Float, default=0.0)    # 0-100 TikTok/Instagram mentions
    search_trend = Column(Float, default=0.0)    # 0-100 Google Trends

    # Intelligence - Market Saturation (Grade Factor 3)
    saturation_level = Column(Float, default=50.0)  # 0-100 (lower = better)
    competitor_count = Column(Integer, default=0)
    differentiation_score = Column(Float, default=0.0)  # 0-10 uniqueness score

    # Intelligence - Quality (Grade Factor 4)
    rating = Column(Float, default=0.0)  # 0-5 stars
    review_count = Column(Integer, default=0)
    complaint_rate = Column(Float, default=0.0)  # 0-1 (complaints / sales)

    # Intelligence - Competitive Edge (Grade Factor 5)
    price_competitiveness = Column(Float, default=50.0)  # 0-100 (100 = best price)
    feature_superiority = Column(Float, default=0.0)  # 0-10 feature score
    brand_strength = Column(Float, default=0.0)  # 0-10 brand score

    # AI-Generated Content
    ai_title = Column(String(512), nullable=True)
    ai_description = Column(Text, nullable=True)
    ai_tags = Column(JSON, default=list)  # ["smart-home", "led", "wifi"]

    # Status
    status = Column(SQLEnum(ProductStatus), default=ProductStatus.DISCOVERED, nullable=False, index=True)

    # Performance Metrics
    total_sales = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    views = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)

    # Timestamps
    discovered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    queued_at = Column(DateTime, nullable=True)  # When queued for deployment
    deployed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Alias for updated_at

    # Relationships
    store = relationship("Store", back_populates="products")
    deployments = relationship("ProductDeployment", back_populates="product", cascade="all, delete-orphan")

    # Composite indexes for frequently queried combinations
    __table_args__ = (
        Index('ix_products_store_status', 'store_id', 'status'),
        Index('ix_products_store_conversion', 'store_id', 'conversion_rate'),
    )

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.product_name[:30]}...', status='{self.status}')>"


# ============================================================================
# PRODUCT DEPLOYMENT MODEL
# ============================================================================

class ProductDeployment(Base):
    """Track product deployment across multiple stores/platforms"""
    __tablename__ = "product_deployments"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)

    # Platform-specific IDs
    platform_product_id = Column(String(255), nullable=True)  # Shopify product ID, Amazon ASIN, etc.
    platform_url = Column(String(1024), nullable=True)
    platform_sku = Column(String(255), nullable=True)

    # Deployment Info
    deployment_status = Column(SQLEnum(DeploymentStatus), default=DeploymentStatus.PENDING, nullable=False, index=True)
    deployment_error = Column(Text, nullable=True)

    # AI-Generated Content (platform-specific)
    generated_title = Column(String(512), nullable=True)
    generated_description = Column(Text, nullable=True)
    generated_tags = Column(JSON, default=list)

    # Pricing (can differ per platform)
    platform_price = Column(Float, nullable=True)
    platform_compare_price = Column(Float, nullable=True)

    # Performance (platform-specific)
    platform_sales = Column(Integer, default=0)
    platform_revenue = Column(Float, default=0.0)
    platform_views = Column(Integer, default=0)
    platform_conversion_rate = Column(Float, default=0.0)

    # Timestamps
    deployed_at = Column(DateTime, nullable=True)
    last_synced = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    product = relationship("Product", back_populates="deployments")
    store = relationship("Store", back_populates="deployments")

    def __repr__(self):
        return f"<ProductDeployment(id={self.id}, product_id={self.product_id}, status='{self.deployment_status}')>"


# ============================================================================
# PRODUCT SATURATION TRACKING MODELS (Prevent AutoDS Problem)
# ============================================================================

class ProductSaturation(Base):
    """Track product saturation - how many users have this product"""
    __tablename__ = "product_saturation"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Product identifier (by name + source)
    product_name = Column(String(512), nullable=False, index=True)
    source_url = Column(String(1024))
    source_product_id = Column(String(255))

    # Saturation tracking
    total_users_count = Column(Integer, default=0, nullable=False)
    active_users_count = Column(Integer, default=0, nullable=False)  # Currently selling

    # Discovery tracking
    first_discovered_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_recommended_at = Column(DateTime)

    # Status
    is_saturated = Column(Boolean, default=False, index=True)
    saturation_threshold = Column(Integer, default=100, nullable=False)  # Max users

    # Performance tracking
    avg_success_rate = Column(Float, default=0.0)  # % of users who made sales
    total_revenue_generated = Column(Float, default=0.0)

    # Metadata
    niche = Column(String(100), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    recommendations = relationship("UserProductRecommendation", back_populates="product_saturation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ProductSaturation {self.product_name[:30]}... - {self.total_users_count} users>"

class ProductVelocity(Base):
    """Track product trend velocity and lifecycle phase"""
    __tablename__ = "product_velocity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_saturation_id = Column(Integer, ForeignKey('product_saturation.id'), nullable=False, index=True)

    # Velocity metrics
    search_volume_7d = Column(Integer, default=0)
    search_volume_30d = Column(Integer, default=0)
    search_growth_rate = Column(Float, default=0.0)  # % change

    reddit_mentions_7d = Column(Integer, default=0)
    reddit_mentions_30d = Column(Integer, default=0)
    reddit_growth_rate = Column(Float, default=0.0)

    # Social signals
    social_engagement_score = Column(Float, default=0.0)  # 0-100
    viral_coefficient = Column(Float, default=0.0)  # Velocity score

    # Lifecycle phase
    phase = Column(String(50), default='discovery', index=True)
    # Phases: 'discovery', 'early_spike', 'growth', 'maturity', 'decline'

    phase_age_days = Column(Integer, default=0)  # Days in current phase
    estimated_peak_date = Column(DateTime)

    # Tracking
    last_analyzed_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    product_saturation = relationship("ProductSaturation", backref="velocity")

    def __repr__(self):
        return f"<ProductVelocity(product_id={self.product_saturation_id}, phase='{self.phase}', velocity={self.viral_coefficient:.1f})>"


# ============================================================================
# AD CAMPAIGN MODEL
# ============================================================================

class ProductSnapshot(Base):
    """Track product metrics over time for velocity analysis"""
    __tablename__ = "product_snapshots"
    
    id = Column(Integer, primary_key=True)
    asin = Column(String, index=True)
    name = Column(String)
    price = Column(Float)
    rating = Column(Float)
    reviews_count = Column(Integer)
    bestseller_rank = Column(Integer)
    snapshot_date = Column(DateTime, default=datetime.utcnow, index=True)
    niche = Column(String)

class ProductIntelligence(Base):
    """Calculated intelligence metrics"""
    __tablename__ = "product_intelligence"
    
    id = Column(Integer, primary_key=True)
    asin = Column(String, unique=True, index=True)
    name = Column(String)
    
    # Velocity (YOUR MOAT)
    momentum_score = Column(Float, default=50.0)  # 0-100
    is_trending = Column(Boolean, default=False)
    rank_velocity_7d = Column(Float, default=0.0)
    review_velocity_7d = Column(Float, default=0.0)
    
    # Saturation (YOUR MOAT)
    saturation_level = Column(String, default='LOW')  # LOW/MEDIUM/HIGH/EXTREME
    opportunity_score = Column(Float, default=100.0)  # 0-100
    competitor_count = Column(Integer, default=0)
    
    last_updated = Column(DateTime, default=datetime.utcnow)

class ABTestVariant(Base):
    """A variant in an A/B test"""
    __tablename__ = "ab_test_variants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("ab_tests.id"), nullable=False, index=True)

    # Variant Identity
    name = Column(String(255), nullable=False)
    is_control = Column(Boolean, default=False, nullable=False)

    # Variant Configuration (test-type specific)
    config = Column(JSON, nullable=False)  # e.g., {"price": 29.99} or {"title": "..."}

    # Traffic Allocation
    traffic_percentage = Column(Float, default=50.0, nullable=False)  # % of traffic

    # Performance Metrics
    impressions = Column(Integer, default=0, nullable=False)
    clicks = Column(Integer, default=0, nullable=False)
    conversions = Column(Integer, default=0, nullable=False)
    revenue = Column(Float, default=0.0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    test = relationship("ABTest", back_populates="variants", foreign_keys=[test_id])
    events = relationship("ABTestEvent", back_populates="variant", cascade="all, delete-orphan")
    assignments = relationship("ABTestAssignment", back_populates="variant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ABTestVariant(id={self.id}, test_id={self.test_id}, name='{self.name}', control={self.is_control})>"
