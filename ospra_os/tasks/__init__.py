"""
Celery Task Modules - GROK RECOMMENDATION #13

Task organization:
- product_tasks: Product discovery, monitoring
- action_tasks: Action execution, auto-pilot
- email_tasks: Email sending, daily briefs
- sync_tasks: Shopify syncs, inventory checks
- analytics_tasks: Performance analysis
- learning_tasks: AI learning and pattern recognition
"""

__all__ = [
    'product_tasks',
    'action_tasks',
    'email_tasks',
    'sync_tasks',
    'analytics_tasks',
    'learning_tasks',
]
