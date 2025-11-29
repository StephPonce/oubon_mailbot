# Gmail OAuth Setup Guide

## Problem
Getting "Error 400: redirect_uri_mismatch" when trying to connect Gmail account.

## Solution: Configure Google Cloud Console

### Step 1: Go to Google Cloud Console
1. Visit https://console.cloud.google.com
2. Select your project (or create a new one)

### Step 2: Enable Gmail API
1. Go to **APIs & Services** → **Library**
2. Search for "Gmail API"
3. Click **Enable** (if not already enabled)

### Step 3: Configure OAuth Consent Screen
1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** user type (unless you have a Google Workspace)
3. Fill in the required fields:
   - App name: `OspraOS Email Automation`
   - User support email: Your email
   - Developer contact email: Your email
4. Click **Save and Continue**
5. On the "Scopes" page, click **Add or Remove Scopes**
6. Add these scopes:
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/userinfo.email`
7. Click **Save and Continue**
8. On "Test users", add your Gmail address (hello@oubonshop.com)
9. Click **Save and Continue**

### Step 4: Create OAuth 2.0 Credentials
1. Go to **APIs & Services** → **Credentials**
2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
3. Select **Web application**
4. Name it: `OspraOS Local Development`
5. Under **Authorized redirect URIs**, click **+ ADD URI**
6. Add this EXACT redirect URI:
   ```
   http://localhost:8001/api/email-oauth/gmail/callback
   ```
7. Click **Create**
8. Save your Client ID and Client Secret

### Step 5: Update .env File
Add these to your `.env` file:
```bash
GOOGLE_OAUTH_CLIENT_ID="your-client-id-here.apps.googleusercontent.com"
GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret-here"
```

### Step 6: Restart Backend Server
```bash
# Stop all running servers
lsof -ti:8001 | xargs kill -9

# Start backend
cd "/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS"
uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001
```

### Step 7: Test Gmail Connection
1. Go to http://localhost:5173
2. Navigate to Email Dashboard → Settings
3. Click on Gmail to connect
4. You should now be redirected to Google's OAuth page
5. Grant permissions
6. You'll be redirected back to the app with your account connected

## Troubleshooting

### Still Getting redirect_uri_mismatch?
- Make sure the redirect URI is EXACTLY: `http://localhost:8001/api/email-oauth/gmail/callback`
- No trailing slash
- Must be `http://` not `https://`
- Must be `localhost` not `127.0.0.1`

### OAuth Consent Screen Shows "Unverified App"?
- This is normal for development
- Click "Advanced" → "Go to OspraOS (unsafe)"
- This only appears because the app isn't published

### Getting "Access Blocked: This app's request is invalid"?
- Make sure you added your email as a test user in the OAuth consent screen
- Check that all required scopes are added

## Supported Email Providers

Currently configured:
- **Gmail** (OAuth 2.0) ✅
- **Outlook** (OAuth 2.0) - Requires Microsoft Azure App Registration
- **Yahoo** (IMAP/SMTP) - Requires app-specific password
- **iCloud** (IMAP/SMTP) - Requires app-specific password
- **ProtonMail** (IMAP/SMTP via Bridge)
- **Zoho** (IMAP/SMTP) - Requires app-specific password

## Next Steps for Other Providers

### Microsoft Outlook OAuth Setup
To enable Outlook OAuth, you need to:
1. Register app at https://portal.azure.com
2. Add redirect URI: `http://localhost:8001/api/email-oauth/outlook/callback`
3. Set environment variables:
   ```
   MICROSOFT_OAUTH_CLIENT_ID="your-app-id"
   MICROSOFT_OAUTH_CLIENT_SECRET="your-secret"
   ```

### IMAP/SMTP Providers (Yahoo, iCloud, Zoho)
These use app-specific passwords instead of OAuth:
1. Generate an app-specific password from your email provider
2. Use the "Connect New Email Account" interface
3. Select the provider and enter credentials

## Security Notes
- Never commit your `.env` file to git
- OAuth tokens are encrypted before storing in the database
- Refresh tokens allow long-term access without re-authentication
- You can revoke access anytime from Google Account settings
