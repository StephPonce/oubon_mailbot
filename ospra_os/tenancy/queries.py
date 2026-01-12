"""
Tenant-Scoped Query Helpers - GROK RECOMMENDATION #14

Automatic tenant-scoping for all database queries.
Every query is filtered to current tenant, preventing cross-tenant data access.
"""

from typing import Any, List, Optional, Type, TypeVar
from sqlalchemy.orm import Session, Query
from sqlalchemy.exc import NoResultFound
from fastapi import HTTPException, status

from ospra_os.tenancy.context import get_current_tenant, require_tenant, TenantContext
from ospra_os.database import (
    User,
    Store,
    Product,
    AdCampaign,
    EmailTemplate,
    ABTest
)

T = TypeVar('T')


# ==================== EXCEPTIONS ====================

class TenantQueryError(Exception):
    """Raised when tenant context is required but not available"""
    pass


# ==================== MODEL CATEGORIZATION ====================

# Models directly scoped to tenant_id (user_id)
DIRECT_TENANT_MODELS = {
    Store,
    EmailTemplate,
    ABTest,
    AdCampaign
}

# Models scoped through user_id field
USER_SCOPED_MODELS = {
    Product
}

# Models that are store-scoped (require store_id)
STORE_SCOPED_MODELS = {
    Product
}

# Models that don't require tenant scoping (system-level)
UNSCOPED_MODELS = {
    User  # Users are tenants themselves
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

        # Apply tenant filtering
        if model in DIRECT_TENANT_MODELS:
            # Models with tenant_id field
            if hasattr(model, 'tenant_id'):
                query = query.filter(model.tenant_id == self._tenant.tenant_id)
            else:
                raise TenantQueryError(
                    f"Model {model.__name__} is marked as DIRECT_TENANT but has no tenant_id field"
                )

        elif model in USER_SCOPED_MODELS:
            # Models with user_id field
            if hasattr(model, 'user_id'):
                query = query.filter(model.user_id == self._tenant.user_id)
            else:
                raise TenantQueryError(
                    f"Model {model.__name__} is marked as USER_SCOPED but has no user_id field"
                )

        else:
            # Unknown model - fail safe
            raise TenantQueryError(
                f"Model {model.__name__} is not categorized for tenant scoping. "
                f"Add to DIRECT_TENANT_MODELS, USER_SCOPED_MODELS, or UNSCOPED_MODELS."
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

        elif model in DIRECT_TENANT_MODELS:
            if hasattr(instance, 'tenant_id'):
                if instance.tenant_id != self._tenant.tenant_id:
                    return None  # Not owned by this tenant

        elif model in USER_SCOPED_MODELS:
            if hasattr(instance, 'user_id'):
                if instance.user_id != self._tenant.user_id:
                    return None  # Not owned by this user

        return instance

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

        # Set tenant fields automatically
        if model in DIRECT_TENANT_MODELS:
            if hasattr(instance, 'tenant_id') and instance.tenant_id is None:
                instance.tenant_id = self._tenant.tenant_id

        if model in USER_SCOPED_MODELS or model in STORE_SCOPED_MODELS:
            if hasattr(instance, 'user_id') and instance.user_id is None:
                instance.user_id = self._tenant.user_id

        # Set store_id if in context
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
        if model in DIRECT_TENANT_MODELS:
            if hasattr(instance, 'tenant_id'):
                if instance.tenant_id != self._tenant.tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot delete resource from another tenant"
                    )

        elif model in USER_SCOPED_MODELS:
            if hasattr(instance, 'user_id'):
                if instance.user_id != self._tenant.user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot delete resource from another user"
                    )

        self._db.delete(instance)

    def bulk_update_mappings(self, model: Type[T], mappings: List[dict]) -> None:
        """
        Bulk update, automatically adding tenant fields.

        Args:
            model: SQLAlchemy model class
            mappings: List of dicts with update data
        """
        # Add tenant fields to all mappings
        for mapping in mappings:
            if model in DIRECT_TENANT_MODELS:
                if 'tenant_id' not in mapping:
                    mapping['tenant_id'] = self._tenant.tenant_id

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
        # Add tenant fields to all mappings
        for mapping in mappings:
            if model in DIRECT_TENANT_MODELS:
                if 'tenant_id' not in mapping:
                    mapping['tenant_id'] = self._tenant.tenant_id

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
