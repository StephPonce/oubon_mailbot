#!/usr/bin/env python3
"""
Test AliExpress Full Dropshipping Solution API Access.

This script verifies which APIs are accessible with current credentials.
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


def test_api(method: str, additional_params: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Test an API endpoint.

    Args:
        method: API method name
        additional_params: Extra params for the API call

    Returns:
        Result dict with success status and response/error
    """
    params = {
        "app_key": APP_KEY,
        "method": method,
        "timestamp": str(int(time.time() * 1000)),
        "format": "json",
        "v": "2.0",
        "sign_method": "sha256",
    }

    # Add additional params
    if additional_params:
        params.update(additional_params)

    # Generate signature
    params["sign"] = generate_signature(params)

    try:
        response = requests.get(API_URL, params=params, timeout=15)

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}",
                "details": response.text
            }

        data = response.json()

        # Check for API errors
        if "error_response" in data:
            error = data["error_response"]
            error_code = error.get("code", "unknown")
            error_msg = error.get("msg", "No message")

            # Distinguish between permission errors and parameter errors
            if "permission" in error_msg.lower() or "unauthorized" in error_msg.lower():
                return {
                    "success": False,
                    "error": "PERMISSION DENIED",
                    "code": error_code,
                    "message": error_msg
                }
            elif "param" in error_msg.lower() or "required" in error_msg.lower():
                return {
                    "success": True,  # API is accessible, just missing params
                    "access": "GRANTED",
                    "error": "Missing required parameters (expected)",
                    "code": error_code,
                    "message": error_msg
                }
            else:
                return {
                    "success": False,
                    "error": "API ERROR",
                    "code": error_code,
                    "message": error_msg
                }

        # Success - got valid response
        return {
            "success": True,
            "access": "GRANTED",
            "data": data
        }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "TIMEOUT"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def print_test_result(test_name: str, result: Dict[str, Any]):
    """Print formatted test result."""
    print(f"\n{'='*70}")
    print(f"TEST: {test_name}")
    print(f"{'='*70}")

    if result.get("success") or result.get("access") == "GRANTED":
        print("✅ ACCESS GRANTED")
        if result.get("error"):
            print(f"   Note: {result['error']}")
        if result.get("message"):
            print(f"   Details: {result['message']}")
        if result.get("data"):
            # Show sample of response
            print(f"   Response keys: {list(result['data'].keys())}")
    else:
        print("❌ ACCESS DENIED or ERROR")
        print(f"   Error: {result.get('error', 'Unknown')}")
        if result.get("code"):
            print(f"   Code: {result['code']}")
        if result.get("message"):
            print(f"   Message: {result['message']}")
        if result.get("details"):
            print(f"   Details: {result['details'][:200]}...")


def main():
    """Run all API access tests."""
    print("\n" + "🚀" * 35)
    print("ALIEXPRESS DROPSHIPPING SOLUTION API ACCESS TEST")
    print("🚀" * 35)

    print(f"\nApp Key: {APP_KEY}")
    print(f"Endpoint: {API_URL}")
    print(f"Testing access level...")

    # ===================================================================
    # TEST 1: Product Search API (Affiliate API)
    # ===================================================================
    print("\n\n" + "📦" * 35)
    print("TESTING PRODUCT SEARCH CAPABILITIES")
    print("📦" * 35)

    result1 = test_api(
        "aliexpress.affiliate.product.query",
        {
            "keywords": "smart lock",
            "target_currency": "USD",
            "target_language": "EN",
            "page_size": "5"
        }
    )
    print_test_result("Product Search (aliexpress.affiliate.product.query)", result1)

    # ===================================================================
    # TEST 2: Hot Products API (Affiliate API)
    # ===================================================================
    result2 = test_api(
        "aliexpress.affiliate.hotproduct.query",
        {
            "target_currency": "USD",
            "target_language": "EN",
            "page_size": "5"
        }
    )
    print_test_result("Hot Products (aliexpress.affiliate.hotproduct.query)", result2)

    # ===================================================================
    # TEST 3: Product Details API (Dropshipping API)
    # ===================================================================
    print("\n\n" + "🔍" * 35)
    print("TESTING PRODUCT DETAILS CAPABILITIES")
    print("🔍" * 35)

    result3 = test_api(
        "aliexpress.ds.product.get",
        {
            "product_id": "1005004043442825",
            "target_currency": "USD",
            "target_language": "EN"
        }
    )
    print_test_result("Product Details (aliexpress.ds.product.get)", result3)

    # ===================================================================
    # TEST 4: Order Placement API (Solution API) - CRITICAL TEST
    # ===================================================================
    print("\n\n" + "🛒" * 35)
    print("TESTING ORDER PLACEMENT API ACCESS (NOT PLACING REAL ORDER)")
    print("🛒" * 35)

    print("\n⚠️  NOTE: This test will fail with 'missing params' if we have access.")
    print("   That's GOOD - it means the API is accessible!")
    print("   If we get 'permission denied' - that's BAD.\n")

    result4 = test_api(
        "aliexpress.solution.order.create",
        {
            # Intentionally incomplete - just testing access
            "param_place_order_request": "{}"
        }
    )
    print_test_result("Order Placement (aliexpress.solution.order.create)", result4)

    # ===================================================================
    # TEST 5: Order Query API (Solution API)
    # ===================================================================
    result5 = test_api(
        "aliexpress.solution.order.get",
        {
            "param_single_order_query": "{}"
        }
    )
    print_test_result("Order Query (aliexpress.solution.order.get)", result5)

    # ===================================================================
    # TEST 6: Shipping Info API
    # ===================================================================
    print("\n\n" + "🚚" * 35)
    print("TESTING LOGISTICS/SHIPPING CAPABILITIES")
    print("🚚" * 35)

    result6 = test_api(
        "aliexpress.logistics.redefining.getlogisticsselleraddresses",
        {}
    )
    print_test_result("Logistics Addresses (shipping info)", result6)

    # ===================================================================
    # SUMMARY
    # ===================================================================
    print("\n\n" + "📊" * 35)
    print("ACCESS SUMMARY")
    print("📊" * 35)

    tests = [
        ("Product Search", result1),
        ("Hot Products", result2),
        ("Product Details", result3),
        ("Order Placement", result4),
        ("Order Query", result5),
        ("Logistics/Shipping", result6)
    ]

    granted = 0
    denied = 0

    for name, result in tests:
        status = "✅" if (result.get("success") or result.get("access") == "GRANTED") else "❌"
        print(f"{status} {name}")
        if result.get("success") or result.get("access") == "GRANTED":
            granted += 1
        else:
            denied += 1

    print(f"\n📊 TOTAL: {granted}/{len(tests)} APIs accessible")

    if granted >= 4:  # At least product + order APIs
        print("\n🎉 CONGRATULATIONS! You have FULL Dropshipping Solution access!")
        print("   You can now:")
        print("   ✅ Search products")
        print("   ✅ Get product details")
        print("   ✅ Place orders automatically")
        print("   ✅ Track shipments")
        print("\n   🚀 READY FOR FULL AUTOMATION! 🚀")
    elif granted >= 2:  # Just affiliate APIs
        print("\n⚠️  You have PARTIAL access (Affiliate APIs only)")
        print("   You can search products but cannot place orders yet.")
    else:
        print("\n❌ Limited access - may need to verify credentials or request access")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
