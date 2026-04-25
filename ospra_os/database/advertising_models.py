"""
Advertising Models for OspraOS
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Index, JSON, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .base import (
    Base,
    SubscriptionTier, Platform, StoreStatus, ProductStatus, DeploymentStatus,
    AIProvider, TaskType, TriggerType, ActionType, LifecycleStage,
    EntryTiming, RiskLevel
)


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

        self.last_updated = datetime.now(timezone.utc)

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
