"""
Security Logging for Authentication Events
==========================================
Logs all authentication attempts, failures, and suspicious activity.
"""

import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

# Configure security logger - separate from application logs
security_logger = logging.getLogger("ospra_os.security")
security_logger.setLevel(logging.INFO)

# Create separate handler for security logs
security_handler = logging.FileHandler("logs/security.log")
security_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - SECURITY - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
)
security_logger.addHandler(security_handler)


class AuthEvent(BaseModel):
    """Authentication event data model"""
    event_type: str  # login_success, login_failure, token_refresh, logout
    user_id: Optional[int] = None
    email: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    tier: Optional[str] = None
    reason: Optional[str] = None  # For failures
    timestamp: datetime = datetime.utcnow()


def log_login_success(user_id: int, email: str, ip_address: str, tier: str, user_agent: Optional[str] = None):
    """Log successful login attempt"""
    security_logger.info(
        f"LOGIN_SUCCESS | user_id={user_id} | email={email} | "
        f"ip={ip_address} | tier={tier} | user_agent={user_agent}"
    )


def log_login_failure(email: str, ip_address: str, reason: str, user_agent: Optional[str] = None):
    """Log failed login attempt - CRITICAL for security monitoring"""
    security_logger.warning(
        f"LOGIN_FAILURE | email={email} | ip={ip_address} | "
        f"reason={reason} | user_agent={user_agent}"
    )


def log_token_refresh(user_id: int, email: str, ip_address: str, tier: str):
    """Log token refresh event"""
    security_logger.info(
        f"TOKEN_REFRESH | user_id={user_id} | email={email} | "
        f"ip={ip_address} | tier={tier}"
    )


def log_logout(user_id: int, email: str, ip_address: str):
    """Log logout event"""
    security_logger.info(
        f"LOGOUT | user_id={user_id} | email={email} | ip={ip_address}"
    )


def log_suspicious_activity(event_type: str, details: str, ip_address: str, user_agent: Optional[str] = None):
    """Log suspicious activity - CRITICAL for security monitoring"""
    security_logger.error(
        f"SUSPICIOUS_ACTIVITY | type={event_type} | details={details} | "
        f"ip={ip_address} | user_agent={user_agent}"
    )


def log_rate_limit_exceeded(ip_address: str, endpoint: str, user_id: Optional[int] = None):
    """Log rate limit violations - May indicate attack or misconfiguration"""
    security_logger.warning(
        f"RATE_LIMIT_EXCEEDED | ip={ip_address} | endpoint={endpoint} | user_id={user_id}"
    )


def log_permission_denied(user_id: int, email: str, tier: str, resource: str, ip_address: str):
    """Log permission denied events - Track tier enforcement"""
    security_logger.warning(
        f"PERMISSION_DENIED | user_id={user_id} | email={email} | "
        f"tier={tier} | resource={resource} | ip={ip_address}"
    )
