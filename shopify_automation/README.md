# 🚀 SHOPIFY AUTOMATION PACKAGE - OUBON SHOP

**Complete automation scripts to set up your Shopify store in minutes instead of hours.**

Version: 1.0.0
Store: Oubon Shop (oubonshop.myshopify.com)
Theme: Dawn with custom branding

---

## 📦 What This Package Does

This automation package saves you **10-12 hours** of manual work by automatically:

✅ Creating 20+ products with real AliExpress data
✅ Generating SEO-optimized titles and descriptions using AI
✅ Setting proper pricing with markup strategies
✅ Downloading and uploading product images
✅ Creating 10+ smart collections with automatic rules
✅ Generating collection descriptions
✅ Validating your entire setup before launch

---

## 🎯 Quick Start (10 Minutes)

### Prerequisites

1. **Shopify store** with Dawn theme
2. **Admin API access token** (see Setup below)
3. **Python 3.8+** installed
4. **Environment variables** configured

### Installation

```bash
# 1. Navigate to automation folder
cd shopify_automation

# 2. Install dependencies
pip install -r requirements.txt
# Or with uv:
uv pip install -r requirements.txt

# 3. Verify environment variables are set
# Check .env file in parent directory has:
# - SHOPIFY_STORE_DOMAIN
# - SHOPIFY_ADMIN_ACCESS_TOKEN
# - ANTHROPIC_API_KEY or OPENAI_API_KEY
```

### Usage

```bash
# Step 1: Create collections (2 minutes)
python create_collections.py

# Step 2: Add products (5-10 minutes)
python setup_products.py --count 20

# Step 3: Validate setup (30 seconds)
python validate_setup.py

# Done! Your store is ready 🎉
```

---

## 📁 Package Contents

```
shopify_automation/
├── config.py                  # Configuration & constants
├── setup_products.py          # Auto-create products from intelligence engine
├── create_collections.py      # Auto-create smart collections
├── validate_setup.py          # Pre-launch validation checks
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── MANUAL_CHECKLIST.md        # Step-by-step launch guide
└── logs/                      # Execution logs
```

---

## 🔧 Detailed Setup

### 1. Get Shopify Admin API Token

1. Go to Shopify Admin → **Apps** → **Develop apps**
2. Click **Create an app**
3. Name it: "Automation Scripts"
4. Go to **Configuration** tab
5. Under **Admin API integration**, click **Configure**
6. Select these scopes:
   - `read_products`
   - `write_products`
   - `read_collections`
   - `write_collections`
   - `read_inventory`
   - `write_inventory`
7. Click **Save**
8. Go to **API credentials** tab
9. Click **Install app**
10. Copy the **Admin API access token** (starts with `shpat_`)

### 2. Configure Environment Variables

Add to `.env` file in parent directory:

```bash
# Shopify
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
SHOPIFY_ADMIN_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
SHOPIFY_API_VERSION=2024-01

# AI (at least one required for descriptions)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
# Or
OPENAI_API_KEY=sk-xxxxxxxxxxxxx

# Optional: Product Intelligence API
INTELLIGENCE_API_URL=http://localhost:8001/api/intelligence/discover
```

### 3. Test Configuration

```bash
python -c "from shopify_automation.config import validate_all; validate_all()"
```

Should output: ✅ Configuration validated successfully

---

## 📖 Script Documentation

### setup_products.py

**Purpose:** Automatically creates products in Shopify using real AliExpress data.

**What it does:**
1. Fetches products from intelligence engine
2. Generates SEO-optimized titles and descriptions using Claude/OpenAI
3. Calculates pricing with 2.5-3x markup
4. Downloads and uploads product images
5. Creates products in Shopify
6. Assigns appropriate tags and product types

**Usage:**

```bash
# Create 20 products from default niches
python setup_products.py --count 20

# Create 30 products from specific niches
python setup_products.py --count 30 --niches "smart lighting,home security,kitchen tech"

# Preview without creating (dry run)
python setup_products.py --count 10 --dry-run

# Create 5 products per niche (default is 5)
python setup_products.py --count 20 --max-per-niche 5
```

**Options:**
- `--count`: Number of products to create (default: 20)
- `--niches`: Comma-separated niches (default: smart home, tech gadgets)
- `--max-per-niche`: Max products per niche (default: 5)
- `--dry-run`: Preview without creating

**Time:** 5-10 minutes for 20 products

**Logs:** `logs/setup_products.log`

---

### create_collections.py

**Purpose:** Automatically creates smart collections with intelligent rules.

**What it does:**
1. Creates category-based collections (Smart Lighting, Home Security, etc.)
2. Creates feature-based collections (Voice Control, Energy Efficient)
3. Creates price-based collections (Under $25, $25-50, Premium)
4. Creates promotional collections (New Arrivals, Sale Items)
5. Generates SEO-optimized descriptions for each collection
6. Sets up automatic product assignment rules

**Usage:**

```bash
# Create all collections
python create_collections.py

# Preview without creating (dry run)
python create_collections.py --dry-run
```

**Collections Created (10):**
- Smart Lighting
- Home Security
- Smart Speakers & Audio
- Kitchen Tech
- Voice Control Compatible
- Under $25
- $25 - $50
- Premium ($50+)
- New Arrivals
- Sale Items

**Time:** 2-3 minutes

**Logs:** `logs/create_collections.log`

---

### validate_setup.py

**Purpose:** Validates your store is ready for launch.

**What it checks:**
- ✅ Shopify API connection
- ✅ Product count (minimum 10)
- ✅ Products have images and descriptions
- ✅ Collection count (minimum 3)
- ⚠️  Manual tasks remaining

**Usage:**

```bash
# Run validation
python validate_setup.py
```

**Output:**
- ✅ Green checkmarks: Passed checks
- ❌ Red X marks: Critical issues (must fix)
- ⚠️  Yellow warnings: Recommendations or manual tasks

**Time:** 30 seconds

**Logs:** `logs/validate_setup.log`

---

## ⚙️ Configuration (config.py)

All settings are centralized in `config.py`:

### Key Settings

**Pricing Strategy:**
```python
MARKUP_MIN = 2.5          # Minimum markup (250%)
MARKUP_MAX = 3.0          # Maximum markup (300%)
MARKUP_DEFAULT = 2.7      # Default markup (270%)
USE_PSYCHOLOGICAL_PRICING = True  # $29.99 instead of $30
ADD_COMPARE_AT_PRICE = True      # Show "sale" pricing
```

**Product Defaults:**
```python
DEFAULT_STATUS = "draft"   # Start as draft (safer)
DEFAULT_VENDOR = "Oubon Shop"
DEFAULT_PRODUCT_TYPE = "Smart Home"
TRACK_INVENTORY = False    # Dropshipping - don't track
```

**Image Settings:**
```python
MAX_WIDTH = 2048           # Max image width
MAX_HEIGHT = 2048          # Max image height
QUALITY = 85               # JPEG quality
MAX_FILE_SIZE_KB = 300     # Target max size
```

**AI Content Generation:**
```python
PRIMARY_AI = "claude"      # Use Claude first
FALLBACK_AI = "openai"     # Fall back to OpenAI
CLAUDE_MODEL = "claude-3-5-sonnet-20240620"
OPENAI_MODEL = "gpt-4o-mini"
```

---

## 🎨 Customization

### Change Pricing Strategy

Edit `config.py`:

```python
class ProductConfig:
    MARKUP_MIN = 3.0  # 300% markup
    MARKUP_MAX = 3.5  # 350% markup
```

### Add More Default Niches

Edit `config.py`:

```python
class ProductConfig:
    DEFAULT_NICHES = [
        "smart lighting led strip",
        "wireless security camera",
        "your-custom-niche-here"
    ]
```

### Change Collection Rules

Edit `config.py` → `CollectionConfig.SMART_COLLECTIONS`:

```python
{
    "title": "Budget Friendly",
    "handle": "budget-friendly",
    "rules": [{"column": "variant_price", "relation": "less_than", "condition": "20"}],
    "sort_order": "price-ascending"
}
```

### Customize AI Prompts

Edit `config.py` → `ContentConfig.PRODUCT_DESCRIPTION_PROMPT`:

```python
PRODUCT_DESCRIPTION_PROMPT = """Your custom prompt here..."""
```

---

## 🐛 Troubleshooting

### Issue: "Configuration error: SHOPIFY_ADMIN_ACCESS_TOKEN not set"

**Solution:**
1. Check `.env` file has the token
2. Token should start with `shpat_`
3. Verify no extra spaces or quotes
4. Restart terminal to reload environment

### Issue: "Intelligence API timeout"

**Solution:**
1. Check intelligence engine is running (port 8001)
2. Increase timeout in `config.py`:
   ```python
   API_TIMEOUT = 180  # 3 minutes
   ```
3. Reduce products per request:
   ```bash
   python setup_products.py --max-per-niche 3
   ```

### Issue: "Shopify API rate limit"

**Solution:**
- Scripts already have rate limiting (2 req/sec)
- If you hit limits, wait 1 minute and retry
- Reduce batch size

### Issue: "No products fetched from intelligence API"

**Solution:**
1. Check intelligence API is accessible:
   ```bash
   curl http://localhost:8001/api/intelligence/discover -X POST \
     -H "Content-Type: application/json" \
     -d '{"niches":["smart home"],"max_per_niche":2}'
   ```
2. Verify AliExpress API keys are set
3. Check API logs for errors

### Issue: "AI description generation fails"

**Solution:**
- Scripts fall back to template descriptions
- Check AI API keys are valid:
  - `ANTHROPIC_API_KEY` for Claude
  - `OPENAI_API_KEY` for OpenAI
- Verify API key hasn't expired
- Check API usage quotas

### Issue: "Products created but no images"

**Solution:**
- AliExpress image URLs may be blocked
- Check image download timeout in `config.py`
- Manually upload images in Shopify Admin

---

## 📊 Performance

**Timing Estimates:**

| Task | Products/Collections | Time |
|------|---------------------|------|
| Create Collections | 10 collections | 2-3 min |
| Setup Products | 20 products | 5-10 min |
| Setup Products | 50 products | 15-20 min |
| Validate Setup | - | 30 sec |

**API Usage:**

| Service | Calls per 20 Products |
|---------|----------------------|
| Intelligence API | 1-2 |
| Shopify API | ~40 (products + variants) |
| Claude API | 20 (if enabled) |
| OpenAI API | 20 (if Claude fails) |

---

## 🔒 Security

**Best Practices:**

1. **Never commit .env file**
   - Already in .gitignore
   - Contains sensitive API keys

2. **Use environment variables**
   - Don't hardcode credentials
   - Rotate keys regularly

3. **Limit API token scopes**
   - Only grant necessary permissions
   - Create separate tokens for different apps

4. **Test in draft mode first**
   - Products created as "draft" by default
   - Review before publishing

---

## 📝 Logs

All scripts create detailed logs in `logs/` folder:

- `setup_products.log` - Product creation log
- `create_collections.log` - Collection creation log
- `validate_setup.log` - Validation results

**Log Format:**
```
2024-01-15 10:30:45 - setup_products - INFO - ✅ Created product: Smart LED Bulb
2024-01-15 10:30:46 - setup_products - ERROR - ❌ Failed to download image: timeout
```

---

## 🆘 Getting Help

**Resources:**
- Shopify Admin API Docs: https://shopify.dev/docs/api/admin-rest
- Dawn Theme Docs: https://shopify.dev/docs/themes/theme-templates/dawn
- Python Requests: https://requests.readthedocs.io/

**Support:**
- Email: support@oubonshop.com
- Check logs for detailed error messages
- Review validation output for specific issues

---

## 🎉 What's Next?

After running the automation scripts:

1. ✅ **Review Created Products** (Shopify Admin → Products)
   - Check titles and descriptions
   - Verify images loaded
   - Confirm pricing looks correct

2. ✅ **Review Collections** (Shopify Admin → Collections)
   - Verify products assigned correctly
   - Check collection images (may need manual upload)

3. ✅ **Run Validation** (`python validate_setup.py`)
   - Fix any critical errors
   - Review warnings

4. ✅ **Complete Manual Tasks** (see MANUAL_CHECKLIST.md)
   - Configure payment gateway
   - Set up shipping rates
   - Install apps
   - Test checkout

5. ✅ **Launch!** 🚀
   - Remove password protection
   - Announce on social media

---

## 📄 License

- Scripts: Proprietary (Oubon Shop)
- Usage: Free for Oubon Shop store
- Modification: Allowed for personal use
- Redistribution: Not permitted

---

## 🙏 Credits

- **Automation Scripts:** Claude Code Assistant
- **Product Intelligence:** Oubon Shop Intelligence Engine
- **AI Content:** Anthropic Claude & OpenAI GPT
- **Store Platform:** Shopify

---

**Version:** 1.0.0
**Last Updated:** 2024
**Questions?** See MANUAL_CHECKLIST.md for step-by-step guidance.

**Ready to automate?** Run `python create_collections.py` to get started! 🚀
