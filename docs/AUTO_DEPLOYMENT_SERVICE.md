# Auto-Deployment Service

## Overview

The Auto-Deployment Service automatically deploys high-scoring products to Shopify without manual intervention. It runs on a schedule (hourly by default) and uses strict criteria to filter products, ensuring only the best opportunities are deployed.

**Status:** ✅ Operational (Disabled by Default)
**Last Updated:** December 7, 2025

---

## Key Features

### 🎯 Intelligent Product Selection
- **Score-based filtering** - Only products scoring ≥80/100
- **Profit margin requirements** - Minimum 35% margin
- **Market saturation checks** - Avoids oversaturated niches
- **Multi-source validation** - Products must be validated by multiple sources
- **Trend velocity monitoring** - Requires ≥70/100 Google Trends score

### 🛡️ Safety Features
- **Daily deployment limits** - Max 5 products/day (configurable)
- **Hourly rate limiting** - Max 2 products/hour
- **Cost controls** - Max $1/day in AI costs
- **Draft-first deployment** - Products saved as drafts for review
- **Admin notifications** - Email/Slack alerts for each deployment
- **Deployment history tracking** - Full audit trail

### 🤖 Full AI Pipeline
- Content generation (Claude Sonnet 4.5)
- Image enhancement (DALL-E 3 + rembg)
- SEO optimization
- Competitive pricing
- Multi-image processing

### 📊 Monitoring & Control
- Real-time status dashboard
- Deployment history with filters
- Cost tracking and budgets
- Manual trigger for testing
- Granular criteria control

---

## Default Configuration

```json
{
  "enabled": false,  // Must be explicitly enabled by admin
  "criteria": {
    "min_score": 80.0,           // Minimum product score (0-100)
    "min_profit_margin": 0.35,   // 35% minimum margin
    "max_saturation": "medium",  // Max saturation: low, medium, high
    "allowed_niches": [
      "smart_home",
      "fitness",
      "tech_gadgets",
      "kitchen"
    ],
    "max_per_day": 5,            // Max deployments per day
    "max_per_hour": 2,           // Max deployments per hour
    "max_daily_cost": 1.0,       // Max $1/day in AI costs
    "require_multiple_sources": true,  // Multi-source validation required
    "min_trend_velocity": 70.0,  // Min Google Trends velocity
    "auto_publish": false        // Always save as draft for safety
  }
}
```

---

## API Endpoints

### 1. Get Status
```http
GET /api/auto-deploy/status
```

**Response:**
```json
{
  "enabled": false,
  "criteria": {...},
  "last_run": "2025-12-07T12:34:56",
  "total_deployed": 42,
  "total_cost": 2.52
}
```

### 2. Enable Auto-Deployment
```http
POST /api/auto-deploy/enable
```

**Response:**
```json
{
  "success": true,
  "message": "Auto-deployment enabled",
  "criteria": {...}
}
```

### 3. Disable Auto-Deployment
```http
POST /api/auto-deploy/disable
```

**Response:**
```json
{
  "success": true,
  "message": "Auto-deployment disabled"
}
```

### 4. Update Criteria
```http
PUT /api/auto-deploy/criteria
```

**Request Body:**
```json
{
  "min_score": 85.0,
  "max_per_day": 10,
  "allowed_niches": ["smart_home", "tech_gadgets"],
  "max_daily_cost": 2.0
}
```

Only provided fields will be updated. All others remain unchanged.

**Response:**
```json
{
  "success": true,
  "message": "Criteria updated",
  "criteria": {...}  // Full updated criteria
}
```

### 5. Get Deployment History
```http
GET /api/auto-deploy/history?limit=50
```

**Response:**
```json
[
  {
    "id": 123,
    "product_name": "Smart WiFi Bulb",
    "niche": "smart_home",
    "score": 87.5,
    "shopify_url": "https://store.com/products/smart-wifi-bulb",
    "success": true,
    "error": null,
    "ai_cost": 0.06,
    "deployed_at": "2025-12-07T12:34:56"
  },
  ...
]
```

### 6. Run Deployment Check Now
```http
POST /api/auto-deploy/run-now
```

Manually trigger an auto-deployment check. Useful for testing configuration.

**Response:**
```json
{
  "success": true,
  "deployed": 3,
  "failed": 0,
  "total_cost": 0.18,
  "message": "Deployed 3 products successfully"
}
```

### 7. Health Check
```http
GET /api/auto-deploy/health
```

**Response:**
```json
{
  "status": "healthy",
  "deployer_initialized": true,
  "database_connected": true,
  "services": {
    "product_deployer": true,
    "product_discovery": true
  }
}
```

---

## How It Works

### Scheduled Workflow

The auto-deployer runs every hour (configurable) with this workflow:

```
1. Check if enabled
   ├─ If disabled → Skip
   └─ If enabled → Continue

2. Check daily limits
   ├─ Deployments today < max_per_day?
   ├─ Daily cost < max_daily_cost?
   └─ If limits reached → Skip

3. Discover candidate products
   ├─ Query unified discovery for each allowed niche
   ├─ Filter by min_score
   └─ Get top 10 per niche

4. Filter by criteria
   ├─ Check profit margin
   ├─ Check saturation level
   ├─ Check multi-source validation
   ├─ Check trend velocity
   └─ Check if already deployed

5. Sort by score (highest first)

6. Select products to deploy
   ├─ Respect hourly limit (max_per_hour)
   ├─ Respect remaining daily quota
   └─ Get top N products

7. Deploy each product
   ├─ Full AI pipeline (content + images + SEO + pricing)
   ├─ Deploy to Shopify as draft
   ├─ Track in database
   ├─ Send admin notification
   └─ 30-second pause between deployments

8. Update statistics
   ├─ Total deployed
   ├─ Total cost
   └─ Last run time
```

### Filtering Logic

Products must meet **ALL** criteria to be auto-deployed:

| Criterion | Default | Description |
|-----------|---------|-------------|
| `min_score` | 80.0 | Product opportunity score (0-100) |
| `min_profit_margin` | 0.35 | Minimum 35% profit margin |
| `max_saturation` | medium | Market saturation level (low/medium/high) |
| `allowed_niches` | 4 niches | Product must be in allowed niche |
| `require_multiple_sources` | true | Product validated by 2+ sources |
| `min_trend_velocity` | 70.0 | Google Trends velocity ≥70/100 |
| Not already deployed | - | Product not in deployment history |

---

## Usage Examples

### Example 1: Enable Auto-Deployment
```bash
# Check current status
curl http://localhost:8001/api/auto-deploy/status | jq

# Enable auto-deployment
curl -X POST http://localhost:8001/api/auto-deploy/enable | jq

# Verify enabled
curl http://localhost:8001/api/auto-deploy/status | jq '.enabled'
# Output: true
```

### Example 2: Update Criteria for Aggressive Deployment
```bash
# Deploy more products per day with lower criteria
curl -X PUT http://localhost:8001/api/auto-deploy/criteria \
  -H "Content-Type: application/json" \
  -d '{
    "min_score": 75.0,
    "max_per_day": 15,
    "max_per_hour": 5,
    "max_daily_cost": 3.0,
    "allowed_niches": [
      "smart_home",
      "fitness",
      "tech_gadgets",
      "kitchen",
      "beauty",
      "pet"
    ]
  }' | jq
```

### Example 3: Conservative Configuration
```bash
# Only deploy highest quality products
curl -X PUT http://localhost:8001/api/auto-deploy/criteria \
  -H "Content-Type: application/json" \
  -d '{
    "min_score": 90.0,
    "min_profit_margin": 0.45,
    "max_saturation": "low",
    "max_per_day": 2,
    "max_daily_cost": 0.50
  }' | jq
```

### Example 4: Test Configuration
```bash
# Update criteria
curl -X PUT http://localhost:8001/api/auto-deploy/criteria \
  -H "Content-Type: application/json" \
  -d '{"min_score": 75.0, "max_per_day": 1}' | jq

# Manually trigger deployment check
curl -X POST http://localhost:8001/api/auto-deploy/run-now | jq

# Check results
curl http://localhost:8001/api/auto-deploy/history?limit=5 | jq
```

### Example 5: Monitor Costs
```bash
# Get total cost
curl http://localhost:8001/api/auto-deploy/status | jq '.total_cost'

# Get deployment history with costs
curl http://localhost:8001/api/auto-deploy/history?limit=10 | \
  jq '[.[] | {product: .product_name, cost: .ai_cost}]'

# Calculate average cost per deployment
curl http://localhost:8001/api/auto-deploy/history?limit=100 | \
  jq '[.[] | .ai_cost] | add / length'
```

---

## Cost Analysis

### Per-Product Costs

| Component | Cost |
|-----------|------|
| Content Generation (Claude) | ~$0.02 |
| Image Enhancement (DALL-E 3) | ~$0.04 |
| **Total per product** | **~$0.06** |

### Monthly Projections

| Deployments/Day | Monthly Cost | Products/Month |
|-----------------|--------------|----------------|
| 1 | $1.80 | 30 |
| 5 (default) | $9.00 | 150 |
| 10 | $18.00 | 300 |
| 20 | $36.00 | 600 |

**Note:** Costs based on all AI features enabled. Can be reduced by disabling image enhancement.

---

## Safety Considerations

### Why Disabled by Default?

Auto-deployment is disabled by default because:
1. **Store control** - You should review your store's first products
2. **Criteria tuning** - Default criteria may not fit your niche
3. **Cost awareness** - AI costs accumulate over time
4. **Brand alignment** - Products should align with your brand

### Safety Mechanisms

1. **Draft-First Deployment**
   - All products saved as draft by default
   - Manual review required before publishing
   - Prevents accidental live deployments

2. **Daily Limits**
   - Prevents flooding your store
   - Allows gradual growth
   - Maintains product quality

3. **Cost Controls**
   - Daily spending limits
   - Cost tracking per deployment
   - Budget alerts

4. **Admin Notifications**
   - Email notification for each deployment
   - Includes product details and Shopify URL
   - Failure notifications for errors

5. **Deployment History**
   - Full audit trail
   - Filterable by date, niche, success
   - Cost tracking

---

## Database Schema

### `auto_deployments` Table

Tracks all auto-deployed products:

```sql
CREATE TABLE auto_deployments (
    id INTEGER PRIMARY KEY,
    product_id VARCHAR,
    product_name VARCHAR,
    niche VARCHAR,
    score FLOAT,
    profit_margin FLOAT,
    shopify_product_id VARCHAR,
    shopify_url VARCHAR,
    success BOOLEAN,
    error TEXT,
    ai_cost FLOAT,
    processing_time FLOAT,
    deployed_at DATETIME,
    criteria_snapshot TEXT  -- JSON snapshot of criteria used
)
```

### `auto_deploy_settings` Table

Stores configuration (singleton):

```sql
CREATE TABLE auto_deploy_settings (
    id INTEGER PRIMARY KEY,
    enabled BOOLEAN DEFAULT FALSE,
    criteria_json TEXT,
    last_run DATETIME,
    total_deployed INTEGER DEFAULT 0,
    total_cost FLOAT DEFAULT 0.0,
    updated_at DATETIME
)
```

**Database Location:** `./data/auto_deploy.db`

---

## Scheduler Configuration

### Default Schedule
- **Frequency:** Every hour
- **First Run:** 1 hour after server startup
- **Prevent Overlap:** Max 1 concurrent run

### Customizing Schedule

Edit `/ospra_os/background_jobs/auto_deploy_job.py`:

```python
# Change from hourly to every 30 minutes
self.scheduler.add_job(
    self.run_check,
    trigger="interval",
    minutes=30,  # Changed from hours=1
    id="auto_deploy_check",
    name="Auto-Deploy Check"
)
```

Or use cron syntax for specific times:

```python
# Run at 9 AM and 5 PM daily
self.scheduler.add_job(
    self.run_check,
    trigger="cron",
    hour="9,17",
    id="auto_deploy_check"
)
```

---

## Troubleshooting

### Issue: No Products Being Deployed

**Possible Causes:**
1. Auto-deploy is disabled
2. No products meet criteria
3. Daily limits reached
4. No products in allowed niches

**Debug Steps:**
```bash
# Check if enabled
curl http://localhost:8001/api/auto-deploy/status | jq '.enabled'

# Check criteria
curl http://localhost:8001/api/auto-deploy/status | jq '.criteria'

# Manually trigger to see logs
curl -X POST http://localhost:8001/api/auto-deploy/run-now | jq

# Lower criteria temporarily
curl -X PUT http://localhost:8001/api/auto-deploy/criteria \
  -H "Content-Type: application/json" \
  -d '{"min_score": 70.0}' | jq
```

### Issue: High AI Costs

**Solutions:**
1. Reduce `max_per_day`
2. Lower `max_daily_cost`
3. Disable image enhancement (save ~$0.04/product)
4. Increase `min_score` (deploy fewer, higher-quality products)

```bash
# Reduce costs
curl -X PUT http://localhost:8001/api/auto-deploy/criteria \
  -H "Content-Type: application/json" \
  -d '{
    "max_per_day": 3,
    "max_daily_cost": 0.50,
    "min_score": 85.0
  }' | jq
```

### Issue: Products Not Meeting Criteria

**Debug:**
```bash
# Check logs for product scores
tail -f logs/ospra_os.log | grep "Candidate:"

# Temporarily lower criteria
curl -X PUT http://localhost:8001/api/auto-deploy/criteria \
  -H "Content-Type: application/json" \
  -d '{"min_score": 60.0, "min_profit_margin": 0.25}' | jq

# Manually trigger
curl -X POST http://localhost:8001/api/auto-deploy/run-now | jq
```

### Issue: Scheduler Not Running

**Check:**
```bash
# Check logs for scheduler startup
grep "Auto-deploy scheduler" logs/ospra_os.log

# Manually trigger to test
curl -X POST http://localhost:8001/api/auto-deploy/run-now | jq

# Restart server
pkill -f "uvicorn ospra_os.main:app"
uv run uvicorn ospra_os.main:app --reload --host 0.0.0.0 --port 8001
```

---

## Best Practices

### 1. Start Conservative
```json
{
  "min_score": 85.0,
  "max_per_day": 2,
  "max_daily_cost": 0.50,
  "auto_publish": false
}
```

### 2. Monitor for 1 Week
- Review deployed products daily
- Check profit margins
- Verify product quality
- Monitor costs

### 3. Gradually Increase
```json
{
  "max_per_day": 5,
  "max_daily_cost": 1.0
}
```

### 4. Add More Niches
```json
{
  "allowed_niches": [
    "smart_home",
    "fitness",
    "tech_gadgets",
    "kitchen",
    "beauty"  // Added
  ]
}
```

### 5. Enable Publishing (When Confident)
```json
{
  "auto_publish": true  // Products go live immediately
}
```

---

## Files Created

1. `/ospra_os/services/auto_deployer.py` - Core service (600+ lines)
2. `/ospra_os/api/auto_deploy_routes.py` - API routes (350+ lines)
3. `/ospra_os/background_jobs/auto_deploy_job.py` - Scheduler integration (100+ lines)
4. `/docs/AUTO_DEPLOYMENT_SERVICE.md` - This documentation

## Files Modified

1. `/ospra_os/main.py` - Router and scheduler registration
   - Lines 312-320: Auto-deploy router import
   - Lines 872-873: Router registration
   - Lines 727-733: Scheduler startup

---

## Next Steps

### Recommended Enhancements

1. **A/B Testing Integration**
   - Deploy multiple variations
   - Track conversion rates
   - Auto-disable low performers

2. **ML-Based Criteria**
   - Learn from successful deployments
   - Adjust criteria automatically
   - Predictive scoring

3. **Smart Scheduling**
   - Deploy during high-traffic hours
   - Avoid weekends/holidays
   - Niche-specific timing

4. **Cost Optimization**
   - Batch processing for efficiency
   - Image enhancement caching
   - Content template reuse

5. **Advanced Notifications**
   - Webhook integration
   - Dashboard alerts
   - Performance reports

6. **Rollback Capability**
   - Auto-unpublish poor performers
   - Refund/return tracking
   - Quality monitoring

---

## Support

For issues or questions:
1. Check server logs: `tail -f logs/ospra_os.log`
2. Test manually: `POST /api/auto-deploy/run-now`
3. Review deployment history: `GET /api/auto-deploy/history`
4. Check health status: `GET /api/auto-deploy/health`

**Status:** ✅ Fully Operational
**Last Updated:** December 7, 2025
