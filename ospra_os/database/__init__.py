"""
OspraOS Database Package
Multi-store, multi-tenant database models - Modular Architecture

Usage:
    from ospra_os.database import get_session, init_database

    # Initialize on startup
    init_database()

    # Get session for queries
    session = get_session()
"""

# Connection utilities (PostgreSQL + SQLite)
from .connection import (
    get_engine,
    get_session,
    get_session_context,
    get_db,
    init_database,
    check_database_connection,
)

# Base and Enums
from .base import (
    Base,
    # Enums
    SubscriptionTier,
    Platform,
    StoreStatus,
    ProductStatus,
    DeploymentStatus,
    AIProvider,
    TaskType,
    TriggerType,
    ActionType,
    LifecycleStage,
    EntryTiming,
    RiskLevel,
)

# Action Models (MUST be imported before User/Store due to relationships)
from .action_models import (
    Action,
    AIActionType,
    AIActionStatus,
)
from .actions_models import (
    AutoPilotLog,
)

# User Models
from .user_models import (
    User,
    UserProductRecommendation,
    UserSettings,
    UserEmailAccount,
)

# Password Reset (from multi_store_models until refactored)
from .multi_store_models import (
    PasswordResetToken,
)

# Store Models
from .store_models import (
    Store,
    CrossStoreLearning,
)

# Product Models
from .product_models import (
    Product,
    ProductDeployment,
    ProductSaturation,
    ProductVelocity,
    ProductSnapshot,
    ProductIntelligence,
    ABTestVariant,
)

# Advertising Models
from .advertising_models import (
    AdCampaign,
)

# Email Models
from .email_models import (
    Email,
    EmailAutomationRule,
    EmailTemplate,
    EmailLabel,
    EmailFollowup,
)

# Testing Models
from .testing_models import (
    ABTest,
    ABTestEvent,
    ABTestAssignment,
)

# Core Models
from .core_models import (
    AIUsage,
    RankingHistory,
    Niche,
    NicheSnapshot,
)

# Performance & Learning Models (G4: Feedback Loop)
from .performance_models import (
    ProductPerformance,
    RecommendationOutcome,
    AILearningEvent,
    ConfidenceCalibration,
    NicheLearning,
    GlobalLearningWeights,
    PersonalLearningWeights,
    PerformanceOutcome,
)

# Backwards compatibility - import helper functions from multi_store_models if they still exist there
try:
    from .multi_store_models import (
        init_multi_store_db,
        get_multi_store_session,
        get_followup_session,
        migrate_existing_store,
        get_user_monthly_ai_usage,
        get_store_performance,
    )
except ImportError:
    # Helper functions will be defined below for forward compatibility
    pass

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

    # Enums
    "SubscriptionTier",
    "Platform",
    "StoreStatus",
    "ProductStatus",
    "DeploymentStatus",
    "AIProvider",
    "TaskType",
    "TriggerType",
    "ActionType",
    "LifecycleStage",
    "EntryTiming",
    "RiskLevel",

    # User Models
    "User",
    "UserProductRecommendation",
    "UserSettings",
    "UserEmailAccount",
    "PasswordResetToken",

    # Store Models
    "Store",
    "CrossStoreLearning",

    # Product Models
    "Product",
    "ProductDeployment",
    "ProductSaturation",
    "ProductVelocity",
    "ProductSnapshot",
    "ProductIntelligence",
    "ABTestVariant",

    # Action Models
    "Action",
    "AIActionType",
    "AIActionStatus",
    "AutoPilotLog",

    # Advertising Models
    "AdCampaign",

    # Email Models
    "Email",
    "EmailAutomationRule",
    "EmailTemplate",
    "EmailLabel",
    "EmailFollowup",

    # Testing Models
    "ABTest",
    "ABTestEvent",
    "ABTestAssignment",

    # Core Models
    "AIUsage",
    "RankingHistory",
    "Niche",
    "NicheSnapshot",

    # Performance & Learning Models (G4: Feedback Loop)
    "ProductPerformance",
    "RecommendationOutcome",
    "AILearningEvent",
    "ConfidenceCalibration",
    "NicheLearning",
    "GlobalLearningWeights",
    "PersonalLearningWeights",
    "PerformanceOutcome",

    # Helper Functions (backwards compatible)
    "init_multi_store_db",
    "get_multi_store_session",
    "get_followup_session",
    "migrate_existing_store",
    "get_user_monthly_ai_usage",
    "get_store_performance",
]
