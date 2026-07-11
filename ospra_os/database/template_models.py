"""
Template Vault - GROK RECOMMENDATION #12

Database models for action template marketplace where users can:
- Create reusable action sequences
- Share/sell templates to other users
- Browse and purchase templates
- Track usage and performance
"""

from sqlalchemy import Column, Integer, String, Float, Text, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

# T161: shared metadata — was its own declarative_base(), so action_templates /
# template_purchases / template_usages / template_reviews were missing from the
# startup create_all() and wouldn't exist on a fresh DB.
from ospra_os.database.base import Base


class TemplateStatus(str, enum.Enum):
    """Template publication status"""
    DRAFT = "draft"
    REVIEW = "review"  # Pending approval
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class TemplateCategory(str, enum.Enum):
    """Template categories"""
    PRICING = "pricing"
    LAUNCH = "launch"
    PROMOTION = "promotion"
    SEASONAL = "seasonal"
    ADVERTISING = "advertising"
    INVENTORY = "inventory"
    EMAIL = "email"
    GROWTH = "growth"
    RECOVERY = "recovery"  # Cart abandonment, win-back
    OTHER = "other"


class ActionTemplate(Base):
    """
    A reusable template of actions/strategies.

    Example: "Black Friday pricing strategy that generated $50K"
    """
    __tablename__ = "action_templates"

    id = Column(Integer, primary_key=True, index=True)

    # Ownership (no FK constraint - cross-database reference)
    creator_id = Column(Integer, nullable=False, index=True)

    # Basic Info
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    short_description = Column(String(500), nullable=True)

    # Categorization
    category = Column(String(50), default="other", index=True)
    tags = Column(JSON, default=list)  # ["black_friday", "high_volume", "fitness"]
    niches = Column(JSON, default=list)  # Applicable niches

    # Template Content
    actions = Column(JSON, nullable=False)
    # Format:
    # [
    #   {
    #     "order": 1,
    #     "type": "adjust_price",
    #     "name": "Initial discount",
    #     "description": "Start with 15% off",
    #     "config": {
    #       "discount_percent": 15,
    #       "apply_to": "all_products"
    #     },
    #     "delay_hours": 0,
    #     "conditions": []
    #   }
    # ]

    # Variables that user must fill in
    variables = Column(JSON, default=list)
    # Format:
    # [
    #   {"name": "discount_percent", "type": "number", "default": 15, "min": 5, "max": 50},
    #   {"name": "ad_budget_daily", "type": "number", "default": 50},
    #   {"name": "target_products", "type": "product_select", "multi": true}
    # ]

    # Requirements
    requirements = Column(JSON, default=dict)
    # Format:
    # {
    #   "min_products": 5,
    #   "integrations": ["shopify", "meta_ads"],
    #   "subscription_tier": "flight"
    # }

    # Metadata
    version = Column(String(20), default="1.0.0")
    changelog = Column(JSON, default=list)

    # Status
    status = Column(String(20), default="draft", index=True)
    rejection_reason = Column(Text, nullable=True)

    # Pricing
    is_free = Column(Boolean, default=True, index=True)
    price = Column(Float, default=0)  # USD
    revenue_share = Column(Float, default=0.7)  # Creator gets 70%

    # Stats
    uses_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0)  # Based on outcomes
    avg_revenue_generated = Column(Float, default=0)

    # Ratings
    avg_rating = Column(Float, default=0)
    ratings_count = Column(Integer, default=0)

    # Visibility
    is_featured = Column(Boolean, default=False, index=True)
    featured_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[creator_id])
    purchases = relationship("TemplatePurchase", back_populates="template", cascade="all, delete-orphan")
    reviews = relationship("TemplateReview", back_populates="template", cascade="all, delete-orphan")
    usages = relationship("TemplateUsage", back_populates="template", cascade="all, delete-orphan")


class TemplatePurchase(Base):
    """Record of template purchases"""
    __tablename__ = "template_purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    template_id = Column(Integer, nullable=False, index=True)

    # Transaction
    price_paid = Column(Float, default=0)
    currency = Column(String(3), default="USD")
    payment_provider = Column(String(50), nullable=True)  # stripe, lemonsqueezy
    transaction_id = Column(String(255), nullable=True, unique=True)

    # Revenue split
    creator_amount = Column(Float, default=0)
    platform_amount = Column(Float, default=0)

    # Status
    status = Column(String(20), default="completed", index=True)  # pending, completed, refunded

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    template = relationship("ActionTemplate", back_populates="purchases")


class TemplateUsage(Base):
    """Tracking when templates are used"""
    __tablename__ = "template_usages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    template_id = Column(Integer, nullable=False, index=True)
    store_id = Column(Integer, nullable=False)

    # Configuration used
    variables_used = Column(JSON, default=dict)

    # Outcome tracking
    status = Column(String(20), default="active", index=True)  # active, completed, cancelled
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Results
    actions_executed = Column(Integer, default=0)
    actions_total = Column(Integer, default=0)

    # Performance metrics
    revenue_before = Column(Float, default=0)
    revenue_after = Column(Float, default=0)
    revenue_attributed = Column(Float, default=0)
    orders_attributed = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    template = relationship("ActionTemplate", back_populates="usages")
    store = relationship("Store", foreign_keys=[store_id])
    review = relationship("TemplateReview", back_populates="usage", uselist=False)


class TemplateReview(Base):
    """User reviews of templates"""
    __tablename__ = "template_reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    template_id = Column(Integer, nullable=False, index=True)
    usage_id = Column(Integer, nullable=True)

    # Review content
    rating = Column(Integer, nullable=False)  # 1-5
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)

    # Verified purchase
    is_verified = Column(Boolean, default=False)

    # Results shared
    revenue_reported = Column(Float, nullable=True)

    # Moderation
    is_approved = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    template = relationship("ActionTemplate", back_populates="reviews")
    usage = relationship("TemplateUsage", back_populates="review")


# Export enums
__all__ = [
    "ActionTemplate",
    "TemplatePurchase",
    "TemplateUsage",
    "TemplateReview",
    "TemplateStatus",
    "TemplateCategory",
]
