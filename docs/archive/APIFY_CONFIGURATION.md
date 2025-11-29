c# Apify Product Discovery Configuration

## Status: Configuration Fixed (Partially Working)

### Overview

The product discovery system uses Apify actors to scrape real product data from multiple sources. The system has been configured correctly, but there are some limitations due to Apify account status.

### Fixed Configuration Issues

#### 1. Amazon Bestsellers Scraper ✅ FIXED
**Problem:** Actor required `categoryUrls` parameter but we were sending `startUrls`
**Fix:** Updated `amazon_bestsellers.py` to use correct parameter format
**File:** `ospra_os/product_research/connectors/apify/amazon_bestsellers.py:49`

```python
run_input = {
    "categoryUrls": [category_url],  # Changed from startUrls
    "maxItems": max_products,
    "country": country
}
```

#### 2. Shopify Competitor Scraper ✅ FIXED
**Problem:** Actor required `pageFunction` parameter for web scraping
**Fix:** Added JavaScript pageFunction to extract Shopify products.json
**File:** `ospra_os/product_research/connectors/apify/shopify_competitor.py:53-70`

```python
page_function = """
async function pageFunction(context) {
    const { request, page, log } = context;
    try {
        const response = await fetch(request.url + '/products.json');
        const data = await response.json();
        return { products: data.products || [] };
    } catch (error) {
        log.error('Failed to fetch products.json:', error);
        return { products: [] };
    }
}
"""
```

#### 3. Google Trends Keywords ✅ FIXED
**Problem:** No keywords configured for "smart_home" niche
**Fix:** Added comprehensive keyword list to TRENDING_KEYWORDS dictionary
**File:** `ospra_os/product_research/multi_source_discovery.py:66-75`

```python
"smart_home": [
    "smart home devices",
    "alexa smart home",
    "wifi smart plug",
    "smart light bulbs",
    "smart home security",
    "google home devices",
    "smart home hub",
    "smart thermostat"
]
```

### Current Limitations

#### TikTok Shop Scraper ⚠️ REQUIRES PAID CREDITS
**Status:** Apify account has insufficient credits ($0.38 remaining)
**Error:** `not-enough-usage-to-run-paid-actor`
**Actor:** `clockworks/tiktok-scraper`

**Solution Options:**
1. Upgrade Apify account to paid plan
2. Add more free credits to Apify account
3. Disable TikTok scraping temporarily (system will use other sources)

**To upgrade:** Visit https://console.apify.com/billing/subscription

### Working Data Sources

| Source | Status | Notes |
|--------|--------|-------|
| Google Trends | ✅ Working | FREE - No Apify credits needed |
| Amazon Bestsellers | ✅ Ready | Requires Apify credits |
| Shopify Competitors | ✅ Ready | Requires Apify credits |
| Reddit Sentiment | ✅ Ready | Requires Apify credits |
| TikTok Shop | ❌ Blocked | Account out of credits |

### Testing the System

Run the discovery test script:

```bash
uv run python test_discovery_fix.py
```

Expected behavior:
- TikTok: Will fail with billing error (expected)
- Amazon: Should work if you have Apify credits
- Shopify: Should work if you have Apify credits
- Google Trends: Should work (doesn't use Apify)

### Environment Variables

Required `.env` configuration:

```env
# Apify Configuration
APIFY_API_TOKEN=your_token_here
APIFY_USER_ID=your_user_id_here

# Optional: Amazon PA-API (for enhanced product data)
AMAZON_ACCESS_KEY=your_key_here
AMAZON_SECRET_KEY=your_secret_here
AMAZON_PARTNER_TAG=your_tag_here

# Optional: AliExpress API (for dropship pricing)
ALIEXPRESS_APP_KEY=your_key_here
ALIEXPRESS_APP_SECRET=your_secret_here
```

### Fallback Behavior

When Apify actors fail (due to credits or configuration), the system will:
1. Log the error
2. Return empty results for that source
3. Continue with other available sources
4. Use Google Trends as the primary free source

This means the system is resilient and will work even with limited Apify access.

## Next Steps

1. **For Production:** Upgrade Apify account to ensure all scrapers work
2. **For Testing:** Google Trends alone can provide trending products
3. **Alternative:** Consider using different free Apify actors or direct API integrations

---

**Last Updated:** 2025-11-23
**Status:** Configurations fixed, waiting on Apify account upgrade
