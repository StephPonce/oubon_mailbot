# ⚡ OUBON SHOP - 3-MINUTE THEME INSTALL

Get your Oubon Shop branded theme installed in **3 simple steps** (no manual color picking needed!)

---

## ✅ Step 1: Upload Custom CSS (2 minutes)

1. Go to **Shopify Admin** → **Online Store** → **Themes**
2. Find your **Dawn theme** and click **Actions** → **Edit code**
3. In left sidebar, click **Assets** folder
4. Click **Add a new asset**
5. Choose **Create a blank file**
6. Name it: `oubon-custom.css`
7. Click **Create asset**
8. Open the file `shopify_theme_oubon/assets/oubon-custom.css` from this package
9. **Copy the entire contents**
10. **Paste** into the empty file in Shopify
11. Click **Save** (top right)

---

## ✅ Step 2: Link CSS to Theme (30 seconds)

1. Still in **Edit code**, open **Layout** folder (left sidebar)
2. Click **theme.liquid**
3. Press `Cmd+F` (Mac) or `Ctrl+F` (Windows) to search
4. Search for: `</head>`
5. **Just above** `</head>`, add this line:

```liquid
{{ 'oubon-custom.css' | asset_url | stylesheet_tag }}
```

6. Click **Save**

**Visual example:**
```liquid
  ... other code ...

  {{ 'oubon-custom.css' | asset_url | stylesheet_tag }}
</head>
<body>
  ... rest of theme ...
```

---

## ✅ Step 3: Configure Colors (optional but recommended) (30 seconds)

1. Still in **Edit code**, open **Config** folder
2. Click **settings_data.json**
3. Find the line that says: `"current": {`
4. Open `shopify_theme_oubon/config/settings_snippet.json` from this package
5. Copy the **color settings** (everything inside "current")
6. **Replace or merge** with your existing settings
7. Click **Save**

**Tip:** If you're not comfortable editing JSON, skip this step. The CSS will still work!

---

## 🎉 Done! View Your Store

1. Click **Customize** (top left in theme editor)
2. Your store now has:
   - ✅ Black header with white text
   - ✅ Electric blue buttons and accents
   - ✅ Dark footer
   - ✅ Premium product card hover effects
   - ✅ Mobile-optimized design

---

## 🔧 Troubleshooting

**CSS doesn't apply:**
- Clear browser cache (Cmd+Shift+R or Ctrl+Shift+R)
- Check in **Incognito/Private** window
- Verify `oubon-custom.css` is in Assets folder
- Verify the link in `theme.liquid` is **above** `</head>`

**Colors look wrong:**
- The CSS overrides everything, so manual theme settings won't matter much
- For best results, apply the `settings_snippet.json` colors

**Some sections still have wrong colors:**
- Some sections have their own color scheme settings
- Go to **Customize** → click section → change **Color scheme** to match

---

## 📋 What's Next?

Now that your theme is branded, move on to:

1. **Add Products** - Use `shopify_automation/setup_products.py`
2. **Create Collections** - Use `shopify_automation/create_collections.py`
3. **Upload Images** - Hero banner, logos, etc.
4. **Install Apps** - Judge.me, Trust Badges, OptiMonk
5. **Configure Settings** - Payment, shipping, taxes

See `MANUAL_CHECKLIST.md` for complete launch checklist.

---

## 💡 Need More Customization?

**Change announcement bar text:**
1. Go to **Customize** → **Announcement bar** section
2. Edit the text: "🎉 Free Shipping..."
3. Save

**Change logo:**
1. Go to **Customize** → **Header** section
2. Upload your logo image
3. Adjust size as needed
4. Save

**Modify button text:**
1. All button text is controlled by your product pages/sections
2. No theme code changes needed

---

## 🆘 Support

Issues? Check:
- Shopify's Dawn theme documentation: https://shopify.dev/docs/themes
- Liquid template language: https://shopify.dev/docs/api/liquid
- Contact: support@oubonshop.com

---

**Estimated Time:** 3 minutes
**Difficulty:** Easy (copy/paste)
**Result:** Fully branded Oubon Shop theme ✨
