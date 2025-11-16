#!/usr/bin/env python3
"""
Platform Integration Tests

Comprehensive test suite for all platform adapters using pytest.
Tests actual API connections, CRUD operations, and integration with multi-store system.

Run:
    pytest test_platforms.py -v
    pytest test_platforms.py -k shopify -v
    pytest test_platforms.py --cov=ospra_os/platforms

Author: OspraOS
Date: November 2025
"""

import pytest
import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import random
import string

from ospra_os.platforms.factory import PlatformFactory
from ospra_os.platforms import (
    PlatformAdapter,
    PlatformAPIError,
    AuthenticationError,
    ProductNotFoundError
)


# ============================================================================
# TEST CONFIGURATION
# ============================================================================

def get_test_credentials(platform: str) -> Optional[Dict]:
    """
    Load test credentials from environment variables.

    Returns None if credentials not configured (test will be skipped).
    """
    if platform == "shopify":
        store_domain = os.getenv("TEST_SHOPIFY_STORE_DOMAIN")
        admin_token = os.getenv("TEST_SHOPIFY_ADMIN_TOKEN")

        if not store_domain or not admin_token:
            return None

        return {
            "store_domain": store_domain,
            "admin_api_token": admin_token
        }

    elif platform == "amazon":
        credentials = {
            "marketplace_id": os.getenv("TEST_AMAZON_MARKETPLACE_ID"),
            "seller_id": os.getenv("TEST_AMAZON_SELLER_ID"),
            "refresh_token": os.getenv("TEST_AMAZON_REFRESH_TOKEN"),
            "client_id": os.getenv("TEST_AMAZON_CLIENT_ID"),
            "client_secret": os.getenv("TEST_AMAZON_CLIENT_SECRET"),
            "aws_access_key": os.getenv("TEST_AMAZON_AWS_ACCESS_KEY"),
            "aws_secret_key": os.getenv("TEST_AMAZON_AWS_SECRET_KEY")
        }

        if not all(credentials.values()):
            return None

        return credentials

    elif platform == "woocommerce":
        store_url = os.getenv("TEST_WOOCOMMERCE_STORE_URL")
        consumer_key = os.getenv("TEST_WOOCOMMERCE_CONSUMER_KEY")
        consumer_secret = os.getenv("TEST_WOOCOMMERCE_CONSUMER_SECRET")

        if not store_url or not consumer_key or not consumer_secret:
            return None

        return {
            "store_url": store_url,
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret
        }

    return None


def generate_test_product() -> Dict:
    """Generate random test product data."""
    random_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    return {
        "title": f"Test Product {random_id}",
        "description": f"This is a test product created by automated tests. ID: {random_id}",
        "short_description": f"Test product {random_id}",
        "price": round(random.uniform(10.0, 100.0), 2),
        "sale_price": round(random.uniform(5.0, 50.0), 2),
        "sku": f"TEST-{random_id}",
        "inventory": random.randint(10, 100),
        "tags": ["test", "automated", f"batch-{random_id[:3]}"],
        "categories": ["Test Products"],
        "status": "draft"  # Don't publish test products
    }


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def shopify_credentials():
    """Get Shopify test credentials."""
    creds = get_test_credentials("shopify")
    if not creds:
        pytest.skip("Shopify credentials not configured")
    return creds


@pytest.fixture
def amazon_credentials():
    """Get Amazon test credentials."""
    creds = get_test_credentials("amazon")
    if not creds:
        pytest.skip("Amazon credentials not configured")
    return creds


@pytest.fixture
def woocommerce_credentials():
    """Get WooCommerce test credentials."""
    creds = get_test_credentials("woocommerce")
    if not creds:
        pytest.skip("WooCommerce credentials not configured")
    return creds


@pytest.fixture
async def shopify_adapter(shopify_credentials):
    """Get authenticated Shopify adapter."""
    adapter = PlatformFactory.get_adapter("shopify", shopify_credentials)
    return adapter


@pytest.fixture
async def amazon_adapter(amazon_credentials):
    """Get authenticated Amazon adapter."""
    adapter = PlatformFactory.get_adapter("amazon", amazon_credentials)
    return adapter


@pytest.fixture
async def woocommerce_adapter(woocommerce_credentials):
    """Get authenticated WooCommerce adapter."""
    adapter = PlatformFactory.get_adapter("woocommerce", woocommerce_credentials)
    return adapter


# ============================================================================
# FACTORY TESTS
# ============================================================================

class TestPlatformFactory:
    """Test PlatformFactory functionality."""

    def test_list_adapters(self):
        """Test listing all available adapters."""
        print("\n🧪 Testing PlatformFactory.list_adapters()")

        adapters = PlatformFactory.list_adapters()

        assert "shopify" in adapters
        assert "amazon" in adapters
        assert "woocommerce" in adapters
        assert len(adapters) == 3

        print(f"✅ Found {len(adapters)} adapters: {', '.join(adapters)}")

    def test_get_available_platforms(self):
        """Test getting platform metadata."""
        print("\n🧪 Testing PlatformFactory.get_available_platforms()")

        platforms = PlatformFactory.get_available_platforms()

        assert len(platforms) == 3

        for platform in platforms:
            assert "name" in platform
            assert "display_name" in platform
            assert "complexity" in platform
            assert "features" in platform

            print(f"✅ {platform['display_name']}")
            print(f"   Complexity: {platform['complexity']}")
            print(f"   Credentials: {platform['credentials_count']}")
            print(f"   Setup time: {platform['setup_time_minutes']} min")

    def test_validate_credentials_shopify(self):
        """Test Shopify credential validation."""
        print("\n🧪 Testing credential validation for Shopify")

        # Valid credentials
        result = PlatformFactory.validate_credentials("shopify", {
            "store_domain": "test.myshopify.com",
            "admin_api_token": "shpat_test123"
        })

        assert result["valid"] is True
        print("✅ Valid credentials accepted")

        # Missing field
        result = PlatformFactory.validate_credentials("shopify", {
            "store_domain": "test.myshopify.com"
        })

        assert result["valid"] is False
        assert len(result["missing_fields"]) == 1
        print(f"✅ Missing field detected: {result['missing_fields'][0]['field']}")

    def test_get_required_credentials(self):
        """Test getting credential schema."""
        print("\n🧪 Testing PlatformFactory.get_required_credentials()")

        for platform in ["shopify", "amazon", "woocommerce"]:
            fields = PlatformFactory.get_required_credentials(platform)

            assert len(fields) > 0

            print(f"\n✅ {platform.title()} requires {len(fields)} credential fields:")
            for field in fields:
                required = "required" if field["required"] else "optional"
                print(f"   - {field['label']} ({required})")

    def test_compare_platforms(self):
        """Test platform comparison."""
        print("\n🧪 Testing PlatformFactory.compare_platforms()")

        comparison = PlatformFactory.compare_platforms()

        assert "platforms" in comparison
        assert "complexity" in comparison
        assert "features_matrix" in comparison

        print(f"\n✅ Compared {len(comparison['platforms'])} platforms")
        print(f"\nComplexity:")
        for platform, complexity in comparison["complexity"].items():
            print(f"   {platform}: {complexity}")

        print(f"\nCredentials count:")
        for platform, count in comparison["credentials_count"].items():
            print(f"   {platform}: {count}")


# ============================================================================
# SHOPIFY TESTS
# ============================================================================

class TestShopify:
    """Test Shopify adapter."""

    @pytest.mark.asyncio
    async def test_shopify_connection(self, shopify_adapter):
        """Test Shopify connection."""
        print("\n🧪 Testing Shopify connection")
        start_time = time.time()

        result = await shopify_adapter.test_connection()

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "store_name" in result

        print(f"✅ Connected to: {result['store_name']}")
        print(f"   Store URL: {result.get('store_url', 'N/A')}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_shopify_get_store_info(self, shopify_adapter):
        """Test getting Shopify store info."""
        print("\n🧪 Testing Shopify get_store_info()")
        start_time = time.time()

        result = await shopify_adapter.get_store_info()

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "store_name" in result
        assert "currency" in result

        print(f"✅ Store info retrieved")
        print(f"   Name: {result['store_name']}")
        print(f"   Currency: {result['currency']}")
        print(f"   Country: {result.get('country', 'N/A')}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_shopify_get_products(self, shopify_adapter):
        """Test fetching Shopify products."""
        print("\n🧪 Testing Shopify get_products()")
        start_time = time.time()

        result = await shopify_adapter.get_products(limit=5)

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "products" in result
        assert "total_count" in result

        print(f"✅ Retrieved {result['total_count']} products")
        for product in result["products"][:3]:
            print(f"   - {product['title']}: ${product['price']}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_shopify_get_orders(self, shopify_adapter):
        """Test fetching Shopify orders."""
        print("\n🧪 Testing Shopify get_orders()")
        start_time = time.time()

        result = await shopify_adapter.get_orders(limit=5)

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "orders" in result

        print(f"✅ Retrieved {result['total_count']} orders")
        for order in result["orders"][:3]:
            print(f"   - Order {order['order_number']}: ${order['total_price']}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_shopify_sync_orders(self, shopify_adapter):
        """Test syncing Shopify orders."""
        print("\n🧪 Testing Shopify sync_orders()")
        start_time = time.time()

        # Sync last 7 days
        since = datetime.utcnow() - timedelta(days=7)
        result = await shopify_adapter.sync_orders(since=since)

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "metrics" in result

        metrics = result["metrics"]
        print(f"✅ Synced {result['orders_synced']} orders")
        print(f"   Total Revenue: ${metrics.get('total_revenue', 0):.2f}")
        print(f"   Avg Order Value: ${metrics.get('avg_order_value', 0):.2f}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")


# ============================================================================
# AMAZON TESTS
# ============================================================================

class TestAmazon:
    """Test Amazon adapter."""

    @pytest.mark.asyncio
    async def test_amazon_connection(self, amazon_adapter):
        """Test Amazon connection."""
        print("\n🧪 Testing Amazon connection")
        start_time = time.time()

        result = await amazon_adapter.test_connection()

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "store_name" in result

        print(f"✅ Connected to: {result['store_name']}")
        print(f"   Marketplace: {result.get('marketplace_id', 'N/A')}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_amazon_get_store_info(self, amazon_adapter):
        """Test getting Amazon store info."""
        print("\n🧪 Testing Amazon get_store_info()")
        start_time = time.time()

        result = await amazon_adapter.get_store_info()

        elapsed = time.time() - start_time

        assert result["success"] is True

        print(f"✅ Store info retrieved")
        print(f"   Name: {result.get('store_name', 'N/A')}")
        print(f"   Currency: {result.get('currency', 'N/A')}")
        print(f"   Country: {result.get('country', 'N/A')}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_amazon_get_orders(self, amazon_adapter):
        """Test fetching Amazon orders."""
        print("\n🧪 Testing Amazon get_orders()")
        start_time = time.time()

        result = await amazon_adapter.get_orders(limit=5)

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "orders" in result

        print(f"✅ Retrieved {result['total_count']} orders")
        for order in result["orders"][:3]:
            print(f"   - Order {order['order_number']}: ${order['total_price']}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_amazon_sync_orders(self, amazon_adapter):
        """Test syncing Amazon orders."""
        print("\n🧪 Testing Amazon sync_orders()")
        start_time = time.time()

        # Sync last 30 days (Amazon default)
        result = await amazon_adapter.sync_orders()

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "metrics" in result

        metrics = result["metrics"]
        print(f"✅ Synced {result['orders_synced']} orders")
        print(f"   Total Revenue: ${metrics.get('total_revenue', 0):.2f}")
        print(f"   Avg Order Value: ${metrics.get('avg_order_value', 0):.2f}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")


# ============================================================================
# WOOCOMMERCE TESTS
# ============================================================================

class TestWooCommerce:
    """Test WooCommerce adapter."""

    @pytest.mark.asyncio
    async def test_woocommerce_connection(self, woocommerce_adapter):
        """Test WooCommerce connection."""
        print("\n🧪 Testing WooCommerce connection")
        start_time = time.time()

        result = await woocommerce_adapter.test_connection()

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "store_name" in result

        print(f"✅ Connected to: {result['store_name']}")
        print(f"   Platform: {result.get('platform_version', 'N/A')}")
        print(f"   WordPress: {result.get('wordpress_version', 'N/A')}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_woocommerce_get_store_info(self, woocommerce_adapter):
        """Test getting WooCommerce store info."""
        print("\n🧪 Testing WooCommerce get_store_info()")
        start_time = time.time()

        result = await woocommerce_adapter.get_store_info()

        elapsed = time.time() - start_time

        assert result["success"] is True

        print(f"✅ Store info retrieved")
        print(f"   Name: {result.get('store_name', 'N/A')}")
        print(f"   Currency: {result.get('currency', 'N/A')}")
        print(f"   WooCommerce: {result.get('woocommerce_version', 'N/A')}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_woocommerce_get_products(self, woocommerce_adapter):
        """Test fetching WooCommerce products."""
        print("\n🧪 Testing WooCommerce get_products()")
        start_time = time.time()

        result = await woocommerce_adapter.get_products(limit=5)

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "products" in result

        print(f"✅ Retrieved {result['total_count']} products")
        for product in result["products"][:3]:
            print(f"   - {product['title']}: ${product['price']}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_woocommerce_get_orders(self, woocommerce_adapter):
        """Test fetching WooCommerce orders."""
        print("\n🧪 Testing WooCommerce get_orders()")
        start_time = time.time()

        result = await woocommerce_adapter.get_orders(limit=5)

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "orders" in result

        print(f"✅ Retrieved {result['total_count']} orders")
        for order in result["orders"][:3]:
            print(f"   - Order #{order['order_number']}: ${order['total_price']}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_woocommerce_sync_orders(self, woocommerce_adapter):
        """Test syncing WooCommerce orders."""
        print("\n🧪 Testing WooCommerce sync_orders()")
        start_time = time.time()

        # Sync last 7 days
        since = datetime.utcnow() - timedelta(days=7)
        result = await woocommerce_adapter.sync_orders(since=since)

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert "metrics" in result

        metrics = result["metrics"]
        print(f"✅ Synced {result['orders_synced']} orders")
        print(f"   Total Revenue: ${metrics.get('total_revenue', 0):.2f}")
        print(f"   Avg Order Value: ${metrics.get('avg_order_value', 0):.2f}")
        print(f"   ⏱️  Time: {elapsed:.2f}s")


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Test performance and concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_store_info(self):
        """Test fetching store info from multiple platforms concurrently."""
        print("\n🧪 Testing concurrent store info retrieval")

        adapters = []
        platform_names = []

        # Create adapters for all configured platforms
        for platform in ["shopify", "amazon", "woocommerce"]:
            creds = get_test_credentials(platform)
            if creds:
                adapter = PlatformFactory.get_adapter(platform, creds)
                adapters.append(adapter)
                platform_names.append(platform)

        if not adapters:
            pytest.skip("No platforms configured for testing")

        # Fetch concurrently
        start_time = time.time()

        tasks = [adapter.get_store_info() for adapter in adapters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start_time

        # Check results
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))

        print(f"✅ Retrieved info from {successful}/{len(adapters)} platforms concurrently")
        print(f"   Platforms: {', '.join(platform_names)}")
        print(f"   ⏱️  Total time: {elapsed:.2f}s")
        print(f"   ⏱️  Avg per platform: {elapsed/len(adapters):.2f}s")

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, shopify_adapter):
        """Test rate limit handling with rapid requests."""
        print("\n🧪 Testing rate limit handling")

        start_time = time.time()
        request_count = 5

        # Make rapid requests
        tasks = [shopify_adapter.get_store_info() for _ in range(request_count)]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        # All should succeed (rate limiting should prevent errors)
        successful = sum(1 for r in results if r.get("success"))

        assert successful == request_count

        print(f"✅ Completed {successful}/{request_count} rapid requests")
        print(f"   ⏱️  Total time: {elapsed:.2f}s")
        print(f"   ⏱️  Avg per request: {elapsed/request_count:.2f}s")
        print(f"   Rate limiting working correctly")


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Test integration scenarios."""

    def test_factory_get_adapter(self):
        """Test factory adapter creation."""
        print("\n🧪 Testing factory adapter creation")

        # Mock credentials for each platform
        test_creds = {
            "shopify": {
                "store_domain": "test.myshopify.com",
                "admin_api_token": "shpat_test"
            },
            "amazon": {
                "marketplace_id": "ATVPDKIKX0DER",
                "seller_id": "A123",
                "refresh_token": "test",
                "client_id": "test",
                "client_secret": "test",
                "aws_access_key": "test",
                "aws_secret_key": "test"
            },
            "woocommerce": {
                "store_url": "https://test.com",
                "consumer_key": "ck_test",
                "consumer_secret": "cs_test"
            }
        }

        for platform, credentials in test_creds.items():
            adapter = PlatformFactory.get_adapter(platform, credentials)

            assert adapter is not None
            assert adapter.platform_name == platform

            print(f"✅ Created {platform} adapter")

    def test_platform_comparison(self):
        """Test platform comparison functionality."""
        print("\n🧪 Testing platform comparison")

        comparison = PlatformFactory.compare_platforms()

        assert len(comparison["platforms"]) == 3

        print(f"\n✅ Platform Comparison:")
        print(f"\n   Complexity:")
        for platform, complexity in comparison["complexity"].items():
            print(f"      {platform}: {complexity}")

        print(f"\n   Credentials Required:")
        for platform, count in comparison["credentials_count"].items():
            print(f"      {platform}: {count}")

        print(f"\n   Setup Time:")
        for platform, time_min in comparison["setup_time"].items():
            print(f"      {platform}: {time_min} minutes")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PLATFORM INTEGRATION TESTS")
    print("=" * 70)
    print()
    print("To run these tests, use pytest:")
    print("   pytest test_platforms.py -v")
    print()
    print("To test specific platform:")
    print("   pytest test_platforms.py -k shopify -v")
    print()
    print("To run with coverage:")
    print("   pytest test_platforms.py --cov=ospra_os/platforms")
    print()
    print("Configure test credentials via environment variables:")
    print("   TEST_SHOPIFY_STORE_DOMAIN, TEST_SHOPIFY_ADMIN_TOKEN")
    print("   TEST_AMAZON_*, TEST_WOOCOMMERCE_*")
    print()
    print("=" * 70)
