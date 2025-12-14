"""
Celery Application Configuration - GROK RECOMMENDATION #13

Replaces APScheduler with production-grade distributed task queue.

Features:
- Distributed workers
- Task retries with backoff
- Scheduled jobs (Celery Beat)
- Task monitoring (Flower)
- Horizontal scaling
- Rate limiting
- Priority queues
"""

import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange

# Redis URL (broker and result backend)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "ospra",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "ospra_os.tasks.product_tasks",
        "ospra_os.tasks.action_tasks",
        "ospra_os.tasks.email_tasks",
        "ospra_os.tasks.sync_tasks",
        "ospra_os.tasks.analytics_tasks",
        "ospra_os.tasks.learning_tasks",
        "ospra_os.tasks.feedback_tasks",  # G4: Complete Feedback Loop
    ]
)

# ==================== CELERY CONFIGURATION ====================

celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,  # Acknowledge after task completes (safer)
    task_reject_on_worker_lost=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # Soft limit at 55 min

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_concurrency=4,  # 4 concurrent tasks per worker
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (memory safety)

    # Result backend
    result_expires=86400,  # Results expire after 24 hours
    result_backend_transport_options={'master_name': 'mymaster'},

    # Retry settings
    task_default_retry_delay=60,  # 1 minute between retries
    task_max_retries=3,

    # Rate limiting
    task_annotations={
        "ospra_os.tasks.email_tasks.send_email": {"rate_limit": "10/m"},
        "ospra_os.tasks.sync_tasks.sync_shopify_products": {"rate_limit": "5/m"},
        "ospra_os.tasks.product_tasks.discover_products_for_user": {"rate_limit": "20/m"},
    },

    # Task routing (different queues for different priorities)
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("high_priority", Exchange("high_priority"), routing_key="high_priority"),
        Queue("low_priority", Exchange("low_priority"), routing_key="low_priority"),
        Queue("scheduled", Exchange("scheduled"), routing_key="scheduled"),
    ),

    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    # Route specific tasks to specific queues
    task_routes={
        "ospra_os.tasks.action_tasks.execute_action": {"queue": "high_priority"},
        "ospra_os.tasks.action_tasks.process_auto_pilot": {"queue": "high_priority"},
        "ospra_os.tasks.email_tasks.*": {"queue": "default"},
        "ospra_os.tasks.analytics_tasks.*": {"queue": "low_priority"},
        "ospra_os.tasks.learning_tasks.*": {"queue": "low_priority"},
    },
)

# ==================== BEAT SCHEDULE (Replaces APScheduler) ====================

celery_app.conf.beat_schedule = {
    # Product Discovery - Daily at 6 AM UTC
    "daily-product-discovery": {
        "task": "ospra_os.tasks.product_tasks.daily_product_discovery",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "scheduled"},
    },

    # Inventory Check - Every 4 hours
    "inventory-check": {
        "task": "ospra_os.tasks.sync_tasks.check_inventory_levels",
        "schedule": crontab(hour="*/4", minute=0),
        "options": {"queue": "scheduled"},
    },

    # Ad Performance Check - Daily at 9 AM UTC
    "daily-ad-check": {
        "task": "ospra_os.tasks.analytics_tasks.check_ad_performance",
        "schedule": crontab(hour=9, minute=0),
        "options": {"queue": "scheduled"},
    },

    # Product Performance Check - Daily at 10 AM UTC
    "daily-product-performance": {
        "task": "ospra_os.tasks.analytics_tasks.check_product_performance",
        "schedule": crontab(hour=10, minute=0),
        "options": {"queue": "scheduled"},
    },

    # Daily Brief Emails - Daily at 7 AM UTC
    "daily-brief-emails": {
        "task": "ospra_os.tasks.email_tasks.send_daily_briefs",
        "schedule": crontab(hour=7, minute=0),
        "options": {"queue": "scheduled"},
    },

    # Learning Analysis - Daily at 2 AM UTC
    "daily-learning-analysis": {
        "task": "ospra_os.tasks.learning_tasks.analyze_learnings",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "low_priority"},
    },

    # Shopify Sync - Every 30 minutes
    "shopify-sync": {
        "task": "ospra_os.tasks.sync_tasks.sync_all_stores",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "scheduled"},
    },

    # Price Monitor - Every 2 hours
    "price-monitor": {
        "task": "ospra_os.tasks.product_tasks.monitor_supplier_prices",
        "schedule": crontab(hour="*/2", minute=15),
        "options": {"queue": "scheduled"},
    },

    # Clean up old data - Daily at 3 AM UTC
    "cleanup-old-data": {
        "task": "ospra_os.tasks.analytics_tasks.cleanup_old_data",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "low_priority"},
    },

    # Process expired actions - Every hour
    "expire-old-actions": {
        "task": "ospra_os.tasks.action_tasks.expire_old_actions",
        "schedule": crontab(minute=0),
        "options": {"queue": "scheduled"},
    },

    # ==================== G4: COMPLETE FEEDBACK LOOP ====================

    # Feedback Loop: Sync Sales Data - Every 6 hours
    "g4-feedback-sync-sales": {
        "task": "ospra_os.tasks.feedback_tasks.sync_all_stores_task",
        "schedule": crontab(hour="*/6", minute=0),
        "args": (1,),  # Sync last 1 day
        "options": {"queue": "scheduled"},
    },

    # Feedback Loop: Evaluate Outcomes - Daily at 2 AM UTC
    "g4-feedback-evaluate-outcomes": {
        "task": "ospra_os.tasks.feedback_tasks.evaluate_outcomes_task",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "scheduled"},
    },

    # Feedback Loop: Process Learning - Daily at 3 AM UTC
    "g4-feedback-process-learning": {
        "task": "ospra_os.tasks.feedback_tasks.process_learning_task",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "low_priority"},
    },

    # Feedback Loop: Update Global Weights - Weekly Monday at 1 AM UTC
    "g4-feedback-update-global-weights": {
        "task": "ospra_os.tasks.feedback_tasks.update_global_weights_task",
        "schedule": crontab(day_of_week=1, hour=1, minute=0),
        "options": {"queue": "low_priority"},
    },

    # Feedback Loop: Daily Master Task - Daily at 4 AM UTC
    "g4-feedback-daily-loop": {
        "task": "ospra_os.tasks.feedback_tasks.daily_feedback_loop",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "scheduled"},
    },
}

# ==================== TASK DISCOVERY ====================

# Auto-discover tasks in task modules
celery_app.autodiscover_tasks([
    'ospra_os.tasks',
])

# ==================== LOGGING ====================

celery_app.conf.worker_hijack_root_logger = False
celery_app.conf.worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
celery_app.conf.worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# Export
__all__ = ['celery_app']
