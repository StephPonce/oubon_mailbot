"""
Shopify Webhook Utilities
=========================

Shared utilities for webhook handling:
- HMAC verification (multi-tenant aware)
- Store lookup from webhook domain
- Logging helpers
- Event recording

Author: Ospra Intelligence
"""

import hmac
import hashlib
import base64
import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)


# ============================================================================
# HMAC VERIFICATION (MULTI-TENANT AWARE)
# ============================================================================

def verify_webhook_signature(
    data: bytes,
    hmac_header: str,
    webhook_secret: Optional[str] = None
) -> bool:
    """
    Verify webhook came from Shopify using HMAC-SHA256.
    
    Args:
        data: Raw request body bytes
        hmac_header: X-Shopify-Hmac-Sha256 header value
        webhook_secret: Store-specific webhook secret (or uses env default)
    
    Returns:
        True if signature is valid
    """
    if not hmac_header:
        logger.warning("⚠️ No HMAC header provided")
        return False
    
    # Use provided secret or fall back to env
    secret = webhook_secret or os.getenv("SHOPIFY_WEBHOOK_SECRET", "")
    
    if not secret:
        logger.warning("⚠️ No webhook secret configured - allowing in DEV MODE")
        return True  # Allow in development
    
    # Calculate HMAC
    computed_hmac = hmac.new(
        secret.encode('utf-8'),
        data,
        hashlib.sha256
    ).digest()
    
    computed_b64 = base64.b64encode(computed_hmac).decode('utf-8')
    
    # Constant-time comparison
    return hmac.compare_digest(computed_b64, hmac_header)


async def verify_and_parse_webhook(
    request: Request,
    hmac_header: Optional[str]
) -> Tuple[Dict[str, Any], Optional[int]]:
    """
    Verify webhook signature and parse body.
    
    Returns:
        Tuple of (parsed_data, store_id)
        store_id is None for single-tenant mode or if store not found
    
    Raises:
        HTTPException on verification failure
    """
    body = await request.body()
    
    # Get shop domain from headers (Shopify sends this)
    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
    
    # Multi-tenant: Look up store and get its webhook secret
    store_id = None
    webhook_secret = None
    
    if shop_domain:
        store_info = await lookup_store_by_domain(shop_domain)
        if store_info:
            store_id = store_info.get("id")
            webhook_secret = store_info.get("webhook_secret")
    
    # Verify signature
    if hmac_header:
        if not verify_webhook_signature(body, hmac_header, webhook_secret):
            logger.error(f"❌ Invalid webhook signature for shop: {shop_domain}")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Parse JSON
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse webhook JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    return data, store_id


# ============================================================================
# STORE LOOKUP (MULTI-TENANT)
# ============================================================================

async def lookup_store_by_domain(shop_domain: str) -> Optional[Dict[str, Any]]:
    """
    Look up store in database by Shopify domain.
    
    For SaaS: Returns store credentials and webhook secret
    For single-tenant: Returns default store config
    
    Args:
        shop_domain: e.g., 'mystore.myshopify.com'
    
    Returns:
        Store info dict or None if not found
    """
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.store_models import Store
        
        # Normalize domain
        if not shop_domain.endswith(".myshopify.com"):
            shop_domain = f"{shop_domain}.myshopify.com"
        
        db = SessionLocal()
        try:
            # Look for store with matching URL
            store = db.query(Store).filter(
                Store.store_url.contains(shop_domain.replace(".myshopify.com", ""))
            ).first()
            
            if store:
                credentials = store.credentials if isinstance(store.credentials, dict) else json.loads(store.credentials or "{}")
                return {
                    "id": store.id,
                    "user_id": store.user_id,
                    "store_name": store.store_name,
                    "shop_domain": shop_domain,
                    "webhook_secret": credentials.get("webhook_secret"),
                    "access_token": credentials.get("access_token"),
                }
            
            return None
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to lookup store: {e}")
        return None


async def get_store_or_default(store_id: Optional[int]) -> Dict[str, Any]:
    """
    Get store info by ID, or return default config for single-tenant mode.
    """
    if store_id:
        try:
            from ospra_os.database.connection import SessionLocal
            from ospra_os.database.store_models import Store
            
            db = SessionLocal()
            try:
                store = db.query(Store).filter(Store.id == store_id).first()
                if store:
                    return {
                        "id": store.id,
                        "user_id": store.user_id,
                        "store_name": store.store_name,
                    }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to get store {store_id}: {e}")
    
    # Fallback to default (single-tenant mode)
    return {
        "id": None,
        "user_id": 1,  # Default user
        "store_name": os.getenv("SHOPIFY_STORE_NAME", "default"),
    }


# ============================================================================
# LEARNING EVENT RECORDING
# ============================================================================

async def record_learning_event(
    event_type: str,
    product_id: Optional[str],
    details: Dict[str, Any],
    store_id: Optional[int] = None,
    user_id: Optional[int] = None
):
    """
    Record an event for the AI self-learning system.
    
    Event types:
    - sale: Product was purchased (positive signal)
    - cancellation: Order was cancelled (negative signal)
    - refund: Order was refunded (strong negative signal)
    - cart_abandoned: Cart was abandoned (informational)
    - product_view: Product was viewed (weak positive)
    - dispute: Chargeback filed (very negative signal)
    """
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.performance_models import AILearningEvent
        
        # Determine user_id
        if not user_id and store_id:
            store_info = await get_store_or_default(store_id)
            user_id = store_info.get("user_id", 1)
        user_id = user_id or 1
        
        db = SessionLocal()
        try:
            event = AILearningEvent(
                user_id=user_id,
                event_type=event_type,
                product_id=product_id,
                details={
                    **details,
                    "store_id": store_id,
                    "recorded_at": datetime.utcnow().isoformat(),
                },
                timestamp=datetime.utcnow()
            )
            db.add(event)
            db.commit()
            
            logger.debug(f"📊 Learning event recorded: {event_type} for product {product_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to record learning event: {e}")


# ============================================================================
# NOTIFICATION CREATION
# ============================================================================

async def create_notification(
    notification_type: str,
    title: str,
    message: str,
    severity: str = "info",
    metadata: Optional[Dict[str, Any]] = None,
    store_id: Optional[int] = None
):
    """
    Create a dashboard notification.
    
    Types: order, refund, alert, info, success, warning, error
    Severity: info, success, warning, error, critical
    """
    try:
        from ospra_os.database.product_history import ProductHistoryDB
        
        db = ProductHistoryDB()
        db.create_notification(
            notification_type=notification_type,
            title=title,
            message=message,
            severity=severity,
            metadata={
                **(metadata or {}),
                "store_id": store_id,
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")


# ============================================================================
# NICHE & PRICE DETECTION HELPERS
# ============================================================================

def detect_product_niche(item: Dict[str, Any]) -> str:
    """
    Detect product niche from item data.
    Uses product type, tags, vendor, and name.
    """
    vendor = str(item.get('vendor', '')).lower()
    product_type = str(item.get('product_type', '')).lower()
    name = str(item.get('name', '')).lower()
    tags = str(item.get('tags', '')).lower() if isinstance(item.get('tags'), str) else ''
    
    combined = f"{vendor} {product_type} {name} {tags}"
    
    niche_keywords = {
        "smart_home": ["smart", "wifi", "alexa", "google home", "iot", "automation", "sensor", "connected"],
        "fitness": ["fitness", "gym", "workout", "exercise", "yoga", "sport", "resistance", "weight"],
        "kitchen": ["kitchen", "cooking", "chef", "food", "utensil", "cookware", "baking"],
        "tech": ["tech", "gadget", "electronic", "usb", "charger", "cable", "phone", "tablet"],
        "beauty": ["beauty", "skincare", "makeup", "cosmetic", "hair", "serum", "cream"],
        "home_office": ["office", "desk", "organizer", "work from home", "laptop", "monitor"],
        "outdoor": ["outdoor", "camping", "hiking", "garden", "patio", "bbq", "grill"],
        "pet": ["pet", "dog", "cat", "animal", "puppy", "kitten"],
        "baby": ["baby", "infant", "toddler", "newborn", "nursery"],
        "automotive": ["car", "auto", "vehicle", "automotive", "truck"],
    }
    
    for niche, keywords in niche_keywords.items():
        for keyword in keywords:
            if keyword in combined:
                return niche
    
    return "general"


def detect_price_point(price: float) -> str:
    """Categorize price into price point buckets."""
    if price < 10:
        return "under_10"
    elif price < 25:
        return "10_to_25"
    elif price < 50:
        return "25_to_50"
    elif price < 100:
        return "50_to_100"
    elif price < 200:
        return "100_to_200"
    else:
        return "over_200"


# ============================================================================
# WEBHOOK TOPIC CONSTANTS
# ============================================================================

class WebhookTopics:
    """All Shopify webhook topics we handle."""
    
    # Orders
    ORDERS_CREATE = "orders/create"
    ORDERS_UPDATED = "orders/updated"
    ORDERS_PAID = "orders/paid"
    ORDERS_FULFILLED = "orders/fulfilled"
    ORDERS_CANCELLED = "orders/cancelled"
    ORDERS_EDITED = "orders/edited"
    
    # Refunds & Disputes
    REFUNDS_CREATE = "refunds/create"
    DISPUTES_CREATE = "disputes/create"
    
    # Products
    PRODUCTS_CREATE = "products/create"
    PRODUCTS_UPDATE = "products/update"
    PRODUCTS_DELETE = "products/delete"
    
    # Inventory
    INVENTORY_LEVELS_UPDATE = "inventory_levels/update"
    INVENTORY_ITEMS_UPDATE = "inventory_items/update"
    
    # Customers
    CUSTOMERS_CREATE = "customers/create"
    CUSTOMERS_UPDATE = "customers/update"
    CUSTOMERS_DELETE = "customers/delete"
    
    # Checkouts
    CHECKOUTS_CREATE = "checkouts/create"
    CHECKOUTS_UPDATE = "checkouts/update"
    
    # Fulfillment
    FULFILLMENTS_CREATE = "fulfillments/create"
    FULFILLMENTS_UPDATE = "fulfillments/update"
    
    # GDPR (Required for Shopify Apps)
    CUSTOMERS_DATA_REQUEST = "customers/data_request"
    CUSTOMERS_REDACT = "customers/redact"
    SHOP_REDACT = "shop/redact"
    
    # App Lifecycle
    APP_UNINSTALLED = "app/uninstalled"
    
    @classmethod
    def all_topics(cls) -> list:
        """Get list of all webhook topics."""
        return [
            cls.ORDERS_CREATE,
            cls.ORDERS_UPDATED,
            cls.ORDERS_PAID,
            cls.ORDERS_FULFILLED,
            cls.ORDERS_CANCELLED,
            cls.ORDERS_EDITED,
            cls.REFUNDS_CREATE,
            cls.DISPUTES_CREATE,
            cls.PRODUCTS_CREATE,
            cls.PRODUCTS_UPDATE,
            cls.PRODUCTS_DELETE,
            cls.INVENTORY_LEVELS_UPDATE,
            cls.INVENTORY_ITEMS_UPDATE,
            cls.CUSTOMERS_CREATE,
            cls.CUSTOMERS_UPDATE,
            cls.CUSTOMERS_DELETE,
            cls.CHECKOUTS_CREATE,
            cls.CHECKOUTS_UPDATE,
            cls.FULFILLMENTS_CREATE,
            cls.FULFILLMENTS_UPDATE,
            cls.CUSTOMERS_DATA_REQUEST,
            cls.CUSTOMERS_REDACT,
            cls.SHOP_REDACT,
            cls.APP_UNINSTALLED,
        ]
    
    @classmethod
    def essential_topics(cls) -> list:
        """Get essential topics for basic operation."""
        return [
            cls.ORDERS_CREATE,
            cls.ORDERS_PAID,
            cls.ORDERS_FULFILLED,
            cls.ORDERS_CANCELLED,
            cls.REFUNDS_CREATE,
            cls.PRODUCTS_UPDATE,
            cls.INVENTORY_LEVELS_UPDATE,
            cls.CUSTOMERS_CREATE,
            cls.CHECKOUTS_CREATE,
            # GDPR required
            cls.CUSTOMERS_DATA_REQUEST,
            cls.CUSTOMERS_REDACT,
            cls.SHOP_REDACT,
            cls.APP_UNINSTALLED,
        ]
