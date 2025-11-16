# 🚀 TikTok Integration Setup Guide

## Step 1: Get TikTok Sandbox Credentials

1. Go to [TikTok for Developers](https://developers.tiktok.com/)
2. Create an app (if you haven't already)
3. Navigate to **Manage Apps** → Your App → **Basic Information**
4. Copy your credentials:
   - **Client Key** (also called App ID)
   - **Client Secret**

## Step 2: Configure Environment Variables

Add these to your `.env` file:

```bash
# TikTok API Credentials
TIKTOK_CLIENT_KEY=awfl4ben3ftbj54c
TIKTOK_CLIENT_SECRET=your_secret_here

# TikTok Redirect URI (IMPORTANT: Must match TikTok portal EXACTLY)
# For LOCAL testing:
TIKTOK_REDIRECT_URI=http://localhost:8001/api/tiktok/oauth-callback

# For PRODUCTION (deployed):
# TIKTOK_REDIRECT_URI=https://app.oubonshop.com/api/tiktok/oauth-callback
```

⚠️ **IMPORTANT:** The redirect URI must match EXACTLY what you configure in TikTok's developer portal (including http/https, trailing slashes, etc.)

## Step 3: Configure TikTok Developer Portal

### A. Add Products to Your App

In your TikTok app settings, enable these products:

1. **Login Kit** ✅
   - Required for OAuth 2.0 authentication

2. **Display API** ✅
   - Required for user profile and video data

3. **Share Kit** ✅
   - Required for product sharing features

4. **Content Posting API** ✅
   - Required for video uploads

### B. Set Redirect URI

In **Login Kit** settings, add your redirect URI:

**For Local Testing:**
```
http://localhost:8001/api/tiktok/oauth-callback
```

**For Production:**
```
https://app.oubonshop.com/api/tiktok/oauth-callback
```

⚠️ **Note:** You can add BOTH URLs (one for local dev, one for production)

### C. Request Scopes

Make sure these scopes are approved for your app:

- ✅ `user.info.basic` - Basic user information
- ✅ `user.info.profile` - Profile details (name, avatar)
- ✅ `user.info.stats` - Follower/video/like counts
- ✅ `video.list` - Access user's videos
- ✅ `video.upload` - Upload videos
- ✅ `video.publish` - Publish videos to TikTok

### D. Add Sandbox Users (for testing)

In **Sandbox Settings**:
1. Add TikTok accounts as "Test Users"
2. Only these accounts can use your app in sandbox mode
3. You need at least one test account to test the integration

## Step 4: Restart Your Backend

After updating `.env`, restart the FastAPI server:

```bash
# Kill any running server
pkill -f "uvicorn ospra_os"

# Start fresh
uv run uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload
```

## Step 5: Verify Configuration

### Check Backend Status

```bash
curl http://localhost:8001/api/tiktok/status | python3 -m json.tool
```

**Expected response:**
```json
{
  "enabled": true,
  "has_client_key": true,
  "has_client_secret": true,
  "has_redirect_uri": true,
  "redirect_uri": "http://localhost:8001/api/tiktok/oauth-callback",
  "message": "TikTok integration configured",
  "demo_url": "/api/tiktok/demo"
}
```

✅ All fields should be `true`

### Test OAuth URL Generation

```bash
curl http://localhost:8001/api/tiktok/auth/url | python3 -m json.tool
```

**Expected response:**
```json
{
  "authorization_url": "https://www.tiktok.com/v2/auth/authorize?client_key=YOUR_KEY&...",
  "state": "random_csrf_token",
  "message": "Visit authorization_url to connect your TikTok account"
}
```

## Step 6: Test the Integration

### Open Demo Page

```
http://localhost:8001/api/tiktok/demo
```

### Click "Connect with TikTok"

The flow should be:
1. ✅ Demo page → Calls backend `/api/tiktok/auth/url`
2. ✅ Backend generates OAuth URL with your credentials
3. ✅ Frontend redirects to TikTok authorization page
4. ✅ User logs in and approves scopes
5. ✅ TikTok redirects to: `/api/tiktok/oauth-callback?code=XXX`
6. ✅ Callback page exchanges code for token
7. ✅ User is redirected back to demo with access token

## Troubleshooting

### ❌ "redirect_uri_mismatch" Error

**Problem:** The redirect URI in your request doesn't match TikTok's settings

**Solution:**
1. Check your `.env` file: `TIKTOK_REDIRECT_URI`
2. Check TikTok Developer Portal → Login Kit → Redirect URIs
3. They must match EXACTLY (including http/https, ports, paths)

**Local testing:**
```
TIKTOK_REDIRECT_URI=http://localhost:8001/api/tiktok/oauth-callback
```

**Production:**
```
TIKTOK_REDIRECT_URI=https://app.oubonshop.com/api/tiktok/oauth-callback
```

### ❌ "invalid_client" Error

**Problem:** Your client key or secret is incorrect

**Solution:**
1. Verify credentials in TikTok Developer Portal
2. Update `.env` with correct values
3. Restart backend server

### ❌ "access_denied" in Sandbox

**Problem:** The TikTok account is not added as a test user

**Solution:**
1. Go to TikTok Developer Portal → Your App → Sandbox
2. Add the TikTok account as a "Test User"
3. Try authorization again

### ❌ Status shows `enabled: false`

**Problem:** Environment variables not loaded

**Solution:**
```bash
# Check if .env exists
ls -la .env

# Verify it has TikTok credentials
grep TIKTOK .env

# Restart server to reload .env
pkill -f uvicorn
uv run uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload
```

### ❌ "TikTok integration not fully configured"

**Problem:** Missing one or more environment variables

**Solution:**
Make sure ALL three are set in `.env`:
```bash
TIKTOK_CLIENT_KEY=your_key_here
TIKTOK_CLIENT_SECRET=your_secret_here
TIKTOK_REDIRECT_URI=http://localhost:8001/api/tiktok/oauth-callback
```

## Production Deployment Checklist

When deploying to production:

- [ ] Update `TIKTOK_REDIRECT_URI` to production URL
- [ ] Add production redirect URI to TikTok Developer Portal
- [ ] Request production approval from TikTok (after sandbox testing)
- [ ] Update frontend demo URL references
- [ ] Enable HTTPS (required for OAuth in production)
- [ ] Test with production TikTok accounts (not sandbox users)
- [ ] Set up error monitoring (e.g., Sentry)
- [ ] Configure rate limiting
- [ ] Add webhook handling for async events

## Quick Reference

### Local Development URLs
```
Demo Page:      http://localhost:8001/api/tiktok/demo
OAuth Callback: http://localhost:8001/api/tiktok/oauth-callback
Status Check:   http://localhost:8001/api/tiktok/status
API Docs:       http://localhost:8001/docs
```

### Production URLs (example)
```
Demo Page:      https://app.oubonshop.com/api/tiktok/demo
OAuth Callback: https://app.oubonshop.com/api/tiktok/oauth-callback
```

### TikTok Developer Portal
```
Main Portal:    https://developers.tiktok.com/
App Dashboard:  https://developers.tiktok.com/apps/
Documentation:  https://developers.tiktok.com/doc
```

## Environment Variables Summary

```bash
# Required for TikTok Integration
TIKTOK_CLIENT_KEY=awfl4ben3ftbj54c          # From TikTok Developer Portal
TIKTOK_CLIENT_SECRET=your_secret_here        # From TikTok Developer Portal
TIKTOK_REDIRECT_URI=http://localhost:8001/api/tiktok/oauth-callback  # Must match portal

# Optional (after OAuth)
TIKTOK_ACCESS_TOKEN=user_access_token_here   # Obtained after user authorizes
```

## Support

If you encounter issues:

1. Check backend logs for detailed error messages
2. Verify TikTok Developer Portal settings
3. Test with `curl` commands to isolate frontend vs backend issues
4. Check TikTok API status: https://developers.tiktok.com/status
5. Review TikTok's official documentation

---

**Ready to test!** Follow the steps above and you'll have TikTok integration working in minutes. 🚀
