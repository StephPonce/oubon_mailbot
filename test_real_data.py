#!/usr/bin/env python3
"""
OUBON SHOP - Real Data Verification Test
Tests that the intelligence engine returns real, unique data (not mock/duplicates)
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict

# Load environment variables
load_dotenv()

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("🧪 OUBON SHOP - REAL DATA VERIFICATION TEST")
print("=" * 70)


def verify_unique_scores(products: List[Dict]) -> bool:
    """Verify that products have unique or varied scores"""
    if not products:
        print("  ❌ No products to verify")
        return False

    scores = [p.get('score', 0) for p in products]
    unique_scores = len(set(scores))
    total_products = len(products)

    print(f"\n  📊 SCORE ANALYSIS:")
    print(f"     Total products: {total_products}")
    print(f"     Unique scores: {unique_scores}")
    print(f"     Uniqueness: {unique_scores / total_products * 100:.1f}%")

    # List all scores
    print(f"     All scores: {sorted(scores, reverse=True)}")

    # We expect at least 70% unique scores for real data
    if unique_scores / total_products >= 0.7:
        print("     ✅ PASS: Good score diversity")
        return True
    else:
        print("     ⚠️  WARNING: Low score diversity (may indicate mock data)")
        return False


def verify_unique_pricing(products: List[Dict]) -> bool:
    """Verify that products have unique pricing"""
    if not products:
        print("  ❌ No products to verify")
        return False

    prices = [p.get('display_data', {}).get('supplier_cost', 0) for p in products]
    unique_prices = len(set(prices))
    total_products = len(products)

    print(f"\n  💰 PRICING ANALYSIS:")
    print(f"     Total products: {total_products}")
    print(f"     Unique prices: {unique_prices}")
    print(f"     Uniqueness: {unique_prices / total_products * 100:.1f}%")

    # List sample prices
    print(f"     Sample prices: ${min(prices):.2f} - ${max(prices):.2f}")

    # We expect at least 80% unique prices for real data
    if unique_prices / total_products >= 0.8:
        print("     ✅ PASS: Good price diversity")
        return True
    else:
        print("     ❌ FAIL: Too many duplicate prices (mock data detected)")
        return False


def verify_exact_supplier_urls(products: List[Dict]) -> bool:
    """Verify that supplier URLs point to exact products (not generic searches)"""
    if not products:
        print("  ❌ No products to verify")
        return False

    print(f"\n  🔗 SUPPLIER URL ANALYSIS:")

    exact_urls = 0
    generic_urls = 0

    for i, product in enumerate(products[:5], 1):  # Check first 5
        url = product.get('display_data', {}).get('supplier_url', '')
        name = product.get('display_data', {}).get('name', 'Unknown')

        print(f"\n     {i}. {name[:50]}...")

        # Check if URL is exact (contains product ID) or generic (just search)
        if '/item/' in url or '/product/' in url or 'productId' in url:
            print(f"        ✅ Exact URL: {url[:60]}...")
            exact_urls += 1
        elif 'search' in url or 'query' in url or url == '#':
            print(f"        ❌ Generic URL: {url[:60]}...")
            generic_urls += 1
        else:
            print(f"        ⚠️  Unknown URL format: {url[:60]}...")

    total_checked = exact_urls + generic_urls
    if total_checked == 0:
        print("     ❌ FAIL: No valid URLs found")
        return False

    exact_percentage = (exact_urls / total_checked) * 100

    print(f"\n     Exact URLs: {exact_urls}/{total_checked} ({exact_percentage:.1f}%)")

    if exact_percentage >= 80:
        print("     ✅ PASS: Most URLs are exact product links")
        return True
    else:
        print("     ❌ FAIL: Too many generic search URLs (not real products)")
        return False


def verify_ai_explanations(products: List[Dict]) -> bool:
    """Verify that AI explanations are unique and meaningful"""
    if not products:
        print("  ❌ No products to verify")
        return False

    print(f"\n  🤖 AI EXPLANATION ANALYSIS:")

    explanations = [p.get('ai_explanation', '') for p in products]
    unique_explanations = len(set(explanations))
    total_products = len(products)

    print(f"     Total products: {total_products}")
    print(f"     Unique explanations: {unique_explanations}")

    # Check for generic/mock explanations
    generic_count = 0
    for exp in explanations:
        if not exp or len(exp) < 50 or "analysis not available" in exp.lower():
            generic_count += 1

    print(f"     Generic explanations: {generic_count}")

    # Show samples
    print(f"\n     Sample explanations:")
    for i, exp in enumerate(explanations[:3], 1):
        print(f"     {i}. {exp[:100]}...")

    # We expect at least 90% unique and meaningful explanations
    valid_explanations = unique_explanations - generic_count
    if valid_explanations / total_products >= 0.9:
        print("     ✅ PASS: AI explanations are unique and meaningful")
        return True
    else:
        print("     ❌ FAIL: Too many generic/duplicate AI explanations")
        return False


async def test_intelligence_engine():
    """Test the ProductIntelligenceEngine V2 for real data"""
    print("\n1️⃣ TESTING INTELLIGENCE ENGINE V2...")
    print("-" * 70)

    try:
        from ospra_os.intelligence.product_intelligence_v2 import ProductIntelligenceEngine

        print("  ✅ ProductIntelligenceEngine V2 imported")

        engine = ProductIntelligenceEngine()
        print("  ✅ Engine initialized")

        # Discover products
        print("\n  🔍 Discovering products (smart home niche)...")
        products = await engine.discover_winning_products(
            niches=['smart home'],
            max_per_niche=5
        )

        if not products:
            print("  ❌ CRITICAL: No products discovered!")
            return False

        print(f"  ✅ Discovered {len(products)} products")

        # Run verification tests
        print("\n" + "=" * 70)
        print("VERIFICATION TESTS")
        print("=" * 70)

        score_pass = verify_unique_scores(products)
        price_pass = verify_unique_pricing(products)
        url_pass = verify_exact_supplier_urls(products)
        ai_pass = verify_ai_explanations(products)

        # Summary
        print("\n" + "=" * 70)
        print("TEST RESULTS SUMMARY")
        print("=" * 70)

        results = {
            "Unique Scores": score_pass,
            "Unique Pricing": price_pass,
            "Exact Supplier URLs": url_pass,
            "AI Explanations": ai_pass
        }

        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status} - {test_name}")

        all_passed = all(results.values())

        print("\n" + "=" * 70)
        if all_passed:
            print("🎉 ALL TESTS PASSED - REAL DATA CONFIRMED!")
            print("The system is returning unique, real products from AliExpress")
        else:
            print("⚠️  SOME TESTS FAILED - CHECK ISSUES ABOVE")
            print("The system may still be using mock data or has configuration issues")
        print("=" * 70)

        return all_passed

    except Exception as e:
        print(f"\n  ❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        print("\n  FULL ERROR:")
        traceback.print_exc()
        return False


async def test_api_endpoint():
    """Test the /api/intelligence/discover endpoint"""
    print("\n\n2️⃣ TESTING API ENDPOINT...")
    print("-" * 70)

    try:
        import httpx

        # Test local server (assumes running on localhost:8000)
        base_url = os.getenv('TEST_API_URL', 'http://localhost:8000')

        print(f"  🌐 Testing API at: {base_url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/api/intelligence/discover",
                json={
                    "niches": ["smart home"],
                    "max_per_niche": 3
                }
            )

            if response.status_code == 200:
                data = response.json()

                if data.get('success'):
                    products = data.get('products', [])
                    print(f"  ✅ API returned {len(products)} products")

                    # Quick verification
                    if products:
                        score_check = len(set(p['score'] for p in products)) / len(products)
                        print(f"  📊 Score uniqueness: {score_check * 100:.1f}%")

                        if score_check >= 0.7:
                            print("  ✅ API endpoint working correctly")
                            return True
                        else:
                            print("  ⚠️  API may be returning duplicate data")
                            return False
                    else:
                        print("  ❌ API returned no products")
                        return False
                else:
                    print(f"  ❌ API returned error: {data.get('message')}")
                    return False
            else:
                print(f"  ❌ API request failed: HTTP {response.status_code}")
                return False

    except Exception as e:
        print(f"  ⚠️  API test skipped (server may not be running): {e}")
        print("  💡 Start server with: python main.py")
        return None  # None = test skipped, not failed


async def test_environment():
    """Test environment configuration"""
    print("\n\n3️⃣ TESTING ENVIRONMENT...")
    print("-" * 70)

    required_vars = {
        'ANTHROPIC_API_KEY': 'Claude AI',
        'ALIEXPRESS_APP_KEY': 'AliExpress API',
        'ALIEXPRESS_APP_SECRET': 'AliExpress Secret',
    }

    all_configured = True

    for var, name in required_vars.items():
        value = os.getenv(var)
        if value:
            masked = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else f"{value[:4]}..."
            print(f"  ✅ {name}: {masked}")
        else:
            print(f"  ❌ {name}: NOT CONFIGURED")
            all_configured = False

    return all_configured


async def main():
    """Run all verification tests"""
    print("\n🚀 STARTING COMPREHENSIVE VERIFICATION")
    print("=" * 70)

    # Test 1: Environment
    env_ok = await test_environment()

    # Test 2: Intelligence Engine
    engine_ok = await test_intelligence_engine()

    # Test 3: API Endpoint (optional)
    api_ok = await test_api_endpoint()

    # Final Summary
    print("\n\n" + "=" * 70)
    print("🎯 FINAL VERIFICATION SUMMARY")
    print("=" * 70)

    print(f"  Environment: {'✅ PASS' if env_ok else '❌ FAIL'}")
    print(f"  Intelligence Engine: {'✅ PASS' if engine_ok else '❌ FAIL'}")

    if api_ok is None:
        print(f"  API Endpoint: ⏭️  SKIPPED (server not running)")
    else:
        print(f"  API Endpoint: {'✅ PASS' if api_ok else '❌ FAIL'}")

    if env_ok and engine_ok:
        print("\n✅ VERIFICATION SUCCESSFUL!")
        print("   The system is working correctly with real data")
        print("\n📋 Next Steps:")
        print("   1. Visit http://localhost:8000/premium/v2")
        print("   2. Click 'Discover Winning Products'")
        print("   3. Verify unique products appear in the dashboard")
        return True
    else:
        print("\n❌ VERIFICATION FAILED")
        print("   Fix the issues above before deploying")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
