"""Quick test of UnifiedProductDiscoveryV2"""
import asyncio
from ospra_os.intelligence.unified_product_discovery import get_discovery_engine

async def test_discovery():
    print("🧪 Testing UnifiedProductDiscoveryV2 with smart_home niche...")
    print()
    engine = get_discovery_engine()
    products = await engine.discover_products(
        niche="smart_home",
        max_products=10,
        min_score=40.0
    )
    print()
    print(f"✅ Discovery test complete!")
    print(f"   Products found: {len(products)}")
    print()
    if products:
        print("Sample products:")
        for i, p in enumerate(products[:5], 1):
            title = p.get("title", "Unknown")
            price = p.get("price", 0)
            score = p.get("final_score", 0)
            source = p.get("source", "unknown")
            print(f"  {i}. {title[:50]} - ${price:.2f} (score: {score:.0f}, source: {source})")
    return len(products)

if __name__ == "__main__":
    result = asyncio.run(test_discovery())
    print()
    if result > 0:
        print(f"✅ Test PASSED: {result} products discovered")
    else:
        print("⚠️  WARNING: No products found - check Apify credentials or use AliExpress fallback")
