"""
Complete system test for differentiation features
"""
import asyncio
import requests
from datetime import datetime


def test_api_endpoints():
    """Test all new API endpoints"""
    base_url = "http://localhost:8000"

    print("🧪 Testing Differentiation System\n")
    print("=" * 60)

    # Test 1: Tier Info
    print("\n1️⃣ Testing Tier System...")
    try:
        r = requests.get(f"{base_url}/api/user/tier?user_id=1")
        data = r.json()
        print(f"✅ User Tier: {data.get('tier')}")
        print(f"   Price: ${data.get('config', {}).get('price')}")
        print(f"   Max Stores: {data.get('config', {}).get('max_stores')}")
    except Exception as e:
        print(f"❌ Tier test failed: {e}")

    # Test 2: Velocity Stats
    print("\n2️⃣ Testing Velocity Detection...")
    try:
        r = requests.get(f"{base_url}/api/velocity/stats?niche=smart_home")
        data = r.json()
        if data.get('success'):
            stats = data.get('stats', {})
            print(f"✅ Velocity Stats:")
            print(f"   Discovery Phase: {len(stats.get('discovery', []))} products")
            print(f"   Early Spike: {len(stats.get('early_spike', []))} products")
            print(f"   Growth: {len(stats.get('growth', []))} products")
            print(f"   Maturity: {len(stats.get('maturity', []))} products")
        else:
            print(f"⚠️  No velocity data yet")
    except Exception as e:
        print(f"❌ Velocity test failed: {e}")

    # Test 3: Smart Recommendations
    print("\n3️⃣ Testing Smart Recommendations...")
    try:
        r = requests.post(
            f"{base_url}/api/recommendations/smart",
            params={"user_id": 1, "max_products": 5}
        )
        data = r.json()
        if data.get('success'):
            print(f"✅ Smart Recommendations:")
            print(f"   User Tier: {data.get('user_tier')}")
            print(f"   Products: {data.get('count')}")
            print(f"   Personalization:")
            for key, value in data.get('personalization', {}).items():
                print(f"   - {key}: {value}")

            # Show first product
            if data.get('products'):
                product = data['products'][0]
                print(f"\n   Sample Product:")
                print(f"   - Name: {product.get('name')}")
                if 'marketing_angle' in product:
                    angle = product['marketing_angle']
                    print(f"   - Angle: {angle.get('angle')}")
                    print(f"   - Title: {angle.get('title')}")
        else:
            print(f"⚠️  Recommendations failed: {data.get('error')}")
    except Exception as e:
        print(f"❌ Recommendations test failed: {e}")

    # Test 4: Analytics
    print("\n4️⃣ Testing Recommendation Analytics...")
    try:
        r = requests.get(f"{base_url}/api/recommendations/analytics/1")
        data = r.json()
        if data.get('success'):
            print(f"✅ Analytics:")
            print(f"   Total Recommended: {data.get('total_recommended', 0)}")
            print(f"   Deployed: {data.get('deployed', 0)}")
            print(f"   Success Rate: {data.get('success_rate', 0):.1f}%")
        else:
            print(f"⚠️  No analytics data yet")
    except Exception as e:
        print(f"❌ Analytics test failed: {e}")

    # Test 5: Auto-Discovery Manual Trigger
    print("\n5️⃣ Testing Auto-Discovery (Manual)...")
    try:
        r = requests.post(f"{base_url}/api/admin/run-discovery-now")
        data = r.json()
        if data.get('success'):
            print(f"✅ Auto-discovery completed")
        else:
            print(f"❌ Discovery failed: {data.get('error')}")
    except Exception as e:
        print(f"❌ Discovery test failed: {e}")

    print("\n" + "=" * 60)
    print("✅ System test complete!\n")


if __name__ == "__main__":
    test_api_endpoints()
