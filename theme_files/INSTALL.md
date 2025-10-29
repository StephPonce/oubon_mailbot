# Quick Install Guide - Oubon Shop Theme

## 🚀 5-Minute Setup

### Step 1: Create ZIP File

```bash
cd theme_files
zip -r oubon-shop-theme.zip . -x "*.DS_Store" -x "__MACOSX/*" -x "README.md" -x "INSTALL.md"
```

**Or manually:**
1. Select all folders: `assets`, `config`, `layout`, `sections`, `snippets`, `templates`
2. Right-click → Compress
3. Name it: `oubon-shop-theme.zip`

### Step 2: Upload to Shopify

1. **Login to Shopify Admin**
   - Go to your store admin panel
   - Navigate to: **Online Store → Themes**

2. **Upload Theme**
   - Scroll to "Theme library"
   - Click **"Add theme"**
   - Select **"Upload ZIP file"**
   - Choose `oubon-shop-theme.zip`
   - Wait 10-30 seconds for upload

3. **Publish Theme**
   - Once uploaded, you'll see "Oubon Shop" in your theme library
   - Click **"Publish"** to make it live
   - OR click **"Customize"** to edit first

### Step 3: Initial Setup (5 minutes)

1. **Customize Homepage:**
   - Click **"Customize"** on your live theme
   - Edit Hero section text
   - Select collection for Featured Products
   - Save changes

2. **Create Navigation Menu:**
   - Go to: **Online Store → Navigation**
   - Edit "Main menu"
   - Add links:
     - Shop → `/collections/all`
     - About → `/pages/about`
     - Support → `/pages/contact`

3. **Create Essential Pages:**
   - Go to: **Online Store → Pages**
   - Create "About" page
   - Create "Contact" page (add contact form)
   - Create "FAQ" page

4. **Add Products:**
   - Go to: **Products → Add product**
   - Add at least 3 products to start
   - Make sure to add images!

5. **Create Collections:**
   - Go to: **Products → Collections**
   - Create: "Smart Lighting", "Home Security", etc.
   - Add products to collections

---

## ✅ You're Done!

Your premium store is now live at: `yourstore.myshopify.com`

**Next Steps:**
1. Add more products
2. Configure shipping settings
3. Set up payment processing
4. Test checkout flow
5. Connect custom domain (if you have one)

---

## 🆘 Quick Troubleshooting

**Theme not showing after upload:**
- Check ZIP structure (folders should be at root level)
- Make sure you uploaded the RIGHT zip file
- Try re-uploading

**Products not displaying:**
- Go to Products → Select product
- Check "Online Store" sales channel is enabled
- Verify product is published (not draft)

**Mobile menu not working:**
- Clear your browser cache
- Try in incognito/private mode
- Check if JavaScript is enabled

**Need more help?**
- Read the full README.md
- Contact: hello@oubonshop.com

---

**That's it! Your premium Oubon Shop is ready. 🎉**
