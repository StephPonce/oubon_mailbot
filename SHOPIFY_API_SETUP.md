# Shopify API Setup Guide

## Problem: HTTP 404 on all Shopify API endpoints

This means your Admin API access token is **invalid, revoked, or missing permissions**.

## Solution: Complete Shopify App Setup

### Step 1: Go to Shopify Admin

1. Open: https://oubonshop.myshopify.com/admin
2. Navigate: **Settings** → **Apps and sales channels**
3. Click: **Develop apps** (top right)

### Step 2: Find or Create Your App

**If you see an existing app (like "Oubon Automation"):**
- Click on it
- Skip to Step 3

**If NO apps exist:**
1. Click **"Create an app"**
2. App name: `Oubon Automation`
3. Click **"Create app"**

### Step 3: Configure API Scopes

1. Click the **"Configuration"** tab
2. Under **"Admin API access scopes"**, click **"Configure"**
3. Check ALL these scopes (required for full functionality):

   **Product Management:**
   ```
   ✅ read_products
   ✅ write_products
   ✅ read_inventory
   ✅ write_inventory
   ✅ read_product_listings
   ✅ write_product_listings
   ```

   **Order Management:**
   ```
   ✅ read_orders
   ✅ write_orders (for processing refunds)
   ✅ read_fulfillments (for tracking info)
   ```

   **Optional (for advanced features):**
   ```
   ⚠️  write_fulfillments (if you mark orders as shipped)
   ⚠️  read_customers (customer data from orders)
   ⚠️  read_all_orders (broader order access)
   ```

4. Click **"Save"**

**Why you need all these scopes:**
- `write_inventory` - Set dropshipping mode (no inventory tracking)
- `write_product_listings` - Publish products to your storefront
- `read_fulfillments` - Get shipping/tracking info for orders
- `write_orders` - Process refunds via Gmail automation

### Step 4: Install the App

1. Still in Configuration tab
2. Click **"Install app"** button
3. Confirm the installation

### Step 5: Get Your Credentials

1. Click the **"API credentials"** tab
2. You'll see 3 credentials:

#### A. Admin API Access Token
- Under "Admin API access token"
- Click **"Reveal token once"**
- **COPY THIS NOW** (you can only see it once!)
- Format: `shpat_xxxxxxxxxxxxxxxxxxxxxxxx`
- This goes in: `SHOPIFY_API_TOKEN`

#### B. API Key
- Under "API key"
- Just copy the value shown
- This goes in: `SHOPIFY_API_KEY`

#### C. API Secret Key
- Under "API secret key"
- Click **"Show"** to reveal it
- Copy the value
- This goes in: `SHOPIFY_API_SECRET`

### Step 6: Add to .env File

Add these lines to your `.env` file:

```bash
# Shopify Admin API Access Token (for making API calls)
SHOPIFY_API_TOKEN=shpat_your_token_from_step_5A

# Shopify API Key (for OAuth - optional for now)
SHOPIFY_API_KEY=your_api_key_from_step_5B

# Shopify API Secret (for OAuth - optional for now)
SHOPIFY_API_SECRET=your_secret_from_step_5C

# Store info
SHOPIFY_STORE=oubonshop.myshopify.com
SHOPIFY_STORE_DOMAIN=oubonshop.myshopify.com
SHOPIFY_API_VERSION=2025-01
```

### Step 7: Add to Render (Production)

1. Go to: https://dashboard.render.com
2. Select your service: `oubon_mailbot`
3. Click **"Environment"** tab
4. Add/Update these variables:
   - `SHOPIFY_API_TOKEN` = (paste token from step 5A)
   - `SHOPIFY_API_KEY` = (paste key from step 5B)
   - `SHOPIFY_API_SECRET` = (paste secret from step 5C)
5. Click **"Save Changes"**
6. Service will auto-redeploy (~2 minutes)

### Step 8: Test the Connection

Run this command to verify it works:

```bash
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot"
uv run python test_shopify_connection.py
```

You should see:
```
✅ Shop Info: SUCCESS
   Store Name: Oubon
   Email: your@email.com
```

## Troubleshooting

### Still Getting 404?

1. **Check app is installed**: In Shopify Admin → Apps, you should see "Oubon Automation" listed
2. **Verify scopes**: Go back to Configuration tab, make sure all scopes are checked
3. **Regenerate token**: In API credentials tab, delete the old token and create a new one
4. **Check store URL**: Make sure it's `oubonshop.myshopify.com` (not `oubonshop.com`)

### Getting 401 Unauthorized?

- Token is wrong or expired
- Copy the token again from Shopify (reveal once)
- Make sure no extra spaces when pasting

### Getting 403 Forbidden?

- Missing required API scopes
- Go back to Configuration tab
- Add the missing scopes
- Save and reinstall the app

## What Each Credential Does

| Credential | Purpose | Required For |
|------------|---------|--------------|
| `SHOPIFY_API_TOKEN` | Make API calls (CRUD products, orders) | ✅ **Required** |
| `SHOPIFY_API_KEY` | OAuth authentication (if building public app) | Optional for now |
| `SHOPIFY_API_SECRET` | OAuth authentication (if building public app) | Optional for now |

**For your use case** (private automation), you only **need** the `SHOPIFY_API_TOKEN`.

The API Key and Secret are for OAuth flows (letting other users install your app), which you don't need right now.

## Next Steps After Setup

Once the token works:

1. Test locally: `uv run python test_shopify_connection.py`
2. Create products: `uv run python shopify_automation/setup_products.py --count 10`
3. Verify in Shopify: Check your products appear in admin
