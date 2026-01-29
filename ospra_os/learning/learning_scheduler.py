"""
Self-Learning Scheduler
========================

Scheduled jobs that activate the self-learning system:
1. Daily Learning Cycle - Analyzes recent sales and updates AI weights
2. Weekly Model Update - More comprehensive learning with historical data
3. Tracking Sync - Syncs tracking from suppliers to Shopify

Author: Ospra Intelligence
"""

import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ospra_os.constants import (
    DAILY_LEARNING_HOUR,
    WEEKLY_LEARNING_DAY,
    WEEKLY_LEARNING_HOUR,
    TRACKING_SYNC_INTERVAL_HOURS,
    LEARNING_DATA_RETENTION_DAYS,
)

logger = logging.getLogger(__name__)

# Global scheduler instance
_learning_scheduler: AsyncIOScheduler = None


def start_learning_scheduler():
    """
    Start the self-learning scheduler.
    
    Schedules:
    - Daily learning cycle at 3:00 AM
    - Weekly comprehensive update on Sundays at 4:00 AM
    - Tracking sync every 6 hours
    """
    global _learning_scheduler
    
    if _learning_scheduler is not None:
        logger.warning("Learning scheduler already running")
        return
    
    _learning_scheduler = AsyncIOScheduler()
    
    # Daily learning cycle at configured hour
    _learning_scheduler.add_job(
        run_daily_learning_cycle,
        CronTrigger(hour=DAILY_LEARNING_HOUR, minute=0),
        id="daily_learning_cycle",
        name="Daily AI Learning Cycle",
        replace_existing=True
    )

    # Weekly comprehensive learning at configured day/hour
    _learning_scheduler.add_job(
        run_weekly_learning_update,
        CronTrigger(day_of_week=WEEKLY_LEARNING_DAY, hour=WEEKLY_LEARNING_HOUR, minute=0),
        id="weekly_learning_update",
        name="Weekly AI Model Update",
        replace_existing=True
    )

    # Tracking sync at configured interval
    _learning_scheduler.add_job(
        sync_supplier_tracking,
        IntervalTrigger(hours=TRACKING_SYNC_INTERVAL_HOURS),
        id="tracking_sync",
        name="Supplier Tracking Sync",
        replace_existing=True
    )
    
    # Learning data cleanup (remove old events) - weekly
    _learning_scheduler.add_job(
        cleanup_old_learning_data,
        CronTrigger(day_of_week='mon', hour=2, minute=0),
        id="learning_cleanup",
        name="Learning Data Cleanup",
        replace_existing=True
    )
    
    _learning_scheduler.start()
    
    logger.info("[BRAIN] Self-Learning Scheduler started")
    logger.info(f"    Daily learning: {DAILY_LEARNING_HOUR}:00 AM")
    logger.info(f"    Weekly update: {WEEKLY_LEARNING_DAY.capitalize()}s {WEEKLY_LEARNING_HOUR}:00 AM")
    logger.info(f"    Tracking sync: Every {TRACKING_SYNC_INTERVAL_HOURS} hours")


async def run_daily_learning_cycle():
    """
    Run daily learning cycle.
    
    Analyzes yesterday's sales and updates AI weights accordingly.
    """
    logger.info("[BRAIN] Starting daily learning cycle...")
    
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database import AILearningEvent
        from ospra_os.learning.hybrid_learning_engine import HybridLearningEngine
        
        db = SessionLocal()
        engine = HybridLearningEngine(db)
        
        try:
            # Get sales events from the last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            events = db.query(AILearningEvent).filter(
                AILearningEvent.event_type == "sale",
                AILearningEvent.timestamp >= yesterday
            ).all()
            
            if not events:
                logger.info("  No new sales data to learn from")
                return
            
            # Convert events to learning data format
            sales_data = []
            for event in events:
                details = event.details or {}
                sales_data.append({
                    "product_id": event.product_id,
                    "product_name": details.get("product_name", "Unknown"),
                    "niche": details.get("niche", "general"),
                    "price": details.get("price", 0),
                    "price_point": details.get("price_point", "20_to_50"),
                    "quantity": details.get("quantity", 1),
                    "revenue": details.get("revenue", 0),
                    "predicted_score": details.get("predicted_score"),  # If we have it
                    "actual_units_sold": details.get("quantity", 1),
                })
            
            logger.info(f"  Found {len(sales_data)} sales to learn from")
            
            # Run global learning
            result = await engine.learn_global(sales_data, user_id=1)
            
            if result.get("success"):
                logger.info(f"  ✅ Daily learning complete")
                logger.info(f"     Niche updates: {result.get('niche_updates', {})}")
                logger.info(f"     Price updates: {result.get('price_updates', {})}")
            else:
                logger.warning(f"  ⚠️ Learning had issues: {result.get('reason')}")
            
            # Update JSON file for backwards compatibility
            await update_learning_json(engine)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"[BRAIN] Daily learning failed: {e}")
        import traceback
        traceback.print_exc()


async def run_weekly_learning_update():
    """
    Run comprehensive weekly learning.
    
    Analyzes entire week's data and recalibrates weights.
    """
    logger.info("[BRAIN] Starting weekly comprehensive learning...")
    
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database import AILearningEvent
        from ospra_os.learning.hybrid_learning_engine import HybridLearningEngine
        
        db = SessionLocal()
        engine = HybridLearningEngine(db)
        
        try:
            # Get sales events from the last 7 days
            last_week = datetime.utcnow() - timedelta(days=7)
            
            sales_events = db.query(AILearningEvent).filter(
                AILearningEvent.event_type == "sale",
                AILearningEvent.timestamp >= last_week
            ).all()
            
            cancellation_events = db.query(AILearningEvent).filter(
                AILearningEvent.event_type == "cancellation",
                AILearningEvent.timestamp >= last_week
            ).all()
            
            logger.info(f"  Weekly data: {len(sales_events)} sales, {len(cancellation_events)} cancellations")
            
            # Prepare comprehensive learning data
            sales_data = []
            for event in sales_events:
                details = event.details or {}
                sales_data.append({
                    "product_id": event.product_id,
                    "niche": details.get("niche", "general"),
                    "price": details.get("price", 0),
                    "price_point": details.get("price_point", "20_to_50"),
                    "revenue": details.get("revenue", 0),
                    "quantity": details.get("quantity", 1),
                    "success": True
                })
            
            # Add cancellations as negative signals
            for event in cancellation_events:
                details = event.details or {}
                sales_data.append({
                    "product_id": event.product_id,
                    "niche": details.get("niche", "general"),
                    "price": details.get("price", 0),
                    "success": False  # Negative signal
                })
            
            if sales_data:
                # Run comprehensive learning with weighted data
                result = await engine.learn_global(sales_data, user_id=1)
                logger.info(f"  ✅ Weekly learning complete: {result}")
            else:
                logger.info("  No data for weekly learning")
            
            # Update JSON file
            await update_learning_json(engine)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"[BRAIN] Weekly learning failed: {e}")
        import traceback
        traceback.print_exc()


async def sync_supplier_tracking():
    """
    Sync tracking numbers from suppliers to Shopify.
    
    Checks CJ Dropshipping orders for tracking updates.
    """
    logger.info("[TRACKING] Syncing supplier tracking...")
    
    try:
        from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
        import json
        import os
        
        engine = get_fulfillment_engine()
        
        # Load fulfillment queue
        queue_file = os.path.join(
            os.path.dirname(__file__),
            '..', 'data', 'fulfillment_queue.json'
        )
        
        if not os.path.exists(queue_file):
            logger.info("  No fulfillment queue found")
            return
        
        with open(queue_file, 'r') as f:
            queue = json.load(f)
        
        orders_to_check = [
            order for order in queue 
            if order.get('status') == 'ordered' and order.get('supplier_type') == 'cj_dropshipping'
        ]
        
        if not orders_to_check:
            logger.info("  No CJ orders to check")
            return
        
        logger.info(f"  Checking {len(orders_to_check)} CJ orders for tracking")
        
        synced = 0
        for order in orders_to_check:
            supplier_order_id = order.get('supplier_order_id')
            if not supplier_order_id:
                continue
            
            tracking = await engine.check_cj_tracking(supplier_order_id)
            
            if tracking and tracking.get('tracking_number'):
                result = await engine.update_tracking(
                    shopify_order_id=order.get('shopify_order_id'),
                    tracking_number=tracking['tracking_number'],
                    carrier=tracking.get('carrier', 'Other')
                )
                
                if result.get('success'):
                    synced += 1
                    # Update queue status
                    order['status'] = 'shipped'
                    order['tracking_number'] = tracking['tracking_number']
        
        # Save updated queue
        if synced > 0:
            with open(queue_file, 'w') as f:
                json.dump(queue, f, indent=2)
        
        logger.info(f"  ✅ Synced {synced} tracking numbers")
        
    except Exception as e:
        logger.error(f"[TRACKING] Sync failed: {e}")


async def cleanup_old_learning_data():
    """
    Clean up old learning events to prevent database bloat.

    Keeps data for configured retention period.
    """
    logger.info("[CLEANUP] Cleaning old learning data...")

    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database import AILearningEvent

        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(days=LEARNING_DATA_RETENTION_DAYS)
            
            deleted = db.query(AILearningEvent).filter(
                AILearningEvent.timestamp < cutoff
            ).delete()
            
            db.commit()
            logger.info(f"  ✅ Cleaned up {deleted} old learning events")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"[CLEANUP] Failed: {e}")


async def update_learning_json(engine):
    """
    Update the learning JSON file for backwards compatibility.
    
    The frontend reads from this file to display learning status.
    """
    import json
    import os
    
    try:
        weights = engine.get_global_weights()
        
        json_data = {
            "version": weights.get("version", "1.0"),
            "last_updated": datetime.utcnow().isoformat(),
            "total_learning_cycles": weights.get("learning_cycles", 0),
            "scoring_weights": weights.get("scoring_weights", {}),
            "niche_confidence": weights.get("niche_confidence", {}),
            "price_point_confidence": weights.get("price_confidence", {}),
            "trend_velocity": weights.get("trend_velocity", {}),
            "accuracy_tracking": weights.get("accuracy", {})
        }
        
        # Save to JSON file
        json_file = os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'data', 'learning', 'confidence_weights.json'
        )
        
        os.makedirs(os.path.dirname(json_file), exist_ok=True)
        
        with open(json_file, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        logger.info("  Updated learning JSON file")
        
    except Exception as e:
        logger.warning(f"  Failed to update JSON: {e}")


# ============================================================================
# MANUAL TRIGGER ENDPOINTS (for testing)
# ============================================================================

async def trigger_learning_now():
    """
    Manually trigger a learning cycle (for testing).
    """
    await run_daily_learning_cycle()
    return {"success": True, "message": "Learning cycle triggered"}


async def get_learning_status():
    """
    Get current learning system status.
    
    Returns status information even if database tables don't exist yet.
    """
    db = None
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database import AILearningEvent
        from ospra_os.learning.hybrid_learning_engine import HybridLearningEngine
        
        db = SessionLocal()
        
        try:
            engine = HybridLearningEngine(db)
            weights = engine.get_global_weights()
        except Exception as engine_error:
            # Database tables don't exist yet
            logger.warning(f"Learning engine init failed: {engine_error}")
            return {
                "status": "not_initialized",
                "learning_cycles": 0,
                "total_sales_analyzed": 0,
                "total_revenue_analyzed": 0,
                "accuracy": {},
                "events_last_24h": 0,
                "events_last_7d": 0,
                "last_updated": None,
                "next_cycle": "3:00 AM daily",
                "scheduler_running": _learning_scheduler is not None and _learning_scheduler.running,
                "error": str(engine_error),
                "fix": "Run database migrations to create learning tables"
            }
        
        # Count recent events
        try:
            last_24h = datetime.utcnow() - timedelta(days=1)
            last_7d = datetime.utcnow() - timedelta(days=7)
            
            events_24h = db.query(AILearningEvent).filter(
                AILearningEvent.timestamp >= last_24h
            ).count()
            
            events_7d = db.query(AILearningEvent).filter(
                AILearningEvent.timestamp >= last_7d
            ).count()
        except Exception:
            events_24h = 0
            events_7d = 0
        
        return {
            "status": "active" if weights.get("learning_cycles", 0) > 0 else "pending_data",
            "learning_cycles": weights.get("learning_cycles", 0),
            "total_sales_analyzed": weights.get("total_sales_analyzed", 0),
            "total_revenue_analyzed": weights.get("total_revenue_analyzed", 0),
            "accuracy": weights.get("accuracy", {}),
            "events_last_24h": events_24h,
            "events_last_7d": events_7d,
            "last_updated": weights.get("last_updated"),
            "next_cycle": "3:00 AM daily",
            "scheduler_running": _learning_scheduler is not None and _learning_scheduler.running
        }
        
    except Exception as e:
        logger.error(f"Failed to get learning status: {e}")
        return {
            "status": "error",
            "learning_cycles": 0,
            "error": str(e),
            "scheduler_running": _learning_scheduler is not None and _learning_scheduler.running
        }
    finally:
        if db:
            db.close()
