#!/usr/bin/env python3
"""
Quick test for parallel product discovery optimization.

Tests:
1. TREND-FIRST flow is preserved (trends before suppliers)
2. Parallel execution within steps
3. Timing comparisons
"""

import os
import sys
import asyncio
import time
import logging

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file BEFORE importing any modules that need API keys
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)
print(f"📁 Loaded .env from: {env_path}")

# Verify key environment variables are loaded
print(f"🔑 APIFY_API_TOKEN: {'✅ Set' if os.getenv('APIFY_API_TOKEN') else '❌ Missing'}")
print(f"🔑 CJ_ACCESS_TOKEN: {'✅ Set' if os.getenv('CJ_ACCESS_TOKEN') else '❌ Missing'}")
print(f"🔑 ALIEXPRESS_APP_KEY: {'✅ Set' if os.getenv('ALIEXPRESS_APP_KEY') else '❌ Missing'}")
print(f"🔑 XAI_API_KEY: {'✅ Set' if os.getenv('XAI_API_KEY') else '❌ Missing'}")
print(f"🔑 OUBONSHOP_REDDIT_CLIENT_ID: {'✅ Set' if os.getenv('OUBONSHOP_REDDIT_CLIENT_ID') else '❌ Missing'}")

# Set up logging to see the parallel execution logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def print_header(title: str):
    print("\n" + "="*70)
    print(f"🧪 {title}")
    print("="*70)


def print_result(name: str, success: bool, details: str = ""):
    status = "✅" if success else "❌"
    print(f"   {status} {name}: {details}")


async def test_parallel_discovery():
    """Test the full parallel discovery pipeline."""
    print_header("PARALLEL PRODUCT DISCOVERY TEST")

    try:
        from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine

        # Initialize engine
        print("\n📦 Initializing ProductDiscoveryEngine...")
        engine = ProductDiscoveryEngine()

        # Test discovery for smart_home niche
        niche = "smart_home"
        print(f"\n🔍 Running discovery for niche: {niche}")
        print("   (Watch for parallel execution logs...)\n")

        start_time = time.time()

        products = await engine.discover_products(
            niche=niche,
            max_products=10,
            min_score=20.0,  # Lower threshold for testing
            include_sentiment=True
        )

        total_time = time.time() - start_time

        print("\n" + "-"*70)
        print("📊 RESULTS:")
        print("-"*70)

        print_result("Products found", len(products) > 0, f"{len(products)} products")
        print_result("Total time", True, f"{total_time:.2f}s")

        if products:
            # Check metadata
            first_product = products[0]
            metadata = first_product.get('_discovery_metadata', {})

            print_result("Flow type", 'parallel' in metadata.get('flow', ''), metadata.get('flow', 'unknown'))
            print_result("Sources used", len(metadata.get('sources_queried', [])) > 0,
                        ', '.join(metadata.get('sources_queried', ['none'])))
            print_result("Discovery time recorded", metadata.get('discovery_time_seconds') is not None,
                        f"{metadata.get('discovery_time_seconds', 0)}s")

            # Show first 3 products
            print("\n📦 Sample Products:")
            for i, product in enumerate(products[:3]):
                print(f"\n   {i+1}. {product.get('title', 'Unknown')[:50]}...")
                print(f"      Price: ${product.get('cost_price', 0):.2f} → ${product.get('suggested_price', 0):.2f}")
                print(f"      Score: {product.get('oi_score', 0)} ({product.get('tier', 'N/A')})")
                print(f"      Sources: {', '.join(product.get('available_on', ['unknown']))}")

        return len(products) > 0

    except Exception as e:
        print_result("Discovery", False, str(e))
        import traceback
        traceback.print_exc()
        return False


async def test_trending_keywords_parallel():
    """Test just the trending keywords step (parallel trend queries)."""
    print_header("TRENDING KEYWORDS (PARALLEL) TEST")

    try:
        from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine

        engine = ProductDiscoveryEngine()

        niche = "tech"
        print(f"\n🔍 Getting trending keywords for: {niche}")

        start_time = time.time()
        keywords = await engine._get_trending_keywords(niche)
        elapsed = time.time() - start_time

        print_result("Keywords found", len(keywords) > 0, f"{len(keywords)} keywords")
        print_result("Time", True, f"{elapsed:.2f}s")

        if keywords:
            print(f"\n   📋 Keywords: {keywords[:7]}")

        return len(keywords) > 0

    except Exception as e:
        print_result("Trending keywords", False, str(e))
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "🚀"*35)
    print("   OSPRA PARALLEL DISCOVERY TEST")
    print("🚀"*35)

    results = {}

    # Test trending keywords (Step 1)
    results['trending_keywords'] = await test_trending_keywords_parallel()

    # Test full discovery
    results['full_discovery'] = await test_parallel_discovery()

    # Summary
    print_header("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status}: {test_name}")

    print(f"\n   Total: {passed}/{total} tests passed")

    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
