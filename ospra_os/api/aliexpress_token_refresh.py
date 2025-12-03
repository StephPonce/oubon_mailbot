"""
AliExpress Token Refresh Service

Automatically refreshes access tokens before they expire using refresh tokens.
"""
import json
import time
import hashlib
import hmac
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os


class AliExpressTokenRefresher:
    """Handles automatic token refresh for AliExpress APIs"""

    def __init__(self):
        # Dropshipping API
        self.dropship_app_key = os.getenv("ALIEXPRESS_APP_KEY", "520918")
        self.dropship_app_secret = os.getenv("ALIEXPRESS_APP_SECRET", "idjX6tOzHx6urVsSylVzEcHZKwBN4YhN")
        self.dropship_tokens_file = Path(".secrets/aliexpress_tokens.json")

        # Affiliate API
        self.affiliate_app_key = os.getenv("ALIEXPRESS_AFFILIATE_APP_KEY", "522382")
        self.affiliate_app_secret = os.getenv("ALIEXPRESS_AFFILIATE_APP_SECRET", "9Kkt2Mn5icXLV7fShLfT38OarpjXqtrL")
        self.affiliate_tokens_file = Path(".secrets/aliexpress_affiliate_tokens.json")

        # Token refresh endpoint
        self.token_refresh_url = "https://api-sg.aliexpress.com/rest/auth/token/create"

        # Refresh window: refresh tokens 7 days before expiry (604800 seconds)
        self.refresh_window = 604800

    def generate_signature_sha256(self, params: dict, app_secret: str, api_path: str = "/auth/token/create") -> str:
        """
        Generate HMAC-SHA256 signature for AliExpress API
        """
        # Sort parameters alphabetically (exclude 'sign')
        sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])

        # Concatenate as: /api/path + key1value1key2value2...
        concat_str = api_path + ''.join([f"{k}{v}" for k, v in sorted_params])

        # Calculate HMAC-SHA256 signature
        signature = hmac.new(
            app_secret.encode('utf-8'),
            concat_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()

        return signature

    def load_tokens(self, tokens_file: Path) -> Optional[Dict[str, Any]]:
        """Load tokens from file"""
        if not tokens_file.exists():
            return None

        try:
            with open(tokens_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading tokens from {tokens_file}: {e}")
            return None

    def save_tokens(self, tokens: dict, tokens_file: Path) -> bool:
        """Save tokens to file"""
        try:
            # Ensure .secrets directory exists
            tokens_file.parent.mkdir(parents=True, exist_ok=True)

            # Add timestamp
            tokens["refreshed_at"] = datetime.now().isoformat()

            with open(tokens_file, 'w') as f:
                json.dump(tokens, f, indent=2)

            print(f"✅ Tokens saved to {tokens_file}")
            return True
        except Exception as e:
            print(f"❌ Error saving tokens to {tokens_file}: {e}")
            return False

    def is_token_expiring_soon(self, tokens: dict) -> bool:
        """
        Check if access token is expiring soon (within refresh window)

        Returns:
            True if token expires within refresh_window seconds
        """
        if not tokens:
            return True

        # Get the obtained_at timestamp
        obtained_at_str = tokens.get("obtained_at") or tokens.get("refreshed_at")
        if not obtained_at_str:
            return True

        try:
            obtained_at = datetime.fromisoformat(obtained_at_str)
        except (ValueError, TypeError):
            return True

        # Get expiration time in seconds
        expires_in = tokens.get("expires_in", 0)
        if not expires_in:
            return True

        # Calculate expiration datetime
        expires_at = obtained_at + timedelta(seconds=expires_in)

        # Calculate time until expiration
        time_until_expiry = (expires_at - datetime.now()).total_seconds()

        # Check if within refresh window
        should_refresh = time_until_expiry <= self.refresh_window

        if should_refresh:
            days_until_expiry = time_until_expiry / 86400
            print(f"⚠️  Token expires in {days_until_expiry:.1f} days - refresh needed")
        else:
            days_until_expiry = time_until_expiry / 86400
            print(f"✅ Token valid for {days_until_expiry:.1f} more days")

        return should_refresh

    async def refresh_token(self, refresh_token: str, app_key: str, app_secret: str) -> Optional[Dict[str, Any]]:
        """
        Refresh access token using refresh token

        Args:
            refresh_token: The refresh token to use
            app_key: Application key
            app_secret: Application secret

        Returns:
            New token response dict or None if failed
        """
        try:
            async with httpx.AsyncClient() as client:
                # Generate timestamp
                timestamp = str(int(time.time() * 1000))

                # Parameters for token refresh
                params = {
                    "app_key": app_key,
                    "timestamp": timestamp,
                    "sign_method": "sha256",
                    "format": "json",
                    "v": "2.0",
                    "method": "auth.token.create",
                    "refresh_token": refresh_token  # Use refresh_token instead of code
                }

                # Generate signature
                signature = self.generate_signature_sha256(params, app_secret)
                params["sign"] = signature

                print(f"🔄 Refreshing token for app {app_key}...")

                # Make refresh request
                response = await client.post(
                    self.token_refresh_url,
                    data=params,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )

                print(f"📡 Refresh Response Status: {response.status_code}")

                if response.status_code == 200:
                    token_response = response.json()

                    # Check if successful
                    if "access_token" in token_response:
                        print(f"✅ Token refreshed successfully!")
                        print(f"   New Access Token: {token_response['access_token'][:20]}...")
                        print(f"   Expires In: {token_response.get('expires_in', 'N/A')} seconds")
                        return token_response
                    else:
                        print(f"❌ Token refresh failed: {token_response}")
                        return None
                else:
                    print(f"❌ Token refresh request failed: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            print(f"❌ Exception during token refresh: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def refresh_dropship_token_if_needed(self) -> bool:
        """
        Check and refresh Dropshipping API token if needed

        Returns:
            True if token is valid (either already valid or successfully refreshed)
        """
        print("\n" + "=" * 80)
        print("🔍 CHECKING DROPSHIPPING API TOKEN (App Key: 520918)")
        print("=" * 80)

        # Load current tokens
        tokens = self.load_tokens(self.dropship_tokens_file)
        if not tokens:
            print("❌ No tokens found - need to authorize first")
            return False

        # Check if refresh is needed
        if not self.is_token_expiring_soon(tokens):
            print("✅ Token is still valid - no refresh needed")
            return True

        # Get refresh token
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            print("❌ No refresh token available - need to re-authorize")
            return False

        # Refresh the token
        new_tokens = await self.refresh_token(
            refresh_token,
            self.dropship_app_key,
            self.dropship_app_secret
        )

        if new_tokens:
            # Save new tokens
            return self.save_tokens(new_tokens, self.dropship_tokens_file)
        else:
            print("❌ Token refresh failed")
            return False

    async def refresh_affiliate_token_if_needed(self) -> bool:
        """
        Check and refresh Affiliate API token if needed

        Returns:
            True if token is valid (either already valid or successfully refreshed)
        """
        print("\n" + "=" * 80)
        print("🔍 CHECKING AFFILIATE API TOKEN (App Key: 522382)")
        print("=" * 80)

        # Load current tokens
        tokens = self.load_tokens(self.affiliate_tokens_file)
        if not tokens:
            print("❌ No tokens found - need to authorize first")
            return False

        # Check if refresh is needed
        if not self.is_token_expiring_soon(tokens):
            print("✅ Token is still valid - no refresh needed")
            return True

        # Get refresh token
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            print("❌ No refresh token available - need to re-authorize")
            return False

        # Refresh the token
        new_tokens = await self.refresh_token(
            refresh_token,
            self.affiliate_app_key,
            self.affiliate_app_secret
        )

        if new_tokens:
            # Save new tokens
            return self.save_tokens(new_tokens, self.affiliate_tokens_file)
        else:
            print("❌ Token refresh failed")
            return False

    async def refresh_all_tokens(self) -> Dict[str, bool]:
        """
        Check and refresh all AliExpress tokens

        Returns:
            Dict with status for each API
        """
        print("\n" + "=" * 80)
        print("🔄 ALIEXPRESS TOKEN REFRESH SERVICE")
        print("=" * 80)
        print(f"Started at: {datetime.now().isoformat()}")
        print(f"Refresh window: {self.refresh_window / 86400:.1f} days before expiry")

        results = {
            "dropship": await self.refresh_dropship_token_if_needed(),
            "affiliate": await self.refresh_affiliate_token_if_needed()
        }

        print("\n" + "=" * 80)
        print("📊 REFRESH SUMMARY")
        print("=" * 80)
        print(f"Dropshipping API: {'✅ Valid' if results['dropship'] else '❌ Failed'}")
        print(f"Affiliate API: {'✅ Valid' if results['affiliate'] else '❌ Failed'}")
        print("=" * 80)

        return results


# Singleton instance
refresher = AliExpressTokenRefresher()


# Convenience functions
async def refresh_all_tokens():
    """Convenience function to refresh all tokens"""
    return await refresher.refresh_all_tokens()


async def refresh_dropship_token():
    """Convenience function to refresh dropshipping token"""
    return await refresher.refresh_dropship_token_if_needed()


async def refresh_affiliate_token():
    """Convenience function to refresh affiliate token"""
    return await refresher.refresh_affiliate_token_if_needed()
