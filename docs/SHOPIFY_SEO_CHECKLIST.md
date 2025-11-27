# Shopify Store Manual Editing Checklist

**Store:** Oubon Shop (oubonshop.com)  
**Audit Date:** 2025-11-16  
**Overall Health Score:** 40/100 (FAIR - Significant Improvements Needed)

---

## 🔗 Access Shopify Admin

**URL:** https://rxxj7d-1i.myshopify.com/admin

**Login Credentials:** Use your Shopify account credentials

---

## 🚨 CRITICAL ISSUES (Fix These First!)

### 1. Store Has NO Products ⚠️

**Current Status:** 0 products  
**Priority:** CRITICAL

The store is completely empty! You need to add products before going live.

**Options:**

#### Option A: Use Ospra OS Discovery System (Recommended)
```bash
# Use the product discovery API to find trending products
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot"
uv run uvicorn ospra_os.main:app --port 8001

# Then discover products:
curl -X POST "http://localhost:8001/api/intelligence/discover" \
  -H "Content-Type: application/json" \
  -d '{"niches": ["smart_home"], "max_per_niche": 10}'
```

#### Option B: Manual Product Addition
1. Go to **Products** → **Add product**
2. For EACH product, fill in:
   - [ ] Product title (clear, keyword-rich)
   - [ ] Description (minimum 300 words)
   - [ ] Price (competitive pricing)
   - [ ] Compare at price (show discount)
   - [ ] Images (minimum 3-5 high-quality)
   - [ ] Variants (if applicable)
   - [ ] SEO title and description
   - [ ] Tags for filtering

**Target:** Add at least 10-20 products before launch

---

### 2. Missing ALL Legal Policies 🔴

**Current Status:** 0/4 policies configured  
**Priority:** CRITICAL (Required by law!)

Go to **Settings** → **Policies**

#### Step 1: Generate Policy Templates
1. Click "Create from template" for each policy
2. Shopify will auto-generate based on your store info

#### Step 2: Privacy Policy
- [ ] Click **Privacy policy** → **Create from template**
- [ ] Review and customize for your business
- [ ] Add your contact email: hello@oubonshop.com
- [ ] Save

#### Step 3: Refund Policy
- [ ] Click **Refund policy** → **Create from template**
- [ ] Customize refund timeframe (recommend 30 days)
- [ ] Specify return conditions
- [ ] Save

**Example Refund Policy:**
```
30-Day Money-Back Guarantee

Not satisfied? Return any unused item within 30 days for a full refund.

How to Return:
1. Email hello@oubonshop.com with your order number
2. We'll send you return instructions
3. Ship the item back (original packaging preferred)
4. Receive refund within 5-7 business days

Items must be:
- In unused condition
- In original packaging
- Returned within 30 days of delivery
```

#### Step 4: Terms of Service
- [ ] Click **Terms of service** → **Create from template**
- [ ] Review all sections
- [ ] Save

#### Step 5: Shipping Policy
- [ ] Click **Shipping policy** → **Create from template**
- [ ] Add shipping times and costs
- [ ] Save

**Example Shipping Policy:**
```
Shipping Information

Processing Time: 1-2 business days
Standard Shipping: 5-10 business days (FREE over $50)
Express Shipping: 2-4 business days ($15)
Overnight: 1-2 business days ($25)

International Shipping: 10-25 business days

Tracking: Sent via email once shipped
```

---

## 📄 ESSENTIAL PAGES ✅ COMPLETED!

**Status:** All essential pages have been created automatically via API!

**Created Pages:**
- ✅ **About Us** - https://rxxj7d-1i.myshopify.com/pages/about-us
- ✅ **Contact** - https://rxxj7d-1i.myshopify.com/pages/contact
- ✅ **FAQ** - https://rxxj7d-1i.myshopify.com/pages/faq
- ✅ **Shipping Information** - https://rxxj7d-1i.myshopify.com/pages/shipping-information
- ✅ **Returns & Exchanges** - https://rxxj7d-1i.myshopify.com/pages/returns-exchanges

**Optional:** Review and customize content if needed:
- [ ] Visit each page to review content
- [ ] Customize branding or add store-specific details
- [ ] Add images or additional sections if desired

---

## 🧭 NAVIGATION MENUS

### Main Navigation (Header Menu)

Go to **Online Store** → **Navigation** → **Main menu**

- [ ] Add these items:

| Menu Item | Link To | Order |
|-----------|---------|-------|
| Home | Home page | 1 |
| Shop | /collections/all | 2 |
| About | /pages/about-us | 3 |
| FAQ | /pages/faq | 4 |
| Contact | /pages/contact | 5 |

- [ ] Save menu

### Footer Navigation

Go to **Online Store** → **Navigation** → **Footer menu**

Create three sections:

**Customer Service:**
- Shipping Information
- Returns & Exchanges
- FAQ
- Contact Us

**Legal:**
- Privacy Policy
- Terms of Service
- Refund Policy

**Company:**
- About Us
- Contact

---

## 🎨 THEME CUSTOMIZATION

Go to **Online Store** → **Themes** → **Customize**

### Homepage Sections

- [ ] Add hero banner with CTA
- [ ] Add featured products section (4-6 products)
- [ ] Add trust badges (Free Shipping, Returns, etc.)
- [ ] Add newsletter signup

### Branding

- [ ] Upload logo (200-300px wide, transparent PNG)
- [ ] Upload favicon (32x32px or 64x64px)
- [ ] Choose brand colors
- [ ] Select readable fonts

---

## 🔍 SEO SETTINGS

Go to **Online Store** → **Preferences**

- [ ] **Homepage title:**  
  `Oubon Shop - Smart Home Products & Lifestyle Essentials`

- [ ] **Homepage meta description:**  
  `Discover innovative smart home products at Oubon Shop. Free shipping over $50, 30-day returns, expert support.`

- [ ] **Social sharing image:** Upload 1200x630px image

---

## 💳 PAYMENT SETTINGS

Go to **Settings** → **Payments**

- [ ] Enable **Shopify Payments** (credit cards, Apple Pay, Google Pay)
- [ ] Enable **PayPal Express** (recommended)
- [ ] Test checkout with test order

---

## 🚚 SHIPPING SETTINGS

Go to **Settings** → **Shipping and delivery**

### Domestic Shipping (United States)
- [ ] Standard Shipping: $5.99
- [ ] Free Shipping: FREE (orders over $50)
- [ ] Express Shipping: $15.00

### International Shipping
- [ ] Standard International: $15.00

---

## ✅ PRE-LAUNCH CHECKLIST

### Before Removing Password Protection

- [ ] **Products:** At least 10-20 products added
- [ ] **Pages:** All essential pages created
- [ ] **Policies:** All 4 legal policies configured
- [ ] **Navigation:** Menus set up correctly
- [ ] **Theme:** Homepage customized
- [ ] **Logo & Favicon:** Uploaded
- [ ] **SEO:** Meta tags configured
- [ ] **Payment:** Payment methods active
- [ ] **Shipping:** Rates configured
- [ ] **Test Order:** Completed successfully
- [ ] **Mobile:** Site tested on mobile
- [ ] **Links:** All navigation links work

### Testing Checklist

1. **Place a Test Order**
   - [ ] Add product to cart
   - [ ] Complete checkout
   - [ ] Verify confirmation email
   - [ ] Check order in admin

2. **Test Refund**
   - [ ] Issue refund for test order
   - [ ] Verify refund email

3. **Mobile Test**
   - [ ] Browse on mobile device
   - [ ] Test all functionality

4. **Link Test**
   - [ ] Click every link
   - [ ] Verify no 404 errors

---

## 🚀 GO LIVE

Once everything is ready:

1. **Remove Password Protection**
   - Go to **Online Store** → **Preferences**
   - Scroll to **Password protection**
   - [ ] Uncheck "Enable password"
   - [ ] Save

2. **Announce Launch**
   - [ ] Share on social media
   - [ ] Email your list
   - [ ] Consider paid advertising

---

## 📊 POST-LAUNCH MONITORING

### First Week
- [ ] Check for orders daily
- [ ] Respond to inquiries within 24 hours
- [ ] Monitor analytics
- [ ] Fix reported issues

### First Month
- [ ] Review top-selling products
- [ ] Optimize descriptions
- [ ] Add new products
- [ ] Collect customer feedback

---

## 📝 QUICK REFERENCE

### Shopify Admin Shortcuts

| Task | Location |
|------|----------|
| Add Products | Products → Add product |
| Create Pages | Online Store → Pages |
| Edit Navigation | Online Store → Navigation |
| Customize Theme | Online Store → Themes → Customize |
| Set up Policies | Settings → Policies |
| Configure Shipping | Settings → Shipping and delivery |
| Set up Payments | Settings → Payments |
| Email Settings | Settings → Notifications |
| SEO Settings | Online Store → Preferences |

---

**Last Updated:** 2025-11-16  
**Store Health Score:** 40/100 → Target: 90+/100  
**Status:** Pre-Launch Setup Phase

**For detailed page content templates, see the full version of this checklist.**
