"""
Tenant Audit Logging - GROK RECOMMENDATION #14

Track all tenant operations for compliance and security.
Records: who accessed what, when, and from where.
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.orm import Session

from ospra_os.database.multi_store_models import Base
from ospra_os.tenancy.context import get_current_tenant, TenantContext


# ==================== AUDIT LOG MODEL ====================

class TenantAuditLog(Base):
    """
    Audit log for tenant operations.

    Records every significant operation performed by tenants for:
    - Compliance (GDPR, SOC2, etc.)
    - Security monitoring
    - Debugging and troubleshooting
    - Usage analytics
    """
    __tablename__ = "tenant_audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Tenant identification
    tenant_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    store_id = Column(Integer, nullable=True, index=True)

    # Action details
    action = Column(String(100), nullable=False, index=True)  # e.g., "product.create", "store.connect"
    resource_type = Column(String(50), nullable=True, index=True)  # e.g., "Product", "Store"
    resource_id = Column(Integer, nullable=True)  # ID of affected resource

    # Request context
    method = Column(String(10), nullable=True)  # HTTP method (GET, POST, etc.)
    path = Column(String(255), nullable=True)  # Request path
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)  # Browser/client info

    # Operation result
    status = Column(String(20), nullable=False, default="success")  # success, failure, error
    error_message = Column(Text, nullable=True)  # If failed, why?

    # Additional context
    audit_metadata = Column(JSON, nullable=True)  # Extra data as JSON

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self) -> str:
        return (
            f"<TenantAuditLog(id={self.id}, tenant_id={self.tenant_id}, "
            f"action={self.action}, status={self.status})>"
        )


# ==================== AUDIT LOGGING FUNCTIONS ====================

def log_tenant_action(
    db: Session,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request: Optional[Any] = None,
    tenant_override: Optional[TenantContext] = None
) -> TenantAuditLog:
    """
    Log a tenant action to audit trail.

    Args:
        db: Database session
        action: Action identifier (e.g., "product.create", "store.connect")
        resource_type: Type of resource affected (e.g., "Product", "Store")
        resource_id: ID of resource affected
        status: Operation status ("success", "failure", "error")
        error_message: Error description if failed
        metadata: Additional context as dict
        request: FastAPI Request object (to extract IP, user agent, path)
        tenant_override: Use specific tenant context (for background tasks)

    Returns:
        Created audit log entry

    Example:
        # In a route handler:
        @router.post("/products")
        def create_product(
            product: ProductCreate,
            tenant_db: TenantScopedSession = Depends(get_tenant_db),
            request: Request
        ):
            new_product = Product(**product.dict())
            tenant_db.add(new_product)
            tenant_db.commit()

            # Log the action
            log_tenant_action(
                db=tenant_db.raw_session,
                action="product.create",
                resource_type="Product",
                resource_id=new_product.id,
                metadata={"name": new_product.name, "price": new_product.price},
                request=request
            )

            return new_product
    """
    # Get tenant context
    tenant = tenant_override or get_current_tenant()

    if tenant is None:
        # No tenant context - can't log (or log as system?)
        raise RuntimeError("Cannot log tenant action without tenant context")

    # Extract request details
    method = None
    path = None
    ip_address = None
    user_agent = None

    if request:
        method = request.method
        path = str(request.url.path)

        # Get IP address
        # Check X-Forwarded-For header first (for proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP in comma-separated list
            ip_address = forwarded_for.split(",")[0].strip()
        else:
            # Use direct client IP
            if hasattr(request, "client") and request.client:
                ip_address = request.client.host

        # Get user agent
        user_agent = request.headers.get("User-Agent")

    # Create audit log entry
    audit_log = TenantAuditLog(
        tenant_id=tenant.tenant_id,
        user_id=tenant.user_id,
        store_id=tenant.store_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        method=method,
        path=path,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        error_message=error_message,
        audit_metadata=metadata
    )

    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    return audit_log


def log_success(
    db: Session,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request: Optional[Any] = None
) -> TenantAuditLog:
    """
    Log a successful tenant action.

    Convenience wrapper for log_tenant_action with status="success".
    """
    return log_tenant_action(
        db=db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status="success",
        metadata=metadata,
        request=request
    )


def log_failure(
    db: Session,
    action: str,
    error_message: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request: Optional[Any] = None
) -> TenantAuditLog:
    """
    Log a failed tenant action.

    Convenience wrapper for log_tenant_action with status="failure".
    """
    return log_tenant_action(
        db=db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status="failure",
        error_message=error_message,
        metadata=metadata,
        request=request
    )


def log_error(
    db: Session,
    action: str,
    error_message: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request: Optional[Any] = None
) -> TenantAuditLog:
    """
    Log an error during tenant action.

    Convenience wrapper for log_tenant_action with status="error".
    """
    return log_tenant_action(
        db=db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status="error",
        error_message=error_message,
        metadata=metadata,
        request=request
    )


# ==================== AUDIT LOG QUERIES ====================

def get_tenant_audit_logs(
    db: Session,
    tenant_id: int,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> list[TenantAuditLog]:
    """
    Retrieve audit logs for a tenant.

    Args:
        db: Database session
        tenant_id: Tenant to get logs for
        action: Filter by action (optional)
        resource_type: Filter by resource type (optional)
        status: Filter by status (optional)
        limit: Max number of logs to return
        offset: Number of logs to skip

    Returns:
        List of audit log entries
    """
    query = db.query(TenantAuditLog).filter(
        TenantAuditLog.tenant_id == tenant_id
    )

    if action:
        query = query.filter(TenantAuditLog.action == action)

    if resource_type:
        query = query.filter(TenantAuditLog.resource_type == resource_type)

    if status:
        query = query.filter(TenantAuditLog.status == status)

    # Order by most recent first
    query = query.order_by(TenantAuditLog.created_at.desc())

    # Apply pagination
    query = query.limit(limit).offset(offset)

    return query.all()


def get_resource_audit_trail(
    db: Session,
    tenant_id: int,
    resource_type: str,
    resource_id: int,
    limit: int = 50
) -> list[TenantAuditLog]:
    """
    Get full audit trail for a specific resource.

    Useful for viewing history of a product, store, campaign, etc.

    Args:
        db: Database session
        tenant_id: Tenant ID
        resource_type: Type of resource (e.g., "Product")
        resource_id: ID of resource
        limit: Max number of logs to return

    Returns:
        List of audit logs for this resource
    """
    return db.query(TenantAuditLog).filter(
        TenantAuditLog.tenant_id == tenant_id,
        TenantAuditLog.resource_type == resource_type,
        TenantAuditLog.resource_id == resource_id
    ).order_by(
        TenantAuditLog.created_at.desc()
    ).limit(limit).all()


# ==================== AUDIT LOG DECORATOR ====================

def audit_action(action: str, resource_type: Optional[str] = None):
    """
    Decorator to automatically audit route actions.

    Usage:
        @router.post("/products")
        @audit_action("product.create", "Product")
        def create_product(...):
            pass

    Note: This requires the route to have 'request' and 'db' dependencies.
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Extract dependencies
            request = kwargs.get("request")
            db = kwargs.get("db") or kwargs.get("tenant_db")

            # Get raw session if tenant_db
            if hasattr(db, "raw_session"):
                db_session = db.raw_session
            else:
                db_session = db

            try:
                # Execute route handler
                result = await func(*args, **kwargs)

                # Log success
                resource_id = None
                if hasattr(result, "id"):
                    resource_id = result.id

                log_success(
                    db=db_session,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    request=request
                )

                return result

            except Exception as e:
                # Log error
                log_error(
                    db=db_session,
                    action=action,
                    resource_type=resource_type,
                    error_message=str(e),
                    request=request
                )
                raise

        def sync_wrapper(*args, **kwargs):
            # Extract dependencies
            request = kwargs.get("request")
            db = kwargs.get("db") or kwargs.get("tenant_db")

            # Get raw session if tenant_db
            if hasattr(db, "raw_session"):
                db_session = db.raw_session
            else:
                db_session = db

            try:
                # Execute route handler
                result = func(*args, **kwargs)

                # Log success
                resource_id = None
                if hasattr(result, "id"):
                    resource_id = result.id

                log_success(
                    db=db_session,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    request=request
                )

                return result

            except Exception as e:
                # Log error
                log_error(
                    db=db_session,
                    action=action,
                    resource_type=resource_type,
                    error_message=str(e),
                    request=request
                )
                raise

        # Check if function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
