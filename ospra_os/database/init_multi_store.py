#!/usr/bin/env python3
"""
Multi-Store Database Initialization and Migration
Initialize new multi-store database and migrate existing Oubon Shop store
"""

import argparse
import sys
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from ospra_os.database.multi_store_models import (
    Base,
    User,
    Store,
    Product,
    ProductDeployment,
    AIUsage,
    UserSettings,
    SubscriptionTier,
    Platform,
    AIProvider,
    init_multi_store_db,
    get_multi_store_session,
)
from ospra_os.core.settings import get_settings


def print_header(text: str):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_success(text: str):
    """Print success message"""
    print(f"✅ {text}")


def print_error(text: str):
    """Print error message"""
    print(f"❌ {text}")


def print_warning(text: str):
    """Print warning message"""
    print(f"⚠️  {text}")


def print_info(text: str):
    """Print info message"""
    print(f"ℹ️  {text}")


def get_table_list(engine) -> list:
    """Get list of existing tables in database"""
    inspector = inspect(engine)
    return inspector.get_table_names()


def initialize_database(database_url: str) -> bool:
    """
    Initialize multi-store database tables

    Args:
        database_url: Database connection string

    Returns:
        bool: True if successful, False otherwise
    """
    print_header("DATABASE INITIALIZATION")

    try:
        print_info(f"Database: {database_url}")

        # Get existing tables before initialization
        from sqlalchemy import create_engine
        engine = create_engine(database_url)
        existing_tables = set(get_table_list(engine))

        print_info(f"Existing tables: {len(existing_tables)}")
        if existing_tables:
            print(f"   {', '.join(sorted(existing_tables))}")

        # Initialize database (creates all tables)
        print("\nCreating multi-store tables...")
        engine = init_multi_store_db(database_url)

        # Get new tables after initialization
        new_tables = set(get_table_list(engine)) - existing_tables
        all_tables = get_table_list(engine)

        print_success(f"Database initialized!")
        print(f"\n📊 Total tables: {len(all_tables)}")

        if new_tables:
            print(f"\n🆕 New tables created ({len(new_tables)}):")
            for table in sorted(new_tables):
                print(f"   • {table}")

        # Show multi-store tables
        multi_store_tables = ['users', 'stores', 'products', 'product_deployments',
                              'ai_usage', 'user_settings']
        existing_multi_store = [t for t in multi_store_tables if t in all_tables]

        print(f"\n✨ Multi-store tables ({len(existing_multi_store)}/{len(multi_store_tables)}):")
        for table in multi_store_tables:
            status = "✅" if table in all_tables else "❌"
            print(f"   {status} {table}")

        return True

    except Exception as e:
        print_error(f"Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def migrate_existing_store(database_url: str, auto_confirm: bool = False) -> bool:
    """
    Migrate existing Oubon Shop store to multi-store schema

    Args:
        database_url: Database connection string
        auto_confirm: Skip confirmation prompt

    Returns:
        bool: True if successful, False otherwise
    """
    print_header("MIGRATE EXISTING STORE")

    try:
        # Get settings
        settings = get_settings()

        # Check for Shopify credentials
        shopify_store = settings.SHOPIFY_STORE_DOMAIN or settings.SHOPIFY_STORE
        shopify_token = settings.SHOPIFY_ADMIN_TOKEN or settings.SHOPIFY_ACCESS_TOKEN
        shopify_version = settings.SHOPIFY_API_VERSION or "2025-01"

        if not shopify_store or not shopify_token:
            print_error("Missing Shopify credentials in environment!")
            print_info("Required environment variables:")
            print("   • OUBONSHOP_SHOPIFY_STORE_DOMAIN (or OUBONSHOP_SHOPIFY_STORE)")
            print("   • OUBONSHOP_SHOPIFY_ADMIN_TOKEN (or OUBONSHOP_SHOPIFY_ACCESS_TOKEN)")
            return False

        # Show what will be migrated
        print_info("Migration Plan:")
        print("\n1️⃣  Create Default User:")
        print(f"   Email: steph@oubonshop.com")
        print(f"   Name: Stephen Ponce")
        print(f"   Tier: PRO")
        print(f"   AI Provider: Claude")
        print(f"   Monthly AI Budget: $200")
        print(f"   Product Limit: 1000")

        print("\n2️⃣  Create Oubon Shop Store:")
        print(f"   Name: Oubon Shop")
        print(f"   Platform: Shopify")
        print(f"   Store URL: {shopify_store}")
        print(f"   API Version: {shopify_version}")
        print(f"   Token: {shopify_token[:15]}...")
        print(f"   Niche: smart_home")
        print(f"   Currency: USD")

        # Confirmation prompt
        if not auto_confirm:
            print("\n" + "-" * 70)
            response = input("Proceed with migration? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print_warning("Migration cancelled by user")
                return False

        # Connect to database
        print("\nConnecting to database...")
        session = get_multi_store_session(database_url)

        try:
            # Check if user already exists
            user_email = "steph@oubonshop.com"
            existing_user = session.query(User).filter(User.email == user_email).first()

            if existing_user:
                print_warning(f"User already exists: {user_email}")
                user = existing_user
            else:
                # Create user
                print("\nCreating user...")
                user = User(
                    email=user_email,
                    name="Stephen Ponce",
                    subscription_tier=SubscriptionTier.PRO,
                    ai_preference=AIProvider.CLAUDE,
                    monthly_ai_budget=200.0,
                    monthly_product_limit=1000,
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                print_success(f"User created: {user.email} (ID: {user.id})")

            # Check if store already exists
            existing_store = session.query(Store).filter(
                Store.user_id == user.id,
                Store.store_url == shopify_store
            ).first()

            if existing_store:
                print_warning(f"Store already exists: {existing_store.store_name}")
                store = existing_store
            else:
                # Create store
                print("\nCreating Oubon Shop store...")
                store = Store(
                    user_id=user.id,
                    store_name="Oubon Shop",
                    store_url=shopify_store,
                    platform=Platform.SHOPIFY,
                    credentials={
                        "shop_url": shopify_store,
                        "access_token": shopify_token,
                        "api_version": shopify_version,
                    },
                    niche="smart_home",
                    target_market="US",
                    currency="USD",
                    is_active=True,
                    rank_position=1,  # First store
                )
                session.add(store)

                # Update user store count
                user.total_stores = session.query(Store).filter(Store.user_id == user.id).count() + 1

                session.commit()
                session.refresh(store)
                print_success(f"Store created: {store.store_name} (ID: {store.id})")

            # Create default user settings if not exists
            existing_settings = session.query(UserSettings).filter(
                UserSettings.user_id == user.id
            ).first()

            if not existing_settings:
                print("\nCreating default user settings...")
                settings_obj = UserSettings(
                    user_id=user.id,
                    auto_deploy_to_shopify=False,  # Safe default
                    auto_generate_content=True,
                    email_notifications=True,
                    notify_new_products=True,
                )
                session.add(settings_obj)
                session.commit()
                print_success("User settings created")

            # Show final status
            print_header("MIGRATION COMPLETE")

            print("📊 Migration Summary:\n")
            print(f"User:")
            print(f"   • Email: {user.email}")
            print(f"   • Tier: {user.subscription_tier.value}")
            print(f"   • Total Stores: {user.total_stores}")
            print(f"   • Created: {user.created_at}")

            print(f"\nStore:")
            print(f"   • Name: {store.store_name}")
            print(f"   • Platform: {store.platform.value}")
            print(f"   • URL: {store.store_url}")
            print(f"   • Rank: #{store.rank_position}")
            print(f"   • Active: {'Yes' if store.is_active else 'No'}")
            print(f"   • Created: {store.created_at}")

            print("\n" + "=" * 70)
            print_success("Oubon Shop successfully migrated to multi-store system!")
            print("\nNext steps:")
            print("   • Test API: curl http://localhost:8001/api/portfolio/overview")
            print("   • View docs: http://localhost:8001/docs")
            print("   • Add more stores: POST /api/portfolio/stores/add")

            return True

        finally:
            session.close()

    except Exception as e:
        print_error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_status(database_url: str) -> bool:
    """
    Show current multi-store database status

    Args:
        database_url: Database connection string

    Returns:
        bool: True if successful, False otherwise
    """
    print_header("MULTI-STORE DATABASE STATUS")

    try:
        # Check if database exists
        from sqlalchemy import create_engine
        engine = create_engine(database_url)

        print_info(f"Database: {database_url}")

        # Get tables
        tables = get_table_list(engine)
        print(f"\n📊 Total tables: {len(tables)}")

        # Check for multi-store tables
        required_tables = ['users', 'stores', 'products', 'product_deployments',
                          'ai_usage', 'user_settings']

        print(f"\n✨ Multi-store tables:")
        all_exist = True
        for table in required_tables:
            exists = table in tables
            status = "✅" if exists else "❌"
            print(f"   {status} {table}")
            if not exists:
                all_exist = False

        if not all_exist:
            print_warning("\nDatabase not initialized! Run: python init_multi_store.py --init")
            return False

        # Query database stats
        print("\n" + "-" * 70)
        session = get_multi_store_session(database_url)

        try:
            # Count records
            user_count = session.query(User).count()
            store_count = session.query(Store).count()
            product_count = session.query(Product).count()
            deployment_count = session.query(ProductDeployment).count()

            print("\n📈 Database Statistics:\n")
            print(f"   Users: {user_count}")
            print(f"   Stores: {store_count}")
            print(f"   Products: {product_count}")
            print(f"   Deployments: {deployment_count}")

            # Show users
            if user_count > 0:
                print("\n👥 Users:")
                users = session.query(User).all()
                for user in users:
                    print(f"\n   • {user.email}")
                    print(f"     Name: {user.name}")
                    print(f"     Tier: {user.subscription_tier.value}")
                    print(f"     Stores: {user.total_stores}")
                    print(f"     Products: {user.total_products}")
                    print(f"     Created: {user.created_at}")

            # Show stores
            if store_count > 0:
                print("\n🏪 Stores:")
                stores = session.query(Store).order_by(Store.rank_position).all()
                for store in stores:
                    active_emoji = "🟢" if store.is_active else "🔴"
                    # Count products for this store
                    products_count = session.query(Product).filter(Product.store_id == store.id).count()

                    print(f"\n   {active_emoji} {store.store_name}")
                    print(f"     Platform: {store.platform.value}")
                    print(f"     URL: {store.store_url}")
                    print(f"     Rank: #{store.rank_position}")
                    print(f"     Niche: {store.niche or 'N/A'}")
                    print(f"     Products: {products_count}")
                    print(f"     Revenue: ${store.total_revenue:.2f}")

            if user_count == 0 and store_count == 0:
                print_warning("\nNo data in database! Run: python init_multi_store.py --migrate")

            print("\n" + "=" * 70)
            print_success("Database is operational!")

            if user_count == 0:
                print("\n💡 Next step: python init_multi_store.py --migrate")
            else:
                print("\n💡 Access API: http://localhost:8001/api/portfolio/overview")

            return True

        finally:
            session.close()

    except Exception as e:
        print_error(f"Status check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Multi-Store Database Initialization and Migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize database tables
  python init_multi_store.py --init

  # Migrate existing Oubon Shop store
  python init_multi_store.py --migrate

  # Migrate without confirmation
  python init_multi_store.py --migrate --yes

  # Show database status
  python init_multi_store.py --status

  # Custom database URL
  python init_multi_store.py --init --db sqlite:///./custom.db
        """
    )

    parser.add_argument(
        '--init',
        action='store_true',
        help='Initialize multi-store database tables'
    )

    parser.add_argument(
        '--migrate',
        action='store_true',
        help='Migrate existing Oubon Shop store to multi-store schema'
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Show current multi-store database status'
    )

    parser.add_argument(
        '--db',
        '--database-url',
        dest='database_url',
        help='Database URL (default: from settings)',
        default=None
    )

    parser.add_argument(
        '--yes',
        '-y',
        action='store_true',
        help='Auto-confirm migration (skip prompt)'
    )

    args = parser.parse_args()

    # Get database URL
    if args.database_url:
        database_url = args.database_url
    else:
        settings = get_settings()
        database_url = settings.database_url

    # Check if any action specified
    if not (args.init or args.migrate or args.status):
        parser.print_help()
        print("\n" + "=" * 70)
        print_warning("No action specified!")
        print_info("Use --init, --migrate, or --status")
        print("=" * 70)
        sys.exit(1)

    # Execute actions
    success = True

    if args.init:
        success = initialize_database(database_url) and success

    if args.migrate:
        if not args.init:
            # Auto-initialize if migrating
            print_info("Auto-initializing database before migration...")
            success = initialize_database(database_url) and success

        if success:
            success = migrate_existing_store(database_url, auto_confirm=args.yes) and success

    if args.status:
        success = show_status(database_url) and success

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
