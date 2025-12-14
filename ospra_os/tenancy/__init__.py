"""
Multi-Tenant Isolation System - GROK RECOMMENDATION #14

Provides bulletproof data isolation between tenants (users).

Every database query is automatically scoped to the current tenant,
making it impossible to accidentally access another user's data.
"""

from ospra_os.tenancy.context import (
    TenantContext,
    get_current_tenant,
    set_current_tenant,
    clear_current_tenant,
    require_tenant,
    tenant_scope
)

from ospra_os.tenancy.queries import (
    TenantScopedSession,
    TenantQueryError,
    get_tenant_session
)

from ospra_os.tenancy.middleware import (
    TenantMiddleware,
    RequireTenantMiddleware,
    StoreContextMiddleware,
    is_path_exempt
)

from ospra_os.tenancy.dependencies import (
    get_tenant,
    get_optional_tenant,
    get_tenant_db,
    get_raw_db,
    require_store,
    get_user_store,
    require_admin,
    require_superuser,
    RequireSubscription,
    get_tenant_and_db,
    get_admin_and_db,
    get_superuser_and_raw_db
)

from ospra_os.tenancy.audit import (
    TenantAuditLog,
    log_tenant_action,
    log_success,
    log_failure,
    log_error,
    get_tenant_audit_logs,
    get_resource_audit_trail,
    audit_action
)

__all__ = [
    # Context
    "TenantContext",
    "get_current_tenant",
    "set_current_tenant",
    "clear_current_tenant",
    "require_tenant",
    "tenant_scope",

    # Queries
    "TenantScopedSession",
    "TenantQueryError",
    "get_tenant_session",

    # Middleware
    "TenantMiddleware",
    "RequireTenantMiddleware",
    "StoreContextMiddleware",
    "is_path_exempt",

    # Dependencies
    "get_tenant",
    "get_optional_tenant",
    "get_tenant_db",
    "get_raw_db",
    "require_store",
    "get_user_store",
    "require_admin",
    "require_superuser",
    "RequireSubscription",
    "get_tenant_and_db",
    "get_admin_and_db",
    "get_superuser_and_raw_db",

    # Audit
    "TenantAuditLog",
    "log_tenant_action",
    "log_success",
    "log_failure",
    "log_error",
    "get_tenant_audit_logs",
    "get_resource_audit_trail",
    "audit_action",
]
