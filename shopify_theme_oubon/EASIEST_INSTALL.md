# 🎯 EASIEST INSTALL - NO FILE UPLOADS (1 Minute!)

The absolute easiest way to brand your Shopify store with Oubon colors.
**No code editing. No file uploads. Just copy/paste into Shopify's theme settings.**

---

## ⚡ Method 1: Custom CSS Section (RECOMMENDED - 1 Minute)

Shopify's Dawn theme has a built-in Custom CSS feature. Just paste our CSS there!

### Steps:

1. **Go to Theme Customizer**
   - Shopify Admin → Online Store → Themes
   - Click **Customize** button on Dawn theme

2. **Open Theme Settings**
   - Click **Theme settings** (gear icon in bottom left sidebar)
   - Scroll down to find **Custom CSS** section
   - If you don't see it, look for **Additional CSS** or **Custom styles**

3. **Paste the CSS**
   - Open the file: `shopify_theme_oubon/assets/oubon-custom.css`
   - Copy **ALL** the CSS code (Cmd+A, Cmd+C)
   - Paste into the **Custom CSS** box in Shopify
   - Click **Save** (top right)

4. **Done!** 🎉
   - Refresh your store preview
   - Your theme now has Oubon branding!

---

## 🎨 Method 2: Shopify CLI (For Developers - 5 Minutes)

If you're comfortable with command line:

### Prerequisites:
```bash
# Install Shopify CLI
npm install -g @shopify/cli @shopify/theme
```

### Steps:

1. **Download Dawn Theme**
```bash
shopify theme init oubon-theme --clone-url https://github.com/Shopify/dawn
cd oubon-theme
```

2. **Add Custom CSS**
```bash
# Copy our custom CSS file
cp ../shopify_theme_oubon/assets/oubon-custom.css assets/
```

3. **Link CSS in Theme**
Edit `layout/theme.liquid` and add before `</head>`:
```liquid
{{ 'oubon-custom.css' | asset_url | stylesheet_tag }}
```

4. **Push to Shopify**
```bash
shopify theme push
```

5. **Publish Theme**
```bash
shopify theme publish
```

---

## 🔧 Method 3: Theme Code Editor (Original Method - 3 Minutes)

If Custom CSS doesn't exist in your theme settings:

1. **Edit Theme Code**
   - Themes → Actions → Edit code

2. **Create CSS Asset**
   - Assets folder → Add a new asset
   - Name: `oubon-custom.css`
   - Paste CSS code
   - Save

3. **Link CSS**
   - Open `layout/theme.liquid`
   - Before `</head>`, add:
   ```liquid
   {{ 'oubon-custom.css' | asset_url | stylesheet_tag }}
   ```
   - Save

---

## 🎯 Method 4: Just the Colors (30 Seconds)

If you only want to change colors without custom styling:

1. **Go to Customize → Theme Settings → Colors**

2. **Set these values:**
   - **Accent 1:** `#3B82F6` (Electric Blue)
   - **Accent 2:** `#000000` (Black)
   - **Background 1:** `#FFFFFF` (White)
   - **Background 2:** `#F9FAFB` (Light Gray)
   - **Text:** `#1F2937` (Dark Gray)
   - **Button background:** `#3B82F6` (Electric Blue)
   - **Button text:** `#FFFFFF` (White)

3. **Click Save**

4. **Done!** Basic branding applied.

**Note:** This won't include hover effects, animations, or footer styling. For full Oubon branding, use Method 1.

---

## ❓ Which Method Should I Use?

| Method | Time | Technical Level | Features |
|--------|------|----------------|----------|
| **Method 1: Custom CSS** | 1 min | Easy | ✅ Full branding |
| Method 2: Shopify CLI | 5 min | Advanced | ✅ Full branding + version control |
| Method 3: Code Editor | 3 min | Medium | ✅ Full branding |
| Method 4: Colors Only | 30 sec | Easy | ⚠️ Basic colors only |

**Recommendation:** Start with **Method 1** (Custom CSS). It's the easiest and gives you full branding.

---

## 🐛 Troubleshooting

### "I don't see Custom CSS section"

**Solution 1:** Update Dawn theme
- Your theme might be older
- Go to Themes → Check for updates
- Update to latest Dawn version (has Custom CSS)

**Solution 2:** Use Method 3 instead
- Edit theme code directly
- Works on all theme versions

### "CSS doesn't apply after pasting"

1. **Clear cache:** Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
2. **Try incognito window:** Test in private browsing
3. **Save again:** Click Save in theme customizer
4. **Check preview:** Make sure you're viewing the changes in preview

### "Some sections still have wrong colors"

- Click the section in customizer
- Look for **Color scheme** dropdown
- Change to **Inverse** or **Accent 1**
- Save

---

## ✅ Verify It Worked

After applying CSS, check:

- [ ] Header is black with white text
- [ ] Buttons are electric blue
- [ ] Button hover effects work (slight lift)
- [ ] Footer is dark with blue accents
- [ ] Product cards have hover effects
- [ ] Mobile view looks good

---

## 🎉 What's Next?

After your theme is branded:

1. **Add Products** → Use automation scripts
2. **Create Collections** → Use automation scripts
3. **Upload Images** → Hero banner, logos
4. **Configure Settings** → Payment, shipping
5. **Go Live!** → Remove password protection

---

**Need the automation scripts?** Continue to the main Shopify automation package!

**Support:** support@oubonshop.com
