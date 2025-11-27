"""
Competitor Intelligence Models - Database schemas for competitive tracking

Tables:
- competitors: Tracked competitor stores
- competitor_products: Products from competitor stores
- competitor_price_history: Historical price tracking
- competitor_activity: Activity log for competitor changes
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, JSON, Boolean, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Competitor(Base):
    """Tracked competitors with analysis and metrics"""
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(String(100), unique=True, index=True, nullable=False)

    # Basic info
    name = Column(String(255), nullable=False)
    store_url = Column(String(500), nullable=False)
    platform = Column(String(50))  # shopify, amazon, woocommerce, custom
    status = Column(String(20), default="ACTIVE")  # ACTIVE, PAUSED, REMOVED

    # Classification
    competitor_type = Column(String(50))  # DIRECT, INDIRECT, MARKET_LEADER, EMERGING
    threat_level = Column(String(20))  # HIGH, MEDIUM, LOW
    priority = Column(Integer, default=5)  # 1-10 scale

    # Estimates
    estimated_revenue = Column(Float)  # Monthly revenue estimate
    estimated_product_count = Column(Integer)
    estimated_daily_orders = Column(Integer)
    price_positioning = Column(String(20))  # BUDGET, MID_MARKET, PREMIUM
    founded_estimate = Column(String(20))  # Year estimate

    # Analysis
    primary_niches = Column(JSON)  # List of niche strings
    strengths = Column(JSON)  # List of strength descriptions
    weaknesses = Column(JSON)  # List of weakness descriptions
    opportunities = Column(JSON)  # List of opportunity descriptions
    threats = Column(JSON)  # List of threat descriptions

    # Product metrics
    total_tracked_products = Column(Integer, default=0)
    overlapping_products = Column(Integer, default=0)  # Products we both sell
    unique_products = Column(Integer, default=0)  # Products only they have
    avg_product_price = Column(Float)
    min_product_price = Column(Float)
    max_product_price = Column(Float)

    # Pricing analysis
    price_vs_ours = Column(String(20))  # LOWER, SIMILAR, HIGHER
    avg_price_difference_percent = Column(Float)
    undercuts_us_on = Column(Integer, default=0)  # Count of products where they're cheaper
    we_undercut_on = Column(Integer, default=0)  # Count of products where we're cheaper

    # Marketing & social
    ad_platforms = Column(JSON)  # List: facebook, google, tiktok, instagram
    estimated_ad_spend = Column(Float)  # Monthly ad spend estimate
    primary_marketing_angles = Column(JSON)  # List of angles
    social_profiles = Column(JSON)  # {platform: url}
    social_followers = Column(JSON)  # {platform: count}

    # Tracking
    first_tracked = Column(Date, default=datetime.utcnow)
    last_scraped = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scrape_frequency = Column(String(20), default="daily")  # daily, weekly, monthly
    next_scrape_scheduled = Column(DateTime)

    # Metadata
    notes = Column(Text)
    metadata = Column(JSON)  # Additional custom data

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes for performance
    __table_args__ = (
        Index('idx_competitor_threat', 'threat_level', 'priority'),
        Index('idx_competitor_type', 'competitor_type', 'status'),
        Index('idx_competitor_scrape', 'next_scrape_scheduled'),
    )


class CompetitorProduct(Base):
    """Products from competitor stores with tracking and comparison"""
    __tablename__ = "competitor_products"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(100), unique=True, index=True, nullable=False)
    competitor_id = Column(String(100), index=True, nullable=False)

    # Product info
    name = Column(String(500))
    url = Column(String(1000))
    image_url = Column(String(1000))
    category = Column(String(200))
    sku = Column(String(200))
    handle = Column(String(300))  # Shopify handle
    description = Column(Text)
    vendor = Column(String(200))
    product_type = Column(String(200))
    tags = Column(JSON)

    # Pricing
    current_price = Column(Float)
    original_price = Column(Float)  # Compare at price
    discount_percent = Column(Float)
    currency = Column(String(10), default="USD")

    # Comparison to our products
    our_product_id = Column(String(100), index=True)  # Matched product from our catalog
    our_product_name = Column(String(500))
    our_price = Column(Float)
    price_difference = Column(Float)  # our_price - competitor_price
    price_difference_percent = Column(Float)
    we_are = Column(String(20))  # HIGHER, LOWER, SAME

    # Metrics
    reviews_count = Column(Integer, default=0)
    avg_rating = Column(Float)
    estimated_monthly_sales = Column(Integer)
    in_stock = Column(Boolean, default=True)
    inventory_quantity = Column(Integer)

    # Variants
    variants_count = Column(Integer, default=1)
    variants_data = Column(JSON)  # Full variant information

    # Tracking flags
    is_new = Column(Boolean, default=False)  # Recently added by competitor
    is_removed = Column(Boolean, default=False)  # Removed by competitor
    price_dropped = Column(Boolean, default=False)  # Recent price drop
    price_drop_percent = Column(Float)
    out_of_stock_alert = Column(Boolean, default=False)

    # Timestamps
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    last_price_change = Column(DateTime)
    last_checked = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Shopify specific
    shopify_product_id = Column(String(100))
    shopify_created_at = Column(DateTime)
    shopify_updated_at = Column(DateTime)

    # Indexes
    __table_args__ = (
        Index('idx_comp_product_competitor', 'competitor_id', 'is_removed'),
        Index('idx_comp_product_price', 'current_price'),
        Index('idx_comp_product_new', 'is_new', 'first_seen'),
        Index('idx_comp_product_match', 'our_product_id'),
        Index('idx_comp_product_alerts', 'price_dropped', 'out_of_stock_alert'),
    )


class CompetitorPriceHistory(Base):
    """Historical price data for competitor products"""
    __tablename__ = "competitor_price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(100), index=True, nullable=False)
    competitor_id = Column(String(100), index=True, nullable=False)

    # Price snapshot
    price = Column(Float, nullable=False)
    original_price = Column(Float)  # Compare at price
    discount_percent = Column(Float)
    currency = Column(String(10), default="USD")

    # Stock status at time of recording
    in_stock = Column(Boolean, default=True)

    # Timestamp
    recorded_at = Column(DateTime, index=True, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_price_history_product_date', 'product_id', 'recorded_at'),
        Index('idx_price_history_competitor_date', 'competitor_id', 'recorded_at'),
    )


class CompetitorActivity(Base):
    """Competitor activity log for tracking changes and alerts"""
    __tablename__ = "competitor_activity"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(String(100), unique=True, index=True)
    competitor_id = Column(String(100), index=True, nullable=False)

    # Activity type
    activity_type = Column(String(50), index=True, nullable=False)
    # Types: NEW_PRODUCT, PRICE_CHANGE, PRODUCT_REMOVED, OUT_OF_STOCK,
    #        BACK_IN_STOCK, NEW_AD, SOCIAL_UPDATE, REVENUE_CHANGE

    activity_date = Column(DateTime, index=True, default=datetime.utcnow, nullable=False)

    # Activity details
    title = Column(String(500))
    description = Column(Text)
    details = Column(JSON)  # Structured activity data

    # Related entities
    product_id = Column(String(100), index=True)  # Related product if applicable
    product_name = Column(String(500))

    # For price changes
    old_value = Column(String(100))
    new_value = Column(String(100))
    change_amount = Column(Float)
    change_percent = Column(Float)

    # Severity/importance
    severity = Column(String(20))  # LOW, MEDIUM, HIGH, CRITICAL
    requires_action = Column(Boolean, default=False)
    is_alert = Column(Boolean, default=False)  # Should trigger notification

    # Status
    viewed = Column(Boolean, default=False)
    dismissed = Column(Boolean, default=False)
    actioned = Column(Boolean, default=False)
    action_taken = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    viewed_at = Column(DateTime)
    actioned_at = Column(DateTime)

    # Indexes
    __table_args__ = (
        Index('idx_activity_competitor_type', 'competitor_id', 'activity_type'),
        Index('idx_activity_date_severity', 'activity_date', 'severity'),
        Index('idx_activity_alerts', 'is_alert', 'viewed'),
        Index('idx_activity_product', 'product_id'),
    )


class CompetitorProductMatch(Base):
    """Mapping between our products and competitor products"""
    __tablename__ = "competitor_product_matches"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String(100), unique=True, index=True)

    # Our product
    our_product_id = Column(String(100), index=True, nullable=False)
    our_product_name = Column(String(500))
    our_sku = Column(String(200))

    # Competitor product
    competitor_product_id = Column(String(100), index=True, nullable=False)
    competitor_id = Column(String(100), index=True, nullable=False)
    competitor_product_name = Column(String(500))

    # Match confidence
    match_confidence = Column(Float)  # 0.0 to 1.0
    match_method = Column(String(50))  # MANUAL, SKU, NAME_SIMILARITY, IMAGE_SIMILARITY

    # Match status
    status = Column(String(20), default="ACTIVE")  # ACTIVE, REJECTED, NEEDS_REVIEW
    verified = Column(Boolean, default=False)
    verified_by = Column(String(100))
    verified_at = Column(DateTime)

    # Notes
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_match_our_product', 'our_product_id'),
        Index('idx_match_competitor_product', 'competitor_product_id'),
        Index('idx_match_status', 'status', 'verified'),
    )


class CompetitorScrapeLogs(Base):
    """Log of competitor scraping attempts and results"""
    __tablename__ = "competitor_scrape_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(String(100), unique=True, index=True)
    competitor_id = Column(String(100), index=True, nullable=False)

    # Scrape info
    scrape_started_at = Column(DateTime, default=datetime.utcnow)
    scrape_completed_at = Column(DateTime)
    duration_seconds = Column(Integer)

    # Results
    status = Column(String(20))  # SUCCESS, FAILED, PARTIAL
    products_found = Column(Integer, default=0)
    products_new = Column(Integer, default=0)
    products_updated = Column(Integer, default=0)
    products_removed = Column(Integer, default=0)
    price_changes = Column(Integer, default=0)

    # Error handling
    error_message = Column(Text)
    error_details = Column(JSON)

    # Metadata
    scraper_version = Column(String(20))
    scrape_config = Column(JSON)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_scrape_log_competitor_date', 'competitor_id', 'scrape_started_at'),
        Index('idx_scrape_log_status', 'status'),
    )


# Initialize database tables
def init_competitor_tables(engine):
    """Create all competitor intelligence tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Competitor intelligence tables created")
    print("   - competitors")
    print("   - competitor_products")
    print("   - competitor_price_history")
    print("   - competitor_activity")
    print("   - competitor_product_matches")
    print("   - competitor_scrape_logs")
