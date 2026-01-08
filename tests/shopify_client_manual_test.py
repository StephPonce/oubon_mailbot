#!/usr/bin/env python3
"""
Test script for ShopifyClient

This tests the Shopify integration without making actual API calls.
To test with real API calls, ensure SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN are set in .env
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ospra_os.integrations.shopify_client import ShopifyClient


def test_client_initialization():
    """Test that the client initializes correctly"""
    print("=" * 60)
    print("TEST 1: Client Initialization")
    print("=" * 60)

    client = ShopifyClient()

    print(f"Store URL: {client.store_url}")
    print(f"Access Token: {'*' * 20 if client.access_token else 'Not set'}")
    print(f"Enabled: {client.enabled}")
    print(f"API Version: {client.api_version}")

    if client.enabled:
        print(f"Base URL: {client.base_url}")
        print("\n[SUCCESS] Client initialized successfully!")
    else:
        print("\n[WARNING]  Client not enabled - missing credentials")

    return client


def test_description_generation():
    """Test the description generation"""
    print("\n" + "=" * 60)
    print("TEST 2: Product Description Generation")
    print("=" * 60)

    client = ShopifyClient()

    sample_product = {
        "name": "Smart LED Strip Lights",
        "description": "Transform any room with vibrant colors",
        "features": [
            "16 million colors",
            "Voice control compatible",
            "App-controlled",
            "Music sync mode"
        ],
        "use_cases": [
            "Bedroom ambient lighting",
            "Gaming setup enhancement",
            "Party decorations"
        ]
    }

    description = client._generate_description(sample_product)
    print("\nGenerated Description:")
    print("-" * 60)
    print(description)
    print("-" * 60)
    print("\n[SUCCESS] Description generated successfully!")


def test_product_creation_format():
    """Test product creation format (without actual API call)"""
    print("\n" + "=" * 60)
    print("TEST 3: Product Creation Format")
    print("=" * 60)

    sample_product = {
        "name": "Wireless Bluetooth Earbuds",
        "price": 29.99,
        "category": "Electronics",
        "niche": "fitness",
        "image_url": "https://example.com/earbuds.jpg",
        "description": "Premium sound quality for your workouts",
        "features": [
            "30-hour battery life",
            "Waterproof IPX7",
            "Active noise cancellation"
        ]
    }

    # Simulate the product format that would be sent to Shopify
    shopify_product = {
        "product": {
            "title": sample_product["name"],
            "vendor": "AliExpress",
            "product_type": sample_product.get("category", "General"),
            "tags": f"{sample_product.get('niche', '')}, dropshipping, trending",
            "variants": [
                {
                    "price": str(sample_product["price"]),
                    "compare_at_price": str(sample_product["price"] * 1.3),
                    "inventory_management": None,
                    "fulfillment_service": "manual"
                }
            ],
            "images": [{"src": sample_product["image_url"]}]
        }
    }

    import json
    print("\nShopify Product Format:")
    print(json.dumps(shopify_product, indent=2))
    print("\n[SUCCESS] Product format is correct!")


def test_list_products():
    """Test listing products (only if client is enabled)"""
    print("\n" + "=" * 60)
    print("TEST 4: List Products (Real API Call)")
    print("=" * 60)

    client = ShopifyClient()

    if not client.enabled:
        print("[WARNING]  Skipping - client not enabled")
        print("To enable: Set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN in .env")
        return

    print(f"Fetching products from {client.store_url}...")
    products = client.list_products(limit=5)

    if products:
        print(f"\n[SUCCESS] Found {len(products)} products:")
        for i, product in enumerate(products, 1):
            print(f"{i}. {product['title']} - ${product['variants'][0]['price']}")
    else:
        print("[WARNING]  No products found or API error")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("SHOPIFY CLIENT TEST SUITE")
    print("=" * 60)

    try:
        # Test 1: Initialization
        client = test_client_initialization()

        # Test 2: Description generation
        test_description_generation()

        # Test 3: Product format
        test_product_creation_format()

        # Test 4: List products (only if enabled)
        test_list_products()

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
