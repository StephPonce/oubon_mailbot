#!/bin/bash
# Quick deployment script for Oubon Shop website
# Usage: ./DEPLOY.sh [provider]
# Providers: cloudflare, vercel, github

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Oubon Shop - Website Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PROVIDER=${1:-cloudflare}

# Verify we're in the website directory
if [ ! -f "index.html" ]; then
  echo "❌ Error: Must run from website/ directory"
  exit 1
fi

echo "📋 Pre-deployment checklist:"
echo "   ✓ index.html ($(wc -l < index.html) lines)"
echo "   ✓ privacy.html ($(wc -l < privacy.html) lines)"
echo "   ✓ terms.html ($(wc -l < terms.html) lines)"
echo "   ✓ demo/index.html ($(wc -l < demo/index.html) lines)"
echo "   ✓ auth/tiktok/callback.html ($(wc -l < auth/tiktok/callback.html) lines)"
echo ""

case $PROVIDER in
  cloudflare)
    echo "🌐 Deploying to Cloudflare Pages..."
    echo ""
    echo "Manual steps required:"
    echo "1. Go to: https://dash.cloudflare.com/pages"
    echo "2. Click 'Create a project' → 'Upload assets'"
    echo "3. Upload this directory: $(pwd)"
    echo "4. Set custom domain: policies.oubonshop.com"
    echo ""
    echo "Or use Wrangler CLI:"
    echo "  npx wrangler pages publish . --project-name=oubon-shop"
    ;;

  vercel)
    echo "🔺 Deploying to Vercel..."
    if ! command -v vercel &> /dev/null; then
      echo "Installing Vercel CLI..."
      npm install -g vercel
    fi
    echo ""
    vercel --prod
    echo ""
    echo "✅ Deployment complete!"
    echo "Configure custom domain in Vercel dashboard"
    ;;

  github)
    echo "📚 Deploying to GitHub Pages..."
    echo ""
    if [ ! -d ".git" ]; then
      echo "Initializing git repository..."
      git init
      git add .
      git commit -m "Initial deployment"
    fi
    echo ""
    echo "Next steps:"
    echo "1. Create a new GitHub repository"
    echo "2. Run:"
    echo "   git remote add origin <your-repo-url>"
    echo "   git branch -M main"
    echo "   git push -u origin main"
    echo "3. Enable GitHub Pages in repo settings"
    echo "4. Add custom domain: policies.oubonshop.com"
    ;;

  *)
    echo "❌ Unknown provider: $PROVIDER"
    echo "Supported providers: cloudflare, vercel, github"
    exit 1
    ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 After deployment, update TikTok Developer Portal:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Web URL:"
echo "  https://policies.oubonshop.com"
echo ""
echo "Redirect URI:"
echo "  https://policies.oubonshop.com/auth/tiktok/callback.html"
echo ""
echo "Privacy Policy:"
echo "  https://policies.oubonshop.com/privacy.html"
echo ""
echo "Terms of Service:"
echo "  https://policies.oubonshop.com/terms.html"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
