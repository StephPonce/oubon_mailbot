"""
OspraOS Database Package
Multi-store, multi-tenant database models

Usage:
    from ospra_os.database import get_session, init_database
    
    # Initialize on startup
    init_database()
    
    # Get session for queries
    session = get_session()
"""

# New connection utilities (PostgreSQL + SQLite)
from .connection import (
    get_engine,
    get_session,
    get_session_context,
    get_db,
    init_database,
    check_database_connection,
)

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
    CrossStoreLearning,

    # Enums
    SubscriptionTier,
    Platform,
    ProductStatus,
    DeploymentStatus,
    AIProvider,
    TaskType,
    StoreStatus,

    # Functions (backwards compatible)
    init_multi_store_db,
    get_multi_store_session,
    migrate_existing_store,
    get_user_monthly_ai_usage,
    get_store_performance,
)

__all__ = [
    # Connection utilities
    "get_engine",
    "get_session",
    "get_session_context",
    "get_db",
    "init_database",
    "check_database_connection",

    # Base
    "Base",

    # Models
    "User",
    "Store",
    "Product",
    "ProductDeployment",
    "AIUsage",
    "UserSettings",
    "CrossStoreLearning",

    # Enums
    "SubscriptionTier",
    "Platform",
    "ProductStatus",
    "DeploymentStatus",
    "AIProvider",
    "TaskType",
    "StoreStatus",

    # Functions (backwards compatible)
    "init_multi_store_db",
    "get_multi_store_session",
    "migrate_existing_store",
    "get_user_monthly_ai_usage",
    "get_store_performance",
]
