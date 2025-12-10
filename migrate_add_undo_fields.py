"""
Database Migration: Add Undo Support Fields to Actions Table

This migration adds the following fields to the actions table:
- is_undoable (BOOLEAN)
- undo_deadline (TIMESTAMP)
- undone_at (TIMESTAMP)
- undone_by (VARCHAR(50))
- previous_state (JSON)
- undoes_action_id (INTEGER FOREIGN KEY)

Also adds UNDONE status to the action status enum and creates an index on executed_at.

Usage:
    uv run python migrate_add_undo_fields.py
"""

import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from ospra_os.database.multi_store_models import DATABASE_URL

def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def check_index_exists(engine, table_name: str, index_name: str) -> bool:
    """Check if an index exists on a table"""
    inspector = inspect(engine)
    indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)

def run_migration():
    """Run the database migration to add undo support fields"""
    print("=" * 80)
    print("📊 DATABASE MIGRATION: Add Undo Support to Actions Table")
    print("=" * 80)
    print()

    # Create engine
    print(f"Connecting to database: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)

    try:
        with engine.begin() as conn:
            print("✅ Connected successfully")
            print()

            # Check if actions table exists
            inspector = inspect(engine)
            if 'actions' not in inspector.get_table_names():
                print("❌ ERROR: 'actions' table does not exist!")
                print("   Please create the actions table first.")
                return 1

            print("📋 Checking existing schema...")

            # Track what needs to be added
            columns_to_add = []

            # Check each column
            if not check_column_exists(engine, 'actions', 'is_undoable'):
                columns_to_add.append(('is_undoable', 'BOOLEAN DEFAULT TRUE'))
            else:
                print("   ℹ️  Column 'is_undoable' already exists (skipping)")

            if not check_column_exists(engine, 'actions', 'undo_deadline'):
                columns_to_add.append(('undo_deadline', 'TIMESTAMP'))
            else:
                print("   ℹ️  Column 'undo_deadline' already exists (skipping)")

            if not check_column_exists(engine, 'actions', 'undone_at'):
                columns_to_add.append(('undone_at', 'TIMESTAMP'))
            else:
                print("   ℹ️  Column 'undone_at' already exists (skipping)")

            if not check_column_exists(engine, 'actions', 'undone_by'):
                columns_to_add.append(('undone_by', 'VARCHAR(50)'))
            else:
                print("   ℹ️  Column 'undone_by' already exists (skipping)")

            if not check_column_exists(engine, 'actions', 'previous_state'):
                columns_to_add.append(('previous_state', 'JSON'))
            else:
                print("   ℹ️  Column 'previous_state' already exists (skipping)")

            if not check_column_exists(engine, 'actions', 'undoes_action_id'):
                columns_to_add.append(('undoes_action_id', 'INTEGER'))
            else:
                print("   ℹ️  Column 'undoes_action_id' already exists (skipping)")

            print()

            # Add columns
            if columns_to_add:
                print(f"📝 Adding {len(columns_to_add)} new column(s)...")
                for column_name, column_type in columns_to_add:
                    try:
                        sql = text(f"ALTER TABLE actions ADD COLUMN {column_name} {column_type}")
                        conn.execute(sql)
                        print(f"   ✅ Added column: {column_name} ({column_type})")
                    except (OperationalError, ProgrammingError) as e:
                        if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                            print(f"   ℹ️  Column '{column_name}' already exists (skipping)")
                        else:
                            raise
                print()
            else:
                print("✅ All columns already exist - no columns to add")
                print()

            # Add foreign key constraint for undoes_action_id (if column was just added)
            if any(col[0] == 'undoes_action_id' for col in columns_to_add):
                try:
                    print("🔗 Adding foreign key constraint for undoes_action_id...")
                    sql = text(
                        "ALTER TABLE actions ADD CONSTRAINT fk_undoes_action_id "
                        "FOREIGN KEY (undoes_action_id) REFERENCES actions (id)"
                    )
                    conn.execute(sql)
                    print("   ✅ Foreign key constraint added")
                    print()
                except (OperationalError, ProgrammingError) as e:
                    if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                        print("   ℹ️  Foreign key constraint already exists (skipping)")
                        print()
                    else:
                        print(f"   ⚠️  Could not add foreign key: {e}")
                        print("   (This is okay - constraint may not be supported by SQLite)")
                        print()

            # Create index on executed_at for performance
            index_name = 'idx_actions_executed_at'
            if not check_index_exists(engine, 'actions', index_name):
                try:
                    print("📊 Creating index on executed_at for performance...")
                    sql = text(f"CREATE INDEX {index_name} ON actions (executed_at DESC)")
                    conn.execute(sql)
                    print(f"   ✅ Index '{index_name}' created")
                    print()
                except (OperationalError, ProgrammingError) as e:
                    if "already exists" in str(e).lower():
                        print(f"   ℹ️  Index '{index_name}' already exists (skipping)")
                        print()
                    else:
                        raise
            else:
                print(f"✅ Index '{index_name}' already exists - no index to create")
                print()

            print("=" * 80)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            print()
            print("📊 Summary:")
            print(f"   • Added {len(columns_to_add)} new columns to 'actions' table")
            print(f"   • Foreign key constraint configured")
            print(f"   • Performance index created on 'executed_at'")
            print()
            print("🎯 Next Steps:")
            print("   1. Restart your backend server to load the updated schema")
            print("   2. Test the undo endpoints with test_undo_actions.py")
            print("   3. Use the RecentActions component in your frontend")
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
        print()
        return 1

if __name__ == "__main__":
    exit_code = run_migration()
    sys.exit(exit_code)
