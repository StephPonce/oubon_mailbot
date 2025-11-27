#!/usr/bin/env python3
"""
AliExpress OAuth Helper
Get a fresh access token for Dropshipping API
"""
import os
import sys
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv, set_key

# Load environment
load_dotenv()

APP_KEY = os.getenv('ALIEXPRESS_APP_KEY')
APP_SECRET = os.getenv('ALIEXPRESS_APP_SECRET')

# OAuth endpoints
AUTHORIZE_URL = "https://oauth.aliexpress.com/authorize"
TOKEN_URL = "https://oauth.aliexpress.com/token"

# Your callback URL (this needs to match what's registered in your AliExpress app)
# Use production HTTPS URL since AliExpress requires HTTPS
REDIRECT_URI = "https://oubon-mailbot.onrender.com/api/aliexpress/callback"


def step1_get_authorization_url():
    """Generate the authorization URL for user to visit"""

    params = {
        'response_type': 'code',
        'client_id': APP_KEY,
        'sp': 'ae',  # REQUIRED: Must be 'ae' for AliExpress accounts
        'redirect_uri': REDIRECT_URI,
        'state': 'random_state_12345',  # Use a random string for security
        'view': 'web',  # Use web view
    }

    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"

    print("\n" + "="*70)
    print("🔐 ALIEXPRESS OAUTH - STEP 1: AUTHORIZATION")
    print("="*70)
    print("")
    print(f"App Key: {APP_KEY}")
    print(f"Redirect URI: {REDIRECT_URI}")
    print("")
    print("📋 INSTRUCTIONS:")
    print("-" * 70)
    print("")
    print("1. Copy this URL and open it in your browser:")
    print("")
    print(f"   {auth_url}")
    print("")
    print("2. Login to your AliExpress account")
    print("")
    print("3. Click 'Authorize' to grant access")
    print("")
    print("4. You'll be redirected to:")
    print(f"   {REDIRECT_URI}?code=XXXXX")
    print("")
    print("5. Copy the 'code' parameter from the URL")
    print("")
    print("6. Run this script again with the code:")
    print(f"   python {__file__} YOUR_CODE_HERE")
    print("")
    print("="*70)
    print("")


def step2_exchange_code_for_token(authorization_code):
    """Exchange authorization code for access token"""

    print("\n" + "="*70)
    print("🔐 ALIEXPRESS OAUTH - STEP 2: TOKEN EXCHANGE")
    print("="*70)
    print("")
    print(f"Authorization Code: {authorization_code[:20]}...")
    print("")

    # Token request parameters
    params = {
        'grant_type': 'authorization_code',
        'client_id': APP_KEY,
        'client_secret': APP_SECRET,
        'code': authorization_code,
        'redirect_uri': REDIRECT_URI,
    }

    print("📡 Requesting access token from AliExpress...")
    print("")

    try:
        response = requests.post(TOKEN_URL, data=params, timeout=30)

        print(f"Response Status: {response.status_code}")
        print("")

        if response.status_code == 200:
            data = response.json()

            if 'access_token' in data:
                access_token = data['access_token']
                expires_in = data.get('expires_in', 'unknown')
                refresh_token = data.get('refresh_token', 'N/A')

                print("✅ SUCCESS! Got new access token")
                print("")
                print(f"Access Token: {access_token[:30]}...{access_token[-10:]}")
                print(f"Expires In: {expires_in} seconds")
                print(f"Refresh Token: {refresh_token[:20] if refresh_token != 'N/A' else 'N/A'}...")
                print("")

                # Update .env file
                env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
                set_key(env_path, 'ALIEXPRESS_ACCESS_TOKEN', access_token)

                print("✅ Updated .env file with new access token!")
                print("")
                print("="*70)
                print("🎉 OAUTH COMPLETE!")
                print("="*70)
                print("")
                print("You can now use the AliExpress Dropshipping API.")
                print("")

                return True
            else:
                print("❌ Error: No access_token in response")
                print("")
                print("Response:")
                print(response.text)
                return False
        else:
            print(f"❌ Token request failed: {response.status_code}")
            print("")
            print("Response:")
            print(response.text)
            return False

    except Exception as e:
        print(f"❌ Error during token exchange: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main OAuth flow"""

    if not APP_KEY or not APP_SECRET:
        print("❌ Error: ALIEXPRESS_APP_KEY and ALIEXPRESS_APP_SECRET must be set in .env")
        sys.exit(1)

    # Check if user provided authorization code
    if len(sys.argv) > 1:
        # Step 2: Exchange code for token
        authorization_code = sys.argv[1]
        success = step2_exchange_code_for_token(authorization_code)
        sys.exit(0 if success else 1)
    else:
        # Step 1: Show authorization URL
        step1_get_authorization_url()


if __name__ == "__main__":
    main()
