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
    SessionLocal,  # Module-level SessionLocal for backward compatibility
    get_multi_store_session,  # Multi-store session support
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
    ActionLog,
    AutoPilotLog,  # Consolidated from actions_models.py
)

# User Models
from .user_models import (
    User,
    UserProductRecommendation,
    UserSettings,
    UserEmailAccount,
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

# Amazon Models (SP-API integration)
try:
    from .amazon_models import (
        AmazonAccount,
        AmazonListing,
        AmazonOrder,
        FBAShipment,
    )
except ImportError:
    # Amazon models import depends on ospra_os.security.credential_encryption
    # being importable at package init time; fall back to None if the package
    # isn't wired up yet in this environment.
    AmazonAccount = None
    AmazonListing = None
    AmazonOrder = None
    FBAShipment = None

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

# Cached Google Trends (task #47 — trend pre-warm store)
from .trend_cache_models import CachedGoogleTrend

# Security Audit Models
try:
    from ospra_os.security.security_audit import SecurityAuditLog
except ImportError:
    SecurityAuditLog = None  # Optional - created if security_audit module exists

# Tenant Audit Models
try:
    from ospra_os.tenancy.audit import TenantAuditLog
except ImportError:
    TenantAuditLog = None  # Optional - created if tenancy module exists

# Backwards compatibility - these functions are now available from connection.py
# and email_models.py/init_multi_store.py but kept in __all__ for compatibility

__all__ = [
    # Connection utilities
    "get_engine",
    "get_session",
    "get_session_context",
    "get_db",
    "init_database",
    "check_database_connection",
    "SessionLocal",  # Module-level SessionLocal for backward compatibility

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
    "ActionLog",
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

    # Amazon Models
    "AmazonAccount",
    "AmazonListing",
    "AmazonOrder",
    "FBAShipment",

    # Core Models
    "AIUsage",
    "RankingHistory",
    "CachedGoogleTrend",
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

    # Audit Models
    "SecurityAuditLog",
    "TenantAuditLog",

    # Helper Functions (backwards compatible)
    "init_multi_store_db",
    "get_multi_store_session",
    "get_followup_session",
    "migrate_existing_store",
    "get_user_monthly_ai_usage",
    "get_store_performance",
]
