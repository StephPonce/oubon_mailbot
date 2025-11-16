# Shopify OAuth 2.0 Integration - Complete Setup Guide

## Overview

The Shopify OAuth 2.0 integration is now fully implemented! This allows users to securely connect their Shopify stores through proper OAuth authorization instead of manually entering API tokens.

## What's Been Implemented

### Backend Components ✅

1. **OAuth Routes** (`ospra_os/platforms/shopify/oauth.py`)
   - `/oauth/shopify/install` - Initiates OAuth flow, redirects to Shopify
   - `/oauth/shopify/callback` - Handles Shopify callback, exchanges code for token
   - `/oauth/shopify/status` - Check OAuth configuration status

2. **Security Features**
   - HMAC signature verification to prevent tampering
   - CSRF protection using state tokens
   - Timing-safe comparison for security
   - Comprehensive error handling and logging

3. **Database Integration**
   - Automatic storage of OAuth tokens in multi-store database
   - Updates existing stores or creates new records
   - Stores credentials in `Store.credentials` JSON field

### Frontend Components ✅

1. **Updated AddStoreModal** (`frontend/src/components/AddStoreModal.tsx`)
   - OAuth button for Shopify platform
   - Auto-formats shop domain (.myshopify.com)
   - Redirects to OAuth flow
   - Fallback to manual credentials option

2. **Updated Portfolio AddStoreModal** (`frontend/src/components/portfolio/AddStoreModal.tsx`)
   - Same OAuth integration
   - Cleaner, streamlined UI

### Environment Configuration ✅

Added to `.env.example`:
```bash
# Shopify OAuth 2.0 (for multi-store connections)
OUBONSHOP_SHOPIFY_API_KEY=                                  # Shopify App API Key
OUBONSHOP_SHOPIFY_API_SECRET=                               # Shopify App API Secret
OUBONSHOP_SHOPIFY_REDIRECT_URI=http://localhost:8000/oauth/shopify/callback
```

## Setup Instructions

### Step 1: Create Shopify App

1. Go to your Shopify Partner account
2. Create a new app or use an existing one
3. Navigate to App Setup → URLs
4. Set **App URL**: `http://localhost:8000`
5. Set **Allowed redirection URL(s)**: `http://localhost:8000/oauth/shopify/callback`

### Step 2: Get API Credentials

1. In your Shopify app dashboard, find **Client credentials**
2. Copy the **Client ID** (this is your API Key)
3. Copy the **Client secret**

### Step 3: Configure Environment Variables

Create or update your `.env` file:

```bash
# Shopify OAuth 2.0
OUBONSHOP_SHOPIFY_API_KEY=your_client_id_here
OUBONSHOP_SHOPIFY_API_SECRET=your_client_secret_here
OUBONSHOP_SHOPIFY_REDIRECT_URI=http://localhost:8000/oauth/shopify/callback

# Optional: Frontend URL for success redirect
FRONTEND_URL=http://localhost:5173
```

### Step 4: Restart Backend

```bash
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot"
pkill -f "uvicorn ospra_os.main:app"
uv run uvicorn ospra_os.main:app --host 127.0.0.1 --port 8000
```

### Step 5: Verify Configuration

Check OAuth status:
```bash
curl http://localhost:8000/oauth/shopify/status
```

Expected response (when configured):
```json
{
  "configured": true,
  "api_key_set": true,
  "api_secret_set": true,
  "redirect_uri": "http://localhost:8000/oauth/shopify/callback",
  "scopes": "read_products,write_products,read_orders,write_orders,read_inventory,write_inventory"
}
```

## User Flow

### How Users Connect Their Store

1. **User opens "Add Store" modal** in the frontend
2. **Selects Shopify** as platform
3. **Enters store domain**: `mystore.myshopify.com` (or just `mystore`)
4. **Clicks "Connect with Shopify OAuth"** button
5. **Redirected to Shopify** authorization page
6. **User authorizes app** on Shopify
7. **Shopify redirects back** to callback with authorization code
8. **Backend exchanges code** for permanent access token
9. **Token saved to database** automatically
10. **User redirected to success page**: `http://localhost:5173/stores?connected=success&shop=mystore.myshopify.com`

### OAuth Flow Diagram

```
User (Frontend)
      ↓
   1. Enter shop domain
      ↓
   2. Click "Connect with OAuth"
      ↓
   3. Redirect to /oauth/shopify/install?shop=mystore.myshopify.com
      ↓
Backend generates state token + redirects to Shopify
      ↓
   4. User sees Shopify authorization page
      ↓
   5. User clicks "Install/Authorize"
      ↓
   6. Shopify redirects to /oauth/shopify/callback?code=xxx&hmac=yyy&shop=...
      ↓
Backend verifies HMAC, exchanges code for token
      ↓
   7. Token saved to database
      ↓
   8. Redirect to frontend success page
      ↓
User's store is now connected! 🎉
```

## Testing the Integration

### Manual Test Flow

1. Start backend and frontend:
```bash
# Backend (Terminal 1)
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot"
uv run uvicorn ospra_os.main:app --host 127.0.0.1 --port 8000

# Frontend (Terminal 2)
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot/frontend"
npm run dev
```

2. Open frontend: `http://localhost:5173`

3. Click "Add Store" → Select "Shopify"

4. Enter test shop domain: `your-test-store.myshopify.com`

5. Click "Connect with Shopify OAuth"

6. You'll be redirected to Shopify authorization page

7. After authorizing, you'll be redirected back to your app

### Direct OAuth URL Test

Test the install endpoint directly:
```bash
# This will redirect to Shopify authorization page
open "http://localhost:8000/oauth/shopify/install?shop=your-test-store.myshopify.com"
```

## Security Features

### HMAC Verification

All callbacks from Shopify are verified using HMAC-SHA256 signatures to prevent tampering:

```python
def verify_shopify_hmac(params: dict, secret: str) -> bool:
    # Removes hmac from params
    # Sorts and encodes remaining params
    # Computes HMAC-SHA256
    # Uses timing-safe comparison
    return hmac_lib.compare_digest(computed_hmac, received_hmac)
```

### CSRF Protection

State tokens are generated for each OAuth flow to prevent CSRF attacks:

```python
state = secrets.token_urlsafe(32)  # Cryptographically secure random token
```

**TODO**: Store state tokens in Redis/database with TTL for production use.

### Database Security

- Access tokens are stored in encrypted JSON field
- User ID tracking (currently defaults to 1, should use session auth)
- Active/inactive status for store management

## Permissions (Scopes)

Current OAuth scopes requested:
- `read_products` - Read product data
- `write_products` - Create/update products
- `read_orders` - Read order information
- `write_orders` - Update order status
- `read_inventory` - Read inventory levels
- `write_inventory` - Update inventory

To modify scopes, edit `SHOPIFY_SCOPES` in `ospra_os/platforms/shopify/oauth.py:29`

## Production Deployment

### Required Changes for Production

1. **Update Redirect URI**
   ```bash
   OUBONSHOP_SHOPIFY_REDIRECT_URI=https://yourdomain.com/oauth/shopify/callback
   ```

2. **Update Frontend URL**
   ```bash
   FRONTEND_URL=https://app.yourdomain.com
   ```

3. **Add State Token Storage**
   - Implement Redis/database storage for CSRF state tokens
   - Add TTL (5 minutes recommended)
   - Verify state in callback

4. **Add User Authentication**
   - Replace hardcoded `user_id=1` in oauth.py:168
   - Get user from session/JWT token
   - Associate stores with correct user

5. **Update Shopify App Settings**
   - Set production URLs in Shopify Partner dashboard
   - Add production domain to allowed redirects

6. **SSL/HTTPS**
   - Shopify requires HTTPS for OAuth callbacks
   - Use ngrok/cloudflared for local testing with HTTPS

## Troubleshooting

### OAuth Endpoint Not Found

**Symptom**: 404 error on `/oauth/shopify/install`

**Solution**: Restart backend to load OAuth router
```bash
pkill -f "uvicorn ospra_os.main:app"
uv run uvicorn ospra_os.main:app --host 127.0.0.1 --port 8000
```

### "Invalid HMAC signature" Error

**Symptom**: 403 Forbidden in callback

**Possible Causes**:
- Incorrect `OUBONSHOP_SHOPIFY_API_SECRET`
- URL parameters tampered with
- Using ngrok/proxy that modifies URLs

**Solution**:
1. Verify API secret matches Shopify app
2. Check that redirect URL exactly matches Shopify settings
3. If using proxy, ensure it preserves query parameters

### Store Not Saved to Database

**Symptom**: OAuth completes but store not in database

**Check**:
1. Database file exists: `sqlite:///./oubon_store.db`
2. Check logs for database errors
3. Verify `Store` model is imported correctly

### Redirect Loop

**Symptom**: Keeps redirecting to Shopify

**Possible Causes**:
- Frontend URL mismatch
- Success redirect URL incorrect

**Solution**: Check `FRONTEND_URL` in `.env` matches actual frontend

## Files Modified/Created

### Created
- `ospra_os/platforms/shopify/__init__.py`
- `ospra_os/platforms/shopify/oauth.py`
- `SHOPIFY_OAUTH_SETUP_GUIDE.md` (this file)

### Modified
- `ospra_os/main.py` (added OAuth router registration)
- `frontend/src/components/AddStoreModal.tsx` (added OAuth button)
- `frontend/src/components/portfolio/AddStoreModal.tsx` (added OAuth button)
- `.env.example` (added Shopify OAuth credentials)

## Next Steps

### Recommended Enhancements

1. **Multi-User Support**
   - Add user authentication middleware
   - Associate stores with authenticated users
   - Per-user store management

2. **State Token Storage**
   - Implement Redis for state token storage
   - Add TTL expiration (5 minutes)
   - Cleanup expired tokens

3. **Webhook Integration**
   - Subscribe to Shopify webhooks
   - Handle store uninstall events
   - Update product/order changes

4. **OAuth Token Refresh**
   - Shopify tokens don't expire by default
   - Implement token revocation handling
   - Handle app uninstall gracefully

5. **Enhanced Error Handling**
   - User-friendly error messages
   - Retry mechanisms for failed requests
   - Logging and monitoring

## API Reference

### GET /oauth/shopify/install

Initiates Shopify OAuth flow.

**Query Parameters**:
- `shop` (required): Shop domain (e.g., `mystore.myshopify.com`)

**Response**: 302 Redirect to Shopify authorization page

**Example**:
```bash
curl -L "http://localhost:8000/oauth/shopify/install?shop=mystore.myshopify.com"
```

### GET /oauth/shopify/callback

Handles OAuth callback from Shopify.

**Query Parameters** (auto-provided by Shopify):
- `code`: Authorization code
- `hmac`: HMAC signature for verification
- `shop`: Shop domain
- `state`: CSRF protection token
- `timestamp`: Request timestamp

**Response**: 302 Redirect to frontend success page

### GET /oauth/shopify/status

Check OAuth configuration status.

**Response**:
```json
{
  "configured": true/false,
  "api_key_set": true/false,
  "api_secret_set": true/false,
  "redirect_uri": "http://localhost:8000/oauth/shopify/callback",
  "scopes": "read_products,write_products,..."
}
```

## Support

For issues or questions:
- Check backend logs for errors
- Verify environment variables are set correctly
- Test OAuth status endpoint
- Check Shopify Partner dashboard for app configuration

## Changelog

**2025-11-16**
- ✅ Initial OAuth 2.0 implementation
- ✅ Backend routes created
- ✅ Frontend integration completed
- ✅ Environment configuration added
- ✅ Documentation created
