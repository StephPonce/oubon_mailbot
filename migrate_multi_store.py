#!/usr/bin/env python3
"""
Multi-Store Schema Migration Script

This script adds the new multi-store fields to the existing database:
- Store.status (enum: setup, active, paused, disconnected, error)
- Store.pending_actions_count (integer)
- Store.sync_error (text, nullable)
- CrossStoreLearning table (new)

Usage:
    python migrate_multi_store.py

This will:
1. Backup the current database
2. Add new columns to the Store table
3. Create the CrossStoreLearning table
4. Set default values for existing stores
"""

import os
import shutil
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session

# Import database models
from ospra_os.database import (
    Base,
    get_engine,
    Store,
    CrossStoreLearning,
    StoreStatus
)


def backup_database(db_path: str) -> str:
    """Create a backup of the database before migration."""
    if not os.path.exists(db_path):
        print(f"⚠️  Database not found at {db_path}")
        return ""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"

    shutil.copy2(db_path, backup_path)
    print(f"✅ Database backed up to: {backup_path}")
    return backup_path


def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column already exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate_database():
    """Run the multi-store migration."""
    print("🚀 Starting Multi-Store Schema Migration")
    print("=" * 60)

    # Get database engine
    engine = get_engine()
    db_url = str(engine.url)

    print(f"📊 Database: {db_url}")

    # Backup database if it's SQLite
    if db_url.startswith('sqlite'):
        db_path = db_url.replace('sqlite:///', '')
        backup_path = backup_database(db_path)
        if not backup_path:
            print("\n⚠️  No existing database found. Creating new database...")

    # Check existing schema
    print("\n🔍 Checking existing schema...")

    # Check Store table columns
    store_columns_to_add = []
    if not check_column_exists(engine, 'stores', 'status'):
        store_columns_to_add.append(('status', 'VARCHAR', 'active'))
    if not check_column_exists(engine, 'stores', 'pending_actions_count'):
        store_columns_to_add.append(('pending_actions_count', 'INTEGER', '0'))
    if not check_column_exists(engine, 'stores', 'sync_error'):
        store_columns_to_add.append(('sync_error', 'TEXT', 'NULL'))

    # Check if CrossStoreLearning table exists
    cross_store_table_exists = check_table_exists(engine, 'cross_store_learnings')

    if not store_columns_to_add and cross_store_table_exists:
        print("✅ Schema is already up to date!")
        return

    # Apply migrations
    with engine.connect() as conn:
        print("\n📝 Applying migrations...")

        # Add new columns to Store table
        for column_name, column_type, default_value in store_columns_to_add:
            print(f"   Adding column: stores.{column_name}")

            if engine.name == 'sqlite':
                # SQLite doesn't support ALTER TABLE ADD COLUMN with DEFAULT and NOT NULL
                # So we add it as nullable first, then update, then make it NOT NULL
                conn.execute(text(
                    f"ALTER TABLE stores ADD COLUMN {column_name} {column_type}"
                ))
                conn.commit()

                # Set default values for existing rows
                if default_value != 'NULL':
                    conn.execute(text(
                        f"UPDATE stores SET {column_name} = {default_value} WHERE {column_name} IS NULL"
                    ))
                    conn.commit()
            else:
                # PostgreSQL supports ALTER TABLE ADD COLUMN with DEFAULT
                conn.execute(text(
                    f"ALTER TABLE stores ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
                ))
                conn.commit()

            print(f"   ✅ Added column: stores.{column_name}")

        # Create CrossStoreLearning table if it doesn't exist
        if not cross_store_table_exists:
            print("   Creating table: cross_store_learnings")
            Base.metadata.tables['cross_store_learnings'].create(engine)
            print("   ✅ Created table: cross_store_learnings")

        # Update existing stores to have 'active' status
        if 'status' in [col[0] for col in store_columns_to_add]:
            print("\n   Setting default status for existing stores...")
            conn.execute(text(
                "UPDATE stores SET status = 'active' WHERE status IS NULL OR status = ''"
            ))
            conn.commit()
            print("   ✅ Updated existing stores to 'active' status")

    print("\n" + "=" * 60)
    print("✅ Migration completed successfully!")
    print("\nNew features available:")
    print("  • Store status tracking (setup, active, paused, disconnected, error)")
    print("  • Pending actions counter")
    print("  • Sync error logging")
    print("  • Cross-store learning system")
    print("\nAPI Endpoints:")
    print("  • GET /api/stores - List all stores")
    print("  • GET /api/stores/{id} - Get store details")
    print("  • POST /api/stores - Create new store")
    print("  • PATCH /api/stores/{id}/status - Update store status")
    print("  • POST /api/stores/generate-learnings - Generate insights")
    print("  • GET /api/stores/{id}/insights - Get recommendations")
    print("  • POST /api/stores/insights/{id}/apply - Apply insight")
    print("  • POST /api/stores/insights/{id}/dismiss - Dismiss insight")


if __name__ == "__main__":
    try:
        migrate_database()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("\nIf you have a backup, you can restore it manually.")
        raise
