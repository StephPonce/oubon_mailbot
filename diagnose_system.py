#!/usr/bin/env python3
"""
OUBON SHOP - Complete System Diagnosis
Run this to find out exactly what's broken
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 70)
print("🔍 OUBON SHOP - COMPLETE SYSTEM DIAGNOSIS")
print("=" * 70)

# TEST 1: Environment Variables
print("\n1️⃣ CHECKING API KEYS...")
print("-" * 70)

keys = {
    'ANTHROPIC_API_KEY': 'Claude AI',
    'ALIEXPRESS_APP_KEY': 'AliExpress',
    'ALIEXPRESS_APP_SECRET': 'AliExpress Secret',
    'SHOPIFY_STORE': 'Shopify Store',
    'SHOPIFY_API_TOKEN': 'Shopify Token'
}

for key, name in keys.items():
    value = os.getenv(key)
    if value:
        masked = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else f"{value[:4]}..."
        print(f"  ✅ {name}: {masked}")
    else:
        print(f"  ❌ {name}: MISSING")

# TEST 2: Check which engine main.py is using
print("\n2️⃣ CHECKING MAIN.PY INTELLIGENCE IMPORT...")
print("-" * 70)

try:
    main_path = Path.cwd() / "ospra_os" / "main.py"
    with open(main_path, 'r') as f:
        content = f.read()

    if "from ospra_os.intelligence.product_intelligence_v2 import" in content:
        print("  ✅ Using V2 engine (CORRECT)")
    elif "from ospra_os.intelligence.product_intelligence import" in content:
        print("  ❌ Using OLD engine (WRONG - still using mock data)")
    else:
        print("  ⚠️  Cannot find intelligence import in main.py")

except Exception as e:
    print(f"  ❌ Error reading main.py: {e}")

# TEST 3: Test Intelligence Engine V2 Directly
print("\n3️⃣ TESTING INTELLIGENCE ENGINE V2...")
print("-" * 70)

async def test_engine():
    try:
        sys.path.insert(0, str(Path.cwd()))
        from ospra_os.intelligence.product_intelligence_v2 import ProductIntelligenceEngine

        print("  ✅ V2 Engine imported successfully")

        engine = ProductIntelligenceEngine()
        print("  ✅ Engine initialized")

        print("  🔍 Discovering products...")
        products = await engine.discover_winning_products(
            niches=['smart home'],
            max_per_niche=3
        )

        print(f"  ✅ Found {len(products)} products\n")

        # Check if products are unique
        names = [p.get('display_data', {}).get('name', 'Unknown') for p in products]
        scores = [p.get('score', 0) for p in products]
        prices = [p.get('display_data', {}).get('supplier_cost', 0) for p in products]

        unique_names = len(set(names))
        unique_scores = len(set(scores))
        unique_prices = len(set(prices))

        print("  📊 UNIQUENESS CHECK:")
        print(f"     Names: {unique_names}/{len(products)} unique")
        print(f"     Scores: {unique_scores}/{len(products)} unique")
        print(f"     Prices: {unique_prices}/{len(products)} unique")

        if unique_names < len(products):
            print("     ❌ PROBLEM: Duplicate product names!")
        if unique_scores < len(products):
            print("     ❌ PROBLEM: Duplicate scores!")
        if unique_prices < len(products):
            print("     ❌ PROBLEM: Duplicate prices!")

        print("\n  🎯 SAMPLE PRODUCTS:")
        for i, product in enumerate(products[:3], 1):
            display = product.get('display_data', {})
            print(f"\n     {i}. {display.get('name', 'Unknown')}")
            print(f"        Score: {product.get('score', 0):.1f}/10")
            print(f"        Cost: ${display.get('supplier_cost', 0):.2f}")
            print(f"        Orders: {display.get('supplier_orders', 0):,}")
            print(f"        URL: {display.get('supplier_url', 'N/A')[:60]}...")

        return True

    except Exception as e:
        print(f"  ❌ ENGINE TEST FAILED: {e}")
        import traceback
        print("\n  FULL ERROR:")
        print(traceback.format_exc())
        return False

# Run async test
try:
    result = asyncio.run(test_engine())
except Exception as e:
    print(f"  ❌ ASYNC ERROR: {e}")
    result = False

# TEST 4: Check AliExpress API
print("\n4️⃣ TESTING ALIEXPRESS API...")
print("-" * 70)

async def test_ali():
    try:
        sys.path.insert(0, str(Path.cwd()))
        from ospra_os.integrations.aliexpress_api import AliExpressAPI

        api = AliExpressAPI()
        products = await api.search_products('smart plug', limit=3)

        print(f"  ✅ Got {len(products)} products from AliExpress API")

        for i, p in enumerate(products[:2], 1):
            print(f"     {i}. {p['name'][:50]}...")
            print(f"        ${p['price']:.2f} | {p['orders']:,} orders")

        return True
    except Exception as e:
        print(f"  ❌ ALIEXPRESS TEST FAILED: {e}")
        return False

try:
    ali_result = asyncio.run(test_ali())
except Exception as e:
    print(f"  ❌ ERROR: {e}")
    ali_result = False

# FINAL VERDICT
print("\n" + "=" * 70)
print("📋 DIAGNOSIS COMPLETE")
print("=" * 70)

if result and ali_result:
    print("✅ ALL SYSTEMS WORKING - Ready to deploy")
else:
    print("❌ PROBLEMS FOUND - See errors above")
    print("\nMost likely issues:")
    print("  1. main.py still using OLD engine")
    print("  2. AliExpress API returning mock data")
    print("  3. Environment variables not loaded")

print("\n" + "=" * 70)
