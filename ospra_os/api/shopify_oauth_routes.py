"""
Shopify OAuth Routes - SaaS Multi-Store Integration
====================================================

Handles complete OAuth flow for connecting Shopify stores:
1. User clicks "Connect Shopify Store"
2. Redirect to Shopify authorization
3. Handle callback with auth code
4. Exchange for access token
5. Store credentials securely
6. AUTO-REGISTER ALL WEBHOOKS
7. Return to dashboard

This enables the "Sign up → Connect store → Done" experience.

Author: Ospra Intelligence
"""

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
import hmac
import hashlib
import secrets
import logging
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urlencode, parse_qs
from pydantic import BaseModel
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User
from ospra_os.security.security_audit import (
    log_oauth_completed,
    log_credential_stored,
    log_security_event,
    SecurityEventType,
    SecuritySeverity,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shopify/oauth", tags=["Shopify OAuth"])


# ============================================================================
# CONFIGURATION
# ============================================================================

# Required scopes for full Ospra functionality
SHOPIFY_SCOPES = [
    # Products
    "read_products",
    "write_products",
    # Orders
    "read_orders",
    "write_orders",
    # Customers
    "read_customers",
    "write_customers",
    # Inventory
    "read_inventory",
    "write_inventory",
    "read_locations",
    # Fulfillment
    "read_fulfillments",
    "write_fulfillments",
    "read_shipping",
    "write_shipping",
    # Analytics
    "read_analytics",
    # Content
    "read_content",
    "write_content",
    # Pricing
    "read_price_rules",
    "write_price_rules",
    "read_discounts",
    "write_discounts",
    # Marketing
    "read_marketing_events",
    "write_marketing_events",
    # Themes (for branding)
    "read_themes",
    # Draft Orders (for B2B)
    "read_draft_orders",
    "write_draft_orders",
    # Checkouts
    "read_checkouts",
    "write_checkouts",
]

# In-memory nonce storage (use Redis in production for multi-instance)
# Maps nonce -> {shop, user_id, created_at}
_oauth_states: Dict[str, Dict[str, Any]] = {}


def get_shopify_credentials():
    """Get Shopify Partner app credentials."""
    api_key = os.getenv("SHOPIFY_API_KEY")
    api_secret = os.getenv("SHOPIFY_API_SECRET")
    
    if not api_key or not api_secret:
        raise ValueError(
            "SHOPIFY_API_KEY and SHOPIFY_API_SECRET must be set. "
            "Get these from your Shopify Partner Dashboard."
        )
    
    return api_key, api_secret


def get_oauth_redirect_uri():
    """Get the OAuth callback URL."""
    base_url = os.getenv(
        "OAUTH_BASE_URL",
        os.getenv("RENDER_EXTERNAL_URL", "https://ospra-intelligence-api.onrender.com")
    )
    return f"{base_url}/api/shopify/oauth/callback"


def get_frontend_url():
    """Get the frontend URL for redirects after OAuth."""
    return os.getenv("FRONTEND_URL", "http://localhost:5173")


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class OAuthInitRequest(BaseModel):
    """Request to start OAuth flow."""
    shop_domain: str  # e.g., "mystore" or "mystore.myshopify.com"
    user_id: Optional[int] = None  # Ospra user ID if logged in


class OAuthStatusResponse(BaseModel):
    """OAuth connection status."""
    connected: bool
    shop_domain: Optional[str] = None
    store_name: Optional[str] = None
    scopes: Optional[list] = None
    connected_at: Optional[str] = None


# ============================================================================
# OAUTH FLOW ENDPOINTS
# ============================================================================

class OAuthInitRequestSecure(BaseModel):
    """Request to start OAuth flow (secure version - no user_id)."""
    shop_domain: str  # e.g., "mystore" or "mystore.myshopify.com"


@router.post("/initiate")
async def initiate_oauth(
    request: OAuthInitRequestSecure,
    current_user: User = Depends(get_current_user)
):
    """
    Step 1: Initiate OAuth flow.

    SECURITY: Requires JWT authentication. User ID is extracted from the token,
    not from the request body (prevents user impersonation attacks).

    Returns the Shopify authorization URL to redirect the user to.

    Usage:
        POST /api/shopify/oauth/initiate
        Authorization: Bearer <token>
        {"shop_domain": "mystore"}

    Response:
        {"authorization_url": "https://mystore.myshopify.com/admin/oauth/authorize?..."}
    """
    # SECURITY: User ID comes from verified JWT token, not request body
    user_id = current_user.id

    try:
        api_key, _ = get_shopify_credentials()
    except ValueError as e:
        logger.error(f"Shopify credentials error: {e}")
        raise HTTPException(status_code=500, detail="Shopify configuration error. Please contact support.")

    # Normalize shop domain
    shop_domain = request.shop_domain.strip().lower()
    if not shop_domain.endswith(".myshopify.com"):
        shop_domain = f"{shop_domain}.myshopify.com"

    # Validate shop domain format
    if not shop_domain.replace(".myshopify.com", "").replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid shop domain format")

    # Generate secure nonce for CSRF protection
    nonce = secrets.token_urlsafe(32)

    # Store nonce with metadata - user_id from JWT token
    _oauth_states[nonce] = {
        "shop": shop_domain,
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Build authorization URL
    redirect_uri = get_oauth_redirect_uri()

    params = {
        "client_id": api_key,
        "scope": ",".join(SHOPIFY_SCOPES),
        "redirect_uri": redirect_uri,
        "state": nonce,
    }

    authorization_url = f"https://{shop_domain}/admin/oauth/authorize?{urlencode(params)}"

    logger.info(f"🔐 OAuth initiated for {shop_domain} by user {user_id}")

    return {
        "authorization_url": authorization_url,
        "shop_domain": shop_domain,
        "state": nonce,
    }


@router.get("/authorize")
async def authorize_redirect(
    shop: str = Query(..., description="Shop domain (e.g., mystore.myshopify.com)"),
    current_user: User = Depends(get_current_user)
):
    """
    Alternative: Direct redirect to Shopify authorization.

    Usage:
        GET /api/shopify/oauth/authorize?shop=mystore

    This will redirect the browser directly to Shopify's authorization page.
    """
    user_id = current_user.id
    try:
        api_key, _ = get_shopify_credentials()
    except ValueError as e:
        logger.error(f"Shopify credentials error: {e}")
        raise HTTPException(status_code=500, detail="Shopify configuration error. Please contact support.")
    
    # Normalize shop domain
    shop_domain = shop.strip().lower()
    if not shop_domain.endswith(".myshopify.com"):
        shop_domain = f"{shop_domain}.myshopify.com"
    
    # Generate nonce
    nonce = secrets.token_urlsafe(32)
    _oauth_states[nonce] = {
        "shop": shop_domain,
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # Build authorization URL
    redirect_uri = get_oauth_redirect_uri()
    
    params = {
        "client_id": api_key,
        "scope": ",".join(SHOPIFY_SCOPES),
        "redirect_uri": redirect_uri,
        "state": nonce,
    }
    
    authorization_url = f"https://{shop_domain}/admin/oauth/authorize?{urlencode(params)}"
    
    logger.info(f"🔐 OAuth redirect for {shop_domain}")
    
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str = Query(..., description="Authorization code from Shopify"),
    shop: str = Query(..., description="Shop domain"),
    state: str = Query(..., description="State nonce for CSRF verification"),
    hmac: Optional[str] = Query(None, description="HMAC signature"),
    timestamp: Optional[str] = Query(None, description="Timestamp"),
):
    """
    Step 2: Handle OAuth callback from Shopify.
    
    This is called by Shopify after the user authorizes the app.
    
    Flow:
    1. Verify HMAC signature
    2. Verify state nonce
    3. Exchange code for access token
    4. Store credentials in database
    5. Register all webhooks
    6. Redirect to frontend
    """
    logger.info(f"📥 OAuth callback received for {shop}")
    
    # ==========================================================
    # STEP 1: Verify HMAC signature (security)
    # ==========================================================
    try:
        _, api_secret = get_shopify_credentials()
    except ValueError as e:
        logger.error(f"OAuth credentials error: {e}")
        return RedirectResponse(
            url=f"{get_frontend_url()}/settings/stores?error=configuration_error"
        )
    
    if hmac:
        # Build query string for HMAC verification (exclude hmac itself)
        query_params = dict(request.query_params)
        received_hmac = query_params.pop("hmac", "")
        
        # Sort and encode
        sorted_params = "&".join(
            f"{k}={v}" for k, v in sorted(query_params.items())
        )
        
        # Calculate expected HMAC
        import hashlib
        import hmac as hmac_module
        
        computed_hmac = hmac_module.new(
            api_secret.encode("utf-8"),
            sorted_params.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac_module.compare_digest(computed_hmac, received_hmac):
            logger.error("❌ HMAC verification failed")
            return RedirectResponse(
                url=f"{get_frontend_url()}/settings/stores?error=invalid_signature"
            )
    
    # ==========================================================
    # STEP 2: Verify state nonce (CSRF protection)
    # ==========================================================
    if state not in _oauth_states:
        logger.error("❌ Invalid or expired state nonce")
        return RedirectResponse(
            url=f"{get_frontend_url()}/settings/stores?error=invalid_state"
        )
    
    state_data = _oauth_states.pop(state)  # Remove used nonce
    user_id = state_data.get("user_id")
    
    # Normalize shop domain
    shop_domain = shop.strip().lower()
    if not shop_domain.endswith(".myshopify.com"):
        shop_domain = f"{shop_domain}.myshopify.com"
    
    # ==========================================================
    # STEP 3: Exchange code for access token
    # ==========================================================
    api_key, api_secret = get_shopify_credentials()
    
    token_url = f"https://{shop_domain}/admin/oauth/access_token"
    
    payload = {
        "client_id": api_key,
        "client_secret": api_secret,
        "code": code,
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, json=payload, timeout=30.0)
            
            if response.status_code != 200:
                logger.error(f"❌ Token exchange failed: {response.text}")
                return RedirectResponse(
                    url=f"{get_frontend_url()}/settings/stores?error=token_exchange_failed"
                )
            
            token_data = response.json()
            access_token = token_data.get("access_token")
            granted_scopes = token_data.get("scope", "")
            
    except Exception as e:
        logger.error(f"❌ Token exchange error: {e}")
        return RedirectResponse(
            url=f"{get_frontend_url()}/settings/stores?error=network_error"
        )
    
    logger.info(f"✅ Access token received for {shop_domain}")
    
    # ==========================================================
    # STEP 4: Get shop info
    # ==========================================================
    try:
        shop_info = await get_shop_info(shop_domain, access_token)
        store_name = shop_info.get("name", shop_domain.replace(".myshopify.com", ""))
        store_email = shop_info.get("email", "")
        store_currency = shop_info.get("currency", "USD")
    except Exception as e:
        logger.warning(f"Could not fetch shop info: {e}")
        store_name = shop_domain.replace(".myshopify.com", "")
        store_email = ""
        store_currency = "USD"
    
    # ==========================================================
    # STEP 5: Generate webhook secret for this store
    # ==========================================================
    webhook_secret = secrets.token_urlsafe(32)
    
    # ==========================================================
    # STEP 6: Store credentials in database
    # ==========================================================
    store_id = await save_store_credentials(
        user_id=user_id,
        shop_domain=shop_domain,
        store_name=store_name,
        access_token=access_token,
        webhook_secret=webhook_secret,
        scopes=granted_scopes,
        currency=store_currency,
        email=store_email,
    )
    
    # ==========================================================
    # STEP 7: AUTO-REGISTER ALL WEBHOOKS 🔥
    # ==========================================================
    try:
        from ospra_os.webhooks.webhook_registry import register_webhooks_for_store
        
        webhook_result = await register_webhooks_for_store(
            shop_domain=shop_domain,
            access_token=access_token,
            essential_only=False,  # Register ALL webhooks
        )
        
        if webhook_result.get("success"):
            logger.info(
                f"✅ Webhooks registered: {webhook_result.get('registered')} new, "
                f"{webhook_result.get('already_existed')} existing"
            )
        else:
            logger.warning(f"⚠️ Webhook registration had issues: {webhook_result}")
            
    except Exception as e:
        logger.error(f"❌ Webhook registration failed: {e}")
        # Don't fail the whole OAuth - store is connected, webhooks can be retried
    
    # ==========================================================
    # STEP 8: Redirect to frontend with success
    # ==========================================================
    logger.info(f"🎉 Store {store_name} ({shop_domain}) successfully connected!")
    
    success_url = (
        f"{get_frontend_url()}/settings/stores"
        f"?success=true"
        f"&shop={shop_domain}"
        f"&store_name={store_name}"
    )
    
    return RedirectResponse(url=success_url)


# ============================================================================
# STORE MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/status")
async def get_oauth_status(
    shop: Optional[str] = Query(None, description="Shop domain to check"),
    current_user: User = Depends(get_current_user)
):
    """
    Check OAuth connection status.

    Can check:
    - Specific shop: ?shop=mystore.myshopify.com
    - All stores for user: uses authenticated user
    """
    user_id = current_user.id
    if shop:
        # Check specific shop
        store = await get_store_by_domain(shop)
        if store:
            return {
                "connected": True,
                "shop_domain": store.get("shop_domain"),
                "store_name": store.get("store_name"),
                "scopes": store.get("scopes", "").split(","),
                "connected_at": store.get("connected_at"),
            }
        return {"connected": False}
    
    if user_id:
        # Get all stores for user
        stores = await get_user_stores(user_id)
        return {
            "stores": stores,
            "count": len(stores),
        }
    
    raise HTTPException(status_code=400, detail="Provide shop or user_id parameter")


@router.post("/disconnect")
async def disconnect_store(
    shop: str = Query(..., description="Shop domain to disconnect"),
    current_user: User = Depends(get_current_user)
):
    """
    Disconnect a Shopify store.

    This:
    1. Marks store as inactive
    2. Revokes webhooks (optional)
    3. Does NOT delete data (for GDPR we wait for shop/redact webhook)
    """
    user_id = current_user.id
    store = await get_store_by_domain(shop)

    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Verify ownership - user must own the store
    if store.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not your store")
    
    # Mark store as inactive
    success = await deactivate_store(shop)
    
    if success:
        logger.info(f"👋 Store {shop} disconnected")
        return {"success": True, "message": f"Store {shop} disconnected"}
    
    raise HTTPException(status_code=500, detail="Failed to disconnect store")


@router.post("/reconnect")
async def reconnect_store(
    request: OAuthInitRequestSecure,
    current_user: User = Depends(get_current_user)
):
    """
    Reconnect a previously disconnected store.

    SECURITY: Requires JWT authentication.
    Initiates new OAuth flow but preserves existing data.
    """
    return await initiate_oauth(request, current_user)


@router.post("/sync-webhooks")
async def sync_webhooks(
    shop: str = Query(..., description="Shop domain"),
    current_user: User = Depends(get_current_user)
):
    """
    Manually sync/re-register webhooks for a store.

    SECURITY: Requires JWT authentication and store ownership verification.
    Useful if webhooks got out of sync or new ones were added.
    """
    user_id = current_user.id
    store = await get_store_by_domain(shop)

    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # SECURITY: Verify the user owns this store
    if store.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to manage this store")

    access_token = store.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Store not properly connected")

    try:
        from ospra_os.webhooks.webhook_registry import sync_store_webhooks

        result = await sync_store_webhooks(
            shop_domain=shop,
            access_token=access_token,
        )

        return {
            "success": True,
            "result": result,
        }

    except Exception as e:
        logger.error(f"Webhook sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to sync webhooks. Please try again later.")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_shop_info(shop_domain: str, access_token: str) -> Dict[str, Any]:
    """Fetch store information from Shopify."""
    api_version = os.getenv("SHOPIFY_API_VERSION", "2024-10")
    url = f"https://{shop_domain}/admin/api/{api_version}/shop.json"
    
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()
        return response.json().get("shop", {})


async def save_store_credentials(
    user_id: Optional[int],
    shop_domain: str,
    store_name: str,
    access_token: str,
    webhook_secret: str,
    scopes: str,
    currency: str,
    email: str,
) -> Optional[int]:
    """Save store credentials to database."""
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.store_models import Store
        from ospra_os.database.base import Platform, StoreStatus
        
        db = SessionLocal()
        try:
            # Check if store already exists
            existing = db.query(Store).filter(
                Store.store_url.contains(shop_domain.replace(".myshopify.com", ""))
            ).first()
            
            credentials = {
                "shop_url": shop_domain,
                "access_token": access_token,
                "webhook_secret": webhook_secret,
                "scopes": scopes,
                "api_version": os.getenv("SHOPIFY_API_VERSION", "2024-10"),
                "connected_at": datetime.utcnow().isoformat(),
            }
            
            if existing:
                # Update existing store
                existing.credentials = credentials
                existing.store_name = store_name
                existing.status = StoreStatus.ACTIVE
                existing.is_active = True
                existing.currency = currency
                existing.last_sync = datetime.utcnow()
                existing.sync_error = None

                if user_id and not existing.user_id:
                    existing.user_id = user_id

                db.commit()
                logger.info(f"Updated existing store: {store_name}")

                # SECURITY AUDIT: Log credential storage
                log_credential_stored(
                    user_id=user_id or existing.user_id,
                    credential_type="shopify_oauth",
                    store_id=existing.id,
                    store_name=store_name,
                    db=db,
                )

                return existing.id

            else:
                # Create new store
                new_store = Store(
                    user_id=user_id or 1,  # Default to user 1 if not provided
                    store_name=store_name,
                    store_url=f"https://{shop_domain}",
                    platform=Platform.SHOPIFY,
                    credentials=credentials,
                    currency=currency,
                    status=StoreStatus.ACTIVE,
                    is_active=True,
                    created_at=datetime.utcnow(),
                    last_sync=datetime.utcnow(),
                )
                db.add(new_store)
                db.commit()
                db.refresh(new_store)

                logger.info(f"Created new store: {store_name} (ID: {new_store.id})")

                # SECURITY AUDIT: Log OAuth completion and credential storage
                log_oauth_completed(
                    user_id=user_id or 1,
                    provider="shopify",
                    store_id=new_store.id,
                    store_name=store_name,
                    db=db,
                )

                return new_store.id
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to save store credentials: {e}")
        import traceback
        traceback.print_exc()
        return None


async def get_store_by_domain(shop_domain: str) -> Optional[Dict[str, Any]]:
    """Get store info by domain."""
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.store_models import Store
        
        # Normalize domain
        if not shop_domain.endswith(".myshopify.com"):
            shop_domain = f"{shop_domain}.myshopify.com"
        
        db = SessionLocal()
        try:
            store = db.query(Store).filter(
                Store.store_url.contains(shop_domain.replace(".myshopify.com", ""))
            ).first()
            
            if store:
                creds = store.credentials if isinstance(store.credentials, dict) else json.loads(store.credentials or "{}")
                return {
                    "id": store.id,
                    "user_id": store.user_id,
                    "store_name": store.store_name,
                    "shop_domain": shop_domain,
                    "access_token": creds.get("access_token"),
                    "webhook_secret": creds.get("webhook_secret"),
                    "scopes": creds.get("scopes", ""),
                    "connected_at": creds.get("connected_at"),
                    "is_active": store.is_active,
                    "status": str(store.status.value) if store.status else "unknown",
                }
            
            return None
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to get store: {e}")
        return None


async def get_user_stores(user_id: int) -> list:
    """Get all stores for a user."""
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.store_models import Store
        
        db = SessionLocal()
        try:
            stores = db.query(Store).filter(Store.user_id == user_id).all()
            
            result = []
            for store in stores:
                creds = store.credentials if isinstance(store.credentials, dict) else json.loads(store.credentials or "{}")
                result.append({
                    "id": store.id,
                    "store_name": store.store_name,
                    "shop_domain": creds.get("shop_url", ""),
                    "platform": str(store.platform.value) if store.platform else "unknown",
                    "is_active": store.is_active,
                    "status": str(store.status.value) if store.status else "unknown",
                    "connected_at": creds.get("connected_at"),
                    "last_sync": store.last_sync.isoformat() if store.last_sync else None,
                })
            
            return result
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to get user stores: {e}")
        return []


async def deactivate_store(shop_domain: str) -> bool:
    """Deactivate a store (disconnect)."""
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.store_models import Store
        from ospra_os.database.base import StoreStatus
        
        # Normalize domain
        if not shop_domain.endswith(".myshopify.com"):
            shop_domain = f"{shop_domain}.myshopify.com"
        
        db = SessionLocal()
        try:
            store = db.query(Store).filter(
                Store.store_url.contains(shop_domain.replace(".myshopify.com", ""))
            ).first()
            
            if store:
                store.is_active = False
                store.status = StoreStatus.DISCONNECTED
                db.commit()
                return True
            
            return False
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to deactivate store: {e}")
        return False


# ============================================================================
# INSTALLATION ENDPOINT (For Shopify App Store)
# ============================================================================

@router.get("/install")
async def install_app(
    shop: str = Query(..., description="Shop domain from Shopify"),
    current_user: User = Depends(get_current_user)
):
    """
    App installation endpoint for Shopify App Store.

    SECURITY: Requires JWT authentication.
    NOTE: If using Shopify App Store public listing, you may need a separate
    unauthenticated flow. For embedded/private apps, JWT auth is required.

    Shopify sends users here when they click "Install" in the app store.
    """
    return await authorize_redirect(shop=shop, current_user=current_user)
