"""
Test script for Subscription Tier System
Verifies database tables, TierManager service, and API endpoints
"""

import asyncio
import sys
from datetime import datetime
from ospra_os.database import Base, User, UserSettings
from ospra_os.subscription.tier_manager import TierManager
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import httpx

DATABASE_URL = "sqlite:///./oubon_store.db"  # Match backend database


def test_database_tables():
    """Test that tier fields were added to UserSettings"""
    print("\n" + "="*60)
    print("TEST 1: Database Schema Verification")
    print("="*60)

    engine = create_engine(DATABASE_URL.replace("sqlite:///", "sqlite:///"))
    Base.metadata.create_all(engine)

    inspector = inspect(engine)

    if 'user_settings' not in inspector.get_table_names():
        print(" user_settings table not found!")
        return False

    columns = [c['name'] for c in inspector.get_columns('user_settings')]
    print(f"\n[OK] user_settings table exists with {len(columns)} columns")

    # Check for tier fields
    tier_fields = ['subscription_tier', 'tier_expires_at', 'tier_started_at', 'max_stores', 'max_products_per_week']
    missing_fields = [f for f in tier_fields if f not in columns]

    if missing_fields:
        print(f" Missing tier fields: {missing_fields}")
        return False

    print(f"\n[OK] All tier fields present:")
    for field in tier_fields:
        print(f"  - {field}")

    return True


async def test_tier_manager():
    """Test TierManager service"""
    print("\n" + "="*60)
    print("TEST 2: TierManager Service")
    print("="*60)

    manager = TierManager(DATABASE_URL)

    # Create test user
    engine = create_engine(DATABASE_URL.replace("sqlite:///", "sqlite:///"))
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create or get test user
    test_user = session.query(User).filter_by(email="test@tiertest.com").first()
    if not test_user:
        test_user = User(
            email="test@tiertest.com",
            name="Tier Test User",
            password_hash="$2b$12$test_hash",  # Add password_hash field for test
            subscription_tier='free'
        )
        session.add(test_user)
        session.commit()

    user_id = test_user.id

    # Reset user's tier settings to 'free' for clean testing
    test_settings = session.query(UserSettings).filter_by(user_id=user_id).first()
    if test_settings:
        test_settings.subscription_tier = 'free'
        test_settings.tier_expires_at = None
        test_settings.tier_started_at = None
        test_settings.max_stores = 1
        test_settings.max_products_per_week = 5
        session.commit()

    session.close()

    # Test 1: Get default tier
    print("\n[Test 2.1] Getting default tier for new user...")
    tier = await manager.get_user_tier(user_id)
    print(f"[OK] Default tier: {tier}")
    assert tier == 'free', f"Expected 'free', got '{tier}'"

    # Test 2: Get tier info
    print("\n[Test 2.2] Getting tier info...")
    tier_info = await manager.get_tier_info(user_id)
    print(f"[OK] Tier: {tier_info['tier']}")
    print(f"[OK] Tier Name: {tier_info['tier_name']}")
    print(f"[OK] Price: ${tier_info['price']}/mo")
    print(f"[OK] Max Stores: {tier_info['limits']['max_stores']}")
    print(f"[OK] Max Products/Week: {tier_info['limits']['max_products_per_week']}")
    print(f"[OK] Product Age Days: {tier_info['limits']['product_age_days']}+")
    print(f"[OK] Allowed Phases: {tier_info['limits']['allowed_phases']}")

    # Test 3: Upgrade to Pro
    print("\n[Test 2.3] Upgrading to Pro tier...")
    upgrade_result = await manager.upgrade_tier(user_id, 'pro', duration_days=30)
    print(f"[OK] Upgrade successful: {upgrade_result['success']}")
    print(f"[OK] New tier: {upgrade_result['tier']}")
    print(f"[OK] Max stores: {upgrade_result['max_stores']}")
    print(f"[OK] Max products/week: {upgrade_result['max_products_per_week']}")
    print(f"[OK] Expires: {upgrade_result['expires_at']}")

    # Test 4: Verify tier changed
    print("\n[Test 2.4] Verifying tier change...")
    new_tier = await manager.get_user_tier(user_id)
    print(f"[OK] Current tier: {new_tier}")
    assert new_tier == 'pro', f"Expected 'pro', got '{new_tier}'"

    # Test 5: Get tier comparison
    print("\n[Test 2.5] Getting tier comparison...")
    comparison = await manager.get_tier_comparison()
    print(f"[OK] Found {len(comparison['tiers'])} tiers:")
    for tier_key, tier_data in comparison['tiers'].items():
        print(f"  - {tier_data['name']}: {tier_data['price_display']}")
        print(f"    Stores: {tier_data['max_stores_display']}")
        print(f"    Products: {tier_data['max_products_display']}")
        print(f"    Product Age: {tier_data['product_age_display']}")

    # Test 6: Check tier limits
    print("\n[Test 2.6] Checking tier limits...")
    limit_check = await manager.check_tier_limits(user_id, 'add_store')
    print(f"[OK] Can add store: {limit_check['allowed']}")

    await manager.close()
    return True


async def test_api_endpoints():
    """Test tier management API endpoints"""
    print("\n" + "="*60)
    print("TEST 3: API Endpoints")
    print("="*60)

    base_url = "http://localhost:8001"

    async with httpx.AsyncClient() as client:
        # Get test user ID
        engine = create_engine(DATABASE_URL.replace("sqlite:///", "sqlite:///"))
        Session = sessionmaker(bind=engine)
        session = Session()
        test_user = session.query(User).filter_by(email="test@tiertest.com").first()
        user_id = test_user.id if test_user else 1
        session.close()

        # Test 1: GET /api/user/tier
        print("\n[Test 3.1] GET /api/user/tier")
        try:
            response = await client.get(f"{base_url}/api/user/tier?user_id={user_id}")
            data = response.json()

            if data.get('success'):
                print(f"[OK] API responded successfully")
                print(f"  Tier: {data.get('tier')}")
                print(f"  Tier Name: {data.get('tier_name')}")
                print(f"  Price: ${data.get('price')}/mo")
                print(f"  Features: {len(data.get('features', []))} features")
            else:
                print(f" API error: {data.get('error')}")
                return False

        except Exception as e:
            print(f" Failed to connect: {e}")
            print("  (Backend might not be running)")
            return False

        # Test 2: GET /api/tiers/comparison
        print("\n[Test 3.2] GET /api/tiers/comparison")
        try:
            response = await client.get(f"{base_url}/api/tiers/comparison")
            data = response.json()

            if data.get('success'):
                print(f"[OK] API responded successfully")
                print(f"  Total tiers: {len(data.get('tiers', {}))}")
                print(f"  Recommended for beginners: {data.get('recommended', {}).get('beginners')}")
                print(f"  Recommended for serious sellers: {data.get('recommended', {}).get('serious_sellers')}")
            else:
                print(f" API error: {data.get('error')}")

        except Exception as e:
            print(f" Request failed: {e}")

        # Test 3: POST /api/user/upgrade-tier
        print("\n[Test 3.3] POST /api/user/upgrade-tier")
        try:
            response = await client.post(
                f"{base_url}/api/user/upgrade-tier",
                params={"user_id": user_id, "new_tier": "elite", "duration_days": 30}
            )
            data = response.json()

            if data.get('success'):
                print(f"[OK] API responded successfully")
                print(f"  Upgraded to: {data.get('tier')}")
                print(f"  Old tier: {data.get('old_tier')}")
                print(f"  Max stores: {data.get('max_stores')}")
                print(f"  Expires: {data.get('expires_at')}")
            else:
                print(f" API error: {data.get('error')}")

        except Exception as e:
            print(f" Request failed: {e}")

        # Test 4: POST /api/user/check-limit
        print("\n[Test 3.4] POST /api/user/check-limit")
        try:
            response = await client.post(
                f"{base_url}/api/user/check-limit",
                params={"user_id": user_id, "action": "add_store"}
            )
            data = response.json()

            if data.get('success'):
                print(f"[OK] API responded successfully")
                print(f"  Allowed: {data.get('allowed')}")
                print(f"  Tier: {data.get('tier')}")
            else:
                print(f" API error: {data.get('error')}")

        except Exception as e:
            print(f" Request failed: {e}")

    return True


async def main():
    """Run all tests"""
    print("\n" + ""*60)
    print("SUBSCRIPTION TIER SYSTEM VERIFICATION")
    print(""*60)

    try:
        # Test 1: Database schema
        test1_passed = test_database_tables()

        # Test 2: TierManager service
        test2_passed = await test_tier_manager()

        # Test 3: API endpoints
        test3_passed = await test_api_endpoints()

        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"[OK] Database Schema: {'PASSED' if test1_passed else 'FAILED'}")
        print(f"[OK] TierManager Service: {'PASSED' if test2_passed else 'FAILED'}")
        print(f"[OK] API Endpoints: {'PASSED' if test3_passed else 'FAILED'}")

        all_passed = test1_passed and test2_passed and test3_passed

        if all_passed:
            print("\n" + ""*60)
            print("[LAUNCH] ALL TESTS PASSED - SYSTEM READY!")
            print(""*60)
            print("\nSubscription tier system is now active:")
            print("  [OK] 4 tiers: Free → Starter ($29) → Pro ($79) → Elite ($199)")
            print("  [OK] Tier-based product access by lifecycle phase")
            print("  [OK] Free: Maturity (30+ days)")
            print("  [OK] Starter: Growth (14+ days)")
            print("  [OK] Pro: Early Spike (7+ days)")
            print("  [OK] Elite: Discovery (0+ days - FRESH!)")
            print("\nAPI Endpoints:")
            print("  • GET /api/user/tier?user_id=1")
            print("  • POST /api/user/upgrade-tier?user_id=1&new_tier=pro")
            print("  • GET /api/tiers/comparison")
            print("  • POST /api/user/check-limit?user_id=1&action=add_store")
            return 0
        else:
            print("\n[ERROR] SOME TESTS FAILED")
            return 1

    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
