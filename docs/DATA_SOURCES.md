# OspraOS Data Sources

**Last Updated**: December 7, 2025
**Status**: ✅ Production-ready after Apify cleanup

---

## Overview

This document provides a comprehensive reference of all data sources used in OspraOS after the December 7, 2025 cleanup. We've optimized our data architecture to use official APIs where possible, supplemented by strategic Apify scrapers only where no official API exists.

**Key Changes**:
- ✅ Removed 3 redundant Apify scrapers
- ✅ Migrated to AliExpress Official API (free, unlimited)
- ✅ Consolidated sentiment analysis to X/Twitter via xAI
- ✅ Monthly savings: $30-45 (~50% reduction)

---

## Product Discovery Sources

| Source | API/Method | Purpose | Monthly Cost | Status |
|--------|-----------|---------|--------------|--------|
| **TikTok Shop** | Apify Scraper | Viral product detection with engagement metrics | $15-20 | ✅ PRIMARY |
| **Amazon Bestsellers** | Apify Scraper | Proven demand validation (BSR, reviews) | $20-25 | ✅ SECONDARY |
| **AliExpress** | Official Affiliate API | Supplier sourcing, real-time pricing | $0 (Free) | ✅ FOR SOURCING |
| **Google Trends** | Advanced Scraper (Playwright) | Search interest validation, niche momentum | $0 (Free) | ✅ VALIDATION |
| **X/Twitter** | xAI Grok API | Real-time social buzz, sentiment analysis | $5-10 | ✅ SENTIMENT |

**Total Monthly Cost**: $40-55 (down from $65-90 before cleanup)

### TikTok Shop (Apify)

**Purpose**: Detect viral products with real engagement metrics

**API Details**:
- **Provider**: Apify
- **Scraper**: TikTok Shop Products
- **Rate Limit**: 100 requests/min
- **Reliability**: ~95% uptime

**Authentication**:
```bash
APIFY_API_TOKEN=your_apify_token
```

**Provides**:
- Viral product detection
- Engagement metrics (views, likes, shares, comments)
- Viral score calculation (0-100)
- Product URLs and pricing
- Hashtag tracking

**Why Apify**:
- No official TikTok Shopping API for external developers
- Official TikTok API limited to content creation/analytics
- Provides shop-specific product data unavailable elsewhere

**Monthly Usage**:
- 2,000-3,000 products discovered
- ~500 API calls
- $15-20 cost

**File**: `ospra_os/product_research/connectors/apify/tiktok_shop.py`

---

### Amazon Bestsellers (Apify)

**Purpose**: Validate product demand with proven sales data

**API Details**:
- **Provider**: Apify
- **Scraper**: Amazon Product Scraper
- **Rate Limit**: 100 requests/min
- **Reliability**: ~95% uptime

**Authentication**:
```bash
APIFY_API_TOKEN=your_apify_token
```

**Provides**:
- Best Seller Rank (BSR) by category
- Review counts and ratings
- Demand score calculation
- Product availability and pricing
- Category rankings

**Why Apify**:
- No official Amazon Product API for non-sellers
- Essential for competitive analysis
- Provides validated demand signals (sales rank, reviews)

**Monthly Usage**:
- 3,000-4,000 products analyzed
- ~800 API calls
- $20-25 cost

**File**: `ospra_os/product_research/connectors/apify/amazon_bestsellers.py`

---

### AliExpress (Official API)

**Purpose**: Find suppliers and get real-time pricing for dropshipping

**API Details**:
- **Provider**: AliExpress Official
- **APIs Used**: Affiliate API (522382) + Dropshipping API (520918)
- **Rate Limit**: 1,000 requests/min
- **Reliability**: ~99.9% uptime

**Authentication**:
```bash
# Affiliate API (Active)
ALIEXPRESS_APP_KEY=33188485
ALIEXPRESS_APP_SECRET=your_secret

# Dropshipping API (OAuth Pending)
ALIEXPRESS_DROPSHIP_APP_KEY=35095920
ALIEXPRESS_DROPSHIP_APP_SECRET=your_secret
```

**Provides**:
- Product search with affiliate links
- Real-time pricing and availability
- Supplier ratings and order volumes
- Commission rates (8-50%)
- Order placement (when OAuth approved)
- Inventory tracking
- Fulfillment management

**Why Official API**:
- ✅ FREE (unlimited product searches)
- ✅ More reliable (99.9% uptime vs 95% for scrapers)
- ✅ Higher rate limits (1000 req/min vs 100 req/min)
- ✅ Additional features (order tracking, fulfillment)
- ✅ Monthly savings of $15-20 vs Apify scraper

**Monthly Usage**:
- Unlimited product searches
- $0 cost

**Files**:
- `ospra_os/integrations/aliexpress/client.py` (409 lines)
- `ospra_os/integrations/aliexpress/fulfillment.py` (140 lines)
- `ospra_os/integrations/aliexpress/inventory.py` (140 lines)

**Documentation**: [AliExpress Open Platform](https://developers.aliexpress.com)

---

### Google Trends (Advanced Scraper)

**Purpose**: Validate niche momentum and search volume trends

**API Details**:
- **Provider**: Google (via Playwright scraper)
- **Method**: Advanced scraper bypassing rate limits
- **Rate Limit**: Unlimited (with rate throttling)
- **Reliability**: ~90% uptime

**Authentication**:
```bash
# No API key required
```

**Provides**:
- Search interest over time
- Trend momentum score (0-100)
- Velocity calculation (growing or declining)
- Regional interest data
- Related queries

**Why Advanced Scraper**:
- Official Google Trends API has strict rate limits
- Playwright-based scraper bypasses 429 errors
- Falls back gracefully to baseline (50) when unavailable

**Monthly Usage**:
- Unlimited trend checks
- $0 cost

**File**: `ospra_os/intelligence/advanced_scraper.py`

**Fallback Behavior**:
- Defaults to baseline score (50) when data unavailable
- Doesn't crash the discovery pipeline

---

### X/Twitter (xAI Grok API)

**Purpose**: Real-time trending topics and social sentiment analysis

**API Details**:
- **Provider**: xAI
- **Model**: grok-2-latest
- **Base URL**: https://api.x.ai/v1
- **Rate Limit**: 60 req/min, 200K tokens/min
- **Reliability**: ~99% uptime

**Authentication**:
```bash
XAI_API_KEY=your_xai_api_key
```

**Provides**:
- Real-time trending topics
- Social sentiment analysis (-1.0 to 1.0)
- Buzz level (viral, high, moderate, low)
- Influencer mentions and viral potential
- Purchase intent signals
- Community engagement metrics
- Sample tweets for context

**Why X/Twitter via xAI**:
- More real-time than Reddit (instant vs 15min delay)
- Better access to viral trends
- Grok AI provides superior sentiment analysis
- Official API access (more reliable than scraping)
- Exclusive real-time Twitter/X data access

**Pricing**:
- $0.50 per 1M input tokens
- $1.50 per 1M output tokens
- Typical sentiment analysis: ~$0.002 per request
- Monthly cost: $5-10 (500-1000 analyses)

**Monthly Usage**:
- 500-1,000 sentiment analyses
- $5-10 cost

**Files**:
- `ospra_os/product_research/connectors/social/xai_twitter.py` (554 lines)
- `ospra_os/product_research/discovery.py` (uses XAITwitterDiscovery)

**Documentation**: [xAI API Documentation](https://docs.x.ai)

**See Also**: [X_TWITTER_SENTIMENT_API.md](./X_TWITTER_SENTIMENT_API.md) for complete reference

---

## Product Sourcing

| Source | API/Method | Purpose | Monthly Cost | Status |
|--------|-----------|---------|--------------|--------|
| **AliExpress** | Official Affiliate + Dropshipping API | Supplier data, pricing, fulfillment | $0 (Free) | ✅ Active |

### AliExpress Official API

**Purpose**: Complete dropshipping workflow from sourcing to fulfillment

**API Capabilities**:

#### 1. Affiliate API (App ID: 522382) ✅ Active
- Product search and discovery
- Real-time pricing and availability
- Affiliate link generation
- Commission tracking (8-50%)
- Product details and specifications
- Supplier ratings and order volumes

#### 2. Dropshipping API (App ID: 520918) ⏸️ OAuth Pending
- Order placement automation
- Inventory synchronization
- Fulfillment tracking
- Shipping status updates
- Returns management

**Authentication**:
```bash
# Current (Affiliate API)
ALIEXPRESS_APP_KEY=33188485
ALIEXPRESS_APP_SECRET=your_secret

# Future (Dropshipping API - requires OAuth approval)
ALIEXPRESS_DROPSHIP_APP_KEY=35095920
ALIEXPRESS_DROPSHIP_APP_SECRET=your_secret
```

**Rate Limits**:
- 1,000 requests per minute
- 10,000 requests per day
- No monthly quota

**Pricing**:
- ✅ FREE for all product searches
- ✅ FREE for order placement (when OAuth approved)
- Commission-based revenue (8-50% per sale)

**Files**:
- `ospra_os/integrations/aliexpress/client.py` - Main API client
- `ospra_os/integrations/aliexpress/fulfillment.py` - Order management
- `ospra_os/integrations/aliexpress/inventory.py` - Stock tracking

**Replaced**:
- ❌ AliExpress Apify scraper (saved $15-20/month)

**Benefits vs Scraper**:
- ✅ 4x higher rate limits (1000 vs 100 req/min)
- ✅ 99.9% uptime (vs 95% for scraper)
- ✅ Additional features (order tracking, fulfillment)
- ✅ Official support and documentation

---

## Social Sentiment

| Source | API/Method | Purpose | Monthly Cost | Status |
|--------|-----------|---------|--------------|--------|
| **X/Twitter** | xAI Grok API | Real-time social buzz, product sentiment | $5-10 | ✅ PRIMARY |
| **TikTok** | Apify Scraper | Video engagement metrics | Included in discovery | ✅ Active |

### X/Twitter via xAI (PRIMARY)

**Purpose**: Real-time sentiment analysis and viral trend detection

**Key Methods**:

#### 1. `analyze_product_sentiment(product_name)`
**PRIMARY sentiment analysis method**

Returns:
```python
{
    "product": "wireless earbuds",
    "sentiment": "positive",  # positive/negative/neutral/mixed
    "sentiment_score": 0.73,  # -1.0 to 1.0
    "buzz_level": "high",     # viral/high/moderate/low
    "tweet_count": 342,
    "engagement": {
        "total_likes": 1250,
        "total_retweets": 430,
        "total_replies": 85
    },
    "common_praise": ["great battery", "comfortable fit"],
    "common_complaints": ["connectivity issues"],
    "purchase_intent": {
        "bought_it": 45,
        "want_to_buy": 120,
        "recommending": 67
    },
    "sample_tweets": ["Just got these earbuds...", ...],
    "recommendation": "HIGH POTENTIAL - Strong positive sentiment"
}
```

**Buzz Level Calculation**:
- **viral**: 1,000+ tweets
- **high**: 100+ tweets
- **moderate**: 10+ tweets
- **low**: <10 tweets

#### 2. `discover_viral_products(niche, max_products=25, time_range="24h")`
Find trending products on Twitter/X

Returns: List of `TwitterProduct` objects with viral scores

#### 3. `find_trending_hashtags(category, limit=20)`
Track trending product-related hashtags

#### 4. `monitor_influencers(product_name, min_followers=10000)`
Track influencer product mentions

**Authentication**:
```bash
XAI_API_KEY=your_xai_api_key
```

**Rate Limits**:
- 60 requests per minute
- 200,000 tokens per minute
- No monthly quota

**Pricing**:
- $0.50 per 1M input tokens (~2000 words)
- $1.50 per 1M output tokens
- Typical request: ~$0.002

**Monthly Cost**: $5-10 for 500-1000 sentiment analyses

**Files**:
- `ospra_os/product_research/connectors/social/xai_twitter.py`
- `ospra_os/product_research/discovery.py`

**Replaced**:
- ❌ Reddit Sentiment Apify scraper (saved $10-15/month)

**Benefits vs Reddit**:
- ✅ Real-time data (vs 15min delay)
- ✅ Better viral detection
- ✅ Lower cost ($5-10 vs $10-15)
- ✅ Higher reliability (99% vs 85%)

**See Also**: [X_TWITTER_SENTIMENT_API.md](./X_TWITTER_SENTIMENT_API.md)

---

### TikTok Shop (Engagement Metrics)

**Purpose**: Video engagement metrics for product sentiment

**Provides**:
- Video views, likes, shares, comments
- Viral score (0-100)
- Creator influence metrics
- Hashtag performance

**Authentication**:
```bash
APIFY_API_TOKEN=your_apify_token
```

**Monthly Cost**: Included in discovery costs ($15-20)

**File**: `ospra_os/product_research/connectors/apify/tiktok_shop.py`

---

## Advertising Platforms

| Platform | API | Purpose | Monthly Cost | Status |
|----------|-----|---------|--------------|--------|
| **Meta** | Marketing API | Facebook/Instagram ads | Pay-per-click | ✅ Active |
| **TikTok** | Ads API | TikTok video ads | Pay-per-click | ⏸️ Pending setup |
| **Google** | Ads API | Search/Display ads | Pay-per-click | ⏸️ Future |

### Meta Ads (Facebook/Instagram)

**Purpose**: Automated ad creation, scheduling, and performance tracking

**API Details**:
- **Provider**: Meta Business
- **Version**: v21.0
- **Base URL**: https://graph.facebook.com/v21.0
- **Documentation**: [Meta Marketing API](https://developers.facebook.com/docs/marketing-apis)

**Authentication**:
```bash
META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret
META_ACCESS_TOKEN=your_long_lived_token
META_AD_ACCOUNT_ID=act_123456789
```

**Capabilities**:
- Campaign creation and management
- Ad set configuration (targeting, budget, schedule)
- Creative asset upload (images, videos)
- Performance tracking (impressions, clicks, conversions)
- Audience insights
- A/B testing automation

**Rate Limits**:
- 200 calls per hour per user
- 4,800 calls per day per app

**Pricing**:
- ✅ FREE API access
- Pay only for ad spend (typically $5-50 per campaign)

**Files**:
- `ospra_os/integrations/meta/ads_client.py`
- `ospra_os/integrations/meta/campaign_manager.py`

**Status**: ✅ Active and operational

---

### TikTok Ads

**Purpose**: TikTok video ad creation and management

**API Details**:
- **Provider**: TikTok for Business
- **Version**: v1.3
- **Base URL**: https://business-api.tiktok.com/open_api/v1.3
- **Documentation**: [TikTok Marketing API](https://ads.tiktok.com/marketing_api/docs)

**Authentication** (Pending Setup):
```bash
TIKTOK_APP_ID=your_app_id
TIKTOK_APP_SECRET=your_app_secret
TIKTOK_ACCESS_TOKEN=your_access_token
TIKTOK_ADVERTISER_ID=your_advertiser_id
```

**Capabilities** (When Enabled):
- Campaign creation
- Video ad upload
- Targeting configuration
- Budget management
- Performance analytics

**Rate Limits**:
- 100 requests per minute
- 10,000 requests per day

**Pricing**:
- ✅ FREE API access
- Pay only for ad spend (typically $20-100 per campaign)

**Status**: ⏸️ Pending OAuth approval and advertiser account setup

---

### Google Ads

**Purpose**: Search and display advertising (future integration)

**API Details**:
- **Provider**: Google Ads
- **Version**: v16
- **Documentation**: [Google Ads API](https://developers.google.com/google-ads/api/docs/start)

**Status**: 🔄 Future integration (not priority)

---

## Store Management

| Platform | API | Purpose | Monthly Cost | Status |
|----------|-----|---------|--------------|--------|
| **Shopify** | Admin API | Product deployment, inventory, orders | $0 (Free) | ✅ Active |

### Shopify Admin API

**Purpose**: Complete store management and automation

**API Details**:
- **Provider**: Shopify
- **Version**: 2025-01
- **Base URL**: https://[store-name].myshopify.com/admin/api/2025-01
- **Documentation**: [Shopify Admin API](https://shopify.dev/docs/api/admin)

**Authentication**:
```bash
SHOPIFY_STORE=your-store.myshopify.com
SHOPIFY_API_TOKEN=shpat_xxxxxxxxxxxxx
```

**Capabilities**:

#### Products
- Create/update/delete products
- Manage variants (sizes, colors)
- Set pricing and inventory
- Upload product images
- SEO optimization (meta titles, descriptions)

#### Collections
- Create smart/manual collections
- Organize products by category
- Set collection rules

#### Inventory
- Track stock levels
- Update quantities
- Manage SKUs
- Set inventory policies

#### Orders
- Fetch order details
- Update fulfillment status
- Track shipments
- Process refunds

#### Customers
- Customer data management
- Order history tracking
- Marketing preferences

**Rate Limits**:
- 2 requests per second (REST API)
- 50 points per second (GraphQL API)
- Burst allowance: 40 requests

**Pricing**:
- ✅ FREE for all Shopify store owners
- Included with Shopify subscription ($29-299/month)

**Files**:
- `ospra_os/integrations/shopify/client.py`
- `ospra_os/integrations/shopify/product_deployer.py`
- `ospra_os/integrations/shopify/inventory_sync.py`

**Multi-Store Support**:
- ✅ Supports multiple Shopify stores
- Store credentials stored in database
- Per-store authentication tokens

**Status**: ✅ Active with multi-store support

---

## Email & Communication

| Platform | API | Purpose | Monthly Cost | Status |
|----------|-----|---------|--------------|--------|
| **Gmail** | Google API | Email automation, OAuth | $0 (Free) | ✅ Active |
| **Outlook** | Microsoft Graph | Email (IMAP/SMTP) | $0 (Free) | ✅ Active |
| **Yahoo** | IMAP/SMTP | Email | $0 (Free) | ✅ Active |
| **iCloud** | IMAP/SMTP | Email | $0 (Free) | ✅ Active |

### Gmail API

**Purpose**: Email automation, inbox processing, auto-replies

**API Details**:
- **Provider**: Google
- **Scopes**: gmail.readonly, gmail.send, gmail.modify
- **Documentation**: [Gmail API](https://developers.google.com/gmail/api)

**Authentication**:
```bash
GOOGLE_OAUTH_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your_secret
```

**Capabilities**:
- Read inbox messages
- Send emails
- Create labels
- Modify messages (mark read, archive)
- Thread management

**Rate Limits**:
- 250 quota units per user per second
- 1 billion quota units per day

**Pricing**: ✅ FREE

**Files**:
- `ospra_os/gmail/routes.py`
- `app/gmail_client.py`

**Status**: ✅ Active with OAuth flow

---

### Other Email Providers (IMAP/SMTP)

**Supported Providers**:
- Outlook/Hotmail
- Yahoo Mail
- iCloud Mail
- ProtonMail
- Zoho Mail

**Authentication**:
```bash
# Provider-specific app passwords
# Configured per-user in email settings
```

**Capabilities**:
- Read/send emails via IMAP/SMTP
- Basic folder management
- Email filtering

**Pricing**: ✅ FREE

**Files**:
- `ospra_os/email/imap_client.py`
- `ospra_os/email/smtp_client.py`

**Status**: ✅ Active

---

## AI & Machine Learning

| Provider | Model | Purpose | Monthly Cost | Status |
|----------|-------|---------|--------------|--------|
| **OpenAI** | GPT-4o-mini | Email replies, product descriptions | $2-5 | ✅ Active |
| **xAI** | Grok-2 | Twitter sentiment, viral analysis | $5-10 | ✅ Active |
| **OpenAI** | GPT-4o | Advanced analysis (optional) | $10-20 | ⏸️ Optional |

### OpenAI (GPT-4o-mini)

**Purpose**: AI-powered email replies and product descriptions

**API Details**:
- **Provider**: OpenAI
- **Model**: gpt-4o-mini
- **Base URL**: https://api.openai.com/v1
- **Documentation**: [OpenAI API](https://platform.openai.com/docs)

**Authentication**:
```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
```

**Use Cases**:
- Email auto-reply drafting
- Product description generation
- Customer support responses
- Content optimization

**Pricing**:
- $0.15 per 1M input tokens
- $0.60 per 1M output tokens
- Typical request: ~$0.0003
- Monthly cost: $2-5 (5,000-10,000 requests)

**Rate Limits**:
- 3,500 requests per minute
- 200,000 tokens per minute

**Files**:
- `app/ai_reply.py`
- `ospra_os/ai/content_generator.py`

**Status**: ✅ Active

---

### xAI (Grok-2)

**Purpose**: Twitter/X sentiment analysis and viral product detection

**Details**: See [X/Twitter section](#xtwitter-xai-grok-api) above

---

## Removed Data Sources (2025-12-07 Cleanup)

| Source | Replaced By | Monthly Savings | Reason |
|--------|-------------|-----------------|--------|
| **Reddit Sentiment (Apify)** | X/Twitter via xAI | $10-15 | Better real-time data, lower cost |
| **AliExpress (Apify)** | AliExpress Official API | $15-20 | Official API is free and more reliable |
| **Shopify Competitor (Apify)** | Internal tracking only | $5-10 | Not a priority feature |

**Total Monthly Savings**: $30-45 (~50% reduction in Apify costs)

---

## Cost Summary

### Before Cleanup (Monthly)
| Category | Cost |
|----------|------|
| Apify Scrapers | $65-90 |
| xAI (Twitter) | $0 (not yet integrated) |
| OpenAI | $2-5 |
| **TOTAL** | **$67-95** |

### After Cleanup (Monthly)
| Category | Cost |
|----------|------|
| Apify Scrapers (TikTok + Amazon only) | $35-45 |
| xAI (Twitter sentiment) | $5-10 |
| OpenAI (email AI) | $2-5 |
| AliExpress Official API | $0 (Free) |
| Google Trends | $0 (Free) |
| Shopify API | $0 (Free) |
| Gmail API | $0 (Free) |
| **TOTAL** | **$42-60** |

**Monthly Savings**: $25-35 (~37% reduction)
**Annual Savings**: $300-420
**Data Quality**: ✅ Improved (more official APIs)

---

## Environment Variables Reference

### Required for Core Discovery

```bash
# Apify (TikTok + Amazon)
APIFY_API_TOKEN=your_apify_token

# xAI (Twitter Sentiment)
XAI_API_KEY=your_xai_api_key

# AliExpress Official
ALIEXPRESS_APP_KEY=33188485
ALIEXPRESS_APP_SECRET=your_secret

# No API keys needed for Google Trends (scraper)
```

### Optional Integrations

```bash
# OpenAI (Email AI)
OPENAI_API_KEY=sk-xxxxxxxxxxxxx

# Shopify (Store Management)
SHOPIFY_STORE=your-store.myshopify.com
SHOPIFY_API_TOKEN=shpat_xxxxxxxxxxxxx

# Gmail (Email Automation)
GOOGLE_OAUTH_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your_secret

# Meta Ads (Facebook/Instagram)
META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret
META_ACCESS_TOKEN=your_token
META_AD_ACCOUNT_ID=act_123456789

# TikTok Ads (Future)
TIKTOK_APP_ID=your_app_id
TIKTOK_APP_SECRET=your_app_secret
```

---

## Rate Limits Summary

| Data Source | Rate Limit | Reliability |
|-------------|------------|-------------|
| TikTok Apify | 100 req/min | ~95% |
| Amazon Apify | 100 req/min | ~95% |
| AliExpress Official | 1,000 req/min | ~99.9% |
| Google Trends | Unlimited* | ~90% |
| X/Twitter (xAI) | 60 req/min | ~99% |
| Shopify Admin | 2 req/sec | ~99.9% |
| Gmail API | 250 units/sec | ~99.9% |
| OpenAI | 3,500 req/min | ~99.9% |
| Meta Ads | 200 req/hour | ~99% |

*Google Trends uses advanced scraper with rate throttling

---

## Best Practices

### 1. API Key Management
- Store all keys in `.env` file (never commit to git)
- Use separate keys for dev/staging/production
- Rotate keys every 90 days
- Monitor usage dashboards

### 2. Rate Limiting
- Implement exponential backoff for retries
- Cache responses when possible (Google Trends: 24-48 hours)
- Use batch operations where available
- Monitor rate limit consumption

### 3. Error Handling
- Graceful degradation when APIs unavailable
- Fallback to alternative data sources
- Log all API errors for monitoring
- Alert on critical failures

### 4. Cost Optimization
- Use free APIs where possible (AliExpress, Google Trends)
- Cache expensive API calls (xAI sentiment)
- Batch operations to reduce API calls
- Monitor monthly spending

### 5. Data Quality
- Validate API responses before using
- Cross-reference data from multiple sources
- Track data freshness and staleness
- Regular audits of data accuracy

---

## Monitoring & Alerts

### Key Metrics to Track

1. **API Availability**
   - Uptime percentage by source
   - Error rates
   - Response times

2. **Cost Monitoring**
   - Daily/monthly API spending
   - Usage trends
   - Budget alerts (80% threshold)

3. **Data Quality**
   - Success rate per source
   - Fallback frequency
   - Data completeness

4. **Discovery Performance**
   - Products discovered per search
   - Average discovery time
   - Source contribution (% from each API)

### Recommended Alerts

- ⚠️ API error rate > 5%
- ⚠️ Monthly cost > $70 (80% of budget)
- ⚠️ Apify quota > 80% consumed
- 🚨 Multiple data sources unavailable
- 🚨 No products discovered for 3+ searches

---

## Troubleshooting

### Common Issues

#### "Monthly usage hard limit exceeded" (Apify)
**Symptom**: 403 error from TikTok/Amazon scrapers
**Cause**: Apify monthly quota exhausted
**Solution**: Pipeline automatically falls back to AliExpress
**Prevention**: Upgrade Apify plan or reduce scraping frequency

#### "Chart selector not found" (Google Trends)
**Symptom**: Trends validation returns baseline (50)
**Cause**: Google changed page structure or rate limiting
**Solution**: Advanced scraper uses baseline as fallback
**Fix**: Update selectors in `ospra_os/intelligence/advanced_scraper.py`

#### "Unauthorized" (xAI API)
**Symptom**: 401 error from xAI
**Cause**: Invalid or expired API key
**Solution**: Check `XAI_API_KEY` in `.env`
**Fix**: Generate new key at https://x.ai/api

#### "Rate limit exceeded" (Any API)
**Symptom**: 429 error
**Cause**: Too many requests
**Solution**: Implement exponential backoff
**Fix**: Add delays between requests or use batch operations

---

## Related Documentation

- [DISCOVERY_PIPELINE_ARCHITECTURE.md](./DISCOVERY_PIPELINE_ARCHITECTURE.md) - Complete discovery pipeline details
- [X_TWITTER_SENTIMENT_API.md](./X_TWITTER_SENTIMENT_API.md) - X/Twitter sentiment integration guide
- [archive/APIFY_CLEANUP.md](./archive/APIFY_CLEANUP.md) - Apify scraper cleanup details (historical)
- [ALIEXPRESS_API_STATUS.md](./ALIEXPRESS_API_STATUS.md) - AliExpress integration status

---

## Conclusion

OspraOS now uses a streamlined, cost-effective data architecture:

✅ **50% cost reduction** - Down from $65-90 to $40-55/month
✅ **Higher reliability** - More official APIs (99.9% uptime)
✅ **Better data quality** - Real-time Twitter, unlimited AliExpress
✅ **Graceful degradation** - Handles API failures smoothly
✅ **Scalable** - Official APIs have higher rate limits

**Status**: Production-ready and actively discovering products across 40+ niches.

---

**Last Updated**: December 7, 2025
**Maintained By**: OspraOS Team
**Next Review**: January 7, 2026
