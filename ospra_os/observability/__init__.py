"""
Observability Module - Logging, Error Tracking, Metrics
Provides centralized observability for OspraOS platform.
"""

from .logger import get_logger, setup_logging, LogContext
from .request_tracing import (
    RequestTracingMiddleware,
    get_request_id,
    get_request_context,
    TracingLogger,
    trace_function,
)
from .logging_config import (
    setup_logging as setup_structured_logging,
    StructuredLogger,
    log_performance,
)
from .error_tracking import (
    setup_sentry,
    capture_exception,
    capture_message,
    set_user_context,
    add_breadcrumb,
    ErrorSeverity
)
from .metrics import (
    MetricsClient,
    track_event,
    increment_counter,
    Events,
    Metrics
)

__all__ = [
    # Logging
    "get_logger",
    "setup_logging",
    "LogContext",
    "setup_structured_logging",
    "StructuredLogger",
    "log_performance",

    # Request Tracing
    "RequestTracingMiddleware",
    "get_request_id",
    "get_request_context",
    "TracingLogger",
    "trace_function",

    # Error Tracking
    "setup_sentry",
    "capture_exception",
    "capture_message",
    "set_user_context",
    "add_breadcrumb",
    "ErrorSeverity",

    # Metrics
    "MetricsClient",
    "track_event",
    "increment_counter",
    "Events",
    "Metrics",
]
