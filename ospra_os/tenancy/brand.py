"""
Tenant Branding Helpers - Cleanup Pass 4 SaaS Refactor

Reads the current tenant's brand name and descriptor so AI prompts,
email signatures, and FAQ templates can be parameterized per tenant.

Defaults ("Oubon Shop" / "a premium smart home and lifestyle store") keep
the single-tenant Oubon production deployment working unchanged when a
user has not set their own brand — i.e. `User.brand_name` is NULL.

Typical usage:

    from ospra_os.tenancy.brand import get_tenant_brand, get_tenant_brand_descriptor

    brand = get_tenant_brand(db)          # "Oubon Shop" by default
    descriptor = get_tenant_brand_descriptor(db)
    prompt = f"You are a copywriter for {brand}, {descriptor}."

`db` is optional. Without a session the helper returns whatever is already
populated on TenantContext (cached from an earlier call in the same
request) or the fallback. Pass a session the first time you need the
brand in a request — subsequent calls in the same context are free.
"""

from __future__ import annotations

from typing import Optional
import logging

from ospra_os.tenancy.context import get_current_tenant

logger = logging.getLogger(__name__)

# Oubon's single-tenant production defaults. These are the values every
# prompt/template used to hardcode before Pass 4. New tenants whose
# `users.brand_name` / `users.brand_descriptor` are set override these.
DEFAULT_BRAND_NAME = "Oubon Shop"
DEFAULT_BRAND_DESCRIPTOR = "a premium smart home and lifestyle store"


def get_tenant_brand(db=None, fallback: str = DEFAULT_BRAND_NAME) -> str:
    """Return the brand name for the current tenant.

    Read order:
        1. `TenantContext.brand_name` if already populated (fast path)
        2. `User.brand_name` via `db.query(User)` if `db` is provided
        3. `fallback` (default "Oubon Shop")

    Safe to call without a tenant context — returns the fallback.
    """
    tenant = get_current_tenant()
    if tenant is None:
        return fallback

    # Fast path - already populated on this request's context
    if tenant.brand_name:
        return tenant.brand_name

    # Lazy DB lookup - only if a session was provided
    if db is not None:
        brand = _lookup_user_field(db, tenant.user_id, "brand_name")
        if brand:
            tenant.brand_name = brand  # Cache on context for the rest of the request
            return brand

    return fallback


def get_tenant_brand_descriptor(
    db=None, fallback: str = DEFAULT_BRAND_DESCRIPTOR
) -> str:
    """Return the short brand descriptor for the current tenant.

    Used after the brand name in prompts, e.g.
    "copywriter for {brand_name}, {descriptor}".

    Read order mirrors `get_tenant_brand`.
    """
    tenant = get_current_tenant()
    if tenant is None:
        return fallback

    if tenant.brand_descriptor:
        return tenant.brand_descriptor

    if db is not None:
        descriptor = _lookup_user_field(db, tenant.user_id, "brand_descriptor")
        if descriptor:
            tenant.brand_descriptor = descriptor
            return descriptor

    return fallback


def get_tenant_brand_pair(db=None) -> tuple[str, str]:
    """Convenience - return (brand_name, brand_descriptor) together."""
    return get_tenant_brand(db), get_tenant_brand_descriptor(db)


def get_tenant_signature(db=None, suffix: str = "Support") -> str:
    """Return an email signature line like '— Oubon Shop Support'."""
    brand = get_tenant_brand(db)
    return f"— {brand} {suffix}"


# ==================== INTERNAL ====================


def _lookup_user_field(db, user_id: int, field: str) -> Optional[str]:
    """Look up a single string column on the User row. Returns None on error."""
    try:
        # Lazy import to avoid circular imports at module load time
        from ospra_os.database import User

        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None
        return getattr(user, field, None)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Failed to look up User.%s for user_id=%s: %s", field, user_id, exc)
        return None
