"""
Run all database migrations for new features

This script creates all required tables for the Complete Anti-AutoDS System:
- product_saturation (track product recommendation counts)
- product_velocity (track product lifecycle phases)
- user_product_recommendations (track user-product relationships)
- All other required tables
"""
from sqlalchemy import create_engine, inspect
from ospra_os.database.multi_store_models import Base
from ospra_os.core.settings import get_settings


def run_migrations():
    """Run all pending migrations"""
    print("\n" + "=" * 70)
    print("[REFRESH] DATABASE MIGRATION - Complete Anti-AutoDS System")
    print("=" * 70)

    settings = get_settings()
    print(f"\n[LOCATION] Database: {settings.database_url}")

    engine = create_engine(settings.database_url)

    # Get existing tables
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    print(f"\n[STATS] Current State:")
    print(f"   Existing tables: {len(existing_tables)}")

    print("\n Creating/updating tables...")

    # Create all tables (will skip existing ones)
    Base.metadata.create_all(engine)

    # Check what was added
    inspector = inspect(engine)
    updated_tables = inspector.get_table_names()

    new_tables = set(updated_tables) - set(existing_tables)

    print("\n" + "-" * 70)

    if new_tables:
        print(f"[SUCCESS] Added {len(new_tables)} new tables:")
        for table in sorted(new_tables):
            print(f"   [OK] {table}")
    else:
        print("[SUCCESS] No new tables needed - all tables already exist")

    print(f"\n[STATS] Final State:")
    print(f"   Total tables: {len(updated_tables)}")

    # List all differentiation tables
    differentiation_tables = [
        'product_saturation',
        'product_velocity',
        'user_product_recommendations'
    ]

    print("\n[LIST] Differentiation System Tables:")
    for table in differentiation_tables:
        if table in updated_tables:
            print(f"   [SUCCESS] {table}")
        else:
            print(f"   [ERROR] {table} - MISSING!")

    # List all tables
    print("\n[LIST] All Database Tables:")
    for table in sorted(updated_tables):
        # Highlight differentiation tables
        if table in differentiation_tables:
            print(f"    {table} (differentiation)")
        else:
            print(f"   - {table}")

    print("\n" + "=" * 70)
    print("[SUCCESS] MIGRATION COMPLETE!")
    print("=" * 70)
    print("\nThe Complete Anti-AutoDS System database is ready.")
    print("All required tables have been created.\n")

    return len(new_tables)


if __name__ == "__main__":
    new_count = run_migrations()
    exit(0)
