"""
🛍️ AliExpress Official API Client
Uses AliExpress Dropshipping API with proper HMAC-SHA256 signing
"""

import hashlib
import hmac
import time
import requests
import json
import os
import urllib.parse
import secrets
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class AliExpressAPI:
    """Official AliExpress Dropshipping API client with proper signing"""

    def __init__(self):
        self.app_key = os.getenv("ALIEXPRESS_APP_KEY")
        self.app_secret = os.getenv("ALIEXPRESS_APP_SECRET")
        self.gateway = os.getenv("ALIEXPRESS_API_GATEWAY", "https://api-sg.aliexpress.com/sync")

        # Load access token if available (from OAuth or env)
        self.access_token = os.getenv("ALIEXPRESS_ACCESS_TOKEN")
        self.refresh_token = os.getenv("ALIEXPRESS_REFRESH_TOKEN")

        if not self.app_key or not self.app_secret:
            raise ValueError("AliExpress API credentials not configured")

    def _sign_request(self, method: str, params: Dict) -> str:
        """Generate HMAC-SHA256 signature for AliExpress API"""

        # Sort parameters alphabetically
        sorted_params = sorted(params.items())

        # Build string to sign: method + sorted params
        params_str = method + "".join([f"{k}{v}" for k, v in sorted_params])

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            params_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()

        return signature

    def _make_request(self, method: str, params: Dict) -> Optional[Dict]:
        """Make signed API request with access token"""

        # Add required parameters
        params.update({
            "app_key": self.app_key,
            "sign_method": "sha256",
            "timestamp": str(int(time.time() * 1000)),
            "format": "json",
            "v": "2.0",
            "method": method
        })

        # Include access token if available
        if self.access_token:
            params["session"] = self.access_token
            logger.debug("✅ Using access_token for API request")
        else:
            logger.warning("⚠️  No access_token - API may require OAuth")

        # Generate signature
        params["sign"] = self._sign_request(method, params)

        try:
            logger.info(f"🔌 AliExpress API: {method}")
            response = requests.post(self.gateway, data=params, timeout=30)

            if response.status_code != 200:
                logger.error(f"❌ AliExpress API returned {response.status_code}")
                return None

            data = response.json()

            # Check for API errors
            if "error_response" in data:
                error = data["error_response"]
                error_msg = error.get('msg', 'Unknown error')

                # Detect token expiration
                if 'access_token' in error_msg.lower() or 'session' in error_msg.lower():
                    logger.warning("🔐 Access token may be expired or invalid")

                logger.error(f"❌ API Error: {error_msg}")
                return None

            return data

        except Exception as e:
            logger.error(f"❌ AliExpress API request failed: {e}")
            return None

    def search_products(self, keywords: str, page: int = 1, page_size: int = 20) -> List[Dict]:
        """
        Search products using AliExpress Dropshipping API
        Method: aliexpress.ds.product.get
        """

        params = {
            "keywords": keywords,
            "page_no": str(page),
            "page_size": str(page_size),
            "sort": "SALE_PRICE_ASC",  # or SALE_PRICE_DESC, NEW_ARRIVAL, etc.
            "target_currency": "USD",
            "target_language": "EN",
            "ship_to_country": "US"
        }

        # Use product search method
        result = self._make_request("aliexpress.ds.product.get", params)

        if not result:
            return []

        # Parse products from response
        products = []

        try:
            # Response structure varies, adjust based on actual API response
            if "aliexpress_ds_product_get_response" in result:
                response_data = result["aliexpress_ds_product_get_response"]

                if "result" in response_data:
                    result_data = response_data["result"]

                    if "products" in result_data:
                        product_list = result_data["products"]["ae_item"]

                        for item in product_list:
                            products.append(self._parse_product(item))

            logger.info(f"✅ Found {len(products)} products from AliExpress API")
            return products

        except Exception as e:
            logger.error(f"Error parsing AliExpress response: {e}")
            return []

    def _parse_product(self, item: Dict) -> Dict:
        """Parse AliExpress product into our format"""

        # Extract price (handle different price formats)
        price = 0
        if "target_sale_price" in item:
            price = float(item["target_sale_price"])
        elif "sale_price" in item:
            price = float(item["sale_price"])

        # Calculate cost (wholesale/supplier price if available)
        cost = price * 0.35  # Default 35% if no wholesale price
        if "original_price" in item:
            cost = float(item["original_price"]) * 0.5

        # Extract other fields
        product_id = str(item.get("product_id", ""))
        title = item.get("subject", item.get("product_title", "Unknown Product"))
        image_url = item.get("product_main_image_url", "")
        product_url = item.get("product_detail_url", "")

        # Sales/orders
        orders = int(item.get("sales", item.get("volume", 0)))

        # Rating
        rating = float(item.get("avg_evaluation_rating", item.get("star", 4.5)))

        return {
            "id": f"ali_{product_id}",
            "name": title,
            "price": round(price, 2),
            "cost": round(cost, 2),
            "profit_margin": round(((price - cost) / price) * 100, 1),
            "estimated_profit": round(price - cost, 2),
            "orders": orders,
            "rating": rating,
            "image_url": image_url,
            "aliexpress_url": product_url,
            "source": "aliexpress_api",
            "score": 7.0,  # Will be enriched later
            "velocity_score": 50  # Will be enriched with trends
        }

    def get_product_details(self, product_id: str) -> Optional[Dict]:
        """Get detailed product information"""

        params = {
            "product_id": product_id,
            "target_currency": "USD",
            "target_language": "EN",
            "ship_to_country": "US"
        }

        result = self._make_request("aliexpress.ds.product.detail.get", params)

        if result:
            # Parse detailed response
            return self._parse_product_details(result)

        return None

    def _parse_product_details(self, data: Dict) -> Dict:
        """Parse detailed product data including description, specs, etc."""

        # Extract rich product data
        try:
            details = data.get("aliexpress_ds_product_detail_get_response", {}).get("result", {})

            return {
                "description": details.get("product_description", ""),
                "specifications": details.get("product_properties", []),
                "shipping_info": details.get("freight", {}),
                "variants": details.get("skus", [])
            }
        except:
            return {}

    # OAuth 2.0 Methods

    def get_authorization_url(self, redirect_uri: str, state: str = None) -> str:
        """
        Generate OAuth authorization URL for user to approve access

        Args:
            redirect_uri: Your callback URL (must match app configuration)
            state: Optional state parameter for security (auto-generated if not provided)

        Returns:
            Authorization URL for user to visit
        """
        if state is None:
            state = secrets.token_urlsafe(16)

        params = {
            "response_type": "code",
            "client_id": self.app_key,
            "redirect_uri": redirect_uri,
            "state": state
        }

        auth_url = "https://oauth.aliexpress.com/authorize"
        query_string = urllib.parse.urlencode(params)

        logger.info(f"🔐 Generated OAuth URL with state: {state}")
        return f"{auth_url}?{query_string}"

    def exchange_code_for_token(self, authorization_code: str) -> Optional[Dict]:
        """
        Exchange authorization code for access token

        Call this after user authorizes and you receive the code from callback

        Args:
            authorization_code: Code received from OAuth callback

        Returns:
            Token data including access_token, refresh_token, expires_in
        """
        params = {
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "code": authorization_code,
            "grant_type": "authorization_code"
        }

        token_url = "https://oauth.aliexpress.com/token"

        try:
            logger.info("🔐 Exchanging authorization code for access token...")
            response = requests.post(token_url, data=params, timeout=30)

            if response.status_code == 200:
                token_data = response.json()

                # Save tokens
                self.access_token = token_data.get("access_token")
                self.refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in")

                logger.info(f"✅ Access token obtained (expires in {expires_in} seconds)")
                logger.info("💾 Store these tokens in your database:")
                logger.info(f"   access_token: {self.access_token[:20]}...")
                logger.info(f"   refresh_token: {self.refresh_token[:20] if self.refresh_token else 'None'}...")

                return token_data
            else:
                logger.error(f"❌ Token exchange failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Token exchange error: {e}")
            return None

    def refresh_access_token(self, refresh_token: str = None) -> Optional[Dict]:
        """
        Refresh expired access token

        Args:
            refresh_token: Refresh token (uses self.refresh_token if not provided)

        Returns:
            New token data with fresh access_token
        """
        if refresh_token is None:
            refresh_token = self.refresh_token

        if not refresh_token:
            logger.error("❌ No refresh token available")
            return None

        params = {
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }

        token_url = "https://oauth.aliexpress.com/token"

        try:
            logger.info("🔄 Refreshing access token...")
            response = requests.post(token_url, data=params, timeout=30)

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")

                logger.info("✅ Access token refreshed successfully")
                logger.info(f"💾 Update database with new token: {self.access_token[:20]}...")

                return token_data
            else:
                logger.error(f"❌ Token refresh failed: HTTP {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"❌ Token refresh error: {e}")
            return None
