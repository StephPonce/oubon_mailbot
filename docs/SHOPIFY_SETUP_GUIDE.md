# Shopify Integration Complete Setup Guide

## Overview

This guide covers three essential setups:
1. **Auto-Fulfillment Flow** - Automatic order processing
2. **Shopify Partner App** - SaaS multi-store OAuth
3. **GDPR Webhooks** - Required for app store compliance

---

## 1️⃣ Auto-Fulfillment Flow

### What It Does

When a customer pays for an order on your Shopify store:
1. Shopify sends `orders/paid` webhook to Ospra
2. Ospra looks up the product's supplier (CJ/AliExpress)
3. Ospra automatically places the order with the supplier
4. Supplier ships and provides tracking
5. Ospra updates Shopify with tracking info
6. Customer receives shipping notification

### Prerequisites

You need at least ONE supplier configured:

#### Option A: CJ Dropshipping (Recommended)
```env
# Add to your .env file
CJ_API_KEY=your_cj_api_key
CJ_EMAIL=your_cj_account_email
```

Get these from: https://cjdropshipping.com → My CJ → API

#### Option B: AliExpress Dropshipping API
```env
# Already configured in your system (token valid until Dec 31, 2025)
ALIEXPRESS_DROPSHIP_APP_KEY=520918
ALIEXPRESS_DROPSHIP_ACCESS_TOKEN=your_access_token
```

### Enable Auto-Fulfillment

**Step 1: Check Current Status**
```bash
curl https://ospra-intelligence-api.onrender.com/api/fulfillment/status
```

**Step 2: Enable Auto-Fulfillment**
```bash
curl -X POST https://ospra-intelligence-api.onrender.com/api/fulfillment/settings \
  -H "Content-Type: application/json" \
  -d '{
    "auto_fulfill_enabled": true,
    "preferred_supplier": "cj_dropshipping",
    "auto_notify_customer": true,
    "fallback_to_manual": true
  }'
```

**Step 3: Test with a Real Order**

1. Go to your Shopify store
2. Place a test order (use Shopify's Bogus Gateway for free testing)
3. Mark as paid
4. Watch the logs in Render Dashboard

### Test Order Flow

```
Customer Order → Shopify → Webhook → Ospra → Supplier → Tracking → Shopify → Customer
```

**Check the Render Logs for:**
```
💰 [orders/paid] Order #1001 PAID - $49.99
📊 Learning: Smart LED Strip (smart_home) - $49.99
✅ Fulfillment: 1/1 items
```

### Manual Fulfillment Queue

If auto-fulfillment fails or is disabled, orders go to manual queue:
```bash
# View pending orders
curl https://ospra-intelligence-api.onrender.com/api/fulfillment/queue

# Add tracking manually
curl -X POST https://ospra-intelligence-api.onrender.com/api/fulfillment/add-tracking \
  -H "Content-Type: application/json" \
  -d '{
    "shopify_order_id": "5551234567890",
    "tracking_number": "1Z999AA10123456784",
    "carrier": "UPS"
  }'
```

---

## 2️⃣ Shopify Partner App (SaaS Multi-Store)

This enables other merchants to connect their stores via OAuth.

### Step 1: Create Shopify Partner Account

1. Go to https://partners.shopify.com
2. Sign up (free)
3. Complete account setup

### Step 2: Create Your App

1. In Partner Dashboard → **Apps** → **Create app**
2. Choose **Create app manually**
3. Fill in:
   - **App name**: Ospra Intelligence
   - **App URL**: `https://ospra-intelligence-api.onrender.com`

### Step 3: Configure App URLs

In your app settings → **App setup**:

**App URL:**
```
https://ospra-intelligence-api.onrender.com
```

**Allowed redirection URL(s):**
```
https://ospra-intelligence-api.onrender.com/api/shopify/oauth/callback
https://ospra-intelligence-api.onrender.com/oauth/shopify/callback
```

### Step 4: Get API Credentials

1. Go to **API credentials** tab
2. Copy:
   - **Client ID** (API key)
   - **Client secret**

### Step 5: Add to Render Environment

In Render Dashboard → Environment:

```env
SHOPIFY_CLIENT_ID=your_client_id_here
SHOPIFY_CLIENT_SECRET=your_client_secret_here
SHOPIFY_APP_URL=https://ospra-intelligence-api.onrender.com
```

### Step 6: Configure Scopes

Your app already requests these scopes (defined in `shopify_oauth_routes.py`):
- `read_products`, `write_products`
- `read_orders`, `write_orders`
- `read_customers`
- `read_inventory`, `write_inventory`
- `read_fulfillments`, `write_fulfillments`
- `read_analytics`

### Step 7: Test OAuth Flow

1. Visit: `https://ospra-intelligence-api.onrender.com/api/shopify/oauth/install?shop=your-store.myshopify.com`
2. Should redirect to Shopify for permission
3. After approval, redirects back with access token

---

## 3️⃣ GDPR Webhooks (App Store Requirement)

Shopify requires these 3 webhooks for ALL public apps.

### Your GDPR Endpoints (Already Implemented)

| Webhook | URL | Purpose |
|---------|-----|---------|
| Customer Data Request | `/webhooks/shopify/gdpr/customers/data_request` | Export customer data |
| Customer Redact | `/webhooks/shopify/gdpr/customers/redact` | Delete customer data |
| Shop Redact | `/webhooks/shopify/gdpr/shop/redact` | Delete ALL store data |

### Configure in Partner Dashboard

1. Go to Partner Dashboard → Your App → **Configuration**
2. Scroll to **Compliance webhooks**
3. Enter these URLs:

**Customer data request endpoint:**
```
https://ospra-intelligence-api.onrender.com/webhooks/shopify/gdpr/customers/data_request
```

**Customer data erasure endpoint:**
```
https://ospra-intelligence-api.onrender.com/webhooks/shopify/gdpr/customers/redact
```

**Shop data erasure endpoint:**
```
https://ospra-intelligence-api.onrender.com/webhooks/shopify/gdpr/shop/redact
```

4. Click **Save**

### Verification

Shopify will send test webhooks when you save. Check Render logs for:
```
📋 [GDPR] Customer data request from test-store.myshopify.com
🗑️ [GDPR] Customer redact request from test-store.myshopify.com
🗑️ [GDPR] Shop redact request - DELETE ALL DATA for test-store.myshopify.com
```

---

## Quick Reference

### Environment Variables Needed

```env
# Shopify Store (Your Own Store - Direct API)
SHOPIFY_STORE_NAME=oubon-shop
SHOPIFY_ACCESS_TOKEN=shpat_xxxxx

# Shopify App (SaaS - OAuth for Other Stores)
SHOPIFY_CLIENT_ID=your_partner_app_client_id
SHOPIFY_CLIENT_SECRET=your_partner_app_client_secret
SHOPIFY_APP_URL=https://ospra-intelligence-api.onrender.com

# Webhook Security
SHOPIFY_WEBHOOK_SECRET=your_webhook_signing_secret

# Fulfillment Suppliers
CJ_API_KEY=your_cj_api_key
CJ_EMAIL=your_cj_email
```

### API Endpoints Summary

| Endpoint | Purpose |
|----------|---------|
| `GET /api/fulfillment/status` | Check fulfillment system status |
| `GET /api/fulfillment/queue` | View pending orders |
| `POST /api/fulfillment/settings` | Update settings |
| `GET /api/shopify/oauth/install` | Start OAuth flow |
| `GET /api/shopify/oauth/callback` | OAuth callback |
| `GET /webhooks/shopify/status` | Webhook system status |

---

## Troubleshooting

### Webhook Not Received
1. Check Shopify Admin → Settings → Notifications → Webhooks
2. Verify URL is correct
3. Check Render logs for errors

### OAuth Fails
1. Verify redirect URLs match exactly
2. Check SHOPIFY_CLIENT_ID and SECRET are set
3. Ensure scopes are correct

### Fulfillment Not Triggering
1. Check `auto_fulfill_enabled` is `true`
2. Verify supplier credentials (CJ/AliExpress)
3. Check product has supplier mapping

---

## Next Steps

After completing this setup:
1. ✅ Place a test order to verify flow
2. ✅ Apply for Shopify App Store listing (optional)
3. ✅ Set up payment/subscription system for SaaS
4. 🔜 AI Image Generation setup
