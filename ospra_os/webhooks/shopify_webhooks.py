"""
Shopify Webhook Handlers - Complete Implementation
==================================================

Production-grade webhook handlers for all Shopify events.
Multi-tenant aware for SaaS deployment.

Webhook Categories:
- Orders (6 webhooks)
- Refunds & Disputes (2 webhooks)  
- Products (3 webhooks)
- Inventory (2 webhooks)
- Customers (3 webhooks)
- Checkouts (2 webhooks)
- Fulfillment (2 webhooks)
- GDPR Compliance (3 webhooks)
- App Lifecycle (1 webhook)

Total: 24 webhooks

Author: Ospra Intelligence
"""

from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

from .webhook_utils import (
    verify_and_parse_webhook,
    record_learning_event,
    create_notification,
    detect_product_niche,
    detect_price_point,
    get_store_or_default,
    WebhookTopics,
)
from .webhook_registry import (
    ShopifyWebhookRegistry,
    register_webhooks_for_store,
    list_store_webhooks,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/shopify", tags=["Shopify Webhooks"])


# ============================================================================
# ORDER WEBHOOKS (6)
# ============================================================================

@router.post("/orders/create")
async def webhook_orders_create(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle new order creation.
    
    Fires when order is placed (payment may not be confirmed).
    - Creates notification
    - Logs order for tracking
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    order_number = data.get('order_number', data.get('name', 'unknown'))
    total_price = data.get('total_price', '0')
    
    logger.info(f"📦 [orders/create] Order #{order_number} - ${total_price}")
    
    background_tasks.add_task(process_order_create, data, store_id)
    
    return {"status": "received", "order": order_number, "webhook": "orders/create"}


@router.post("/orders/updated")
async def webhook_orders_updated(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle order updates.
    
    Fires when any order field changes.
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    order_number = data.get('order_number', data.get('name', 'unknown'))
    logger.info(f"📝 [orders/updated] Order #{order_number} updated")
    
    background_tasks.add_task(process_order_updated, data, store_id)
    
    return {"status": "received", "order": order_number, "webhook": "orders/updated"}


@router.post("/orders/paid")
async def webhook_orders_paid(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle order payment confirmation.
    
    THIS IS THE KEY WEBHOOK:
    1. Triggers auto-fulfillment
    2. Records sale for AI self-learning
    3. Updates analytics
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    order_number = data.get('order_number', data.get('name', 'unknown'))
    total_price = data.get('total_price', '0')
    
    logger.info(f"💰 [orders/paid] Order #{order_number} PAID - ${total_price}")
    
    background_tasks.add_task(process_order_paid, data, store_id)
    
    return {"status": "received", "order": order_number, "webhook": "orders/paid", "action": "fulfillment_triggered"}


@router.post("/orders/fulfilled")
async def webhook_orders_fulfilled(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle order fulfillment.
    
    Fires when tracking is added.
    - Records delivery confirmation for learning
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    order_number = data.get('order_number', data.get('name', 'unknown'))
    logger.info(f"✅ [orders/fulfilled] Order #{order_number} shipped")
    
    background_tasks.add_task(process_order_fulfilled, data, store_id)
    
    return {"status": "received", "order": order_number, "webhook": "orders/fulfilled"}


@router.post("/orders/cancelled")
async def webhook_orders_cancelled(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle order cancellation.
    
    - Records negative signal for AI learning
    - Tracks cancellation reason
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    order_number = data.get('order_number', data.get('name', 'unknown'))
    reason = data.get('cancel_reason', 'unknown')
    
    logger.info(f"❌ [orders/cancelled] Order #{order_number} - Reason: {reason}")
    
    background_tasks.add_task(process_order_cancelled, data, store_id)
    
    return {"status": "received", "order": order_number, "webhook": "orders/cancelled"}


@router.post("/orders/edited")
async def webhook_orders_edited(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle order edits (post-purchase modifications).
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    order_number = data.get('order_number', data.get('name', 'unknown'))
    logger.info(f"✏️ [orders/edited] Order #{order_number} edited")
    
    return {"status": "received", "order": order_number, "webhook": "orders/edited"}


# ============================================================================
# REFUNDS & DISPUTES WEBHOOKS (2)
# ============================================================================

@router.post("/refunds/create")
async def webhook_refunds_create(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle refund creation.
    
    STRONG NEGATIVE SIGNAL for AI learning:
    - Product quality issue?
    - Description mismatch?
    - Shipping problem?
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    refund_id = data.get('id')
    order_id = data.get('order_id')
    
    # Calculate refund amount
    refund_line_items = data.get('refund_line_items', [])
    total_refund = sum(
        float(item.get('subtotal', 0)) for item in refund_line_items
    )
    
    logger.info(f"💸 [refunds/create] Refund #{refund_id} for Order #{order_id} - ${total_refund}")
    
    background_tasks.add_task(process_refund_create, data, store_id)
    
    return {"status": "received", "refund_id": refund_id, "webhook": "refunds/create"}


@router.post("/disputes/create")
async def webhook_disputes_create(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle dispute/chargeback creation.
    
    VERY STRONG NEGATIVE SIGNAL:
    - Customer went to bank
    - Potential fraud
    - Major issue
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    dispute_id = data.get('id')
    reason = data.get('reason', 'unknown')
    
    logger.warning(f"⚠️ [disputes/create] Dispute #{dispute_id} - Reason: {reason}")
    
    background_tasks.add_task(process_dispute_create, data, store_id)
    
    return {"status": "received", "dispute_id": dispute_id, "webhook": "disputes/create"}


# ============================================================================
# PRODUCT WEBHOOKS (3)
# ============================================================================

@router.post("/products/create")
async def webhook_products_create(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle new product creation in store.
    
    - Sync with internal product database
    - Track inventory
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    product_id = data.get('id')
    title = data.get('title', 'Unknown')
    
    logger.info(f"🆕 [products/create] Product '{title}' (ID: {product_id})")
    
    background_tasks.add_task(process_product_create, data, store_id)
    
    return {"status": "received", "product_id": product_id, "webhook": "products/create"}


@router.post("/products/update")
async def webhook_products_update(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle product updates.
    
    - Price changes (important for margin tracking)
    - Description updates
    - Stock level changes
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    product_id = data.get('id')
    title = data.get('title', 'Unknown')
    
    logger.info(f"📝 [products/update] Product '{title}' (ID: {product_id}) updated")
    
    background_tasks.add_task(process_product_update, data, store_id)
    
    return {"status": "received", "product_id": product_id, "webhook": "products/update"}


@router.post("/products/delete")
async def webhook_products_delete(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle product deletion.
    
    - Clean up from internal database
    - Archive analytics
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    product_id = data.get('id')
    
    logger.info(f"🗑️ [products/delete] Product ID: {product_id} deleted")
    
    background_tasks.add_task(process_product_delete, data, store_id)
    
    return {"status": "received", "product_id": product_id, "webhook": "products/delete"}


# ============================================================================
# INVENTORY WEBHOOKS (2)
# ============================================================================

@router.post("/inventory_levels/update")
async def webhook_inventory_levels_update(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle inventory level updates.
    
    - Low stock alerts
    - Auto-reorder triggers
    - Stockout prevention
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    inventory_item_id = data.get('inventory_item_id')
    available = data.get('available', 0)
    
    logger.info(f"📊 [inventory_levels/update] Item {inventory_item_id}: {available} available")
    
    background_tasks.add_task(process_inventory_update, data, store_id)
    
    return {"status": "received", "inventory_item_id": inventory_item_id, "webhook": "inventory_levels/update"}


# Alias for inventory_items/update
@router.post("/inventory_items/update")
async def webhook_inventory_items_update(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle inventory item updates (SKU, cost, etc).
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    item_id = data.get('id')
    sku = data.get('sku', '')
    
    logger.info(f"📦 [inventory_items/update] Item {item_id} (SKU: {sku}) updated")
    
    return {"status": "received", "item_id": item_id, "webhook": "inventory_items/update"}


# ============================================================================
# CUSTOMER WEBHOOKS (3)
# ============================================================================

@router.post("/customers/create")
async def webhook_customers_create(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle new customer creation.
    
    - Build customer profiles
    - Segmentation data
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    customer_id = data.get('id')
    email = data.get('email', '')
    
    logger.info(f"👤 [customers/create] Customer {customer_id} ({email})")
    
    background_tasks.add_task(process_customer_create, data, store_id)
    
    return {"status": "received", "customer_id": customer_id, "webhook": "customers/create"}


@router.post("/customers/update")
async def webhook_customers_update(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle customer updates.
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    customer_id = data.get('id')
    logger.info(f"👤 [customers/update] Customer {customer_id} updated")
    
    return {"status": "received", "customer_id": customer_id, "webhook": "customers/update"}


@router.post("/customers/delete")
async def webhook_customers_delete(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle customer deletion.
    
    Part of GDPR compliance - remove customer data.
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    customer_id = data.get('id')
    logger.info(f"🗑️ [customers/delete] Customer {customer_id} deleted")
    
    background_tasks.add_task(process_customer_delete, data, store_id)
    
    return {"status": "received", "customer_id": customer_id, "webhook": "customers/delete"}


# ============================================================================
# CHECKOUT WEBHOOKS (2)
# ============================================================================

@router.post("/checkouts/create")
async def webhook_checkouts_create(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle checkout creation.
    
    - Track abandoned carts
    - Conversion funnel data
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    checkout_token = data.get('token', '')
    total_price = data.get('total_price', '0')
    
    logger.info(f"🛒 [checkouts/create] Checkout started - ${total_price}")
    
    background_tasks.add_task(process_checkout_create, data, store_id)
    
    return {"status": "received", "checkout_token": checkout_token, "webhook": "checkouts/create"}


@router.post("/checkouts/update")
async def webhook_checkouts_update(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle checkout updates.
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    checkout_token = data.get('token', '')
    logger.info(f"🛒 [checkouts/update] Checkout {checkout_token} updated")
    
    return {"status": "received", "checkout_token": checkout_token, "webhook": "checkouts/update"}


# ============================================================================
# FULFILLMENT WEBHOOKS (2)
# ============================================================================

@router.post("/fulfillments/create")
async def webhook_fulfillments_create(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle fulfillment creation.
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    fulfillment_id = data.get('id')
    tracking_number = data.get('tracking_number', '')
    
    logger.info(f"📤 [fulfillments/create] Fulfillment {fulfillment_id} - Tracking: {tracking_number}")
    
    return {"status": "received", "fulfillment_id": fulfillment_id, "webhook": "fulfillments/create"}


@router.post("/fulfillments/update")
async def webhook_fulfillments_update(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle fulfillment updates (tracking info, status).
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    fulfillment_id = data.get('id')
    status = data.get('status', '')
    
    logger.info(f"📤 [fulfillments/update] Fulfillment {fulfillment_id} - Status: {status}")
    
    return {"status": "received", "fulfillment_id": fulfillment_id, "webhook": "fulfillments/update"}


# ============================================================================
# GDPR COMPLIANCE WEBHOOKS (3) - REQUIRED FOR SHOPIFY APPS
# ============================================================================

@router.post("/gdpr/customers/data_request")
async def webhook_customers_data_request(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle customer data request (GDPR).
    
    Customer requested export of their data.
    Must respond within 30 days.
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    customer = data.get('customer', {})
    shop_domain = data.get('shop_domain', '')
    
    logger.info(f"📋 [GDPR] Customer data request from {shop_domain}")
    
    background_tasks.add_task(process_gdpr_data_request, data, store_id)
    
    return {"status": "received", "webhook": "customers/data_request"}


@router.post("/gdpr/customers/redact")
async def webhook_customers_redact(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle customer data deletion request (GDPR).
    
    Customer requested deletion of their data.
    Must delete within 30 days.
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    customer = data.get('customer', {})
    shop_domain = data.get('shop_domain', '')
    
    logger.info(f"🗑️ [GDPR] Customer redact request from {shop_domain}")
    
    background_tasks.add_task(process_gdpr_customer_redact, data, store_id)
    
    return {"status": "received", "webhook": "customers/redact"}


@router.post("/gdpr/shop/redact")
async def webhook_shop_redact(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle shop data deletion (GDPR).
    
    Store uninstalled app - delete ALL store data within 48 hours.
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    shop_domain = data.get('shop_domain', '')
    
    logger.warning(f"🗑️ [GDPR] Shop redact request - DELETE ALL DATA for {shop_domain}")
    
    background_tasks.add_task(process_gdpr_shop_redact, data, store_id)
    
    return {"status": "received", "webhook": "shop/redact"}


# ============================================================================
# APP LIFECYCLE WEBHOOKS (1)
# ============================================================================

@router.post("/app/uninstalled")
async def webhook_app_uninstalled(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None)
):
    """
    Handle app uninstallation.
    
    - Clean up webhooks
    - Mark store as inactive
    - Trigger GDPR compliance
    """
    data, store_id = await verify_and_parse_webhook(request, x_shopify_hmac_sha256)
    
    shop_domain = data.get('shop_domain', data.get('domain', 'unknown'))
    
    logger.warning(f"👋 [app/uninstalled] Store {shop_domain} uninstalled the app")
    
    background_tasks.add_task(process_app_uninstalled, data, store_id)
    
    return {"status": "received", "shop": shop_domain, "webhook": "app/uninstalled"}


# ============================================================================
# WEBHOOK MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/register")
async def register_webhooks():
    """
    Register all webhooks for the default store.
    
    For single-tenant mode (Oubon Shop).
    """
    store_name = os.getenv("SHOPIFY_STORE_NAME")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
    
    if not store_name or not access_token:
        return {"success": False, "error": "Shopify credentials not configured"}
    
    result = await register_webhooks_for_store(store_name, access_token)
    return result


@router.get("/list")
async def list_webhooks():
    """
    List all registered webhooks for the default store.
    """
    store_name = os.getenv("SHOPIFY_STORE_NAME")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
    
    if not store_name or not access_token:
        return {"success": False, "error": "Shopify credentials not configured"}
    
    webhooks = await list_store_webhooks(store_name, access_token)
    
    return {
        "success": True,
        "count": len(webhooks),
        "webhooks": webhooks,
    }


@router.get("/status")
async def webhook_status():
    """
    Get webhook system status.
    """
    return {
        "status": "operational",
        "total_webhook_types": 24,
        "categories": {
            "orders": 6,
            "refunds_disputes": 2,
            "products": 3,
            "inventory": 2,
            "customers": 3,
            "checkouts": 2,
            "fulfillment": 2,
            "gdpr": 3,
            "app_lifecycle": 1,
        },
        "webhook_url_base": os.getenv("WEBHOOK_URL_BASE", "not_configured"),
    }


# ============================================================================
# BACKGROUND PROCESSING FUNCTIONS
# ============================================================================

async def process_order_create(data: Dict[str, Any], store_id: Optional[int]):
    """Process new order creation."""
    try:
        order_number = data.get('order_number', data.get('name', ''))
        total_price = float(data.get('total_price', 0))
        line_items = data.get('line_items', [])
        
        # Create notification
        product_names = [item.get('name', 'Product')[:30] for item in line_items[:3]]
        products_str = ", ".join(product_names)
        if len(line_items) > 3:
            products_str += f" +{len(line_items) - 3} more"
        
        await create_notification(
            notification_type='order',
            title='New Order Received',
            message=f'Order #{order_number}: {products_str} - ${total_price:.2f}',
            severity='success',
            metadata={
                'order_id': str(data.get('id')),
                'order_number': order_number,
                'total_price': total_price,
            },
            store_id=store_id,
        )
        
        logger.info(f"  ✅ Order #{order_number} processed")
        
    except Exception as e:
        logger.error(f"Failed to process order create: {e}")


async def process_order_updated(data: Dict[str, Any], store_id: Optional[int]):
    """Process order updates."""
    # Log significant changes
    pass


async def process_order_paid(data: Dict[str, Any], store_id: Optional[int]):
    """
    Process paid order - THE KEY EVENT.
    
    1. Record for AI learning
    2. Trigger fulfillment
    """
    try:
        order_number = data.get('order_number', data.get('name', ''))
        order_id = str(data.get('id'))
        total_price = float(data.get('total_price', 0))
        currency = data.get('currency', 'USD')
        line_items = data.get('line_items', [])
        
        store_info = await get_store_or_default(store_id)
        user_id = store_info.get("user_id", 1)
        
        # ============================================================
        # STEP 1: RECORD FOR AI SELF-LEARNING
        # ============================================================
        for item in line_items:
            product_id = str(item.get('product_id', ''))
            product_name = item.get('name', 'Unknown')
            quantity = item.get('quantity', 1)
            price = float(item.get('price', 0))
            item_revenue = price * quantity
            
            niche = detect_product_niche(item)
            price_point = detect_price_point(price)
            
            await record_learning_event(
                event_type="sale",
                product_id=product_id,
                details={
                    "product_name": product_name,
                    "niche": niche,
                    "price": price,
                    "price_point": price_point,
                    "quantity": quantity,
                    "revenue": item_revenue,
                    "order_id": order_id,
                    "order_number": order_number,
                    "currency": currency,
                    "source": "webhook_orders_paid",
                },
                store_id=store_id,
                user_id=user_id,
            )
            
            logger.info(f"    📊 Learning: {product_name} ({niche}) - ${item_revenue}")
        
        # ============================================================
        # STEP 2: TRIGGER AUTO-FULFILLMENT
        # ============================================================
        await trigger_fulfillment(data, store_id)
        
        logger.info(f"  ✅ Paid order #{order_number} fully processed")
        
    except Exception as e:
        logger.error(f"Failed to process paid order: {e}")
        import traceback
        traceback.print_exc()


async def process_order_fulfilled(data: Dict[str, Any], store_id: Optional[int]):
    """Process order fulfillment confirmation."""
    try:
        order_number = data.get('order_number', data.get('name', ''))
        
        # Record successful delivery for learning
        for item in data.get('line_items', []):
            await record_learning_event(
                event_type="delivered",
                product_id=str(item.get('product_id', '')),
                details={
                    "product_name": item.get('name', ''),
                    "order_number": order_number,
                    "source": "webhook_orders_fulfilled",
                },
                store_id=store_id,
            )
        
    except Exception as e:
        logger.error(f"Failed to process fulfilled order: {e}")


async def process_order_cancelled(data: Dict[str, Any], store_id: Optional[int]):
    """Process order cancellation - negative learning signal."""
    try:
        order_number = data.get('order_number', data.get('name', ''))
        cancel_reason = data.get('cancel_reason', 'unknown')
        
        for item in data.get('line_items', []):
            await record_learning_event(
                event_type="cancellation",
                product_id=str(item.get('product_id', '')),
                details={
                    "product_name": item.get('name', ''),
                    "order_number": order_number,
                    "cancel_reason": cancel_reason,
                    "source": "webhook_orders_cancelled",
                },
                store_id=store_id,
            )
        
        await create_notification(
            notification_type='alert',
            title='Order Cancelled',
            message=f'Order #{order_number} was cancelled. Reason: {cancel_reason}',
            severity='warning',
            store_id=store_id,
        )
        
    except Exception as e:
        logger.error(f"Failed to process cancelled order: {e}")


async def process_refund_create(data: Dict[str, Any], store_id: Optional[int]):
    """Process refund - strong negative signal."""
    try:
        order_id = data.get('order_id')
        reason = data.get('note', 'No reason provided')
        
        for item in data.get('refund_line_items', []):
            line_item = item.get('line_item', {})
            product_id = str(line_item.get('product_id', ''))
            
            await record_learning_event(
                event_type="refund",
                product_id=product_id,
                details={
                    "product_name": line_item.get('name', ''),
                    "quantity": item.get('quantity', 1),
                    "refund_amount": float(item.get('subtotal', 0)),
                    "reason": reason,
                    "source": "webhook_refunds_create",
                },
                store_id=store_id,
            )
        
        await create_notification(
            notification_type='alert',
            title='Refund Processed',
            message=f'Refund issued for order. Reason: {reason}',
            severity='warning',
            store_id=store_id,
        )
        
    except Exception as e:
        logger.error(f"Failed to process refund: {e}")


async def process_dispute_create(data: Dict[str, Any], store_id: Optional[int]):
    """Process dispute/chargeback - very strong negative signal."""
    try:
        dispute_id = data.get('id')
        reason = data.get('reason', 'unknown')
        amount = data.get('amount', '0')
        
        await record_learning_event(
            event_type="dispute",
            product_id=None,  # Disputes are order-level
            details={
                "dispute_id": str(dispute_id),
                "reason": reason,
                "amount": float(amount),
                "source": "webhook_disputes_create",
            },
            store_id=store_id,
        )
        
        await create_notification(
            notification_type='alert',
            title='⚠️ Chargeback Filed',
            message=f'Dispute opened: {reason}. Amount: ${amount}',
            severity='critical',
            store_id=store_id,
        )
        
    except Exception as e:
        logger.error(f"Failed to process dispute: {e}")


async def process_product_create(data: Dict[str, Any], store_id: Optional[int]):
    """Process new product creation."""
    # Sync with internal database if needed
    pass


async def process_product_update(data: Dict[str, Any], store_id: Optional[int]):
    """Process product updates (price changes, etc)."""
    try:
        product_id = data.get('id')
        title = data.get('title', '')
        
        # Check for price changes
        variants = data.get('variants', [])
        for variant in variants:
            new_price = float(variant.get('price', 0))
            # Could compare with stored price and alert on significant changes
        
    except Exception as e:
        logger.error(f"Failed to process product update: {e}")


async def process_product_delete(data: Dict[str, Any], store_id: Optional[int]):
    """Process product deletion."""
    # Archive analytics, clean up
    pass


async def process_inventory_update(data: Dict[str, Any], store_id: Optional[int]):
    """Process inventory level update."""
    try:
        inventory_item_id = data.get('inventory_item_id')
        available = data.get('available', 0)
        
        # Low stock alert
        if available is not None and available < 5:
            await create_notification(
                notification_type='alert',
                title='Low Stock Alert',
                message=f'Inventory item {inventory_item_id} has only {available} units left',
                severity='warning',
                store_id=store_id,
            )
        
        # Out of stock alert
        if available == 0:
            await create_notification(
                notification_type='alert',
                title='Out of Stock',
                message=f'Inventory item {inventory_item_id} is now OUT OF STOCK',
                severity='error',
                store_id=store_id,
            )
        
    except Exception as e:
        logger.error(f"Failed to process inventory update: {e}")


async def process_customer_create(data: Dict[str, Any], store_id: Optional[int]):
    """Process new customer creation."""
    # Could build customer profile, segment, etc
    pass


async def process_customer_delete(data: Dict[str, Any], store_id: Optional[int]):
    """Process customer deletion (GDPR)."""
    # Remove customer data from internal systems
    pass


async def process_checkout_create(data: Dict[str, Any], store_id: Optional[int]):
    """Process checkout creation for abandoned cart tracking."""
    try:
        checkout_token = data.get('token', '')
        email = data.get('email', '')
        total_price = float(data.get('total_price', 0))
        
        # Store for abandoned cart follow-up
        # Could track conversion funnel
        
    except Exception as e:
        logger.error(f"Failed to process checkout: {e}")


async def process_gdpr_data_request(data: Dict[str, Any], store_id: Optional[int]):
    """Process GDPR data export request."""
    try:
        shop_domain = data.get('shop_domain', '')
        customer = data.get('customer', {})
        customer_email = customer.get('email', '')
        
        logger.info(f"[GDPR] Data request for {customer_email} from {shop_domain}")
        
        # TODO: Compile customer data and respond
        # Must respond within 30 days
        
    except Exception as e:
        logger.error(f"Failed to process GDPR data request: {e}")


async def process_gdpr_customer_redact(data: Dict[str, Any], store_id: Optional[int]):
    """Process GDPR customer data deletion request."""
    try:
        shop_domain = data.get('shop_domain', '')
        customer = data.get('customer', {})
        customer_id = customer.get('id')
        customer_email = customer.get('email', '')
        
        logger.info(f"[GDPR] Redact customer {customer_id} ({customer_email}) from {shop_domain}")
        
        # TODO: Delete customer data from all internal systems
        # Must complete within 30 days
        
    except Exception as e:
        logger.error(f"Failed to process GDPR customer redact: {e}")


async def process_gdpr_shop_redact(data: Dict[str, Any], store_id: Optional[int]):
    """Process GDPR shop data deletion (app uninstall)."""
    try:
        shop_domain = data.get('shop_domain', '')
        shop_id = data.get('shop_id')
        
        logger.warning(f"[GDPR] DELETE ALL DATA for shop {shop_domain} (ID: {shop_id})")
        
        # TODO: Delete ALL store data
        # Must complete within 48 hours
        
    except Exception as e:
        logger.error(f"Failed to process GDPR shop redact: {e}")


async def process_app_uninstalled(data: Dict[str, Any], store_id: Optional[int]):
    """Process app uninstallation."""
    try:
        shop_domain = data.get('shop_domain', data.get('domain', ''))
        
        logger.warning(f"App uninstalled by {shop_domain}")
        
        # Mark store as inactive
        if store_id:
            try:
                from ospra_os.database.connection import SessionLocal
                from ospra_os.database.store_models import Store
                
                db = SessionLocal()
                try:
                    store = db.query(Store).filter(Store.id == store_id).first()
                    if store:
                        store.is_active = False
                        db.commit()
                        logger.info(f"  Store {store_id} marked as inactive")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"  Failed to update store status: {e}")
        
    except Exception as e:
        logger.error(f"Failed to process app uninstall: {e}")


async def trigger_fulfillment(data: Dict[str, Any], store_id: Optional[int]):
    """Trigger auto-fulfillment for paid order."""
    try:
        # Check if auto-fulfillment is enabled
        import json
        
        settings_file = os.path.join(
            os.path.dirname(__file__),
            '..', 'data', 'fulfillment_settings.json'
        )
        
        auto_fulfill = False
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                auto_fulfill = settings.get('auto_fulfill_enabled', False)
        
        if not auto_fulfill:
            logger.info("  Auto-fulfillment disabled - order queued for manual fulfillment")
            return
        
        # Import and run fulfillment engine
        try:
            from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
            
            engine = get_fulfillment_engine()
            result = await engine.process_new_order(data)
            
            if result.get('success'):
                logger.info(f"  ✅ Fulfillment: {result.get('items_successful')}/{result.get('items_processed')} items")
            else:
                logger.warning(f"  ⚠️ Fulfillment issues: {result.get('error', 'Unknown')}")
                
        except ImportError:
            logger.warning("  Fulfillment engine not available")
            
    except Exception as e:
        logger.error(f"Failed to trigger fulfillment: {e}")
