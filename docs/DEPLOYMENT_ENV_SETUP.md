# Deployment API - Environment Variables Setup

This guide explains how to configure the unified product deployment system to connect to Shopify, Amazon, and WooCommerce.

## Required Environment Variables

Add these variables to your `.env` file:

### Shopify Configuration

```bash
# Shopify Store Domain (without https://)
SHOPIFY_STORE=your-store.myshopify.com

# Shopify Admin API Access Token
# Get from: Shopify Admin → Apps → Develop apps → Create an app
SHOPIFY_API_TOKEN=shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Required Shopify API Scopes:**
- `write_products` - Create and update products
- `read_products` - Read product data
- `write_inventory` - Update inventory
- `read_inventory` - Read inventory levels

---

### Amazon Seller Central (SP-API) Configuration

```bash
# Amazon Seller Central Refresh Token
AMAZON_REFRESH_TOKEN=Atzr|IwEBxxxxxxxxxxxxxxxxxx

# Amazon SP-API Client ID (from Developer Console)
AMAZON_CLIENT_ID=amzn1.application-oa2-client.xxxxxxxxxxxxxxxx

# Amazon SP-API Client Secret
AMAZON_CLIENT_SECRET=your_client_secret_here

# Amazon Region (default: us-east-1)
AMAZON_REGION=us-east-1

# Amazon Marketplace ID (default: US marketplace)
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
```

**How to Get Amazon Credentials:**

1. **Register as Amazon Developer**
   - Go to: https://developer.amazonservices.com/
   - Register for SP-API access

2. **Create an SP-API Application**
   - Developer Console → Add new App
   - Select "SP-API" as the API type
   - Note your `Client ID` and `Client Secret`

3. **Generate Refresh Token**
   - Use Amazon's LWA (Login with Amazon) OAuth flow
   - Authorize your app
   - Exchange authorization code for refresh token
   - Store the refresh token (it doesn't expire)

**Supported Regions:**
- `us-east-1` - North America (US, Canada, Mexico)
- `eu-west-1` - Europe (UK, DE, FR, IT, ES, etc.)
- `us-west-2` - Far East (Japan, Australia, Singapore)

---

### WooCommerce Configuration

```bash
# WooCommerce Store URL (with https://)
WOOCOMMERCE_STORE_URL=https://yourstore.com

# WooCommerce REST API Consumer Key
WOOCOMMERCE_CONSUMER_KEY=ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# WooCommerce REST API Consumer Secret
WOOCOMMERCE_CONSUMER_SECRET=cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**How to Get WooCommerce Credentials:**

1. **Login to WordPress Admin**
   - Go to your WordPress site admin panel

2. **Navigate to WooCommerce API Settings**
   - WooCommerce → Settings → Advanced → REST API

3. **Create API Key**
   - Click "Add key"
   - Description: "Oubon Deployment API"
   - User: Select your admin user
   - Permissions: **Read/Write**
   - Click "Generate API Key"

4. **Copy Credentials**
   - Consumer Key (starts with `ck_`)
   - Consumer Secret (starts with `cs_`)
   - **Save these immediately** (secret is shown only once)

---

## Example .env File

```bash
# ============================================================================
# PRODUCT DEPLOYMENT - MULTI-PLATFORM
# ============================================================================

# Shopify
SHOPIFY_STORE=rxxj7d-1i.myshopify.com
SHOPIFY_API_TOKEN=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

# Amazon Seller Central (SP-API)
AMAZON_REFRESH_TOKEN=Atzr|IwEBIKnmBpFqoVl...
AMAZON_CLIENT_ID=amzn1.application-oa2-client.a1b2c3d4e5f6
AMAZON_CLIENT_SECRET=abc123def456ghi789jkl012mno345pqr678stu901
AMAZON_REGION=us-east-1
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER

# WooCommerce
WOOCOMMERCE_STORE_URL=https://mystore.com
WOOCOMMERCE_CONSUMER_KEY=ck_1234567890abcdef1234567890abcdef12345678
WOOCOMMERCE_CONSUMER_SECRET=cs_1234567890abcdef1234567890abcdef12345678
```

---

## Testing Your Configuration

Once you've added the environment variables, test the connections:

### 1. Check Platform Status

```bash
curl http://localhost:8001/api/deploy/platforms/status
```

**Expected Response:**
```json
{
  "shopify": {
    "configured": true,
    "store": "your-store.myshopify.com",
    "status": "ready"
  },
  "amazon": {
    "configured": true,
    "region": "us-east-1",
    "status": "ready"
  },
  "woocommerce": {
    "configured": true,
    "store_url": "https://yourstore.com",
    "status": "ready"
  }
}
```

### 2. Test Product Deployment

```bash
curl -X POST http://localhost:8001/api/deploy/product \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "test_123",
    "product_data": {
      "name": "Test Product",
      "description": "This is a test product",
      "price": 29.99,
      "image_url": "https://example.com/image.jpg",
      "category": "electronics"
    },
    "platforms": ["shopify"],
    "generate_ai_description": false,
    "optimize_seo": true
  }'
```

---

## API Endpoints

Once configured, these endpoints are available:

### Deploy Product
```
POST /api/deploy/product
```
Deploy a single product to one or more platforms

### Bulk Deploy
```
POST /api/deploy/bulk
```
Deploy multiple products at once

### Platform Status
```
GET /api/deploy/platforms/status
```
Check connection status for all platforms

### Update Inventory
```
PUT /api/deploy/inventory/update
```
Update product inventory across platforms

### Sync Orders
```
POST /api/deploy/stores/sync-orders
```
Fetch orders from Amazon or WooCommerce

### Health Check
```
GET /api/deploy/health
```
Check if deployment service is running

---

## Security Best Practices

1. **Never commit `.env` file to Git**
   - Add `.env` to `.gitignore`
   - Use `.env.example` for templates

2. **Rotate API Keys Regularly**
   - Change keys every 90 days
   - Immediately rotate if compromised

3. **Use Environment-Specific Keys**
   - Development keys for testing
   - Production keys for live deployments

4. **Restrict API Permissions**
   - Only grant necessary scopes
   - Use read-only keys when possible

5. **Monitor API Usage**
   - Check for unusual activity
   - Set up rate limit alerts

---

## Troubleshooting

### Shopify: "403 Forbidden"
- Check API token has correct scopes
- Verify store domain is correct (no https://)
- Regenerate token if expired

### Amazon: "Authentication Failed"
- Verify refresh token is valid
- Check client ID and secret
- Ensure region matches your seller account

### WooCommerce: "Connection Refused"
- Verify store URL includes https://
- Check WordPress site is accessible
- Confirm API keys have Read/Write permissions
- Enable WooCommerce REST API in settings

### All Platforms: "Not Configured"
- Check .env file exists in project root
- Verify environment variables are loaded
- Restart the backend server after adding variables

---

## Support

For issues or questions:
- Check API docs: `http://localhost:8001/docs`
- Review platform documentation
- Test endpoints individually to isolate issues

**Platform Documentation:**
- [Shopify Admin API](https://shopify.dev/api/admin-rest)
- [Amazon SP-API](https://developer-docs.amazon.com/sp-api/)
- [WooCommerce REST API](https://woocommerce.github.io/woocommerce-rest-api-docs/)
