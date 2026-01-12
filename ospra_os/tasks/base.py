"""
Base Task Classes - GROK RECOMMENDATIONS #13 + #14

Provides database-aware base classes for Celery tasks.

DatabaseTask: Automatic database session management
UserTask: Extends DatabaseTask with user-specific helpers
TenantTask: Tenant-scoped task with automatic isolation (GROK #14)
SystemTask: System-level task that operates across all tenants
"""

import logging
from typing import List, Optional
from celery import Task
from sqlalchemy.orm import Session

from ospra_os.database.connection import get_session_factory
from ospra_os.database import User, Store

# Multi-Tenant Support (GROK #14)
from ospra_os.tenancy.context import TenantContext, tenant_scope
from ospra_os.tenancy.queries import TenantScopedSession

logger = logging.getLogger(__name__)

# Create session factory once at module level
SessionLocal = get_session_factory()


class DatabaseTask(Task):
    """
    Base task with automatic database session management.

    Usage:
        @celery_app.task(bind=True, base=DatabaseTask)
        def my_task(self, user_id: int):
            user = self.db.query(User).get(user_id)
            # ... do work ...
            self.db.commit()
    """

    _db: Optional[Session] = None

    def __call__(self, *args, **kwargs):
        """Execute task with database session"""
        try:
            return self.run(*args, **kwargs)
        finally:
            self.cleanup_db()

    @property
    def db(self) -> Session:
        """Get or create database session"""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def cleanup_db(self):
        """Close database session"""
        if self._db is not None:
            try:
                self._db.close()
            except Exception as e:
                logger.error(f"Error closing database session: {e}")
            finally:
                self._db = None

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Rollback database on failure"""
        if self._db is not None:
            try:
                self._db.rollback()
            except Exception as e:
                logger.error(f"Error rolling back database: {e}")

        super().on_failure(exc, task_id, args, kwargs, einfo)


class UserTask(DatabaseTask):
    """
    Base task with user-specific helpers.

    Extends DatabaseTask with common user queries:
    - get_user(user_id)
    - get_all_active_users()
    - get_user_stores(user_id)

    Usage:
        @celery_app.task(bind=True, base=UserTask)
        def process_all_users(self):
            users = self.get_all_active_users()
            for user in users:
                process_user.delay(user.id)
    """

    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_all_active_users(self, tier: Optional[str] = None) -> List[User]:
        """
        Get all active users

        Args:
            tier: Optional tier filter (nest, flight, hypersonic)

        Returns:
            List of active User objects
        """
        query = self.db.query(User).filter(
            User.is_active == True  # noqa: E712
        )

        if tier:
            query = query.filter(User.subscription_tier == tier)

        return query.all()

    def get_user_stores(self, user_id: int, active_only: bool = True) -> List[Store]:
        """
        Get stores for a user

        Args:
            user_id: User ID
            active_only: Only return connected stores

        Returns:
            List of Store objects
        """
        query = self.db.query(Store).filter(
            Store.user_id == user_id
        )

        if active_only:
            query = query.filter(Store.status == "connected")  # noqa: E712

        return query.all()

    def get_all_active_stores(self) -> List[Store]:
        """Get all active stores across all users"""
        return self.db.query(Store).filter(
            Store.status == "connected"  # noqa: E712
        ).all()


# ==================== TENANT-AWARE TASKS (GROK #14) ====================

class TenantTask(DatabaseTask):
    """
    Tenant-scoped task with automatic data isolation.

    IMPORTANT: This task requires tenant_id to be passed as first argument.
    All database queries are automatically filtered to the tenant.

    Usage:
        @celery_app.task(bind=True, base=TenantTask)
        def process_user_products(self, tenant_id: int, user_id: int):
            # tenant_db is automatically scoped to tenant
            products = self.tenant_db.query(Product).all()
            # Only returns products for this tenant
            return len(products)

        # Trigger from route:
        from ospra_os.tenancy import get_tenant
        tenant = get_tenant()
        process_user_products.delay(tenant.tenant_id, tenant.user_id)
    """

    _tenant_db: Optional[TenantScopedSession] = None
    _tenant_context: Optional[TenantContext] = None

    def __call__(self, *args, **kwargs):
        """Execute task with tenant context"""
        # First argument MUST be tenant_id
        if not args or not isinstance(args[0], int):
            raise ValueError(
                "TenantTask requires tenant_id as first argument. "
                "Usage: task.delay(tenant_id, ...other_args)"
            )

        tenant_id = args[0]

        # If second argument looks like user_id, extract it
        user_id = args[1] if len(args) > 1 and isinstance(args[1], int) else tenant_id

        # Create tenant context
        self._tenant_context = TenantContext(
            tenant_id=tenant_id,
            user_id=user_id,
            subscription_tier="nest"  # Default, override if needed
        )

        try:
            # Set tenant context for duration of task
            with tenant_scope(self._tenant_context):
                return self.run(*args, **kwargs)
        finally:
            self.cleanup_tenant()

    @property
    def tenant_db(self) -> TenantScopedSession:
        """
        Get tenant-scoped database session.

        All queries through this session are automatically filtered to current tenant.
        """
        if self._tenant_db is None:
            if self._tenant_context is None:
                raise RuntimeError(
                    "No tenant context available. Ensure task was called with tenant_id."
                )

            self._tenant_db = TenantScopedSession(self.db, self._tenant_context)

        return self._tenant_db

    @property
    def tenant(self) -> TenantContext:
        """Get current tenant context"""
        if self._tenant_context is None:
            raise RuntimeError("No tenant context available")
        return self._tenant_context

    def cleanup_tenant(self):
        """Clean up tenant-specific resources"""
        self._tenant_db = None
        self._tenant_context = None

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Rollback and cleanup on failure"""
        self.cleanup_tenant()
        super().on_failure(exc, task_id, args, kwargs, einfo)


class SystemTask(UserTask):
    """
    System-level task that operates across all tenants.

    Use this for:
    - Admin operations
    - System maintenance
    - Cross-tenant analytics
    - Scheduled jobs that process all users

    IMPORTANT: This task bypasses tenant isolation.
    Use with caution and only for legitimate system operations.

    Usage:
        @celery_app.task(bind=True, base=SystemTask)
        def daily_cleanup(self):
            # Can access all users
            users = self.get_all_active_users()

            for user in users:
                # Spawn tenant-scoped tasks for each user
                process_user_products.delay(user.id, user.id)

        # Or process directly with tenant context:
        @celery_app.task(bind=True, base=SystemTask)
        def sync_all_stores(self):
            for user in self.get_all_active_users():
                tenant_context = TenantContext(
                    tenant_id=user.id,
                    user_id=user.id,
                    subscription_tier=user.subscription_tier
                )

                with tenant_scope(tenant_context):
                    tenant_db = TenantScopedSession(self.db, tenant_context)
                    # Now queries are scoped to this user
                    products = tenant_db.query(Product).all()
                    # Process products...
    """

    def process_all_tenants(self, tenant_task_func, *args, **kwargs):
        """
        Helper to run a function for all active tenants.

        Args:
            tenant_task_func: Function to call for each tenant
            *args, **kwargs: Additional arguments to pass

        Example:
            def process_tenant(tenant_context, tenant_db):
                products = tenant_db.query(Product).all()
                # ... process products

            self.process_all_tenants(process_tenant)
        """
        users = self.get_all_active_users()

        results = []
        for user in users:
            tenant_context = TenantContext(
                tenant_id=user.id,
                user_id=user.id,
                subscription_tier=user.subscription_tier
            )

            with tenant_scope(tenant_context):
                tenant_db = TenantScopedSession(self.db, tenant_context)

                try:
                    result = tenant_task_func(tenant_context, tenant_db, *args, **kwargs)
                    results.append({"user_id": user.id, "result": result, "success": True})
                except Exception as e:
                    logger.error(f"Error processing tenant {user.id}: {e}")
                    results.append({"user_id": user.id, "error": str(e), "success": False})

        return results
