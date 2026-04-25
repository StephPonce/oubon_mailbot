"""
Sentry Error Tracking Integration
Provides centralized error tracking, alerting, and performance monitoring.

Sentry SDK is treated as an optional dependency: if `sentry_sdk` isn't
installed (e.g. lean test environments), every public function in this module
becomes a no-op so that importing this module never breaks application boot
or test collection. Setup is gated on the DSN being present in production.
"""

from typing import Optional, Dict, Any
from enum import Enum

try:
    import sentry_sdk  # type: ignore
    from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration  # type: ignore
    from sentry_sdk.integrations.httpx import HttpxIntegration  # type: ignore
    HAS_SENTRY = True
except ImportError:
    sentry_sdk = None  # type: ignore
    FastApiIntegration = None  # type: ignore
    SqlalchemyIntegration = None  # type: ignore
    HttpxIntegration = None  # type: ignore
    HAS_SENTRY = False


class ErrorSeverity(str, Enum):
    """Error severity levels for Sentry"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


def setup_sentry(
    dsn: str,
    environment: str = "production",
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
    enable_tracing: bool = True
):
    """
    Initialize Sentry SDK for error tracking and performance monitoring.

    Args:
        dsn: Sentry Data Source Name (DSN) from Sentry project settings
        environment: Deployment environment (production, staging, development)
        traces_sample_rate: Percentage of transactions to trace (0.0-1.0)
        profiles_sample_rate: Percentage of transactions to profile (0.0-1.0)
        enable_tracing: Enable performance monitoring

    Usage:
        setup_sentry(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=0.1  # 10% of requests
        )
    """

    if not HAS_SENTRY:
        print("[WARNING]  sentry_sdk not installed - error tracking disabled")
        return

    if not dsn:
        print("[WARNING]  Sentry DSN not provided - error tracking disabled")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,

        # Integrations
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            HttpxIntegration(),
        ],

        # Performance Monitoring
        enable_tracing=enable_tracing,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,

        # Release tracking (set via CI/CD)
        # release="ospra-os@1.2.3",

        # PII filtering
        send_default_pii=False,

        # Filter out health check transactions
        before_send_transaction=_filter_transactions,

        # Filter sensitive data
        before_send=_filter_events,
    )

    print(f"[SUCCESS] Sentry initialized: environment={environment}, tracing={enable_tracing}")


def _filter_transactions(event, hint):
    """Filter out noise from transaction tracking"""
    url_string = event.get("request", {}).get("url", "")

    # Ignore health checks
    if "/health" in url_string or "/metrics" in url_string:
        return None

    return event


def _filter_events(event, hint):
    """Filter sensitive data from error events"""
    # Remove sensitive request data
    if "request" in event:
        request = event["request"]

        # Redact authorization headers
        if "headers" in request:
            headers = request["headers"]
            if "Authorization" in headers:
                headers["Authorization"] = "[Filtered]"
            if "Cookie" in headers:
                headers["Cookie"] = "[Filtered]"

    return event


def capture_exception(
    error: Exception,
    level: ErrorSeverity = ErrorSeverity.ERROR,
    extra: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None,
    user: Optional[Dict[str, Any]] = None
):
    """
    Capture an exception and send to Sentry.

    Args:
        error: The exception to capture
        level: Severity level
        extra: Additional context data
        tags: Tags for filtering/grouping
        user: User context (id, email, username)

    Usage:
        try:
            risky_operation()
        except Exception as e:
            capture_exception(
                e,
                level=ErrorSeverity.ERROR,
                extra={"order_id": 123, "user_id": 456},
                tags={"feature": "checkout"}
            )
    """

    if not HAS_SENTRY:
        return

    with sentry_sdk.push_scope() as scope:
        # Set severity
        scope.level = level.value

        # Add extra context
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)

        # Add tags
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)

        # Set user context
        if user:
            scope.user = user

        # Capture the exception
        sentry_sdk.capture_exception(error)


def capture_message(
    message: str,
    level: ErrorSeverity = ErrorSeverity.INFO,
    extra: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None
):
    """
    Capture a message (non-exception event) and send to Sentry.

    Args:
        message: Message to capture
        level: Severity level
        extra: Additional context data
        tags: Tags for filtering/grouping

    Usage:
        capture_message(
            "Unusual activity detected",
            level=ErrorSeverity.WARNING,
            extra={"ip_address": "1.2.3.4", "failed_attempts": 5}
        )
    """

    if not HAS_SENTRY:
        return

    with sentry_sdk.push_scope() as scope:
        scope.level = level.value

        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)

        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)

        sentry_sdk.capture_message(message)


def set_user_context(user_id: int, email: Optional[str] = None, username: Optional[str] = None):
    """
    Set user context for error tracking.

    Args:
        user_id: User ID
        email: User email (optional)
        username: Username (optional)

    Usage:
        set_user_context(user_id=123, email="user@example.com")
    """

    if not HAS_SENTRY:
        return
    sentry_sdk.set_user({
        "id": user_id,
        "email": email,
        "username": username
    })


def add_breadcrumb(
    message: str,
    category: str = "default",
    level: str = "info",
    data: Optional[Dict[str, Any]] = None
):
    """
    Add a breadcrumb (trail of events leading to an error).

    Args:
        message: Breadcrumb message
        category: Event category (e.g., "auth", "database", "api")
        level: Severity (debug, info, warning, error)
        data: Additional data

    Usage:
        add_breadcrumb(
            message="User login attempt",
            category="auth",
            level="info",
            data={"method": "oauth", "provider": "google"}
        )
    """

    if not HAS_SENTRY:
        return
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data or {}
    )


def start_transaction(name: str, op: str = "http.server") -> Any:
    """
    Start a performance monitoring transaction.

    Args:
        name: Transaction name (e.g., "POST /api/products")
        op: Operation type (e.g., "http.server", "db.query")

    Returns:
        Transaction object (use as context manager)

    Usage:
        with start_transaction(name="process_order", op="task"):
            # ... expensive operation ...
            pass
    """
    if not HAS_SENTRY:
        return _NullSpan()
    return sentry_sdk.start_transaction(name=name, op=op)


def start_span(description: str, op: str = "function") -> Any:
    """
    Start a performance monitoring span within a transaction.

    Args:
        description: Span description (e.g., "Fetch product from database")
        op: Operation type (e.g., "db.query", "http.client")

    Returns:
        Span object (use as context manager)

    Usage:
        with start_transaction(name="process_order"):
            with start_span(description="Validate payment", op="validation"):
                validate_payment()
            with start_span(description="Update inventory", op="db.query"):
                update_inventory()
    """
    if not HAS_SENTRY:
        return _NullSpan()
    return sentry_sdk.start_span(description=description, op=op)


class _NullSpan:
    """No-op context manager returned when Sentry SDK isn't installed.

    Allows callers to use `with start_transaction(...)` / `with start_span(...)`
    without crashing when Sentry is disabled.
    """
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def set_tag(self, *_args, **_kwargs):
        pass

    def set_data(self, *_args, **_kwargs):
        pass

    def set_status(self, *_args, **_kwargs):
        pass
