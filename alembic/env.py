"""
Alembic Environment Configuration for Ospra OS
================================================

This file configures Alembic to:
1. Import ALL SQLAlchemy models for autogenerate
2. Connect to PostgreSQL in production or SQLite locally
3. Run migrations online or offline

Usage:
    alembic revision --autogenerate -m "Description of changes"
    alembic upgrade head
    alembic downgrade -1
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ============================================================================
# CRITICAL: Import ALL models before target_metadata
# This ensures Alembic knows about all tables for autogenerate
# ============================================================================

from ospra_os.database.base import Base

# Import all model files to register them with Base.metadata
# Order matters for foreign key dependencies!

# 1. Core/Base models (no FK dependencies)
from ospra_os.database import user_models
from ospra_os.database import federated_models

# 2. Models with FK to users
from ospra_os.database import store_models
from ospra_os.database import core_models

# 3. Models with FK to stores
from ospra_os.database import product_models

# 4. Models with FK to products/stores
from ospra_os.database import advertising_models
from ospra_os.database import email_models
from ospra_os.database import testing_models
from ospra_os.database import action_models
# NOTE: actions_models (plural) was consolidated into action_models (singular).
# The AutoPilotLog class now lives in action_models.
from ospra_os.database import performance_models

# Optional models (import if they exist)
try:
    from ospra_os.database import whitelabel_models
except ImportError:
    pass

try:
    from ospra_os.database import template_models
except ImportError:
    pass

try:
    from ospra_os.database import amazon_models
except ImportError:
    pass

try:
    from ospra_os.database import aliexpress_tokens
except ImportError:
    pass

try:
    from ospra_os.database import cached_products
except ImportError:
    pass

print(f"[ALEMBIC] Loaded {len(Base.metadata.tables)} tables")

# Set target metadata for autogenerate
target_metadata = Base.metadata


# ============================================================================
# Database URL Configuration
# ============================================================================

def get_url():
    """
    Get database URL from environment.
    
    Priority:
    1. DATABASE_URL environment variable
    2. Fallback to local SQLite for development
    """
    url = os.getenv("DATABASE_URL")
    
    if not url:
        print("[ALEMBIC] WARNING: DATABASE_URL not set, using local SQLite")
        return "sqlite:///./data/ospra_local.db"
    
    # Handle Render's postgres:// format
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    # Remove async driver if present
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    
    return url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we create an Engine and associate a connection
    with the context.
    """
    # Override sqlalchemy.url from alembic.ini with environment variable
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
