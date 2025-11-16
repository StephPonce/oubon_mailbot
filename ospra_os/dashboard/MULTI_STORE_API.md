# Multi-Store Portfolio API Documentation

Complete REST API for managing multiple e-commerce stores across platforms (Shopify, Amazon, WooCommerce, Etsy, eBay).

## Base URL

```
http://localhost:8001/api/portfolio
```

## Authentication

Currently uses a default user (`steph@oubonshop.com`). In production, add JWT/OAuth authentication.

## Endpoints

### 1. GET /api/portfolio/overview

Get aggregated metrics across all user's stores.

**Response:**
```json
{
  "total_revenue": 45678.90,
  "monthly_revenue": 12345.00,
  "active_stores": 3,
  "total_stores": 3,
  "total_products": 156,
  "active_products": 142,
  "avg_conversion_rate": 3.45,
  "best_performing_store": "Main Shopify Store",
  "total_orders": 234,
  "platforms": {
    "shopify": 2,
    "amazon": 1
  }
}
```

**Example:**
```bash
curl http://localhost:8001/api/portfolio/overview
```

---

### 2. GET /api/portfolio/rankings

Get store performance rankings sorted by monthly revenue.

**Response:**
```json
[
  {
    "id": 1,
    "store_name": "Main Shopify Store",
    "platform": "shopify",
    "monthly_revenue": 8500.00,
    "total_revenue": 34500.00,
    "conversion_rate": 4.2,
    "product_count": 89,
    "active_products": 85,
    "rank_position": 1,
    "rank_change": 0,
    "rank_change_label": "—"
  },
  {
    "id": 2,
    "store_name": "Amazon Storefront",
    "platform": "amazon",
    "monthly_revenue": 6200.00,
    "total_revenue": 18900.00,
    "conversion_rate": 2.8,
    "product_count": 45,
    "active_products": 42,
    "rank_position": 2,
    "rank_change": 1,
    "rank_change_label": "↑ +1"
  }
]
```

**Rank Change Labels:**
- `↑ +3` - Moved up 3 positions
- `↓ -2` - Dropped 2 positions
- `—` - No change

**Example:**
```bash
curl http://localhost:8001/api/portfolio/rankings
```

---

### 3. POST /api/portfolio/stores/add

Add new store to portfolio.

**Request Body:**
```json
{
  "store_name": "My Shopify Store",
  "store_url": "my-store.myshopify.com",
  "platform": "shopify",
  "credentials": {
    "shop_url": "my-store.myshopify.com",
    "access_token": "shpat_abc123...",
    "api_version": "2025-01"
  },
  "niche": "smart_home",
  "target_market": "US",
  "currency": "USD"
}
```

**Amazon Example:**
```json
{
  "store_name": "Amazon Storefront",
  "store_url": "amazon.com/sp?seller=ABC123",
  "platform": "amazon",
  "credentials": {
    "seller_id": "ABC123",
    "mws_token": "amzn.mws...",
    "marketplace_id": "ATVPDKIKX0DER"
  },
  "niche": "electronics",
  "target_market": "US",
  "currency": "USD"
}
```

**WooCommerce Example:**
```json
{
  "store_name": "WooCommerce Site",
  "store_url": "mystore.com",
  "platform": "woocommerce",
  "credentials": {
    "site_url": "https://mystore.com",
    "consumer_key": "ck_...",
    "consumer_secret": "cs_..."
  },
  "niche": "fashion",
  "target_market": "UK",
  "currency": "GBP"
}
```

**Response:** (Same as GET /stores/{store_id})

**Example:**
```bash
curl -X POST http://localhost:8001/api/portfolio/stores/add \
  -H "Content-Type: application/json" \
  -d '{
    "store_name": "Test Store",
    "store_url": "test.myshopify.com",
    "platform": "shopify",
    "credentials": {
      "shop_url": "test.myshopify.com",
      "access_token": "shpat_test123",
      "api_version": "2025-01"
    },
    "niche": "smart_home"
  }'
```

**Supported Platforms:**
- `shopify`
- `amazon`
- `woocommerce`
- `etsy`
- `ebay`

---

### 4. POST /api/portfolio/stores/{store_id}/switch

Switch active/default store (sets as rank #1).

**Example:**
```bash
curl -X POST http://localhost:8001/api/portfolio/stores/2/switch
```

**Response:** (Same as GET /stores/{store_id})

**Use Case:** Quick store switching in UI. Sets selected store to rank 1, shifts current #1 to rank 2.

---

### 5. GET /api/portfolio/stores/{store_id}

Get detailed store information.

**Response:**
```json
{
  "id": 1,
  "store_name": "Main Shopify Store",
  "store_url": "main-store.myshopify.com",
  "platform": "shopify",
  "niche": "smart_home",
  "target_market": "US",
  "currency": "USD",
  "is_active": true,
  "total_revenue": 34500.00,
  "monthly_revenue": 8500.00,
  "total_orders": 156,
  "conversion_rate": 4.2,
  "rank_position": 1,
  "rank_change": 0,
  "product_count": 89,
  "active_products": 85,
  "last_sync": "2025-11-14T02:30:00Z",
  "created_at": "2025-10-01T10:00:00Z"
}
```

**Example:**
```bash
curl http://localhost:8001/api/portfolio/stores/1
```

---

### 6. PUT /api/portfolio/stores/{store_id}

Update store information.

**Request Body:** (All fields optional)
```json
{
  "store_name": "Updated Store Name",
  "niche": "tech_gadgets",
  "target_market": "UK",
  "currency": "GBP",
  "is_active": false
}
```

**Response:** (Same as GET /stores/{store_id})

**Example:**
```bash
curl -X PUT http://localhost:8001/api/portfolio/stores/1 \
  -H "Content-Type: application/json" \
  -d '{
    "store_name": "Renamed Store",
    "niche": "fitness"
  }'
```

---

### 7. DELETE /api/portfolio/stores/{store_id}

Delete store from portfolio.

**Validation:** Cannot delete if it's the only store.

**Response:** 204 No Content (success)

**Example:**
```bash
curl -X DELETE http://localhost:8001/api/portfolio/stores/3
```

**Error Response (last store):**
```json
{
  "detail": "Cannot delete the only store. Add another store first."
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid credentials for shopify. Please check and try again."
}
```

### 404 Not Found
```json
{
  "detail": "Store not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to add store: <error message>"
}
```

---

## Complete Workflow Example

### 1. Initialize Database
```python
from ospra_os.database import init_multi_store_db

engine = init_multi_store_db("sqlite:///./oubon_store.db")
```

### 2. Start Backend
```bash
cd /path/to/oubon_mailbot
uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001
```

### 3. Check Health
```bash
curl http://localhost:8001/health

# Response:
{
  "status": "ok",
  "service": "OspraOS",
  "multi_store_loaded": true,
  ...
}
```

### 4. Add First Store
```bash
curl -X POST http://localhost:8001/api/portfolio/stores/add \
  -H "Content-Type: application/json" \
  -d '{
    "store_name": "Main Shopify",
    "store_url": "main.myshopify.com",
    "platform": "shopify",
    "credentials": {
      "shop_url": "main.myshopify.com",
      "access_token": "shpat_real_token",
      "api_version": "2025-01"
    },
    "niche": "smart_home"
  }'
```

### 5. Add Second Store (Amazon)
```bash
curl -X POST http://localhost:8001/api/portfolio/stores/add \
  -H "Content-Type: application/json" \
  -d '{
    "store_name": "Amazon Store",
    "store_url": "amazon.com/sp?seller=ABC",
    "platform": "amazon",
    "credentials": {
      "seller_id": "ABC123",
      "mws_token": "amzn.mws.token",
      "marketplace_id": "ATVPDKIKX0DER"
    },
    "niche": "electronics"
  }'
```

### 6. View Portfolio Overview
```bash
curl http://localhost:8001/api/portfolio/overview

# Response:
{
  "total_revenue": 0,
  "monthly_revenue": 0,
  "active_stores": 2,
  "total_stores": 2,
  "total_products": 0,
  ...
}
```

### 7. View Rankings
```bash
curl http://localhost:8001/api/portfolio/rankings

# Response: Array of ranked stores
```

### 8. Switch Active Store
```bash
curl -X POST http://localhost:8001/api/portfolio/stores/2/switch
```

### 9. Update Store
```bash
curl -X PUT http://localhost:8001/api/portfolio/stores/1 \
  -H "Content-Type: application/json" \
  -d '{"niche": "fitness"}'
```

### 10. Delete Store
```bash
curl -X DELETE http://localhost:8001/api/portfolio/stores/2
```

---

## Testing with FastAPI Docs

Visit: **http://localhost:8001/docs**

Interactive Swagger UI with all endpoints:
- Try out endpoints directly
- See request/response schemas
- Test validation
- View error responses

---

## Next Steps

1. **Add Authentication**
   - Replace `get_current_user()` with JWT/OAuth
   - Add user registration/login endpoints

2. **Add Credential Encryption**
   - Encrypt `Store.credentials` at rest
   - Use `sqlalchemy_utils.EncryptedType`

3. **Add Real Platform Validation**
   - Implement actual API calls in `validate_store_credentials()`
   - Test Shopify connection
   - Test Amazon MWS connection
   - Test WooCommerce REST API

4. **Add Product Management**
   - Import products from stores
   - Sync products across stores
   - Track deployments

5. **Add Analytics Dashboard**
   - Revenue charts
   - Conversion tracking
   - Performance comparisons

6. **Add Webhooks**
   - Listen for Shopify order events
   - Listen for Amazon notifications
   - Auto-update store metrics

---

## Database Schema

See `/ospra_os/database/README.md` for complete schema documentation.

**Key Tables:**
- `users` - Multi-tenant users
- `stores` - Platform-agnostic stores
- `products` - Product catalog
- `product_deployments` - Cross-platform tracking
- `ai_usage` - Cost tracking
- `user_settings` - Preferences

---

## Support

For issues or questions:
- Check `/ospra_os/database/README.md`
- Check FastAPI docs: http://localhost:8001/docs
- Review `/ospra_os/dashboard/routes_multi_store.py`

---

**Built with FastAPI + SQLAlchemy + Pydantic**
**Part of OspraOS - Ospra LLC**
