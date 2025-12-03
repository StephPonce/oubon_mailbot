# Ospra Intelligence - Marketing Site

Beautiful, responsive landing page for Ospra Intelligence.

## 🚀 Quick Deploy (FREE)

### Option 1: Netlify (Recommended - Easiest)
1. Go to [netlify.com](https://netlify.com) and sign up (free)
2. Click "Add new site" → "Deploy manually"
3. Drag and drop this entire `marketing-site` folder
4. Done! You get a free URL like `random-name.netlify.app`
5. Add your custom domain in Site Settings → Domain Management

### Option 2: Vercel
1. Go to [vercel.com](https://vercel.com) and sign up (free)
2. Click "Add New" → "Project"
3. Upload this folder or connect to GitHub
4. Done! Free URL + custom domain support

### Option 3: GitHub Pages
1. Create a GitHub repo
2. Push this folder to the repo
3. Go to Settings → Pages
4. Select branch and folder
5. Free hosting at `username.github.io/repo-name`

### Option 4: Cloudflare Pages
1. Go to [pages.cloudflare.com](https://pages.cloudflare.com)
2. Connect your GitHub or upload directly
3. Free hosting with great performance

## 🔧 Customization

### Update Links
Find and replace these URLs in `index.html`:
- `https://app.ospra.io` → Your actual dashboard URL
- `https://api.ospra.io` → Your actual API URL

### Update Content
- Hero section: Line ~100
- Features: Line ~300
- Pricing: Line ~450
- Testimonials: Line ~550
- FAQ: Line ~600

### Colors (Tailwind Config)
```javascript
colors: {
    nest: '#8B7355',      // Earthy brown
    flight: '#87CEEB',    // Sky blue
    soar: '#0EA5E9',      // Bright blue
    stratosphere: '#7C3AED', // Purple
    space: '#1E1B4B',     // Deep space
}
```

## 📁 Files

```
marketing-site/
├── index.html      # Complete landing page
└── README.md       # This file
```

## 🌐 Domain Setup

### If you have ospra.io:
1. Deploy this site
2. In your DNS settings, add:
   - `A` record: `@` → Netlify/Vercel IP
   - `CNAME` record: `www` → your-site.netlify.app

### Subdomain setup:
- `ospra.io` → Marketing site (this)
- `app.ospra.io` → Dashboard (your Render app)

## 📱 Features

- ✅ Fully responsive (mobile, tablet, desktop)
- ✅ Modern design with animations
- ✅ Sky/flight theme matching your brand
- ✅ Pricing cards with all 4 tiers
- ✅ Stratosphere waitlist form
- ✅ FAQ accordion
- ✅ Smooth scroll navigation
- ✅ SEO meta tags
- ✅ Fast loading (Tailwind via CDN)

## 🎨 Screenshots

The site includes:
- Hero with animated dashboard mockup
- Problem/Solution section
- 4-column feature grid
- 3-step "How it works"
- Pricing cards (Nest, Flight, Soar, Stratosphere)
- Testimonials
- FAQ accordion
- CTA section
- Footer with links

## 💡 Next Steps

1. Deploy the site
2. Connect your domain
3. Update the waitlist API endpoint
4. Add real testimonials when you get them
5. Add analytics (Google Analytics, Plausible, etc.)

---

Built with ❤️ for Ospra Intelligence
