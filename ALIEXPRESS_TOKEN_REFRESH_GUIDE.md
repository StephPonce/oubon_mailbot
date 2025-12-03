# AliExpress Token Refresh System

**Automatic token refresh system to keep AliExpress API access tokens valid**

---

## Overview

The AliExpress token refresh system automatically monitors and refreshes access tokens before they expire, ensuring uninterrupted API access.

### Key Features:
- ✅ **Automatic Refresh:** Checks tokens daily and refreshes 7 days before expiry
- ✅ **Dual API Support:** Handles both Dropshipping (520918) and Affiliate (522382) APIs
- ✅ **Startup Check:** Validates tokens when server starts
- ✅ **Manual Refresh:** API endpoints for manual token refresh
- ✅ **Status Monitoring:** Real-time token status endpoint

---

## How It Works

### Token Lifecycle:
1. **Initial Auth:** OAuth flow generates access + refresh tokens
2. **Access Token:** Valid for 30 days (2592000 seconds)
3. **Refresh Token:** Valid for 60 days (5184000 seconds)
4. **Auto Refresh:** System refreshes 7 days before access token expires
5. **New Tokens:** Refresh generates new access + refresh tokens

### Architecture:
```
┌─────────────────────────────────────────────────────────────┐
│                   Token Refresh System                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │   Scheduler      │───▶  │  Token Checker   │            │
│  │  (Daily 2AM UTC) │      │  (Refresh Logic) │            │
│  └──────────────────┘      └──────────────────┘            │
│            │                         │                       │
│            │                         ▼                       │
│            │                ┌──────────────────┐            │
│            │                │  API Refresher   │            │
│            │                │ (HMAC-SHA256)    │            │
│            │                └──────────────────┘            │
│            │                         │                       │
│            ▼                         ▼                       │
│  ┌───────────────────────────────────────┐                 │
│  │   .secrets/aliexpress_tokens.json     │                 │
│  │   .secrets/aliexpress_affiliate_...   │                 │
│  └───────────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Files

### Core Components:

1. **`ospra_os/api/aliexpress_token_refresh.py`**
   - Token refresh logic
   - Signature generation
   - Token storage

2. **`ospra_os/api/aliexpress_token_routes.py`**
   - API endpoints for manual refresh
   - Token status endpoint

3. **`ospra_os/api/aliexpress_token_scheduler.py`**
   - Background scheduler (daily at 2 AM UTC)
   - Startup check
   - Shutdown cleanup

4. **`ospra_os/main.py`** (updated)
   - Router registration
   - Startup/shutdown events

---

## API Endpoints

### 1. Check Token Status

```bash
GET /api/aliexpress/tokens/status
```

**Response:**
```json
{
  "timestamp": "2025-12-03T10:00:00",
  "dropship": {
    "status": "valid",
    "obtained_at": "2025-12-03T07:10:16",
    "expires_at": "2026-01-02T07:10:16",
    "expires_in_seconds": 2580000,
    "expires_in_days": 29.9,
    "needs_refresh": false,
    "has_refresh_token": true,
    "access_token_preview": "50000401502c291cab40..."
  },
  "affiliate": {
    "status": "valid",
    ...
  }
}
```

### 2. Manually Refresh All Tokens

```bash
POST /api/aliexpress/tokens/refresh/all
```

**Response:**
```json
{
  "status": "started",
  "message": "Token refresh task started in background",
  "timestamp": "2025-12-03T10:00:00"
}
```

### 3. Refresh Dropshipping Token

```bash
POST /api/aliexpress/tokens/refresh/dropship
```

### 4. Refresh Affiliate Token

```bash
POST /api/aliexpress/tokens/refresh/affiliate
```

---

## Configuration

### Refresh Window

Tokens are refreshed **7 days before expiry** by default.

To change, edit `ospra_os/api/aliexpress_token_refresh.py`:

```python
# Refresh window: refresh tokens 7 days before expiry (604800 seconds)
self.refresh_window = 604800
```

### Schedule

By default, the scheduler runs **daily at 2:00 AM UTC**.

To change, edit `ospra_os/api/aliexpress_token_scheduler.py`:

```python
# Add job to run daily at 2 AM UTC
scheduler.add_job(
    scheduled_token_refresh,
    trigger=CronTrigger(hour=2, minute=0),  # Change hour/minute here
    ...
)
```

---

## Usage

### Automatic (Default)

The system runs automatically:
1. **On Startup:** Checks tokens when server starts
2. **Daily at 2 AM UTC:** Scheduled check
3. **Refreshes:** If token expires within 7 days

No manual intervention needed!

### Manual Refresh

#### Using API:
```bash
# Check status
curl http://localhost:8001/api/aliexpress/tokens/status

# Refresh all tokens
curl -X POST http://localhost:8001/api/aliexpress/tokens/refresh/all
```

#### Using Python:
```python
from ospra_os.api.aliexpress_token_refresh import refresh_all_tokens
import asyncio

# Refresh all tokens
results = asyncio.run(refresh_all_tokens())
print(f"Dropship: {results['dropship']}")
print(f"Affiliate: {results['affiliate']}")
```

---

## Monitoring

### Logs

Check server logs for refresh activity:

```
🔄 ALIEXPRESS TOKEN REFRESH SERVICE
Started at: 2025-12-03T02:00:00
Refresh window: 7.0 days before expiry

🔍 CHECKING DROPSHIPPING API TOKEN (App Key: 520918)
✅ Token valid for 23.5 more days
✅ Token is still valid - no refresh needed

🔍 CHECKING AFFILIATE API TOKEN (App Key: 522382)
⚠️  Token expires in 5.2 days - refresh needed
🔄 Refreshing token for app 522382...
✅ Token refreshed successfully!
   New Access Token: 50000400d16ABmoun...
   Expires In: 2592000 seconds
✅ Tokens saved to .secrets/aliexpress_affiliate_tokens.json

📊 REFRESH SUMMARY
Dropshipping API: ✅ Valid
Affiliate API: ✅ Valid
```

### Health Check

Monitor token health via the status endpoint:

```bash
# Get status
curl http://localhost:8001/api/aliexpress/tokens/status | jq '.dropship.expires_in_days'
```

Set up monitoring alerts for when `expires_in_days < 10`.

---

## Troubleshooting

### Tokens Not Refreshing

**Symptom:** Tokens expire even though scheduler is running

**Solutions:**
1. Check logs for refresh errors
2. Verify refresh tokens are valid (check `.secrets/*.json`)
3. Manually trigger refresh: `POST /api/aliexpress/tokens/refresh/all`
4. If refresh token expired (>60 days), re-authorize via OAuth

### Refresh Token Expired

**Symptom:** `"No refresh token available - need to re-authorize"`

**Solution:** Re-run OAuth flow:
- Dropshipping: `https://api-sg.aliexpress.com/oauth/authorize?client_id=520918&response_type=code&redirect_uri=https://oubon-mailbot.onrender.com/api/aliexpress/callback&sp=ae`
- Affiliate: `https://api-sg.aliexpress.com/oauth/authorize?client_id=522382&response_type=code&redirect_uri=https://oubon-mailbot.onrender.com/api/aliexpress-affiliate/callback&sp=ae`

### Signature Errors

**Symptom:** `"IncompleteSignature" or "Invalid signature"`

**Solution:**
- Verify app secrets in `.env` are correct
- Check that `sign_method="sha256"` matches HMAC-SHA256 algorithm
- See `ALIEXPRESS_OAUTH_FINAL_RESEARCH.md` for signature algorithm details

---

## Testing

### Test Token Status

```bash
python3 /tmp/test_token_refresh_system.py
```

### Test API Endpoints

```bash
# Status
curl http://localhost:8001/api/aliexpress/tokens/status | jq

# Refresh (returns immediately, runs in background)
curl -X POST http://localhost:8001/api/aliexpress/tokens/refresh/all
```

---

## Token Files

### Location:
```
.secrets/
├── aliexpress_tokens.json           # Dropshipping API (520918)
└── aliexpress_affiliate_tokens.json # Affiliate API (522382)
```

### Format:
```json
{
  "access_token": "50000401502c291cab4051u...",
  "refresh_token": "50001400702deJ1bd5b73aLc...",
  "expires_in": 2592000,
  "refresh_expires_in": 5184000,
  "user_id": "6661980864",
  "account": "sponce96@icloud.com",
  "obtained_at": "2025-12-03T07:10:16.387012",
  "refreshed_at": "2025-12-25T02:00:00.123456"  // Added on refresh
}
```

---

## Important Notes

### Security:
- ✅ Token files are in `.secrets/` (gitignored)
- ✅ Tokens transmitted over HTTPS only
- ✅ Secrets never logged or exposed in API responses

### Timing:
- **Access tokens:** 30 days (2592000 seconds)
- **Refresh tokens:** 60 days (5184000 seconds)
- **Refresh window:** 7 days before expiry
- **Schedule:** Daily at 2 AM UTC

### Limitations:
- Refresh tokens expire after 60 days
- After refresh token expires, must re-authorize via OAuth
- Maximum refresh attempts per token: unlimited (until refresh token expires)

---

## Next Steps

1. ✅ **System is Active:** Automatic refresh is now running
2. ⏰ **Wait 23 Days:** First auto-refresh will occur 7 days before expiry
3. 📊 **Monitor:** Check status endpoint periodically
4. 🔄 **Test Manual Refresh:** Try manual endpoint to verify it works

---

## Support

### Need to Re-Authorize?

If tokens expire or refresh fails, re-run OAuth:

1. Visit authorization URL (see above)
2. Log in to AliExpress
3. Click "Authorize"
4. New tokens will be saved automatically

### Questions?

See also:
- `ALIEXPRESS_OAUTH_FINAL_RESEARCH.md` - OAuth implementation details
- `ospra_os/api/aliexpress_token_refresh.py` - Source code
- Server logs - Real-time refresh activity
