"""
Multi-Store, Multi-Tenant Database Models
Supports Shopify, Amazon, WooCommerce with AI provider abstraction
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Index, JSON, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, sessionmaker
from sqlalchemy import create_engine
from datetime import datetime
import enum
import json
import os

Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class SubscriptionTier(str, enum.Enum):
    """
    User subscription levels - Sky/Flight themed
    
    🪺 Nest → Free tier (grounded, learning)
    ✈️ Flight → $29/mo (first flight, momentum)
    🦅 Soar → $79/mo (high altitude, seeing far)
    🌌 Stratosphere → $199/mo (edge of space, first to see)
    """
    NEST = "nest"
    FLIGHT = "flight"
    SOAR = "soar"
    STRATOSPHERE = "stratosphere"
    
    # Legacy aliases for backward compatibility
    FREE = "nest"        # Maps to NEST
    STARTER = "flight"   # Maps to FLIGHT  
    PRO = "soar"         # Maps to SOAR
    ENTERPRISE = "stratosphere"  # Maps to STRATOSPHERE


class Platform(str, enum.Enum):
    """Supported e-commerce platforms"""
    SHOPIFY = "shopify"
    AMAZON = "amazon"
    WOOCOMMERCE = "woocommerce"
    ETSY = "etsy"
    EBAY = "ebay"


class StoreStatus(str, enum.Enum):
    """Store connection and operational status"""
    SETUP = "setup"           # Initial setup in progress
    ACTIVE = "active"         # Connected and operational
    PAUSED = "paused"         # Temporarily paused by user
    DISCONNECTED = "disconnected"  # API connection lost
    ERROR = "error"           # Configuration or API error


class ProductStatus(str, enum.Enum):
    """Product lifecycle status"""
    DISCOVERED = "discovered"      # Found by intelligence engine
    QUEUED = "queued"              # Queued for deployment
    DEPLOYING = "deploying"        # Being deployed
    DEPLOYED = "deployed"          # Successfully deployed
    ACTIVE = "active"              # Live and selling
    PAUSED = "paused"              # Temporarily paused
    DISCONTINUED = "discontinued"  # Removed from store


class DeploymentStatus(str, enum.Enum):
    """Product deployment status per platform"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SYNCING = "syncing"


class AIProvider(str, enum.Enum):
    """AI providers for content generation"""
    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"
    CUSTOM = "custom"


class TaskType(str, enum.Enum):
    """AI task types for cost tracking"""
    PRODUCT_ANALYSIS = "product_analysis"
    CONTENT_GENERATION = "content_generation"
    TITLE_OPTIMIZATION = "title_optimization"
    DESCRIPTION_GENERATION = "description_generation"
    TREND_ANALYSIS = "trend_analysis"
    PRICING_OPTIMIZATION = "pricing_optimization"


class TriggerType(str, enum.Enum):
    """Email automation trigger types"""
    KEYWORD = "keyword"
    SENDER = "sender"
    SUBJECT = "subject"
    LABEL = "label"


class ActionType(str, enum.Enum):
    """Email automation action types"""
    LABEL = "label"
    REPLY = "reply"
    FORWARD = "forward"
    DELETE = "delete"
    MARK_READ = "mark_read"
    AI_REPLY = "ai_reply"  # AI-powered contextual response


class LifecycleStage(str, enum.Enum):
    """Niche lifecycle stages"""
    EMERGING = "emerging"      # 🌱 New niche, low competition, growing interest
    GROWTH = "growth"          # 🚀 Accelerating demand, increasing competition
    PEAK = "peak"              # 📈 Maximum demand, high competition
    DECLINE = "decline"        # 📉 Decreasing demand, oversaturated
    DEAD = "dead"              # 💀 Minimal demand, avoid


class EntryTiming(str, enum.Enum):
    """Niche entry timing recommendations"""
    EXCELLENT = "excellent"    # Score 80+: Enter immediately
    GOOD = "good"              # Score 60-79: Good time to enter
    FAIR = "fair"              # Score 40-59: Proceed with caution
    POOR = "poor"              # Score 20-39: High risk
    AVOID = "avoid"            # Score <20: Do not enter


class RiskLevel(str, enum.Enum):
    """Risk levels for niche entry"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# USER MODEL
# ============================================================================

class User(Base):
    """Multi-tenant user with subscription and AI preferences"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    
    # Authentication
    password_hash = Column(String(255), nullable=True)  # Nullable for existing users

    # Subscription
    subscription_tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.NEST, nullable=False)
    subscription_started = Column(DateTime, default=datetime.utcnow)
    subscription_expires = Column(DateTime, nullable=True)

    # AI Preferences
    ai_preference = Column(SQLEnum(AIProvider), default=AIProvider.CLAUDE, nullable=False)
    custom_ai_keys = Column(JSON, default=dict)  # Encrypted JSON: {"openai": "sk-...", "claude": "sk-..."}

    # Usage Limits (based on tier)
    monthly_ai_budget = Column(Float, default=10.0)  # USD
    monthly_product_limit = Column(Integer, default=50)

    # Tracking
    total_stores = Column(Integer, default=0)
    total_products = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    stores = relationship("Store", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    ai_usage = relationship("AIUsage", back_populates="user", cascade="all, delete-orphan")
    product_recommendations = relationship("UserProductRecommendation", back_populates="user", cascade="all, delete-orphan")
    email_accounts = relationship("UserEmailAccount", back_populates="user", cascade="all, delete-orphan")
    emails = relationship("Email", back_populates="user", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', tier='{self.subscription_tier}')>"


# ============================================================================
# STORE MODEL
# ============================================================================

class Store(Base):
    """Platform-agnostic store representation"""
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Store Identity
    store_name = Column(String(255), nullable=False)
    store_url = Column(String(512), nullable=False)
    platform = Column(SQLEnum(Platform), nullable=False, index=True)

    # Platform-specific credentials (encrypted JSON)
    # Shopify: {"shop_url": "...", "access_token": "...", "api_version": "2025-01"}
    # Amazon: {"seller_id": "...", "mws_token": "...", "marketplace_id": "..."}
    # WooCommerce: {"site_url": "...", "consumer_key": "...", "consumer_secret": "..."}
    credentials = Column(JSON, nullable=False)

    # Store Configuration
    niche = Column(String(255), nullable=True)  # smart_home, fitness, beauty, etc.
    target_market = Column(String(100), default="US")
    currency = Column(String(10), default="USD")

    # Performance Tracking
    total_revenue = Column(Float, default=0.0)
    monthly_revenue = Column(Float, default=0.0)
    total_orders = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)  # Percentage

    # Ranking (for leaderboards)
    rank_position = Column(Integer, nullable=True)
    rank_change = Column(Integer, default=0)  # +5, -2, etc.

    # Status (GROK #11: Multi-Store Support)
    status = Column(SQLEnum(StoreStatus), default=StoreStatus.SETUP, nullable=False, index=True)
    is_active = Column(Boolean, default=True)  # Kept for backward compatibility
    pending_actions_count = Column(Integer, default=0, nullable=False)
    last_sync = Column(DateTime, nullable=True)
    sync_error = Column(Text, nullable=True)  # Last sync error message

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="stores")
    products = relationship("Product", back_populates="store", cascade="all, delete-orphan")
    deployments = relationship("ProductDeployment", back_populates="store", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="store", cascade="all, delete-orphan")
    cross_store_learnings_source = relationship("CrossStoreLearning", foreign_keys="CrossStoreLearning.source_store_id", back_populates="source_store", cascade="all, delete-orphan")
    cross_store_learnings_target = relationship("CrossStoreLearning", foreign_keys="CrossStoreLearning.target_store_id", back_populates="target_store", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Store(id={self.id}, name='{self.store_name}', platform='{self.platform}', status='{self.status}')>"

    def get_credentials(self):
        """Helper to access credentials safely"""
        return self.credentials if isinstance(self.credentials, dict) else json.loads(self.credentials)


# ============================================================================
# CROSS-STORE LEARNING MODEL (GROK #11)
# ============================================================================

class CrossStoreLearning(Base):
    """
    Track learnings from one store that can be applied to another.

    Example: "Yoga mats convert at 4.2% in Store A (Fitness First),
    recommend for Store B (Health Hub) if niche matches."
    """
    __tablename__ = "cross_store_learnings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Source and Target Stores
    source_store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    target_store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)

    # Learning Type
    learning_type = Column(String(50), nullable=False, index=True)
    # Types: "product_performance", "pricing_strategy", "niche_affinity", "audience_insight"

    # Product-specific learning (optional)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    product_name = Column(String(512), nullable=True)
    product_category = Column(String(255), nullable=True)

    # Performance Metrics from Source Store
    source_conversion_rate = Column(Float, nullable=True)  # 4.2%
    source_revenue = Column(Float, nullable=True)  # $5,420
    source_orders = Column(Integer, nullable=True)  # 127 orders
    source_avg_order_value = Column(Float, nullable=True)  # $42.68

    # Niche Applicability
    applicable_niches = Column(JSON, default=list)  # ["fitness", "wellness", "yoga"]
    niche_match_score = Column(Float, default=0.0)  # 0-100, how well this applies to target store

    # Insight & Recommendation
    insight = Column(Text, nullable=False)  # "Yoga mats convert exceptionally well in fitness stores"
    recommendation = Column(Text, nullable=False)  # "Add yoga mats to Health Hub - projected 3.8% conversion"
    confidence_score = Column(Float, default=0.0)  # 0-100, confidence in this recommendation

    # Projected Impact on Target Store
    projected_conversion_rate = Column(Float, nullable=True)
    projected_monthly_revenue = Column(Float, nullable=True)
    projected_roi = Column(Float, nullable=True)  # Return on investment %

    # Action Status
    status = Column(String(50), default="pending", index=True)
    # Statuses: "pending", "applied", "testing", "successful", "failed", "dismissed"
    applied_at = Column(DateTime, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    dismissal_reason = Column(Text, nullable=True)

    # Actual Performance (if applied)
    actual_conversion_rate = Column(Float, nullable=True)
    actual_revenue = Column(Float, nullable=True)
    actual_orders = Column(Integer, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source_store = relationship("Store", foreign_keys=[source_store_id], back_populates="cross_store_learnings_source")
    target_store = relationship("Store", foreign_keys=[target_store_id], back_populates="cross_store_learnings_target")
    product = relationship("Product", foreign_keys=[product_id])

    # Composite indexes for efficient queries
    __table_args__ = (
        Index('idx_cross_learning_source_target', 'source_store_id', 'target_store_id'),
        Index('idx_cross_learning_type_status', 'learning_type', 'status'),
        Index('idx_cross_learning_target_status', 'target_store_id', 'status'),
    )

    def __repr__(self):
        return f"<CrossStoreLearning(source_store={self.source_store_id}, target_store={self.target_store_id}, type='{self.learning_type}', status='{self.status}')>"


# ============================================================================
# PRODUCT MODEL
# ============================================================================

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


class UserProductRecommendation(Base):
    """Track which products were recommended to which users"""
    __tablename__ = "user_product_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    product_saturation_id = Column(Integer, ForeignKey('product_saturation.id'), nullable=False, index=True)

    # Recommendation details
    recommended_at = Column(DateTime, default=datetime.utcnow, index=True)
    recommendation_score = Column(Float)  # AI score when recommended

    # User actions
    was_deployed = Column(Boolean, default=False)
    deployed_at = Column(DateTime)

    was_successful = Column(Boolean, default=False)  # Made sales?
    total_sales = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)

    # Status
    is_active = Column(Boolean, default=True)  # Still selling?
    removed_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="product_recommendations")
    product_saturation = relationship("ProductSaturation", back_populates="recommendations")

    __table_args__ = (
        UniqueConstraint('user_id', 'product_saturation_id', name='unique_user_product'),
    )

    def __repr__(self):
        return f"<UserProductRecommendation User {self.user_id} - Product {self.product_saturation_id}>"


# ============================================================================
# PRODUCT VELOCITY MODEL
# ============================================================================

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

class AdCampaign(Base):
    """Track advertising campaigns across Meta, TikTok, and Google Ads"""
    __tablename__ = "ad_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True, index=True)

    # Campaign Details
    campaign_id = Column(String(255), nullable=False, index=True)  # Platform campaign ID
    platform = Column(String(50), nullable=False, index=True)  # meta, tiktok, google
    campaign_name = Column(String(512), nullable=False)

    # Budget
    daily_budget = Column(Float, default=0.0, nullable=False)
    total_spend = Column(Float, default=0.0)
    budget_limit = Column(Float, nullable=True)  # Optional hard limit

    # Performance Metrics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)

    # Calculated Metrics (updated automatically)
    ctr = Column(Float, default=0.0)  # Click-through rate (%)
    cpc = Column(Float, default=0.0)  # Cost per click
    roas = Column(Float, default=0.0)  # Return on ad spend

    # Status
    status = Column(String(50), default='paused', index=True)  # active, paused, ended
    pause_reason = Column(Text, nullable=True)

    # Creative Info
    ad_copy = Column(Text, nullable=True)
    image_url = Column(String(1024), nullable=True)
    video_id = Column(String(255), nullable=True)

    # Targeting
    target_audience = Column(JSON, default=dict)  # Platform-specific targeting params

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    activated_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    # user = relationship("User", backref="ad_campaigns")
    # product = relationship("Product", backref="ad_campaigns")
    # store = relationship("Store", backref="ad_campaigns")

    def __repr__(self):
        return f"<AdCampaign(id={self.id}, platform='{self.platform}', status='{self.status}')>"

    def update_metrics(self, impressions: int = None, clicks: int = None,
                      conversions: int = None, revenue: float = None, spend: float = None):
        """
        Update campaign metrics and calculate derived values.

        Args:
            impressions: Total impressions
            clicks: Total clicks
            conversions: Total conversions
            revenue: Total revenue
            spend: Total spend
        """
        if impressions is not None:
            self.impressions = impressions
        if clicks is not None:
            self.clicks = clicks
        if conversions is not None:
            self.conversions = conversions
        if revenue is not None:
            self.revenue = revenue
        if spend is not None:
            self.total_spend = spend

        # Calculate CTR
        if self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        else:
            self.ctr = 0.0

        # Calculate CPC
        if self.clicks > 0 and self.total_spend > 0:
            self.cpc = self.total_spend / self.clicks
        else:
            self.cpc = 0.0

        # Calculate ROAS
        if self.total_spend > 0:
            self.roas = self.revenue / self.total_spend
        else:
            self.roas = 0.0

        self.last_updated = datetime.utcnow()

    def get_performance_summary(self) -> dict:
        """Get campaign performance summary."""
        return {
            'campaign_id': self.campaign_id,
            'platform': self.platform,
            'status': self.status,
            'daily_budget': self.daily_budget,
            'total_spend': round(self.total_spend, 2),
            'impressions': self.impressions,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'revenue': round(self.revenue, 2),
            'ctr': round(self.ctr, 2),
            'cpc': round(self.cpc, 2),
            'roas': round(self.roas, 2),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'activated_at': self.activated_at.isoformat() if self.activated_at else None
        }


# ============================================================================
# AI USAGE MODEL
# ============================================================================

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

class UserSettings(Base):
    """User preferences and automation settings"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # AI Preferences
    preferred_ai_provider = Column(SQLEnum(AIProvider), default=AIProvider.CLAUDE)
    ai_creativity_level = Column(Float, default=0.7)  # 0.0 (conservative) to 1.0 (creative)

    # Subscription Tier
    subscription_tier = Column(String(20), default='free', index=True)
    # Options: 'free', 'starter', 'pro', 'elite'

    tier_expires_at = Column(DateTime)  # Subscription expiry
    tier_started_at = Column(DateTime)

    # Tier Limits
    max_stores = Column(Integer, default=1)  # Free: 1, Starter: 3, Pro: 10, Elite: unlimited (-1)
    max_products_per_week = Column(Integer, default=5)  # Free: 5, Starter: 25, Pro/Elite: unlimited (-1)

    # Discovery Preferences
    auto_discover_products = Column(Boolean, default=True)
    min_discovery_score = Column(Float, default=7.0)  # Only show products with score >= 7.0
    max_supplier_cost = Column(Float, default=50.0)   # Max product cost in USD
    preferred_niches = Column(JSON, default=list)     # ["smart_home", "fitness"]

    # Automation Settings
    auto_deploy_to_shopify = Column(Boolean, default=False)
    auto_generate_content = Column(Boolean, default=True)
    auto_optimize_pricing = Column(Boolean, default=True)

    # Notification Settings
    email_notifications = Column(Boolean, default=True)
    notify_new_products = Column(Boolean, default=True)
    notify_price_drops = Column(Boolean, default=False)
    notify_trend_spikes = Column(Boolean, default=True)

    # Auto-Pilot Settings
    auto_pilot_enabled = Column(Boolean, default=False)
    auto_pilot_threshold = Column(Float, default=85.0)  # 0-100 confidence threshold
    auto_pilot_rules = Column(JSON, default=dict)  # Per-action type rules
    notify_on_auto_execute = Column(Boolean, default=True)
    daily_summary_email = Column(Boolean, default=True)
    daily_auto_execute_limit = Column(Integer, default=20)  # Max auto-executions per day
    max_auto_spend = Column(Float, default=500.0)  # Max $ impact per day

    # Dashboard Settings
    default_currency = Column(String(10), default="USD")
    default_timezone = Column(String(50), default="UTC")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, auto_deploy={self.auto_deploy_to_shopify})>"


# ============================================================================
# USER EMAIL ACCOUNTS - Multi-Provider OAuth
# ============================================================================

class UserEmailAccount(Base):
    """
    Multi-provider email OAuth credentials for users.

    Supports Gmail, Outlook, and Yahoo with encrypted credential storage.
    Each user can connect multiple email accounts.
    """
    __tablename__ = "user_email_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    # Provider & Account Info
    provider = Column(String(50), nullable=False)  # 'gmail', 'outlook', 'yahoo'
    email_address = Column(String(255), nullable=False, index=True)

    # Encrypted OAuth Credentials
    encrypted_credentials = Column(Text, nullable=False)  # JSON with access_token, refresh_token, etc.

    # Account Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)  # One primary per user

    # Sync Status
    last_synced = Column(DateTime, nullable=True)
    sync_status = Column(String(50), default='active')  # 'active', 'error', 'paused'
    sync_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="email_accounts")
    emails = relationship("Email", back_populates="email_account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserEmailAccount(id={self.id}, user_id={self.user_id}, provider='{self.provider}', email='{self.email_address}', primary={self.is_primary})>"


class Email(Base):
    """
    Synced emails from connected email accounts.

    Stores emails fetched via Gmail API, Outlook Graph API, or IMAP.
    """
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    email_account_id = Column(Integer, ForeignKey('user_email_accounts.id'), nullable=False, index=True)

    # Email identifiers (provider-specific)
    message_id = Column(String(500), nullable=False, index=True)  # Gmail: message ID, Outlook: message ID, IMAP: UID
    external_id = Column(String(500), nullable=True, index=True)  # Provider-specific external ID (for Outlook Graph API)
    thread_id = Column(String(500), nullable=True, index=True)  # For threading emails

    # Email headers
    from_address = Column(String(500), nullable=False, index=True)
    from_name = Column(String(500), nullable=True)
    to_addresses = Column(Text, nullable=True)  # JSON array
    cc_addresses = Column(Text, nullable=True)  # JSON array
    bcc_addresses = Column(Text, nullable=True)  # JSON array
    subject = Column(Text, nullable=True)

    # Email content
    body_plain = Column(Text, nullable=True)  # Plain text body
    body_html = Column(Text, nullable=True)  # HTML body
    snippet = Column(Text, nullable=True)  # Short preview

    # Email metadata
    received_at = Column(DateTime, nullable=False, index=True)  # When email was sent/received
    labels = Column(JSON, nullable=True)  # Gmail labels or Outlook categories
    is_read = Column(Boolean, default=False, nullable=False)
    is_starred = Column(Boolean, default=False, nullable=False)
    is_important = Column(Boolean, default=False, nullable=False)
    has_attachments = Column(Boolean, default=False, nullable=False)

    # Sync metadata
    synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_data = Column(JSON, nullable=True)  # Full API response for debugging

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="emails")
    email_account = relationship("UserEmailAccount", back_populates="emails")

    # Unique constraint: one message per account
    __table_args__ = (
        UniqueConstraint('email_account_id', 'message_id', name='unique_email_per_account'),
        Index('idx_email_user_received', 'user_id', 'received_at'),
        Index('idx_email_account_received', 'email_account_id', 'received_at'),
        Index('idx_email_from', 'from_address'),
        Index('idx_email_read', 'is_read'),
    )

    def __repr__(self):
        return f"<Email(id={self.id}, from='{self.from_address}', subject='{self.subject[:50] if self.subject else ''}', received={self.received_at})>"


# ============================================================================
# EMAIL AUTOMATION MODELS
# ============================================================================

class EmailAutomationRule(Base):
    """
    User-defined email automation rules.

    Triggers: keyword in body, sender address, subject line, label
    Actions: apply label, auto-reply with template, forward, delete, mark as read
    """
    __tablename__ = "email_automation_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    # Rule Identity
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Trigger Configuration
    trigger_type = Column(SQLEnum(TriggerType), nullable=False, index=True)
    trigger_value = Column(Text, nullable=False)  # keyword, sender email, subject pattern, label name

    # Action Configuration
    action_type = Column(SQLEnum(ActionType), nullable=False, index=True)
    action_value = Column(Text, nullable=False)  # label name, template ID, forward address, etc.

    # Rule Settings
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    priority = Column(Integer, default=100, nullable=False)  # Lower number = higher priority

    # Usage Statistics
    times_triggered = Column(Integer, default=0)
    last_triggered = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<EmailAutomationRule(id={self.id}, name='{self.name}', trigger='{self.trigger_type}', action='{self.action_type}')>"


class EmailTemplate(Base):
    """
    Reusable email templates with variable support.

    Variables use {{variable_name}} syntax and are replaced with dynamic content.
    """
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    # Template Identity
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Template Content
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)

    # Variable Configuration
    variables = Column(JSON, default=list)  # ['name', 'order_id', 'ticket_id', etc.]

    # Usage Statistics
    times_used = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<EmailTemplate(id={self.id}, name='{self.name}', subject='{self.subject[:30]}...')>"


class EmailLabel(Base):
    """
    User-defined custom email labels with colors.

    Used to organize and categorize emails beyond provider defaults.
    """
    __tablename__ = "email_labels"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    # Label Identity
    name = Column(String(100), nullable=False)
    color = Column(String(7), nullable=False)  # Hex color code (e.g., '#3B82F6')

    # Usage Statistics
    email_count = Column(Integer, default=0)  # Number of emails with this label

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: one label name per user
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='unique_label_per_user'),
    )

    def __repr__(self):
        return f"<EmailLabel(id={self.id}, name='{self.name}', color='{self.color}', count={self.email_count})>"


# ============================================================================
# INDEXES FOR PERFORMANCE
# ============================================================================

# User indexes
Index('idx_user_email', User.email)
Index('idx_user_subscription', User.subscription_tier)

# Store indexes
Index('idx_store_user_platform', Store.user_id, Store.platform)
Index('idx_store_active', Store.is_active)

# Product indexes
Index('idx_product_store_status', Product.store_id, Product.status)
Index('idx_product_discovery_score', Product.discovery_score)
Index('idx_product_discovered_at', Product.discovered_at)

# Deployment indexes
Index('idx_deployment_product_store', ProductDeployment.product_id, ProductDeployment.store_id)
Index('idx_deployment_status', ProductDeployment.deployment_status)

# AI Usage indexes
Index('idx_ai_usage_user_date', AIUsage.user_id, AIUsage.created_at)
Index('idx_ai_usage_provider', AIUsage.provider)

# Ad Campaign indexes
Index('idx_ad_campaign_user_platform', AdCampaign.user_id, AdCampaign.platform)
Index('idx_ad_campaign_status', AdCampaign.status)
Index('idx_ad_campaign_product', AdCampaign.product_id)
Index('idx_ad_campaign_created', AdCampaign.created_at)


# ============================================================================
# DATABASE INITIALIZATION FUNCTIONS
# ============================================================================

def init_multi_store_db(database_url: str = "sqlite:///./multi_store.db"):
    """
    Initialize multi-store database with all tables

    Args:
        database_url: SQLAlchemy database URL

    Returns:
        engine: SQLAlchemy engine
    """
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        echo=False
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    print(f"✅ Multi-store database initialized at: {database_url}")
    print(f"   Tables created: {len(Base.metadata.tables)}")

    return engine


def get_multi_store_session(database_url: str = "sqlite:///./multi_store.db") -> Session:
    """
    Get database session for multi-store operations

    Args:
        database_url: SQLAlchemy database URL

    Returns:
        Session: SQLAlchemy session
    """
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
    )

    # Ensure all tables exist before creating session
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def migrate_existing_store(
    database_url: str,
    user_email: str,
    user_name: str,
    shopify_credentials: dict,
    store_name: str = "My Shopify Store"
):
    """
    Migration helper to import existing single-store setup into multi-store system

    Args:
        database_url: Database URL
        user_email: User email
        user_name: User full name
        shopify_credentials: Dict with Shopify credentials
        store_name: Store display name

    Returns:
        tuple: (user, store)
    """
    session = get_multi_store_session(database_url)

    try:
        # Check if user exists
        user = session.query(User).filter(User.email == user_email).first()

        if not user:
            # Create new user
            user = User(
                email=user_email,
                name=user_name,
                subscription_tier=SubscriptionTier.SOAR,
                ai_preference=AIProvider.CLAUDE
            )
            session.add(user)
            session.flush()  # Get user ID

            # Create default settings
            settings = UserSettings(user_id=user.id)
            session.add(settings)

        # Create Shopify store
        store = Store(
            user_id=user.id,
            store_name=store_name,
            store_url=shopify_credentials.get("shop_url", ""),
            platform=Platform.SHOPIFY,
            credentials=shopify_credentials,
            is_active=True
        )
        session.add(store)

        # Update user counts
        user.total_stores += 1

        session.commit()

        print(f"✅ Migration complete!")
        print(f"   User: {user.email} (ID: {user.id})")
        print(f"   Store: {store.store_name} (ID: {store.id})")

        return user, store

    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        session.close()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_user_monthly_ai_usage(session: Session, user_id: int) -> float:
    """Get user's AI spending for current month"""
    from datetime import datetime
    from sqlalchemy import func

    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_cost = session.query(func.sum(AIUsage.estimated_cost))\
        .filter(AIUsage.user_id == user_id)\
        .filter(AIUsage.created_at >= start_of_month)\
        .scalar()

    return total_cost or 0.0


def get_store_performance(session: Session, store_id: int) -> dict:
    """Get comprehensive store performance metrics"""
    store = session.query(Store).filter(Store.id == store_id).first()

    if not store:
        return {}

    # Count products by status
    from sqlalchemy import func

    product_counts = session.query(
        Product.status,
        func.count(Product.id)
    ).filter(Product.store_id == store_id)\
     .group_by(Product.status)\
     .all()

    return {
        "store_id": store.id,
        "store_name": store.store_name,
        "platform": store.platform,
        "total_revenue": store.total_revenue,
        "monthly_revenue": store.monthly_revenue,
        "conversion_rate": store.conversion_rate,
        "product_counts": dict(product_counts),
        "last_sync": store.last_sync.isoformat() if store.last_sync else None
    }


if __name__ == "__main__":
    # Demo usage
    print("🔧 Initializing Multi-Store Database...")
    engine = init_multi_store_db()

    print("\n📊 Database Schema:")
    for table_name in Base.metadata.tables.keys():
        print(f"   • {table_name}")

    print("\n✅ Ready for multi-store, multi-platform e-commerce!")

# ═══════════════════════════════════════════════════════
# INTELLIGENCE LAYER - YOUR COMPETITIVE MOAT
# ═══════════════════════════════════════════════════════

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
# DATABASE SESSION MANAGEMENT
# ============================================================================

# Database URL (from environment or default to SQLite)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ospra_os.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Database session dependency for FastAPI.

    Usage in FastAPI routes:
        @router.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db session here
            pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database (create all tables)"""
    Base.metadata.create_all(bind=engine)
