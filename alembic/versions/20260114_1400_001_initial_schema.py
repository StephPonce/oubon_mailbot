"""Initial schema - baseline current database state

Revision ID: 001
Revises: 
Create Date: 2026-01-14 14:00:00.000000

This migration establishes the baseline for Ospra Intelligence database.
All tables that exist in production as of this date are captured here.

IMPORTANT: This migration uses checkfirst=True to safely run against
existing databases without failing if tables already exist.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create all tables if they don't exist.
    
    This is a baseline migration - it stamps the current schema state.
    Tables are created with checkfirst=True so this safely runs on
    databases that already have the tables.
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()
    
    print(f"[MIGRATION 001] Existing tables: {len(existing_tables)}")
    
    # If critical tables exist, this is an existing database - just stamp it
    if 'users' in existing_tables and 'stores' in existing_tables:
        print("[MIGRATION 001] Database already has schema - stamping as baseline")
        return
    
    print("[MIGRATION 001] Creating initial schema...")
    
    # Import all models to ensure they're registered
    from ospra_os.database.base import Base
    from ospra_os.database import user_models
    from ospra_os.database import federated_models
    from ospra_os.database import core_models
    from ospra_os.database import product_models
    from ospra_os.database import store_models
    from ospra_os.database import testing_models
    from ospra_os.database import email_models
    from ospra_os.database import action_models
    from ospra_os.database import advertising_models
    
    # Create all tables
    Base.metadata.create_all(bind=bind, checkfirst=True)
    
    # Verify
    inspector = inspect(bind)
    new_tables = inspector.get_table_names()
    print(f"[MIGRATION 001] Tables after migration: {len(new_tables)}")


def downgrade() -> None:
    """
    Downgrade removes all tables.
    
    WARNING: This is destructive and will delete all data!
    Only use in development or when intentionally resetting the database.
    """
    bind = op.get_bind()
    
    # Import to get metadata
    from ospra_os.database.base import Base
    from ospra_os.database import user_models
    from ospra_os.database import federated_models
    from ospra_os.database import core_models
    from ospra_os.database import product_models
    from ospra_os.database import store_models
    from ospra_os.database import testing_models
    from ospra_os.database import email_models
    from ospra_os.database import action_models
    from ospra_os.database import advertising_models
    
    # Drop all tables
    Base.metadata.drop_all(bind=bind)
    print("[MIGRATION 001] All tables dropped")
