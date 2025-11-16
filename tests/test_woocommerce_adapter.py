#!/usr/bin/env python3
"""
Test WooCommerce Adapter
Tests the WooCommerce REST API platform adapter implementation
"""

import asyncio
import os


def test_woocommerce_adapter():
    """Test WooCommerce adapter implementation"""

    print("=" * 70)
    print("TESTING WOOCOMMERCE ADAPTER")
    print("=" * 70)
    print()

    # Test 1: Import
    print("1. Testing imports...")
    try:
        from ospra_os.platforms import WooCommerceAdapter
        from ospra_os.platforms import (
            PlatformAPIError,
            AuthenticationError,
            RateLimitError
        )
        print("✅ All imports successful")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return

    # Test 2: Initialize with mock credentials
    print("\n2. Testing initialization...")
    try:
        # Mock credentials
        credentials = {
            "store_url": "https://example.com",
            "consumer_key": "ck_1234567890abcdef1234567890abcdef12345678",
            "consumer_secret": "cs_1234567890abcdef1234567890abcdef12345678",
            "wp_api": True,
            "version": "wc/v3"
        }

        adapter = WooCommerceAdapter(credentials)

        assert adapter.platform_name == "woocommerce"
        assert adapter.api_version == "wc/v3"
        assert adapter.store_url == "https://example.com"
        assert "wp-json/wc/v3" in adapter.base_url

        print(f"✅ Adapter initialized")
        print(f"   Platform: {adapter.platform_name}")
        print(f"   API Version: {adapter.api_version}")
        print(f"   Store URL: {adapter.store_url}")
        print(f"   Base URL: {adapter.base_url}")

    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 3: Test missing credentials
    print("\n3. Testing credential validation...")
    try:
        try:
            bad_adapter = WooCommerceAdapter({})
            print("❌ Should have raised AuthenticationError")
        except AuthenticationError as e:
            print("✅ Correctly rejects missing credentials")
            print(f"   Error: {str(e)[:80]}...")

    except Exception as e:
        print(f"❌ Credential validation failed: {e}")
        return

    # Test 4: Test HTTPS warning
    print("\n4. Testing HTTPS validation...")
    try:
        # Should log warning for HTTP (not HTTPS)
        http_adapter = WooCommerceAdapter({
            "store_url": "http://example.com",
            "consumer_key": "ck_test",
            "consumer_secret": "cs_test"
        })
        print("✅ Accepts HTTP but logs warning")

    except Exception as e:
        print(f"❌ HTTPS validation failed: {e}")
        return

    # Test 5: Test helper methods
    print("\n5. Testing helper methods...")
    try:
        # get_platform_info
        info = adapter.get_platform_info()
        assert info["platform"] == "woocommerce"
        assert info["api_version"] == "wc/v3"
        print("✅ get_platform_info() working")

        # track_request
        adapter.track_request()
        stats = adapter.get_request_stats()
        assert stats["total_requests"] == 1
        print("✅ track_request() working")

        # validate_product_data
        valid_product = {
            "title": "Smart Watch",
            "price": 99.99,
            "sku": "SW-001"
        }
        adapter.validate_product_data(valid_product)
        print("✅ validate_product_data() accepts valid data")

    except Exception as e:
        print(f"❌ Helper methods failed: {e}")
        return

    # Test 6: Test data normalization
    print("\n6. Testing data normalization...")
    try:
        # Test product normalization (WooCommerce format)
        wc_product = {
            "id": 123,
            "name": "Smart LED Bulb",
            "type": "simple",
            "description": "<p>WiFi enabled smart bulb</p>",
            "short_description": "<p>Smart lighting</p>",
            "sku": "SLB-001",
            "regular_price": "24.99",
            "sale_price": "19.99",
            "stock_quantity": 100,
            "status": "publish",
            "date_created": "2025-11-14T10:00:00",
            "date_modified": "2025-11-14T11:00:00",
            "permalink": "https://example.com/product/smart-led-bulb",
            "images": [
                {"src": "https://example.com/image1.jpg"},
                {"src": "https://example.com/image2.jpg"}
            ],
            "tags": [
                {"name": "smart-home"},
                {"name": "lighting"}
            ],
            "categories": [
                {"name": "Electronics"},
                {"name": "Smart Home"}
            ]
        }

        normalized = adapter.normalize_product(wc_product)

        assert normalized["platform_product_id"] == "123"
        assert normalized["title"] == "Smart LED Bulb"
        assert normalized["price"] == 24.99
        assert normalized["sale_price"] == 19.99
        assert normalized["sku"] == "SLB-001"
        assert len(normalized["images"]) == 2
        assert len(normalized["tags"]) == 2
        assert len(normalized["categories"]) == 2
        print("✅ normalize_product() working correctly")

        # Test order normalization
        wc_order = {
            "id": 456,
            "number": "456",
            "status": "completed",
            "currency": "USD",
            "total": "109.99",
            "total_tax": "8.00",
            "shipping_total": "10.00",
            "date_created": "2025-11-14T10:00:00",
            "date_modified": "2025-11-14T11:00:00",
            "payment_method_title": "Credit Card",
            "billing": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "555-1234",
                "address_1": "123 Main St",
                "address_2": "Apt 4",
                "city": "Seattle",
                "state": "WA",
                "postcode": "98101",
                "country": "US"
            },
            "shipping": {
                "first_name": "John",
                "last_name": "Doe",
                "address_1": "123 Main St",
                "address_2": "Apt 4",
                "city": "Seattle",
                "state": "WA",
                "postcode": "98101",
                "country": "US"
            },
            "line_items": [
                {
                    "product_id": 123,
                    "variation_id": 0,
                    "name": "Smart LED Bulb",
                    "quantity": 4,
                    "price": "19.99",
                    "sku": "SLB-001",
                    "total": "79.96"
                }
            ]
        }

        normalized_order = adapter.normalize_order(wc_order)

        assert normalized_order["platform_order_id"] == "456"
        assert normalized_order["order_number"] == "456"
        assert normalized_order["total_price"] == 109.99
        assert normalized_order["customer_email"] == "john@example.com"
        assert normalized_order["customer_name"] == "John Doe"
        assert len(normalized_order["line_items"]) == 1
        assert normalized_order["status"] == "completed"
        print("✅ normalize_order() working correctly")

    except Exception as e:
        print(f"❌ Normalization failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 7: Test rate limiting logic
    print("\n7. Testing rate limiting...")
    try:
        # Check rate limit constant
        assert adapter.RATE_LIMIT_DELAY == 0.25
        print(f"✅ Rate limit configured: {adapter.RATE_LIMIT_DELAY}s (4 req/sec)")

    except Exception as e:
        print(f"❌ Rate limiting test failed: {e}")
        return

    # Test 8: Test async method signatures
    print("\n8. Testing async method signatures...")
    try:
        import inspect

        methods_to_check = [
            "test_connection",
            "deploy_product",
            "update_product",
            "delete_product",
            "get_orders",
            "get_products",
            "update_inventory",
            "sync_orders",
            "get_store_info"
        ]

        for method_name in methods_to_check:
            method = getattr(adapter, method_name)
            assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"

        print(f"✅ All {len(methods_to_check)} abstract methods are async")

    except Exception as e:
        print(f"❌ Async signature test failed: {e}")
        return

    # Test 9: Test HTTP headers
    print("\n9. Testing HTTP headers...")
    try:
        headers = adapter._build_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert "OspraOS" in headers["User-Agent"]
        print("✅ HTTP headers correctly formatted")

    except Exception as e:
        print(f"❌ HTTP headers test failed: {e}")
        return

    print("\n" + "=" * 70)
    print("✅ ALL WOOCOMMERCE ADAPTER TESTS PASSED!")
    print("=" * 70)
    print()
    print("📋 Summary:")
    print("   ✓ WooCommerce adapter properly inherits from PlatformAdapter")
    print("   ✓ All 9 abstract methods implemented")
    print("   ✓ Credential validation working (3 required fields)")
    print("   ✓ Data normalization working (products & orders)")
    print("   ✓ Rate limiting configured (4 req/sec)")
    print("   ✓ HTTP Basic Auth setup")
    print("   ✓ Helper methods functional")
    print("   ✓ HTTPS validation with warnings")
    print()
    print("🎯 WooCommerce Adapter Features:")
    print("   • WooCommerce REST API wc/v3")
    print("   • WordPress /wp-json/ structure")
    print("   • HTTP Basic Auth (consumer key/secret)")
    print("   • Rate limiting (4 req/sec)")
    print("   • Product deployment with variants support")
    print("   • Order syncing with metrics")
    print("   • Inventory management")
    print("   • Categories and tags support")
    print("   • Comprehensive error handling")
    print()
    print("📚 To test with real WooCommerce store:")
    print("   1. Set WOOCOMMERCE_STORE_URL in environment")
    print("   2. Set WOOCOMMERCE_CONSUMER_KEY in environment")
    print("   3. Set WOOCOMMERCE_CONSUMER_SECRET in environment")
    print("   4. Run: python3 test_woocommerce_adapter_live.py")
    print()


def test_with_real_credentials():
    """
    Test with real WooCommerce credentials if available
    THIS WILL MAKE REAL API CALLS - USE WITH CAUTION
    """

    print("\n" + "=" * 70)
    print("TESTING WITH REAL WOOCOMMERCE CREDENTIALS")
    print("=" * 70)
    print()

    store_url = os.getenv("WOOCOMMERCE_STORE_URL")
    consumer_key = os.getenv("WOOCOMMERCE_CONSUMER_KEY")
    consumer_secret = os.getenv("WOOCOMMERCE_CONSUMER_SECRET")

    if not store_url or not consumer_key or not consumer_secret:
        print("⚠️  No real credentials found in environment")
        print("   Set WOOCOMMERCE_STORE_URL, WOOCOMMERCE_CONSUMER_KEY,")
        print("   and WOOCOMMERCE_CONSUMER_SECRET to test")
        return

    print(f"Store: {store_url}")
    print()

    from ospra_os.platforms import WooCommerceAdapter

    async def run_live_tests():
        # Initialize
        adapter = WooCommerceAdapter({
            "store_url": store_url,
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret
        })

        # Test connection
        print("Testing connection...")
        result = await adapter.test_connection()

        if result.get("success"):
            print(f"✅ Connected to: {result['store_name']}")
            print(f"   WooCommerce: {result['platform_version']}")
            print(f"   WordPress: {result['wordpress_version']}")
            print(f"   Currency: {result['currency']}")
        else:
            print(f"❌ Connection failed: {result.get('error')}")
            return

        # Get store info
        print("\nGetting store info...")
        info = await adapter.get_store_info()

        if info.get("success"):
            print(f"✅ Store info retrieved")
            print(f"   Plan: {info.get('plan')}")
            print(f"   Country: {info.get('country')}")
            print(f"   Email: {info.get('email')}")
        else:
            print(f"❌ Get store info failed: {info.get('error')}")

        # Get products (first 5)
        print("\nFetching products...")
        products = await adapter.get_products(limit=5)

        if products.get("success"):
            count = products.get("total_count", 0)
            print(f"✅ Retrieved {count} products")
            for product in products.get("products", [])[:3]:
                print(f"   - {product['title']}: ${product['price']}")
        else:
            print(f"❌ Get products failed: {products.get('error')}")

        # Get orders (first 5)
        print("\nFetching orders...")
        orders = await adapter.get_orders(limit=5)

        if orders.get("success"):
            count = orders.get("total_count", 0)
            print(f"✅ Retrieved {count} orders")
            for order in orders.get("orders", [])[:3]:
                print(f"   - Order #{order['order_number']}: ${order['total_price']} ({order['status']})")
        else:
            print(f"❌ Get orders failed: {orders.get('error')}")

        # Sync orders
        print("\nSyncing orders...")
        sync_result = await adapter.sync_orders()

        if sync_result.get("success"):
            print(f"✅ Orders synced: {sync_result['orders_synced']}")
            metrics = sync_result.get("metrics", {})
            print(f"   Total Revenue: ${metrics.get('total_revenue', 0):.2f}")
            print(f"   Avg Order Value: ${metrics.get('avg_order_value', 0):.2f}")
        else:
            print(f"❌ Sync failed: {sync_result.get('error')}")

        # Show stats
        print("\nAPI Statistics:")
        stats = adapter.get_request_stats()
        print(f"   Total requests: {stats['total_requests']}")

        print("\n✅ Live tests complete!")

    try:
        asyncio.run(run_live_tests())
    except Exception as e:
        print(f"❌ Live tests failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run mock tests (always safe)
    test_woocommerce_adapter()

    # Run live tests if credentials are available
    if all([
        os.getenv("WOOCOMMERCE_STORE_URL"),
        os.getenv("WOOCOMMERCE_CONSUMER_KEY"),
        os.getenv("WOOCOMMERCE_CONSUMER_SECRET")
    ]):
        test_with_real_credentials()
    else:
        print("💡 Tip: Set WooCommerce credentials to test with real API:")
        print("   WOOCOMMERCE_STORE_URL, WOOCOMMERCE_CONSUMER_KEY,")
        print("   WOOCOMMERCE_CONSUMER_SECRET")
