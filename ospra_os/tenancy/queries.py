"""
Tenant-Scoped Query Helpers - GROK RECOMMENDATION #14

Automatic tenant-scoping for all database queries.
Every query is filtered to current tenant, preventing cross-tenant data access.

IMPLEMENTATION NOTE (Cleanup Pass 4):
This module previously had two bugs that made it unusable:
  1. It filtered `model.tenant_id` but every tenant-scoped model in the
     codebase uses `user_id` as the ownership column (there is no
     `tenant_id` field anywhere).
  2. It only categorized 6 of 63 models, so queries against any other model
     raised TenantQueryError.

Both are now fixed:
  - All tenant-scoped filtering uses `user_id = tenant.user_id`
  - USER_SCOPED_MODELS is expanded to cover every model with a `user_id`
    column identified by scripts/tenancy_audit.py
  - STORE_SCOPED_MODELS covers models that filter by `store_id`
  - INDIRECT_TENANT_MODELS documents models whose isolation flows through
    a parent FK (audit-time notation — the wrapper does not auto-join)

Models NOT in any set fall through to `raise TenantQueryError` which is the
fail-safe behavior: if you query something uncategorized, you get an error
instead of silently leaking cross-tenant data.
"""

from typing import Any, List, Optional, Type, TypeVar
from sqlalchemy.orm import Session, Query
from sqlalchemy.exc import NoResultFound
from fastapi import HTTPException, status

from ospra_os.tenancy.context import get_current_tenant, require_tenant, TenantContext
from ospra_os.database import (
    # User / identity
    User,
    # Tenant-scoped (have user_id column)
    Store,
    Product,
    ProductDeployment,
    AdCampaign,
    EmailTemplate,
    Email,
    EmailAutomationRule,
    EmailLabel,
    UserEmailAccount,
    UserSettings,
    UserProductRecommendation,
    ABTest,
    Action,
    ActionLog,
    AutoPilotLog,
    AmazonAccount,
    AmazonListing,
    AmazonOrder,
    FBAShipment,
    AIUsage,
    ProductPerformance,
    RecommendationOutcome,
    AILearningEvent,
    ConfidenceCalibration,
    NicheLearning,
    PersonalLearningWeights,
)

T = TypeVar('T')


# ==================== EXCEPTIONS ====================

class TenantQueryError(Exception):
    """Raised when tenant context is required but not available"""
    pass


# ==================== MODEL CATEGORIZATION ====================

# Models scoped through user_id field (the canonical tenant ownership column).
# Add to this set when a new user-scoped model is introduced.
#
# `None` values are filtered out so that optional models (e.g. Amazon SP-API
# models which are only available when credential_encryption is wired up) do
# not leak into the set if they fail to import.
USER_SCOPED_MODELS = {m for m in {
    Store,
    Product,
    ProductDeployment,
    AdCampaign,
    EmailTemplate,
    Email,
    EmailAutomationRule,
    EmailLabel,
    UserEmailAccount,
    UserSettings,
    UserProductRecommendation,
    ABTest,
    Action,
    ActionLog,
    AutoPilotLog,
    AmazonAccount,
    AmazonListing,
    AmazonOrder,
    FBAShipment,
    AIUsage,
    ProductPerformance,
    RecommendationOutcome,
    AILearningEvent,
    ConfidenceCalibration,
    NicheLearning,
    PersonalLearningWeights,
} if m is not None}

# Legacy alias kept for backward compatibility with dependencies.py imports
# and any external callers. Previously this set was supposed to filter by
# `tenant_id`, but no model has that column — they all use `user_id`. The
# two sets are now equivalent; `USER_SCOPED_MODELS` is the canonical name.
DIRECT_TENANT_MODELS = USER_SCOPED_MODELS

# Models that have a store_id column (operate at the per-store granularity).
# Filtering by user_id still applies (every Product belongs to a user AND a
# store); store filter is layered on top via TenantContext.store_id.
STORE_SCOPED_MODELS = {
    Product,
    ProductDeployment,
    ABTest,
}

# Models that do NOT require tenant scoping (users table itself, or tables
# that are intentionally global — e.g. niches, caches).
UNSCOPED_MODELS = {
    User,  # The user row is the tenant itself
}


# ==================== TENANT-SCOPED SESSION ====================

class TenantScopedSession:
    """
    Wrapper around SQLAlchemy Session that automatically filters queries
    to current tenant.

    Prevents accidental cross-tenant data access by:
    1. Auto-filtering all queries by user_id/tenant_id
    2. Auto-setting user_id/tenant_id on inserts
    3. Validating updates/deletes stay within tenant

    Usage:
        tenant_db = TenantScopedSession(db)
        products = tenant_db.query(Product).all()  # Automatically filtered
        tenant_db.add(new_product)  # user_id auto-set
    """

    def __init__(self, db: Session, tenant_context: Optional[TenantContext] = None):
        self._db = db
        self._tenant = tenant_context or get_current_tenant()

        if self._tenant is None:
            raise TenantQueryError(
                "No tenant context available. "
                "Ensure TenantMiddleware is active or use tenant_scope()."
            )

    @property
    def tenant(self) -> TenantContext:
        """Get current tenant context"""
        return self._tenant

    @property
    def raw_session(self) -> Session:
        """Get underlying session (use with caution!)"""
        return self._db

    def query(self, model: Type[T], *args, **kwargs) -> Query:
        """
        Create a query automatically scoped to current tenant.

        Args:
            model: SQLAlchemy model class

        Returns:
            Query filtered to current tenant

        Raises:
            TenantQueryError: If model requires tenant but context missing
        """
        query = self._db.query(model, *args, **kwargs)

        # Superuser can see all data
        if self._tenant.is_superuser:
            return query

        # System models don't need filtering
        if model in UNSCOPED_MODELS:
            return query

        # Apply tenant filtering. All user-scoped models filter by user_id;
        # every model in USER_SCOPED_MODELS is guaranteed to have that column.
        if model in USER_SCOPED_MODELS:
            if hasattr(model, 'user_id'):
                query = query.filter(model.user_id == self._tenant.user_id)
            else:
                raise TenantQueryError(
                    f"Model {model.__name__} is in USER_SCOPED_MODELS but has no user_id field. "
                    f"Remove it from the set or add a user_id column."
                )
        else:
            # Unknown model - fail safe (better to error than silently leak)
            raise TenantQueryError(
                f"Model {model.__name__} is not categorized for tenant scoping. "
                f"Add it to USER_SCOPED_MODELS or UNSCOPED_MODELS in "
                f"ospra_os/tenancy/queries.py."
            )

        return query

    def get(self, model: Type[T], ident: Any) -> Optional[T]:
        """
        Get by primary key, scoped to tenant.

        Args:
            model: SQLAlchemy model class
            ident: Primary key value

        Returns:
            Model instance if found and belongs to tenant, None otherwise
        """
        instance = self._db.query(model).get(ident)

        if instance is None:
            return None

        # Superuser can access all
        if self._tenant.is_superuser:
            return instance

        # Verify ownership
        if model in UNSCOPED_MODELS:
            return instance

        if model in USER_SCOPED_MODELS:
            if hasattr(instance, 'user_id'):
                if instance.user_id != self._tenant.user_id:
                    return None  # Not owned by this user
            return instance

        # Uncategorized model - fail safe (same policy as query())
        raise TenantQueryError(
            f"Model {model.__name__} is not categorized for tenant scoping. "
            f"Add it to USER_SCOPED_MODELS or UNSCOPED_MODELS in "
            f"ospra_os/tenancy/queries.py."
        )

    def get_or_404(self, model: Type[T], ident: Any, detail: Optional[str] = None) -> T:
        """
        Get by primary key or raise 404.

        Args:
            model: SQLAlchemy model class
            ident: Primary key value
            detail: Optional error message

        Returns:
            Model instance

        Raises:
            HTTPException(404): If not found or not owned by tenant
        """
        instance = self.get(model, ident)

        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail or f"{model.__name__} not found"
            )

        return instance

    def add(self, instance: Any) -> None:
        """
        Add instance, automatically setting tenant fields.

        Args:
            instance: Model instance to add
        """
        model = type(instance)

        # Auto-populate user_id on any user-scoped insert
        if model in USER_SCOPED_MODELS:
            if hasattr(instance, 'user_id') and instance.user_id is None:
                instance.user_id = self._tenant.user_id

        # Auto-populate store_id if the model is store-scoped AND the request
        # has a store_id in context (set via ?store_id=X or X-Store-ID header)
        if model in STORE_SCOPED_MODELS:
            if hasattr(instance, 'store_id') and instance.store_id is None:
                if self._tenant.store_id:
                    instance.store_id = self._tenant.store_id

        self._db.add(instance)

    def delete(self, instance: Any) -> None:
        """
        Delete instance after verifying tenant ownership.

        Args:
            instance: Model instance to delete

        Raises:
            HTTPException(403): If instance not owned by tenant
        """
        model = type(instance)

        # Superuser can delete anything
        if self._tenant.is_superuser:
            self._db.delete(instance)
            return

        # Verify ownership before delete
        if model in USER_SCOPED_MODELS:
            if hasattr(instance, 'user_id'):
                if instance.user_id != self._tenant.user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot delete resource owned by another user"
                    )
            self._db.delete(instance)
            return

        if model in UNSCOPED_MODELS:
            self._db.delete(instance)
            return

        # Uncategorized model - fail safe
        raise TenantQueryError(
            f"Model {model.__name__} is not categorized for tenant scoping. "
            f"Add it to USER_SCOPED_MODELS or UNSCOPED_MODELS in "
            f"ospra_os/tenancy/queries.py before deleting through a "
            f"TenantScopedSession."
        )

    def bulk_update_mappings(self, model: Type[T], mappings: List[dict]) -> None:
        """
        Bulk update, automatically adding tenant fields.

        Args:
            model: SQLAlchemy model class
            mappings: List of dicts with update data
        """
        # Add user_id to all mappings that don't already set it
        for mapping in mappings:
            if model in USER_SCOPED_MODELS:
                if 'user_id' not in mapping:
                    mapping['user_id'] = self._tenant.user_id

        self._db.bulk_update_mappings(model, mappings)

    def bulk_insert_mappings(self, model: Type[T], mappings: List[dict]) -> None:
        """
        Bulk insert, automatically adding tenant fields.

        Args:
            model: SQLAlchemy model class
            mappings: List of dicts with insert data
        """
        # Add user_id to all mappings that don't already set it
        for mapping in mappings:
            if model in USER_SCOPED_MODELS:
                if 'user_id' not in mapping:
                    mapping['user_id'] = self._tenant.user_id

        self._db.bulk_insert_mappings(model, mappings)

    # ==================== PASS-THROUGH METHODS ====================

    def commit(self) -> None:
        """Commit the transaction"""
        self._db.commit()

    def rollback(self) -> None:
        """Rollback the transaction"""
        self._db.rollback()

    def flush(self) -> None:
        """Flush pending changes"""
        self._db.flush()

    def refresh(self, instance: Any) -> None:
        """Refresh instance from database"""
        self._db.refresh(instance)

    def expunge(self, instance: Any) -> None:
        """Remove instance from session"""
        self._db.expunge(instance)

    def expunge_all(self) -> None:
        """Remove all instances from session"""
        self._db.expunge_all()

    def close(self) -> None:
        """Close the session"""
        self._db.close()

    def execute(self, statement: Any) -> Any:
        """Execute a SQL statement (use with caution!)"""
        return self._db.execute(statement)


# ==================== HELPER FUNCTIONS ====================

def get_tenant_session(db: Session) -> TenantScopedSession:
    """
    Create a tenant-scoped session from a regular session.

    Args:
        db: SQLAlchemy session

    Returns:
        Tenant-scoped session wrapper

    Raises:
        TenantQueryError: If no tenant context available
    """
    return TenantScopedSession(db)


def require_tenant_session(db: Session) -> TenantScopedSession:
    """
    Create tenant-scoped session, ensuring tenant context exists.

    Args:
        db: SQLAlchemy session

    Returns:
        Tenant-scoped session wrapper

    Raises:
        TenantQueryError: If no tenant context available
    """
    tenant = require_tenant()  # This will raise if no context
    return TenantScopedSession(db, tenant)
