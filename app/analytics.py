"""Analytics and metrics tracking for email automation."""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json

Base = declarative_base()


class EmailMetric(Base):
    """Track email processing metrics."""
    __tablename__ = "email_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Email info
    message_id = Column(String)
    customer_email = Column(String)
    subject = Column(String)
    label = Column(String)  # Support, Tracking, etc.

    # Processing info
    response_mode = Column(String)  # "ai" or "template"
    ai_provider = Column(String)  # "Claude", "OpenAI", etc.

    # Timing
    processing_time_ms = Column(Float)  # How long to process

    # AI usage
    tokens_used = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)

    # Actions taken
    auto_reply_sent = Column(Boolean, default=False)
    auto_refund_processed = Column(Boolean, default=False)
    shopify_lookup = Column(Boolean, default=False)
    followup_needed = Column(Boolean, default=False)

    # Results
    success = Column(Boolean, default=True)
    error_message = Column(Text)


class DailyStats(Base):
    """Aggregate daily statistics."""
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, unique=True)

    total_emails = Column(Integer, default=0)
    auto_replies = Column(Integer, default=0)
    ai_responses = Column(Integer, default=0)
    template_responses = Column(Integer, default=0)

    auto_refunds = Column(Integer, default=0)
    auto_refund_amount = Column(Float, default=0.0)

    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)

    avg_response_time_ms = Column(Float, default=0.0)

    errors = Column(Integer, default=0)


class Analytics:
    """Analytics tracking and reporting."""

    def __init__(self, database_url: str):
        sync_url = database_url.replace("+aiosqlite", "")
        self.engine = create_engine(sync_url, echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def track_email(
        self,
        message_id: str,
        customer_email: str,
        subject: str,
        label: str,
        response_mode: str,
        ai_provider: str = None,
        processing_time_ms: float = 0,
        tokens_used: int = 0,
        estimated_cost: float = 0.0,
        auto_reply_sent: bool = False,
        auto_refund_processed: bool = False,
        shopify_lookup: bool = False,
        followup_needed: bool = False,
        success: bool = True,
        error_message: str = None,
    ):
        """Track individual email processing."""
        metric = EmailMetric(
            timestamp=datetime.utcnow(),
            message_id=message_id,
            customer_email=customer_email,
            subject=subject,
            label=label,
            response_mode=response_mode,
            ai_provider=ai_provider,
            processing_time_ms=processing_time_ms,
            tokens_used=tokens_used,
            estimated_cost=estimated_cost,
            auto_reply_sent=auto_reply_sent,
            auto_refund_processed=auto_refund_processed,
            shopify_lookup=shopify_lookup,
            followup_needed=followup_needed,
            success=success,
            error_message=error_message,
        )
        self.session.add(metric)
        self.session.commit()

    def get_daily_stats(self, date: datetime = None) -> Dict[str, Any]:
        """Get statistics for a specific day."""
        if date is None:
            date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        next_day = date + timedelta(days=1)

        metrics = self.session.query(EmailMetric).filter(
            EmailMetric.timestamp >= date,
            EmailMetric.timestamp < next_day
        ).all()

        total_emails = len(metrics)
        auto_replies = sum(1 for m in metrics if m.auto_reply_sent)
        ai_responses = sum(1 for m in metrics if m.response_mode == "ai")
        template_responses = sum(1 for m in metrics if m.response_mode == "template")

        auto_refunds = sum(1 for m in metrics if m.auto_refund_processed)

        total_tokens = sum(m.tokens_used for m in metrics)
        total_cost = sum(m.estimated_cost for m in metrics)

        processing_times = [m.processing_time_ms for m in metrics if m.processing_time_ms > 0]
        avg_response_time = sum(processing_times) / len(processing_times) if processing_times else 0

        errors = sum(1 for m in metrics if not m.success)

        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_emails": total_emails,
            "auto_replies": auto_replies,
            "ai_responses": ai_responses,
            "template_responses": template_responses,
            "auto_refunds": auto_refunds,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4),
            "avg_response_time_ms": round(avg_response_time, 2),
            "errors": errors,
            "success_rate": round((total_emails - errors) / total_emails * 100, 2) if total_emails > 0 else 100,
        }

    def get_weekly_stats(self) -> List[Dict[str, Any]]:
        """Get last 7 days of statistics."""
        stats = []
        for i in range(7):
            date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
            stats.append(self.get_daily_stats(date))
        return list(reversed(stats))

    def get_top_labels(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get most common email categories."""
        start_date = datetime.utcnow() - timedelta(days=days)

        metrics = self.session.query(EmailMetric).filter(
            EmailMetric.timestamp >= start_date
        ).all()

        label_counts = {}
        for m in metrics:
            label_counts[m.label] = label_counts.get(m.label, 0) + 1

        return [
            {"label": label, "count": count}
            for label, count in sorted(label_counts.items(), key=lambda x: x[1], reverse=True)
        ]

    def get_cost_breakdown(self, days: int = 30) -> Dict[str, Any]:
        """Get AI cost breakdown."""
        start_date = datetime.utcnow() - timedelta(days=days)

        metrics = self.session.query(EmailMetric).filter(
            EmailMetric.timestamp >= start_date,
            EmailMetric.response_mode == "ai"
        ).all()

        claude_cost = sum(m.estimated_cost for m in metrics if m.ai_provider == "Claude 3.5 Sonnet")
        openai_cost = sum(m.estimated_cost for m in metrics if m.ai_provider == "OpenAI GPT-4o-mini")

        total_cost = claude_cost + openai_cost

        return {
            "period_days": days,
            "total_cost": round(total_cost, 4),
            "claude_cost": round(claude_cost, 4),
            "openai_cost": round(openai_cost, 4),
            "total_ai_responses": len(metrics),
            "avg_cost_per_email": round(total_cost / len(metrics), 6) if metrics else 0,
        }


def init_analytics_db(database_url: str):
    """Initialize analytics database."""
    sync_url = database_url.replace("+aiosqlite", "")
    engine = create_engine(sync_url, echo=False)
    Base.metadata.create_all(engine)
    print("✅ Analytics database initialized")


def get_analytics_summary(database_url: str) -> Dict[str, Any]:
    """
    Get summary analytics for dashboard display.

    Args:
        database_url: SQLAlchemy database URL

    Returns:
        Dict with total_processed, total_replied, labels_applied
    """
    try:
        tracker = AnalyticsTracker(database_url)

        # Get all-time stats
        metrics = tracker.session.query(EmailMetric).all()

        total_processed = len(metrics)
        total_replied = sum(1 for m in metrics if m.auto_reply_sent)

        # Count labels
        labels_applied = {}
        for m in metrics:
            if m.label:
                labels_applied[m.label] = labels_applied.get(m.label, 0) + 1

        return {
            "total_processed": total_processed,
            "total_replied": total_replied,
            "labels_applied": labels_applied
        }
    except Exception as e:
        return {
            "total_processed": 0,
            "total_replied": 0,
            "labels_applied": {},
            "error": str(e)
        }
