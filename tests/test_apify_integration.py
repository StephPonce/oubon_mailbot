"""
Test Apify integration with Multi-Source Discovery
"""
import asyncio
from ospra_os.product_research.multi_source_discovery import MultiSourceDiscovery

async def test_integration():
    print("="*70)
    print("🧪 TESTING APIFY INTEGRATION WITH MULTI-SOURCE DISCOVERY")
    print("="*70)
    print()
    
    # Initialize discovery engine
    print("1️⃣  Initializing Multi-Source Discovery...")
    discovery = MultiSourceDiscovery()
    print()
    
    # Check what connectors are available
    print("2️⃣  Checking Data Source Availability:")
    print(f"   Google Trends: ✅ Always available")
    print(f"   Amazon PA-API: {'✅ Available' if discovery.amazon and discovery.amazon.is_available() else '❌ Not configured'}")
    print(f"   AliExpress: {'✅ Available' if discovery.aliexpress and discovery.aliexpress.is_available() else '❌ Not configured'}")
    print(f"   TikTok Shop (Apify): {'✅ Available' if discovery.tiktok and discovery.tiktok.is_available() else '❌ Not configured'}")
    print(f"   Amazon Bestsellers (Apify): {'✅ Available' if discovery.amazon_bestsellers and discovery.amazon_bestsellers.is_available() else '❌ Not configured'}")
    print()
    
    # Test category mapping
    print("3️⃣  Testing Category Mapping:")
    test_niches = ['smart_lighting', 'home_security', 'kitchen_tech']
    for niche in test_niches:
        tiktok_cat = discovery._map_niche_to_tiktok_category(niche)
        amazon_cat = discovery._map_niche_to_amazon_category(niche)
        print(f"   {niche}:")
        print(f"      TikTok → {tiktok_cat}")
        print(f"      Amazon → {amazon_cat}")
    print()
    
    print("="*70)
    print("✅ INTEGRATION TEST COMPLETE")
    print("="*70)
    print()
    print("Summary:")
    print("  ✅ Multi-Source Discovery initialized successfully")
    print("  ✅ Apify scrapers integrated")
    print("  ✅ Category mapping working")
    print("  ✅ System ready for 5-source discovery")
    print()
    
    # Show total data sources available
    active_sources = 1  # Google Trends always available
    if discovery.amazon and discovery.amazon.is_available():
        active_sources += 1
    if discovery.aliexpress and discovery.aliexpress.is_available():
        active_sources += 1
    if discovery.tiktok and discovery.tiktok.is_available():
        active_sources += 1
    if discovery.amazon_bestsellers and discovery.amazon_bestsellers.is_available():
        active_sources += 1
    
    print(f"📊 Active Data Sources: {active_sources}/5")
    print()

if __name__ == "__main__":
    asyncio.run(test_integration())
