# Oubon Shop Website - Deployment Guide

This directory contains all files for the **policies.oubonshop.com** website.

## 📁 Directory Structure

```
website/
├── index.html              # Main landing page
├── privacy.html            # Privacy policy
├── terms.html              # Terms of service
├── demo/
│   └── index.html          # TikTok integration demo
└── auth/
    └── tiktok/
        └── callback.html   # OAuth callback handler
```

## 🚀 Deployment Instructions

### Option 1: Deploy to Cloudflare Pages (Recommended)

1. **Create Cloudflare Pages Project:**
   ```bash
   # From this directory
   cd website/

   # Initialize git (if not already in a repo)
   git init
   git add .
   git commit -m "Initial website deployment"
   ```

2. **Connect to Cloudflare:**
   - Go to Cloudflare Dashboard → Pages
   - Click "Create a project" → "Connect to Git"
   - Select your repository
   - Set build settings:
     - **Build command:** (leave empty)
     - **Build output directory:** `/`
     - **Root directory:** `website/`

3. **Configure Custom Domain:**
   - In Cloudflare Pages → Custom domains
   - Add: `policies.oubonshop.com`
   - Add DNS records as prompted

### Option 2: Deploy to GitHub Pages

1. **Create a new repository:**
   ```bash
   cd website/
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

2. **Enable GitHub Pages:**
   - Go to repository Settings → Pages
   - Source: Deploy from a branch
   - Branch: `main` / `root`
   - Save

3. **Configure Custom Domain:**
   - In Pages settings, add custom domain: `policies.oubonshop.com`
   - Add DNS CNAME record pointing to `<username>.github.io`

### Option 3: Deploy to Vercel

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

2. **Deploy:**
   ```bash
   cd website/
   vercel --prod
   ```

3. **Configure Domain:**
   - Go to Vercel Dashboard → Project → Settings → Domains
   - Add: `policies.oubonshop.com`
   - Follow DNS configuration instructions

## 🔧 TikTok Developer Portal Configuration

After deploying, update your TikTok app settings:

1. **Web URL:** `https://policies.oubonshop.com`
2. **Redirect URI:** `https://policies.oubonshop.com/auth/tiktok/callback.html`
3. **Privacy Policy:** `https://policies.oubonshop.com/privacy.html`
4. **Terms of Service:** `https://policies.oubonshop.com/terms.html`

## 📋 URL Structure

| Page | URL | Purpose |
|------|-----|---------|
| Landing | https://policies.oubonshop.com | Main website |
| Demo | https://policies.oubonshop.com/demo/ | TikTok integration demo |
| OAuth Callback | https://policies.oubonshop.com/auth/tiktok/callback.html | TikTok OAuth handler |
| Privacy | https://policies.oubonshop.com/privacy.html | Privacy policy |
| Terms | https://policies.oubonshop.com/terms.html | Terms of service |

## ✅ Pre-Deployment Checklist

- [ ] All files are present in the website/ directory
- [ ] OAuth callback URL matches TikTok app settings
- [ ] Privacy and Terms pages are complete
- [ ] Demo page functionality tested locally
- [ ] Custom domain DNS configured
- [ ] SSL certificate is active (should be automatic)

## 🧪 Local Testing

To test locally before deployment:

```bash
# Option 1: Python simple server
cd website/
python3 -m http.server 8080

# Option 2: Node.js http-server
npx http-server website/ -p 8080

# Then visit: http://localhost:8080
```

## 📞 Support

For questions or issues:
- Email: support@oubonshop.com
- Company: Ospra LLC
- Location: Houston, TX

---

**Last Updated:** January 2025
