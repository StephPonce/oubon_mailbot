"""
Email Analytics API Routes

FastAPI endpoints for email automation metrics and dashboard statistics.
"""

from fastapi import APIRouter, Depends, Query
from ospra_os.auth.jwt_auth import get_current_user
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from ospra_os.analytics.email_analytics import Analytics, EmailMetric
from ospra_os.core.settings import Settings

# SECURITY (2026-08): router-level auth. /api/emails/recent returned
# customer_email + subject for ALL tenants with no auth and no tenant filter
# (live: 200). EmailMetric has no user_id column, so this gate is a stopgap —
# real isolation needs a migration adding user_id + backfill + filtering.
router = APIRouter(
    prefix="/api",
    tags=["Email Analytics"],
    dependencies=[Depends(get_current_user)],
)

# Initialize settings
settings = Settings()


@router.get("/dashboard/emails")
async def get_email_dashboard_stats():
    """
    Get email dashboard statistics for today and this week.

    Returns:
        {
            "summary": {
                "processed_today": int,
                "processed_week": int,
                "auto_replied_today": int
            },
            "response_rate": float
        }
    """
    analytics = Analytics(settings.database_url)

    # Get today's stats
    today_stats = analytics.get_daily_stats()

    # Get weekly stats
    weekly_stats = analytics.get_weekly_stats()
    total_week = sum(day["total_emails"] for day in weekly_stats)
    total_auto_replies_week = sum(day["auto_replies"] for day in weekly_stats)

    # Calculate response rate (% of emails that got auto-reply)
    response_rate = (total_auto_replies_week / total_week * 100) if total_week > 0 else 0.0

    return {
        "summary": {
            "processed_today": today_stats["total_emails"],
            "processed_week": total_week,
            "auto_replied_today": today_stats["auto_replies"]
        },
        "response_rate": round(response_rate, 1)
    }


@router.get("/emails/recent")
async def get_recent_emails(
    limit: int = Query(20, le=100),
    current_user=Depends(get_current_user),
):
    """
    Get recent processed emails.

    Args:
        limit: Maximum number of emails to return (max 100)

    Returns:
        {
            "emails": [
                {
                    "from": str,
                    "subject": str,
                    "category": str,
                    "date": str,
                    "auto_replied": bool,
                    "response_mode": str,
                    "processing_time_ms": float
                }
            ],
            "total": int
        }
    """
    analytics = Analytics(settings.database_url)

    # Query recent emails from database
    session = analytics.session
    # TENANT SCOPING (2026-08). This query had no filter at all, so it returned
    # every tenant's customer_email + subject. Router-level auth narrowed the
    # audience to logged-in users; this narrows it to the CALLER'S OWN rows.
    # Rows predating migration 010 have user_id NULL — they are UNOWNED and
    # deliberately never served, rather than attributing them to whoever asks.
    recent_metrics = (
        session.query(EmailMetric)
        .filter(EmailMetric.user_id == current_user.id)
        .order_by(EmailMetric.timestamp.desc())
        .limit(limit)
        .all()
    )

    emails = []
    for metric in recent_metrics:
        emails.append({
            "from": metric.customer_email,
            "subject": metric.subject,
            "category": metric.label or "Uncategorized",
            "date": metric.timestamp.isoformat(),
            "auto_replied": metric.auto_reply_sent,
            "response_mode": metric.response_mode,
            "processing_time_ms": metric.processing_time_ms or 0,
            "success": metric.success
        })

    return {
        "emails": emails,
        "total": len(emails)
    }


@router.get("/emails/stats/weekly")
async def get_weekly_email_stats():
    """
    Get detailed statistics for the last 7 days.

    Returns:
        List of daily statistics with breakdowns
    """
    analytics = Analytics(settings.database_url)
    return analytics.get_weekly_stats()


@router.get("/emails/stats/categories")
async def get_email_categories(days: int = Query(7, le=90)):
    """
    Get email distribution by category/label.

    Args:
        days: Number of days to analyze (max 90)

    Returns:
        List of categories with counts
    """
    analytics = Analytics(settings.database_url)
    return analytics.get_top_labels(days=days)


@router.get("/emails/stats/costs")
async def get_ai_costs(days: int = Query(30, le=90)):
    """
    Get AI usage and cost breakdown.

    Args:
        days: Number of days to analyze (max 90)

    Returns:
        Cost breakdown by AI provider
    """
    analytics = Analytics(settings.database_url)
    return analytics.get_cost_breakdown(days=days)


@router.get("/emails/stats/performance")
async def get_performance_metrics():
    """
    Get email processing performance metrics.

    Returns:
        {
            "avg_response_time_ms": float,
            "success_rate": float,
            "ai_vs_template": {
                "ai_count": int,
                "template_count": int
            }
        }
    """
    analytics = Analytics(settings.database_url)

    # Get last 7 days for performance metrics
    start_date = datetime.now(timezone.utc) - timedelta(days=7)
    session = analytics.session

    recent_metrics = session.query(EmailMetric).filter(
        EmailMetric.timestamp >= start_date
    ).all()

    if not recent_metrics:
        return {
            "avg_response_time_ms": 0,
            "success_rate": 100,
            "ai_vs_template": {
                "ai_count": 0,
                "template_count": 0
            }
        }

    # Calculate metrics
    processing_times = [m.processing_time_ms for m in recent_metrics if m.processing_time_ms > 0]
    avg_response_time = sum(processing_times) / len(processing_times) if processing_times else 0

    total = len(recent_metrics)
    successful = sum(1 for m in recent_metrics if m.success)
    success_rate = (successful / total * 100) if total > 0 else 100

    ai_count = sum(1 for m in recent_metrics if m.response_mode == "ai")
    template_count = sum(1 for m in recent_metrics if m.response_mode == "template")

    return {
        "avg_response_time_ms": round(avg_response_time, 2),
        "success_rate": round(success_rate, 2),
        "ai_vs_template": {
            "ai_count": ai_count,
            "template_count": template_count
        }
    }
