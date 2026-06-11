"""
Tenant Middleware - GROK RECOMMENDATION #14

Automatically sets tenant context from authenticated user.
Ensures every request has proper tenant isolation.
"""

from typing import Callable, Optional, Set
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ospra_os.tenancy.context import TenantContext, set_current_tenant, clear_current_tenant
from ospra_os.auth.jwt_auth import decode_token


# ==================== EXEMPT PATHS ====================

# Paths that don't require tenant context
EXEMPT_PATHS: Set[str] = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/health/celery",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/verify-email",
    "/api/auth/reset-password",
    "/auth/url",
    "/oauth2callback",
    "/api/gmail/oauth-callback",
    "/api/tiktok/oauth-callback",
    "/api/aliexpress/oauth-callback",
}

# Paths that start with these prefixes are exempt
EXEMPT_PREFIXES: Set[str] = {
    "/static/",
    "/assets/",
    "/_next/",
    "/api/public/",  # no-auth marketing endpoints (scoreboard, task #52)
}


def is_path_exempt(path: str) -> bool:
    """Check if path is exempt from tenant requirement"""
    # Check exact matches
    if path in EXEMPT_PATHS:
        return True

    # Check prefixes
    for prefix in EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True

    return False


# ==================== TENANT MIDDLEWARE ====================

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Sets tenant context from authenticated user.

    For every request with a valid JWT token:
    1. Decode token to get user info
    2. Create TenantContext with user_id as tenant_id
    3. Set context for the request lifetime
    4. Clear context after request completes

    This makes tenant context available to:
    - Route handlers (via get_current_tenant())
    - Database queries (via TenantScopedSession)
    - Background tasks (must be passed explicitly)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and set tenant context"""

        # Check if path is exempt
        if is_path_exempt(request.url.path):
            return await call_next(request)

        # Try to extract tenant from JWT token
        tenant_context = None
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix

            try:
                # Decode JWT token
                payload = decode_token(token)

                if payload:
                    # Extract user info from token
                    user_id = int(payload.get("sub"))
                    email = payload.get("email")
                    tier = payload.get("tier", "nest")

                    # Check for admin/superuser roles
                    is_admin = payload.get("is_admin", False)
                    is_superuser = payload.get("is_superuser", False)

                    # Create tenant context
                    tenant_context = TenantContext(
                        tenant_id=user_id,  # User ID = Tenant ID in our model
                        user_id=user_id,
                        store_id=None,  # Set by specific routes if needed
                        is_admin=is_admin,
                        is_superuser=is_superuser,
                        subscription_tier=tier
                    )

                    # Set context for request
                    set_current_tenant(tenant_context)

            except Exception as e:
                # Invalid token - clear context and continue
                # Auth middleware will handle 401 if needed
                clear_current_tenant()

        try:
            # Process request
            response = await call_next(request)
            return response

        finally:
            # Always clear context after request
            clear_current_tenant()


# ==================== REQUIRE TENANT MIDDLEWARE ====================

class RequireTenantMiddleware(BaseHTTPMiddleware):
    """
    Enforces tenant context requirement.

    Returns 403 if no tenant context is set for non-exempt paths.
    Use this AFTER TenantMiddleware to enforce strict isolation.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check tenant context exists"""
        from ospra_os.tenancy.context import get_current_tenant
        from fastapi.responses import JSONResponse

        # Check if path is exempt
        if is_path_exempt(request.url.path):
            return await call_next(request)

        # Check tenant context exists
        tenant = get_current_tenant()

        if tenant is None:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Tenant context required. Please authenticate.",
                    "error": "no_tenant_context"
                }
            )

        # Continue with request
        return await call_next(request)


# ==================== STORE CONTEXT MIDDLEWARE ====================

class StoreContextMiddleware(BaseHTTPMiddleware):
    """
    Sets store_id in tenant context from query param or header.

    Useful for routes that operate on specific stores.
    Can extract store_id from:
    - Query parameter: ?store_id=123
    - Header: X-Store-ID: 123
    - Path parameter: /stores/{store_id}/...
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Extract and set store context"""
        from ospra_os.tenancy.context import get_current_tenant, set_current_tenant

        # Get current tenant
        tenant = get_current_tenant()

        if tenant is None:
            # No tenant context - skip store context
            return await call_next(request)

        # Try to extract store_id
        store_id = None

        # From query parameter
        store_id_param = request.query_params.get("store_id")
        if store_id_param:
            try:
                store_id = int(store_id_param)
            except (ValueError, TypeError):
                pass

        # From header
        if not store_id:
            store_id_header = request.headers.get("X-Store-ID")
            if store_id_header:
                try:
                    store_id = int(store_id_header)
                except (ValueError, TypeError):
                    pass

        # From path parameter (requires path_params in request state)
        if not store_id and hasattr(request, "path_params"):
            store_id_path = request.path_params.get("store_id")
            if store_id_path:
                try:
                    store_id = int(store_id_path)
                except (ValueError, TypeError):
                    pass

        # Update tenant context with store_id
        if store_id:
            # Create new context with store_id (preserve brand fields so lazy
            # lookups populated earlier in the request are not discarded)
            updated_tenant = TenantContext(
                tenant_id=tenant.tenant_id,
                user_id=tenant.user_id,
                store_id=store_id,
                is_admin=tenant.is_admin,
                is_superuser=tenant.is_superuser,
                subscription_tier=tenant.subscription_tier,
                brand_name=tenant.brand_name,
                brand_descriptor=tenant.brand_descriptor,
            )
            set_current_tenant(updated_tenant)

        try:
            response = await call_next(request)
            return response

        finally:
            # Restore original tenant context (without store_id)
            if store_id:
                set_current_tenant(tenant)
