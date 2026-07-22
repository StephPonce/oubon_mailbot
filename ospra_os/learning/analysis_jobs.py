"""
Continuous Learning Analysis Jobs
==================================

Background jobs that run periodically to analyze learning events and update
global and personal learning weights.

These jobs should be scheduled to run:
- calculate_global_patterns(): Daily (recommended)
- calculate_personal_patterns(): Daily for each active user
- cleanup_old_events(): Weekly (optional, for database maintenance)
"""

import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import List, Dict, Any

from ospra_os.database import SessionLocal, User
from ospra_os.database.performance_models import ORGANIC_SALE_EVENT_TYPES
from ospra_os.learning.hybrid_learning_engine import (
    LearningEvent,
    GlobalLearningWeights,
    PersonalLearningWeights,
    DEFAULT_SCORING_WEIGHTS
)

logger = logging.getLogger(__name__)


async def calculate_global_patterns():
    """
    Calculate and update global learning weights from all learning events.

    This function:
    1. Fetches all learning events (sales, deployments, ad performance)
    2. Aggregates patterns across all users
    3. Updates global_learning_weights table

    Should run: Daily
    """
    logger.info("[BRAIN] Starting global pattern calculation...")

    db = SessionLocal()
    try:
        # Fetch all learning events
        events = db.query(LearningEvent).all()

        if not events:
            logger.warning("[WARNING] No learning events found - skipping calculation")
            return

        # Aggregate stats by niche
        niche_stats = defaultdict(lambda: {
            "revenue": 0.0,
            "units": 0,
            "count": 0,
            "ad_spend": 0.0,
            "ad_revenue": 0.0
        })

        # Aggregate stats by price range
        price_ranges = defaultdict(lambda: {
            "revenue": 0.0,
            "units": 0,
            "count": 0
        })

        total_revenue = 0.0
        total_units = 0
        total_ad_spend = 0.0
        total_ad_revenue = 0.0
        unique_users = set()

        for event in events:
            details = event.details
            event_type = event.event_type

            # Track unique users
            if event.user_id:
                unique_users.add(event.user_id)

            # Process sales events
            if event_type in ORGANIC_SALE_EVENT_TYPES:  # provenance guard: seeded imports never count
                niche = details.get("niche", "unknown")
                price = details.get("price", 0)
                quantity = details.get("quantity", 0)
                revenue = details.get("revenue", 0)

                niche_stats[niche]["revenue"] += revenue
                niche_stats[niche]["units"] += quantity
                niche_stats[niche]["count"] += 1

                total_revenue += revenue
                total_units += quantity

                # Price range aggregation
                if price < 20:
                    price_range = "under_20"
                elif price < 40:
                    price_range = "20_to_40"
                elif price < 60:
                    price_range = "40_to_60"
                else:
                    price_range = "over_60"

                price_ranges[price_range]["revenue"] += revenue
                price_ranges[price_range]["units"] += quantity
                price_ranges[price_range]["count"] += 1

            # Process ad performance events
            elif event_type == "ad_performance":
                niche = details.get("niche", "unknown")
                spend = details.get("spend", 0)
                ad_revenue = details.get("revenue", 0)

                niche_stats[niche]["ad_spend"] += spend
                niche_stats[niche]["ad_revenue"] += ad_revenue

                total_ad_spend += spend
                total_ad_revenue += ad_revenue

        # Calculate niche confidence (revenue-weighted)
        niche_confidence = {}
        for niche, stats in niche_stats.items():
            confidence = stats["revenue"] / total_revenue if total_revenue > 0 else 0
            niche_confidence[niche] = round(confidence, 4)

        # Calculate price confidence
        price_confidence = {}
        for price_range, stats in price_ranges.items():
            confidence = stats["revenue"] / total_revenue if total_revenue > 0 else 0
            price_confidence[price_range] = round(confidence, 4)

        # Calculate overall ROAS by niche
        niche_roas = {}
        for niche, stats in niche_stats.items():
            if stats["ad_spend"] > 0:
                roas = stats["ad_revenue"] / stats["ad_spend"]
                niche_roas[niche] = round(roas, 2)

        # Sort niches by performance
        top_niches = sorted(
            niche_confidence.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Create or update global weights
        global_weights = db.query(GlobalLearningWeights).first()

        if not global_weights:
            global_weights = GlobalLearningWeights(
                version="1.0",
                learning_cycles=1,
                scoring_weights=DEFAULT_SCORING_WEIGHTS,
                niche_confidence=niche_confidence,
                price_confidence=price_confidence,
                trend_velocity={
                    "fast_trending_threshold": 0.7,
                    "moderate_trending_threshold": 0.4,
                    "slow_trending_threshold": 0.2
                },
                accuracy={
                    "total_predictions": 0,
                    "correct_predictions": 0,
                    "accuracy_rate": 0.0,
                    "note": "Accuracy tracking coming soon"
                },
                total_users_contributing=len(unique_users),
                total_sales_analyzed=len([e for e in events if e.event_type in ORGANIC_SALE_EVENT_TYPES]),
                total_revenue_analyzed=total_revenue
            )
            db.add(global_weights)
        else:
            # Update existing
            global_weights.learning_cycles += 1
            global_weights.niche_confidence = niche_confidence
            global_weights.price_confidence = price_confidence
            global_weights.total_users_contributing = len(unique_users)
            global_weights.total_sales_analyzed = len([e for e in events if e.event_type in ORGANIC_SALE_EVENT_TYPES])
            global_weights.total_revenue_analyzed = total_revenue
            global_weights.updated_at = datetime.now(timezone.utc)

        db.commit()

        logger.info("[SUCCESS] Global patterns calculated:")
        logger.info(f"   Top niches: {', '.join([f'{n}({c:.1%})' for n, c in top_niches])}")
        logger.info(f"   Total sales: {len([e for e in events if e.event_type in ORGANIC_SALE_EVENT_TYPES])}")
        logger.info(f"   Total revenue: ${total_revenue:,.2f}")
        logger.info(f"   Users contributing: {len(unique_users)}")

    except Exception as e:
        logger.error(f"[ERROR] Failed to calculate global patterns: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


async def calculate_personal_patterns(user_id: int):
    """
    Calculate and update personal learning weights for a specific user.

    This function:
    1. Fetches user's learning events
    2. Identifies their best performing niches, price ranges, etc.
    3. Updates personal_learning_weights table

    Args:
        user_id: User ID to calculate patterns for

    Should run: Daily for each active user
    """
    logger.info(f" Calculating personal patterns for user {user_id}...")

    db = SessionLocal()
    try:
        # Fetch user's learning events
        events = db.query(LearningEvent).filter(
            LearningEvent.user_id == user_id
        ).all()

        if not events:
            logger.warning(f"[WARNING] No learning events for user {user_id} - skipping")
            return

        # Aggregate user's niche performance
        niche_performance = defaultdict(lambda: {
            "revenue": 0.0,
            "units": 0,
            "ad_spend": 0.0,
            "ad_revenue": 0.0
        })

        price_stats = []
        total_revenue = 0.0
        sales_count = 0

        for event in events:
            details = event.details
            event_type = event.event_type

            if event_type in ORGANIC_SALE_EVENT_TYPES:  # provenance guard: seeded imports never count
                niche = details.get("niche", "unknown")
                price = details.get("price", 0)
                revenue = details.get("revenue", 0)
                quantity = details.get("quantity", 0)

                niche_performance[niche]["revenue"] += revenue
                niche_performance[niche]["units"] += quantity
                price_stats.append(price)
                total_revenue += revenue
                sales_count += 1

            elif event_type == "ad_performance":
                niche = details.get("niche", "unknown")
                niche_performance[niche]["ad_spend"] += details.get("spend", 0)
                niche_performance[niche]["ad_revenue"] += details.get("revenue", 0)

        # Find best performing niches (by revenue)
        best_niches = sorted(
            niche_performance.items(),
            key=lambda x: x[1]["revenue"],
            reverse=True
        )[:5]

        best_niche_names = [niche for niche, _ in best_niches]

        # Calculate optimal price range
        if price_stats:
            min_price = min(price_stats)
            max_price = max(price_stats)
            avg_price = sum(price_stats) / len(price_stats)
            optimal_price_range = {
                "min": round(min_price, 2),
                "max": round(max_price, 2),
                "avg": round(avg_price, 2)
            }
        else:
            optimal_price_range = {}

        # Create or update personal weights
        personal = db.query(PersonalLearningWeights).filter_by(user_id=user_id).first()

        if not personal:
            personal = PersonalLearningWeights(
                user_id=user_id,
                version="1.0",
                learning_cycles=1,
                scoring_adjustments={},
                niche_adjustments={},
                price_adjustments={},
                best_performing_niches=best_niche_names,
                optimal_price_range=optimal_price_range,
                peak_selling_days=[],
                predictions_made=0,
                predictions_correct=0,
                accuracy_rate=0.0,
                sales_analyzed=sales_count,
                revenue_analyzed=total_revenue
            )
            db.add(personal)
        else:
            # Update existing
            personal.learning_cycles += 1
            personal.best_performing_niches = best_niche_names
            personal.optimal_price_range = optimal_price_range
            personal.sales_analyzed = sales_count
            personal.revenue_analyzed = total_revenue
            personal.updated_at = datetime.now(timezone.utc)

        db.commit()

        logger.info(f"[SUCCESS] Personal patterns calculated for user {user_id}:")
        logger.info(f"   Best niches: {', '.join(best_niche_names)}")
        logger.info(f"   Optimal price: ${optimal_price_range.get('min', 0):.2f} - ${optimal_price_range.get('max', 0):.2f}")
        logger.info(f"   Sales analyzed: {sales_count}")

    except Exception as e:
        logger.error(f"[ERROR] Failed to calculate personal patterns for user {user_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


async def calculate_all_personal_patterns():
    """
    Calculate personal patterns for all active users.

    Should run: Daily
    """
    logger.info(" Calculating personal patterns for all users...")

    db = SessionLocal()
    try:
        # Get all users with learning events
        users_with_events = db.query(LearningEvent.user_id).distinct().all()
        user_ids = [u[0] for u in users_with_events if u[0] is not None]

        logger.info(f"   Found {len(user_ids)} users with learning events")

        for user_id in user_ids:
            await calculate_personal_patterns(user_id)

        logger.info(f"[SUCCESS] Personal patterns calculated for {len(user_ids)} users")

    except Exception as e:
        logger.error(f"[ERROR] Failed to calculate all personal patterns: {e}")
    finally:
        db.close()


async def cleanup_old_events(days_to_keep: int = 90):
    """
    Delete learning events older than N days to keep database size manageable.

    Args:
        days_to_keep: Keep events from the past N days (default: 90)

    Should run: Weekly or monthly
    """
    logger.info(f" Cleaning up learning events older than {days_to_keep} days...")

    db = SessionLocal()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        deleted_count = db.query(LearningEvent).filter(
            LearningEvent.timestamp < cutoff_date
        ).delete()

        db.commit()

        logger.info(f"[SUCCESS] Deleted {deleted_count} old learning events")

    except Exception as e:
        logger.error(f"[ERROR] Failed to cleanup old events: {e}")
        db.rollback()
    finally:
        db.close()


# ============================================================================
# SCHEDULER INTEGRATION (Optional - for automatic background execution)
# ============================================================================

def setup_learning_jobs():
    """
    Set up scheduled jobs using APScheduler.

    Call this function once at application startup to schedule the learning jobs.

    Example:
        from ospra_os.learning.analysis_jobs import setup_learning_jobs
        setup_learning_jobs()
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = AsyncIOScheduler()

        # Daily at 2 AM: Calculate global patterns
        scheduler.add_job(
            calculate_global_patterns,
            CronTrigger(hour=2, minute=0),
            id="calculate_global_patterns",
            name="Calculate global learning patterns",
            replace_existing=True
        )

        # Daily at 3 AM: Calculate all personal patterns
        scheduler.add_job(
            calculate_all_personal_patterns,
            CronTrigger(hour=3, minute=0),
            id="calculate_all_personal_patterns",
            name="Calculate personal learning patterns for all users",
            replace_existing=True
        )

        # Weekly on Sunday at 4 AM: Cleanup old events
        scheduler.add_job(
            cleanup_old_events,
            CronTrigger(day_of_week="sun", hour=4, minute=0),
            id="cleanup_old_events",
            name="Cleanup old learning events",
            replace_existing=True
        )

        scheduler.start()

        logger.info("[SUCCESS] Learning analysis jobs scheduled")
        logger.info("   - Global patterns: Daily at 2 AM")
        logger.info("   - Personal patterns: Daily at 3 AM")
        logger.info("   - Cleanup: Weekly on Sunday at 4 AM")

        return scheduler

    except ImportError:
        logger.warning("[WARNING] APScheduler not installed - background jobs not scheduled")
        logger.info("   Install with: pip install apscheduler")
        logger.info("   Or run jobs manually via API endpoints")
        return None
    except Exception as e:
        logger.error(f"[ERROR] Failed to setup learning jobs: {e}")
        return None
