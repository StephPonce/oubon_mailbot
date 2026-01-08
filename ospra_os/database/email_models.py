"""
Email Models for OspraOS
"""

import os
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Index, JSON, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Session, sessionmaker
from datetime import datetime

from .base import (
    Base,
    SubscriptionTier, Platform, StoreStatus, ProductStatus, DeploymentStatus,
    AIProvider, TaskType, TriggerType, ActionType, LifecycleStage,
    EntryTiming, RiskLevel
)
from .connection import get_engine


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

    print(f"[SUCCESS] Multi-store database initialized at: {database_url}")
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

        print(f"[SUCCESS] Migration complete!")
        print(f"   User: {user.email} (ID: {user.id})")
        print(f"   Store: {store.store_name} (ID: {store.id})")

        return user, store

    except Exception as e:
        session.rollback()
        print(f"[ERROR] Migration failed: {e}")
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
    print("[FIX] Initializing Multi-Store Database...")
    engine = init_multi_store_db()

    print("\n[STATS] Database Schema:")
    for table_name in Base.metadata.tables.keys():
        print(f"   • {table_name}")

    print("\n[SUCCESS] Ready for multi-store, multi-platform e-commerce!")

# 
# INTELLIGENCE LAYER - YOUR COMPETITIVE MOAT
# 

class EmailFollowup(Base):
    """Track emails that need AI follow-up during operating hours."""

    __tablename__ = "email_followups"

    gmail_message_id = Column(String, primary_key=True)  # Gmail message ID
    customer_email = Column(String, nullable=False)
    customer_name = Column(String)
    subject = Column(String)
    body = Column(Text)
    label = Column(String)  # Support, Tracking, Return/Refund, etc.

    needs_followup = Column(Boolean, default=False)  # True if sent template during quiet hours
    followup_sent = Column(Boolean, default=False)   # True after AI follow-up sent

    received_at = Column(DateTime, default=datetime.utcnow)
    template_sent_at = Column(DateTime)  # When template was sent
    followup_sent_at = Column(DateTime)  # When AI follow-up was sent

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<EmailFollowup {self.gmail_message_id} - {self.customer_email}>"


def get_followup_session(database_url: str):
    """Get a synchronous database session for follow-up tracking."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    sync_url = database_url.replace("+aiosqlite", "")
    engine = create_engine(sync_url, echo=False)
    Session = sessionmaker(bind=engine)
    return Session()


print("[SUCCESS] Email Automation models added")


# ============================================================================
# DATABASE SESSION MANAGEMENT
# ============================================================================

# Use centralized engine from connection module (handles PostgreSQL with psycopg2)
engine = get_engine()

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
