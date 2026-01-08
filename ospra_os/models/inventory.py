"""
Inventory Models - Database schemas for inventory forecasting and management

Tables:
- inventory_levels: Current inventory status per product
- inventory_snapshots: Daily snapshots for trending
- restock_orders: Track restock orders
- stockout_events: Track stockout incidents
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, JSON, Boolean, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class InventoryLevel(Base):
    """Current inventory status per product with forecasts"""
    __tablename__ = "inventory_levels"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(100), unique=True, index=True, nullable=False)
    shopify_product_id = Column(String(100), index=True)
    store_id = Column(String(100), index=True)
    sku = Column(String(100), index=True)
    product_name = Column(String(255))

    # Stock levels
    current_stock = Column(Integer, default=0)
    reserved = Column(Integer, default=0)
    available = Column(Integer, default=0)
    incoming_stock = Column(Integer, default=0)  # Stock on order

    # Velocity metrics
    daily_velocity = Column(Float)
    weekly_velocity = Column(Float)
    monthly_velocity = Column(Float)
    velocity_trend = Column(String(20))  # increasing, stable, decreasing
    velocity_trend_percentage = Column(Float)
    velocity_confidence = Column(Float)  # 0-1
    velocity_std_deviation = Column(Float)

    # Forecasts
    days_of_stock = Column(Float)
    stockout_date = Column(Date)
    units_needed_30d = Column(Integer)
    units_needed_60d = Column(Integer)
    units_needed_90d = Column(Integer)

    # Reorder calculations
    reorder_point = Column(Integer)
    should_reorder = Column(Boolean, default=False)
    reorder_urgency = Column(String(20))  # NORMAL, SOON, URGENT, CRITICAL
    recommended_quantity = Column(Integer)
    recommended_order_date = Column(Date)

    # Safety stock
    safety_stock = Column(Integer)
    safety_stock_days = Column(Float)
    service_level = Column(Float, default=0.95)

    # Status
    status = Column(String(20), index=True)  # HEALTHY, LOW, CRITICAL, OUT_OF_STOCK
    stockout_risk = Column(Float)  # 0-1
    risk_level = Column(String(20))  # LOW, MEDIUM, HIGH, CRITICAL

    # Supplier information
    supplier_id = Column(String(100))
    supplier_name = Column(String(255))
    supplier_product_id = Column(String(100))
    lead_time_days = Column(Integer)
    min_order_quantity = Column(Integer)
    current_unit_cost = Column(Float)
    price_trend = Column(String(20))  # stable, increasing, decreasing

    # Seasonality
    is_seasonal = Column(Boolean, default=False)
    seasonal_pattern = Column(JSON)  # Monthly indices
    peak_months = Column(JSON)  # List of peak months
    seasonal_adjustment_factor = Column(Float, default=1.0)

    # History
    stockouts_last_90d = Column(Integer, default=0)
    avg_days_to_restock = Column(Float)
    last_restock_date = Column(Date)
    last_restock_quantity = Column(Integer)
    last_stockout_date = Column(Date)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    forecast_updated_at = Column(DateTime)

    # Indexes for performance
    __table_args__ = (
        Index('idx_inventory_status_risk', 'status', 'stockout_risk'),
        Index('idx_inventory_reorder', 'should_reorder', 'reorder_urgency'),
        Index('idx_inventory_store_status', 'store_id', 'status'),
    )


class InventorySnapshot(Base):
    """Daily inventory snapshot for trending and velocity calculation"""
    __tablename__ = "inventory_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(100), index=True, nullable=False)
    snapshot_date = Column(Date, index=True, nullable=False)

    # Stock snapshot
    stock_level = Column(Integer)
    reserved = Column(Integer)
    available = Column(Integer)

    # Sales snapshot
    units_sold = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    orders_count = Column(Integer, default=0)

    # Velocity snapshot
    daily_velocity = Column(Float)
    velocity_trend = Column(String(20))

    # Status snapshot
    status = Column(String(20))
    days_of_stock = Column(Float)
    stockout_risk = Column(Float)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Composite index for efficient queries
    __table_args__ = (
        Index('idx_snapshot_product_date', 'product_id', 'snapshot_date'),
    )


class RestockOrder(Base):
    """Track restock orders and their status"""
    __tablename__ = "restock_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(100), unique=True, index=True, nullable=False)
    product_id = Column(String(100), index=True, nullable=False)
    store_id = Column(String(100), index=True)

    # Product details
    product_name = Column(String(255))
    sku = Column(String(100))

    # Order details
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Float)
    shipping_cost = Column(Float, default=0.0)
    total_cost = Column(Float)

    # Supplier
    supplier_id = Column(String(100))
    supplier_name = Column(String(255))
    supplier_order_id = Column(String(100))

    # Dates
    order_date = Column(Date, nullable=False)
    expected_arrival = Column(Date)
    actual_arrival = Column(Date)
    lead_time_days = Column(Integer)
    actual_lead_time_days = Column(Integer)

    # Status
    status = Column(String(20), index=True, nullable=False)  # PENDING, ORDERED, SHIPPED, ARRIVED, CANCELLED
    tracking_number = Column(String(100))
    carrier = Column(String(100))

    # Notes
    notes = Column(Text)
    urgency = Column(String(20))  # NORMAL, URGENT, CRITICAL
    reason = Column(String(255))  # Why was this order placed?

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    shipped_at = Column(DateTime)
    arrived_at = Column(DateTime)

    # Indexes
    __table_args__ = (
        Index('idx_restock_status_date', 'status', 'expected_arrival'),
        Index('idx_restock_product_status', 'product_id', 'status'),
    )


class StockoutEvent(Base):
    """Track stockout incidents and their impact"""
    __tablename__ = "stockout_events"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(100), index=True, nullable=False)
    store_id = Column(String(100), index=True)

    # Product details
    product_name = Column(String(255))
    sku = Column(String(100))

    # Stockout timeline
    stockout_start = Column(DateTime, nullable=False)
    stockout_end = Column(DateTime)
    duration_hours = Column(Float)
    is_resolved = Column(Boolean, default=False)

    # Impact metrics
    estimated_lost_units = Column(Integer, default=0)
    estimated_lost_revenue = Column(Float, default=0.0)
    missed_orders = Column(Integer, default=0)

    # Analysis
    cause = Column(String(100))  # supplier_delay, demand_surge, planning_error, etc.
    root_cause = Column(Text)
    prevention_notes = Column(Text)

    # Context
    stock_before = Column(Integer)
    daily_velocity_before = Column(Float)
    warning_issued = Column(Boolean, default=False)
    warning_issued_at = Column(DateTime)

    # Notes
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime)

    # Indexes
    __table_args__ = (
        Index('idx_stockout_product_date', 'product_id', 'stockout_start'),
        Index('idx_stockout_resolved', 'is_resolved', 'stockout_start'),
    )


# Initialize database tables
def init_inventory_tables(engine):
    """Create all inventory tables"""
    Base.metadata.create_all(bind=engine)
    print("[SUCCESS] Inventory tables created")
    print("   - inventory_levels")
    print("   - inventory_snapshots")
    print("   - restock_orders")
    print("   - stockout_events")
