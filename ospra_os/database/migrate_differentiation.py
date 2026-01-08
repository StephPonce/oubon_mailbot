"""
Database migration for differentiation features

Creates tables for:
- ProductSaturation (track product recommendation counts)
- ProductVelocity (track product lifecycle phases)
- UserProductRecommendation (track user-product relationships)
"""
from sqlalchemy import create_engine, inspect
from ospra_os.database.multi_store_models import Base, ProductVelocity, ProductSaturation, UserProductRecommendation
from ospra_os.core.settings import get_settings


def migrate():
    """Run migration to add differentiation tables"""
    settings = get_settings()
    engine = create_engine(settings.database_url)

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    print("=" * 70)
    print("[REFRESH] DIFFERENTIATION SYSTEM MIGRATION")
    print("=" * 70)

    # Create all new tables
    print("\nCreating differentiation tables...")
    Base.metadata.create_all(engine)

    # Tables to check
    new_tables = [
        'product_saturation',
        'product_velocity',
        'user_product_recommendations'
    ]

    print("\nTable Status:")
    for table in new_tables:
        if table in existing_tables:
            print(f"  [SUCCESS] {table} - Already exists")
        else:
            print(f"  [SUCCESS] {table} - Created successfully")

    # Verify all tables exist now
    inspector = inspect(engine)
    current_tables = inspector.get_table_names()

    all_created = all(table in current_tables for table in new_tables)

    print("\n" + "=" * 70)
    if all_created:
        print("[SUCCESS] MIGRATION COMPLETE - All tables ready!")
    else:
        print("[WARNING]  MIGRATION INCOMPLETE - Some tables missing")
        missing = [t for t in new_tables if t not in current_tables]
        print(f"Missing: {', '.join(missing)}")
    print("=" * 70)

    return all_created


if __name__ == "__main__":
    success = migrate()
    exit(0 if success else 1)
