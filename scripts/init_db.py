#!/usr/bin/env python3
"""
Initialize/Migrate Database
===========================

This script ensures all database tables exist, including:
- PasswordResetToken (for password reset flow)
- All other models

Run this whenever you add new models or on fresh install.

Usage:
    python scripts/init_db.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import create_engine, inspect
from ospra_os.database.multi_store_models import Base, PasswordResetToken, User

def init_database():
    """Initialize database and create all tables"""
    
    # Get database URL from environment
    database_url = os.getenv("OUBONSHOP_database_url", "sqlite:///./ospra_os.db")
    
    print(f"[FIX] Initializing database: {database_url}")
    
    # Create engine
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        echo=False
    )
    
    # Get list of existing tables
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    print(f"[LIST] Existing tables: {existing_tables}")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Verify tables after creation
    inspector = inspect(engine)
    new_tables = inspector.get_table_names()
    print(f"[SUCCESS] Tables after migration: {new_tables}")
    
    # Check specifically for PasswordResetToken
    if "password_reset_tokens" in new_tables:
        print("[SUCCESS] password_reset_tokens table exists!")
    else:
        print("[ERROR] password_reset_tokens table NOT found!")
    
    # Check for users table
    if "users" in new_tables:
        print("[SUCCESS] users table exists!")
    else:
        print("[ERROR] users table NOT found!")
    
    # Show all model tables
    print("\n[STATS] All registered models:")
    for table_name in Base.metadata.tables.keys():
        status = "[SUCCESS]" if table_name in new_tables else "[ERROR]"
        print(f"   {status} {table_name}")
    
    return engine

if __name__ == "__main__":
    print("=" * 60)
    print("  OSPRA DATABASE INITIALIZATION")
    print("=" * 60)
    
    try:
        engine = init_database()
        print("\n[SUCCESS] Database initialization complete!")
    except Exception as e:
        print(f"\n[ERROR] Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
