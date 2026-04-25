"""
Logging Configuration for Ospra OS
==================================

Centralized logging setup with structured logging, rotation, and observability.

Features:
- JSON structured logging for production
- Human-readable logs for development
- Log rotation and retention
- Request context inclusion
- Performance metrics logging

Usage:
    from ospra_os.observability.logging_config import setup_logging

    # Call at app startup
    setup_logging()

Author: OspraOS
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pathlib import Path


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default log level
DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Log file settings
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = os.getenv("LOG_FILE", "ospra.log")
MAX_LOG_SIZE = int(os.getenv("MAX_LOG_SIZE_MB", "50")) * 1024 * 1024  # Default 50MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# JSON logging in production
USE_JSON_LOGS = os.getenv("JSON_LOGS", "").lower() == "true"


# =============================================================================
# FORMATTERS
# =============================================================================

class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs logs in JSON format for easy parsing by log aggregators
    like Datadog, Splunk, or ELK.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add request context if available
        try:
            from ospra_os.observability.request_tracing import get_request_id, get_request_context
            request_id = get_request_id()
            if request_id:
                log_data["request_id"] = request_id

            request_context = get_request_context()
            if request_context:
                log_data["request_context"] = request_context
        except ImportError:
            pass

        # Add any extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """
    Colored formatter for development console output.

    Makes logs easier to read in terminal with color coding by level.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Add color to level name
        color = self.COLORS.get(record.levelname, "")

        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Try to get request ID
        request_id = ""
        try:
            from ospra_os.observability.request_tracing import get_request_id
            rid = get_request_id()
            if rid:
                request_id = f"[{rid}] "
        except ImportError:
            pass

        # Build formatted message
        level_padded = record.levelname.ljust(8)
        message = record.getMessage()

        formatted = f"{color}{timestamp} {level_padded}{self.RESET} {request_id}{message}"

        # Add exception if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


# =============================================================================
# SETUP FUNCTIONS
# =============================================================================

def setup_logging(
    level: Optional[str] = None,
    json_logs: Optional[bool] = None,
    log_file: Optional[str] = None
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Force JSON logging (default: auto-detect from env)
        log_file: Path to log file (default: from LOG_FILE env)
    """
    # Determine settings
    log_level = getattr(logging, level or DEFAULT_LOG_LEVEL, logging.INFO)
    use_json = json_logs if json_logs is not None else USE_JSON_LOGS

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if use_json:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColoredFormatter())

    root_logger.addHandler(console_handler)

    # File handler (if in production or explicitly configured)
    if log_file or (use_json and LOG_FILE):
        file_path = log_file or os.path.join(LOG_DIR, LOG_FILE)

        # Ensure log directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        # Use rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=MAX_LOG_SIZE,
            backupCount=LOG_BACKUP_COUNT
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(JSONFormatter())  # Always JSON for files

        root_logger.addHandler(file_handler)

    # Configure third-party loggers to be less verbose
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    logging.info(f"Logging configured: level={level or DEFAULT_LOG_LEVEL}, json={use_json}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    This is a convenience function that ensures logging is configured.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# =============================================================================
# CONTEXT LOGGING
# =============================================================================

class StructuredLogger:
    """
    Logger that supports structured fields.

    Usage:
        logger = StructuredLogger(__name__)
        logger.info("Processing order", order_id=123, customer="john@example.com")
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(self, level: int, message: str, **kwargs) -> None:
        """Internal logging with extra fields."""
        extra = {"extra_data": kwargs} if kwargs else {}
        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """Log an exception with traceback."""
        self._logger.exception(message, extra={"extra_data": kwargs} if kwargs else {})


# =============================================================================
# PERFORMANCE LOGGING
# =============================================================================

import time
from contextlib import contextmanager


@contextmanager
def log_performance(operation: str, logger: logging.Logger = None, threshold_ms: float = 100):
    """
    Context manager to log operation performance.

    Args:
        operation: Name of the operation being timed
        logger: Logger to use (default: root logger)
        threshold_ms: Only log if operation takes longer than this

    Usage:
        with log_performance("database_query"):
            result = db.execute(query)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    start_time = time.time()

    try:
        yield
    finally:
        elapsed_ms = (time.time() - start_time) * 1000

        if elapsed_ms >= threshold_ms:
            logger.info(f"Performance: {operation} took {elapsed_ms:.0f}ms")


def log_slow_query(query: str, duration_ms: float, threshold_ms: float = 100):
    """Log slow database queries."""
    if duration_ms >= threshold_ms:
        logger = logging.getLogger("ospra.database")
        logger.warning(
            f"Slow query ({duration_ms:.0f}ms): {query[:200]}..."
            if len(query) > 200 else f"Slow query ({duration_ms:.0f}ms): {query}"
        )


# =============================================================================
# INITIALIZATION
# =============================================================================

# Auto-setup logging when module is imported
_initialized = False

def ensure_logging_initialized():
    """Ensure logging is initialized (call from main.py startup)."""
    global _initialized
    if not _initialized:
        setup_logging()
        _initialized = True


logging.getLogger(__name__).info("[SUCCESS] Logging configuration module loaded")
