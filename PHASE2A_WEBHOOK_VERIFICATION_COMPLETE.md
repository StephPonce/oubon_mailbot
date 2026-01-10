# Phase 2A Security: Webhook Signature Verification - COMPLETE ✅

**Date**: January 10, 2026
**Status**: 7/7 Tests Passing (100%) - Production Ready
**Component**: Webhook Signature Verification

---

## 🎉 Executive Summary

Webhook signature verification is **COMPLETE** with comprehensive support for 6 providers. All cryptographic implementations tested and verified working correctly with 100% test pass rate.

**Providers Supported**:
- ✅ Shopify (Base64 HMAC-SHA256)
- ✅ Stripe (Timestamp-based HMAC-SHA256 with replay protection)
- ✅ LemonSqueezy (Hex HMAC-SHA256)
- ✅ AliExpress (MD5 with secret sandwich)
- ✅ CJ Dropshipping (Hex HMAC-SHA256)
- ✅ TikTok (Hex HMAC-SHA256) - Added in this session

---

## Overview

Webhook signature verification ensures that incoming webhook requests are genuinely from the claimed provider and haven't been tampered with. This prevents webhook spoofing attacks, replay attacks, and unauthorized API access.

### Security Features Implemented

1. **HMAC-SHA256 Verification** - Cryptographic signature validation for most providers
2. **MD5 Verification** - AliExpress-specific signature format
3. **Replay Attack Prevention** - Stripe's timestamp validation (5-minute window)
4. **Timing-Safe Comparison** - Using `hmac.compare_digest()` to prevent timing attacks
5. **Rate Limiting** - Webhook-specific rate limiter (100 requests/60 seconds)
6. **Security Logging** - Integration with existing security event logging
7. **FastAPI Dependencies** - Automatic verification in route handlers

---

## Implementation Details

### File Structure

```
ospra_os/
├── security/
│   └── webhook_verification.py    # Core verification module (588 lines)
├── core/
│   └── settings.py                # Webhook secret configuration
└── main.py                        # FastAPI app integration (future)

test_webhook_verification.py       # Test suite (379 lines)
PHASE2A_WEBHOOK_VERIFICATION_COMPLETE.md  # This document
```

### Core Module: `ospra_os/security/webhook_verification.py`

**Classes**:
- `WebhookConfig` - Configuration constants (signature headers, env vars, rate limits)
- `WebhookVerifier` - Main verification class with provider-specific methods
- `WebhookRateLimiter` - Rate limiting for webhook endpoints

**Key Methods**:
```python
# Generic verification
verifier.verify(provider, body, signature, timestamp)

# Provider-specific verification
verifier.verify_shopify(body, signature)
verifier.verify_stripe(body, signature, timestamp)
verifier.verify_lemonsqueezy(body, signature)
verifier.verify_aliexpress(body, signature)
verifier.verify_cj(body, signature)
verifier.verify_tiktok(body, signature)  # NEW

# Status check
verifier.is_configured(provider)
```

**FastAPI Dependencies**:
```python
from ospra_os.security.webhook_verification import (
    verify_shopify_webhook,
    verify_stripe_webhook,
    verify_lemonsqueezy_webhook,
    webhook_rate_limit
)

# Usage in routes
@router.post("/webhooks/shopify/orders")
async def handle_shopify_order(
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook)
):
    data = json.loads(body)
    # Process webhook...
```

---

## Configuration Guide

### Step 1: Obtain Webhook Secrets

Each provider has a different process for obtaining webhook secrets:

#### Shopify
1. Go to **Settings → Notifications** in Shopify Admin
2. Scroll to **Webhooks** section
3. Create a webhook subscription
4. Copy the **Webhook Signing Secret** (starts with `shp_whsec_`)

**Example**: `shp_whsec_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

#### Stripe
1. Go to **Developers → Webhooks** in Stripe Dashboard
2. Click **Add endpoint**
3. Enter your webhook URL
4. Copy the **Signing secret** (starts with `whsec_`)

**Example**: `whsec_1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z`

#### LemonSqueezy
1. Go to **Settings → Webhooks** in LemonSqueezy Dashboard
2. Click **Create webhook**
3. Copy the **Signing secret**

**Example**: `lemon_secret_abc123def456ghi789`

#### AliExpress
1. Go to **AliExpress Dropshipping Center** Developer Portal
2. Navigate to **Webhooks** or **App Settings**
3. Copy your **App Secret** (used for webhook signature)

**Example**: `ae_app_secret_xyz789abc123`

#### CJ Dropshipping
1. Log in to **CJ Dropshipping Merchant Portal**
2. Go to **API Management → Webhooks**
3. Copy the **Webhook Secret Key**

**Example**: `cj_webhook_secret_def456ghi789`

#### TikTok
1. Go to **TikTok for Business → Developer Portal**
2. Navigate to **App Settings → Webhooks**
3. Copy the **Webhook Secret** (used for X-TikTok-Signature header)

**Example**: `tiktok_secret_ghi789jkl012mno345`

---

### Step 2: Configure Environment Variables

Add webhook secrets to your `.env` file:

```bash
# Webhook Security Secrets (Phase 2A)
SHOPIFY_WEBHOOK_SECRET=shp_whsec_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
STRIPE_WEBHOOK_SECRET=whsec_1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z
LEMONSQUEEZY_WEBHOOK_SECRET=lemon_secret_abc123def456ghi789
ALIEXPRESS_WEBHOOK_SECRET=ae_app_secret_xyz789abc123
CJ_WEBHOOK_SECRET=cj_webhook_secret_def456ghi789
TIKTOK_WEBHOOK_SECRET=tiktok_secret_ghi789jkl012mno345
```

**Security Notes**:
- ✅ Never commit `.env` files to version control
- ✅ Use different secrets for development/staging/production
- ✅ Rotate secrets periodically (every 90 days recommended)
- ✅ Store production secrets in secure vault (AWS Secrets Manager, HashiCorp Vault)

---

### Step 3: Verify Configuration

Run the configuration status check:

```python
from ospra_os.security.webhook_verification import get_webhook_status

status = get_webhook_status()
print(f"Configured: {status['configured_providers']}/{status['total_providers']}")

for provider, info in status['providers'].items():
    if info['configured']:
        print(f"✅ {provider} - Ready")
    else:
        print(f"❌ {provider} - Missing secret: {info['env_var']}")
```

**Expected Output**:
```
Configured: 6/6
✅ shopify - Ready
✅ stripe - Ready
✅ lemonsqueezy - Ready
✅ aliexpress - Ready
✅ cj - Ready
✅ tiktok - Ready
```

---

## Testing

### Run Test Suite

```bash
# Start OspraOS
uv run uvicorn ospra_os.main:app --reload --port 8001

# Run webhook verification tests
uv run python test_webhook_verification.py
```

**Expected Output**:
```
======================================================================
PHASE 2A SECURITY: WEBHOOK SIGNATURE VERIFICATION TEST SUITE
======================================================================

============================================================
TEST 1: Shopify Webhook Verification
============================================================
✅ PASS: Valid Shopify signature accepted
✅ PASS: Invalid Shopify signature rejected

✅ Shopify verification test PASSED

[... similar output for all providers ...]

======================================================================
TEST SUMMARY
======================================================================
✅ Shopify              - PASS
✅ Stripe               - PASS
✅ LemonSqueezy         - PASS
✅ AliExpress           - PASS
✅ CJ Dropshipping      - PASS
✅ TikTok               - PASS
✅ Webhook Status       - PASS

======================================================================
RESULTS: 7/7 tests passed
======================================================================

🎉 ALL TESTS PASSED - Webhook verification is working!
```

### Manual Testing with cURL

#### Test Shopify Webhook

```bash
# Generate test signature (use Python)
python3 -c "
import hmac
import hashlib
import base64
import json

body = json.dumps({'id': 820982911946154508, 'email': 'test@example.com'})
secret = 'your_shopify_secret'
sig = base64.b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).decode()
print(f'Signature: {sig}')
print(f'Body: {body}')
"

# Send webhook request
curl -X POST http://localhost:8001/webhooks/shopify/orders \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Hmac-SHA256: YOUR_SIGNATURE_HERE" \
  -d '{"id": 820982911946154508, "email": "test@example.com"}'
```

#### Test Stripe Webhook

```bash
# Stripe provides a CLI tool for testing
stripe listen --forward-to localhost:8001/webhooks/stripe

# Trigger test event
stripe trigger payment_intent.succeeded
```

---

## Integration with FastAPI Routes

### Example: Shopify Order Webhook

```python
from fastapi import APIRouter, Depends
from ospra_os.security.webhook_verification import (
    verify_shopify_webhook,
    webhook_rate_limit
)
import json

router = APIRouter(prefix="/webhooks/shopify", tags=["Webhooks"])

@router.post("/orders")
async def handle_shopify_order(
    _: None = Depends(webhook_rate_limit),      # Apply rate limiting
    body: bytes = Depends(verify_shopify_webhook)  # Verify signature
):
    """
    Handle Shopify order webhook.

    Signature verification happens automatically via dependency.
    If verification fails, HTTPException 401 is raised.
    """
    data = json.loads(body)

    order_id = data.get('id')
    email = data.get('email')
    total = data.get('total_price')

    # Process order...
    print(f"✅ Order {order_id} received: {email} - ${total}")

    return {"status": "success", "order_id": order_id}
```

### Example: Stripe Payment Webhook

```python
from fastapi import APIRouter, Depends
from ospra_os.security.webhook_verification import verify_stripe_webhook
import json

router = APIRouter(prefix="/webhooks/stripe", tags=["Webhooks"])

@router.post("/payments")
async def handle_stripe_payment(
    body: bytes = Depends(verify_stripe_webhook)
):
    """
    Handle Stripe payment webhook.

    Includes automatic timestamp validation (replay protection).
    """
    event = json.loads(body)

    event_type = event.get('type')

    if event_type == 'customer.subscription.created':
        # Handle new subscription
        customer_id = event['data']['object']['customer']
        print(f"✅ New subscription: {customer_id}")

    elif event_type == 'invoice.payment_succeeded':
        # Handle successful payment
        invoice_id = event['data']['object']['id']
        print(f"✅ Payment succeeded: {invoice_id}")

    return {"status": "success"}
```

### Example: TikTok Webhook

```python
from fastapi import APIRouter, Depends, Header
from ospra_os.security.webhook_verification import WebhookVerifier, get_webhook_verifier
import json

router = APIRouter(prefix="/webhooks/tiktok", tags=["Webhooks"])

@router.post("/orders")
async def handle_tiktok_order(
    request: Request,
    x_tiktok_signature: str = Header(..., alias="X-TikTok-Signature")
):
    """
    Handle TikTok order webhook.

    Manual verification example (for custom logic).
    """
    body = await request.body()
    verifier = get_webhook_verifier()

    if not verifier.verify_tiktok(body, x_tiktok_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = json.loads(body)

    order_id = data['data']['order_id']
    status = data['data']['status']

    print(f"✅ TikTok order {order_id}: {status}")

    return {"status": "success", "order_id": order_id}
```

---

## Provider-Specific Implementation Details

### Shopify
**Signature Method**: HMAC-SHA256 with Base64 encoding
**Header**: `X-Shopify-Hmac-SHA256`
**Computation**: `base64(HMAC-SHA256(secret, body))`

```python
computed = hmac.new(secret.encode(), body, hashlib.sha256).digest()
signature = base64.b64encode(computed).decode()
```

### Stripe
**Signature Method**: HMAC-SHA256 with timestamp
**Header**: `Stripe-Signature`
**Format**: `t=timestamp,v1=signature`
**Computation**: `HMAC-SHA256(secret, timestamp.body)`
**Replay Protection**: Rejects requests older than 5 minutes

```python
timestamp = int(time.time())
signed_payload = f"{timestamp}.{body.decode()}"
signature = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
header = f"t={timestamp},v1={signature}"
```

### LemonSqueezy
**Signature Method**: HMAC-SHA256 with hex encoding
**Header**: `X-Signature`
**Computation**: `hex(HMAC-SHA256(secret, body))`

```python
signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
```

### AliExpress
**Signature Method**: MD5 with secret sandwich
**Header**: `X-AE-Signature`
**Computation**: `MD5(secret + body + secret).upper()`

```python
signature = hashlib.md5(
    (secret + body.decode() + secret).encode()
).hexdigest().upper()
```

### CJ Dropshipping
**Signature Method**: HMAC-SHA256 with hex encoding
**Header**: `X-CJ-Signature`
**Computation**: `hex(HMAC-SHA256(secret, body))`

```python
signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
```

### TikTok
**Signature Method**: HMAC-SHA256 with hex encoding
**Header**: `X-TikTok-Signature`
**Computation**: `hex(HMAC-SHA256(secret, body))`

```python
signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
```

---

## Security Best Practices

### 1. Secret Management

✅ **DO**:
- Store secrets in environment variables
- Use secret management services (AWS Secrets Manager, HashiCorp Vault) in production
- Rotate secrets every 90 days
- Use different secrets for each environment (dev/staging/prod)
- Log secret rotation events

❌ **DON'T**:
- Hardcode secrets in code
- Commit secrets to version control
- Share secrets via email or Slack
- Reuse secrets across providers
- Use weak or guessable secrets

### 2. Request Validation

✅ **DO**:
- Always verify webhook signatures
- Implement replay attack prevention (timestamp validation)
- Use timing-safe comparison (`hmac.compare_digest()`)
- Rate limit webhook endpoints
- Log failed verification attempts

❌ **DON'T**:
- Trust webhook data without verification
- Skip signature validation in "trusted" networks
- Use string equality for signature comparison
- Allow unlimited webhook requests
- Ignore security event logs

### 3. Error Handling

✅ **DO**:
- Return generic 401 errors for verification failures
- Log detailed error information internally
- Monitor failed verification patterns
- Alert on repeated failures from same IP

❌ **DON'T**:
- Expose secret information in error messages
- Return different errors for different failure types (timing attack risk)
- Ignore verification failures
- Process webhooks with invalid signatures

### 4. Monitoring

Monitor these metrics in production:

- **Verification Success Rate**: Should be >99%
- **Failed Verifications by Provider**: Detect configuration issues
- **Failed Verifications by IP**: Detect attacks
- **Rate Limit Violations**: Detect flooding attacks
- **Webhook Processing Time**: Performance monitoring

```bash
# Monitor security log for webhook failures
tail -f logs/security.log | grep "WEBHOOK"

# Count verification failures
grep "signature mismatch" logs/security.log | wc -l

# Find IPs with repeated failures
grep "Invalid.*webhook" logs/security.log | awk '{print $X}' | sort | uniq -c
```

---

## Production Deployment Checklist

### Pre-Deployment

- [ ] Configure webhook secrets for all providers in production environment
- [ ] Verify `.env` file contains all required `*_WEBHOOK_SECRET` variables
- [ ] Test webhook verification with production secrets (use test mode where available)
- [ ] Confirm webhook URLs registered with each provider
- [ ] Enable HTTPS for all webhook endpoints
- [ ] Set up secret rotation schedule (90 days)

### Deployment

- [ ] Deploy application with webhook verification enabled
- [ ] Register webhook endpoints with each provider
- [ ] Verify webhooks receive and process test events
- [ ] Check `logs/security.log` for verification success/failure
- [ ] Monitor rate limiting behavior under load

### Post-Deployment

- [ ] Monitor webhook success rates (target: >99%)
- [ ] Set up alerts for verification failures
- [ ] Document webhook endpoints and secrets in runbook
- [ ] Schedule secret rotation reminders
- [ ] Review security logs weekly for patterns

---

## Troubleshooting

### Issue: "No secret configured for provider"

**Cause**: Environment variable not set or incorrect name

**Solution**:
```bash
# Check current environment
python3 -c "
from ospra_os.security.webhook_verification import get_webhook_status
import json
status = get_webhook_status()
print(json.dumps(status, indent=2))
"

# Set missing secret
export SHOPIFY_WEBHOOK_SECRET="your_secret_here"

# Restart application
```

### Issue: "Invalid webhook signature"

**Cause**: Secret mismatch, encoding issue, or body modification

**Solution**:
1. Verify secret matches provider dashboard exactly (no extra spaces)
2. Ensure request body is not modified before verification
3. Check Content-Type header matches what provider sends
4. Verify webhook URL registered with provider is correct
5. Test with provider's webhook testing tool

```python
# Debug signature verification
from ospra_os.security.webhook_verification import WebhookVerifier, generate_test_signature
import json

body = json.dumps({"test": "data"}).encode()
secret = "your_secret"

# Generate expected signature
expected_sig = generate_test_signature("shopify", body, secret)
print(f"Expected: {expected_sig}")

# Compare with actual signature from webhook
actual_sig = "signature_from_webhook_header"
print(f"Actual: {actual_sig}")
print(f"Match: {expected_sig == actual_sig}")
```

### Issue: "Stripe webhook timestamp too old"

**Cause**: Replay attack protection - webhook older than 5 minutes

**Solution**:
- Ensure server clock is synchronized (use NTP)
- Check network latency between Stripe and your server
- Verify webhook processing isn't delayed in queue

```bash
# Check server time
date -u

# Sync with NTP (if needed)
sudo ntpdate -s time.nist.gov
```

### Issue: Rate limit exceeded

**Cause**: Too many webhook requests from same IP

**Solution**:
```python
# Check rate limiter status
from ospra_os.security.webhook_verification import _webhook_rate_limiter

remaining = _webhook_rate_limiter.get_remaining("client_ip")
print(f"Remaining requests: {remaining}")

# Increase limits if legitimate (modify webhook_verification.py)
_webhook_rate_limiter = WebhookRateLimiter(
    max_requests=200,  # Increase from 100
    window_seconds=60
)
```

---

## Testing Summary

**Test Suite**: `test_webhook_verification.py`
**Total Tests**: 7
**Status**: ✅ 7/7 PASSING (100%)

| Test | Provider | Status |
|------|----------|--------|
| 1 | Shopify | ✅ PASS |
| 2 | Stripe | ✅ PASS |
| 3 | LemonSqueezy | ✅ PASS |
| 4 | AliExpress | ✅ PASS |
| 5 | CJ Dropshipping | ✅ PASS |
| 6 | TikTok | ✅ PASS |
| 7 | Webhook Status | ✅ PASS |

**Test Coverage**:
- ✅ Valid signature acceptance
- ✅ Invalid signature rejection
- ✅ Provider-specific encoding (base64, hex, MD5)
- ✅ Timestamp validation (Stripe)
- ✅ Configuration status endpoint
- ✅ Error handling and logging

---

## Files Modified/Created

### Created:
- `test_webhook_verification.py` (379 lines) - Comprehensive test suite
- `PHASE2A_WEBHOOK_VERIFICATION_COMPLETE.md` (this file) - Complete documentation

### Modified:
- `ospra_os/security/webhook_verification.py`:
  - Added TikTok to `SIGNATURE_HEADERS` (line 50)
  - Added TikTok to `SECRET_ENV_VARS` (line 63)
  - Added TikTok routing in `verify()` (lines 131-132)
  - Implemented `verify_tiktok()` method (lines 303-330)
  - Fixed `generate_test_signature()` for TikTok (line 544)

- `ospra_os/core/settings.py`:
  - Added 6 webhook secret fields (lines 131-137)

---

## Next Steps

Phase 2A Security Components Remaining:

### 1. Redis-Backed Rate Limiting (4-6 hours)
- Replace in-memory rate limiter with Redis
- Support distributed systems
- Add rate limit analytics
- Implement per-endpoint and per-tier limits

### 2. JWT Token Refresh (8-10 hours)
- Implement refresh token rotation
- Short-lived access tokens (15 minutes)
- Long-lived refresh tokens (30 days)
- Secure token storage and revocation

### 3. Database Audit Trail (6-8 hours)
- PostgreSQL-backed security event logging
- Queryable audit trail for compliance
- Event retention policies
- Forensic analysis capabilities

---

## Status

**Phase 2A - Webhook Verification**: ✅ **COMPLETE**
**Testing**: ✅ **7/7 PASSING (100%)**
**Documentation**: ✅ **COMPLETE**
**Production Ready**: ✅ **YES** (pending secret configuration)

---

**Implementation Date**: January 10, 2026
**Tested**: ✅ All providers verified with mock payloads
**Production Deployment**: Pending webhook secret configuration

🎉 **Webhook signature verification is complete and ready for production!**
