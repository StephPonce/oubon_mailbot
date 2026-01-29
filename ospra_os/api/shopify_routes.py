"""
Shopify Integration - Production SaaS
=====================================

ALL stores connect through OAuth. No auto-connect.
"""

import os
import secrets
import hashlib
import hmac
import re
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlencode, quote
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx

logger = logging.getLogger(__name__)

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User
from ospra_os.constants import SHOPIFY_API_TIMEOUT, DEFAULT_PAGE_SIZE, SHOPIFY_MAX_PAGE_SIZE

load_dotenv()

router = APIRouter(prefix="/api/shopify", tags=["Shopify"])

# ============================================================================
# CONFIGURATION
# ============================================================================

SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2024-10")

REQUIRED_SCOPES = [
    "read_products", "write_products",
    "read_inventory", "write_inventory",
    "read_orders", "write_orders",
    "read_fulfillments", "write_fulfillments",
    "read_customers",
    "read_analytics",
    "read_locations",
    "read_price_rules", "read_discounts",
    "read_shipping",
]

# OAuth state storage
_oauth_states: Dict[str, Dict[str, Any]] = {}

# Connected stores (in production, use database)
_connected_stores: Dict[str, Dict[str, Any]] = {}

# ============================================================================
# MODELS
# ============================================================================

class ConnectStoreRequest(BaseModel):
    shop_domain: str

# ============================================================================
# SHOPIFY CLIENT
# ============================================================================

class ShopifyClient:
    def __init__(self, store_domain: str, access_token: str):
        store_domain = store_domain.lower().strip()
        if not store_domain.endswith('.myshopify.com'):
            store_domain = f"{store_domain}.myshopify.com"
        
        self.store_domain = store_domain
        self.access_token = access_token
        self.base_url = f"https://{store_domain}/admin/api/{SHOPIFY_API_VERSION}"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }
    
    async def get(self, endpoint: str, params: dict = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/{endpoint}",
                headers=self.headers,
                params=params,
                timeout=SHOPIFY_API_TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()

    async def post(self, endpoint: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/{endpoint}",
                headers=self.headers,
                json=data,
                timeout=SHOPIFY_API_TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()
    
    async def get_shop(self) -> dict:
        data = await self.get("shop.json")
        return data.get("shop", {})
    
    async def get_products_count(self) -> int:
        data = await self.get("products/count.json")
        return data.get("count", 0)
    
    async def get_products(self, limit: int = 50) -> list:
        data = await self.get("products.json", {"limit": limit})
        return data.get("products", [])
    
    async def get_orders_count(self, status: str = "any") -> int:
        data = await self.get("orders/count.json", {"status": status})
        return data.get("count", 0)
    
    async def get_orders(self, limit: int = 50, status: str = "any") -> list:
        data = await self.get("orders.json", {"limit": limit, "status": status})
        return data.get("orders", [])
    
    async def get_customers_count(self) -> int:
        data = await self.get("customers/count.json")
        return data.get("count", 0)
    
    async def create_product(self, product_data: dict) -> dict:
        data = await self.post("products.json", {"product": product_data})
        return data.get("product", {})


# ============================================================================
# HELPERS
# ============================================================================

def get_oauth_config() -> Dict[str, str]:
    return {
        "api_key": os.getenv("SHOPIFY_PARTNER_CLIENT_ID", ""),
        "api_secret": os.getenv("SHOPIFY_PARTNER_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("SHOPIFY_REDIRECT_URI", "http://localhost:8001/api/shopify/oauth/callback"),
        "app_url": os.getenv("APP_URL", "http://localhost:5173"),
    }


def normalize_domain(domain: str) -> str:
    domain = domain.lower().strip()
    domain = re.sub(r'^https?://', '', domain)
    domain = domain.rstrip('/').split('/')[0]
    if not domain.endswith('.myshopify.com'):
        domain = domain.replace('.com', '').replace('.', '-')
        domain = f"{domain}.myshopify.com"
    return domain


# ============================================================================
# ROUTES
# ============================================================================

@router.get("/stores")
async def list_stores(current_user: User = Depends(get_current_user)):
    """List connected stores."""
    stores = []
    
    for store_id, store_data in _connected_stores.items():
        stores.append({
            "id": store_id,
            "store_name": store_data.get("store_name"),
            "store_url": store_data.get("store_url"),
            "domain": store_data.get("domain"),
            "currency": store_data.get("currency", "USD"),
            "status": "active",
            "connected_at": store_data.get("connected_at"),
        })
    
    return {"success": True, "stores": stores, "count": len(stores)}


@router.post("/connect")
async def connect_store(
    request: ConnectStoreRequest,
    current_user: User = Depends(get_current_user)
):
    """Initiate OAuth flow to connect a store."""
    shop_domain = request.shop_domain.strip()
    shop_normalized = normalize_domain(shop_domain)
    
    config = get_oauth_config()
    
    if not config["api_key"] or not config["api_secret"]:
        raise HTTPException(
            status_code=400,
            detail="Shopify app not configured. Set SHOPIFY_API_KEY and SHOPIFY_API_SECRET in .env"
        )
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    _oauth_states[state] = {
        "shop_domain": shop_normalized,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # Build OAuth URL
    params = {
        "client_id": config["api_key"],
        "scope": ",".join(REQUIRED_SCOPES),
        "redirect_uri": config["redirect_uri"],
        "state": state,
    }
    
    auth_url = f"https://{shop_normalized}/admin/oauth/authorize?{urlencode(params)}"
    
    return {
        "success": True,
        "oauth_required": True,
        "authorization_url": auth_url,
    }


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    shop: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(None),
):
    """OAuth callback - exchange code for token."""
    config = get_oauth_config()
    frontend_url = config["app_url"]
    
    # Verify state
    if state not in _oauth_states:
        return RedirectResponse(url=f"{frontend_url}?error=Invalid+or+expired+state")
    
    state_data = _oauth_states.pop(state)
    shop_normalized = normalize_domain(shop)
    
    try:
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://{shop_normalized}/admin/oauth/access_token",
                json={
                    "client_id": config["api_key"],
                    "client_secret": config["api_secret"],
                    "code": code,
                },
                timeout=30.0
            )
            resp.raise_for_status()
            token_data = resp.json()
        
        access_token = token_data.get("access_token")
        scope = token_data.get("scope", "")
        
        if not access_token:
            return RedirectResponse(url=f"{frontend_url}?error=No+access+token+received")
        
        # Get shop info
        shop_client = ShopifyClient(shop_normalized, access_token)
        shop_info = await shop_client.get_shop()
        
        # Store the connection
        store_id = shop_normalized.replace('.myshopify.com', '')
        _connected_stores[store_id] = {
            "store_name": shop_info.get("name", shop),
            "store_url": shop_normalized,
            "domain": shop_info.get("domain"),
            "currency": shop_info.get("currency", "USD"),
            "access_token": access_token,
            "scope": scope,
            "connected_at": datetime.utcnow().isoformat(),
        }
        
        return RedirectResponse(url=f"{frontend_url}?store_connected=true")
        
    except httpx.HTTPStatusError as e:
        error_msg = f"Shopify+error+{e.response.status_code}"
        return RedirectResponse(url=f"{frontend_url}?error={error_msg}")
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return RedirectResponse(url=f"{frontend_url}?error=connection_failed")


@router.delete("/stores/{store_id}")
async def disconnect_store(
    store_id: str,
    current_user: User = Depends(get_current_user)
):
    """Disconnect a store."""
    if store_id in _connected_stores:
        del _connected_stores[store_id]
        return {"success": True, "message": "Store disconnected"}
    
    raise HTTPException(status_code=404, detail="Store not found")


@router.get("/stores/{store_id}/stats")
async def get_store_stats(
    store_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get store statistics."""
    if store_id not in _connected_stores:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = _connected_stores[store_id]
    client = ShopifyClient(store["store_url"], store["access_token"])
    
    try:
        products = await client.get_products_count()
        orders_total = await client.get_orders_count()
        customers = await client.get_customers_count()
        orders = await client.get_orders(limit=100)
        
        now = datetime.utcnow()
        rev_7d = rev_30d = 0.0
        ord_7d = ord_30d = 0
        
        for order in orders:
            created_str = order.get("created_at", "")
            if not created_str:
                continue
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                days = (now - created.replace(tzinfo=None)).days
                total = float(order.get("total_price", 0))
                
                if days <= 7:
                    rev_7d += total
                    ord_7d += 1
                if days <= 30:
                    rev_30d += total
                    ord_30d += 1
            except (ValueError, TypeError, AttributeError):
                continue  # Invalid date format or missing data
        
        return {
            "success": True,
            "stats": {
                "products_count": products,
                "orders_count": orders_total,
                "customers_count": customers,
                "revenue_7d": round(rev_7d, 2),
                "revenue_30d": round(rev_30d, 2),
                "orders_7d": ord_7d,
                "orders_30d": ord_30d,
                "avg_order_value": round(rev_30d / ord_30d, 2) if ord_30d > 0 else 0,
            }
        }
    except Exception as e:
        logger.error(f"Failed to get store analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve store analytics")


@router.get("/stores/{store_id}/products")
async def get_products(
    store_id: str,
    limit: int = Query(50, ge=1, le=250),
    current_user: User = Depends(get_current_user)
):
    """Get products from store."""
    if store_id not in _connected_stores:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = _connected_stores[store_id]
    client = ShopifyClient(store["store_url"], store["access_token"])
    
    try:
        products = await client.get_products(limit=limit)
        return {
            "success": True,
            "products": [
                {
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "handle": p.get("handle"),
                    "status": p.get("status"),
                    "vendor": p.get("vendor"),
                    "price": p.get("variants", [{}])[0].get("price") if p.get("variants") else None,
                }
                for p in products
            ],
            "count": len(products),
        }
    except Exception as e:
        logger.error(f"Failed to get products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve products")


@router.get("/stores/{store_id}/orders")
async def get_orders(
    store_id: str,
    limit: int = Query(50, ge=1, le=250),
    current_user: User = Depends(get_current_user)
):
    """Get orders from store."""
    if store_id not in _connected_stores:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = _connected_stores[store_id]
    client = ShopifyClient(store["store_url"], store["access_token"])
    
    try:
        orders = await client.get_orders(limit=limit)
        return {
            "success": True,
            "orders": [
                {
                    "id": o.get("id"),
                    "order_number": o.get("order_number"),
                    "name": o.get("name"),
                    "email": o.get("email"),
                    "total_price": o.get("total_price"),
                    "currency": o.get("currency"),
                    "financial_status": o.get("financial_status"),
                    "fulfillment_status": o.get("fulfillment_status"),
                    "created_at": o.get("created_at"),
                }
                for o in orders
            ],
            "count": len(orders),
        }
    except Exception as e:
        logger.error(f"Failed to get orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve orders")


# GDPR Webhooks
@router.post("/webhooks/customers/data_request")
async def webhook_customer_data_request(request: Request):
    return {"received": True}

@router.post("/webhooks/customers/redact")
async def webhook_customer_redact(request: Request):
    return {"received": True}

@router.post("/webhooks/shop/redact")
async def webhook_shop_redact(request: Request):
    return {"received": True}


@router.get("/info")
async def get_info():
    """Check if OAuth is configured."""
    config = get_oauth_config()
    return {
        "oauth_configured": bool(config["api_key"] and config["api_secret"]),
        "redirect_uri": config["redirect_uri"],
        "required_scopes": REQUIRED_SCOPES,
    }
