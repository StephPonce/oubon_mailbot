"""
User Models for OspraOS
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


class User(Base):
    """Multi-tenant user with subscription and AI preferences"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # Tenant branding (used in AI prompts, email signatures, FAQ templates)
    # Nullable - callers fall back to the platform default ("Oubon Shop" /
    # "a premium smart home and lifestyle store") when these are not set.
    # See ospra_os/tenancy/brand.py for the read-path helpers.
    brand_name = Column(String(255), nullable=True)
    brand_descriptor = Column(String(500), nullable=True)

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

class UserProductRecommendation(Base):
    """Track which products were recommended to which users"""
    __tablename__ = "user_product_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False, index=True)
    product_saturation_id = Column(Integer, ForeignKey('product_saturation.id', ondelete="CASCADE"), nullable=False, index=True)

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

class UserSettings(Base):
    """User preferences and automation settings"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

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
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False, index=True)

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


# ============================================================================
# PASSWORD RESET TOKEN MODEL
# ============================================================================

class PasswordResetToken(Base):
    """
    Password reset tokens for secure password recovery.

    Stores tokens in database instead of memory to persist across server restarts.
    Tokens expire after 1 hour for security.
    """
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    used = Column(Boolean, default=False, nullable=False)  # Track if token was used

    def __repr__(self):
        return f"<PasswordResetToken(email='{self.email}', expires={self.expires_at}, used={self.used})>"

    @property
    def is_expired(self) -> bool:
        """Check if token has expired"""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not used)"""
        return not self.is_expired and not self.used
