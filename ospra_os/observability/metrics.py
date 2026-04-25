"""
Metrics and Event Tracking
Provides custom event tracking for business metrics and operational monitoring.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum

# Sentry SDK is optional — degrade gracefully when not installed (e.g. in
# lean test environments). Every helper that calls sentry_sdk should guard
# on HAS_SENTRY first.
try:
    import sentry_sdk  # type: ignore
    HAS_SENTRY = True
except ImportError:
    sentry_sdk = None  # type: ignore
    HAS_SENTRY = False


class Events(str, Enum):
    """Pre-defined business events to track"""

    # User Events
    USER_REGISTERED = "user.registered"
    USER_UPGRADED = "user.upgraded"
    USER_DOWNGRADED = "user.downgraded"

    # Product Events
    PRODUCT_DEPLOYED = "product.deployed"
    PRODUCT_REMOVED = "product.removed"
    PRODUCT_OUT_OF_STOCK = "product.out_of_stock"

    # Order Events
    ORDER_CREATED = "order.created"
    ORDER_FULFILLED = "order.fulfilled"
    ORDER_REFUNDED = "order.refunded"

    # Action Events
    ACTION_APPROVED = "action.approved"
    ACTION_SKIPPED = "action.skipped"
    ACTION_EXECUTED = "action.executed"
    ACTION_FAILED = "action.failed"
    ACTION_UNDONE = "action.undone"

    # Email Events
    EMAIL_SENT = "email.sent"
    EMAIL_DELIVERED = "email.delivered"
    EMAIL_BOUNCED = "email.bounced"

    # Ad Events
    AD_CAMPAIGN_LAUNCHED = "ad.campaign_launched"
    AD_CAMPAIGN_PAUSED = "ad.campaign_paused"
    AD_BUDGET_EXHAUSTED = "ad.budget_exhausted"


class Metrics(str, Enum):
    """Pre-defined metrics to track"""

    # Performance
    API_REQUEST_DURATION = "api.request.duration"
    DATABASE_QUERY_DURATION = "database.query.duration"
    EXTERNAL_API_DURATION = "external.api.duration"

    # Business
    REVENUE = "business.revenue"
    PROFIT_MARGIN = "business.profit_margin"
    CONVERSION_RATE = "business.conversion_rate"

    # AI Usage
    AI_REQUESTS = "ai.requests"
    AI_COST = "ai.cost"
    AI_TOKENS_USED = "ai.tokens_used"

    # Actions
    ACTIONS_CREATED = "actions.created"
    ACTIONS_APPROVED = "actions.approved"
    ACTIONS_EXECUTED = "actions.executed"

    # Errors
    ERROR_RATE = "errors.rate"
    ERROR_COUNT = "errors.count"


class MetricsClient:
    """
    Client for tracking custom metrics and events.

    Sends events to Sentry and can be extended to support
    other analytics platforms (Mixpanel, Amplitude, etc.)
    """

    def __init__(self):
        # Auto-disable when sentry_sdk isn't installed so every track/incr
        # becomes a no-op instead of raising.
        self.enabled = HAS_SENTRY

    def track_event(
        self,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Track a business event.

        Args:
            event_name: Event name (use Events enum)
            properties: Event properties/context
            user_id: User ID associated with event
            timestamp: Event timestamp (defaults to now)

        Usage:
            track_event(
                Events.PRODUCT_DEPLOYED,
                properties={
                    "product_id": 123,
                    "platform": "shopify",
                    "price": 29.99
                },
                user_id=456
            )
        """

        if not self.enabled:
            return

        properties = properties or {}
        timestamp = timestamp or datetime.now(timezone.utc)

        # Add metadata
        properties["timestamp"] = timestamp.isoformat()
        if user_id:
            properties["user_id"] = user_id

        # Send to Sentry as custom event
        with sentry_sdk.push_scope() as scope:
            scope.set_context("event_properties", properties)
            scope.set_tag("event_name", event_name)
            if user_id:
                scope.set_user({"id": user_id})

            sentry_sdk.capture_message(
                f"Event: {event_name}",
                level="info"
            )

    def increment_counter(
        self,
        metric_name: str,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None
    ):
        """
        Increment a counter metric.

        Args:
            metric_name: Metric name (use Metrics enum)
            value: Value to increment by (default 1.0)
            tags: Tags for filtering/grouping

        Usage:
            increment_counter(
                Metrics.ACTIONS_EXECUTED,
                value=1,
                tags={"action_type": "deploy_product"}
            )
        """

        if not self.enabled:
            return

        tags = tags or {}

        # Send to Sentry as metric
        sentry_sdk.metrics.incr(
            key=metric_name,
            value=value,
            tags=tags
        )

    def record_gauge(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """
        Record a gauge metric (point-in-time value).

        Args:
            metric_name: Metric name
            value: Current value
            tags: Tags for filtering/grouping

        Usage:
            record_gauge(
                Metrics.AI_COST,
                value=12.45,
                tags={"user_id": "123", "model": "gpt-4"}
            )
        """

        if not self.enabled:
            return

        tags = tags or {}

        sentry_sdk.metrics.gauge(
            key=metric_name,
            value=value,
            tags=tags
        )

    def record_distribution(
        self,
        metric_name: str,
        value: float,
        unit: str = "millisecond",
        tags: Optional[Dict[str, str]] = None
    ):
        """
        Record a distribution metric (for timing, sizes, etc.).

        Args:
            metric_name: Metric name
            value: Measured value
            unit: Unit of measurement (millisecond, byte, etc.)
            tags: Tags for filtering/grouping

        Usage:
            record_distribution(
                Metrics.API_REQUEST_DURATION,
                value=245.3,
                unit="millisecond",
                tags={"endpoint": "/api/products"}
            )
        """

        if not self.enabled:
            return

        tags = tags or {}

        sentry_sdk.metrics.distribution(
            key=metric_name,
            value=value,
            unit=unit,
            tags=tags
        )


# Global metrics client instance
_metrics_client = MetricsClient()


def track_event(
    event_name: str,
    properties: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None
):
    """
    Convenience function for tracking events.

    Usage:
        from ospra_os.observability import track_event, Events

        track_event(
            Events.ACTION_EXECUTED,
            properties={"action_id": 123, "success": True},
            user_id=456
        )
    """
    _metrics_client.track_event(event_name, properties, user_id)


def increment_counter(
    metric_name: str,
    value: float = 1.0,
    tags: Optional[Dict[str, str]] = None
):
    """
    Convenience function for incrementing counters.

    Usage:
        from ospra_os.observability import increment_counter, Metrics

        increment_counter(
            Metrics.ACTIONS_CREATED,
            tags={"action_type": "deploy_product"}
        )
    """
    _metrics_client.increment_counter(metric_name, value, tags)
