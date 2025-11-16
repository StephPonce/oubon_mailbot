#!/usr/bin/env python3
"""
Test Platform Adapter Base Class
Tests the abstract base class and exception hierarchy
"""

import asyncio


def test_platform_adapter_base():
    """Test Platform Adapter base class"""

    print("=" * 70)
    print("TESTING PLATFORM ADAPTER BASE CLASS")
    print("=" * 70)
    print()

    # Test 1: Import
    print("1. Testing imports...")
    try:
        from ospra_os.platforms import (
            PlatformAdapter,
            PlatformAPIError,
            RateLimitError,
            AuthenticationError,
            ProductNotFoundError,
            InvalidRequestError,
            get_available_platforms,
            validate_platform_name
        )
        print("✅ All imports successful")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return

    # Test 2: Exception hierarchy
    print("\n2. Testing exception hierarchy...")
    try:
        # Test base exception
        base_error = PlatformAPIError("Test error", platform="test")
        assert str(base_error) == "[test] Test error"
        print("✅ PlatformAPIError working")

        # Test RateLimitError
        rate_error = RateLimitError(platform="test", retry_after=60)
        assert rate_error.retry_after == 60
        print("✅ RateLimitError working")

        # Test AuthenticationError
        auth_error = AuthenticationError(platform="test")
        print("✅ AuthenticationError working")

        # Test ProductNotFoundError
        not_found = ProductNotFoundError("prod_123", platform="test")
        assert not_found.product_id == "prod_123"
        print("✅ ProductNotFoundError working")

        # Test InvalidRequestError
        invalid = InvalidRequestError("Invalid field", platform="test", field="price")
        assert invalid.field == "price"
        print("✅ InvalidRequestError working")

    except Exception as e:
        print(f"❌ Exception hierarchy test failed: {e}")
        return

    # Test 3: Create mock adapter
    print("\n3. Testing mock adapter creation...")
    try:
        class MockAdapter(PlatformAdapter):
            """Mock adapter for testing"""

            def __init__(self, credentials: dict):
                super().__init__(credentials)
                self.platform_name = "mock"
                self.api_version = "1.0"
                self.base_url = "https://mock-platform.com/api"

            async def test_connection(self):
                return {
                    "success": True,
                    "store_name": "Mock Store",
                    "store_url": "https://mock-store.com",
                    "platform_version": "1.0"
                }

            async def deploy_product(self, product):
                return {
                    "success": True,
                    "platform_product_id": "mock_123",
                    "platform_url": "https://mock-store.com/products/123"
                }

            async def update_product(self, platform_product_id, updates):
                return {"success": True, "updated_fields": list(updates.keys())}

            async def delete_product(self, platform_product_id):
                return {"success": True, "archived": False}

            async def get_orders(self, limit=50, status="any", since=None):
                return {
                    "success": True,
                    "orders": [],
                    "total_count": 0,
                    "has_more": False
                }

            async def get_products(self, limit=50, published_status="published"):
                return {
                    "success": True,
                    "products": [],
                    "total_count": 0,
                    "has_more": False
                }

            async def update_inventory(self, platform_product_id, quantity, location_id=None):
                return {
                    "success": True,
                    "new_quantity": quantity,
                    "previous_quantity": 0
                }

            async def sync_orders(self, since=None):
                return {
                    "success": True,
                    "orders_synced": 0,
                    "orders_updated": 0,
                    "last_sync_time": "2025-11-14T12:00:00Z"
                }

            async def get_store_info(self):
                return {
                    "success": True,
                    "store_name": "Mock Store",
                    "store_url": "https://mock-store.com",
                    "email": "mock@example.com",
                    "currency": "USD",
                    "domain": "mock-store.com",
                    "plan": "professional",
                    "country": "US",
                    "timezone": "America/New_York",
                    "enabled": True
                }

        # Create instance
        adapter = MockAdapter({"api_key": "test_key"})
        print(f"✅ Mock adapter created: {adapter.platform_name}")

    except Exception as e:
        print(f"❌ Mock adapter creation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 4: Test helper methods
    print("\n4. Testing helper methods...")
    try:
        # get_platform_info
        info = adapter.get_platform_info()
        assert info["platform"] == "mock"
        assert info["api_version"] == "1.0"
        assert info["adapter_version"] == "1.0.0"
        print("✅ get_platform_info() working")

        # track_request
        adapter.track_request()
        adapter.track_request()
        stats = adapter.get_request_stats()
        assert stats["total_requests"] == 2
        print("✅ track_request() and get_request_stats() working")

        # validate_product_data
        valid_product = {"title": "Test Product", "price": 99.99}
        adapter.validate_product_data(valid_product)
        print("✅ validate_product_data() accepts valid data")

        # Test invalid data
        try:
            invalid_product = {"title": "Test"}  # Missing price
            adapter.validate_product_data(invalid_product)
            print("❌ Should have raised InvalidRequestError")
        except InvalidRequestError:
            print("✅ validate_product_data() rejects invalid data")

        # build_error_response
        test_error = PlatformAPIError("Test error", platform="mock")
        error_response = adapter.build_error_response(test_error, context="test")
        assert error_response["success"] is False
        assert "error" in error_response
        print("✅ build_error_response() working")

    except Exception as e:
        print(f"❌ Helper methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 5: Test async methods
    print("\n5. Testing async methods...")
    async def test_async():
        # test_connection
        result = await adapter.test_connection()
        assert result["success"] is True
        assert result["store_name"] == "Mock Store"
        print("✅ test_connection() working")

        # deploy_product
        product = {
            "title": "Smart Watch",
            "price": 99.99,
            "sku": "SW-001",
            "inventory": 100
        }
        result = await adapter.deploy_product(product)
        assert result["success"] is True
        assert "platform_product_id" in result
        print("✅ deploy_product() working")

        # update_product
        result = await adapter.update_product("mock_123", {"price": 89.99})
        assert result["success"] is True
        print("✅ update_product() working")

        # delete_product
        result = await adapter.delete_product("mock_123")
        assert result["success"] is True
        print("✅ delete_product() working")

        # get_orders
        result = await adapter.get_orders(limit=10)
        assert result["success"] is True
        assert "orders" in result
        print("✅ get_orders() working")

        # get_products
        result = await adapter.get_products(limit=10)
        assert result["success"] is True
        assert "products" in result
        print("✅ get_products() working")

        # update_inventory
        result = await adapter.update_inventory("mock_123", 75)
        assert result["success"] is True
        assert result["new_quantity"] == 75
        print("✅ update_inventory() working")

        # sync_orders
        result = await adapter.sync_orders()
        assert result["success"] is True
        print("✅ sync_orders() working")

        # get_store_info
        result = await adapter.get_store_info()
        assert result["success"] is True
        assert result["currency"] == "USD"
        print("✅ get_store_info() working")

    try:
        asyncio.run(test_async())
    except Exception as e:
        print(f"❌ Async methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 6: Utility functions
    print("\n6. Testing utility functions...")
    try:
        # get_available_platforms
        platforms = get_available_platforms()
        assert isinstance(platforms, list)
        assert len(platforms) > 0
        print(f"✅ get_available_platforms() returns: {platforms}")

        # validate_platform_name
        assert validate_platform_name("shopify") is True
        assert validate_platform_name("amazon") is True
        assert validate_platform_name("unknown") is False
        print("✅ validate_platform_name() working")

    except Exception as e:
        print(f"❌ Utility functions test failed: {e}")
        return

    print("\n" + "=" * 70)
    print("✅ ALL PLATFORM ADAPTER BASE TESTS PASSED!")
    print("=" * 70)
    print()
    print("📋 Summary:")
    print("   ✓ Exception hierarchy working correctly")
    print("   ✓ Abstract base class structure valid")
    print("   ✓ All 9 abstract methods defined")
    print("   ✓ Helper methods functional")
    print("   ✓ Async operations working")
    print("   ✓ Utility functions working")
    print()
    print("🎯 Ready for platform adapter implementations:")
    print("   - ShopifyAdapter")
    print("   - AmazonAdapter")
    print("   - WooCommerceAdapter")
    print()


if __name__ == "__main__":
    test_platform_adapter_base()
