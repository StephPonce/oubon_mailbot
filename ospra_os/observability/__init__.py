"""
Observability Module - Logging, Error Tracking, Metrics
Provides centralized observability for OspraOS platform.
"""

from .logger import get_logger, setup_logging, LogContext
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
