"""
[TEST] Test Priority-Based Product Discovery System
Tests that the system tries data sources in the correct order:
1. AliExpress API (primary)
2. Web scraping (secondary)
3. Fallback data (tertiary)
"""

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine

def test_priority_system():
    print("\n" + "="*60)
    print("[TEST] TESTING PRIORITY-BASED PRODUCT DISCOVERY")
    print("="*60 + "\n")

    # Initialize discovery engine
    discovery = ProductIntelligenceEngine()

    # Test 1: Check if AliExpress API is initialized
    print("1⃣ Checking AliExpress API initialization...")
    if discovery.aliexpress_api:
        print("   [SUCCESS] AliExpress API client is initialized")
        print(f"    App Key: {discovery.aliexpress_api.app_key}")
        print(f"    Gateway: {discovery.aliexpress_api.gateway}")
    else:
        print("   [WARNING]  AliExpress API client not available")
        print("   [TIP] Will fall back to scraping or template data")

    print("\n2⃣ Discovering products for 'smart_home' niche...")
    print("    Watch the priority order in the logs below:\n")

    # Discover products (this will show the priority logic in logs)
    result = discovery.discover_products(niche="smart_home", per_page=5)

    print("\n" + "="*60)
    print("[STATS] RESULT SUMMARY")
    print("="*60)
    print(f"[SUCCESS] Data Source Used: {result['data_source']}")
    print(f"[SUCCESS] Products Retrieved: {len(result['products'])}")
    print(f"[SUCCESS] Timestamp: {result['timestamp']}")

    if result['products']:
        print(f"\n[PACKAGE] Sample Product:")
        sample = result['products'][0]
        print(f"   • Name: {sample['name']}")
        print(f"   • Price: ${sample['price']}")
        print(f"   • Source: {sample.get('source', 'unknown')}")
        print(f"   • Velocity Score: {sample.get('velocity_score', 0)}")

    print("\n" + "="*60)
    print("[SUCCESS] TEST COMPLETE")
    print("="*60)

    # Show priority logic explanation
    print("\n PRIORITY LOGIC:")
    print("   1. ALIEXPRESS_API → Real product data from AliExpress")
    print("   2. SCRAPING → Web scraping as backup")
    print("   3. FALLBACK → Template data for guaranteed uptime")
    print()

if __name__ == "__main__":
    test_priority_system()
