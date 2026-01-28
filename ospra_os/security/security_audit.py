"""
Security Audit Logging for Ospra OS
====================================

Dedicated audit logging for security-sensitive operations.

Unlike tenant audit logs (ospra_os/tenancy/audit.py), this module:
- Does NOT require tenant context (works for auth events)
- Focuses on security-sensitive actions
- Has stricter retention (never auto-deleted)
- Includes threat indicators

Actions logged:
- Authentication (login, logout, token refresh)
- Password changes/resets
- Credential storage/access
- API key operations
- Tier changes
- Account linking (OAuth)
- Failed access attempts

Author: Ospra OS Security
Date: January 2025
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Boolean, Index
from sqlalchemy.orm import Session

from ospra_os.database import Base, SessionLocal

logger = logging.getLogger(__name__)


# ============================================================================
# SECURITY EVENT TYPES
# ============================================================================

class SecurityEventType(str, Enum):
    """Categories of security events."""
    # Authentication
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    LOGOUT = "auth.logout"
    TOKEN_REFRESH = "auth.token.refresh"
    TOKEN_REVOKED = "auth.token.revoked"

    # Password management
    PASSWORD_CHANGED = "password.changed"
    PASSWORD_RESET_REQUESTED = "password.reset.requested"
    PASSWORD_RESET_COMPLETED = "password.reset.completed"
    PASSWORD_RESET_FAILED = "password.reset.failed"

    # Credential operations
    CREDENTIAL_STORED = "credential.stored"
    CREDENTIAL_ACCESSED = "credential.accessed"
    CREDENTIAL_DELETED = "credential.deleted"
    CREDENTIAL_ROTATED = "credential.rotated"

    # API key management
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    API_KEY_USED = "api_key.used"

    # OAuth operations
    OAUTH_INITIATED = "oauth.initiated"
    OAUTH_COMPLETED = "oauth.completed"
    OAUTH_FAILED = "oauth.failed"
    OAUTH_REVOKED = "oauth.revoked"

    # Account changes
    TIER_CHANGED = "account.tier.changed"
    EMAIL_CHANGED = "account.email.changed"
    ACCOUNT_LOCKED = "account.locked"
    ACCOUNT_UNLOCKED = "account.unlocked"

    # Access control
    ACCESS_DENIED = "access.denied"
    TIER_LIMIT_HIT = "access.tier_limit"
    RATE_LIMIT_HIT = "access.rate_limit"

    # Administrative
    ADMIN_ACTION = "admin.action"
    DATA_EXPORT = "data.export"
    DATA_DELETION = "data.deletion"


class SecuritySeverity(str, Enum):
    """Severity levels for security events."""
    LOW = "low"          # Normal operations
    MEDIUM = "medium"    # Worth monitoring
    HIGH = "high"        # Requires attention
    CRITICAL = "critical"  # Immediate action needed


# ============================================================================
# SECURITY AUDIT LOG MODEL
# ============================================================================

class SecurityAuditLog(Base):
    """
    Security-focused audit log.

    RETENTION: These logs should NEVER be auto-deleted.
    Required for compliance (SOC2, GDPR, etc.)
    """
    __tablename__ = "security_audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Event identification
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="low", index=True)

    # Actor (who performed the action)
    user_id = Column(Integer, nullable=True, index=True)  # May be null for failed logins
    user_email = Column(String(255), nullable=True)  # For audit trail when user deleted
    actor_type = Column(String(50), nullable=True)  # "user", "system", "admin", "api"

    # Target (what was affected)
    target_type = Column(String(50), nullable=True)  # "user", "store", "credential"
    target_id = Column(Integer, nullable=True)
    target_identifier = Column(String(255), nullable=True)  # email, store name, etc.

    # Request context
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    request_path = Column(String(255), nullable=True)
    request_method = Column(String(10), nullable=True)

    # Event details
    success = Column(Boolean, nullable=False, default=True)
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)  # Additional context

    # Threat indicators
    is_suspicious = Column(Boolean, nullable=False, default=False, index=True)
    threat_indicators = Column(JSON, nullable=True)  # Why it's suspicious

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_security_audit_user_event', 'user_id', 'event_type'),
        Index('ix_security_audit_ip_created', 'ip_address', 'created_at'),
        Index('ix_security_audit_suspicious', 'is_suspicious', 'created_at'),
    )

    def __repr__(self) -> str:
        return (
            f"<SecurityAuditLog(id={self.id}, event={self.event_type}, "
            f"user_id={self.user_id}, success={self.success})>"
        )


# ============================================================================
# SECURITY AUDIT FUNCTIONS
# ============================================================================

def log_security_event(
    event_type: SecurityEventType,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    target_identifier: Optional[str] = None,
    success: bool = True,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    severity: SecuritySeverity = SecuritySeverity.LOW,
    request: Optional[Any] = None,
    db: Optional[Session] = None,
    is_suspicious: bool = False,
    threat_indicators: Optional[list] = None,
) -> Optional[SecurityAuditLog]:
    """
    Log a security event.

    Args:
        event_type: Type of security event
        user_id: ID of user performing/affected by action
        user_email: Email for audit trail
        target_type: Type of resource affected
        target_id: ID of resource affected
        target_identifier: Human-readable identifier
        success: Whether operation succeeded
        message: Human-readable description
        details: Additional context (will be stored as JSON)
        severity: Event severity level
        request: FastAPI Request object
        db: Database session (will create one if not provided)
        is_suspicious: Flag for suspicious activity
        threat_indicators: List of reasons why activity is suspicious

    Returns:
        Created audit log entry, or None if logging failed

    Example:
        # Log successful login
        log_security_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user_id=user.id,
            user_email=user.email,
            request=request,
            message="User logged in successfully"
        )

        # Log credential access
        log_security_event(
            event_type=SecurityEventType.CREDENTIAL_ACCESSED,
            user_id=current_user.id,
            target_type="store",
            target_id=store.id,
            target_identifier=store.name,
            details={"purpose": "API call to Shopify"}
        )
    """
    # Create or use existing session
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        # Extract request context
        ip_address = None
        user_agent = None
        request_path = None
        request_method = None

        if request:
            request_method = getattr(request, 'method', None)
            request_path = str(request.url.path) if hasattr(request, 'url') else None

            # Get IP address (check proxy headers)
            if hasattr(request, 'headers'):
                forwarded_for = request.headers.get("X-Forwarded-For")
                if forwarded_for:
                    ip_address = forwarded_for.split(",")[0].strip()
                else:
                    real_ip = request.headers.get("X-Real-IP")
                    if real_ip:
                        ip_address = real_ip

                user_agent = request.headers.get("User-Agent")

            # Fallback to direct client IP
            if not ip_address and hasattr(request, 'client') and request.client:
                ip_address = request.client.host

        # Determine actor type
        actor_type = "user" if user_id else "anonymous"
        if details and details.get("actor_type"):
            actor_type = details.pop("actor_type")

        # Create audit log
        audit_log = SecurityAuditLog(
            event_type=event_type.value if isinstance(event_type, SecurityEventType) else event_type,
            severity=severity.value if isinstance(severity, SecuritySeverity) else severity,
            user_id=user_id,
            user_email=user_email,
            actor_type=actor_type,
            target_type=target_type,
            target_id=target_id,
            target_identifier=target_identifier,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            success=success,
            message=message,
            details=details,
            is_suspicious=is_suspicious,
            threat_indicators=threat_indicators,
        )

        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)

        # Log to application logger as well
        log_level = logging.INFO if success else logging.WARNING
        if severity == SecuritySeverity.HIGH:
            log_level = logging.WARNING
        elif severity == SecuritySeverity.CRITICAL:
            log_level = logging.ERROR

        logger.log(
            log_level,
            f"[SECURITY] {event_type.value if isinstance(event_type, SecurityEventType) else event_type} "
            f"user_id={user_id} success={success} ip={ip_address} "
            f"{'SUSPICIOUS' if is_suspicious else ''}"
        )

        return audit_log

    except Exception as e:
        logger.error(f"Failed to log security event: {e}")
        return None

    finally:
        if should_close_db:
            db.close()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def log_login_success(
    user_id: int,
    user_email: str,
    request: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Optional[SecurityAuditLog]:
    """Log a successful login."""
    return log_security_event(
        event_type=SecurityEventType.LOGIN_SUCCESS,
        user_id=user_id,
        user_email=user_email,
        message="User logged in successfully",
        request=request,
        db=db,
    )


def log_login_failed(
    email: str,
    reason: str = "Invalid credentials",
    request: Optional[Any] = None,
    db: Optional[Session] = None,
    is_suspicious: bool = False,
    threat_indicators: Optional[list] = None,
) -> Optional[SecurityAuditLog]:
    """Log a failed login attempt."""
    return log_security_event(
        event_type=SecurityEventType.LOGIN_FAILED,
        user_email=email,
        success=False,
        message=f"Login failed: {reason}",
        severity=SecuritySeverity.MEDIUM if is_suspicious else SecuritySeverity.LOW,
        request=request,
        db=db,
        is_suspicious=is_suspicious,
        threat_indicators=threat_indicators,
    )


def log_password_reset_requested(
    email: str,
    user_id: Optional[int] = None,
    request: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Optional[SecurityAuditLog]:
    """Log a password reset request."""
    return log_security_event(
        event_type=SecurityEventType.PASSWORD_RESET_REQUESTED,
        user_id=user_id,
        user_email=email,
        message="Password reset requested",
        severity=SecuritySeverity.MEDIUM,
        request=request,
        db=db,
    )


def log_password_changed(
    user_id: int,
    user_email: str,
    via_reset: bool = False,
    request: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Optional[SecurityAuditLog]:
    """Log a password change."""
    return log_security_event(
        event_type=SecurityEventType.PASSWORD_CHANGED,
        user_id=user_id,
        user_email=user_email,
        message=f"Password changed {'via reset link' if via_reset else 'by user'}",
        severity=SecuritySeverity.MEDIUM,
        details={"via_reset": via_reset},
        request=request,
        db=db,
    )


def log_credential_stored(
    user_id: int,
    credential_type: str,
    store_id: Optional[int] = None,
    store_name: Optional[str] = None,
    request: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Optional[SecurityAuditLog]:
    """Log when credentials are stored (encrypted)."""
    return log_security_event(
        event_type=SecurityEventType.CREDENTIAL_STORED,
        user_id=user_id,
        target_type="store" if store_id else "credential",
        target_id=store_id,
        target_identifier=store_name,
        message=f"Stored encrypted {credential_type} credentials",
        details={"credential_type": credential_type},
        request=request,
        db=db,
    )


def log_credential_accessed(
    user_id: int,
    credential_type: str,
    store_id: Optional[int] = None,
    store_name: Optional[str] = None,
    purpose: Optional[str] = None,
    request: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Optional[SecurityAuditLog]:
    """Log when credentials are accessed (decrypted)."""
    return log_security_event(
        event_type=SecurityEventType.CREDENTIAL_ACCESSED,
        user_id=user_id,
        target_type="store" if store_id else "credential",
        target_id=store_id,
        target_identifier=store_name,
        message=f"Accessed {credential_type} credentials" + (f" for {purpose}" if purpose else ""),
        details={"credential_type": credential_type, "purpose": purpose},
        request=request,
        db=db,
    )


def log_oauth_completed(
    user_id: int,
    provider: str,
    store_id: Optional[int] = None,
    store_name: Optional[str] = None,
    request: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Optional[SecurityAuditLog]:
    """Log successful OAuth connection."""
    return log_security_event(
        event_type=SecurityEventType.OAUTH_COMPLETED,
        user_id=user_id,
        target_type="store",
        target_id=store_id,
        target_identifier=store_name,
        message=f"Connected {provider} account via OAuth",
        details={"provider": provider},
        request=request,
        db=db,
    )


def log_tier_changed(
    user_id: int,
    user_email: str,
    old_tier: str,
    new_tier: str,
    request: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Optional[SecurityAuditLog]:
    """Log subscription tier change."""
    return log_security_event(
        event_type=SecurityEventType.TIER_CHANGED,
        user_id=user_id,
        user_email=user_email,
        message=f"Subscription changed from {old_tier} to {new_tier}",
        details={"old_tier": old_tier, "new_tier": new_tier},
        request=request,
        db=db,
    )


def log_access_denied(
    user_id: Optional[int],
    resource: str,
    reason: str,
    request: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Optional[SecurityAuditLog]:
    """Log access denial."""
    return log_security_event(
        event_type=SecurityEventType.ACCESS_DENIED,
        user_id=user_id,
        success=False,
        message=f"Access denied to {resource}: {reason}",
        severity=SecuritySeverity.MEDIUM,
        details={"resource": resource, "reason": reason},
        request=request,
        db=db,
    )


# ============================================================================
# QUERY FUNCTIONS
# ============================================================================

def get_user_security_events(
    db: Session,
    user_id: int,
    event_types: Optional[list] = None,
    limit: int = 100,
    include_suspicious_only: bool = False,
) -> list:
    """Get security events for a user."""
    query = db.query(SecurityAuditLog).filter(
        SecurityAuditLog.user_id == user_id
    )

    if event_types:
        type_values = [et.value if isinstance(et, SecurityEventType) else et for et in event_types]
        query = query.filter(SecurityAuditLog.event_type.in_(type_values))

    if include_suspicious_only:
        query = query.filter(SecurityAuditLog.is_suspicious == True)

    return query.order_by(SecurityAuditLog.created_at.desc()).limit(limit).all()


def get_failed_logins_by_ip(
    db: Session,
    ip_address: str,
    since_hours: int = 24,
    limit: int = 100,
) -> list:
    """Get failed login attempts from an IP address."""
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(hours=since_hours)

    return db.query(SecurityAuditLog).filter(
        SecurityAuditLog.ip_address == ip_address,
        SecurityAuditLog.event_type == SecurityEventType.LOGIN_FAILED.value,
        SecurityAuditLog.created_at >= since,
    ).order_by(SecurityAuditLog.created_at.desc()).limit(limit).all()


def get_suspicious_events(
    db: Session,
    since_hours: int = 24,
    limit: int = 100,
) -> list:
    """Get recent suspicious security events."""
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(hours=since_hours)

    return db.query(SecurityAuditLog).filter(
        SecurityAuditLog.is_suspicious == True,
        SecurityAuditLog.created_at >= since,
    ).order_by(SecurityAuditLog.created_at.desc()).limit(limit).all()


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "SecurityEventType",
    "SecuritySeverity",
    # Model
    "SecurityAuditLog",
    # Main function
    "log_security_event",
    # Convenience functions
    "log_login_success",
    "log_login_failed",
    "log_password_reset_requested",
    "log_password_changed",
    "log_credential_stored",
    "log_credential_accessed",
    "log_oauth_completed",
    "log_tier_changed",
    "log_access_denied",
    # Query functions
    "get_user_security_events",
    "get_failed_logins_by_ip",
    "get_suspicious_events",
]
