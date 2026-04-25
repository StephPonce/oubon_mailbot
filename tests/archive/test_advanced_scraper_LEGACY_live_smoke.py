import asyncio
import sys
sys.path.insert(0, '/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot')

from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine

def test_discovery():
    """Direct test of discovery engine (bypasses API/database)"""

    print("=" * 80)
    print("[TEST] DIRECT DISCOVERY ENGINE TEST")
    print("=" * 80)
    print()
    print("This directly calls discover_products() - no API, no cache")
    print("Expected: 30-60 seconds (real scraping)")
    print()

    # Initialize discovery engine
    discovery = ProductIntelligenceEngine()

    # Call discovery directly (this WILL scrape)
    result = discovery.discover_products(niche="portable_charger", per_page=5)

    print()
    print("=" * 80)
    print("[STATS] RESULTS")
    print("=" * 80)
    print(f"Data Source: {result.get('data_source')}")
    print(f"Total Products: {result.get('total')}")
    print()

    if result.get('data_source') == 'ADVANCED_SCRAPING':
        print("[SUCCESS] [SUCCESS] [SUCCESS] ADVANCED SCRAPER WORKING! [SUCCESS] [SUCCESS] [SUCCESS]")
        print()
        print("First 3 products:")
        for i, product in enumerate(result.get('products', [])[:3], 1):
            print(f"\n{i}. {product.get('name', 'No name')[:60]}")
            print(f"   Velocity: {product.get('velocity_score', 'N/A')}/100")
            print(f"   Source: {product.get('source', 'unknown')}")
    elif result.get('data_source') == 'FALLBACK':
        print("[WARNING]  Scraping failed - system fell back to default data")
        print("This is OK - priority chain is working, scraping just failed")
    else:
        print(f"[ERROR] Unexpected data source: {result.get('data_source')}")

    print()
    print("=" * 80)

if __name__ == "__main__":
    test_discovery()
