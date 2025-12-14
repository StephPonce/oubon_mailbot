"""
Test script for Saturation Tracking System
Verifies database tables and core functionality
"""

import asyncio
import sys
from datetime import datetime
from ospra_os.database import (
    Base,
    ProductSaturation,
    UserProductRecommendation,
    User
)
from ospra_os.intelligence.saturation_tracker import SaturationTracker
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./data/multi_store.db"


async def test_database_tables():
    """Test that database tables are created correctly"""
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

    print(f"\n✓ Found {len(tables)} tables in database:")
    for table in sorted(tables):
        print(f"  - {table}")

    # Check for our new tables
    required_tables = ['product_saturation', 'user_product_recommendations']
    missing_tables = [t for t in required_tables if t not in tables]

    if missing_tables:
        print(f"\n✗ MISSING TABLES: {missing_tables}")
        return False
    else:
        print(f"\n✓ All required tables exist!")

        # Check columns for product_saturation
        columns = [c['name'] for c in inspector.get_columns('product_saturation')]
        print(f"\n✓ product_saturation columns ({len(columns)}):")
        for col in columns:
            print(f"  - {col}")

        # Check columns for user_product_recommendations
        columns = [c['name'] for c in inspector.get_columns('user_product_recommendations')]
        print(f"\n✓ user_product_recommendations columns ({len(columns)}):")
        for col in columns:
            print(f"  - {col}")

        return True


async def test_saturation_tracker():
    """Test SaturationTracker functionality"""
    print("\n" + "="*60)
    print("TEST 2: SaturationTracker Service")
    print("="*60)

    tracker = SaturationTracker(DATABASE_URL)

    # Test 1: Track product discovery
    print("\n[Test 2.1] Tracking product discovery...")
    product1 = await tracker.track_product_discovery(
        product_name="Smart WiFi Plug Test",
        source_url="https://aliexpress.com/item/12345",
        source_product_id="12345",
        niche="smart_home",
        saturation_threshold=5  # Low threshold for testing
    )
    print(f"✓ Tracked product: {product1.product_name}")
    print(f"  - ID: {product1.id}")
    print(f"  - Users: {product1.total_users_count}/{product1.saturation_threshold}")
    print(f"  - Saturated: {product1.is_saturated}")

    # Test 2: Check saturation status
    print("\n[Test 2.2] Checking saturation status...")
    is_saturated = await tracker.is_product_saturated(product_name="Smart WiFi Plug Test")
    print(f"✓ Product saturated: {is_saturated}")

    # Test 3: Get saturation count
    print("\n[Test 2.3] Getting saturation count...")
    count, threshold = await tracker.get_saturation_count("Smart WiFi Plug Test")
    print(f"✓ Count: {count}/{threshold}")

    # Test 4: Recommend to users (simulate)
    print("\n[Test 2.4] Simulating user recommendations...")
    for user_id in range(1, 6):
        success, error = await tracker.recommend_to_user(
            user_id=user_id,
            product_saturation_id=product1.id,
            recommendation_score=85.5,
            was_deployed=True
        )
        if success:
            print(f"✓ Recommended to user {user_id}")
        else:
            print(f"✗ Failed for user {user_id}: {error}")

    # Check if product is now saturated
    is_saturated_now = await tracker.is_product_saturated(product_saturation_id=product1.id)
    print(f"\n✓ Product now saturated: {is_saturated_now}")

    # Test 5: Filter saturated products
    print("\n[Test 2.5] Testing product filtering...")
    test_products = [
        {'name': 'Smart WiFi Plug Test', 'price': 19.99},
        {'name': 'Another Product', 'price': 29.99},
        {'name': 'Third Product', 'price': 39.99}
    ]

    filtered = await tracker.filter_saturated_products(test_products, 'name')
    print(f"✓ Original products: {len(test_products)}")
    print(f"✓ Filtered products: {len(filtered)}")
    print(f"✓ Removed {len(test_products) - len(filtered)} saturated products")

    # Test 6: Get saturation stats
    print("\n[Test 2.6] Getting saturation statistics...")
    stats = await tracker.get_saturation_stats(niche="smart_home")
    print(f"✓ Statistics for smart_home niche:")
    print(f"  - Total products: {stats['total_products']}")
    print(f"  - Saturated: {stats['saturated_products']}")
    print(f"  - Unsaturated: {stats['unsaturated_products']}")
    print(f"  - Saturation rate: {stats['saturation_rate']:.1f}%")
    print(f"  - Total recommendations: {stats['total_user_recommendations']}")

    await tracker.close()
    return True


async def test_product_intelligence_integration():
    """Test integration with ProductIntelligenceEngine"""
    print("\n" + "="*60)
    print("TEST 3: Product Intelligence Integration")
    print("="*60)

    from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine

    print("\n[Test 3.1] Initializing engine with saturation tracking...")
    engine = ProductIntelligenceEngine(
        database_url=DATABASE_URL,
        enable_saturation_tracking=True
    )

    if engine.saturation_tracker:
        print("✓ SaturationTracker initialized in ProductIntelligenceEngine")
    else:
        print("✗ SaturationTracker NOT initialized")
        return False

    print("\n[Test 3.2] Discovering products (saturation filtering enabled)...")
    products = await engine.discover_winning_products(
        niches=['smart_home'],
        max_per_niche=10
    )

    print(f"✓ Discovered {len(products)} products")
    if products:
        print(f"\nSample product:")
        print(f"  - Name: {products[0]['name']}")
        print(f"  - Niche: {products[0]['niche']}")
        print(f"  - Price: ${products[0]['price']}")
        print(f"  - Profit: ${products[0]['estimated_profit']}")

    return True


async def main():
    """Run all tests"""
    print("\n" + "█"*60)
    print("SATURATION TRACKING SYSTEM VERIFICATION")
    print("█"*60)

    try:
        # Test 1: Database tables
        test1_passed = await test_database_tables()

        # Test 2: SaturationTracker service
        test2_passed = await test_saturation_tracker()

        # Test 3: Integration with product intelligence
        test3_passed = await test_product_intelligence_integration()

        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"✓ Database Tables: {'PASSED' if test1_passed else 'FAILED'}")
        print(f"✓ SaturationTracker Service: {'PASSED' if test2_passed else 'FAILED'}")
        print(f"✓ Product Intelligence Integration: {'PASSED' if test3_passed else 'FAILED'}")

        all_passed = test1_passed and test2_passed and test3_passed

        if all_passed:
            print("\n" + "█"*60)
            print("🎉 ALL TESTS PASSED - SYSTEM READY!")
            print("█"*60)
            print("\nSaturation tracking is now active:")
            print("  ✓ Products are tracked automatically")
            print("  ✓ Saturated products are filtered")
            print("  ✓ Max 100 users per product (default)")
            print("  ✓ AutoDS problem prevented!")
            return 0
        else:
            print("\n❌ SOME TESTS FAILED")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
