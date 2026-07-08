"""
Tenant Dependencies - GROK RECOMMENDATION #14

FastAPI dependencies for tenant context and permissions.
Use these in route handlers to ensure tenant isolation.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ospra_os.tenancy.context import (
    get_current_tenant,
    require_tenant,
    TenantContext
)
from ospra_os.tenancy.queries import TenantScopedSession, get_tenant_session
from ospra_os.database.connection import get_db
from ospra_os.database import Store, User


# ==================== BASIC TENANT DEPENDENCIES ====================

def get_tenant() -> TenantContext:
    """
    Get current tenant context.

    Use this dependency in routes that need tenant information.

    Example:
        @router.get("/profile")
        def get_profile(tenant: TenantContext = Depends(get_tenant)):
            return {"user_id": tenant.user_id, "tier": tenant.subscription_tier}

    Raises:
        RuntimeError: If no tenant context is set
    """
    return require_tenant()


def get_optional_tenant() -> Optional[TenantContext]:
    """
    Get current tenant context, or None if not authenticated.

    Use this for public endpoints that have different behavior for authenticated users.

    Example:
        @router.get("/products")
        def list_products(tenant: Optional[TenantContext] = Depends(get_optional_tenant)):
            if tenant:
                # Show user's saved products
                pass
            else:
                # Show public product catalog
                pass
    """
    return get_current_tenant()


# ==================== DATABASE DEPENDENCIES ====================

def get_tenant_db(db: Session = Depends(get_db)) -> TenantScopedSession:
    """
    Get tenant-scoped database session.

    All queries through this session are automatically filtered to current tenant.
    Use this instead of get_db() for tenant-isolated routes.

    Example:
        @router.get("/products")
        def list_products(tenant_db: TenantScopedSession = Depends(get_tenant_db)):
            # This query is automatically filtered to current tenant
            products = tenant_db.query(Product).all()
            return products

    Raises:
        TenantQueryError: If no tenant context is set
    """
    return get_tenant_session(db)


def get_raw_db(db: Session = Depends(get_db)) -> Session:
    """
    Get raw database session (NOT tenant-scoped).

    [WARNING] USE WITH EXTREME CAUTION [WARNING]

    This bypasses tenant isolation. Only use for:
    - System administration
    - Cross-tenant operations by superusers
    - Specific operations that need full database access

    Example:
        @router.get("/admin/all-users")
        def list_all_users(
            raw_db: Session = Depends(get_raw_db),
            tenant: TenantContext = Depends(get_tenant)
        ):
            if not tenant.is_superuser:
                raise HTTPException(403, "Superuser required")

            # Now we can query across all tenants
            users = raw_db.query(User).all()
            return users
    """
    return db


# ==================== STORE DEPENDENCIES ====================

def require_store(
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> int:
    """
    Require that tenant has a store_id in context AND actually owns it.

    Use this for routes that operate on stores.

    Example:
        @router.get("/store/products")
        def list_store_products(
            store_id: int = Depends(require_store),
            tenant_db: TenantScopedSession = Depends(get_tenant_db)
        ):
            products = tenant_db.query(Product).filter(
                Product.store_id == store_id
            ).all()
            return products

    Raises:
        HTTPException(400): If no store_id in context
        HTTPException(403): If the store is not owned by this tenant
    """
    if tenant.store_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Store context required. Provide ?store_id=X or X-Store-ID header"
        )

    # T163: verify the caller actually OWNS this store. store_id is taken from a
    # client-supplied ?store_id= query param / X-Store-ID header, so before this
    # check any authenticated user could pass another tenant's store id. Reads
    # through TenantScopedSession were still filtered by Store.user_id, but
    # writes/inserts keyed on this id — and any route using the unscoped get_db
    # session — would operate on the other tenant's store.
    if not tenant.can_access_store(tenant.store_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this store.",
        )

    return tenant.store_id


def get_user_store(
    store_id: int,
    tenant_db: TenantScopedSession = Depends(get_tenant_db)
) -> Store:
    """
    Get store by ID, ensuring it belongs to current tenant.

    Use this for route path parameters like /stores/{store_id}/...

    Example:
        @router.get("/stores/{store_id}/products")
        def list_store_products(
            store: Store = Depends(get_user_store),
            tenant_db: TenantScopedSession = Depends(get_tenant_db)
        ):
            products = tenant_db.query(Product).filter(
                Product.store_id == store.id
            ).all()
            return products

    Raises:
        HTTPException(404): If store not found or not owned by tenant
    """
    return tenant_db.get_or_404(
        Store,
        store_id,
        detail="Store not found"
    )


# ==================== PERMISSION DEPENDENCIES ====================

def require_admin(
    tenant: TenantContext = Depends(get_tenant)
) -> TenantContext:
    """
    Require admin permissions within tenant.

    Use this for tenant admin operations (not platform admin).

    Example:
        @router.post("/team/invite")
        def invite_team_member(
            email: str,
            tenant: TenantContext = Depends(require_admin)
        ):
            # Only tenant admins can invite team members
            pass

    Raises:
        HTTPException(403): If user is not admin
    """
    if not tenant.is_admin and not tenant.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required"
        )

    return tenant


def require_superuser(
    tenant: TenantContext = Depends(get_tenant)
) -> TenantContext:
    """
    Require platform superuser permissions.

    Use this for platform administration endpoints.

    Example:
        @router.get("/admin/system-stats")
        def get_system_stats(
            tenant: TenantContext = Depends(require_superuser),
            raw_db: Session = Depends(get_raw_db)
        ):
            # Only superusers can see system-wide stats
            total_users = raw_db.query(User).count()
            return {"total_users": total_users}

    Raises:
        HTTPException(403): If user is not superuser
    """
    if not tenant.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser permissions required"
        )

    return tenant


# ==================== SUBSCRIPTION TIER DEPENDENCIES ====================

class RequireSubscription:
    """
    Require specific subscription tier.

    Use this to gate features by subscription level.

    Example:
        @router.post("/ads/create")
        def create_ad_campaign(
            campaign: AdCampaignCreate,
            tenant: TenantContext = Depends(RequireSubscription("eagle"))
        ):
            # Only Eagle tier and above can create ads
            pass

    Tiers (in order):
    - nest (free)
    - egg (starter)
    - eagle (professional)
    - legend (enterprise)
    """

    # Tier hierarchy (lower index = higher tier)
    TIER_ORDER = ["legend", "eagle", "egg", "nest"]

    def __init__(self, required_tier: str):
        """
        Initialize with required tier.

        Args:
            required_tier: Minimum tier required (nest, egg, eagle, legend)
        """
        if required_tier not in self.TIER_ORDER:
            raise ValueError(
                f"Invalid tier: {required_tier}. "
                f"Must be one of: {', '.join(self.TIER_ORDER)}"
            )

        self.required_tier = required_tier

    def __call__(self, tenant: TenantContext = Depends(get_tenant)) -> TenantContext:
        """Check if tenant has required tier"""

        # Superuser bypasses tier checks
        if tenant.is_superuser:
            return tenant

        # Check tier level
        try:
            user_tier_level = self.TIER_ORDER.index(tenant.subscription_tier)
            required_tier_level = self.TIER_ORDER.index(self.required_tier)

            if user_tier_level > required_tier_level:
                # User tier is lower than required
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"Subscription tier '{self.required_tier}' or higher required. "
                           f"Current tier: '{tenant.subscription_tier}'"
                )

        except ValueError:
            # Unknown tier - deny access
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown subscription tier: {tenant.subscription_tier}"
            )

        return tenant


# ==================== COMBINED DEPENDENCIES ====================

def get_tenant_and_db(
    tenant: TenantContext = Depends(get_tenant),
    tenant_db: TenantScopedSession = Depends(get_tenant_db)
) -> tuple[TenantContext, TenantScopedSession]:
    """
    Get both tenant context and database in one dependency.

    Convenience function to reduce boilerplate.

    Example:
        @router.get("/dashboard")
        def get_dashboard(deps = Depends(get_tenant_and_db)):
            tenant, tenant_db = deps
            products = tenant_db.query(Product).count()
            return {
                "user_id": tenant.user_id,
                "tier": tenant.subscription_tier,
                "product_count": products
            }
    """
    return (tenant, tenant_db)


def get_admin_and_db(
    tenant: TenantContext = Depends(require_admin),
    tenant_db: TenantScopedSession = Depends(get_tenant_db)
) -> tuple[TenantContext, TenantScopedSession]:
    """
    Get tenant context (with admin check) and database.

    Example:
        @router.post("/settings/update")
        def update_settings(deps = Depends(get_admin_and_db)):
            tenant, tenant_db = deps
            # Update settings for this tenant
            pass
    """
    return (tenant, tenant_db)


def get_superuser_and_raw_db(
    tenant: TenantContext = Depends(require_superuser),
    raw_db: Session = Depends(get_raw_db)
) -> tuple[TenantContext, Session]:
    """
    Get superuser context and raw database access.

    Example:
        @router.get("/admin/users")
        def list_all_users(deps = Depends(get_superuser_and_raw_db)):
            tenant, raw_db = deps
            users = raw_db.query(User).all()
            return users
    """
    return (tenant, raw_db)
