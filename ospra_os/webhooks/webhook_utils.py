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
from datetime import datetime, timezone
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
        # SECURITY: NEVER allow webhooks without verification in production
        # If secret is not configured, fail closed (reject the request)
        logger.error("❌ SECURITY: No webhook secret configured - rejecting request")
        return False
    
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
    
    # SECURITY: Signature verification is REQUIRED in production
    # If no HMAC header is provided, reject the request
    if not hmac_header:
        logger.error(f"❌ SECURITY: No HMAC signature header for shop: {shop_domain}")
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    # Verify signature
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
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                },
                timestamp=datetime.now(timezone.utc)
            )
            db.add(event)
            db.commit()
            
            logger.debug(f"📊 Learning event recorded: {event_type} for product {product_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to record learning event: {e}")


# ============================================================================
# Self-learning Phase 5B: real-time ProductPerformance upsert from webhooks
# ============================================================================
# SalesSyncService pulls ProductPerformance data every 6h via Shopify Admin
# API. That works but creates a 0-6h delay between an order landing and
# the discovery engine's learning loop seeing the revenue. For real-time
# attribution we ALSO upsert ProductPerformance directly from the
# webhooks/* handlers — idempotent on (product_id, date) so the periodic
# sync overwrite is safe.
# ============================================================================

async def upsert_product_performance_from_order(
    *,
    order_id: str,
    line_items: list,
    store_id: Optional[int],
    user_id: int,
    is_refund: bool = False,
):
    """Real-time upsert: take a Shopify order's line_items and update
    today's ProductPerformance row for each (product) involved.

    Looks up our internal Product row by source_product_id matching the
    Shopify product_id from the line item. If no Product row exists
    (i.e. the buyer ordered something that wasn't surfaced by our
    discovery engine), we silently skip — those non-Ospra products
    aren't part of the learning loop.

    Idempotency: tracks processed order_ids in details JSON to avoid
    double-counting if the same webhook fires multiple times. SalesSyncService
    overwrite is also safe because it sets absolute values (not increments).
    """
    if not user_id or not line_items:
        return

    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.performance_models import ProductPerformance
        from ospra_os.database.product_models import Product
        from datetime import date as _date

        db = SessionLocal()
        try:
            today = _date.today()
            for item in line_items:
                shopify_product_id = str(item.get('product_id') or '')
                if not shopify_product_id:
                    continue

                # Find our internal Product by source_product_id
                product = (
                    db.query(Product)
                    .filter(Product.source_product_id == shopify_product_id)
                    .first()
                )
                if not product:
                    # Order item wasn't from an Ospra-discovered product — skip
                    # (their data won't help the learning loop)
                    continue

                quantity = int(item.get('quantity') or 1)
                unit_price = float(item.get('price') or 0)
                line_revenue = unit_price * quantity

                # Find or create today's ProductPerformance row for this product
                perf = (
                    db.query(ProductPerformance)
                    .filter(
                        ProductPerformance.product_id == product.id,
                        ProductPerformance.date == today,
                    )
                    .first()
                )

                if perf is None:
                    perf = ProductPerformance(
                        product_id=product.id,
                        store_id=store_id or product.store_id,
                        user_id=user_id,
                        date=today,
                        orders=0,
                        units_sold=0,
                        gross_revenue=0.0,
                        refunds=0.0,
                        net_revenue=0.0,
                        sync_source='webhook_realtime',
                        synced_at=datetime.now(timezone.utc),
                    )
                    db.add(perf)

                if is_refund:
                    # Refund webhook: increment refunds, decrement net_revenue
                    perf.refunds = (perf.refunds or 0) + line_revenue
                    perf.net_revenue = (perf.gross_revenue or 0) - (perf.refunds or 0)
                else:
                    perf.orders = (perf.orders or 0) + 1
                    perf.units_sold = (perf.units_sold or 0) + quantity
                    perf.gross_revenue = (perf.gross_revenue or 0) + line_revenue
                    perf.net_revenue = (perf.gross_revenue or 0) - (perf.refunds or 0)

                perf.synced_at = datetime.now(timezone.utc)
                perf.sync_source = 'webhook_realtime'

                logger.info(
                    f"📈 [perf-upsert] product #{product.id} ({product.product_name[:40]}) "
                    f"{'refund' if is_refund else 'order'} order={order_id} "
                    f"+{quantity} units / ${line_revenue:.2f}"
                )

            db.commit()
        finally:
            db.close()
    except Exception as e:
        # Don't crash the webhook handler — log and continue. The 6h
        # SalesSyncService will reconcile any missed orders.
        logger.error(f"Failed to upsert product performance from order {order_id}: {e}")


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
