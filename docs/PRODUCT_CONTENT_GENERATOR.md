# Product Content Generator - AI-Powered Product Listings

## Overview

**ProductContentGenerator** is an AI-powered service that transforms raw AliExpress/Amazon product data into professional, SEO-optimized Shopify listings using Claude Sonnet 4.5.

**Features:**
- ✅ Clean, SEO-friendly product titles
- ✅ Compelling product descriptions (short + long formats)
- ✅ Complete SEO metadata (meta tags, keywords, slugs)
- ✅ Competitive pricing suggestions with psychological pricing
- ✅ One-call complete listing generation
- ✅ Built-in rate limiting (50 calls/min)
- ✅ Cost tracking and usage analytics

**Model:** `claude-sonnet-4-20250514` (latest, cost-efficient)

**Cost:** ~$0.01-0.03 per product

## Installation

The service is already included in `/ospra_os/services/product_content_generator.py`.

**Requirements:**
- `anthropic` Python package (already in dependencies)
- `ANTHROPIC_API_KEY` environment variable

## Quick Start

### Basic Usage

```python
from ospra_os.services.product_content_generator import ProductContentGenerator

# Initialize
generator = ProductContentGenerator()

# Generate complete listing
aliexpress_data = {
    "title": "2024 New Smart LED Bulb WiFi RGB Color Changing Light E27 Alexa Google Home",
    "features": [
        "WiFi connectivity",
        "RGB color changing (16 million colors)",
        "Works with Alexa and Google Home",
        "E27 base, fits standard sockets",
        "Energy efficient LED"
    ],
    "category": "Smart Lighting",
    "price": 12.99,
    "images": ["https://..."]
}

listing = await generator.generate_complete_listing(
    aliexpress_data=aliexpress_data,
    niche="smart_home",
    brand_name="Oubon Shop"
)

# listing contains:
# - title: "Smart WiFi LED Bulb - RGB Color Changing, Works with Alexa & Google Home"
# - description_html: Full HTML product page content
# - short_description: 1-2 sentence preview
# - bullet_points: Key features as bullets
# - seo: {meta_title, meta_description, url_slug, keywords, image_alt_text}
# - pricing: {suggested_price, min_viable_price, premium_price, margin, rationale}
# - tags: Product tags for Shopify
# - product_type: Category
# - vendor: Brand name
```

## API Reference

### Class: `ProductContentGenerator`

#### `__init__(api_key: Optional[str] = None, rate_limit: int = 50)`

Initialize the generator.

**Parameters:**
- `api_key` (str, optional): Anthropic API key. Falls back to `ANTHROPIC_API_KEY` env var.
- `rate_limit` (int): Max API calls per minute (default: 50)

**Example:**
```python
# Use env var
generator = ProductContentGenerator()

# Or provide key directly
generator = ProductContentGenerator(api_key="sk-ant-...")

# Custom rate limit
generator = ProductContentGenerator(rate_limit=30)
```

---

### Method: `generate_product_title()`

Transform ugly AliExpress titles into clean, professional titles.

```python
async def generate_product_title(
    original_title: str,
    product_category: str,
    brand_voice: str = "modern, minimal, premium"
) -> str
```

**Parameters:**
- `original_title`: Raw AliExpress title (usually messy)
- `product_category`: Product category (e.g., "Smart Lighting")
- `brand_voice`: Brand tone (default: "modern, minimal, premium")

**Returns:** Clean, optimized product title (under 70 chars)

**Example:**
```python
title = await generator.generate_product_title(
    original_title="2024 New Smart LED Bulb WiFi RGB Color Changing Light E27 Alexa Google Home",
    product_category="Smart Lighting"
)
# Result: "Smart WiFi LED Bulb - RGB Color Changing, Works with Alexa & Google Home"
```

**Title Optimization:**
- ✅ Removes spam keywords ("2024", "New", "Hot Sale")
- ✅ Under 70 characters (Shopify best practice)
- ✅ SEO-friendly (includes key search terms)
- ✅ Highlights 1-2 key features
- ✅ Professional formatting

---

### Method: `generate_product_description()`

Generate complete product description with multiple formats.

```python
async def generate_product_description(
    product_name: str,
    features: List[str],
    category: str,
    target_audience: str = "homeowners interested in smart home technology",
    tone: str = "professional yet approachable",
    include_specs: bool = True
) -> Dict
```

**Parameters:**
- `product_name`: Product name
- `features`: List of product features
- `category`: Product category
- `target_audience`: Who is this for?
- `tone`: Writing tone
- `include_specs`: Include technical specs section

**Returns:**
```python
{
    "short_description": "1-2 sentence preview for product cards",
    "long_description": "Full HTML formatted product page content",
    "bullet_points": ["Feature 1", "Feature 2", ...],
    "meta_description": "SEO meta description (155 chars max)",
    "generated_at": "2024-12-06T12:34:56"
}
```

**Example:**
```python
description = await generator.generate_product_description(
    product_name="Smart WiFi LED Bulb",
    features=[
        "WiFi connectivity",
        "RGB color changing (16 million colors)",
        "Works with Alexa and Google Home"
    ],
    category="Smart Lighting",
    target_audience="smart home enthusiasts"
)

print(description["short_description"])
# "Transform your home lighting with our WiFi-enabled RGB LED bulb,
#  featuring 16 million colors and seamless voice control."

print(description["bullet_points"])
# ["WiFi connectivity for smartphone control",
#  "16 million color options",
#  "Compatible with Alexa & Google Home", ...]
```

**Description Features:**
- ✅ Benefit-focused (not just features)
- ✅ HTML formatted for Shopify
- ✅ Scannable (short paragraphs, bullet points)
- ✅ Includes social proof hooks
- ✅ Strong call-to-action

---

### Method: `generate_seo_content()`

Generate SEO-optimized metadata.

```python
async def generate_seo_content(
    product_name: str,
    category: str,
    description: str
) -> Dict
```

**Parameters:**
- `product_name`: Product name
- `category`: Product category
- `description`: Product description

**Returns:**
```python
{
    "meta_title": "60 chars max, keyword-focused",
    "meta_description": "155 chars max, compelling preview",
    "url_slug": "product-name-slug",
    "keywords": {
        "primary": "main search term",
        "secondary": ["keyword1", "keyword2", "keyword3"]
    },
    "image_alt_text": "Descriptive alt text for main image"
}
```

**Example:**
```python
seo = await generator.generate_seo_content(
    product_name="Smart WiFi LED Bulb",
    category="Smart Lighting",
    description="Transform your home lighting with WiFi-enabled RGB..."
)

print(seo["meta_title"])
# "Smart WiFi LED Bulb | RGB Color Changing | Oubon Shop"

print(seo["url_slug"])
# "smart-wifi-led-bulb-rgb"

print(seo["keywords"]["primary"])
# "smart led bulb"
```

**SEO Best Practices:**
- ✅ Meta title: 60 chars max, keyword at start
- ✅ Meta description: 155 chars, includes CTA
- ✅ URL slug: Lowercase, hyphens, keyword-rich
- ✅ Keywords: Primary + 5 secondary terms
- ✅ Alt text: Descriptive, under 125 chars

---

### Method: `suggest_competitive_price()`

Suggest optimal pricing with psychological pricing.

```python
async def suggest_competitive_price(
    cost_price: float,
    category: str,
    competitor_prices: Optional[List[float]] = None,
    target_margin: float = 0.4
) -> Dict
```

**Parameters:**
- `cost_price`: Product cost (AliExpress price)
- `category`: Product category
- `competitor_prices`: Optional list of competitor prices
- `target_margin`: Target profit margin (default: 40%)

**Returns:**
```python
{
    "suggested_price": 29.99,
    "min_viable_price": 24.99,
    "premium_price": 39.99,
    "margin_at_suggested": 0.42,
    "pricing_rationale": "Explanation of pricing strategy..."
}
```

**Example:**
```python
pricing = await generator.suggest_competitive_price(
    cost_price=12.99,
    category="Smart Lighting",
    competitor_prices=[24.99, 29.99, 34.99],
    target_margin=0.4
)

print(f"Suggested: ${pricing['suggested_price']}")
# Suggested: $29.99

print(f"Margin: {pricing['margin_at_suggested'] * 100}%")
# Margin: 42%
```

**Pricing Features:**
- ✅ Psychological pricing (.99, .97 endings)
- ✅ Competitor price analysis
- ✅ Category-aware pricing norms
- ✅ Target margin enforcement
- ✅ Premium/discount tiers

---

### Method: `generate_complete_listing()` ⭐ **Recommended**

One-call method to generate everything needed for Shopify.

```python
async def generate_complete_listing(
    aliexpress_data: Dict,
    niche: str,
    brand_name: str = "Oubon Shop"
) -> Dict
```

**Parameters:**
- `aliexpress_data`: Raw product data from AliExpress
  ```python
  {
      "title": "Original AliExpress title",
      "features": ["feature1", "feature2", ...],
      "category": "Smart Lighting",
      "price": 12.99,
      "images": ["url1", "url2", ...]
  }
  ```
- `niche`: Product niche (e.g., "smart_home")
- `brand_name`: Store brand name

**Returns:**
```python
{
    "title": "Clean optimized title",
    "description_html": "Full HTML product page",
    "short_description": "Preview text",
    "bullet_points": ["Feature 1", "Feature 2", ...],
    "seo": {
        "meta_title": "...",
        "meta_description": "...",
        "url_slug": "...",
        "keywords": {"primary": "...", "secondary": [...]},
        "image_alt_text": "..."
    },
    "pricing": {
        "suggested_price": 29.99,
        "min_viable_price": 24.99,
        "premium_price": 39.99,
        "margin_at_suggested": 0.42,
        "pricing_rationale": "..."
    },
    "tags": ["smart-home", "smart-lighting", "wifi", ...],
    "product_type": "Smart Lighting",
    "vendor": "Oubon Shop",
    "meta": {
        "generated_at": "2024-12-06T12:34:56",
        "original_title": "...",
        "cost_price": 12.99
    }
}
```

**Example:**
```python
# Complete listing in one call
listing = await generator.generate_complete_listing(
    aliexpress_data={
        "title": "2024 New Smart LED Bulb WiFi RGB...",
        "features": ["WiFi", "RGB colors", "Alexa compatible"],
        "category": "Smart Lighting",
        "price": 12.99
    },
    niche="smart_home",
    brand_name="Oubon Shop"
)

# Ready for Shopify deployment
print(listing["title"])
# "Smart WiFi LED Bulb - RGB Color Changing, Works with Alexa"

print(listing["pricing"]["suggested_price"])
# 29.99

print(listing["seo"]["meta_title"])
# "Smart WiFi LED Bulb | RGB Color Changing | Oubon Shop"
```

---

### Method: `get_usage_stats()`

Get API usage statistics and costs.

```python
def get_usage_stats(last_n_hours: int = 24) -> Dict
```

**Parameters:**
- `last_n_hours`: Look back period (default: 24 hours)

**Returns:**
```python
{
    "total_calls": 150,
    "successful_calls": 148,
    "failed_calls": 2,
    "total_input_tokens": 45000,
    "total_output_tokens": 30000,
    "total_cost": 0.585,
    "average_cost_per_call": 0.0039
}
```

**Example:**
```python
# Check today's usage
stats = generator.get_usage_stats(last_n_hours=24)

print(f"Calls: {stats['total_calls']}")
print(f"Cost: ${stats['total_cost']:.2f}")
print(f"Avg per product: ${stats['average_cost_per_call']:.4f}")
```

## Cost Analysis

### Pricing Model

**Claude Sonnet 4.5 Pricing:**
- Input tokens: $3 per million
- Output tokens: $15 per million

### Per-Product Costs

| Method | Avg Tokens (In/Out) | Cost |
|--------|---------------------|------|
| `generate_product_title()` | 200/50 | $0.0014 |
| `generate_product_description()` | 400/800 | $0.0132 |
| `generate_seo_content()` | 300/200 | $0.0039 |
| `suggest_competitive_price()` | 200/100 | $0.0021 |
| **Complete listing** | **1100/1150** | **~$0.02** |

### Monthly Cost Projections

| Products/Month | Complete Listings | Monthly Cost |
|----------------|-------------------|--------------|
| 100 products | 100 × $0.02 | **$2.00** |
| 500 products | 500 × $0.02 | **$10.00** |
| 1,000 products | 1,000 × $0.02 | **$20.00** |
| 5,000 products | 5,000 × $0.02 | **$100.00** |

**Very cost-effective!** Claude Sonnet 4.5 is significantly cheaper than GPT-4 while maintaining high quality.

## Rate Limiting

**Built-in Rate Limiter:**
- Default: 50 calls per minute
- Automatically waits if limit exceeded
- Configurable on initialization

**Example:**
```python
# Conservative rate limiting
generator = ProductContentGenerator(rate_limit=30)

# Aggressive (if you have higher limits)
generator = ProductContentGenerator(rate_limit=100)
```

**Anthropic Rate Limits (as of 2024):**
- Tier 1: 50 requests/min, 40,000 tokens/min
- Tier 2: 1,000 requests/min, 80,000 tokens/min
- Tier 3+: Higher limits available

## Integration with Deployment

### Use in ProductDeploymentService

Update `/ospra_os/integrations/shopify/deployment.py`:

```python
from ospra_os.services.product_content_generator import ProductContentGenerator

class ProductDeploymentService:
    def __init__(self, ...):
        self.content_generator = ProductContentGenerator()

    async def deploy_product(self, product_data: Dict, ...) -> Dict:
        # Generate complete listing
        listing = await self.content_generator.generate_complete_listing(
            aliexpress_data={
                "title": product_data.get("name"),
                "features": product_data.get("features", []),
                "category": product_data.get("category"),
                "price": product_data.get("cost", 0)
            },
            niche=product_data.get("niche", "smart_home")
        )

        # Use generated content for Shopify
        shopify_product = await self.shopify.create_product(
            title=listing["title"],
            description=listing["description_html"],
            price=listing["pricing"]["suggested_price"],
            tags=listing["tags"],
            ...
        )
```

## Error Handling

The service includes comprehensive error handling:

```python
try:
    listing = await generator.generate_complete_listing(
        aliexpress_data=data,
        niche="smart_home"
    )
except ValueError as e:
    # API key not configured
    print(f"Configuration error: {e}")
except Exception as e:
    # API error or other failure
    print(f"Generation failed: {e}")
    # Use fallback/template content
```

**Graceful Degradation:**
- If API call fails, exception is raised
- You can catch and use template-based content as fallback
- Usage is still tracked even on failures

## Best Practices

### 1. Batch Processing

Process multiple products efficiently:

```python
async def process_batch(products):
    generator = ProductContentGenerator()

    results = []
    for product in products:
        try:
            listing = await generator.generate_complete_listing(
                aliexpress_data=product,
                niche=product.get("niche")
            )
            results.append({"success": True, "listing": listing})
        except Exception as e:
            results.append({"success": False, "error": str(e)})

    # Check usage
    stats = generator.get_usage_stats()
    print(f"Processed {len(products)} products")
    print(f"Total cost: ${stats['total_cost']:.2f}")

    return results
```

### 2. Cost Monitoring

Track costs in production:

```python
# Check usage daily
stats = generator.get_usage_stats(last_n_hours=24)

if stats["total_cost"] > 10.0:  # Alert if daily cost > $10
    send_alert(f"High API usage: ${stats['total_cost']:.2f}")
```

### 3. Caching

Cache generated content to avoid re-generating:

```python
import json

# Save generated listing
with open(f"cache/{product_id}.json", "w") as f:
    json.dump(listing, f)

# Check cache before generating
if os.path.exists(f"cache/{product_id}.json"):
    with open(f"cache/{product_id}.json") as f:
        listing = json.load(f)
else:
    listing = await generator.generate_complete_listing(...)
```

### 4. A/B Testing

Generate multiple title variations:

```python
titles = []
for voice in ["modern", "playful", "luxury", "technical"]:
    title = await generator.generate_product_title(
        original_title=original,
        product_category=category,
        brand_voice=voice
    )
    titles.append({"voice": voice, "title": title})

# Test which performs better
```

## Environment Setup

### Required Environment Variable

```bash
# .env file
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### Get API Key

1. Sign up at https://console.anthropic.com
2. Go to API Keys section
3. Create new key
4. Add to `.env` file

## Examples

### Example 1: Clean AliExpress Title

```python
# Messy AliExpress title
original = "2024 New Hot Sale Smart LED Bulb WiFi RGB Color Changing Light E27 Base Compatible with Alexa Google Home Assistant Best Quality!!!"

title = await generator.generate_product_title(
    original_title=original,
    product_category="Smart Lighting"
)

print(title)
# Output: "Smart WiFi LED Bulb - RGB Color Changing, Works with Alexa & Google Home"
```

### Example 2: Generate Description from Features

```python
description = await generator.generate_product_description(
    product_name="Smart WiFi LED Bulb",
    features=[
        "WiFi 2.4GHz connectivity",
        "16 million RGB colors",
        "Voice control (Alexa, Google Home)",
        "E27 standard base",
        "Energy efficient 9W LED",
        "Smartphone app control",
        "Schedule and timer functions"
    ],
    category="Smart Lighting",
    target_audience="smart home enthusiasts",
    tone="friendly and informative"
)

print(description["short_description"])
# "Transform your home with voice-controlled RGB lighting..."
```

### Example 3: SEO Optimization

```python
seo = await generator.generate_seo_content(
    product_name="Smart WiFi LED Bulb",
    category="Smart Lighting",
    description="RGB color changing LED bulb with WiFi control..."
)

# Use in Shopify
shopify_product = {
    "metafields_global_title_tag": seo["meta_title"],
    "metafields_global_description_tag": seo["meta_description"],
    "handle": seo["url_slug"],
    "tags": seo["keywords"]["secondary"]
}
```

### Example 4: Competitive Pricing

```python
# You found similar products at $24.99, $29.99, $34.99
pricing = await generator.suggest_competitive_price(
    cost_price=12.99,
    category="Smart Lighting",
    competitor_prices=[24.99, 29.99, 34.99],
    target_margin=0.4
)

print(f"Suggested price: ${pricing['suggested_price']}")
# $29.99 (competitive + psychological pricing)

print(f"Margin: {pricing['margin_at_suggested'] * 100:.1f}%")
# 56.6%

print(pricing["pricing_rationale"])
# "Positioned at market average with .99 ending for optimal conversion..."
```

## Troubleshooting

### Issue: "ANTHROPIC_API_KEY not set"

**Solution:**
```bash
# Add to .env file
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env

# Or export temporarily
export ANTHROPIC_API_KEY=sk-ant-...
```

### Issue: Rate limit exceeded

**Solution:**
```python
# Reduce rate limit
generator = ProductContentGenerator(rate_limit=30)

# Or add delays between batches
import asyncio
await asyncio.sleep(60)  # Wait 1 minute between batches
```

### Issue: High costs

**Solution:**
```python
# Use individual methods instead of complete listing
title = await generator.generate_product_title(...)  # $0.001
# Skip description generation if not needed

# Monitor usage
stats = generator.get_usage_stats()
if stats["total_cost"] > budget:
    raise Exception("Budget exceeded")
```

### Issue: Poor quality output

**Solution:**
```python
# Provide better input data
aliexpress_data = {
    "title": "Detailed product name",
    "features": [
        "Specific feature 1",
        "Specific feature 2",
        "Specific feature 3"
    ],  # More features = better output
    "category": "Specific category",  # Not just "electronics"
    "price": 12.99
}
```

## Summary

**ProductContentGenerator** is a powerful, cost-effective AI service for e-commerce content creation.

**Key Benefits:**
- ✅ Transforms messy AliExpress data into professional Shopify listings
- ✅ SEO-optimized content (meta tags, keywords, descriptions)
- ✅ Intelligent pricing with psychological optimization
- ✅ Very low cost (~$0.02 per complete listing)
- ✅ Built-in rate limiting and usage tracking
- ✅ Easy integration with existing deployment pipeline

**Next Steps:**
1. Set `ANTHROPIC_API_KEY` environment variable
2. Use `generate_complete_listing()` for new products
3. Monitor costs with `get_usage_stats()`
4. Integrate into `ProductDeploymentService`

**Support:**
- API Documentation: https://docs.anthropic.com/claude/reference/
- Service Code: `/ospra_os/services/product_content_generator.py`
- Claude Console: https://console.anthropic.com
