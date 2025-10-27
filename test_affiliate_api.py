#!/usr/bin/env python3
"""
Test AliExpress Affiliate API (no OAuth needed).

This API only requires App Key + Secret with HMAC signature.
No access_token needed!
"""

import time
import hmac
import hashlib
import requests
from typing import Dict, Any


# Your credentials
APP_KEY = "520918"
APP_SECRET = "idjX6tOzHx6urVsSylVzEcHZKwBN4YhN"
API_URL = "https://api-sg.aliexpress.com/sync"


def generate_signature(params: Dict[str, str]) -> str:
    """Generate HMAC-SHA256 signature for API request."""
    sorted_params = sorted(params.items())
    sign_string = "".join([f"{k}{v}" for k, v in sorted_params])
    signature = hmac.new(
        APP_SECRET.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()
    return signature


def test_affiliate_product_search(keywords: str = "smart lock"):
    """
    Test Affiliate Product Search API.

    This should work WITHOUT OAuth!
    """
    params = {
        "app_key": APP_KEY,
        "method": "aliexpress.affiliate.product.query",
        "timestamp": str(int(time.time() * 1000)),
        "format": "json",
        "v": "2.0",
        "sign_method": "sha256",
        # Search parameters
        "keywords": keywords,
        "target_currency": "USD",
        "target_language": "EN",
        "page_size": "5",
        "sort": "SALE_PRICE_ASC"
    }

    # Generate signature
    params["sign"] = generate_signature(params)

    try:
        print(f"\n🔍 Testing Affiliate Product Search: '{keywords}'")
        print(f"Endpoint: {API_URL}")
        print(f"Method: {params['method']}")

        response = requests.get(API_URL, params=params, timeout=15)

        print(f"\nHTTP Status: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ Failed: HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None

        data = response.json()

        # Check for API errors
        if "error_response" in data:
            error = data["error_response"]
            print(f"❌ API Error: {error.get('code')} - {error.get('msg')}")
            return None

        # Success!
        if "aliexpress_affiliate_product_query_response" in data:
            result = data["aliexpress_affiliate_product_query_response"]["resp_result"]

            if "result" in result and "products" in result["result"]:
                products = result["result"]["products"]["product"]

                print(f"\n✅ SUCCESS! Found {len(products)} products:")

                for i, product in enumerate(products[:3], 1):
                    print(f"\n{i}. {product.get('product_title', 'No title')}")
                    print(f"   Price: ${product.get('target_sale_price', 'N/A')}")
                    print(f"   URL: {product.get('product_detail_url', 'N/A')}")
                    print(f"   Image: {product.get('product_main_image_url', 'N/A')}")

                return products
            else:
                print("✅ API call successful but no products found")
                return []
        else:
            print(f"❌ Unexpected response format: {list(data.keys())}")
            return None

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return None


def test_affiliate_hot_products():
    """Test Hot Products API (trending items)."""
    params = {
        "app_key": APP_KEY,
        "method": "aliexpress.affiliate.hotproduct.query",
        "timestamp": str(int(time.time() * 1000)),
        "format": "json",
        "v": "2.0",
        "sign_method": "sha256",
        "target_currency": "USD",
        "target_language": "EN",
        "page_size": "3"
    }

    params["sign"] = generate_signature(params)

    try:
        print(f"\n\n🔥 Testing Hot Products API")
        response = requests.get(API_URL, params=params, timeout=15)

        if response.status_code != 200:
            print(f"❌ Failed: HTTP {response.status_code}")
            return None

        data = response.json()

        if "error_response" in data:
            error = data["error_response"]
            print(f"❌ API Error: {error.get('code')} - {error.get('msg')}")
            return None

        if "aliexpress_affiliate_hotproduct_query_response" in data:
            result = data["aliexpress_affiliate_hotproduct_query_response"]["resp_result"]

            if "result" in result and "products" in result["result"]:
                products = result["result"]["products"]["product"]
                print(f"✅ SUCCESS! Found {len(products)} hot products")
                return products

        print(f"❌ Unexpected response: {list(data.keys())}")
        return None

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return None


if __name__ == "__main__":
    print("=" * 70)
    print("ALIEXPRESS AFFILIATE API TEST")
    print("=" * 70)
    print("\nTesting if we can access Affiliate APIs without OAuth...")

    # Test 1: Product Search
    products = test_affiliate_product_search("smart lock")

    # Test 2: Hot Products
    hot_products = test_affiliate_hot_products()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if products is not None:
        print("✅ Affiliate Product Search: WORKING")
        print("   We can search products without OAuth!")
    else:
        print("❌ Affiliate Product Search: FAILED")

    if hot_products is not None:
        print("✅ Hot Products API: WORKING")
    else:
        print("❌ Hot Products API: FAILED")

    if products is not None or hot_products is not None:
        print("\n💡 GOOD NEWS: We can use Affiliate API for product search!")
        print("   This gives us:")
        print("   - Product search by keywords")
        print("   - Product details (title, price, images)")
        print("   - Product URLs")
        print("   - Hot/trending products")
        print("\n   We can add these to the dashboard NOW!")
    else:
        print("\n⚠️  Affiliate API also requires access we don't have")

    print("\n" + "=" * 70 + "\n")
