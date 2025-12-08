# Shopify AI-Powered Deployment Integration

## Overview

The Shopify integration has been enhanced with full AI-powered capabilities from the unified deployment pipeline. Products can now be deployed to Shopify with automatic content generation, image enhancement, SEO optimization, and competitive pricing - all powered by Claude Sonnet 4.5, DALL-E 3, and advanced AI algorithms.

**Date:** December 7, 2025
**Status:** ✅ Complete and Operational

---

## Integration Summary

### What Was Done

1. **Updated Shopify Deployment Routes** (`/ospra_os/integrations/shopify/routes.py`)
   - Integrated `ProductDeployer` from unified AI pipeline
   - Added AI control flags to request models
   - Enhanced response models with AI metrics
   - Added preview endpoint for pre-deployment review

2. **Registered Router in Main Application** (`/ospra_os/main.py`)
   - Added Shopify deployment router import (line 292-300)
   - Registered router in FastAPI app (line 838-839)

3. **AI Features Enabled**
   - Content Generation (Claude Sonnet 4.5)
   - Image Enhancement (DALL-E 3 + rembg)
   - SEO Optimization
   - Competitive Pricing Intelligence

---

## API Endpoints

All endpoints are accessible at: `http://localhost:8001/api/shopify/`

### 1. Get Shopify Status
```http
GET /api/shopify/status
```

**Response:**
```json
{
  "configured": true,
  "store_name": "Your Store Name",
  "store_domain": "yourstore.myshopify.com",
  "api_version": "2025-01",
  "mode": "safe",
  "connection": "active",
  "product_count": 42,
  "currency": "USD"
}
```

### 2. Deploy Single Product (AI-Powered)
```http
POST /api/shopify/deploy
```

**Request Body:**
```json
{
  "product_id": "internal_product_123",
  "name": "Smart LED Bulb WiFi RGB Control",
  "niche": "smart_home",
  "supplier_cost": 12.99,
  "supplier_url": "https://aliexpress.com/item/...",
  "images": [
    "https://ae01.alicdn.com/kf/H123.jpg",
    "https://ae01.alicdn.com/kf/H456.jpg"
  ],
  "features": [
    "WiFi connectivity",
    "RGB color control",
    "Alexa compatible",
    "Energy efficient LED"
  ],

  // AI Control Flags (all default to true/false)
  "ai_content": true,        // Generate title/description
  "ai_images": true,          // Enhance images with AI
  "ai_pricing": true,         // Auto-calculate competitive price
  "ai_seo": true,             // Generate SEO metadata
  "publish": false,           // Publish immediately vs draft

  // Deployment Options
  "target_margin": 0.4,       // 40% profit margin
  "add_branding": true,       // Add watermark to images
  "max_images": 5             // Max images to process
}
```

**Response:**
```json
{
  "success": true,
  "product_id": "internal_product_123",
  "shopify_product_id": 7891234567890,
  "shopify_url": "https://yourstore.myshopify.com/products/smart-led-bulb",
  "admin_url": "https://yourstore.myshopify.com/admin/products/7891234567890",
  "price": 29.99,
  "deployed_at": "2025-12-07T12:34:56",

  // AI Enhancement Metrics
  "content_generated": {
    "title": "Smart WiFi RGB LED Bulb - Alexa Compatible Smart Lighting",
    "description_preview": "Transform your home with...",
    "seo_meta_title": "Smart WiFi LED Bulb | RGB Color Control | Alexa",
    "seo_meta_description": "Control your lighting from anywhere..."
  },
  "images_enhanced": 2,
  "ai_costs": {
    "content_generation": 0.02,
    "image_enhancement": 0.04
  },
  "total_cost": 0.06,
  "processing_time_seconds": 23.5,
  "published": false
}
```

### 3. Preview Deployment (No Deploy)
```http
POST /api/shopify/deploy/preview
```

**Purpose:** Generate all AI content and enhanced images WITHOUT deploying to Shopify. Perfect for review/approval workflow.

**Request:** Same as `/deploy` endpoint

**Response:**
```json
{
  "title": "Smart WiFi RGB LED Bulb - Alexa Compatible Smart Lighting",
  "description_html": "<h3>Transform Your Home...</h3><ul><li>...</li></ul>",
  "short_description": "WiFi-enabled RGB LED bulb with voice control",
  "bullet_points": [
    "WiFi connectivity for remote control",
    "16 million RGB colors",
    "Works with Alexa & Google Home",
    "Energy-efficient LED technology"
  ],
  "images": [
    "http://localhost:8001/static/images/products/123/enhanced_001.png",
    "http://localhost:8001/static/images/products/123/enhanced_002.png"
  ],
  "pricing": {
    "cost_price": 12.99,
    "retail_price": 29.99,
    "profit_margin": 56.7,
    "psychological_price": true
  },
  "seo": {
    "meta_title": "Smart WiFi LED Bulb | RGB Color Control | Alexa Compatible",
    "meta_description": "Control your lighting from anywhere with our smart WiFi LED bulb...",
    "url_slug": "smart-wifi-rgb-led-bulb",
    "keywords": ["smart bulb", "wifi led", "rgb lighting", "alexa bulb"]
  },
  "tags": ["smart_home", "new-arrival", "trending"],
  "estimated_cost": 0.06,
  "processing_time": 18.2
}
```

### 4. Bulk Deploy
```http
POST /api/shopify/deploy/bulk
```

**Request:**
```json
{
  "products": [
    { /* ProductDeployRequest */ },
    { /* ProductDeployRequest */ },
    { /* ProductDeployRequest */ }
  ],
  "max_concurrent": 3
}
```

**Response:**
```json
[
  { /* DeploymentResult for product 1 */ },
  { /* DeploymentResult for product 2 */ },
  { /* DeploymentResult for product 3 */ }
]
```

### 5. List Products
```http
GET /api/shopify/products?limit=50
```

### 6. Delete Product
```http
DELETE /api/shopify/products/{product_id}
```

### 7. Update Inventory
```http
PATCH /api/shopify/products/{product_id}/inventory?quantity=100
```

### 8. Analytics
```http
GET /api/shopify/analytics
```

---

## AI Features Breakdown

### 1. Content Generation (ai_content: true)
**Provider:** Claude Sonnet 4.5
**Cost:** ~$0.02 per product
**Processing Time:** ~8-10 seconds

**Generates:**
- SEO-optimized product title (max 70 chars)
- Long-form HTML description (150-250 words)
- Short description for previews
- Bullet point features list
- Meta title (60 chars)
- Meta description (155 chars)
- URL slug
- SEO keywords

### 2. Image Enhancement (ai_images: true)
**Providers:** rembg (FREE) + DALL-E 3
**Cost:** ~$0.04 per product (first image only)
**Processing Time:** ~10-15 seconds

**Pipeline:**
1. Download original AliExpress image
2. Remove background (rembg - local, FREE)
3. Generate lifestyle background (DALL-E 3 - $0.04)
4. Composite product onto background with shadows
5. Add optional branding/watermark
6. Save to local storage with HTTP serving

### 3. Pricing Intelligence (ai_pricing: true)
**Provider:** Claude Sonnet 4.5
**Cost:** Included in content generation
**Processing Time:** < 1 second

**Features:**
- Analyzes product category and market
- Calculates price based on target margin
- Applies psychological pricing (.99 endings)
- Considers competitive pricing data
- Returns margin analysis and recommendations

### 4. SEO Optimization (ai_seo: true)
**Provider:** Claude Sonnet 4.5
**Cost:** Included in content generation
**Processing Time:** < 1 second

**Generates:**
- Meta title optimized for search engines
- Meta description with keywords
- URL-friendly slug
- Keyword suggestions
- Alt text for images

---

## Cost Analysis

### Per-Product Deployment Cost

| Feature | Provider | Cost |
|---------|----------|------|
| Content Generation | Claude Sonnet 4.5 | ~$0.02 |
| Image Enhancement (first image) | DALL-E 3 | ~$0.04 |
| Image Background Removal | rembg (local) | FREE |
| SEO Optimization | Claude Sonnet 4.5 | Included |
| Pricing Intelligence | Claude Sonnet 4.5 | Included |
| **Total (all AI enabled)** | | **~$0.06** |

### Monthly Cost Projections

| Products/Month | AI Cost | Notes |
|----------------|---------|-------|
| 100 | $6 | Small store |
| 500 | $30 | Medium store |
| 1,000 | $60 | Large store |
| 5,000 | $300 | Enterprise |

**Note:** Costs assume all AI features enabled. Disabling image enhancement reduces cost to ~$0.02/product.

---

## Usage Examples

### Example 1: Full AI Deployment
```python
import requests

# Deploy with all AI features
response = requests.post("http://localhost:8001/api/shopify/deploy", json={
    "product_id": "prod_123",
    "name": "Smart LED Strip 5M RGB WiFi",
    "niche": "smart_home",
    "supplier_cost": 15.99,
    "images": ["https://aliexpress.com/img/123.jpg"],
    "features": ["WiFi control", "RGB colors", "Music sync"],

    # All AI enabled (defaults)
    "ai_content": True,
    "ai_images": True,
    "ai_pricing": True,
    "ai_seo": True,
    "publish": False,  # Save as draft

    "target_margin": 0.45  # 45% margin
})

print(response.json())
```

### Example 2: Preview Before Deploy
```python
# Generate preview first
preview = requests.post("http://localhost:8001/api/shopify/deploy/preview", json={
    "product_id": "prod_123",
    "name": "Smart LED Strip 5M RGB WiFi",
    "niche": "smart_home",
    "supplier_cost": 15.99,
    "images": ["https://aliexpress.com/img/123.jpg"],
    "features": ["WiFi control", "RGB colors"]
}).json()

# Review the generated content
print(f"Title: {preview['title']}")
print(f"Price: ${preview['pricing']['retail_price']}")
print(f"Cost: ${preview['estimated_cost']}")

# If approved, deploy
if approved:
    deploy = requests.post("http://localhost:8001/api/shopify/deploy", json={
        # Same request body as preview
    })
```

### Example 3: Cost-Optimized Deployment
```python
# Deploy without image enhancement to save cost
response = requests.post("http://localhost:8001/api/shopify/deploy", json={
    "product_id": "prod_123",
    "name": "Smart LED Strip",
    "niche": "smart_home",
    "supplier_cost": 15.99,
    "images": ["https://aliexpress.com/img/123.jpg"],

    "ai_content": True,    # Keep content generation
    "ai_images": False,    # Disable image enhancement (saves $0.04)
    "ai_pricing": True,
    "ai_seo": True,
    "publish": True        # Publish immediately
})

# Cost: ~$0.02 instead of ~$0.06
```

### Example 4: Bulk Deployment
```python
products = []
for i in range(10):
    products.append({
        "product_id": f"prod_{i}",
        "name": f"Product {i}",
        "niche": "smart_home",
        "supplier_cost": 20.00,
        "images": [f"https://example.com/img{i}.jpg"],
        "ai_content": True,
        "ai_images": True
    })

response = requests.post("http://localhost:8001/api/shopify/deploy/bulk", json={
    "products": products,
    "max_concurrent": 3  # Process 3 at a time
})

# Total cost: ~$0.60 for 10 products
# Total time: ~100-120 seconds
```

---

## Files Modified

### 1. `/ospra_os/integrations/shopify/routes.py`
**Changes:**
- Added `ProductDeployer` import
- Enhanced `ProductDeployRequest` model with AI flags:
  - `ai_content`, `ai_images`, `ai_pricing`, `ai_seo`, `publish`
  - `target_margin`, `add_branding`, `max_images`, `features`
- Enhanced `DeploymentResult` model with AI metrics:
  - `content_generated`, `images_enhanced`, `ai_costs`, `total_cost`, `processing_time_seconds`, `published`
- Added `PreviewResult` model
- Added `get_unified_deployer()` initialization function
- Rewrote `deploy_product()` endpoint to use unified AI pipeline
- Added `preview_deployment()` endpoint

**Lines Modified:** ~150 lines updated

### 2. `/ospra_os/main.py`
**Changes:**
- Added Shopify deployment router import (lines 292-300)
- Added router registration (lines 838-839)

**Lines Modified:** 11 lines added

---

## Testing

### Manual Testing

1. **Test Shopify Connection:**
```bash
curl http://localhost:8001/api/shopify/status | python3 -m json.tool
```

2. **Test Preview Endpoint:**
```bash
curl -X POST http://localhost:8001/api/shopify/deploy/preview \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "test_1",
    "name": "Smart WiFi Plug",
    "niche": "smart_home",
    "supplier_cost": 8.99,
    "images": ["https://example.com/img.jpg"],
    "features": ["WiFi", "Alexa compatible"]
  }' | python3 -m json.tool
```

3. **Test Deployment:**
```bash
curl -X POST http://localhost:8001/api/shopify/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "test_1",
    "name": "Smart WiFi Plug",
    "niche": "smart_home",
    "supplier_cost": 8.99,
    "images": ["https://example.com/img.jpg"],
    "features": ["WiFi", "Alexa compatible"],
    "ai_content": true,
    "ai_images": false,
    "ai_pricing": true,
    "ai_seo": true,
    "publish": false
  }' | python3 -m json.tool
```

### Expected Results

- ✅ `/api/shopify/status` returns Shopify store info
- ✅ `/api/shopify/deploy/preview` generates AI content without deploying
- ✅ `/api/shopify/deploy` creates product in Shopify with AI enhancements
- ✅ All AI features can be toggled individually
- ✅ Cost tracking included in responses
- ✅ Processing time ~20-30 seconds per product

---

## Next Steps (Recommended)

### Frontend Integration
1. **Update Dashboard UI** to show AI-generated preview before deployment
2. **Add AI Control Toggles** in deployment modal
3. **Display AI Cost Estimates** before deploying
4. **Show AI-Generated Content** for admin review/approval

### Settings & Configuration
1. **Create Settings Table** for default AI preferences
2. **Add Brand Voice Configuration** for content generation
3. **Configure Default Margin** per niche
4. **Enable/Disable AI Features** globally

### Enhancements
1. **Batch Preview** - Preview multiple products at once
2. **A/B Testing** - Generate multiple variations
3. **Approval Workflow** - Review queue for AI-generated content
4. **Cost Tracking Dashboard** - Monitor monthly AI spend
5. **Multi-Image Enhancement** - Process all images (not just first)

---

## Troubleshooting

### Issue: Shopify Routes Not Loading
**Solution:** Ensure router is registered in main.py:
```python
if _HAS_SHOPIFY_DEPLOYMENT and shopify_deployment_router:
    app.include_router(shopify_deployment_router)
```

### Issue: AI Content Generation Fails
**Cause:** Missing ANTHROPIC_API_KEY
**Solution:** Set environment variable:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Issue: Image Enhancement Fails
**Cause:** Missing OPENAI_API_KEY or rembg dependencies
**Solution:**
```bash
export OPENAI_API_KEY="sk-..."
pip install rembg pillow
```

### Issue: High Costs
**Solution:** Disable image enhancement:
```json
{
  "ai_images": false  // Reduces cost from ~$0.06 to ~$0.02
}
```

---

## API Documentation Links

- Shopify Admin API: https://shopify.dev/docs/api/admin-rest
- Claude API: https://docs.anthropic.com/
- DALL-E 3 API: https://platform.openai.com/docs/guides/images
- rembg: https://github.com/danielgatis/rembg

---

## Support

For issues or questions:
1. Check server logs: `tail -f logs/ospra_os.log`
2. Test endpoints manually with curl
3. Verify environment variables are set
4. Check Shopify store credentials

**Status:** ✅ Integration Complete and Operational
**Last Updated:** December 7, 2025
