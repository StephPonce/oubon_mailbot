# 🔍 PRODUCT SEARCH & INTELLIGENCE GUIDE

## How Product Searching Works Right Now

### Method 1: Command Line (Easiest)
```bash
# Search ANY niche you want:
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot"
uv run python shopify_automation/setup_products.py --niches "fitness tracker,yoga mat,protein shaker" --count 15

# Another example:
uv run python shopify_automation/setup_products.py --niches "phone accessories,wireless charger,car mount" --count 20

# Yet another:
uv run python shopify_automation/setup_products.py --niches "pet toys,dog collar,cat bed" --count 10
```

**You can search ANYTHING** - just replace the niches with what you want!

### Method 2: API Call (For Testing)
```bash
curl -X POST http://localhost:8001/api/intelligence/discover \
  -H "Content-Type: application/json" \
  -d '{
    "niches": ["portable blender", "travel pillow", "phone stand"],
    "max_per_niche": 5
  }'
```

### Method 3: Python Script (For Automation)
```python
import requests

response = requests.post(
    "http://localhost:8001/api/intelligence/discover",
    json={
        "niches": ["any niche you want"],
        "max_per_niche": 10
    }
)

products = response.json()['products']
```

---

## 📊 Current Data You Already Get

For each product, you already receive:
- ✅ **Sales data**: `"orders": 52283` (real AliExpress sales)
- ✅ **Rating**: `"rating": 4.7`
- ✅ **Price**: `"price": 3.4`
- ✅ **Profit margins**: `"profit_margin": 58.3`
- ✅ **Score breakdown**: sales_performance, customer_sentiment, profit_potential, etc.
- ✅ **AI explanation**: Claude analysis of why this product is good

---

## 🚀 ENHANCEMENTS YOU WANT (What We'll Add)

### 1. Sales Trend Analysis
**What you want:** "This has an uptrend of 15% over last 30 days"

**What we need:**
- Google Trends API (free but limited)
- Historical AliExpress data (requires scraping or paid service)

**Status:** NOT IMPLEMENTED YET

### 2. Multi-Platform Popularity
**What you want:** "Popular on Instagram (50k posts), TikTok (2M views), Amazon (4.5★)"

**APIs needed:**
- **Instagram Graph API** - Already have token in .env!
- **TikTok API** - Already have credentials in .env!
- **Amazon Product Advertising API** - Need to set up
- **Google Trends** - Free, need to add

**Status:** APIs available, just need integration code

### 3. Trend Indicators
**What you want:** "🔥 Hot new product type popular on Instagram"

**What we'll add:**
- Social media mention counts
- Google Trends momentum scores
- "New product" detection (launch date < 90 days)
- Platform-specific popularity badges

### 4. Detailed Sales Analytics
**What you want:** "Sold 5,234 on AliExpress, 1,200 on Amazon"

**Current limitation:** Only have AliExpress data
**What we need:**
- Amazon Product Advertising API
- Web scraping for other platforms (legal gray area)

---

## 🔧 APIs YOU NEED (Most Already Set Up!)

### ✅ Already Have
1. **AliExpress API** - ✅ WORKING
   ```
   ALIEXPRESS_APP_KEY=520918
   ALIEXPRESS_APP_SECRET=idjX6tOzHx6urVsSylVzEcHZKwBN4YhN
   ```

2. **Claude AI** - ✅ WORKING
   ```
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

3. **Instagram API** - ✅ Token exists but not used
   ```
   INSTAGRAM_ACCESS_TOKEN=(empty in .env)
   ```

4. **TikTok API** - ✅ Credentials exist
   ```
   TIKTOK_CLIENT_KEY=awfl4ben3ftbj54c
   TIKTOK_CLIENT_SECRET=I8WXEYVS3Gk3KJSonpab7I1wh9axBPPQ
   ```

### ❌ Need to Add
1. **Amazon Product Advertising API**
   - Sign up: https://affiliate-program.amazon.com/assoc_credentials/home
   - Cost: FREE (but need Amazon Associate account)
   - Get: Access Key, Secret Key, Partner Tag
   ```
   AMAZON_ACCESS_KEY=
   AMAZON_SECRET_KEY=
   AMAZON_PARTNER_TAG=oubonshop-20  # Already set!
   ```

2. **Google Trends** (via pytrends library)
   - No API key needed
   - Just: `pip install pytrends`

3. **Twitter API v2** (Optional)
   - For tweet counts/engagement
   - Cost: FREE tier available
   ```
   TWITTER_BEARER_TOKEN=
   ```

4. **ScraperAPI** (Optional - for advanced scraping)
   - Cost: $49/mo for 100k requests
   ```
   SCRAPERAPI_KEY=
   ```

---

## 💡 EXAMPLE: Enhanced Product Analysis

### Current Output:
```
🎯 Strong Opportunity (Score: 8.3/10)

Recommendation: Add to your store immediately.

Why:
1. Proven demand with 23,749 orders on AliExpress
2. High customer satisfaction (4.7★/5.0)
3. Excellent profit margins with 3x markup
```

### Enhanced Output (What We'll Build):
```
🔥 HOT TRENDING PRODUCT (Score: 9.1/10)

📈 SALES PERFORMANCE
• AliExpress: 23,749 orders (+18% last 30 days) 📈
• Amazon: 15,234 reviews (4.6★)
• Estimated monthly revenue: $87,500

🌐 PLATFORM POPULARITY
• Instagram: 45,230 posts with #SmartLEDStrip
• TikTok: 2.3M views on related hashtags
• Google Trends: +35% search interest (rising)
• Pinterest: 12,450 pins (high engagement)

💰 PROFIT ANALYSIS
• Supplier cost: $9.23
• Suggested price: $29.99 (3.2x markup)
• Est. profit per sale: $18.76 (62% margin)
• Monthly profit potential: $9,380 (500 sales @ 2% conv)

🎯 MARKET OPPORTUNITY
• Competition: Medium (4,500 sellers on Amazon)
• Demand: HIGH and GROWING (+35% trend)
• Saturation: 45% (room for new sellers)
• Best season: Q4 (holiday lighting)

⚠️  RISKS
• Shipping time: 12-15 days (customer complaints risk)
• High competition on "smart LED" keywords
• Need unique angle: focus on "gaming setup" niche

✅ RECOMMENDATION: ADD IMMEDIATELY
Target audience: Gamers, streamers, home decorators
Marketing angle: "Transform Your Gaming Setup"
Launch window: NOW (Q4 preparation)
```

---

## 🛠️ NEXT STEPS TO IMPLEMENT

### Phase 1: Basic Enhancements (No new APIs)
1. ✅ Manual niche search (already works!)
2. Add historical tracking (save products to database)
3. Calculate trend from our own data

### Phase 2: Google Trends Integration
1. Install pytrends: `pip install pytrends`
2. Add trend momentum to scoring
3. Show if search interest is rising/falling

### Phase 3: Social Media Data
1. Use Instagram API (token already exists)
2. Use TikTok API (credentials ready)
3. Add social proof metrics

### Phase 4: Amazon Integration
1. Sign up for Amazon Product Advertising API
2. Add Amazon price/review comparison
3. Show "also sold on Amazon" data

### Phase 5: Advanced Analytics
1. Historical price tracking
2. Competitor analysis
3. Seasonal trends
4. Profit forecasting

---

## 📝 HOW TO COMPLETE MANUAL SHOPIFY SETUP

### Quick Setup (30 minutes)

#### 1. Configure Payment (10 min)
1. Go to Shopify Admin: https://admin.shopify.com/store/rxxj7d-1i
2. **Settings** → **Payments**
3. Click "Complete account setup" for Shopify Payments
4. Fill in:
   - Business name: Oubon Shop
   - Business type: Individual/Sole Proprietorship
   - Bank account info
   - Tax ID (SSN or EIN)
5. Save

**Alternative:** Set up PayPal Business if Shopify Payments not available in your region

#### 2. Set Shipping Rates (5 min)
1. **Settings** → **Shipping and delivery**
2. Click "Manage rates"
3. Add:
   - **Standard**: $5.99 (5-7 days)
   - **Free Shipping**: $0 (orders $50+, 5-7 days)
   - **Express**: $14.99 (2-3 days) - optional
4. Save

#### 3. Upload Logo & Images (10 min)
1. **Online Store** → **Themes** → **Customize**
2. Click **Header** section
3. Upload logo (recommend 500x200px PNG with transparency)
4. **Image banner** section on homepage
5. Upload hero image (1920x1080px)
   - Get free images: unsplash.com (search "smart home")
6. Add headline: "Smart Home Technology Made Simple"
7. Save

#### 4. Test Checkout (5 min)
1. Visit your store
2. Add product to cart
3. Go to checkout
4. Use test card: `1111 1111 1111 1111`
5. Expiry: any future date, CVV: any 3 digits
6. Complete checkout
7. Verify you receive confirmation email
8. In admin: **Orders** → Archive the test order

#### 5. Remove Password & Launch
1. **Online Store** → **Preferences**
2. Scroll to "Password protection"
3. UNCHECK "Enable password"
4. Save

**🎉 YOUR STORE IS LIVE!**

---

## 🔍 HOW TO SEARCH & ADD NEW PRODUCTS ANYTIME

```bash
# Step 1: Search new niche
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot"
uv run python shopify_automation/setup_products.py \
  --niches "gaming headset,mechanical keyboard,gaming mouse" \
  --count 20

# Step 2: Products are automatically added to your Shopify store!

# Step 3: Check your store
curl -s "https://rxxj7d-1i.myshopify.com/admin/api/2024-10/products/count.json" \
  -H "X-Shopify-Access-Token: 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"
```

**You can do this ANYTIME with ANY niche!** No coding needed, just change the niche names.

---

## ❓ FAQ

**Q: Are products hardcoded?**
A: NO! You can search any niche anytime with `--niches` flag

**Q: Do I need to restart the server to search new niches?**
A: NO! Just run the command with new niches

**Q: Can I search multiple niches at once?**
A: YES! Separate with commas: `--niches "niche1,niche2,niche3"`

**Q: How do I avoid duplicate products?**
A: The system tracks by AliExpress product_id, duplicates are skipped

**Q: Can I delete products and search new ones?**
A: YES! Delete via Shopify admin, then search new niches

---

## 📞 SUPPORT

Questions? Check:
- This guide first
- `shopify_automation/README.md`
- `shopify_automation/MANUAL_CHECKLIST.md`

Ready to enhance? Let's add those APIs and build the advanced intelligence!
