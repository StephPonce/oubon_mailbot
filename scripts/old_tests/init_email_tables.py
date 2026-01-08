#!/usr/bin/env python3
"""
Initialize email-related database tables.

This script ensures the user_email_accounts and emails tables are created.
"""

from ospra_os.database.multi_store_models import Base, User, UserEmailAccount, Email, init_multi_store_db, get_multi_store_session
from sqlalchemy import inspect

def main():
    print("=" * 70)
    print("Database Table Initialization")
    print("=" * 70)
    print()

    # Initialize database (creates all tables)
    database_url = "sqlite:///./oubon_store.db"
    engine = init_multi_store_db(database_url)

    # Verify tables were created
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"\n[STATS] Total tables in database: {len(tables)}")
    print("\n[SUCCESS] Tables:")
    for table in sorted(tables):
        print(f"   • {table}")

    # Check specifically for email tables
    print("\n[SEARCH] Email-related tables:")
    email_tables = ['user_email_accounts', 'emails']
    for table_name in email_tables:
        if table_name in tables:
            print(f"   [SUCCESS] {table_name}")

            # Show columns
            columns = inspector.get_columns(table_name)
            print(f"      Columns: {len(columns)}")
            for col in columns:
                print(f"         - {col['name']} ({col['type']})")
        else:
            print(f"   [ERROR] {table_name} - MISSING!")

    print()
    print("=" * 70)
    print("[SUCCESS] Database initialization complete!")
    print("=" * 70)

if __name__ == '__main__':
    main()
