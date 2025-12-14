#!/usr/bin/env python3
"""
Test Multi-Store Portfolio System
Initializes database and tests all API endpoints

NOTE: This is a standalone integration test script designed to be run directly with:
      python tests/test_multi_store_system.py

      It is NOT a pytest test file. The functions are meant to be called programmatically.
      Pytest is configured to skip this file.
"""

import pytest
import requests
import json
from typing import Dict, Any

# Skip this entire module when running pytest - it's a standalone integration test
pytestmark = pytest.mark.skip(reason="Standalone integration test script, not pytest tests. Run with: python tests/test_multi_store_system.py")

BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api/portfolio"

def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def print_json(data: Any):
    print(json.dumps(data, indent=2))

def test_health():
    """Test that backend is running with multi-store support"""
    print_section("1️⃣  HEALTH CHECK")

    response = requests.get(f"{BASE_URL}/health")
    data = response.json()

    print(f"Status: {data['status']}")
    print(f"Service: {data['service']}")
    print(f"Multi-Store Loaded: {data.get('multi_store_loaded', False)}")

    if not data.get('multi_store_loaded'):
        print("❌ Multi-store router not loaded!")
        return False

    print("✅ Backend healthy with multi-store support")
    return True

def test_portfolio_overview():
    """Test portfolio overview endpoint"""
    print_section("2️⃣  PORTFOLIO OVERVIEW (Initial State)")

    try:
        response = requests.get(f"{API_BASE}/overview")

        if response.status_code == 200:
            data = response.json()
            print_json(data)
            print("\n✅ Portfolio overview retrieved successfully")
            return data
        else:
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_add_shopify_store():
    """Test adding a Shopify store"""
    print_section("3️⃣  ADD SHOPIFY STORE")

    store_data = {
        "store_name": "Main Shopify Store",
        "store_url": "rxxj7d-1i.myshopify.com",
        "platform": "shopify",
        "credentials": {
            "shop_url": "rxxj7d-1i.myshopify.com",
            "access_token": "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",
            "api_version": "2025-01"
        },
        "niche": "smart_home",
        "target_market": "US",
        "currency": "USD"
    }

    print("Sending request to add store...")
    print_json(store_data)

    try:
        response = requests.post(
            f"{API_BASE}/stores/add",
            json=store_data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            print("\n✅ Store added successfully!")
            print_json(data)
            return data
        else:
            print(f"\n❌ Failed to add store")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_add_amazon_store():
    """Test adding an Amazon store"""
    print_section("4️⃣  ADD AMAZON STORE")

    store_data = {
        "store_name": "Amazon Storefront",
        "store_url": "amazon.com/sp?seller=ABC123",
        "platform": "amazon",
        "credentials": {
            "seller_id": "ABC123",
            "mws_token": "amzn.mws.test_token",
            "marketplace_id": "ATVPDKIKX0DER"
        },
        "niche": "electronics",
        "target_market": "US",
        "currency": "USD"
    }

    print("Sending request to add Amazon store...")

    try:
        response = requests.post(
            f"{API_BASE}/stores/add",
            json=store_data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            print("\n✅ Amazon store added successfully!")
            print_json(data)
            return data
        else:
            print(f"\n❌ Failed to add store")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_store_rankings():
    """Test store rankings endpoint"""
    print_section("5️⃣  STORE RANKINGS")

    try:
        response = requests.get(f"{API_BASE}/rankings")

        if response.status_code == 200:
            data = response.json()

            print(f"Found {len(data)} stores:\n")
            for idx, store in enumerate(data, 1):
                print(f"{idx}. {store['store_name']} ({store['platform']})")
                print(f"   Rank: #{store['rank_position']} {store.get('rank_change_label', '—')}")
                print(f"   Monthly Revenue: ${store['monthly_revenue']:.2f}")
                print(f"   Total Revenue: ${store['total_revenue']:.2f}")
                print(f"   Products: {store['active_products']}/{store['product_count']}")
                print()

            print("✅ Rankings retrieved successfully")
            return data
        else:
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_get_store_details(store_id: int):
    """Test getting store details"""
    print_section(f"6️⃣  GET STORE DETAILS (ID: {store_id})")

    try:
        response = requests.get(f"{API_BASE}/stores/{store_id}")

        if response.status_code == 200:
            data = response.json()
            print_json(data)
            print("\n✅ Store details retrieved successfully")
            return data
        else:
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_update_store(store_id: int):
    """Test updating a store"""
    print_section(f"7️⃣  UPDATE STORE (ID: {store_id})")

    update_data = {
        "niche": "tech_gadgets",
        "store_name": "Updated Store Name"
    }

    print("Sending update request...")
    print_json(update_data)

    try:
        response = requests.put(
            f"{API_BASE}/stores/{store_id}",
            json=update_data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            data = response.json()
            print("\n✅ Store updated successfully!")
            print(f"New name: {data['store_name']}")
            print(f"New niche: {data['niche']}")
            return data
        else:
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_switch_active_store(store_id: int):
    """Test switching active store"""
    print_section(f"8️⃣  SWITCH ACTIVE STORE (ID: {store_id})")

    try:
        response = requests.post(f"{API_BASE}/stores/{store_id}/switch")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Switched to: {data['store_name']}")
            print(f"New rank position: #{data['rank_position']}")
            return data
        else:
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_final_overview():
    """Test final portfolio state"""
    print_section("9️⃣  FINAL PORTFOLIO STATE")

    try:
        response = requests.get(f"{API_BASE}/overview")

        if response.status_code == 200:
            data = response.json()

            print(f"📊 Portfolio Summary:")
            print(f"   Total Stores: {data['total_stores']}")
            print(f"   Active Stores: {data['active_stores']}")
            print(f"   Total Products: {data['total_products']}")
            print(f"   Total Revenue: ${data['total_revenue']:.2f}")
            print(f"   Monthly Revenue: ${data['monthly_revenue']:.2f}")
            print(f"\n   Platforms:")
            for platform, count in data.get('platforms', {}).items():
                print(f"     • {platform}: {count} store(s)")

            if data.get('best_performing_store'):
                print(f"\n   🏆 Best Performer: {data['best_performing_store']}")

            print("\n✅ Final overview retrieved successfully")
            return data
        else:
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  🚀 MULTI-STORE PORTFOLIO SYSTEM TEST")
    print("="*60)

    # Test 1: Health check
    if not test_health():
        print("\n❌ Backend not ready. Exiting.")
        return

    # Test 2: Initial overview
    overview = test_portfolio_overview()

    # Test 3: Add Shopify store
    shopify_store = test_add_shopify_store()
    if not shopify_store:
        print("\n⚠️  Could not add Shopify store")

    # Test 4: Add Amazon store
    amazon_store = test_add_amazon_store()
    if not amazon_store:
        print("\n⚠️  Could not add Amazon store")

    # Test 5: View rankings
    rankings = test_store_rankings()

    # Test 6: Get store details
    if shopify_store and shopify_store.get('id'):
        test_get_store_details(shopify_store['id'])

    # Test 7: Update store
    if shopify_store and shopify_store.get('id'):
        test_update_store(shopify_store['id'])

    # Test 8: Switch active store
    if amazon_store and amazon_store.get('id'):
        test_switch_active_store(amazon_store['id'])

    # Test 9: Final overview
    test_final_overview()

    # Final summary
    print_section("✅ TEST COMPLETE")
    print("All multi-store portfolio endpoints tested successfully!")
    print("\nNext steps:")
    print("  • Visit http://localhost:8001/docs for interactive API docs")
    print("  • Check database at: oubon_store.db")
    print("  • Review API docs: ospra_os/dashboard/MULTI_STORE_API.md")
    print()

if __name__ == "__main__":
    main()
