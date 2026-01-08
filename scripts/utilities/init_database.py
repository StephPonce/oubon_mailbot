#!/usr/bin/env python3
"""
Initialize Multi-Store Database
Creates all tables and adds default user
"""

from ospra_os.database import (
    init_multi_store_db,
    get_multi_store_session,
    User,
    SubscriptionTier,
    AIProvider
)

def main():
    print("[FIX] Initializing Multi-Store Database...")
    print("="*60)

    # Database path
    db_path = "sqlite:///./oubon_store.db"

    # Initialize database (creates all tables)
    print(f"\n1⃣  Creating database: {db_path}")
    engine = init_multi_store_db(db_path)
    print("   [SUCCESS] All tables created successfully")

    # Create default user
    print("\n2⃣  Creating default user...")
    session = get_multi_store_session(db_path)

    try:
        # Check if user already exists
        existing_user = session.query(User).filter(
            User.email == "steph@oubonshop.com"
        ).first()

        if existing_user:
            print("   [WARNING]  User already exists:")
            print(f"      Email: {existing_user.email}")
            print(f"      Name: {existing_user.name}")
            print(f"      Tier: {existing_user.subscription_tier.value}")
            print(f"      Stores: {existing_user.total_stores}")
        else:
            # Create new user
            user = User(
                email="steph@oubonshop.com",
                name="Stephen Ponce",
                subscription_tier=SubscriptionTier.PRO,
                ai_preference=AIProvider.CLAUDE,
                monthly_ai_budget=200.0,
                monthly_product_limit=1000
            )
            session.add(user)
            session.commit()

            print("   [SUCCESS] Default user created:")
            print(f"      Email: {user.email}")
            print(f"      Name: {user.name}")
            print(f"      Tier: {user.subscription_tier.value}")
            print(f"      Monthly AI Budget: ${user.monthly_ai_budget}")
            print(f"      Product Limit: {user.monthly_product_limit}")

    except Exception as e:
        print(f"   [ERROR] Error creating user: {e}")
        session.rollback()
    finally:
        session.close()

    print("\n" + "="*60)
    print("[SUCCESS] Database Initialization Complete!")
    print("\nNext steps:")
    print("  • Backend will now work with /api/portfolio endpoints")
    print("  • Run: python3 test_multi_store_system.py")
    print("  • Or visit: http://localhost:8001/docs")
    print()

if __name__ == "__main__":
    main()
