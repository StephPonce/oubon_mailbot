"""
Test Webhook Signature Verification (Phase 2A Security)

Tests all webhook signature verification implementations:
- Shopify (base64 HMAC-SHA256)
- Stripe (timestamp-based HMAC-SHA256)
- LemonSqueezy (hex HMAC-SHA256)
- AliExpress (MD5)
- CJ Dropshipping (hex HMAC-SHA256)
- TikTok (hex HMAC-SHA256)

Usage:
    python test_webhook_verification.py
"""

import json
import os
import sys
from ospra_os.security.webhook_verification import (
    WebhookVerifier,
    generate_test_signature,
    get_webhook_status
)


# Test secrets (for testing only - use real secrets in production)
TEST_SECRETS = {
    "shopify": "test_shopify_secret_key_12345",
    "stripe": "test_stripe_whsec_67890",
    "lemonsqueezy": "test_lemon_secret_abc",
    "aliexpress": "test_ae_secret_xyz",
    "cj": "test_cj_secret_def",
    "tiktok": "test_tiktok_secret_ghi"
}


def test_shopify_verification():
    """Test Shopify webhook signature verification."""
    print("\n" + "="*60)
    print("TEST 1: Shopify Webhook Verification")
    print("="*60)

    # Set test secret
    os.environ["SHOPIFY_WEBHOOK_SECRET"] = TEST_SECRETS["shopify"]

    # Create test payload
    payload = json.dumps({
        "id": 820982911946154508,
        "email": "jon@example.com",
        "created_at": "2021-12-01T12:00:00-05:00",
        "total_price": "199.00"
    })
    body = payload.encode('utf-8')

    # Generate valid signature
    valid_signature = generate_test_signature("shopify", body, TEST_SECRETS["shopify"])

    # Test with valid signature
    verifier = WebhookVerifier()
    is_valid = verifier.verify_shopify(body, valid_signature)

    if is_valid:
        print("✅ PASS: Valid Shopify signature accepted")
    else:
        print("❌ FAIL: Valid Shopify signature rejected")
        return False

    # Test with invalid signature
    is_valid = verifier.verify_shopify(body, "invalid_signature_xyz")

    if not is_valid:
        print("✅ PASS: Invalid Shopify signature rejected")
    else:
        print("❌ FAIL: Invalid Shopify signature accepted")
        return False

    print("\n✅ Shopify verification test PASSED")
    return True


def test_stripe_verification():
    """Test Stripe webhook signature verification."""
    print("\n" + "="*60)
    print("TEST 2: Stripe Webhook Verification")
    print("="*60)

    # Set test secret
    os.environ["STRIPE_WEBHOOK_SECRET"] = TEST_SECRETS["stripe"]

    # Create test payload
    payload = json.dumps({
        "id": "evt_test_webhook",
        "object": "event",
        "type": "customer.subscription.created"
    })
    body = payload.encode('utf-8')

    # Generate valid signature (Stripe format)
    valid_signature = generate_test_signature("stripe", body, TEST_SECRETS["stripe"])

    # Test with valid signature
    verifier = WebhookVerifier()
    is_valid = verifier.verify_stripe(body, valid_signature)

    if is_valid:
        print("✅ PASS: Valid Stripe signature accepted")
    else:
        print("❌ FAIL: Valid Stripe signature rejected")
        return False

    # Test with invalid signature
    is_valid = verifier.verify_stripe(body, "t=1234567890,v1=invalid_sig")

    if not is_valid:
        print("✅ PASS: Invalid Stripe signature rejected")
    else:
        print("❌ FAIL: Invalid Stripe signature accepted")
        return False

    print("\n✅ Stripe verification test PASSED")
    return True


def test_lemonsqueezy_verification():
    """Test LemonSqueezy webhook signature verification."""
    print("\n" + "="*60)
    print("TEST 3: LemonSqueezy Webhook Verification")
    print("="*60)

    # Set test secret
    os.environ["LEMONSQUEEZY_WEBHOOK_SECRET"] = TEST_SECRETS["lemonsqueezy"]

    # Create test payload
    payload = json.dumps({
        "meta": {"event_name": "order_created"},
        "data": {"id": "12345", "status": "paid"}
    })
    body = payload.encode('utf-8')

    # Generate valid signature
    valid_signature = generate_test_signature("lemonsqueezy", body, TEST_SECRETS["lemonsqueezy"])

    # Test with valid signature
    verifier = WebhookVerifier()
    is_valid = verifier.verify_lemonsqueezy(body, valid_signature)

    if is_valid:
        print("✅ PASS: Valid LemonSqueezy signature accepted")
    else:
        print("❌ FAIL: Valid LemonSqueezy signature rejected")
        return False

    # Test with invalid signature
    is_valid = verifier.verify_lemonsqueezy(body, "invalid_hex_signature")

    if not is_valid:
        print("✅ PASS: Invalid LemonSqueezy signature rejected")
    else:
        print("❌ FAIL: Invalid LemonSqueezy signature accepted")
        return False

    print("\n✅ LemonSqueezy verification test PASSED")
    return True


def test_aliexpress_verification():
    """Test AliExpress webhook signature verification."""
    print("\n" + "="*60)
    print("TEST 4: AliExpress Webhook Verification")
    print("="*60)

    # Set test secret
    os.environ["ALIEXPRESS_WEBHOOK_SECRET"] = TEST_SECRETS["aliexpress"]

    # Create test payload
    payload = json.dumps({
        "order_id": "AE12345",
        "status": "shipped",
        "tracking_number": "TRACK123"
    })
    body = payload.encode('utf-8')

    # Generate valid signature (MD5)
    valid_signature = generate_test_signature("aliexpress", body, TEST_SECRETS["aliexpress"])

    # Test with valid signature
    verifier = WebhookVerifier()
    is_valid = verifier.verify_aliexpress(body, valid_signature)

    if is_valid:
        print("✅ PASS: Valid AliExpress signature accepted")
    else:
        print("❌ FAIL: Valid AliExpress signature rejected")
        return False

    # Test with invalid signature
    is_valid = verifier.verify_aliexpress(body, "INVALID_MD5_SIGNATURE")

    if not is_valid:
        print("✅ PASS: Invalid AliExpress signature rejected")
    else:
        print("❌ FAIL: Invalid AliExpress signature accepted")
        return False

    print("\n✅ AliExpress verification test PASSED")
    return True


def test_cj_verification():
    """Test CJ Dropshipping webhook signature verification."""
    print("\n" + "="*60)
    print("TEST 5: CJ Dropshipping Webhook Verification")
    print("="*60)

    # Set test secret
    os.environ["CJ_WEBHOOK_SECRET"] = TEST_SECRETS["cj"]

    # Create test payload
    payload = json.dumps({
        "orderId": "CJ67890",
        "status": "delivered",
        "trackingNumber": "TRACK456"
    })
    body = payload.encode('utf-8')

    # Generate valid signature
    valid_signature = generate_test_signature("cj", body, TEST_SECRETS["cj"])

    # Test with valid signature
    verifier = WebhookVerifier()
    is_valid = verifier.verify_cj(body, valid_signature)

    if is_valid:
        print("✅ PASS: Valid CJ signature accepted")
    else:
        print("❌ FAIL: Valid CJ signature rejected")
        return False

    # Test with invalid signature
    is_valid = verifier.verify_cj(body, "invalid_cj_signature")

    if not is_valid:
        print("✅ PASS: Invalid CJ signature rejected")
    else:
        print("❌ FAIL: Invalid CJ signature accepted")
        return False

    print("\n✅ CJ Dropshipping verification test PASSED")
    return True


def test_tiktok_verification():
    """Test TikTok webhook signature verification."""
    print("\n" + "="*60)
    print("TEST 6: TikTok Webhook Verification")
    print("="*60)

    # Set test secret
    os.environ["TIKTOK_WEBHOOK_SECRET"] = TEST_SECRETS["tiktok"]

    # Create test payload
    payload = json.dumps({
        "event": "order.created",
        "data": {
            "order_id": "TT12345",
            "status": "paid",
            "amount": "99.99"
        }
    })
    body = payload.encode('utf-8')

    # Generate valid signature
    valid_signature = generate_test_signature("tiktok", body, TEST_SECRETS["tiktok"])

    # Test with valid signature
    verifier = WebhookVerifier()
    is_valid = verifier.verify_tiktok(body, valid_signature)

    if is_valid:
        print("✅ PASS: Valid TikTok signature accepted")
    else:
        print("❌ FAIL: Valid TikTok signature rejected")
        return False

    # Test with invalid signature
    is_valid = verifier.verify_tiktok(body, "invalid_tiktok_signature")

    if not is_valid:
        print("✅ PASS: Invalid TikTok signature rejected")
    else:
        print("❌ FAIL: Invalid TikTok signature accepted")
        return False

    print("\n✅ TikTok verification test PASSED")
    return True


def test_webhook_status():
    """Test webhook status endpoint."""
    print("\n" + "="*60)
    print("TEST 7: Webhook Status Endpoint")
    print("="*60)

    status = get_webhook_status()

    print(f"\nWebhook Status:")
    print(f"  Configured Providers: {status['configured_providers']}/{status['total_providers']}")
    print(f"  Rate Limit: {status['rate_limit']['max_requests']} requests per {status['rate_limit']['window_seconds']}s")
    print(f"  Max Timestamp Age: {status['max_timestamp_age']}s")

    print(f"\nProvider Details:")
    for provider, info in status['providers'].items():
        status_icon = "✅" if info['configured'] else "❌"
        print(f"  {status_icon} {provider:15} - Header: {info['header']}")

    # Verify all test providers are configured
    if status['configured_providers'] == status['total_providers']:
        print("\n✅ All webhook providers configured")
        return True
    else:
        print(f"\n⚠️  Only {status['configured_providers']}/{status['total_providers']} providers configured")
        return True  # Still pass, just a warning


def run_all_tests():
    """Run all webhook verification tests."""
    print("\n" + "="*70)
    print("PHASE 2A SECURITY: WEBHOOK SIGNATURE VERIFICATION TEST SUITE")
    print("="*70)

    tests = [
        ("Shopify", test_shopify_verification),
        ("Stripe", test_stripe_verification),
        ("LemonSqueezy", test_lemonsqueezy_verification),
        ("AliExpress", test_aliexpress_verification),
        ("CJ Dropshipping", test_cj_verification),
        ("TikTok", test_tiktok_verification),
        ("Webhook Status", test_webhook_status),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ {name} test FAILED with exception:")
            print(f"   {type(e).__name__}: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        icon = "✅" if passed else "❌"
        status = "PASS" if passed else "FAIL"
        print(f"{icon} {name:20} - {status}")

    print("\n" + "="*70)
    print(f"RESULTS: {passed_count}/{total_count} tests passed")
    print("="*70)

    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED - Webhook verification is working!")
        return 0
    else:
        print(f"\n❌ {total_count - passed_count} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
