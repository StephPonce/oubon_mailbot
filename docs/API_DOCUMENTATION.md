# 📚 Ospra Intelligence API Documentation

## Base URL
`http://localhost:8000` (development)
`https://api.ospraintelligence.com` (production)

## Authentication
Currently: Basic auth with user email
Future: JWT tokens

## Portfolio Management

### GET /api/portfolio/overview
Get aggregated metrics across all stores.

Response:
```json
{
  "totalRevenue": 125000.00,
  "activeStores": 3,
  "totalProducts": 247,
  "avgConversion": 2.5
}
```

### GET /api/portfolio/rankings
Get store performance rankings.

### POST /api/portfolio/stores/add
Add new store to portfolio.

Request:
```json
{
  "store_name": "My Shop",
  "platform": "shopify",
  "credentials": {...},
  "niche": "smart_home"
}
```

### POST /api/portfolio/stores/{id}/sync
Sync store data from platform.

## Product Discovery

### POST /api/intelligence/discover
Discover winning products.

Request:
```json
{
  "niches": ["smart_home", "fitness"],
  "max_per_niche": 5
}
```

Response:
```json
{
  "success": true,
  "products": [...],
  "count": 10
}
```

## Product Deployment

### POST /api/deploy/product/{product_id}/to-store/{store_id}
Deploy product to specific store.

### POST /api/deploy/product/{product_id}/to-all-stores
Deploy to all user's stores.

## AI Management

### GET /api/ai/providers
List available AI providers.

### POST /api/ai/test/{provider}
Test AI provider credentials.

## Platform Management

### GET /api/platforms
List available platforms.

### POST /api/platforms/{platform}/test
Test platform credentials.

## Error Responses

All errors return:
```json
{
  "success": false,
  "error": "Error message",
  "code": "ERROR_CODE"
}
```

Common error codes:
- AUTH_FAILED
- PLATFORM_ERROR
- AI_ERROR
- RATE_LIMIT_EXCEEDED
- INVALID_CREDENTIALS
