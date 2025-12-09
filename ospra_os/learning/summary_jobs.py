"""
Nightly Summary Background Jobs
================================

Scheduled jobs to pre-compute daily learning summaries.
Runs at 3 AM UTC to compress unlimited raw events into token-efficient summaries.
"""

import logging
from datetime import datetime
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ospra_os.database.multi_store_models import SessionLocal
from ospra_os.learning.summary_generator import generate_daily_summaries
from ospra_os.learning.summary_models import (
    LearningSummary,
    NichePerformance,
    ProductPerformance,
    TimeSeriesMetrics
)
from ospra_os.learning.hybrid_learning_engine import LearningEvent

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


async def nightly_summary_job():
    """
    Nightly job to generate summaries for all active users.

    Runs at 3 AM UTC daily.
    Compresses unlimited raw learning_events into ~800-1000 token summaries.
    """
    logger.info("🌙 Starting nightly summary job...")

    db = SessionLocal()
    try:
        # Get all unique user IDs from learning events
        user_ids = db.query(LearningEvent.user_id).distinct().all()
        user_ids = [uid[0] for uid in user_ids]

        if not user_ids:
            logger.info("   No users with learning data - skipping")
            return

        logger.info(f"   Processing summaries for {len(user_ids)} users...")

        success_count = 0
        error_count = 0

        for user_id in user_ids:
            try:
                # Generate summary
                summary_data = generate_daily_summaries(user_id, db)

                # Save to database
                summary = LearningSummary(
                    user_id=user_id,
                    summary_date=datetime.utcnow(),
                    overall_performance=summary_data['overall_performance'],
                    niche_insights=summary_data['niche_insights'],
                    top_products=summary_data['top_products'],
                    underperformers=summary_data['underperformers'],
                    price_insights=summary_data['price_insights'],
                    ad_insights=summary_data['ad_insights'],
                    recommendations=summary_data['recommendations'],
                    estimated_tokens=summary_data['estimated_tokens']
                )

                db.add(summary)
                db.commit()

                success_count += 1
                logger.info(f"   ✓ User {user_id}: {summary_data['estimated_tokens']} tokens")

            except Exception as e:
                error_count += 1
                logger.error(f"   ✗ User {user_id} failed: {e}")
                db.rollback()

        logger.info(f"✅ Nightly summary job complete: {success_count} succeeded, {error_count} failed")

    except Exception as e:
        logger.error(f"❌ Nightly summary job failed: {e}")
        db.rollback()
    finally:
        db.close()


async def update_aggregated_tables():
    """
    Update aggregated performance tables.

    Runs at 3:30 AM UTC daily (after summaries are generated).
    Updates:
    - NichePerformance: Real-time aggregation by niche
    - ProductPerformance: Lifetime stats per product
    - TimeSeriesMetrics: Weekly/monthly rollups
    """
    logger.info("📊 Updating aggregated performance tables...")

    db = SessionLocal()
    try:
        # Get all unique user IDs
        user_ids = db.query(LearningEvent.user_id).distinct().all()
        user_ids = [uid[0] for uid in user_ids]

        for user_id in user_ids:
            # Update niche performance
            _update_niche_performance(user_id, db)

            # Update product performance
            _update_product_performance(user_id, db)

            # Update time series metrics
            _update_time_series(user_id, db)

        db.commit()
        logger.info("✅ Aggregated tables updated")

    except Exception as e:
        logger.error(f"❌ Aggregated table update failed: {e}")
        db.rollback()
    finally:
        db.close()


def _update_niche_performance(user_id: int, db: SessionLocal):
    """Update NichePerformance table for a user."""
    # Get all sales events
    sales = db.query(LearningEvent).filter(
        LearningEvent.user_id == user_id,
        LearningEvent.event_type.in_(['sale', 'historical_sale'])
    ).all()

    # Aggregate by niche
    niche_stats = {}
    for sale in sales:
        details = sale.details
        niche = details.get('niche', 'unknown')

        if niche not in niche_stats:
            niche_stats[niche] = {
                'total_revenue': 0,
                'total_units_sold': 0,
                'products': set(),
                'prices': [],
                'first_sale': sale.created_at,
                'last_sale': sale.created_at
            }

        niche_stats[niche]['total_revenue'] += details.get('revenue', 0)
        niche_stats[niche]['total_units_sold'] += details.get('quantity', details.get('units_sold', 0))
        niche_stats[niche]['products'].add(details.get('product_id'))
        niche_stats[niche]['prices'].append(details.get('price', 0))

        if sale.created_at > niche_stats[niche]['last_sale']:
            niche_stats[niche]['last_sale'] = sale.created_at

    # Update or create records
    for niche, stats in niche_stats.items():
        record = db.query(NichePerformance).filter_by(
            user_id=user_id,
            niche=niche
        ).first()

        avg_price = sum(stats['prices']) / len(stats['prices']) if stats['prices'] else 0

        if record:
            # Update existing
            record.total_revenue = stats['total_revenue']
            record.total_units_sold = stats['total_units_sold']
            record.total_products = len(stats['products'])
            record.avg_price = avg_price
            record.last_sale_date = stats['last_sale']
            record.first_sale_date = stats['first_sale']
        else:
            # Create new
            record = NichePerformance(
                user_id=user_id,
                niche=niche,
                total_revenue=stats['total_revenue'],
                total_units_sold=stats['total_units_sold'],
                total_products=len(stats['products']),
                avg_price=avg_price,
                last_sale_date=stats['last_sale'],
                first_sale_date=stats['first_sale']
            )
            db.add(record)


def _update_product_performance(user_id: int, db: SessionLocal):
    """Update ProductPerformance table for a user."""
    # Get all product events
    events = db.query(LearningEvent).filter(
        LearningEvent.user_id == user_id
    ).all()

    # Aggregate by product
    product_stats = {}
    for event in events:
        details = event.details
        product_id = details.get('product_id')

        if not product_id:
            continue

        if product_id not in product_stats:
            product_stats[product_id] = {
                'product_name': details.get('product_name', 'Unknown'),
                'niche': details.get('niche', 'unknown'),
                'total_revenue': 0,
                'total_units_sold': 0,
                'total_ad_spend': 0,
                'total_ad_revenue': 0,
                'prices': [],
                'deploy_date': None,
                'last_sale_date': None
            }

        # Sale events
        if event.event_type in ['sale', 'historical_sale']:
            product_stats[product_id]['total_revenue'] += details.get('revenue', 0)
            product_stats[product_id]['total_units_sold'] += details.get('quantity', details.get('units_sold', 0))
            product_stats[product_id]['prices'].append(details.get('price', 0))
            product_stats[product_id]['last_sale_date'] = event.created_at

        # Deployment events
        elif event.event_type == 'product_deployed':
            if not product_stats[product_id]['deploy_date']:
                product_stats[product_id]['deploy_date'] = event.created_at

        # Ad performance events
        elif event.event_type == 'ad_performance':
            product_stats[product_id]['total_ad_spend'] += details.get('spend', 0)
            product_stats[product_id]['total_ad_revenue'] += details.get('revenue', 0)

    # Update or create records
    for product_id, stats in product_stats.items():
        record = db.query(ProductPerformance).filter_by(
            user_id=user_id,
            product_id=product_id
        ).first()

        avg_price = sum(stats['prices']) / len(stats['prices']) if stats['prices'] else 0
        roas = (stats['total_ad_revenue'] / stats['total_ad_spend']) if stats['total_ad_spend'] > 0 else 0
        roi = ((stats['total_revenue'] - stats['total_ad_spend']) / stats['total_ad_spend'] * 100) if stats['total_ad_spend'] > 0 else 0
        is_profitable = 1 if stats['total_revenue'] > stats['total_ad_spend'] else 0

        if record:
            # Update existing
            record.product_name = stats['product_name']
            record.niche = stats['niche']
            record.total_revenue = stats['total_revenue']
            record.total_units_sold = stats['total_units_sold']
            record.total_ad_spend = stats['total_ad_spend']
            record.total_ad_revenue = stats['total_ad_revenue']
            record.avg_price = avg_price
            record.roas = roas
            record.roi_percentage = roi
            record.is_profitable = is_profitable
            if stats['deploy_date']:
                record.deploy_date = stats['deploy_date']
            if stats['last_sale_date']:
                record.last_sale_date = stats['last_sale_date']
        else:
            # Create new
            record = ProductPerformance(
                user_id=user_id,
                product_id=product_id,
                product_name=stats['product_name'],
                niche=stats['niche'],
                total_revenue=stats['total_revenue'],
                total_units_sold=stats['total_units_sold'],
                total_ad_spend=stats['total_ad_spend'],
                total_ad_revenue=stats['total_ad_revenue'],
                avg_price=avg_price,
                roas=roas,
                roi_percentage=roi,
                is_profitable=is_profitable,
                deploy_date=stats['deploy_date'],
                last_sale_date=stats['last_sale_date']
            )
            db.add(record)


def _update_time_series(user_id: int, db: SessionLocal):
    """Update TimeSeriesMetrics table for a user."""
    # This is a simplified version - in production you'd want more sophisticated rollup logic
    from datetime import timedelta

    now = datetime.utcnow()

    # Get events from last month
    month_ago = now - timedelta(days=30)
    events = db.query(LearningEvent).filter(
        LearningEvent.user_id == user_id,
        LearningEvent.created_at >= month_ago
    ).all()

    if not events:
        return

    # Simple monthly rollup
    total_revenue = 0
    total_units = 0
    total_products = set()
    total_ad_spend = 0
    total_ad_revenue = 0
    niche_revenue = {}

    for event in events:
        details = event.details

        if event.event_type in ['sale', 'historical_sale']:
            total_revenue += details.get('revenue', 0)
            total_units += details.get('quantity', details.get('units_sold', 0))

            niche = details.get('niche', 'unknown')
            niche_revenue[niche] = niche_revenue.get(niche, 0) + details.get('revenue', 0)

        elif event.event_type == 'product_deployed':
            total_products.add(details.get('product_id'))

        elif event.event_type == 'ad_performance':
            total_ad_spend += details.get('spend', 0)
            total_ad_revenue += details.get('revenue', 0)

    # Find top niche
    top_niche = max(niche_revenue.items(), key=lambda x: x[1]) if niche_revenue else (None, 0)

    # Check if record exists for this month
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    record = db.query(TimeSeriesMetrics).filter(
        TimeSeriesMetrics.user_id == user_id,
        TimeSeriesMetrics.period_type == 'month',
        TimeSeriesMetrics.period_start == period_start
    ).first()

    avg_roas = (total_ad_revenue / total_ad_spend) if total_ad_spend > 0 else 0

    if record:
        # Update existing
        record.total_revenue = total_revenue
        record.total_units_sold = total_units
        record.total_products_deployed = len(total_products)
        record.total_ad_spend = total_ad_spend
        record.total_ad_revenue = total_ad_revenue
        record.avg_roas = avg_roas
        record.top_niche = top_niche[0]
        record.top_niche_revenue = top_niche[1]
    else:
        # Create new
        record = TimeSeriesMetrics(
            user_id=user_id,
            period_type='month',
            period_start=period_start,
            period_end=period_end,
            total_revenue=total_revenue,
            total_units_sold=total_units,
            total_products_deployed=len(total_products),
            total_ad_spend=total_ad_spend,
            total_ad_revenue=total_ad_revenue,
            avg_roas=avg_roas,
            top_niche=top_niche[0],
            top_niche_revenue=top_niche[1]
        )
        db.add(record)


def setup_summary_jobs():
    """
    Setup scheduled jobs for summary generation.

    Call this from main.py on app startup.
    """
    global scheduler

    if scheduler is not None:
        logger.warning("Summary jobs scheduler already initialized")
        return scheduler

    try:
        scheduler = AsyncIOScheduler()

        # Nightly summary job at 3:00 AM UTC
        scheduler.add_job(
            nightly_summary_job,
            trigger=CronTrigger(hour=3, minute=0),
            id='nightly_summary_job',
            name='Generate daily learning summaries',
            replace_existing=True,
            misfire_grace_time=3600  # Allow 1 hour grace period
        )

        # Aggregated tables update at 3:30 AM UTC (after summaries)
        scheduler.add_job(
            update_aggregated_tables,
            trigger=CronTrigger(hour=3, minute=30),
            id='update_aggregated_tables',
            name='Update aggregated performance tables',
            replace_existing=True,
            misfire_grace_time=3600
        )

        scheduler.start()
        logger.info("✅ Summary background jobs scheduled:")
        logger.info("   - Nightly summaries: 3:00 AM UTC")
        logger.info("   - Aggregated tables: 3:30 AM UTC")

        return scheduler

    except Exception as e:
        logger.error(f"❌ Failed to setup summary jobs: {e}")
        return None


def shutdown_summary_jobs():
    """Shutdown the scheduler gracefully."""
    global scheduler

    if scheduler:
        scheduler.shutdown()
        logger.info("✅ Summary jobs scheduler shut down")


# Manual trigger functions for testing

async def trigger_summary_job_now():
    """Manually trigger the summary job (for testing)."""
    logger.info("🔄 Manually triggering summary job...")
    await nightly_summary_job()


async def trigger_aggregation_now():
    """Manually trigger the aggregation job (for testing)."""
    logger.info("🔄 Manually triggering aggregation job...")
    await update_aggregated_tables()


if __name__ == "__main__":
    """Test the jobs manually."""
    import asyncio

    async def test():
        print("Testing summary jobs...")
        await trigger_summary_job_now()
        await trigger_aggregation_now()
        print("Done!")

    asyncio.run(test())
