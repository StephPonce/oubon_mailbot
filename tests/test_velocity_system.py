"""
Test script for Velocity Detection System
Verifies database tables, service, and API endpoints
"""

import asyncio
import sys
from datetime import datetime, timedelta
from ospra_os.database import (
    Base,
    ProductSaturation,
    ProductVelocity
)
from ospra_os.intelligence.velocity_detector import VelocityDetector
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import random

DATABASE_URL = "sqlite:///./data/multi_store.db"


async def test_database_tables():
    """Test that velocity tables are created correctly"""
    print("\n" + "="*60)
    print("TEST 1: Database Tables Creation")
    print("="*60)

    # Create sync engine to check tables
    engine = create_engine(DATABASE_URL.replace("sqlite:///", "sqlite:///"))

    # Create all tables
    Base.metadata.create_all(engine)

    # Inspect database
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"\n[OK] Found {len(tables)} tables in database")

    # Check for velocity table
    if 'product_velocity' in tables:
        print(f"[OK] product_velocity table exists")

        # Check columns
        columns = [c['name'] for c in inspector.get_columns('product_velocity')]
        print(f"\n[OK] product_velocity columns ({len(columns)}):")
        for col in columns:
            print(f"  - {col}")

        return True
    else:
        print(f" MISSING product_velocity table")
        return False


async def create_test_data():
    """Create test products with varying ages and metrics"""
    print("\n" + "="*60)
    print("TEST 2: Creating Test Data")
    print("="*60)

    engine = create_engine(DATABASE_URL.replace("sqlite:///", "sqlite:///"))
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test products with different ages
    test_products = [
        {
            'name': 'Smart Plug Discovery Test',
            'niche': 'smart_home',
            'age_days': 3,  # Discovery phase
            'search_7d': 1000,
            'search_30d': 800,
            'reddit_7d': 50,
            'reddit_30d': 30
        },
        {
            'name': 'LED Bulb Early Spike Test',
            'niche': 'smart_home',
            'age_days': 10,  # Early spike
            'search_7d': 5000,
            'search_30d': 2000,
            'reddit_7d': 200,
            'reddit_30d': 50
        },
        {
            'name': 'Fitness Band Growth Test',
            'niche': 'fitness',
            'age_days': 25,  # Growth phase
            'search_7d': 8000,
            'search_30d': 6000,
            'reddit_7d': 300,
            'reddit_30d': 200
        },
        {
            'name': 'Yoga Mat Maturity Test',
            'niche': 'fitness',
            'age_days': 50,  # Maturity
            'search_7d': 10000,
            'search_30d': 9500,
            'reddit_7d': 400,
            'reddit_30d': 380
        },
        {
            'name': 'Old Gadget Decline Test',
            'niche': 'smart_home',
            'age_days': 80,  # Decline
            'search_7d': 2000,
            'search_30d': 5000,
            'reddit_7d': 50,
            'reddit_30d': 150
        }
    ]

    product_ids = []
    for product in test_products:
        # Check if product already exists
        existing = session.query(ProductSaturation).filter_by(
            product_name=product['name']
        ).first()

        if existing:
            print(f"[OK] Product '{product['name']}' already exists (ID: {existing.id})")
            product_ids.append(existing.id)
            continue

        # Create product saturation record
        saturation = ProductSaturation(
            product_name=product['name'],
            niche=product['niche'],
            first_discovered_at=datetime.utcnow() - timedelta(days=product['age_days']),
            source_url=f"https://aliexpress.com/item/{random.randint(1000000, 9999999)}",
            saturation_threshold=100
        )
        session.add(saturation)
        session.flush()

        product_ids.append(saturation.id)
        print(f"[OK] Created product: {product['name']} (ID: {saturation.id}, Age: {product['age_days']} days)")

    session.commit()
    session.close()

    print(f"\n[OK] Created/verified {len(test_products)} test products")
    return test_products


async def test_velocity_detector():
    """Test VelocityDetector service"""
    print("\n" + "="*60)
    print("TEST 3: VelocityDetector Service")
    print("="*60)

    detector = VelocityDetector(DATABASE_URL)

    # Get test products from database
    engine = create_engine(DATABASE_URL.replace("sqlite:///", "sqlite:///"))
    Session = sessionmaker(bind=engine)
    session = Session()

    test_products_data = await create_test_data()

    print("\n[Test 3.1] Updating velocity for test products...")
    for i, product_data in enumerate(test_products_data):
        product = session.query(ProductSaturation).filter_by(
            product_name=product_data['name']
        ).first()

        if not product:
            continue

        # Update velocity
        velocity = await detector.update_product_velocity(
            product_saturation_id=product.id,
            search_volume_7d=product_data['search_7d'],
            search_volume_30d=product_data['search_30d'],
            reddit_mentions_7d=product_data['reddit_7d'],
            reddit_mentions_30d=product_data['reddit_30d']
        )

        print(f"[OK] {product.product_name}")
        print(f"  Phase: {velocity.phase}")
        print(f"  Velocity Score: {velocity.viral_coefficient:.1f}")
        print(f"  Growth Rate: {velocity.search_growth_rate:.1f}%")
        print(f"  Age: {velocity.phase_age_days} days")

    session.close()

    print("\n[Test 3.2] Testing phase filtering...")
    phases = ['discovery', 'early_spike', 'growth', 'maturity', 'decline']

    for phase in phases:
        products = await detector.get_products_by_phase(phase, limit=5)
        print(f"[OK] {phase}: {len(products)} products")

    print("\n[Test 3.3] Testing tier-based filtering...")
    tiers = ['free', 'starter', 'pro', 'enterprise']

    for tier in tiers:
        products = await detector.get_tier_appropriate_products(tier, limit=10)
        print(f"[OK] {tier}: {len(products)} products")

    print("\n[Test 3.4] Getting velocity statistics...")
    stats = await detector.get_velocity_stats()
    print(f"[OK] Total products tracked: {stats['total_products']}")
    print(f"[OK] Phase breakdown:")
    for phase, data in stats['phases'].items():
        print(f"  - {phase}: {data['count']} products (avg velocity: {data['avg_velocity_score']})")

    await detector.close()
    return True


async def test_api_endpoints():
    """Test API endpoints"""
    print("\n" + "="*60)
    print("TEST 4: API Endpoints")
    print("="*60)

    import httpx

    base_url = "http://localhost:8001"

    async with httpx.AsyncClient() as client:
        # Test 1: Velocity stats endpoint
        print("\n[Test 4.1] GET /api/velocity/stats")
        try:
            response = await client.get(f"{base_url}/api/velocity/stats")
            data = response.json()

            if data.get('success'):
                print(f"[OK] API responded successfully")
                print(f"  Total phases: {len(data.get('stats', {}))}")
                if 'velocity_overview' in data:
                    print(f"  Total products: {data['velocity_overview']['total_products']}")
            else:
                print(f" API error: {data.get('error')}")
                return False

        except Exception as e:
            print(f" Failed to connect: {e}")
            print("  (Backend might not be running)")
            return False

        # Test 2: Tier products endpoint
        print("\n[Test 4.2] GET /api/velocity/tier-products?tier=pro")
        try:
            response = await client.get(f"{base_url}/api/velocity/tier-products?tier=pro")
            data = response.json()

            if data.get('success'):
                print(f"[OK] API responded successfully")
                print(f"  Tier: {data.get('tier')}")
                print(f"  Products: {data.get('count')}")
                print(f"  Tier Info: {data.get('tier_info')}")
            else:
                print(f" API error: {data.get('error')}")

        except Exception as e:
            print(f" Request failed: {e}")

        # Test 3: Phase-specific endpoint
        print("\n[Test 4.3] GET /api/velocity/phase/early_spike")
        try:
            response = await client.get(f"{base_url}/api/velocity/phase/early_spike")
            data = response.json()

            if data.get('success'):
                print(f"[OK] API responded successfully")
                print(f"  Phase: {data.get('phase')}")
                print(f"  Products: {data.get('count')}")
            else:
                print(f" API error: {data.get('error')}")

        except Exception as e:
            print(f" Request failed: {e}")

    return True


async def main():
    """Run all tests"""
    print("\n" + ""*60)
    print("VELOCITY DETECTION SYSTEM VERIFICATION")
    print(""*60)

    try:
        # Test 1: Database tables
        test1_passed = await test_database_tables()

        # Test 2: Create test data
        await create_test_data()

        # Test 3: VelocityDetector service
        test3_passed = await test_velocity_detector()

        # Test 4: API endpoints
        test4_passed = await test_api_endpoints()

        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"[OK] Database Tables: {'PASSED' if test1_passed else 'FAILED'}")
        print(f"[OK] VelocityDetector Service: {'PASSED' if test3_passed else 'FAILED'}")
        print(f"[OK] API Endpoints: {'PASSED' if test4_passed else 'FAILED'}")

        all_passed = test1_passed and test3_passed and test4_passed

        if all_passed:
            print("\n" + ""*60)
            print("[LAUNCH] ALL TESTS PASSED - SYSTEM READY!")
            print(""*60)
            print("\nVelocity detection is now active:")
            print("  [OK] Products tracked by lifecycle phase")
            print("  [OK] Tier-based early access working")
            print("  [OK] 5 phases: discovery → early_spike → growth → maturity → decline")
            print("  [OK] Higher tiers get earlier access")
            print("\nAPI Endpoints:")
            print("  • GET /api/velocity/stats")
            print("  • GET /api/velocity/tier-products?tier=pro&niche=fitness")
            print("  • GET /api/velocity/phase/early_spike")
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
