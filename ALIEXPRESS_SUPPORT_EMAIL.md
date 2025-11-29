# Email to AliExpress Developer Support

**Subject:** OAuth Token Exchange Failing for Both Affiliate and Dropshipping APIs - "appkey not exists" Error

---

## Support Request Details

**Developer Account:** [Your AliExpress developer account email]
**Issue Type:** OAuth Authentication
**Severity:** Critical - Cannot access either API
**Apps Affected:**
- Affiliate API - App Key: 522382
- Dropshipping API - App Key: 520918

---

## Issue Summary

I have two approved AliExpress applications that are both experiencing the **same OAuth token exchange error**. The authorization step works correctly (I receive authorization codes), but the token exchange endpoint returns an error indicating the app keys don't exist.

---

## Issue #1: Affiliate API (App Key: 522382)

### Problem
OAuth token exchange fails with error: **"appkey not exists"**

### Steps Taken

1. **Authorization Request** (✅ WORKS):
   ```
   GET https://api-sg.aliexpress.com/oauth/authorize
   Parameters:
   - response_type: code
   - client_id: 522382
   - redirect_uri: https://oubon-mailbot.onrender.com/api/aliexpress-affiliate/callback
   - sp: ae
   ```
   **Result:** Successfully redirects with authorization code (e.g., `3_522382_VDNEosRXP0mCpt6AG70svw233157`)

2. **Token Exchange Request** (❌ FAILS):
   ```
   POST https://oauth.aliexpress.com/token
   Content-Type: application/x-www-form-urlencoded

   Parameters:
   - client_id: 522382
   - app_key: 522382
   - client_secret: [secret]
   - app_secret: [secret]
   - grant_type: authorization_code
   - code: [authorization code from step 1]
   - redirect_uri: https://oubon-mailbot.onrender.com/api/aliexpress-affiliate/callback
   - sp: ae
   ```

   **Response (HTTP 200):**
   ```json
   {
     "error_msg": "appkey not exists",
     "error_code": "param-appkey.not.exists"
   }
   ```

### Additional Context
- I previously had a working access token for this app that has since expired
- The app is approved and shows as active in my developer console
- The authorization code is fresh (tested within seconds of generation)
- Tried multiple variations of parameters (client_id, app_key, both)

---

## Issue #2: Dropshipping API (App Key: 520918)

### Problem
**Identical error** as Affiliate API

### Steps Taken

1. **Authorization Request** (✅ WORKS):
   ```
   GET https://api-sg.aliexpress.com/oauth/authorize
   Parameters:
   - response_type: code
   - client_id: 520918
   - redirect_uri: https://oubon-mailbot.onrender.com/api/aliexpress/callback
   - sp: ae
   ```
   **Result:** Successfully redirects with authorization code

2. **Token Exchange Request** (❌ FAILS):
   ```
   POST https://oauth.aliexpress.com/token
   [Same parameters as Affiliate API but with app key 520918]
   ```

   **Response (HTTP 200):**
   ```json
   {
     "error_msg": "appkey not exists",
     "error_code": "param-appkey.not.exists"
   }
   ```

---

## Questions for Support

1. **Is `https://oauth.aliexpress.com/token` the correct endpoint for token exchange?**
   - Both of my apps fail with "appkey not exists" at this endpoint
   - Is there a different endpoint for Affiliate vs. Dropshipping APIs?

2. **Are my apps properly configured for OAuth token exchange?**
   - App 522382 (Affiliate API)
   - App 520918 (Dropshipping API)
   - Both show as approved in my developer console
   - Both successfully complete the authorization step

3. **Is there an alternative authentication method?**
   - Can I generate access tokens manually from the developer console?
   - Is there a different OAuth flow I should be using?
   - Are these APIs compatible with OAuth 2.0 token exchange?

4. **What is causing the "param-appkey.not.exists" error?**
   - The authorization endpoint recognizes my app keys
   - But the token exchange endpoint does not
   - This suggests the endpoints are checking different databases?

---

## What I've Tried

### Different Parameter Combinations
- ✅ Sending both `client_id` and `app_key` (same value)
- ✅ Sending both `client_secret` and `app_secret` (same value)
- ✅ Including `sp=ae` parameter
- ✅ Testing with fresh authorization codes (within seconds)
- ✅ Different redirect URIs (both on approved list)

### Different Signature Methods
- ✅ MD5 signature
- ✅ HMAC-MD5 signature
- ✅ No signature (OAuth 2.0 standard)

### Verified Configuration
- ✅ Apps are approved and active in developer console
- ✅ Redirect URIs are registered correctly
- ✅ Authorization step works (proves app keys are valid)
- ✅ Using correct app secrets

---

## Expected Behavior

Based on OAuth 2.0 standard, after receiving an authorization code, I should be able to exchange it for an access token using:

```
POST /token
{
  "grant_type": "authorization_code",
  "code": "[auth_code]",
  "client_id": "[app_key]",
  "client_secret": "[app_secret]",
  "redirect_uri": "[callback_url]"
}
```

**Expected Response:**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 86400
}
```

**Actual Response:**
```json
{
  "error_msg": "appkey not exists",
  "error_code": "param-appkey.not.exists"
}
```

---

## Request for Assistance

Could you please help me understand:

1. Why the token exchange endpoint doesn't recognize my app keys when the authorization endpoint does?
2. What is the correct OAuth token exchange endpoint for:
   - Affiliate API (app 522382)
   - Dropshipping API (app 520918)
3. If OAuth token exchange isn't supported, how should I obtain access tokens?
4. Is there additional app configuration required to enable OAuth token exchange?

---

## Technical Details

- **Implementation:** FastAPI backend with `httpx` for HTTP requests
- **OAuth Flow:** Standard Authorization Code Grant (OAuth 2.0)
- **Testing:** Automated callback handler that immediately exchanges codes
- **Timing:** Codes tested within seconds of generation (not expired)
- **Documentation Referenced:**
  - https://developers.aliexpress.com/
  - Standard OAuth 2.0 specification

---

## Urgency

Both APIs are currently unusable due to this authentication issue. My previous Affiliate API access token has expired, and I cannot obtain new tokens for either API.

I would greatly appreciate guidance on:
- The correct token exchange process for these apps
- Or manual token generation if OAuth isn't supported
- Any additional configuration needed

Thank you for your assistance!

---

**Developer Contact:**
[Your Name]
[Your Email]
[Your Phone Number (optional)]

**App Keys:**
- Affiliate: 522382
- Dropshipping: 520918
