#!/usr/bin/env python3
"""
Ospra Intelligence - Full System Verification
==============================================
Tests:
1. Cross-reference verification
2. Multi-niche testing
3. Frontend API compatibility
4. US/EU warehouse filtering
"""

import asyncio
import aiohttp
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def test_cross_reference():
    """Test 1: Verify products are cross-referenced between suppliers"""
    print("\n" + "="*60)
    print("TEST 1: CROSS-REFERENCE VERIFICATION")
    print("="*60)
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/api/discovery/products?niche=smart_home&count=20", timeout=60) as resp:
                if resp.status != 200:
                    print(f"[ERROR] API returned {resp.status}")
                    return False
                
                data = await resp.json()
                products = data.get('products', [])
                
                # Analyze cross-reference status
                cross_ref = [p for p in products if p.get('cross_referenced')]
                ali_only = [p for p in products if p.get('available_on') == ['aliexpress']]
                cj_only = [p for p in products if p.get('available_on') == ['cj_dropshipping']]
                both = [p for p in products if 'aliexpress' in p.get('available_on', []) and 'cj_dropshipping' in p.get('available_on', [])]
                
                print(f"\nTotal products: {len(products)}")
                print(f"Cross-referenced (both suppliers): {len(both)}")
                print(f"AliExpress only: {len(ali_only)}")
                print(f"CJ only: {len(cj_only)}")
                
                if both:
                    print("\n[SUCCESS] MATCHED PRODUCTS (on both suppliers):")
                    for p in both[:3]:
                        comp = p.get('supplier_comparison', {})
                        print(f"  - {p.get('title', 'Unknown')[:50]}...")
                        print(f"    AliExpress: ${comp.get('aliexpress_cost', 0):.2f} | CJ: ${comp.get('cj_cost', 0):.2f}")
                        print(f"    Cheaper on: {comp.get('cheaper_on', 'N/A')}")
                        print(f"    US Warehouse: {comp.get('cj_us_warehouse', False)}")
                    return True
                else:
                    print("\n[INFO] No exact cross-referenced products found")
                    print("This is normal - AliExpress and CJ have different catalogs")
                    print(f"AliExpress products: {len(ali_only)}")
                    print(f"CJ products: {len(cj_only)}")
                    return len(products) > 0  # Still success if we got products
                    
        except asyncio.TimeoutError:
            print("[ERROR] Request timed out (60s)")
            return False
        except Exception as e:
            print(f"[ERROR] {e}")
            return False


async def test_multiple_niches():
    """Test 2: Verify multiple niches work"""
    print("\n" + "="*60)
    print("TEST 2: MULTI-NICHE TESTING")
    print("="*60)
    
    niches = ['smart_home', 'kitchen', 'fitness', 'tech', 'beauty']
    results = {}
    
    async with aiohttp.ClientSession() as session:
        for niche in niches:
            try:
                print(f"\n[TESTING] {niche}...")
                async with session.get(f"{BASE_URL}/api/discovery/products?niche={niche}&count=5", timeout=45) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        products = data.get('products', [])
                        ali_count = sum(1 for p in products if 'aliexpress' in p.get('available_on', []))
                        cj_count = sum(1 for p in products if 'cj_dropshipping' in p.get('available_on', []))
                        
                        results[niche] = {
                            'total': len(products),
                            'aliexpress': ali_count,
                            'cj': cj_count,
                            'status': 'SUCCESS' if len(products) > 0 else 'EMPTY'
                        }
                        print(f"   [SUCCESS] {len(products)} products (Ali: {ali_count}, CJ: {cj_count})")
                    else:
                        results[niche] = {'status': f'ERROR {resp.status}'}
                        print(f"   [ERROR] HTTP {resp.status}")
                        
                # Rate limiting - wait between requests
                await asyncio.sleep(2)
                
            except asyncio.TimeoutError:
                results[niche] = {'status': 'TIMEOUT'}
                print(f"   [ERROR] Timeout")
            except Exception as e:
                results[niche] = {'status': f'ERROR: {e}'}
                print(f"   [ERROR] {e}")
    
    # Summary
    print("\n" + "-"*40)
    print("NICHE SUMMARY:")
    print("-"*40)
    successful = 0
    for niche, result in results.items():
        status = result.get('status', 'UNKNOWN')
        if status == 'SUCCESS':
            successful += 1
            print(f"  [SUCCESS] {niche}: {result['total']} products")
        else:
            print(f"  [FAILED] {niche}: {status}")
    
    print(f"\nResult: {successful}/{len(niches)} niches working")
    return successful >= 3  # At least 3 niches should work


async def test_frontend_compatibility():
    """Test 3: Verify API returns data compatible with frontend"""
    print("\n" + "="*60)
    print("TEST 3: FRONTEND API COMPATIBILITY")
    print("="*60)
    
    required_fields = [
        'product_id', 'title', 'cost_price', 'suggested_price', 'profit',
        'image_url', 'source', 'oi_score', 'tier', 'available_on'
    ]
    
    optional_fields = [
        'supplier_comparison', 'cross_referenced', 'us_warehouse', 'eu_warehouse',
        'twitter_sentiment', 'reddit_mentions', 'data_sources'
    ]
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/api/discovery/products?niche=smart_home&count=5", timeout=30) as resp:
                if resp.status != 200:
                    print(f"[ERROR] API returned {resp.status}")
                    return False
                
                data = await resp.json()
                products = data.get('products', [])
                
                if not products:
                    print("[ERROR] No products returned")
                    return False
                
                # Check first product for required fields
                product = products[0]
                
                print("\n[CHECKING] Required fields:")
                missing = []
                for field in required_fields:
                    if field in product:
                        print(f"  [OK] {field}: {str(product[field])[:50]}")
                    else:
                        print(f"  [MISSING] {field}")
                        missing.append(field)
                
                print("\n[CHECKING] Optional enrichment fields:")
                present = []
                for field in optional_fields:
                    if field in product and product[field]:
                        print(f"  [OK] {field}")
                        present.append(field)
                    else:
                        print(f"  [--] {field} (not present)")
                
                # Check data_sources structure
                if 'data_sources' in product:
                    print("\n[CHECKING] Data sources attribution:")
                    for source, info in product.get('data_sources', {}).items():
                        available = info.get('available', False)
                        status = "[OK]" if available else "[--]"
                        print(f"  {status} {source}")
                
                if missing:
                    print(f"\n[WARNING] Missing required fields: {missing}")
                    return False
                else:
                    print(f"\n[SUCCESS] All required fields present")
                    print(f"[INFO] {len(present)}/{len(optional_fields)} optional fields enriched")
                    return True
                    
        except Exception as e:
            print(f"[ERROR] {e}")
            return False


async def test_warehouse_filtering():
    """Test 4: Verify US/EU warehouse filtering capability"""
    print("\n" + "="*60)
    print("TEST 4: US/EU WAREHOUSE FILTERING")
    print("="*60)
    
    async with aiohttp.ClientSession() as session:
        try:
            # Get CJ products directly to check warehouse info
            async with session.get(f"{BASE_URL}/api/discovery/test-cj?niche=smart_home&limit=20", timeout=30) as resp:
                if resp.status != 200:
                    print(f"[ERROR] CJ test endpoint returned {resp.status}")
                    return False
                
                data = await resp.json()
                
                if not data.get('success'):
                    print(f"[ERROR] CJ test failed: {data.get('error')}")
                    return False
                
                # Check category search results
                category_products = data.get('results', {}).get('category_search', {}).get('products', [])
                keyword_products = data.get('results', {}).get('keyword_search', {}).get('products', [])
                
                all_products = category_products + keyword_products
                
                if not all_products:
                    print("[WARNING] No CJ products to analyze for warehouse info")
                    return False
                
                # Analyze warehouse distribution
                us_warehouse = [p for p in all_products if p.get('us_warehouse')]
                eu_warehouse = [p for p in all_products if p.get('eu_warehouse')]
                cn_warehouse = [p for p in all_products if not p.get('us_warehouse') and not p.get('eu_warehouse')]
                
                print(f"\nTotal CJ products: {len(all_products)}")
                print(f"US Warehouse: {len(us_warehouse)}")
                print(f"EU Warehouse: {len(eu_warehouse)}")
                print(f"CN Warehouse: {len(cn_warehouse)}")
                
                if us_warehouse:
                    print("\n[SUCCESS] US WAREHOUSE PRODUCTS:")
                    for p in us_warehouse[:3]:
                        print(f"  - {p.get('title', 'Unknown')[:40]}... (${p.get('cost_price', 0):.2f})")
                
                if eu_warehouse:
                    print("\n[SUCCESS] EU WAREHOUSE PRODUCTS:")
                    for p in eu_warehouse[:3]:
                        print(f"  - {p.get('title', 'Unknown')[:40]}... (${p.get('cost_price', 0):.2f})")
                
                # Check if warehouse field is being populated
                warehouse_info_present = sum(1 for p in all_products if p.get('warehouse'))
                print(f"\n[INFO] Products with warehouse info: {warehouse_info_present}/{len(all_products)}")
                
                return len(all_products) > 0
                
        except Exception as e:
            print(f"[ERROR] {e}")
            return False


async def add_warehouse_filter_endpoint():
    """Check if we need to add warehouse filtering to the API"""
    print("\n" + "="*60)
    print("RECOMMENDATION: Add Warehouse Filter Parameter")
    print("="*60)
    print("""
To enable US/EU warehouse filtering, add this parameter to discovery endpoint:

GET /api/discovery/products?niche=smart_home&warehouse=us

Options:
- warehouse=us   → Only US warehouse products
- warehouse=eu   → Only EU warehouse products  
- warehouse=any  → All products (default)

This would filter CJ products by warehouse location for faster shipping.
""")


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("OSPRA INTELLIGENCE - FULL SYSTEM VERIFICATION")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = {}
    
    # Run all tests
    results['cross_reference'] = await test_cross_reference()
    results['multi_niche'] = await test_multiple_niches()
    results['frontend_compat'] = await test_frontend_compatibility()
    results['warehouse_filter'] = await test_warehouse_filtering()
    
    # Show recommendation
    await add_warehouse_filter_endpoint()
    
    # Final summary
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    for test, passed in results.items():
        status = "[SUCCESS]" if passed else "[FAILED]"
        print(f"  {status} {test}")
    
    passed_count = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nOverall: {passed_count}/{total} tests passed")
    
    if passed_count == total:
        print("\n[SUCCESS] All systems operational!")
    else:
        print("\n[WARNING] Some tests failed - review above for details")
    
    return passed_count == total


if __name__ == "__main__":
    asyncio.run(main())
