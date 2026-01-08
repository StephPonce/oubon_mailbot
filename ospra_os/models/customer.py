"""
Customer Models - Database schemas for customer analytics

Tables:
- customers: Customer profiles with calculated metrics
- customer_snapshots: Daily snapshots for trending
- customer_events: Event tracking for analysis
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, JSON, Boolean, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Customer(Base):
    """Customer profiles with lifetime metrics and segmentation"""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), unique=True, index=True, nullable=False)
    shopify_customer_id = Column(String(100), index=True)
    store_id = Column(String(100), index=True)

    # Basic info
    email = Column(String(255), index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(50))

    # Acquisition
    acquisition_source = Column(String(100))  # facebook_ads, google_ads, organic, referral
    acquisition_campaign = Column(String(255))
    acquisition_date = Column(Date, index=True)
    acquisition_cost = Column(Float, default=0.0)

    # Calculated metrics (updated regularly)
    total_orders = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    total_profit = Column(Float, default=0.0)
    average_order_value = Column(Float, default=0.0)

    # LTV metrics
    ltv = Column(Float, default=0.0)
    predicted_ltv = Column(Float)
    ltv_percentile = Column(Integer)

    # RFM scores (1-5 scale)
    rfm_recency = Column(Integer)
    rfm_frequency = Column(Integer)
    rfm_monetary = Column(Integer)
    rfm_score = Column(Integer)  # Combined R+F+M

    # Segmentation
    segment = Column(String(50), index=True)  # CHAMPION, LOYAL, AT_RISK, etc.
    segment_tags = Column(JSON)  # Additional tags
    previous_segment = Column(String(50))  # Track segment changes

    # Behavior metrics
    last_order_date = Column(Date)
    days_since_last_order = Column(Integer)
    purchase_frequency_days = Column(Float)  # Average days between purchases
    favorite_category = Column(String(100))
    favorite_products = Column(JSON)  # List of product IDs

    # Risk & predictions
    churn_probability = Column(Float)
    risk_level = Column(String(20))  # LOW, MEDIUM, HIGH
    predicted_next_purchase = Column(Date)
    predicted_next_value = Column(Float)

    # Preferences
    preferred_payment = Column(String(50))
    average_cart_size = Column(Float)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metrics_updated_at = Column(DateTime)

    # Indexes for performance
    __table_args__ = (
        Index('idx_customer_segment_ltv', 'segment', 'ltv'),
        Index('idx_customer_risk', 'churn_probability', 'ltv'),
        Index('idx_customer_acquisition', 'acquisition_date', 'acquisition_source'),
    )


class CustomerSnapshot(Base):
    """Daily snapshot of customer metrics for trending and cohort analysis"""
    __tablename__ = "customer_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), index=True, nullable=False)
    snapshot_date = Column(Date, index=True, nullable=False)

    # Snapshot metrics
    total_orders = Column(Integer)
    total_revenue = Column(Float)
    ltv = Column(Float)
    rfm_score = Column(Integer)
    segment = Column(String(50))
    churn_probability = Column(Float)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Composite index for efficient queries
    __table_args__ = (
        Index('idx_snapshot_customer_date', 'customer_id', 'snapshot_date'),
    )


class CustomerEvent(Base):
    """Track customer events for behavior analysis"""
    __tablename__ = "customer_events"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), index=True, nullable=False)
    event_type = Column(String(50), index=True, nullable=False)  # order, email_open, site_visit, support_ticket, return
    event_date = Column(DateTime, index=True, nullable=False)
    event_data = Column(JSON)  # Additional event details

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_event_customer_type', 'customer_id', 'event_type'),
        Index('idx_event_date_type', 'event_date', 'event_type'),
    )


class CustomerCohort(Base):
    """Cohort tracking for retention analysis"""
    __tablename__ = "customer_cohorts"

    id = Column(Integer, primary_key=True, index=True)
    cohort_name = Column(String(50), index=True, nullable=False)  # 2025-08, 2025-W32, campaign_xyz
    cohort_type = Column(String(20), nullable=False)  # monthly, weekly, campaign
    cohort_date = Column(Date, nullable=False)
    customer_id = Column(String(100), index=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_cohort_name_customer', 'cohort_name', 'customer_id'),
    )


# Initialize database tables
def init_customer_tables(engine):
    """Create all customer analytics tables"""
    Base.metadata.create_all(bind=engine)
    print("[SUCCESS] Customer analytics tables created")
    print("   - customers")
    print("   - customer_snapshots")
    print("   - customer_events")
    print("   - customer_cohorts")
