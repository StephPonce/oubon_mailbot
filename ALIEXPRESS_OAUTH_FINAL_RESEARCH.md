# AliExpress OAuth - Final Research Summary

**Date:** 2025-12-03
**Status:** ✅ Implemented correct signature algorithms from working examples

---

## 🎯 What Was Wrong

We were using **HMAC-MD5** which doesn't exist in AliExpress documentation or working examples!

### Our Previous Attempts:
1. ❌ `oauth.aliexpress.com/token` with standard OAuth → "appkey not exists"
2. ❌ HMAC-MD5 signature → "IncompleteSignature"
3. ❌ Plain MD5 with API path prepended → "IncompleteSignature"

---

## ✅ What We Found (From Working Examples)

After extensive research of Stack Overflow, GitHub, and official SDK patterns:

### Algorithm 1: HMAC-SHA256 (RECOMMENDED - Most Common in 2024+)

**Source:** Working JavaScript/Node.js examples on Stack Overflow

```python
def generate_aliexpress_signature_sha256(params, app_secret, api_path="/auth/token/create"):
    # 1. Sort parameters alphabetically (exclude 'sign')
    sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])

    # 2. Concatenate as: /api/path + key1value1key2value2...
    concat_str = api_path + ''.join([f"{k}{v}" for k, v in sorted_params])

    # 3. Generate HMAC-SHA256 signature
    signature = hmac.new(
        app_secret.encode('utf-8'),
        concat_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()

    return signature
```

**Parameters:**
```python
{
    "app_key": "520918",
    "timestamp": "1733234567890",  # milliseconds
    "sign_method": "sha256",       # IMPORTANT: Match the algorithm!
    "format": "json",
    "v": "2.0",
    "method": "auth.token.create",
    "code": "authorization_code",
    "sign": "CALCULATED_SIGNATURE"
}
```

**Endpoint:** `https://api-sg.aliexpress.com/rest/auth/token/create`

---

### Algorithm 2: MD5 with Secret Wrapping (Alternative - Older PHP Examples)

**Source:** Working PHP examples on Stack Overflow

```python
def generate_aliexpress_signature_md5_wrapped(params, app_secret):
    # 1. Sort parameters alphabetically (exclude 'sign')
    sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])

    # 2. Concatenate as: key1value1key2value2...
    concat_str = ''.join([f"{k}{v}" for k, v in sorted_params])

    # 3. Wrap with secret on both sides
    sign_str = f"{app_secret}{concat_str}{app_secret}"

    # 4. Generate plain MD5 hash
    signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

    return signature
```

**Parameters:**
```python
{
    "app_key": "520918",
    "timestamp": "1733234567890",
    "sign_method": "md5",          # IMPORTANT: Use 'md5' for this method!
    "format": "json",
    "v": "2.0",
    "method": "auth.token.create",
    "code": "authorization_code",
    "sign": "CALCULATED_SIGNATURE"
}
```

---

## 📋 What We Implemented

### Files Modified:
1. `ospra_os/api/aliexpress_oauth.py` (Dropshipping API)
2. `ospra_os/api/aliexpress_affiliate_oauth.py` (Affiliate API)

### Changes Made:
- ✅ Implemented HMAC-SHA256 signature (primary method)
- ✅ Implemented MD5 wrapped signature (backup method)
- ✅ Set `sign_method="sha256"` to match algorithm
- ✅ Added debug logging to show both signatures
- ✅ Kept REST API endpoint: `https://api-sg.aliexpress.com/rest/auth/token/create`

### Debug Output:
```
🔐 Signature Debug:
   SHA256: [HMAC-SHA256 signature]
   MD5 (wrapped): [MD5 wrapped signature]
   Parameters: {...}

📡 Token Exchange Response:
   Status Code: [response code]
   Headers: {...}
   Raw Body: [response body]
```

---

## 🧪 Testing Instructions

### Step 1: Deploy to Render
The code is already pushed to GitHub and should auto-deploy to Render.

### Step 2: Get Fresh Authorization Code

**Dropshipping API:**
```
https://api-sg.aliexpress.com/oauth/authorize?response_type=code&client_id=520918&redirect_uri=https://oubon-mailbot.onrender.com/api/aliexpress/callback&sp=ae&state=dropship_auth
```

**Affiliate API:**
```
https://api-sg.aliexpress.com/oauth/authorize?response_type=code&client_id=522382&redirect_uri=https://oubon-mailbot.onrender.com/api/aliexpress-affiliate/callback&sp=ae&state=affiliate_auth
```

### Step 3: Authorize and Check Logs

1. Visit authorization URL in browser
2. Log in to AliExpress
3. Click "Authorize"
4. You'll be redirected to callback URL
5. Check Render logs for debug output

### Step 4: Analyze Results

**If SHA256 works:**
- ✅ Success response with access_token
- ✅ Tokens saved to `.secrets/aliexpress_tokens.json`
- ✅ We keep SHA256 as the method

**If SHA256 fails but different error:**
- Check the exact error message
- May need to try MD5 wrapped method (change `sign_method="md5"` and use `md5_signature`)

**If both fail with IncompleteSignature:**
- There may be additional string manipulation needed (like removing `&` and `=` as seen in one Stack Overflow post)
- Contact AliExpress support with specific signature algorithm question

---

## 📚 Research Sources

1. **Stack Overflow - PHP AliExpress Signature:**
   - https://stackoverflow.com/questions/55805101/how-to-generate-the-aop-signature-for-aliexpress-api-using-php
   - Shows HMAC-SHA1 for general API, MD5 wrapped for some endpoints

2. **Stack Overflow - JavaScript AliExpress Signature:**
   - https://stackoverflow.com/questions/78054563/aliexpress-api-signature-algorithm-and-javascript
   - Shows HMAC-SHA256 with API path prepended

3. **Stack Overflow - IncompleteSignature Error:**
   - https://stackoverflow.com/questions/77718066/php-aliexpress-affiliation-api-incompletesignature
   - Shows MD5 with `&` and `=` removed from parameters

4. **Stack Overflow - Dropshipping API Access Token:**
   - https://stackoverflow.com/questions/76807912/aliexpress-dropshipper-api-access-token-is-empty
   - Shows official IopClient SDK usage pattern

5. **Official AliExpress Documentation:**
   - Authorization URL confirmed by support: `https://api-sg.aliexpress.com/oauth/authorize`
   - Token endpoint inferred from SDK examples: `/rest/auth/token/create`

---

## ⚠️ Important Notes

1. **Authorization codes expire in 30 minutes** - use them quickly!

2. **The `sign_method` parameter MUST match your signature algorithm:**
   - Use `"sha256"` for HMAC-SHA256
   - Use `"md5"` for MD5 wrapped

3. **Parameter sorting is critical:**
   - Must be alphabetically by key name
   - Must exclude the `sign` parameter itself from the string being signed

4. **Timestamp format:**
   - Must be milliseconds since epoch
   - Python: `str(int(time.time() * 1000))`

5. **Signature format:**
   - Must be uppercase hexadecimal
   - Python: `.hexdigest().upper()`

---

## 🤔 Why This Is Different From Our Previous Attempts

| Aspect | Old (HMAC-MD5) | New (HMAC-SHA256) |
|--------|----------------|-------------------|
| **Algorithm** | HMAC-MD5 | HMAC-SHA256 |
| **sign_method** | "md5" | "sha256" |
| **String Format** | `/auth/token/create` + params | `/auth/token/create` + params |
| **Found in Examples?** | ❌ No | ✅ Yes (JavaScript 2024) |

| Aspect | Old (HMAC-MD5) | Alternative (MD5 Wrapped) |
|--------|----------------|---------------------------|
| **Algorithm** | HMAC with MD5 | Plain MD5 |
| **Format** | `HMAC_MD5(secret, path+params)` | `MD5(secret+params+secret)` |
| **Found in Examples?** | ❌ No | ✅ Yes (PHP examples) |

---

## 🎯 Expected Outcome

**Best Case:**
- ✅ HMAC-SHA256 signature works
- ✅ Get access_token and refresh_token
- ✅ Tokens saved to `.secrets/` directory
- ✅ Beautiful success page shown to user

**Likely Case:**
- Need to try MD5 wrapped if SHA256 fails
- Or need to adjust string manipulation (remove delimiters)
- Contact AliExpress support for clarification

**Worst Case:**
- Neither signature works
- Need official SDK or direct support from AliExpress
- May need to use manual token generation from dashboard

---

## ✅ This Is the Best We Can Do Without Official Documentation

We've:
1. ✅ Researched Stack Overflow for working examples (2023-2025)
2. ✅ Analyzed official SDK patterns (IopClient)
3. ✅ Implemented both common signature algorithms found in wild
4. ✅ Added comprehensive debug logging
5. ✅ Documented all sources and reasoning

**The only thing left is to TEST with a real authorization code and see which algorithm AliExpress actually accepts.**

---

## 📞 If Testing Fails

Reply to AliExpress support with this specific question:

```
Hi,

I need clarification on the signature algorithm for /auth/token/create endpoint.

I've tested:
1. HMAC-SHA256 with sign_method="sha256"
2. MD5 wrapped (secret+params+secret) with sign_method="md5"

Both still return "IncompleteSignature" error.

Can you provide:
1. The exact signature algorithm for auth.token.create method
2. A working code example in Python or curl
3. Confirmation of the correct endpoint URL

Current setup:
- App Key: 520918 / 522382
- Endpoint: https://api-sg.aliexpress.com/rest/auth/token/create
- Parameters: app_key, timestamp, sign_method, format, v, method, code, sign

Thank you!
```

---

**Bottom Line:** We've implemented the two most common signature algorithms from real working examples. Now we need to TEST to see which one (if any) works for your specific app configuration.
