"""
Structured Logging with Context
Provides JSON-formatted logging with request-scoped context propagation.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Request-scoped context storage
_log_context: ContextVar[Dict[str, Any]] = ContextVar('log_context', default={})


class LogContext:
    """
    Request-scoped logging context manager.

    Usage:
        with LogContext(user_id=123, store_id=456):
            logger.info("Processing order")  # Includes user_id and store_id
    """

    def __init__(self, **kwargs):
        self.context = kwargs
        self.token = None

    def __enter__(self):
        current = _log_context.get().copy()
        current.update(self.context)
        self.token = _log_context.set(current)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _log_context.reset(self.token)


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs logs as JSON objects with consistent fields:
    - timestamp (ISO 8601)
    - level (INFO, ERROR, etc.)
    - logger (module name)
    - message
    - context (request-scoped context)
    - extra (additional fields)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request-scoped context
        context = _log_context.get()
        if context:
            log_data["context"] = context

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        extra = {}
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'lineno', 'module', 'msecs', 'message',
                'pathname', 'process', 'processName', 'relativeCreated',
                'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info'
            ]:
                extra[key] = value

        if extra:
            log_data["extra"] = extra

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable formatter for console output.

    Formats logs with colors and readable structure:
    2024-12-11 10:30:45 | INFO | module.name | Message here [context]
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']

        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')

        message = f"{timestamp} | {color}{record.levelname:8}{reset} | {record.name:30} | {record.getMessage()}"

        # Add context if present
        context = _log_context.get()
        if context:
            message += f" {color}[{json.dumps(context)}]{reset}"

        # Add exception if present
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"

        return message


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None
):
    """
    Configure application logging.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "console")
        log_file: Optional file path for log output
    """

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Choose formatter
    if log_format == "json":
        formatter = StructuredFormatter()
    else:
        formatter = ConsoleFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())  # Always use JSON for files
        root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    root_logger.info(f"Logging configured: level={log_level}, format={log_format}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance

    Usage:
        logger = get_logger(__name__)
        logger.info("Processing started", extra={"order_id": 123})
    """
    return logging.getLogger(name)
