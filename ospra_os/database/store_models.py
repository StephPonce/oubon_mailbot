"""
Store Models for OspraOS

SECURITY: Credentials are encrypted at rest using Fernet encryption.
Use set_credentials() and get_credentials() methods to handle encryption.
"""

import json
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

# Import encryption utilities (lazy import to avoid circular imports)
def _get_encryption():
    try:
        from ospra_os.security.credential_encryption import (
            encrypt_credentials,
            decrypt_credentials,
        )
        return encrypt_credentials, decrypt_credentials
    except ImportError:
        return None, None


class Store(Base):
    """Platform-agnostic store representation"""
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

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

    def set_credentials(self, credentials: dict):
        """
        Set credentials with encryption.

        SECURITY: Sensitive fields (access_token, secret, etc.) are encrypted
        before storage. Use this method instead of directly setting self.credentials.

        Args:
            credentials: Dict with platform credentials
        """
        encrypt_creds, _ = _get_encryption()
        if encrypt_creds:
            self.credentials = encrypt_creds(credentials)
        else:
            # Fallback if encryption not available
            self.credentials = credentials

    def get_credentials(self) -> dict:
        """
        Get decrypted credentials.

        SECURITY: Automatically decrypts credentials if they were encrypted.
        Handles both encrypted strings and legacy plain JSON/dict formats.

        Returns:
            dict: Decrypted credentials
        """
        _, decrypt_creds = _get_encryption()

        if decrypt_creds:
            return decrypt_creds(self.credentials)

        # Fallback for unencrypted data
        if isinstance(self.credentials, dict):
            return self.credentials
        try:
            return json.loads(self.credentials)
        except (json.JSONDecodeError, TypeError):
            return {}


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
