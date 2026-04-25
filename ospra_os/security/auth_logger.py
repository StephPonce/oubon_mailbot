"""
Security Logging for Authentication Events
==========================================
Logs all authentication attempts, failures, and suspicious activity.

Audit fixes (2026-04):
  - The ``FileHandler("logs/security.log")`` used to be initialised at
    module import time. On a fresh container without a ``logs/``
    directory (e.g. Render's first cold boot) this raised
    ``FileNotFoundError`` *during import*, taking down ``ospra_os.auth``
    along with it — auth logging deserves attention, but it shouldn't
    crash the whole auth subsystem. We now create the directory if it
    doesn't exist and fall back to stderr-only logging if file logging
    isn't available (see ``_attach_file_handler``).
  - ``AuthEvent.timestamp = datetime.now(timezone.utc)`` was a Pydantic field
    *default value* — that expression evaluates ONCE at class-load time
    and freezes the timestamp for every instance for the life of the
    process. A login at 3 AM tomorrow would have logged a timestamp from
    last Tuesday. Fixed to ``Field(default_factory=...)``.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# Configure security logger - separate from application logs
security_logger = logging.getLogger("ospra_os.security")
security_logger.setLevel(logging.INFO)


def _attach_file_handler(log_path: Path) -> Optional[logging.Handler]:
    """
    Attempt to attach a ``FileHandler`` for ``log_path``, creating the
    parent directory if needed. Returns the handler on success, ``None``
    on failure (in which case the caller should fall back to stderr).

    We never raise from import time. If the filesystem is read-only or
    the directory can't be created, security logging silently degrades to
    stderr — the application keeps serving traffic, and the operator
    sees a clear ``logger.warning`` in stdout.
    """
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(log_path))
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - SECURITY - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        return handler
    except (OSError, PermissionError) as exc:
        logging.getLogger(__name__).warning(
            "auth_logger: file logging disabled — could not open %s (%s). "
            "Security events will still appear on stderr.",
            log_path, exc,
        )
        return None


# Honour an env override so prod / Render deployments can point this at a
# writable mount (or /dev/null if they ship security events via a
# structured-logging pipeline instead).
_LOG_PATH = Path(os.getenv("OSPRA_SECURITY_LOG_PATH") or "logs/security.log")
_file_handler = _attach_file_handler(_LOG_PATH)
if _file_handler is not None:
    security_logger.addHandler(_file_handler)


class AuthEvent(BaseModel):
    """Authentication event data model"""
    event_type: str  # login_success, login_failure, token_refresh, logout
    user_id: Optional[int] = None
    email: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    tier: Optional[str] = None
    reason: Optional[str] = None  # For failures
    # ``default_factory`` evaluates per-instance at construction time;
    # the previous ``= datetime.now(timezone.utc)`` form evaluated once at import
    # and froze the same timestamp on every ``AuthEvent`` ever created.
    # Also switched to a tz-aware UTC stamp so downstream consumers don't
    # have to guess at offset.
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def log_login_success(user_id: int, email: str, ip_address: str, tier: str, user_agent: Optional[str] = None) -> None:
    """Log successful login attempt."""
    security_logger.info(
        f"LOGIN_SUCCESS | user_id={user_id} | email={email} | "
        f"ip={ip_address} | tier={tier} | user_agent={user_agent}"
    )


def log_login_failure(email: str, ip_address: str, reason: str, user_agent: Optional[str] = None) -> None:
    """Log failed login attempt - CRITICAL for security monitoring."""
    security_logger.warning(
        f"LOGIN_FAILURE | email={email} | ip={ip_address} | "
        f"reason={reason} | user_agent={user_agent}"
    )


def log_token_refresh(user_id: int, email: str, ip_address: str, tier: str) -> None:
    """Log token refresh event."""
    security_logger.info(
        f"TOKEN_REFRESH | user_id={user_id} | email={email} | "
        f"ip={ip_address} | tier={tier}"
    )


def log_logout(user_id: int, email: str, ip_address: str) -> None:
    """Log logout event."""
    security_logger.info(
        f"LOGOUT | user_id={user_id} | email={email} | ip={ip_address}"
    )


def log_suspicious_activity(event_type: str, details: str, ip_address: str, user_agent: Optional[str] = None) -> None:
    """Log suspicious activity - CRITICAL for security monitoring."""
    security_logger.error(
        f"SUSPICIOUS_ACTIVITY | type={event_type} | details={details} | "
        f"ip={ip_address} | user_agent={user_agent}"
    )


def log_rate_limit_exceeded(ip_address: str, endpoint: str, user_id: Optional[int] = None) -> None:
    """Log rate limit violations - May indicate attack or misconfiguration."""
    security_logger.warning(
        f"RATE_LIMIT_EXCEEDED | ip={ip_address} | endpoint={endpoint} | user_id={user_id}"
    )


def log_permission_denied(user_id: int, email: str, tier: str, resource: str, ip_address: str) -> None:
    """Log permission denied events - Track tier enforcement."""
    security_logger.warning(
        f"PERMISSION_DENIED | user_id={user_id} | email={email} | "
        f"tier={tier} | resource={resource} | ip={ip_address}"
    )
