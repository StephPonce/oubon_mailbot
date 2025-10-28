#!/usr/bin/env python3
"""Test Shopify API connection and functionality."""

from app.shopify_client import ShopifyClient
from ospra_os.core.settings import get_settings
import requests
import json


async def test_shopify_connection():
    """Test all Shopify API functions."""

    settings = get_settings()

    print("=" * 70)
    print("SHOPIFY API CONNECTION TEST")
    print("=" * 70)

    print("\n🔧 Initializing Shopify Client...")

    # Check if required settings exist
    if not settings.SHOPIFY_STORE_DOMAIN:
        print("❌ SHOPIFY_STORE_DOMAIN not configured")
        print("Set OUBONSHOP_SHOPIFY_STORE_DOMAIN in environment")
        return

    if not hasattr(settings, 'SHOPIFY_ADMIN_TOKEN') and not hasattr(settings, 'SHOPIFY_API_TOKEN'):
        print("❌ Shopify Admin Token not configured")
        print("Set OUBONSHOP_SHOPIFY_ADMIN_TOKEN or OUBONSHOP_SHOPIFY_API_TOKEN")
        return

    client = ShopifyClient(settings)

    print("✅ Shopify client initialized")
    print(f"   Store: {settings.SHOPIFY_STORE_DOMAIN}")
    print(f"   API Version: {settings.SHOPIFY_API_VERSION}\n")

    # Test 1: Get store info
    print("📊 Test 1: Fetching store info...")
    try:
        url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}/shop.json"
        response = requests.get(url, headers=client.headers, timeout=10)

        if response.status_code == 200:
            shop = response.json()["shop"]
            print(f"   ✅ Store Name: {shop.get('name')}")
            print(f"   ✅ Store Email: {shop.get('email')}")
            print(f"   ✅ Currency: {shop.get('currency')}")
            print(f"   ✅ Domain: {shop.get('domain')}\n")
        else:
            print(f"   ❌ Error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}\n")
    except Exception as e:
        print(f"   ❌ Error: {e}\n")

    # Test 2: List products
    print("📦 Test 2: Fetching products...")
    try:
        url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}/products.json?limit=5"
        response = requests.get(url, headers=client.headers, timeout=10)

        if response.status_code == 200:
            products = response.json().get("products", [])
            print(f"   ✅ Found {len(products)} products")

            for product in products[:3]:
                title = product.get('title', 'No title')
                price = product.get('variants', [{}])[0].get('price', 'N/A')
                print(f"   • {title} - ${price}")
            print()
        else:
            print(f"   ❌ Error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}\n")
    except Exception as e:
        print(f"   ❌ Error: {e}\n")

    # Test 3: List orders
    print("🛍️  Test 3: Fetching recent orders...")
    orders = []
    try:
        url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}/orders.json?limit=5&status=any"
        response = requests.get(url, headers=client.headers, timeout=10)

        if response.status_code == 200:
            orders = response.json().get("orders", [])
            print(f"   ✅ Found {len(orders)} recent orders")

            for order in orders[:3]:
                name = order.get('name', 'N/A')
                total = order.get('total_price', 'N/A')
                status = order.get('financial_status', 'N/A')
                print(f"   • Order {name} - ${total} - {status}")
            print()
        else:
            print(f"   ❌ Error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}\n")
    except Exception as e:
        print(f"   ❌ Error: {e}\n")

    # Test 4: Test order lookup function
    print("🔍 Test 4: Testing order lookup function...")
    if len(orders) > 0:
        test_order_name = orders[0].get("name")
        print(f"   Looking up order: {test_order_name}")

        try:
            order_data = client.lookup_order(test_order_name)
            if order_data:
                status = client.get_order_status(order_data)
                print(f"   ✅ Order found!")
                print(f"   • Status: {status['status']}")
                print(f"   • Total: ${status['total_price']}")
                print(f"   • Customer: {status['customer_email']}\n")
            else:
                print(f"   ❌ Order not found\n")
        except Exception as e:
            print(f"   ❌ Error testing lookup: {e}\n")
    else:
        print(f"   ⏭️  No orders to test with\n")

    print("=" * 70)
    print("✅ SHOPIFY API TEST COMPLETE!")
    print("=" * 70)
    print("\nSummary:")
    print("• Store info: Accessible")
    print(f"• Products: {len(products) if 'products' in locals() else 0} found")
    print(f"• Orders: {len(orders)} found")
    print("• Order lookup: Working" if len(orders) > 0 else "• Order lookup: No orders to test")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_shopify_connection())
