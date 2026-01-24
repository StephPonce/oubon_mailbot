#!/usr/bin/env python3
"""
Shopify Webhook Verification Script
====================================
Tests that all webhook endpoints are responding correctly.

Usage:
    python scripts/verify_webhooks.py [--production]
    
    Default: Tests local server (localhost:8001)
    --production: Tests production server (ospra-intelligence-api.onrender.com)
"""

import httpx
import hmac
import hashlib
import json
import sys
import time
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

LOCAL_BASE = "http://localhost:8001"
PROD_BASE = "https://ospra-intelligence-api.onrender.com"

# Test webhook secret (for signature generation)
TEST_SECRET = "test_webhook_secret_for_verification"

# All 19 webhooks you set up manually
WEBHOOKS = [
    # Orders (6)
    ("orders/create", "orders/create"),
    ("orders/updated", "orders/updated"),
    ("orders/paid", "orders/paid"),
    ("orders/fulfilled", "orders/fulfilled"),
    ("orders/cancelled", "orders/cancelled"),
    ("orders/edited", "orders/edited"),
    # Refunds (1)
    ("refunds/create", "refunds/create"),
    # Products (3)
    ("products/create", "products/create"),
    ("products/update", "products/update"),
    ("products/delete", "products/delete"),
    # Inventory (2)
    ("inventory_levels/update", "inventory_levels/update"),
    ("inventory_items/update", "inventory_items/update"),
    # Customers (3)
    ("customers/create", "customers/create"),
    ("customers/update", "customers/update"),
    ("customers/delete", "customers/delete"),
    # Checkouts (2)
    ("checkouts/create", "checkouts/create"),
    ("checkouts/update", "checkouts/update"),
    # Fulfillments (2)
    ("fulfillments/create", "fulfillments/create"),
    ("fulfillments/update", "fulfillments/update"),
]

# GDPR Webhooks (configured in Partner Dashboard, not Shopify Admin)
GDPR_WEBHOOKS = [
    ("customers/data_request", "gdpr/customers/data_request"),
    ("customers/redact", "gdpr/customers/redact"),
    ("shop/redact", "gdpr/shop/redact"),
]

# Sample payloads for different webhook types
SAMPLE_PAYLOADS = {
    "orders/create": {
        "id": 123456789,
        "name": "#1001",
        "email": "test@example.com",
        "created_at": "2026-01-23T00:00:00-06:00",
        "total_price": "99.99",
        "currency": "USD",
        "line_items": [
            {"title": "Test Product", "quantity": 1, "price": "99.99"}
        ]
    },
    "orders/paid": {
        "id": 123456789,
        "name": "#1001",
        "financial_status": "paid",
        "total_price": "99.99"
    },
    "products/create": {
        "id": 987654321,
        "title": "Test Product",
        "vendor": "Test Vendor",
        "product_type": "Test Type",
        "variants": [{"price": "49.99", "sku": "TEST-001"}]
    },
    "customers/create": {
        "id": 111222333,
        "email": "customer@example.com",
        "first_name": "Test",
        "last_name": "Customer"
    },
    "checkouts/create": {
        "id": 444555666,
        "token": "test_checkout_token",
        "email": "checkout@example.com",
        "total_price": "149.99"
    },
    "inventory_levels/update": {
        "inventory_item_id": 777888999,
        "location_id": 123123123,
        "available": 50
    },
    "refunds/create": {
        "id": 999888777,
        "order_id": 123456789,
        "created_at": "2026-01-23T00:00:00-06:00"
    },
    "fulfillments/create": {
        "id": 555444333,
        "order_id": 123456789,
        "status": "success",
        "tracking_number": "1Z999AA10123456784"
    }
}


def get_sample_payload(topic: str) -> dict:
    """Get appropriate sample payload for webhook topic."""
    # Check for exact match
    if topic in SAMPLE_PAYLOADS:
        return SAMPLE_PAYLOADS[topic]
    
    # Check for category match
    category = topic.split("/")[0]
    for key, payload in SAMPLE_PAYLOADS.items():
        if key.startswith(category):
            return payload
    
    # Default minimal payload
    return {"id": 123456789, "test": True}


def generate_signature(payload: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature like Shopify does."""
    digest = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).digest()
    import base64
    return base64.b64encode(digest).decode('utf-8')


def test_webhook(base_url: str, topic: str, path: str) -> dict:
    """Test a single webhook endpoint."""
    url = f"{base_url}/webhooks/shopify/{path}"
    payload = get_sample_payload(topic)
    payload_bytes = json.dumps(payload).encode('utf-8')
    
    # Generate signature
    signature = generate_signature(payload_bytes, TEST_SECRET)
    
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Topic": topic,
        "X-Shopify-Shop-Domain": "test-store.myshopify.com",
        "X-Shopify-Hmac-Sha256": signature,
        "X-Shopify-Webhook-Id": f"test-{int(time.time())}",
        "X-Shopify-API-Version": "2024-01"
    }
    
    result = {
        "topic": topic,
        "url": url,
        "status": None,
        "success": False,
        "message": "",
        "response_time_ms": 0
    }
    
    try:
        start = time.time()
        response = httpx.post(url, content=payload_bytes, headers=headers, timeout=10.0)
        result["response_time_ms"] = int((time.time() - start) * 1000)
        result["status"] = response.status_code
        
        # 200, 202 = success (processed or accepted)
        # 401 = signature validation working (expected with test secret)
        # 404 = endpoint not found
        # 500+ = server error
        
        if response.status_code in [200, 202]:
            result["success"] = True
            result["message"] = "✅ Endpoint responding & accepting webhooks"
        elif response.status_code == 401:
            result["success"] = True  # This is actually GOOD - means signature validation works
            result["message"] = "✅ Endpoint live, signature validation working (expected failure with test secret)"
        elif response.status_code == 404:
            result["success"] = False
            result["message"] = "❌ Endpoint not found - route not registered"
        elif response.status_code >= 500:
            result["success"] = False
            result["message"] = f"❌ Server error: {response.text[:100]}"
        else:
            result["message"] = f"⚠️ Unexpected status: {response.status_code}"
            
    except httpx.ConnectError:
        result["message"] = "❌ Connection refused - server not running?"
    except httpx.TimeoutException:
        result["message"] = "❌ Timeout - server not responding"
    except Exception as e:
        result["message"] = f"❌ Error: {str(e)}"
    
    return result


def test_health(base_url: str) -> bool:
    """Check if server is up."""
    try:
        response = httpx.get(f"{base_url}/health", timeout=10.0)
        return response.status_code == 200
    except:
        return False


def main():
    # Determine which server to test
    use_production = "--production" in sys.argv or "-p" in sys.argv
    include_gdpr = "--gdpr" in sys.argv or "-g" in sys.argv
    base_url = PROD_BASE if use_production else LOCAL_BASE
    
    print("=" * 70)
    print("🔍 SHOPIFY WEBHOOK VERIFICATION")
    print("=" * 70)
    print(f"Target: {base_url}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if include_gdpr:
        print("Mode: Including GDPR endpoints")
    print("=" * 70)
    print()
    
    # Health check
    print("📡 Checking server health...")
    if test_health(base_url):
        print("   ✅ Server is UP\n")
    else:
        print("   ❌ Server is DOWN or unreachable")
        if not use_production:
            print("   💡 Start local server: uv run uvicorn ospra_os.main:app --reload --port 8001")
        print()
        # Continue anyway to show which endpoints would fail
    
    # Combine webhook lists
    webhooks_to_test = WEBHOOKS.copy()
    if include_gdpr:
        webhooks_to_test.extend(GDPR_WEBHOOKS)
    
    # Test each webhook
    print("🔔 Testing webhook endpoints...\n")
    
    results = []
    passed = 0
    failed = 0
    
    for topic, path in webhooks_to_test:
        result = test_webhook(base_url, topic, path)
        results.append(result)
        
        status_icon = "✅" if result["success"] else "❌"
        print(f"   {status_icon} {topic}")
        print(f"      Status: {result['status'] or 'N/A'} | {result['response_time_ms']}ms")
        print(f"      {result['message']}")
        print()
        
        if result["success"]:
            passed += 1
        else:
            failed += 1
    
    # Summary
    print("=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    print(f"   Total:  {len(webhooks_to_test)}")
    print(f"   Passed: {passed} ✅")
    print(f"   Failed: {failed} ❌")
    print()
    
    if failed == 0:
        print("🎉 All webhook endpoints are responding correctly!")
    else:
        print("⚠️  Some endpoints need attention. Check the errors above.")
    
    print()
    print("=" * 70)
    print("📝 NEXT STEPS")
    print("=" * 70)
    
    if failed > 0:
        print("1. Ensure the server is running")
        print("2. Check that webhook routes are registered in main.py")
        print("3. Review server logs for errors")
    else:
        print("1. Test with real Shopify webhooks using 'Send test notification'")
        print("2. In Shopify Admin → Settings → Notifications → Webhooks")
        print("3. Click the webhook → 'Send test notification'")
        if not include_gdpr:
            print("4. Run with --gdpr flag to also test GDPR endpoints")
    
    print()
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
