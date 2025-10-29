# OUBON SHOP - Premium Shopify Theme

**A sophisticated e-commerce theme for smart home products**

Built with precision, designed for conversion, optimized for performance.

---

## 🎨 Design Philosophy

- **Brand**: Bold, modern, sophisticated
- **Inspiration**: Apple, Huckberry, Sonos, Allbirds
- **Target Audience**: Tech-forward professionals (25-50, $60k-150k+)
- **Positioning**: Premium smart home technology

---

## ✨ Features

### Design
- ✅ Premium black & electric blue color scheme
- ✅ Inter font (Google Fonts) throughout
- ✅ Sophisticated animations & micro-interactions
- ✅ Fully responsive (mobile-first)
- ✅ Accessibility compliant (ARIA labels, keyboard nav)

### Performance
- ✅ Optimized CSS & JavaScript
- ✅ Lazy loading images
- ✅ Minimal dependencies
- ✅ Fast page loads

### Functionality
- ✅ Product discovery integration ready
- ✅ Dynamic cart with notifications
- ✅ Trust badges
- ✅ Category browsing
- ✅ Search functionality
- ✅ Mobile menu
- ✅ Product variants support
- ✅ Quantity selectors

---

## 📁 File Structure

```
theme_files/
├── layout/
│   └── theme.liquid          # Main layout wrapper
├── sections/
│   ├── header.liquid         # Navigation bar
│   ├── footer.liquid         # Footer with links
│   ├── hero.liquid           # Homepage hero section
│   └── featured-products.liquid # Product showcase
├── templates/
│   ├── index.liquid          # Homepage
│   ├── product.liquid        # Product page
│   ├── collection.liquid     # Collection browsing
│   └── page.liquid           # Basic pages
├── snippets/
│   └── meta-tags.liquid      # SEO meta tags
├── assets/
│   ├── theme.css             # Complete stylesheet
│   └── theme.js              # JavaScript interactions
└── README.md                 # This file
```

---

## 🚀 Installation Instructions

### Step 1: Prepare Theme Files

1. **Compress the theme folder:**
   ```bash
   cd theme_files
   zip -r oubon-shop-theme.zip .
   ```

2. Make sure the ZIP contains these folders at the root:
   - `layout/`
   - `sections/`
   - `templates/`
   - `assets/`
   - `snippets/`

### Step 2: Upload to Shopify

1. **Go to your Shopify Admin:**
   - Navigate to: **Online Store → Themes**

2. **Upload theme:**
   - Click **"Add theme"** button
   - Select **"Upload ZIP file"**
   - Choose your `oubon-shop-theme.zip`
   - Wait for upload to complete (usually 10-30 seconds)

3. **Publish theme:**
   - Once uploaded, click **"Publish"** button
   - Or click **"Customize"** to preview first

### Step 3: Initial Configuration

After publishing, configure these settings:

#### A. Navigation Menu
1. Go to: **Online Store → Navigation**
2. Click **"Main menu"**
3. Add these links:
   - Shop → `/collections/all`
   - About → `/pages/about` (create page first)
   - Support → `/pages/contact`

#### B. Footer Links
Social media links can be configured in:
- **Theme Settings → Footer**
- Add your Instagram, Twitter, Facebook URLs

#### C. Homepage Sections
1. Click **"Customize"** on your theme
2. Configure Hero section:
   - Edit eyebrow text
   - Edit heading
   - Edit subheading
   - Set CTA button link

3. Configure Featured Products:
   - Select a collection to feature
   - Choose number of products to show

---

## 📝 Creating Essential Pages

### 1. About Page

1. Go to: **Online Store → Pages**
2. Click **"Add page"**
3. Title: `About`
4. Content example:
   ```
   Oubon Shop was born from a simple frustration: finding quality smart home
   products shouldn't require hours of research and endless Amazon scrolling.

   We test, curate, and handpick only the products that actually deliver on
   their promises. Every item in our store is chosen for its innovation,
   quality, and real-world performance.

   We believe your home should work for you—effortlessly, intelligently,
   and beautifully.
   ```

### 2. Contact Page

1. Create page titled: `Contact`
2. Content:
   ```
   Have questions? We're here to help!

   Email: hello@oubonshop.com
   Response time: Within 24 hours

   Or use the form below:
   ```
3. Add contact form: Insert → Contact Form

### 3. FAQ Page

1. Create page titled: `FAQ`
2. Add common questions:
   - Shipping times
   - Return policy
   - Product warranties
   - International shipping

---

## 🏪 Setting Up Collections

### Recommended Collections to Create:

1. **Smart Lighting**
   - Handle: `smart-lighting`
   - Add products: LED strips, smart bulbs, etc.

2. **Home Security**
   - Handle: `home-security`
   - Add products: Cameras, smart locks, etc.

3. **Kitchen Tech**
   - Handle: `kitchen-tech`
   - Add products: Smart appliances, etc.

4. **Cleaning Gadgets**
   - Handle: `cleaning-gadgets`
   - Add products: Robot vacuums, etc.

5. **Smart Home Hub**
   - Handle: `smart-home-hub`
   - Add products: Speakers, displays, etc.

6. **Climate Control**
   - Handle: `climate-control`
   - Add products: Thermostats, fans, etc.

### How to Create Collections:

1. Go to: **Products → Collections**
2. Click **"Create collection"**
3. Enter title (e.g., "Smart Lighting")
4. Shopify auto-generates handle
5. Add description
6. Set collection type (Manual or Automated)
7. Add products

---

## 🛍️ Adding Products

### Standard Product Fields:

- **Title**: Product name (e.g., "LED Strip Lights 50ft RGB")
- **Description**: Detailed product information
- **Price**: Your selling price
- **Compare at price**: Original price (for discounts)
- **Type**: Category (e.g., "Smart Lighting")
- **Tags**: Use for filtering (e.g., "led", "wifi", "app-control")
- **Images**: Product photos (recommended: 800x800px minimum)

### Custom Product Fields (Optional):

For enhanced features, add these metafields:

1. **Priority Score** (number)
   - Namespace: `custom`
   - Key: `priority_score`
   - Value: 0-10 (e.g., 8.5)
   - Used for: Priority badges

2. **Profit Margin** (number)
   - Namespace: `custom`
   - Key: `profit_margin`
   - Value: 0-100 (e.g., 62 for 62%)
   - Used for: Displaying margin on cards

3. **Features** (text)
   - Namespace: `custom`
   - Key: `features`
   - Value: Pipe-separated list (e.g., "App Control|Voice Compatible|RGB Colors")
   - Used for: Feature list with checkmarks

---

## 🎨 Customization Options

### Colors (in assets/theme.css):

```css
:root {
  --color-black: #000000;        /* Primary brand color */
  --color-electric: #3b82f6;     /* Electric blue CTAs */
  --color-success: #10b981;      /* Green accents */
  --color-white: #ffffff;        /* Backgrounds */
}
```

### Typography:

- Font: Inter (Google Fonts)
- Loaded automatically
- To change: Edit Google Fonts import in `theme.css`

### Animations:

All animations can be disabled by setting:
```css
* {
  animation: none !important;
  transition: none !important;
}
```

---

## ⚡ Performance Tips

1. **Optimize Images:**
   - Use WebP format when possible
   - Compress before uploading
   - Recommended tools: TinyPNG, Squoosh

2. **Limit Apps:**
   - Only install essential Shopify apps
   - Too many apps slow down your store

3. **Enable Shopify CDN:**
   - Automatically enabled
   - No action needed

4. **Use Collections Wisely:**
   - Automated collections are more efficient
   - Limit manual collection updates

---

## 🔧 Troubleshooting

### Theme not appearing after upload:
- Ensure ZIP file has correct structure
- Check file/folder names (case-sensitive)
- Re-upload theme

### Sections not showing:
- Go to: Customize Theme
- Click "Add section"
- Select section from list

### Products not displaying:
- Ensure products are published
- Check collection settings
- Verify product has "Online Store" sales channel

### Mobile menu not working:
- Clear browser cache
- Check if JavaScript loaded (view page source)
- Verify theme.js is in assets folder

---

## 📱 Mobile Optimization

Theme is fully responsive with these breakpoints:

- **Mobile**: < 640px
- **Tablet**: 640px - 1024px
- **Desktop**: > 1024px

Test on these devices:
- iPhone (Safari)
- Android (Chrome)
- iPad (Safari)
- Desktop (Chrome, Firefox, Safari)

---

## 🔒 Security

### Shopify Handles:
- PCI compliant checkout
- SSL certificates (automatic)
- Secure payment processing

### Your Responsibilities:
- Use strong admin password
- Enable 2FA on Shopify account
- Keep theme files backed up

---

## 🚀 Going Live Checklist

Before launching your store:

### Settings:
- [ ] Store name configured
- [ ] Contact email set
- [ ] Legal pages created (Privacy, Terms, Refunds)
- [ ] Shipping zones configured
- [ ] Tax settings configured
- [ ] Payment providers connected

### Content:
- [ ] Homepage customized
- [ ] About page written
- [ ] Contact information added
- [ ] At least 10 products added
- [ ] Collections created
- [ ] Product images optimized

### Testing:
- [ ] Test checkout process
- [ ] Test mobile experience
- [ ] Test all links
- [ ] Test contact forms
- [ ] Test search functionality

### Marketing:
- [ ] Social media links added
- [ ] Google Analytics installed (optional)
- [ ] Facebook Pixel installed (optional)
- [ ] Meta description set for all pages

---

## 🆘 Support

### Theme Issues:
- Check this README first
- Review Shopify theme documentation
- Check browser console for errors

### Shopify Platform Help:
- Shopify Help Center: help.shopify.com
- Shopify Community Forums
- Shopify Support (chat/email)

---

## 📄 License

This theme is proprietary software built for Oubon Shop.

**© 2025 Oubon Shop. All rights reserved.**

---

## 🎯 Next Steps

1. **Upload theme** following instructions above
2. **Customize homepage** with your content
3. **Add products** from your discovery system
4. **Create collections** to organize inventory
5. **Set up payment processing**
6. **Configure shipping**
7. **Test checkout flow**
8. **Launch** when ready!

---

**Built with care for Oubon Shop**
*What If Your Home Could Do More?*
