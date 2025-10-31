# ✅ SIMPLE COPY/PASTE METHOD - 2 MINUTES

Since Dawn doesn't have built-in Custom CSS, here's the easiest working method.
**Just copy/paste code directly into your theme files.**

---

## 📝 Step 1: Add CSS to base.css (1 minute)

1. **Go to:** Shopify Admin → Online Store → Themes
2. **Click:** "Actions" → "Edit code"
3. **In left sidebar, click "Assets" folder**
4. **Find and click:** `base.css` (it's in the Assets folder)
5. **Scroll to the VERY BOTTOM** of the file
6. **Open:** `shopify_theme_oubon/assets/oubon-custom.css` (from this package)
7. **Copy ALL the CSS** (Cmd+A, Cmd+C or Ctrl+A, Ctrl+C)
8. **Go back to Shopify**
9. **Paste at the very bottom** of `base.css`
10. **Click "Save"** (top right)

**That's it!** Your theme now has Oubon branding.

---

## 🎨 What This Does

By adding our CSS to the bottom of `base.css`, it overrides Dawn's default styles:

- ✅ Black header with white text
- ✅ Electric blue buttons
- ✅ Hover effects
- ✅ Dark footer
- ✅ Product card animations
- ✅ Mobile optimizations

---

## 🔍 How to Find base.css

Visual guide:

```
Edit code page:
├── Layout/
├── Templates/
├── Sections/
├── Snippets/
└── Assets/                    ← Click here
    ├── base.css              ← Click this file
    ├── component-card.css
    ├── ... other CSS files
```

`base.css` is usually around **4000-6000 lines** long.

**Scroll all the way to the bottom** and paste our CSS after the last closing brace `}`.

---

## ✅ Verify It Worked

1. **Go back to:** Themes page
2. **Click:** "Customize"
3. **Check:**
   - Header should be black with white text
   - Buttons should be blue
   - If you hover over buttons, they should lift slightly

4. **If nothing changed:**
   - Clear browser cache (Cmd+Shift+R or Ctrl+Shift+R)
   - Or open in Incognito/Private window

---

## 🐛 Troubleshooting

### "I can't find base.css"

**Solution:** It might be named differently in your theme version.
- Look for: `theme.css` or `styles.css` or `global.css`
- Any CSS file in the Assets folder will work
- Just paste at the bottom

### "The file is too long, I can't scroll to bottom"

**Solution:** Use keyboard shortcut
- Click inside the code editor
- Press: Cmd+Down Arrow (Mac) or Ctrl+End (Windows)
- This jumps to the very bottom
- Paste the CSS there

### "I get an error when saving"

**Solution:** Check for syntax errors
- Make sure you pasted AFTER the last `}` in the file
- Don't paste in the middle of existing code
- Leave a blank line before pasting for safety

### "Some styles still look wrong"

**Solution:** Our CSS needs to be LAST to override everything
- Make sure you pasted at the VERY bottom of base.css
- There should be NO code after our CSS
- Save again

---

## 🎯 Alternative: Create New CSS File (Slightly More Steps)

If you prefer not to modify base.css:

1. **In Edit code, click Assets folder**
2. **Click "Add a new asset"**
3. **Select "Create a blank file"**
4. **Name it:** `oubon-custom.css`
5. **Click "Create asset"**
6. **Paste all the CSS** from our file
7. **Save**
8. **Now link it in theme.liquid:**
   - In left sidebar, click **Layout** folder
   - Click **theme.liquid**
   - Press Cmd+F (Mac) or Ctrl+F (Windows)
   - Search for: `</head>`
   - **Just above** `</head>`, add a new line with:
     ```liquid
     {{ 'oubon-custom.css' | asset_url | stylesheet_tag }}
     ```
   - Save

This method keeps our CSS separate from Dawn's files.

---

## 📊 Which Method is Better?

| Method | Pros | Cons |
|--------|------|------|
| **Add to base.css** | ✅ Faster (1 step)<br>✅ Always works | ⚠️ Mixed with theme code |
| **Create new file** | ✅ Clean separation<br>✅ Easier to update | ⚠️ 2 steps required |

**For most users:** Just add to base.css. It's faster and works perfectly.

**For developers:** Create new file for better organization.

---

## 🎉 After Installation

Once your theme is branded:

1. **Test on mobile:** Use phone or Chrome DevTools
2. **Check all pages:** Home, Product, Collection, Cart
3. **Clear cache** if styles don't show immediately

Then move on to:
- Adding products (automation scripts)
- Creating collections (automation scripts)
- Uploading images
- Configuring store settings

---

## 💡 Pro Tip

**Backup first!** Before editing base.css:
1. Select all the original content (Cmd+A / Ctrl+A)
2. Copy it (Cmd+C / Ctrl+C)
3. Paste into a text file on your computer
4. Save as `base-css-backup.txt`

Now you can safely add our CSS. If anything goes wrong, you can restore from backup.

---

**Need help?** Contact: support@oubonshop.com

**Ready to automate product setup?** Check out the `shopify_automation/` folder for scripts to auto-create products and collections!
