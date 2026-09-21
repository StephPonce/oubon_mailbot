"""
Analytics Tasks - GROK RECOMMENDATION #13

Performance monitoring, reporting, and data cleanup.

Low-priority tasks that run analytics and generate reports.

Scheduled Jobs:
- check_ad_performance: Daily at 9 AM UTC
- check_product_performance: Daily at 10 AM UTC
- cleanup_old_data: Daily at 3 AM UTC
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from ospra_os.celery_app import celery_app
from ospra_os.tasks.base import UserTask
from ospra_os.database import Product

logger = logging.getLogger(__name__)



# A campaign earning back less than this per ad dollar gets flagged for review.
LOW_ROAS_THRESHOLD = 2.0


def _fetch_campaign_metrics(campaign) -> Optional[Dict[str, Any]]:
    """Live metrics for one campaign, or None if the platform is unreachable.

    None is NOT an empty dict: "we could not ask" and "the campaign spent
    nothing" are different facts, and conflating them writes a zero over real
    spend.
    """
    import asyncio

    platform = (campaign.platform or "").lower()
    try:
        if platform == "meta":
            from ospra_os.advertising.meta.meta_ads import MetaAdsManager
            raw = asyncio.run(
                MetaAdsManager().get_campaign_metrics(campaign.campaign_id)
            )
        else:
            # TikTok/Google managers exist but expose different shapes; wiring
            # them is a separate change rather than a guess made here.
            logger.debug("No metrics adapter for platform %r", platform)
            return None
    except Exception as exc:
        logger.warning(
            "Ad metrics unreachable for %s campaign %s: %s",
            platform, campaign.campaign_id, exc,
        )
        return None

    if not raw:
        return None

    def _f(key):
        v = raw.get(key)
        try:
            return float(v) if v is not None and v != "" else None
        except (TypeError, ValueError):
            return None

    return {
        "impressions": int(_f("impressions") or 0),
        "clicks": int(_f("clicks") or 0),
        "spend": _f("spend"),
    }


def _attribute_spend_to_products(db, campaigns) -> int:
    """Write each campaign's spend onto today's ProductPerformance row.

    Without this the spend sits on AdCampaign where no margin calculation can
    see it, which is why `sales_sync_service` hard-coded ad_spend to 0.0 and
    F1's margin_actual has been gross margin wearing a net-margin label.

    Spend is SET, not accumulated: `total_spend` is the campaign's lifetime
    figure from the platform, so adding it each run would compound daily.
    """
    from ospra_os.database.performance_models import ProductPerformance

    today = datetime.utcnow().date()
    by_product: Dict[int, float] = {}
    for c in campaigns:
        if c.product_id is None or not c.total_spend:
            continue
        by_product[c.product_id] = by_product.get(c.product_id, 0.0) + float(c.total_spend)

    written = 0
    for product_id, spend in by_product.items():
        row = (
            db.query(ProductPerformance)
            .filter(
                ProductPerformance.product_id == product_id,
                ProductPerformance.date == today,
            )
            .first()
        )
        if row is None:
            # No sales row for today yet. Skipped rather than invented: a
            # performance row conjured from ad spend alone would carry a
            # fabricated store_id/user_id, and the sales sync will create the
            # real one.
            continue
        row.ad_spend = spend
        row.total_cost = (
            (row.product_cost or 0.0) + (row.shipping_cost or 0.0)
            + (row.platform_fees or 0.0) + spend
        )
        row.net_profit = (row.net_revenue or 0.0) - row.total_cost
        if row.net_revenue:
            row.profit_margin = (row.net_profit / row.net_revenue) * 100
        written += 1
    return written


@celery_app.task(
    bind=True,
    base=UserTask,
    name="ospra_os.tasks.analytics_tasks.check_ad_performance",
    max_retries=2,
    default_retry_delay=300,
    queue="low_priority"
)
def check_ad_performance(self) -> Dict[str, Any]:
    """Pull REAL ad spend from the platforms, attribute it, and flag problems.

    This was a stub: the entire body was commented out and it returned
    ``{"status": "success", "campaigns_checked": 0}`` — reporting success
    while doing nothing, which is why `ProductPerformance.ad_spend` has never
    held a real number and F1's `margin_actual` ignores ad cost.

    THIS TASK NEVER SPENDS, PAUSES, OR SCALES. It reads spend and RECORDS a
    recommendation. Acting on ad budget is a propose-then-approve decision
    that belongs to the owner, and a scheduled job that could pause or scale
    campaigns on its own is exactly the thing that must not exist here.

    Scheduled: daily at 9 AM UTC.
    """
    from ospra_os.database.advertising_models import AdCampaign

    logger.info("Starting ad performance check")

    try:
        campaigns = (
            self.db.query(AdCampaign)
            .filter(AdCampaign.status == "active")
            .all()
        )
        if not campaigns:
            logger.info("Ad check: no active campaigns")
            return {
                "status": "success", "campaigns_checked": 0, "updated": 0,
                "low_roas_count": 0, "recommendations": 0, "unreachable": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        updated = low_roas = unreachable = 0
        recommendations: list = []

        for campaign in campaigns:
            metrics = _fetch_campaign_metrics(campaign)
            if metrics is None:
                # Could not reach the platform. Leave the stored numbers
                # alone: a stale real figure beats a fabricated fresh one,
                # and silently zeroing spend would make every campaign look
                # free.
                unreachable += 1
                continue

            spend = metrics.get("spend")
            campaign.update_metrics(
                impressions=metrics.get("impressions"),
                clicks=metrics.get("clicks"),
                spend=spend,
            )
            if spend is not None:
                campaign.total_spend = float(spend)
            updated += 1

            roas = campaign.roas or 0.0
            if spend and float(spend) > 0 and roas < LOW_ROAS_THRESHOLD:
                low_roas += 1
                recommendations.append({
                    "campaign_id": campaign.campaign_id,
                    "platform": campaign.platform,
                    "roas": round(roas, 2),
                    "spend": round(float(spend), 2),
                    # A recommendation, not an action.
                    "suggested_action": "review_or_pause",
                    "reason": f"ROAS {roas:.2f} below {LOW_ROAS_THRESHOLD}",
                })

        attributed = _attribute_spend_to_products(self.db, campaigns)
        self.db.commit()

        logger.info(
            "Ad check complete: %d checked, %d updated, %d unreachable, "
            "%d low-ROAS, %d product-days attributed",
            len(campaigns), updated, unreachable, low_roas, attributed,
        )

        return {
            "status": "success",
            "campaigns_checked": len(campaigns),
            "updated": updated,
            "unreachable": unreachable,
            "low_roas_count": low_roas,
            "recommendations": len(recommendations),
            "recommendation_detail": recommendations,
            "product_days_attributed": attributed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error checking ad performance: {e}")
        self.db.rollback()
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=UserTask,
    name="ospra_os.tasks.analytics_tasks.check_product_performance",
    max_retries=2,
    default_retry_delay=300,
    queue="low_priority"
)
def check_product_performance(self) -> Dict[str, Any]:
    """
    Check product performance across all stores.

    Identifies:
    - Zero-sale products (last 30 days)
    - Declining products
    - Trending products
    - Products needing price adjustments

    Scheduled: Daily at 10 AM UTC
    """
    logger.info("Starting product performance check")

    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

        # Get all active products
        products = self.db.query(Product).filter(
            Product.is_active == True  # noqa: E712
        ).all()

        zero_sales_count = 0
        declining_count = 0
        trending_count = 0

        for product in products:
            # TODO: Check sales performance
            # sales = self._get_product_sales(product, since=cutoff_date)
            #
            # if sales.total == 0:
            #     zero_sales_count += 1
            #     self._send_zero_sales_alert(product)
            # elif sales.trend == "declining":
            #     declining_count += 1
            # elif sales.trend == "trending":
            #     trending_count += 1

            pass

        logger.info(f"Product check complete: {zero_sales_count} zero-sale products")

        return {
            "status": "success",
            "products_checked": len(products),
            "zero_sales": zero_sales_count,
            "declining": declining_count,
            "trending": trending_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Error checking product performance: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=UserTask,
    name="ospra_os.tasks.analytics_tasks.cleanup_old_data",
    max_retries=2,
    default_retry_delay=300,
    queue="low_priority"
)
def cleanup_old_data(self) -> Dict[str, Any]:
    """
    Clean up old data to prevent database bloat.

    Removes:
    - Logs older than 90 days
    - Expired action records
    - Old analytics snapshots
    - Temporary files

    Scheduled: Daily at 3 AM UTC
    """
    logger.info("Starting data cleanup")

    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=90)

        # TODO: Delete old logs
        # deleted_logs = self.db.query(Log).filter(
        #     Log.created_at < cutoff_date
        # ).delete()

        # TODO: Delete expired actions
        # deleted_actions = self.db.query(ScheduledAction).filter(
        #     ScheduledAction.status == "expired",
        #     ScheduledAction.created_at < cutoff_date
        # ).delete()

        # self.db.commit()

        deleted_logs = 0
        deleted_actions = 0

        logger.info(f"Cleanup complete: deleted {deleted_logs} logs, {deleted_actions} actions")

        return {
            "status": "success",
            "deleted_logs": deleted_logs,
            "deleted_actions": deleted_actions,
            "cutoff_date": cutoff_date.isoformat(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=UserTask,
    name="ospra_os.tasks.analytics_tasks.generate_analytics_report",
    max_retries=2,
    default_retry_delay=60,
    queue="low_priority"
)
def generate_analytics_report(
    self,
    user_id: int,
    period: str = "week",
    report_type: str = "performance"
) -> Dict[str, Any]:
    """
    Generate analytics report for a user.

    Report types:
    - performance: Overall store performance
    - products: Product-level analytics
    - ads: Advertising performance
    - customers: Customer behavior

    Periods:
    - day, week, month, quarter, year

    Args:
        user_id: User ID
        period: Time period
        report_type: Type of report

    Returns:
        Report data
    """
    logger.info(f"Generating {report_type} report for user {user_id} ({period})")

    try:
        user = self.get_user(user_id)
        if not user:
            logger.warning(f"User {user_id} not found")
            return {"status": "failed", "reason": "user_not_found"}

        # TODO: Generate report based on type
        # if report_type == "performance":
        #     data = self._generate_performance_report(user, period)
        # elif report_type == "products":
        #     data = self._generate_products_report(user, period)
        # elif report_type == "ads":
        #     data = self._generate_ads_report(user, period)
        # elif report_type == "customers":
        #     data = self._generate_customers_report(user, period)

        report_data = {
            "user_id": user_id,
            "period": period,
            "type": report_type,
            "metrics": {}
        }

        logger.info(f"Report generated for user {user_id}")

        return {
            "status": "success",
            "report": report_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Error generating report for user {user_id}: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=UserTask,
    name="ospra_os.tasks.analytics_tasks.calculate_roi",
    max_retries=2,
    default_retry_delay=60
)
def calculate_roi(
    self,
    user_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate ROI for a user across all activities.

    Includes:
    - Ad spend vs revenue
    - Product cost vs sales
    - Platform fee vs profit
    - Overall profitability

    Args:
        user_id: User ID
        start_date: Optional start date (ISO format)
        end_date: Optional end date (ISO format)

    Returns:
        ROI metrics
    """
    logger.info(f"Calculating ROI for user {user_id}")

    try:
        user = self.get_user(user_id)
        if not user:
            logger.warning(f"User {user_id} not found")
            return {"status": "failed", "reason": "user_not_found"}

        # TODO: Calculate ROI metrics
        # total_revenue = self._get_total_revenue(user, start_date, end_date)
        # total_costs = self._get_total_costs(user, start_date, end_date)
        # roi = ((total_revenue - total_costs) / total_costs) * 100

        roi_data = {
            "user_id": user_id,
            "total_revenue": 0.0,
            "total_costs": 0.0,
            "profit": 0.0,
            "roi_percent": 0.0
        }

        logger.info(f"ROI calculated for user {user_id}")

        return {
            "status": "success",
            "roi": roi_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Error calculating ROI for user {user_id}: {e}")
        raise self.retry(exc=e)
