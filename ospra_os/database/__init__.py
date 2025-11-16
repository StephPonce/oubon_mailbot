"""
OspraOS Database Package
Multi-store, multi-tenant database models
"""

from .multi_store_models import (
    # Base
    Base,

    # Models
    User,
    Store,
    Product,
    ProductDeployment,
    AIUsage,
    UserSettings,

    # Enums
    SubscriptionTier,
    Platform,
    ProductStatus,
    DeploymentStatus,
    AIProvider,
    TaskType,

    # Functions
    init_multi_store_db,
    get_multi_store_session,
    migrate_existing_store,
    get_user_monthly_ai_usage,
    get_store_performance,
)

__all__ = [
    # Base
    "Base",

    # Models
    "User",
    "Store",
    "Product",
    "ProductDeployment",
    "AIUsage",
    "UserSettings",

    # Enums
    "SubscriptionTier",
    "Platform",
    "ProductStatus",
    "DeploymentStatus",
    "AIProvider",
    "TaskType",

    # Functions
    "init_multi_store_db",
    "get_multi_store_session",
    "migrate_existing_store",
    "get_user_monthly_ai_usage",
    "get_store_performance",
]
