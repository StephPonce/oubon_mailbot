"""
WooCommerce Integration - Universal OAuth
==========================================

No app registration needed. Works with ANY WooCommerce store.
Users authorize directly on their own WordPress site.
"""

import os
import secrets
import json
from typing import Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlencode, quote
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx
import base64

load_dotenv()

router = APIRouter(prefix="/api/woocommerce", tags=["WooCommerce"])

# ============================================================================
# CONFIGURATION
# ============================================================================

APP_NAME = "Ospra Intelligence"
APP_URL = os.getenv("APP_URL", "http://localhost:5173")
CALLBACK_URL = os.getenv("WOOCOMMERCE_CALLBACK_URL", "http://localhost:8001/api/woocommerce/oauth/callback")

# OAuth state storage (use Redis in production)
_oauth_states: Dict[str, Dict[str, Any]] = {}

# Connected stores (use database in production)
_connected_stores: Dict[str, Dict[str, Any]] = {}

# ============================================================================
# MODELS
# ============================================================================

class ConnectStoreRequest(BaseModel):
    store_url: str

# ============================================================================
# WOOCOMMERCE CLIENT
# ============================================================================

class WooCommerceClient:
    def __init__(self, store_url: str, consumer_key: str, consumer_secret: str):
        # Normalize URL
        store_url = store_url.lower().strip().rstrip('/')
        if not store_url.startswith('http'):
            store_url = f"https://{store_url}"
        
        self.store_url = store_url
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.base_url = f"{store_url}/wp-json/wc/v3"
    
    def _get_auth(self) -> tuple:
        """Basic auth for WooCommerce API."""
        return (self.consumer_key, self.consumer_secret)
    
    async def get(self, endpoint: str, params: dict = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/{endpoint}",
                auth=self._get_auth(),
                params=params,
                timeout=30.0
            )
            resp.raise_for_status()
            return resp.json()
    
    async def post(self, endpoint: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/{endpoint}",
                auth=self._get_auth(),
                json=data,
                timeout=30.0
            )
            resp.raise_for_status()
            return resp.json()
    
    async def put(self, endpoint: str, data: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self.base_url}/{endpoint}",
                auth=self._get_auth(),
                json=data,
                timeout=30.0
            )
            resp.raise_for_status()
            return resp.json()
    
    # --- Store Info ---
    async def get_store_info(self) -> dict:
        """Get store system status and info."""
        return await self.get("system_status")
    
    # --- Products ---
    async def get_products_count(self) -> int:
        products = await self.get("reports/products/totals")
        return sum(p.get("total", 0) for p in products)
    
    async def get_products(self, per_page: int = 50, page: int = 1) -> list:
        return await self.get("products", {"per_page": per_page, "page": page})
    
    async def get_product(self, product_id: int) -> dict:
        return await self.get(f"products/{product_id}")
    
    async def create_product(self, product_data: dict) -> dict:
        return await self.post("products", product_data)
    
    async def update_product(self, product_id: int, product_data: dict) -> dict:
        return await self.put(f"products/{product_id}", product_data)
    
    # --- Orders ---
    async def get_orders_count(self) -> int:
        totals = await self.get("reports/orders/totals")
        return sum(t.get("total", 0) for t in totals)
    
    async def get_orders(self, per_page: int = 50, page: int = 1, status: str = "any") -> list:
        params = {"per_page": per_page, "page": page}
        if status != "any":
            params["status"] = status
        return await self.get("orders", params)
    
    async def get_order(self, order_id: int) -> dict:
        return await self.get(f"orders/{order_id}")
    
    # --- Customers ---
    async def get_customers_count(self) -> int:
        totals = await self.get("reports/customers/totals")
        return sum(t.get("total", 0) for t in totals)
    
    async def get_customers(self, per_page: int = 50, page: int = 1) -> list:
        return await self.get("customers", {"per_page": per_page, "page": page})
    
    # --- Reports ---
    async def get_sales_report(self, period: str = "month") -> dict:
        return await self.get("reports/sales", {"period": period})
    
    async def get_top_sellers(self, period: str = "month") -> list:
        return await self.get("reports/top_sellers", {"period": period})


# ============================================================================
# HELPERS
# ============================================================================

def normalize_store_url(url: str) -> str:
    """Normalize store URL."""
    url = url.lower().strip().rstrip('/')
    # Remove protocol for storage key
    url = url.replace('https://', '').replace('http://', '')
    # Remove www
    if url.startswith('www.'):
        url = url[4:]
    return url


def get_full_url(url: str) -> str:
    """Get full URL with protocol."""
    url = url.lower().strip().rstrip('/')
    if not url.startswith('http'):
        url = f"https://{url}"
    return url


# ============================================================================
# ROUTES
# ============================================================================

@router.get("/stores")
async def list_stores():
    """List connected WooCommerce stores."""
    stores = []
    
    for store_id, store_data in _connected_stores.items():
        stores.append({
            "id": store_id,
            "store_name": store_data.get("store_name", store_id),
            "store_url": store_data.get("store_url"),
            "currency": store_data.get("currency", "USD"),
            "status": "active",
            "platform": "woocommerce",
            "connected_at": store_data.get("connected_at"),
        })
    
    return {"success": True, "stores": stores, "count": len(stores)}


@router.post("/connect")
async def connect_store(request: ConnectStoreRequest):
    """Initiate WooCommerce OAuth flow."""
    store_url = request.store_url.strip()
    full_url = get_full_url(store_url)
    
    # Generate unique state
    state = secrets.token_urlsafe(32)
    
    _oauth_states[state] = {
        "store_url": full_url,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # WooCommerce OAuth endpoint
    # Docs: https://woocommerce.github.io/woocommerce-rest-api-docs/#authentication
    auth_params = {
        "app_name": APP_NAME,
        "scope": "read_write",  # read, write, or read_write
        "user_id": state,  # We use state as user_id for simplicity
        "return_url": f"{APP_URL}?wc_connected=true",
        "callback_url": CALLBACK_URL,
    }
    
    auth_url = f"{full_url}/wc-auth/v1/authorize?{urlencode(auth_params)}"
    
    return {
        "success": True,
        "oauth_required": True,
        "authorization_url": auth_url,
        "message": "Redirecting to your WooCommerce store for authorization..."
    }


@router.post("/oauth/callback")
async def oauth_callback(request: Request):
    """
    WooCommerce OAuth callback.
    WooCommerce POSTs the credentials to this endpoint.
    """
    try:
        body = await request.json()
    except:
        body = {}
    
    # WooCommerce sends: user_id (our state), consumer_key, consumer_secret
    user_id = body.get("user_id")  # This is our state
    consumer_key = body.get("consumer_key")
    consumer_secret = body.get("consumer_secret")
    
    if not all([user_id, consumer_key, consumer_secret]):
        return {"success": False, "error": "Missing credentials"}
    
    # Verify state
    if user_id not in _oauth_states:
        return {"success": False, "error": "Invalid or expired state"}
    
    state_data = _oauth_states.pop(user_id)
    store_url = state_data.get("store_url")
    
    # Test the connection and get store info
    try:
        client = WooCommerceClient(store_url, consumer_key, consumer_secret)
        store_info = await client.get_store_info()
        
        store_name = store_info.get("environment", {}).get("site_url", store_url)
        # Clean up store name
        store_name = store_name.replace("https://", "").replace("http://", "").rstrip("/")
        
        currency = store_info.get("settings", {}).get("currency", "USD")
        
    except Exception as e:
        # Still save, but with limited info
        store_name = normalize_store_url(store_url)
        currency = "USD"
    
    # Store the connection
    store_id = normalize_store_url(store_url)
    _connected_stores[store_id] = {
        "store_name": store_name,
        "store_url": store_url,
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret,
        "currency": currency,
        "connected_at": datetime.utcnow().isoformat(),
    }
    
    return {"success": True, "message": "Store connected successfully"}


@router.get("/oauth/callback")
async def oauth_callback_get(
    success: str = Query(None),
    user_id: str = Query(None),
):
    """
    Handle GET callback (some WooCommerce versions redirect with GET).
    """
    frontend_url = APP_URL
    
    if success == "1" or success == "true":
        return RedirectResponse(url=f"{frontend_url}?wc_connected=true")
    else:
        return RedirectResponse(url=f"{frontend_url}?error=WooCommerce+authorization+failed")


@router.delete("/stores/{store_id:path}")
async def disconnect_store(store_id: str):
    """Disconnect a WooCommerce store."""
    # URL decode the store_id
    store_id = store_id.replace("%2F", "/").replace("%3A", ":")
    normalized = normalize_store_url(store_id)
    
    if normalized in _connected_stores:
        del _connected_stores[normalized]
        return {"success": True, "message": "Store disconnected"}
    
    raise HTTPException(status_code=404, detail="Store not found")


@router.get("/stores/{store_id:path}/stats")
async def get_store_stats(store_id: str):
    """Get WooCommerce store statistics."""
    normalized = normalize_store_url(store_id)
    
    if normalized not in _connected_stores:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = _connected_stores[normalized]
    client = WooCommerceClient(
        store["store_url"],
        store["consumer_key"],
        store["consumer_secret"]
    )
    
    try:
        # Get counts
        products_count = await client.get_products_count()
        orders_count = await client.get_orders_count()
        customers_count = await client.get_customers_count()
        
        # Get recent orders for revenue calculation
        orders = await client.get_orders(per_page=100)
        
        now = datetime.utcnow()
        rev_7d = rev_30d = 0.0
        ord_7d = ord_30d = 0
        
        for order in orders:
            date_str = order.get("date_created", "")
            if not date_str:
                continue
            try:
                # WooCommerce format: 2024-01-15T10:30:00
                created = datetime.fromisoformat(date_str.replace("Z", ""))
                days = (now - created).days
                total = float(order.get("total", 0))
                
                if days <= 7:
                    rev_7d += total
                    ord_7d += 1
                if days <= 30:
                    rev_30d += total
                    ord_30d += 1
            except:
                continue
        
        return {
            "success": True,
            "stats": {
                "products_count": products_count,
                "orders_count": orders_count,
                "customers_count": customers_count,
                "revenue_7d": round(rev_7d, 2),
                "revenue_30d": round(rev_30d, 2),
                "orders_7d": ord_7d,
                "orders_30d": ord_30d,
                "avg_order_value": round(rev_30d / ord_30d, 2) if ord_30d > 0 else 0,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores/{store_id:path}/products")
async def get_products(store_id: str, per_page: int = Query(50, ge=1, le=100), page: int = Query(1, ge=1)):
    """Get products from WooCommerce store."""
    normalized = normalize_store_url(store_id)
    
    if normalized not in _connected_stores:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = _connected_stores[normalized]
    client = WooCommerceClient(
        store["store_url"],
        store["consumer_key"],
        store["consumer_secret"]
    )
    
    try:
        products = await client.get_products(per_page=per_page, page=page)
        return {
            "success": True,
            "products": [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "slug": p.get("slug"),
                    "status": p.get("status"),
                    "price": p.get("price"),
                    "regular_price": p.get("regular_price"),
                    "sale_price": p.get("sale_price"),
                    "stock_status": p.get("stock_status"),
                    "stock_quantity": p.get("stock_quantity"),
                }
                for p in products
            ],
            "count": len(products),
            "page": page,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores/{store_id:path}/orders")
async def get_orders(store_id: str, per_page: int = Query(50, ge=1, le=100), page: int = Query(1, ge=1)):
    """Get orders from WooCommerce store."""
    normalized = normalize_store_url(store_id)
    
    if normalized not in _connected_stores:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = _connected_stores[normalized]
    client = WooCommerceClient(
        store["store_url"],
        store["consumer_key"],
        store["consumer_secret"]
    )
    
    try:
        orders = await client.get_orders(per_page=per_page, page=page)
        return {
            "success": True,
            "orders": [
                {
                    "id": o.get("id"),
                    "number": o.get("number"),
                    "status": o.get("status"),
                    "total": o.get("total"),
                    "currency": o.get("currency"),
                    "customer_email": o.get("billing", {}).get("email"),
                    "customer_name": f"{o.get('billing', {}).get('first_name', '')} {o.get('billing', {}).get('last_name', '')}".strip(),
                    "date_created": o.get("date_created"),
                }
                for o in orders
            ],
            "count": len(orders),
            "page": page,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stores/{store_id:path}/products")
async def create_product(store_id: str, request: Request):
    """Create a product in WooCommerce store."""
    normalized = normalize_store_url(store_id)
    
    if normalized not in _connected_stores:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = _connected_stores[normalized]
    client = WooCommerceClient(
        store["store_url"],
        store["consumer_key"],
        store["consumer_secret"]
    )
    
    try:
        product_data = await request.json()
        product = await client.create_product(product_data)
        return {"success": True, "product": product}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_info():
    """Get WooCommerce integration info."""
    return {
        "platform": "woocommerce",
        "oauth_type": "OAuth 1.0a (REST API Keys)",
        "requires_app_registration": False,
        "callback_url": CALLBACK_URL,
        "supported_scopes": ["read", "write", "read_write"],
        "notes": "No approval needed. Works with any WooCommerce store immediately."
    }
