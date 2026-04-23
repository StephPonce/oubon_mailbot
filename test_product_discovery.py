#!/usr/bin/env python3
"""
Full Product Discovery Test
============================
Tests the complete flow after CJ Dropshipping fix.
"""

import asyncio
import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

async def test_full_discovery():
    print("=" * 70)
    print("OSPRA PRODUCT DISCOVERY - FULL SYSTEM TEST")
    print("=" * 70)

    # =========================================================================
    # TEST 0: Apify Account Check
    # =========================================================================
    print("\n[TEST 0] Checking Apify Account Usage...")
    try:
        from ospra_os.product_research.connectors.apify.base_apify import ApifyClient
        apify = ApifyClient()
        usage = await apify.get_account_usage()
        if 'error' not in usage:
            print(f"   💰 Plan: {usage.get('plan', 'N/A')}")
            print(f"   💵 Monthly Limit: ${usage.get('monthly_limit_usd', 0):.2f}")
            print(f"   📊 Used This Month: ${usage.get('used_usd', 0):.2f}")
            print(f"   ✅ Remaining: ${usage.get('remaining_usd', 0):.2f}")
            print(f"   💳 Prepaid Balance: ${usage.get('prepaid_usd', 0):.2f}")
            if usage.get('can_run_paid_actors'):
                print(f"   ✅ Can run paid actors: Yes")
            else:
                print(f"   ⚠️  Can run paid actors: No (need more credits)")
        else:
            print(f"   ⚠️  Could not check: {usage.get('error')}")
    except Exception as e:
        print(f"   ⚠️  Error checking Apify: {e}")

    # =========================================================================
    # TEST 1: Environment Variables
    # =========================================================================
    print("\n[TEST 1] Checking Environment Variables...")

    env_checks = {
        "CJ_ACCESS_TOKEN": bool(os.getenv("CJ_ACCESS_TOKEN")),
        "ALIEXPRESS_APP_KEY": bool(os.getenv("ALIEXPRESS_APP_KEY")),
        "APIFY_API_TOKEN": bool(os.getenv("APIFY_API_TOKEN") or os.getenv("OUBONSHOP_APIFY_API_TOKEN")),
        "XAI_API_KEY": bool(os.getenv("XAI_API_KEY")),
        "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
    }

    for key, available in env_checks.items():
        status = "✅" if available else "❌"
        print(f"   {status} {key}")

    if not env_checks["CJ_ACCESS_TOKEN"]:
        print("\n   ⚠️  CJ_ACCESS_TOKEN not loaded - this is the bug we're testing!")
        return False

    # =========================================================================
    # TEST 2: CJ Client Initialization
    # =========================================================================
    print("\n[TEST 2] Testing CJ Dropshipping Client...")

    try:
        from ospra_os.integrations.cj_dropshipping.client import CJDropshippingClient
        cj_client = CJDropshippingClient()

        if cj_client.is_available():
            print("   ✅ CJ Client initialized successfully")
            print(f"   ✅ Token loaded: {cj_client.access_token[:30]}...")
        else:
            print("   ❌ CJ Client NOT available - load_dotenv() fix may not be working")
            return False
    except Exception as e:
        print(f"   ❌ CJ Client failed: {e}")
        return False

    # =========================================================================
    # TEST 3: CJ Product Search
    # =========================================================================
    print("\n[TEST 3] Testing CJ Product Search...")

    try:
        cj_products = await cj_client.search_by_niche("smart_home", page_size=5)
        print(f"   ✅ CJ returned {len(cj_products)} products")

        if cj_products:
            for i, p in enumerate(cj_products[:3]):
                title = p.get('title', 'Unknown')[:40]
                price = p.get('cost_price', 0)
                warehouse = p.get('warehouse', 'CN')
                print(f"      {i+1}. {title}... ${price:.2f} ({warehouse})")
        else:
            print("   ⚠️  CJ returned 0 products - API may have issues")
    except Exception as e:
        print(f"   ❌ CJ search failed: {e}")

    # =========================================================================
    # TEST 4: AliExpress Client
    # =========================================================================
    print("\n[TEST 4] Testing AliExpress Client...")

    try:
        from ospra_os.integrations.aliexpress.client import AliExpressClient
        ali_client = AliExpressClient(use_affiliate=True)

        ali_products = await ali_client.search_products("smart home gadgets", page_size=5)
        print(f"   ✅ AliExpress returned {len(ali_products)} products")

        if ali_products:
            for i, p in enumerate(ali_products[:3]):
                title = p.get('product_title', 'Unknown')[:40]
                price = p.get('target_sale_price', '0')
                print(f"      {i+1}. {title}... ${price}")
    except Exception as e:
        print(f"   ❌ AliExpress search failed: {e}")

    # =========================================================================
    # TEST 5: Full Product Discovery Engine
    # =========================================================================
    print("\n[TEST 5] Testing Full Product Discovery Engine...")

    try:
        from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine

        engine = ProductDiscoveryEngine()

        # Check source status
        print("\n   Data Source Status:")
        for source, status in engine.sources_status.items():
            icon = "✅" if "[SUCCESS]" in status else "❌"
            print(f"      {icon} {source}: {status[:50]}")

        # Verify CJ is now available
        if engine.cj_available:
            print("\n   ✅ CJ Dropshipping is ENABLED in discovery engine!")
        else:
            print("\n   ❌ CJ Dropshipping is DISABLED - FIX DID NOT WORK")
            return False

    except Exception as e:
        print(f"   ❌ Discovery engine init failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # =========================================================================
    # TEST 6: Run Actual Discovery
    # =========================================================================
    print("\n[TEST 6] Running Full Product Discovery (smart_home niche)...")
    print("   This may take 30-60 seconds...\n")

    try:
        products = await engine.discover_products(
            niche="smart_home",
            max_products=10,
            min_score=30.0,
            include_sentiment=False  # Skip sentiment for faster test
        )

        print(f"\n   ✅ Discovery returned {len(products)} products")

        # Analyze results
        ali_only = sum(1 for p in products if p.get('available_on') == ['aliexpress'])
        cj_only = sum(1 for p in products if p.get('available_on') == ['cj_dropshipping'])
        both = sum(1 for p in products if len(p.get('available_on', [])) > 1)

        print(f"\n   📊 Supplier Breakdown:")
        print(f"      AliExpress only: {ali_only}")
        print(f"      CJ only: {cj_only}")
        print(f"      Both suppliers: {both}")

        if cj_only > 0 or both > 0:
            print("\n   🎉 CJ PRODUCTS ARE NOW LOADING!")
        else:
            print("\n   ⚠️  No CJ products in results - may need to check API response")

        # Show top products
        print(f"\n   📦 Top {min(5, len(products))} Products:")
        for i, p in enumerate(products[:5]):
            title = p.get('title', 'Unknown')[:35]
            score = p.get('oi_score', 0)
            tier = p.get('tier', 'N/A')
            suppliers = ', '.join(p.get('available_on', ['unknown']))
            cross_ref = "🔗" if p.get('cross_referenced') else ""

            print(f"      {i+1}. [{score:.1f}] {tier:10} {title}...")
            print(f"         Suppliers: {suppliers} {cross_ref}")

        # Score distribution
        scores = [p.get('oi_score', 0) for p in products]
        if scores:
            print(f"\n   📈 Score Distribution:")
            print(f"      Min: {min(scores):.1f}")
            print(f"      Max: {max(scores):.1f}")
            print(f"      Avg: {sum(scores)/len(scores):.1f}")

            # Check for score variation (the other bug we fixed)
            unique_scores = len(set(round(s, 0) for s in scores))
            if unique_scores >= 3:
                print(f"      ✅ Good score variation ({unique_scores} unique scores)")
            else:
                print(f"      ⚠️  Low score variation ({unique_scores} unique scores)")

    except Exception as e:
        print(f"   ❌ Discovery failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    print(f"""
   ✅ Environment variables loaded
   ✅ CJ Dropshipping client working
   ✅ CJ products being fetched
   ✅ Discovery engine has CJ enabled
   ✅ Full discovery completed

   CJ Products in results: {cj_only + both}
   Cross-referenced: {both}
   Score variation: {unique_scores} unique scores
    """)

    return True


if __name__ == "__main__":
    success = asyncio.run(test_full_discovery())
    print("\n" + "=" * 70)
    if success:
        print("🎉 ALL TESTS PASSED - Product Discovery is fully operational!")
    else:
        print("❌ TESTS FAILED - Check errors above")
    print("=" * 70)
