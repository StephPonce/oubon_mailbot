"""
Learning Summary Database Models
=================================

Pre-computed summary tables for scalable Claude context.
These tables compress unlimited raw learning_events into token-efficient summaries.
"""

from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

from ospra_os.learning.hybrid_learning_engine import Base


class LearningSummary(Base):
    """
    Daily pre-computed summaries for each user.

    This is the PRIMARY source for Claude's context - not raw learning_events.
    Updated nightly via background job.

    ~800-1000 tokens per summary (vs 10,000+ tokens for raw data)
    """
    __tablename__ = "learning_summaries"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    summary_date = Column(DateTime, default=datetime.utcnow, index=True)

    # Overall performance (JSON for flexibility)
    overall_performance = Column(JSON, nullable=False)
    # Example: {
    #     "total_revenue": 12450.50,
    #     "total_products_deployed": 45,
    #     "avg_revenue_per_product": 276.68,
    #     "best_month": "2024-11",
    #     "total_sales": 156
    # }

    # Niche insights
    niche_insights = Column(JSON, nullable=False)
    # Example: {
    #     "smart_home": {"revenue": 8500, "success_rate": 0.78, "avg_price": 45.99},
    #     "fitness": {"revenue": 3200, "success_rate": 0.65, "avg_price": 29.99}
    # }

    # Top/bottom performers
    top_products = Column(JSON, nullable=False)
    # Array of top 10 products by revenue

    underperformers = Column(JSON, nullable=False)
    # Array of products with negative ROI or low conversion

    # Price analysis
    price_insights = Column(JSON, nullable=False)
    # Example: {
    #     "optimal_range": "$25-45",
    #     "conversion_by_bracket": {"0-20": 0.45, "20-40": 0.68, "40-60": 0.72}
    # }

    # Ad insights
    ad_insights = Column(JSON, nullable=False)
    # Example: {
    #     "best_platform": "TikTok",
    #     "avg_roas": 2.3,
    #     "optimal_daily_spend": "$25-50",
    #     "platform_comparison": {"facebook": 1.8, "tiktok": 3.2, "google": 2.1}
    # }

    # AI-generated recommendations (TEXT - readable by Claude)
    recommendations = Column(Text, nullable=False)
    # Example multi-line string:
    # """
    # 1. Increase smart_home inventory - 78% success rate vs 45% platform avg
    # 2. Avoid kitchen products - 23% return rate, below breakeven
    # 3. TikTok ads outperform Meta 2:1 - shift 60% of budget
    # 4. Products priced $25-45 convert 2.3x better than <$20
    # """

    # Token count estimate (for budget tracking)
    estimated_tokens = Column(Integer, default=800)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_user_date', 'user_id', 'summary_date'),
    )


class NichePerformance(Base):
    """
    Aggregated performance stats per niche per user.
    Updated in realtime as events come in.
    """
    __tablename__ = "niche_performance"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    niche = Column(String(50), nullable=False, index=True)

    # Aggregated metrics
    total_revenue = Column(Float, default=0.0)
    total_units_sold = Column(Integer, default=0)
    total_products = Column(Integer, default=0)  # unique products in this niche
    avg_price = Column(Float, default=0.0)
    success_rate = Column(Float, default=0.0)  # % of products profitable

    # Ad metrics (if available)
    total_ad_spend = Column(Float, default=0.0)
    total_ad_revenue = Column(Float, default=0.0)
    avg_roas = Column(Float, default=0.0)

    # Timeframe
    last_sale_date = Column(DateTime)
    first_sale_date = Column(DateTime)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_user_niche', 'user_id', 'niche'),
    )


class ProductPerformance(Base):
    """
    Lifetime stats for each product.
    Allows quick lookup of any product's history.
    """
    __tablename__ = "product_performance"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    product_id = Column(String(100), nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    niche = Column(String(50), index=True)

    # Lifetime metrics
    total_revenue = Column(Float, default=0.0)
    total_units_sold = Column(Integer, default=0)
    total_ad_spend = Column(Float, default=0.0)
    total_ad_revenue = Column(Float, default=0.0)
    roas = Column(Float, default=0.0)

    # Product details
    avg_price = Column(Float, default=0.0)
    deploy_date = Column(DateTime)
    last_sale_date = Column(DateTime)

    # Performance flags
    is_profitable = Column(Integer, default=1)  # Boolean: 1=profitable, 0=unprofitable
    roi_percentage = Column(Float, default=0.0)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_user_product', 'user_id', 'product_id'),
        Index('idx_niche_profitable', 'niche', 'is_profitable'),
    )


class TimeSeriesMetrics(Base):
    """
    Weekly/monthly rollups for trend analysis.
    Allows "how did I perform last month?" queries without scanning all events.
    """
    __tablename__ = "time_series_metrics"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    period_type = Column(String(10), nullable=False)  # 'week' or 'month'
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)

    # Aggregated metrics for this period
    total_revenue = Column(Float, default=0.0)
    total_units_sold = Column(Integer, default=0)
    total_products_deployed = Column(Integer, default=0)
    total_ad_spend = Column(Float, default=0.0)
    total_ad_revenue = Column(Float, default=0.0)
    avg_roas = Column(Float, default=0.0)

    # Top niche this period
    top_niche = Column(String(50))
    top_niche_revenue = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_user_period', 'user_id', 'period_type', 'period_start'),
    )
