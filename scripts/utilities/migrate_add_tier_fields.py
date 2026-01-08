"""
Database Migration: Add Subscription Tier Fields to UserSettings

Adds 5 new columns to the user_settings table:
- subscription_tier (default: 'free')
- tier_expires_at (nullable)
- tier_started_at (nullable)
- max_stores (default: 1)
- max_products_per_week (default: 5)
"""

import sqlite3
from datetime import datetime

DATABASE_PATH = "./oubon_store.db"  # Backend uses this file


def migrate():
    """Add tier fields to user_settings table"""
    print("="*60)
    print("DATABASE MIGRATION: Add Tier Fields to UserSettings")
    print("="*60)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(user_settings)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"\nCurrent columns in user_settings: {len(columns)}")

    tier_columns = {
        'subscription_tier': "ALTER TABLE user_settings ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'free'",
        'tier_expires_at': "ALTER TABLE user_settings ADD COLUMN tier_expires_at DATETIME",
        'tier_started_at': "ALTER TABLE user_settings ADD COLUMN tier_started_at DATETIME",
        'max_stores': "ALTER TABLE user_settings ADD COLUMN max_stores INTEGER DEFAULT 1",
        'max_products_per_week': "ALTER TABLE user_settings ADD COLUMN max_products_per_week INTEGER DEFAULT 5"
    }

    added_count = 0
    skipped_count = 0

    for column_name, alter_statement in tier_columns.items():
        if column_name in columns:
            print(f"  [OK] {column_name} already exists, skipping")
            skipped_count += 1
        else:
            try:
                cursor.execute(alter_statement)
                print(f"  [OK] Added column: {column_name}")
                added_count += 1
            except sqlite3.OperationalError as e:
                print(f"   Failed to add {column_name}: {e}")

    conn.commit()

    # Verify the changes
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60)

    cursor.execute("PRAGMA table_info(user_settings)")
    new_columns = [row[1] for row in cursor.fetchall()]
    print(f"\nTotal columns after migration: {len(new_columns)}")

    # Check for tier fields
    tier_field_names = ['subscription_tier', 'tier_expires_at', 'tier_started_at', 'max_stores', 'max_products_per_week']
    missing = [f for f in tier_field_names if f not in new_columns]

    if missing:
        print(f"\n Still missing fields: {missing}")
        conn.close()
        return False
    else:
        print("\n[OK] All tier fields present:")
        for field in tier_field_names:
            print(f"  - {field}")

    # Create index on subscription_tier for faster queries
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_settings_subscription_tier ON user_settings(subscription_tier)")
        print("\n[OK] Created index on subscription_tier")
    except sqlite3.OperationalError as e:
        print(f"\n  Index already exists or failed: {e}")

    conn.commit()
    conn.close()

    print("\n" + "="*60)
    print(f"MIGRATION COMPLETE")
    print(f"  Added: {added_count} columns")
    print(f"  Skipped: {skipped_count} columns (already exist)")
    print("="*60)

    return True


if __name__ == "__main__":
    success = migrate()
    if success:
        print("\n[LAUNCH] Database migration successful!")
        print("\nYou can now run: python test_tier_system.py")
    else:
        print("\n[ERROR] Migration failed - please check errors above")
        exit(1)
