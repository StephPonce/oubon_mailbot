# API Quick Reference - Frontend

Quick reference for all API endpoints used by the frontend.

## Base URL
```
Development: http://localhost:8001
Production: https://your-domain.com
```

## Authentication

### Login (OAuth2)
```http
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=email@example.com&password=yourpassword
```

### Register
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "User Name"
}
```

### Get Current User
```http
GET /auth/me
Authorization: Bearer {access_token}
```

## Products

### List Products
```http
GET /api/dashboard/v2/products?niche=smart_home&page=1
```

### Get Single Product
```http
GET /api/dashboard/v2/products/{product_id}
```

### Discover Products
```http
POST /api/intelligence/discover
Content-Type: application/json

{
  "niches": ["smart_home", "fitness"],
  "max_per_niche": 10
}
```

### Analyze Product
```http
POST /api/dashboard/v2/products/{product_id}/analyze
```

### Deploy to Shopify
```http
POST /api/shopify/deploy
Content-Type: application/json

{
  "product_data": {...}
}
```

## Niches

### List All Niches
```http
GET /api/niches
```

### Get Niche Details
```http
GET /api/niches/{niche_id}
```

### Get Niche Products
```http
GET /api/niches/{niche_id}/products?limit=50
```

### Analyze Niche
```http
POST /api/niches/{niche_id}/analyze
```

## Trends

### Get Live Trends
```http
GET /api/trends/live?limit=20
```

### Get Movers (Up/Down)
```http
GET /api/trends/movers?direction=up&limit=10
```

### Get Breakouts
```http
GET /api/trends/breakouts
```

### Get Heatmap
```http
GET /api/trends/heatmap?rows=10&cols=5
```

### Get Product Momentum
```http
GET /api/trends/product/{product_id}
```

## Analytics

### Dashboard Overview
```http
GET /api/dashboard/v2/overview
```

### Revenue Data
```http
GET /api/analytics/revenue?period=month
```

### Conversion Funnel
```http
GET /api/analytics/funnel
```

### Product Performance
```http
GET /api/analytics/products/performance
```

### Customer Segments
```http
GET /api/customers/segments
```

## Competitors

### List Competitors
```http
GET /api/competitors
```

### Get Competitor Details
```http
GET /api/competitors/{competitor_id}
```

### Price Comparison
```http
GET /api/competitors/prices
```

### Analyze Competitor
```http
POST /api/competitors/{competitor_id}/analyze
```

## Intelligence (Oi AI)

### Chat with Oi
```http
POST /api/dashboard/v2/claude/chat
Content-Type: application/json

{
  "message": "What products should I sell?",
  "context": {...}
}
```

### Get Morning Briefing
```http
GET /api/intelligence/briefing/morning
```

### Analyze Product (AI)
```http
POST /api/intelligence/analyze/product/{product_id}
```

### Analyze Niche (AI)
```http
POST /api/intelligence/analyze/niche/{niche_id}
```

### Smart Recommendations
```http
POST /api/recommendations/smart
Content-Type: application/json

{
  "user_id": 1,
  "max_products": 10
}
```

## Email

### Get Recent Emails
```http
GET /api/emails/recent?status=unread&limit=50
```

### Get Email Stats
```http
GET /api/dashboard/emails
```

### Reply to Email
```http
POST /api/emails/messages/{message_id}/reply
Content-Type: application/json

{
  "message": "Thank you for your inquiry..."
}
```

### Ignore Email
```http
POST /api/emails/messages/{message_id}/ignore
```

### Sync Emails
```http
POST /api/emails/sync
```

## A/B Testing

### List Tests
```http
GET /api/abtesting/tests
```

### Get Test Details
```http
GET /api/abtesting/tests/{test_id}
```

### Create Test
```http
POST /api/abtesting/tests
Content-Type: application/json

{
  "name": "Price Test",
  "variants": [...]
}
```

### Pause Test
```http
POST /api/abtesting/tests/{test_id}/pause
```

### Resume Test
```http
POST /api/abtesting/tests/{test_id}/resume
```

### Get Test Results
```http
GET /api/abtesting/tests/{test_id}/results
```

## System

### Health Check
```http
GET /health
```

### Detailed Health
```http
GET /api/health/detailed
```

### Frontend Compatibility Check
```http
GET /api/frontend-compat/health
```

## Response Format

All endpoints return JSON with this structure:

### Success Response
```json
{
  "success": true,
  "data": {...},
  "message": "Optional message"
}
```

### Error Response
```json
{
  "detail": "Error message",
  "status_code": 400
}
```

## Authentication

Most endpoints require authentication. Include the access token in the Authorization header:

```http
Authorization: Bearer {access_token}
```

Tokens expire after 30 minutes. Use the refresh token to get a new access token:

```http
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "your_refresh_token"
}
```

## Rate Limiting

- Public endpoints: 100 requests/minute
- Authenticated endpoints: 1000 requests/minute
- AI endpoints: 10 requests/minute

## Error Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Rate Limit Exceeded
- `500` - Server Error

## Need Help?

- API Documentation: http://localhost:8001/docs
- Issues: Check console for detailed error messages
- Support: Refer to CLAUDE.md for project guidelines
