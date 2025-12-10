"""
Database Migration: Add Auto-Pilot Support Tables

This migration adds the following tables:
- user_settings: Per-user auto-pilot configuration
- auto_pilot_logs: Decision audit trail for auto-pilot actions

Implements GROK RECOMMENDATION #7: Auto-Pilot Mode Toggle

Usage:
    uv run python migrate_add_auto_pilot.py
"""

import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from ospra_os.database.multi_store_models import DATABASE_URL

def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def check_index_exists(engine, table_name: str, index_name: str) -> bool:
    """Check if an index exists on a table"""
    inspector = inspect(engine)
    try:
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    except:
        return False

def run_migration():
    """Run the database migration to add auto-pilot tables"""
    print("=" * 80)
    print("📊 DATABASE MIGRATION: Add Auto-Pilot Support Tables")
    print("   Implements GROK RECOMMENDATION #7: Auto-Pilot Mode Toggle")
    print("=" * 80)
    print()

    # Create engine
    print(f"Connecting to database: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)

    try:
        with engine.begin() as conn:
            print("✅ Connected successfully")
            print()

            # Check if users table exists (prerequisite)
            inspector = inspect(engine)
            if 'users' not in inspector.get_table_names():
                print("❌ ERROR: 'users' table does not exist!")
                print("   Please ensure the database is properly initialized.")
                return 1

            # ============================================================
            # Create user_settings table
            # ============================================================
            if not check_table_exists(engine, 'user_settings'):
                print("📝 Creating 'user_settings' table...")
                try:
                    sql = text("""
                        CREATE TABLE user_settings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL UNIQUE,
                            auto_pilot_enabled BOOLEAN DEFAULT FALSE,
                            auto_pilot_threshold REAL DEFAULT 85.0,
                            auto_pilot_rules JSON DEFAULT '{}',
                            notify_on_auto_execute BOOLEAN DEFAULT TRUE,
                            daily_summary_email BOOLEAN DEFAULT TRUE,
                            daily_auto_execute_limit INTEGER DEFAULT 20,
                            max_auto_spend REAL DEFAULT 500.0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                        )
                    """)
                    conn.execute(sql)
                    print("   ✅ Created table: user_settings")
                    print()
                except (OperationalError, ProgrammingError) as e:
                    if "already exists" in str(e).lower():
                        print("   ℹ️  Table 'user_settings' already exists (skipping)")
                        print()
                    else:
                        raise
            else:
                print("✅ Table 'user_settings' already exists - skipping creation")
                print()

            # Create index on user_id for user_settings
            index_name = 'idx_user_settings_user_id'
            if not check_index_exists(engine, 'user_settings', index_name):
                try:
                    print(f"📊 Creating index '{index_name}' on user_settings...")
                    sql = text(f"CREATE UNIQUE INDEX {index_name} ON user_settings (user_id)")
                    conn.execute(sql)
                    print(f"   ✅ Index '{index_name}' created")
                    print()
                except (OperationalError, ProgrammingError) as e:
                    if "already exists" in str(e).lower():
                        print(f"   ℹ️  Index '{index_name}' already exists (skipping)")
                        print()
                    else:
                        print(f"   ⚠️  Could not create index: {e}")
                        print()

            # ============================================================
            # Create auto_pilot_logs table
            # ============================================================
            if not check_table_exists(engine, 'auto_pilot_logs'):
                print("📝 Creating 'auto_pilot_logs' table...")
                try:
                    sql = text("""
                        CREATE TABLE auto_pilot_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            action_id INTEGER NOT NULL,
                            confidence REAL,
                            threshold_used REAL,
                            executed BOOLEAN DEFAULT FALSE,
                            skipped_reason VARCHAR(255),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                            FOREIGN KEY (action_id) REFERENCES actions (id) ON DELETE CASCADE
                        )
                    """)
                    conn.execute(sql)
                    print("   ✅ Created table: auto_pilot_logs")
                    print()
                except (OperationalError, ProgrammingError) as e:
                    if "already exists" in str(e).lower():
                        print("   ℹ️  Table 'auto_pilot_logs' already exists (skipping)")
                        print()
                    else:
                        raise
            else:
                print("✅ Table 'auto_pilot_logs' already exists - skipping creation")
                print()

            # Create indexes on auto_pilot_logs for performance
            indexes_to_create = [
                ('idx_autopilot_user_id', 'user_id'),
                ('idx_autopilot_action_id', 'action_id'),
                ('idx_autopilot_created_at', 'created_at DESC')
            ]

            for index_name, column_spec in indexes_to_create:
                if not check_index_exists(engine, 'auto_pilot_logs', index_name):
                    try:
                        print(f"📊 Creating index '{index_name}' on auto_pilot_logs...")
                        sql = text(f"CREATE INDEX {index_name} ON auto_pilot_logs ({column_spec})")
                        conn.execute(sql)
                        print(f"   ✅ Index '{index_name}' created")
                        print()
                    except (OperationalError, ProgrammingError) as e:
                        if "already exists" in str(e).lower():
                            print(f"   ℹ️  Index '{index_name}' already exists (skipping)")
                            print()
                        else:
                            print(f"   ⚠️  Could not create index: {e}")
                            print()

            # Create composite index for common query pattern
            composite_index = 'idx_autopilot_user_created'
            if not check_index_exists(engine, 'auto_pilot_logs', composite_index):
                try:
                    print(f"📊 Creating composite index '{composite_index}'...")
                    sql = text(f"CREATE INDEX {composite_index} ON auto_pilot_logs (user_id, created_at DESC)")
                    conn.execute(sql)
                    print(f"   ✅ Composite index '{composite_index}' created")
                    print()
                except (OperationalError, ProgrammingError) as e:
                    if "already exists" in str(e).lower():
                        print(f"   ℹ️  Index '{composite_index}' already exists (skipping)")
                        print()
                    else:
                        print(f"   ⚠️  Could not create composite index: {e}")
                        print()

            print("=" * 80)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            print()
            print("📊 Summary:")
            print("   • Created 'user_settings' table with per-user auto-pilot config")
            print("   • Created 'auto_pilot_logs' table for decision audit trail")
            print("   • Created performance indexes for efficient querying")
            print()
            print("🎯 Next Steps:")
            print("   1. Restart your backend server to load the updated schema")
            print("   2. Register the auto-pilot router in ospra_os/main.py")
            print("   3. Test the auto-pilot endpoints")
            print("   4. Add AutoPilotToggle component to your dashboard")
            print()
            print("📖 Auto-Pilot Features:")
            print("   • Autonomous execution of high-confidence actions (≥85%)")
            print("   • User-configurable thresholds and safety limits")
            print("   • Daily execution caps (default: 20 actions/day)")
            print("   • Daily spend limits (default: $500/day)")
            print("   • Complete audit trail of all decisions")
            print("   • Per-action-type rules and overrides")
            print()

            return 0

    except Exception as e:
        print()
        print("=" * 80)
        print("❌ MIGRATION FAILED!")
        print("=" * 80)
        print(f"Error: {e}")
        print()
        print("💡 Troubleshooting:")
        print("   1. Ensure the database is accessible")
        print("   2. Verify DATABASE_URL in ospra_os/database/multi_store_models.py")
        print("   3. Make sure no other process is locking the database")
        print("   4. Check that 'users' and 'actions' tables exist")
        print()
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = run_migration()
    sys.exit(exit_code)
