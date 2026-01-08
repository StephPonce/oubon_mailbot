"""
Shopify OAuth Service
=====================

Handles OAuth flow for connecting any Shopify store.
SaaS-ready implementation.

Flow:
1. User clicks "Connect Shopify Store"
2. Redirect to Shopify OAuth authorization URL
3. User authorizes the app
4. Shopify redirects back with auth code
5. Exchange code for access token
6. Store credentials in database
"""

import os
import hmac
import hashlib
import secrets
import httpx
from urllib.parse import urlencode, parse_qs
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class ShopifyOAuth:
    """
    Shopify OAuth handler for multi-store SaaS.
    """
    
    # Required scopes for full store access
    DEFAULT_SCOPES = [
        "read_products",
        "write_products",
        "read_orders",
        "write_orders",
        "read_customers",
        "read_inventory",
        "write_inventory",
        "read_locations",
        "read_fulfillments",
        "write_fulfillments",
        "read_shipping",
        "read_analytics",
        "read_themes",
        "read_content",
        "read_price_rules",
        "read_discounts",
        "read_marketing_events",
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        scopes: Optional[list] = None
    ):
        """
        Initialize OAuth handler.
        
        Args:
            api_key: Shopify app API key (from Partner Dashboard)
            api_secret: Shopify app API secret
            redirect_uri: OAuth callback URL
            scopes: List of permission scopes
        """
        self.api_key = api_key or os.getenv("SHOPIFY_API_KEY")
        self.api_secret = api_secret or os.getenv("SHOPIFY_API_SECRET")
        self.redirect_uri = redirect_uri or os.getenv(
            "SHOPIFY_REDIRECT_URI",
            "http://localhost:8001/api/shopify/oauth/callback"
        )
        self.scopes = scopes or self.DEFAULT_SCOPES
        
        if not self.api_key or not self.api_secret:
            raise ValueError("SHOPIFY_API_KEY and SHOPIFY_API_SECRET are required")
    
    def generate_nonce(self) -> str:
        """Generate a secure random nonce for OAuth state."""
        return secrets.token_urlsafe(32)
    
    def get_authorization_url(self, shop_domain: str, state: Optional[str] = None) -> Dict[str, str]:
        """
        Generate the OAuth authorization URL.
        
        Args:
            shop_domain: Store domain (e.g., 'mystore.myshopify.com' or 'mystore')
            state: Optional state parameter (nonce for CSRF protection)
        
        Returns:
            Dictionary with 'url' and 'state' (nonce)
        """
        # Normalize domain
        if not shop_domain.endswith(".myshopify.com"):
            shop_domain = f"{shop_domain}.myshopify.com"
        
        # Generate state if not provided
        if not state:
            state = self.generate_nonce()
        
        params = {
            "client_id": self.api_key,
            "scope": ",".join(self.scopes),
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        
        auth_url = f"https://{shop_domain}/admin/oauth/authorize?{urlencode(params)}"
        
        return {
            "url": auth_url,
            "state": state,
            "shop": shop_domain,
        }
    
    def verify_hmac(self, query_params: Dict[str, str]) -> bool:
        """
        Verify the HMAC signature from Shopify callback.
        
        Args:
            query_params: Dictionary of query parameters from callback
        
        Returns:
            True if signature is valid
        """
        received_hmac = query_params.get("hmac", "")
        
        # Remove hmac from params for verification
        params_to_verify = {k: v for k, v in query_params.items() if k != "hmac"}
        
        # Sort and encode
        sorted_params = "&".join(
            f"{k}={v}" for k, v in sorted(params_to_verify.items())
        )
        
        # Calculate expected HMAC
        computed_hmac = hmac.new(
            self.api_secret.encode("utf-8"),
            sorted_params.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_hmac, received_hmac)
    
    async def exchange_code_for_token(
        self,
        shop_domain: str,
        code: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            shop_domain: Store domain
            code: Authorization code from callback
        
        Returns:
            Dictionary with access_token and scope
        """
        # Normalize domain
        if not shop_domain.endswith(".myshopify.com"):
            shop_domain = f"{shop_domain}.myshopify.com"
        
        token_url = f"https://{shop_domain}/admin/oauth/access_token"
        
        payload = {
            "client_id": self.api_key,
            "client_secret": self.api_secret,
            "code": code,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "access_token": data.get("access_token"),
                "scope": data.get("scope"),
                "shop": shop_domain,
            }
    
    async def get_shop_info(
        self,
        shop_domain: str,
        access_token: str
    ) -> Dict[str, Any]:
        """
        Get store information after OAuth.
        
        Args:
            shop_domain: Store domain
            access_token: Access token from OAuth
        
        Returns:
            Store information dictionary
        """
        if not shop_domain.endswith(".myshopify.com"):
            shop_domain = f"{shop_domain}.myshopify.com"
        
        api_version = os.getenv("SHOPIFY_API_VERSION", "2025-01")
        url = f"https://{shop_domain}/admin/api/{api_version}/shop.json"
        
        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json().get("shop", {})


# Singleton instance
_oauth_instance: Optional[ShopifyOAuth] = None


def get_shopify_oauth() -> ShopifyOAuth:
    """Get or create Shopify OAuth instance."""
    global _oauth_instance
    if _oauth_instance is None:
        _oauth_instance = ShopifyOAuth()
    return _oauth_instance
