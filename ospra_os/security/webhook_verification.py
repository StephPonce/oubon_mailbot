"""
WEBHOOK SIGNATURE VERIFICATION
==============================

Secure webhook handling for:
- Shopify webhooks
- Stripe/LemonSqueezy payments
- AliExpress notifications
- CJ Dropshipping updates

Security Features:
- HMAC-SHA256 signature verification
- Timestamp validation (replay attack prevention)
- Request body integrity checking
- Rate limiting for webhook endpoints

Author: OspraOS
Date: December 2024
"""

import hmac
import hashlib
import base64
import time
import os
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class WebhookConfig:
    """Webhook security configuration."""
    
    # Signature header names by provider
    SIGNATURE_HEADERS = {
        "shopify": "X-Shopify-Hmac-SHA256",
        "stripe": "Stripe-Signature",
        "lemonsqueezy": "X-Signature",
        "aliexpress": "X-AE-Signature",
        "cj": "X-CJ-Signature",
        "tiktok": "X-TikTok-Signature",
    }
    
    # Max age for webhook timestamps (prevent replay attacks)
    MAX_TIMESTAMP_AGE_SECONDS = 300  # 5 minutes
    
    # Environment variable names for secrets
    SECRET_ENV_VARS = {
        "shopify": "SHOPIFY_WEBHOOK_SECRET",
        "stripe": "STRIPE_WEBHOOK_SECRET",
        "lemonsqueezy": "LEMONSQUEEZY_WEBHOOK_SECRET",
        "aliexpress": "ALIEXPRESS_WEBHOOK_SECRET",
        "cj": "CJ_WEBHOOK_SECRET",
        "tiktok": "TIKTOK_WEBHOOK_SECRET",
    }


# =============================================================================
# SIGNATURE VERIFICATION
# =============================================================================

class WebhookVerifier:
    """
    Webhook signature verification for multiple providers.
    
    Usage:
        verifier = WebhookVerifier()
        
        # Verify Shopify webhook
        is_valid = verifier.verify_shopify(request_body, signature_header)
        
        # Verify with automatic provider detection
        is_valid = verifier.verify(provider, request_body, signature_header)
    """
    
    def __init__(self):
        """Initialize with secrets from environment."""
        self.secrets = {}
        for provider, env_var in WebhookConfig.SECRET_ENV_VARS.items():
            secret = os.getenv(env_var)
            if secret:
                self.secrets[provider] = secret
                logger.info(f"[SUCCESS] {provider} webhook secret configured")
            else:
                logger.debug(f"[WARNING]  {provider} webhook secret not configured ({env_var})")
    
    def verify(
        self,
        provider: str,
        body: bytes,
        signature: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """
        Verify webhook signature for any provider.
        
        Args:
            provider: Provider name (shopify, stripe, etc.)
            body: Raw request body as bytes
            signature: Signature from header
            timestamp: Optional timestamp for replay protection
            
        Returns:
            True if signature is valid
        """
        provider = provider.lower()
        
        if provider not in self.secrets:
            logger.error(f"No secret configured for provider: {provider}")
            return False
        
        if provider == "shopify":
            return self.verify_shopify(body, signature)
        elif provider == "stripe":
            return self.verify_stripe(body, signature, timestamp)
        elif provider == "lemonsqueezy":
            return self.verify_lemonsqueezy(body, signature)
        elif provider == "aliexpress":
            return self.verify_aliexpress(body, signature)
        elif provider == "cj":
            return self.verify_cj(body, signature)
        elif provider == "tiktok":
            return self.verify_tiktok(body, signature)
        else:
            logger.error(f"Unknown provider: {provider}")
            return False
    
    def verify_shopify(self, body: bytes, signature: str) -> bool:
        """
        Verify Shopify webhook signature.
        
        Shopify uses HMAC-SHA256 with base64 encoding.
        """
        secret = self.secrets.get("shopify")
        if not secret:
            return False
        
        try:
            computed = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).digest()
            computed_b64 = base64.b64encode(computed).decode('utf-8')
            
            is_valid = hmac.compare_digest(computed_b64, signature)
            
            if not is_valid:
                logger.warning("Shopify webhook signature mismatch")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Shopify verification error: {e}")
            return False
    
    def verify_stripe(
        self,
        body: bytes,
        signature: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """
        Verify Stripe webhook signature.
        
        Stripe uses a timestamp-prefixed signature format:
        t=timestamp,v1=signature
        """
        secret = self.secrets.get("stripe")
        if not secret:
            return False
        
        try:
            # Parse Stripe signature format
            elements = dict(item.split("=") for item in signature.split(","))
            
            t = elements.get("t")
            v1 = elements.get("v1")
            
            if not t or not v1:
                logger.warning("Invalid Stripe signature format")
                return False
            
            # Check timestamp age (replay attack prevention)
            timestamp_int = int(t)
            current_time = int(time.time())
            
            if abs(current_time - timestamp_int) > WebhookConfig.MAX_TIMESTAMP_AGE_SECONDS:
                logger.warning(f"Stripe webhook timestamp too old: {current_time - timestamp_int}s")
                return False
            
            # Compute expected signature
            signed_payload = f"{t}.{body.decode('utf-8')}"
            expected = hmac.new(
                secret.encode('utf-8'),
                signed_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            is_valid = hmac.compare_digest(expected, v1)
            
            if not is_valid:
                logger.warning("Stripe webhook signature mismatch")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Stripe verification error: {e}")
            return False
    
    def verify_lemonsqueezy(self, body: bytes, signature: str) -> bool:
        """
        Verify LemonSqueezy webhook signature.
        
        LemonSqueezy uses HMAC-SHA256 with hex encoding.
        """
        secret = self.secrets.get("lemonsqueezy")
        if not secret:
            return False
        
        try:
            computed = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()
            
            is_valid = hmac.compare_digest(computed, signature)
            
            if not is_valid:
                logger.warning("LemonSqueezy webhook signature mismatch")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"LemonSqueezy verification error: {e}")
            return False
    
    def verify_aliexpress(self, body: bytes, signature: str) -> bool:
        """
        Verify AliExpress webhook signature.
        
        AliExpress uses MD5 with app secret.
        """
        secret = self.secrets.get("aliexpress")
        if not secret:
            return False
        
        try:
            # AliExpress uses MD5 for some signatures
            computed = hashlib.md5(
                (secret + body.decode('utf-8') + secret).encode('utf-8')
            ).hexdigest().upper()
            
            is_valid = hmac.compare_digest(computed, signature.upper())
            
            if not is_valid:
                logger.warning("AliExpress webhook signature mismatch")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"AliExpress verification error: {e}")
            return False
    
    def verify_cj(self, body: bytes, signature: str) -> bool:
        """
        Verify CJ Dropshipping webhook signature.

        CJ uses HMAC-SHA256 with hex encoding.
        """
        secret = self.secrets.get("cj")
        if not secret:
            return False

        try:
            computed = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()

            is_valid = hmac.compare_digest(computed, signature)

            if not is_valid:
                logger.warning("CJ webhook signature mismatch")

            return is_valid

        except Exception as e:
            logger.error(f"CJ verification error: {e}")
            return False

    def verify_tiktok(self, body: bytes, signature: str) -> bool:
        """
        Verify TikTok webhook signature.

        TikTok uses HMAC-SHA256 with hex encoding.
        Header: X-TikTok-Signature
        """
        secret = self.secrets.get("tiktok")
        if not secret:
            return False

        try:
            computed = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()

            is_valid = hmac.compare_digest(computed, signature)

            if not is_valid:
                logger.warning("TikTok webhook signature mismatch")

            return is_valid

        except Exception as e:
            logger.error(f"TikTok verification error: {e}")
            return False

    def is_configured(self, provider: str) -> bool:
        """Check if a provider's webhook secret is configured."""
        return provider.lower() in self.secrets


# =============================================================================
# FASTAPI DEPENDENCIES
# =============================================================================

# Global verifier instance
_webhook_verifier: Optional[WebhookVerifier] = None


def get_webhook_verifier() -> WebhookVerifier:
    """Get or create the global webhook verifier."""
    global _webhook_verifier
    if _webhook_verifier is None:
        _webhook_verifier = WebhookVerifier()
    return _webhook_verifier


async def verify_shopify_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(..., alias="X-Shopify-Hmac-SHA256")
) -> bytes:
    """
    FastAPI dependency for Shopify webhook verification.
    
    Usage:
        @router.post("/webhooks/shopify/orders")
        async def handle_order(body: bytes = Depends(verify_shopify_webhook)):
            data = json.loads(body)
            ...
    """
    body = await request.body()
    verifier = get_webhook_verifier()
    
    if not verifier.verify_shopify(body, x_shopify_hmac_sha256):
        logger.warning(f"Invalid Shopify webhook from {request.client.host}")
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )
    
    return body


async def verify_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature")
) -> bytes:
    """
    FastAPI dependency for Stripe webhook verification.
    
    Usage:
        @router.post("/webhooks/stripe")
        async def handle_payment(body: bytes = Depends(verify_stripe_webhook)):
            event = json.loads(body)
            ...
    """
    body = await request.body()
    verifier = get_webhook_verifier()
    
    if not verifier.verify_stripe(body, stripe_signature):
        logger.warning(f"Invalid Stripe webhook from {request.client.host}")
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )
    
    return body


async def verify_lemonsqueezy_webhook(
    request: Request,
    x_signature: str = Header(..., alias="X-Signature")
) -> bytes:
    """
    FastAPI dependency for LemonSqueezy webhook verification.
    
    Usage:
        @router.post("/webhooks/lemonsqueezy")
        async def handle_subscription(body: bytes = Depends(verify_lemonsqueezy_webhook)):
            data = json.loads(body)
            ...
    """
    body = await request.body()
    verifier = get_webhook_verifier()
    
    if not verifier.verify_lemonsqueezy(body, x_signature):
        logger.warning(f"Invalid LemonSqueezy webhook from {request.client.host}")
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )
    
    return body


# =============================================================================
# WEBHOOK RATE LIMITING
# =============================================================================

class WebhookRateLimiter:
    """
    Rate limiter for webhook endpoints.
    
    Prevents webhook flooding attacks.
    """
    
    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}  # ip -> [timestamps]
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed."""
        now = time.time()
        cutoff = now - self.window_seconds
        
        # Clean old entries
        if client_ip in self.requests:
            self.requests[client_ip] = [
                t for t in self.requests[client_ip] if t > cutoff
            ]
        else:
            self.requests[client_ip] = []
        
        # Check limit
        if len(self.requests[client_ip]) >= self.max_requests:
            logger.warning(f"Webhook rate limit exceeded for {client_ip}")
            return False
        
        # Record this request
        self.requests[client_ip].append(now)
        return True
    
    def get_remaining(self, client_ip: str) -> int:
        """Get remaining requests in window."""
        if client_ip not in self.requests:
            return self.max_requests
        
        now = time.time()
        cutoff = now - self.window_seconds
        recent = [t for t in self.requests[client_ip] if t > cutoff]
        
        return max(0, self.max_requests - len(recent))


# Global rate limiter
_webhook_rate_limiter = WebhookRateLimiter()


async def webhook_rate_limit(request: Request):
    """
    FastAPI dependency for webhook rate limiting.
    
    Usage:
        @router.post("/webhooks/shopify/orders")
        async def handle_order(
            _: None = Depends(webhook_rate_limit),
            body: bytes = Depends(verify_shopify_webhook)
        ):
            ...
    """
    client_ip = request.client.host if request.client else "unknown"
    
    if not _webhook_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many webhook requests"
        )


# =============================================================================
# TESTING UTILITIES
# =============================================================================

def generate_test_signature(
    provider: str,
    body: bytes,
    secret: str
) -> str:
    """
    Generate a test signature for a provider.
    
    Useful for testing webhook handlers.
    """
    provider = provider.lower()
    
    if provider == "shopify":
        computed = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).digest()
        return base64.b64encode(computed).decode('utf-8')
    
    elif provider == "stripe":
        timestamp = int(time.time())
        signed_payload = f"{timestamp}.{body.decode('utf-8')}"
        signature = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"t={timestamp},v1={signature}"
    
    elif provider in ["lemonsqueezy", "cj", "tiktok"]:
        return hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
    
    elif provider == "aliexpress":
        return hashlib.md5(
            (secret + body.decode('utf-8') + secret).encode('utf-8')
        ).hexdigest().upper()
    
    else:
        raise ValueError(f"Unknown provider: {provider}")


# =============================================================================
# STATUS/HEALTH
# =============================================================================

def get_webhook_status() -> Dict[str, Any]:
    """Get webhook configuration status."""
    verifier = get_webhook_verifier()
    
    providers = {}
    for provider in WebhookConfig.SECRET_ENV_VARS.keys():
        providers[provider] = {
            "configured": verifier.is_configured(provider),
            "header": WebhookConfig.SIGNATURE_HEADERS.get(provider),
            "env_var": WebhookConfig.SECRET_ENV_VARS.get(provider)
        }
    
    configured_count = sum(1 for p in providers.values() if p["configured"])
    
    return {
        "configured_providers": configured_count,
        "total_providers": len(providers),
        "providers": providers,
        "rate_limit": {
            "max_requests": _webhook_rate_limiter.max_requests,
            "window_seconds": _webhook_rate_limiter.window_seconds
        },
        "max_timestamp_age": WebhookConfig.MAX_TIMESTAMP_AGE_SECONDS
    }
