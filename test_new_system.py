#!/usr/bin/env python3
"""
Quick test script for the new intelligence system
Run this to verify everything is working
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_intelligence_engine():
    """Test the new ProductIntelligenceEngine v2"""
    print("🧪 Testing ProductIntelligenceEngine V2...")
    print("=" * 60)
    
    try:
        from ospra_os.intelligence.product_intelligence_v2 import ProductIntelligenceEngine
        print("✅ Import successful: product_intelligence_v2")
        
        engine = ProductIntelligenceEngine()
        print("✅ Engine initialized")
        
        print("\n🔍 Discovering products...")
        products = await engine.discover_winning_products(
            niches=['smart home'],
            max_per_niche=3
        )
        
        print(f"\n✅ Found {len(products)} products!")
        print("\nSample Products:")
        print("-" * 60)
        
        for i, product in enumerate(products[:3], 1):
            display = product.get('display_data', {})
            print(f"\n{i}. {display.get('name', 'Unknown')}")
            print(f"   Score: {product.get('score', 0):.1f}/10 | Priority: {product.get('priority', 'N/A')}")
            print(f"   Cost: ${display.get('supplier_cost', 0):.2f} → Sell: ${display.get('market_price', 0):.2f}")
            print(f"   Profit: ${display.get('estimated_profit', 0):.2f} ({display.get('profit_margin', 0):.1f}%)")
            print(f"   AliExpress: {display.get('supplier_orders', 0):,} orders | {display.get('supplier_rating', 0)}★")
            
            if product.get('ai_explanation'):
                print(f"   🤖 Claude: {product['ai_explanation'][:100]}...")
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_aliexpress_api():
    """Test AliExpress API integration"""
    print("\n🧪 Testing AliExpress API...")
    print("=" * 60)
    
    try:
        from ospra_os.integrations.aliexpress_api import AliExpressAPI
        print("✅ Import successful: AliExpressAPI")
        
        api = AliExpressAPI()
        print("✅ API initialized")
        
        products = await api.search_products(
            query='smart led strip',
            min_orders=1000,
            limit=3
        )
        
        print(f"✅ Found {len(products)} products")
        
        for product in products[:2]:
            print(f"\n   • {product['name']}")
            print(f"     Price: ${product['price']:.2f} | Orders: {product['orders']:,} | Rating: {product['rating']}★")
        
        return True
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        return False

def test_environment():
    """Test environment variables"""
    print("\n🧪 Testing Environment Configuration...")
    print("=" * 60)
    
    required_vars = {
        'ANTHROPIC_API_KEY': 'Claude AI',
        'ALIEXPRESS_APP_KEY': 'AliExpress API',
        'SHOPIFY_STORE': 'Shopify Store',
        'SHOPIFY_API_TOKEN': 'Shopify API'
    }
    
    all_good = True
    for var, name in required_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:8] + '...' + value[-4:] if len(value) > 12 else value[:4] + '...'
            print(f"✅ {name}: {masked}")
        else:
            print(f"❌ {name}: NOT CONFIGURED")
            all_good = False
    
    return all_good

async def main():
    """Run all tests"""
    print("\n🚀 OUBON SHOP - SYSTEM TEST")
    print("=" * 60)
    
    # Test 1: Environment
    env_ok = test_environment()
    
    # Test 2: AliExpress API
    ali_ok = await test_aliexpress_api()
    
    # Test 3: Intelligence Engine
    engine_ok = await test_intelligence_engine()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Environment: {'✅ PASS' if env_ok else '❌ FAIL'}")
    print(f"AliExpress API: {'✅ PASS' if ali_ok else '❌ FAIL'}")
    print(f"Intelligence Engine: {'✅ PASS' if engine_ok else '❌ FAIL'}")
    
    if env_ok and ali_ok and engine_ok:
        print("\n🎉 ALL SYSTEMS GO! Ready to deploy.")
        print("\nNext steps:")
        print("1. Start server: python main.py")
        print("2. Visit: http://localhost:8000/premium")
        print("3. Click 'Discover Winning Products'")
    else:
        print("\n⚠️  Some tests failed. Check errors above.")
    
    return env_ok and ali_ok and engine_ok

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
