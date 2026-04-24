"""
Tenant Context Management - GROK RECOMMENDATION #14

Thread-safe context variable storage for current tenant information.
Uses contextvars for proper async/await support.
"""

from contextvars import ContextVar
from typing import Optional
from dataclasses import dataclass

# Context variable to store current tenant
_current_tenant: ContextVar[Optional["TenantContext"]] = ContextVar(
    "current_tenant", default=None
)


@dataclass
class TenantContext:
    """
    Current tenant context information.

    Stores the currently authenticated user/tenant and their permissions.
    This context is automatically set by middleware and used by
    tenant-scoped queries to filter all database access.
    """
    tenant_id: int  # Primary tenant identifier (usually user.id)
    user_id: int    # User ID (same as tenant_id in simple model)
    store_id: Optional[int] = None  # Currently selected store (if applicable)

    # Permissions
    is_admin: bool = False  # Admin within their own tenant
    is_superuser: bool = False  # Platform admin, can see all tenants

    # Subscription info
    subscription_tier: str = "nest"

    # Tenant branding (populated lazily by ospra_os.tenancy.brand.get_tenant_brand)
    brand_name: Optional[str] = None
    brand_descriptor: Optional[str] = None

    def can_access_tenant(self, tenant_id: int) -> bool:
        """Check if current context can access a specific tenant"""
        if self.is_superuser:
            return True
        return self.tenant_id == tenant_id

    def can_access_store(self, store_id: int) -> bool:
        """Check if current context can access a specific store"""
        if self.is_superuser:
            return True
        # Would need to query DB to verify store belongs to user
        # For now, trust the store_id if user is authenticated
        return True

    def __repr__(self) -> str:
        return f"TenantContext(tenant_id={self.tenant_id}, user_id={self.user_id}, store_id={self.store_id})"


def get_current_tenant() -> Optional[TenantContext]:
    """
    Get the current tenant context from thread-local storage.

    Returns None if no tenant context is set.
    This is safe to call from anywhere - middleware, routes, tasks, etc.
    """
    return _current_tenant.get()


def set_current_tenant(tenant: TenantContext) -> None:
    """
    Set the current tenant context.

    Typically called by middleware or manually in tasks.
    """
    _current_tenant.set(tenant)


def clear_current_tenant() -> None:
    """Clear the current tenant context"""
    _current_tenant.set(None)


def require_tenant() -> TenantContext:
    """
    Get current tenant or raise error if not set.

    Use this in code that absolutely requires tenant context.
    """
    tenant = get_current_tenant()
    if tenant is None:
        raise RuntimeError(
            "No tenant context set. "
            "Ensure TenantMiddleware is active or tenant context is manually set."
        )
    return tenant


class TenantContextManager:
    """
    Context manager for setting tenant scope.

    Usage:
        tenant = TenantContext(tenant_id=1, user_id=1)
        with tenant_scope(tenant):
            # All queries here are scoped to tenant
            products = db.query(Product).all()
    """

    def __init__(self, tenant: TenantContext):
        self.tenant = tenant
        self.previous_tenant: Optional[TenantContext] = None

    def __enter__(self) -> TenantContext:
        self.previous_tenant = get_current_tenant()
        set_current_tenant(self.tenant)
        return self.tenant

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.previous_tenant:
            set_current_tenant(self.previous_tenant)
        else:
            clear_current_tenant()
        return False


def tenant_scope(tenant: TenantContext):
    """
    Create a context manager for tenant scope.

    Example:
        with tenant_scope(TenantContext(tenant_id=1, user_id=1)):
            # Code here runs in tenant 1's context
            products = tenant_db.query(Product).all()
    """
    return TenantContextManager(tenant)
