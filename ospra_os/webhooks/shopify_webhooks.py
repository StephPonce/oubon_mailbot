"""
Shopify Webhook Handlers
========================

Processes order notifications and events from Shopify:
- orders/create: New order placed
- orders/paid: Order payment confirmed (triggers fulfillment + learning)
- orders/fulfilled: Order shipped
- orders/cancelled: Order cancelled

Author: Ospra Intelligence
"""

from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
import hmac
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/shopify", tags=["Shopify Webhooks"])


def verify_shopify_webhook(data: bytes, hmac_header: str) -> bool:
    """
    Verify webhook came from Shopify using HMAC.
    
    IMPORTANT: In production, always verify webhooks!
    """
    secret = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")

    if not secret:
        logger.warning("⚠️ No webhook secret configured - skipping verification (DEV MODE)")
        return True  # Allow in development

    # Calculate HMAC
    computed_hmac = hmac.new(
        secret.encode('utf-8'),
        data,
        hashlib.sha256
    ).digest()
    
    import base64
    computed_b64 = base64.b64encode(computed_hmac).decode('utf-8')

    # Compare with header
    return hmac.compare_digest(computed_b64, hmac_header)


# ============================================================================
# ORDER CREATED WEBHOOK
# ============================================================================

@router.post("/orders/create")
async def order_created(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    Handle new order creation from Shopify.
    
    This fires when an order is placed, but payment may not be confirmed yet.
    We log it but don't fulfill until /orders/paid webhook.
    """
    body = await request.body()

    if x_shopify_hmac_sha256:
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256):
            logger.error("❌ Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        order_data = json.loads(body)
    except Exception as e:
        logger.error(f"❌ Failed to parse webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    order_number = order_data.get('order_number', order_data.get('name', 'unknown'))
    logger.info(f"📦 New order received: #{order_number}")

    # Process in background (don't block webhook response)
    background_tasks.add_task(process_new_order, order_data)

    return {"status": "received", "order": order_number}


# ============================================================================
# ORDER PAID WEBHOOK (PRIMARY - TRIGGERS FULFILLMENT + LEARNING)
# ============================================================================

@router.post("/orders/paid")
async def order_paid(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    Handle order payment confirmation from Shopify.
    
    THIS IS THE KEY WEBHOOK:
    1. Triggers auto-fulfillment
    2. Records sale for self-learning
    3. Updates analytics
    """
    body = await request.body()

    if x_shopify_hmac_sha256:
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256):
            logger.error("❌ Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        order_data = json.loads(body)
    except Exception as e:
        logger.error(f"❌ Failed to parse webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    order_number = order_data.get('order_number', order_data.get('name', 'unknown'))
    total_price = order_data.get('total_price', '0')
    
    logger.info(f"💰 Order PAID: #{order_number} - ${total_price}")

    # Process in background
    background_tasks.add_task(process_paid_order, order_data)

    return {"status": "received", "order": order_number, "action": "fulfillment_triggered"}


# ============================================================================
# ORDER FULFILLED WEBHOOK
# ============================================================================

@router.post("/orders/fulfilled")
async def order_fulfilled(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    Handle order fulfillment confirmation from Shopify.
    
    This fires when tracking is added (either by us or manually).
    """
    body = await request.body()

    if x_shopify_hmac_sha256:
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256):
            logger.error("❌ Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        order_data = json.loads(body)
    except Exception as e:
        logger.error(f"❌ Failed to parse webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    order_number = order_data.get('order_number', order_data.get('name', 'unknown'))
    logger.info(f"✅ Order fulfilled: #{order_number}")

    return {"status": "received", "order": order_number}


# ============================================================================
# ORDER CANCELLED WEBHOOK
# ============================================================================

@router.post("/orders/cancelled")
async def order_cancelled(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    Handle order cancellation from Shopify.
    
    Updates learning data (negative signal).
    """
    body = await request.body()

    if x_shopify_hmac_sha256:
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256):
            logger.error("❌ Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        order_data = json.loads(body)
    except Exception as e:
        logger.error(f"❌ Failed to parse webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    order_number = order_data.get('order_number', order_data.get('name', 'unknown'))
    logger.info(f"❌ Order cancelled: #{order_number}")

    # Record cancellation for learning
    await record_cancellation_for_learning(order_data)

    return {"status": "received", "order": order_number}


# ============================================================================
# BACKGROUND PROCESSING FUNCTIONS
# ============================================================================

async def process_new_order(order_data: dict):
    """
    Process new order (background task).
    
    - Saves order to database
    - Creates notification
    """
    try:
        shopify_order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number', order_data.get('name', ''))
        
        customer = order_data.get('customer', {})
        customer_email = customer.get('email', order_data.get('email', ''))
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        
        line_items = order_data.get('line_items', [])
        total_price = float(order_data.get('total_price', 0))
        
        logger.info(f"  Processing order #{order_number}: {len(line_items)} items, ${total_price}")
        
        # Create notification
        try:
            from ospra_os.database.product_history import ProductHistoryDB
            db = ProductHistoryDB()
            
            product_names = [item.get('name', 'Product') for item in line_items[:3]]
            products_str = ", ".join(product_names)
            if len(line_items) > 3:
                products_str += f" +{len(line_items) - 3} more"
            
            db.create_notification(
                notification_type='order',
                title='New Order Received',
                message=f'Order #{order_number}: {products_str} - ${total_price:.2f}',
                severity='success',
                metadata={
                    'order_id': shopify_order_id,
                    'order_number': order_number,
                    'customer_email': customer_email,
                    'total_price': total_price
                }
            )
        except Exception as e:
            logger.warning(f"  Failed to create notification: {e}")
        
        logger.info(f"  ✅ Order #{order_number} processed")
        
    except Exception as e:
        logger.error(f"❌ Failed to process order: {e}")
        import traceback
        traceback.print_exc()


async def process_paid_order(order_data: dict):
    """
    Process paid order (background task).
    
    THIS IS THE MAIN EVENT:
    1. Record sale for self-learning
    2. Trigger auto-fulfillment
    """
    try:
        shopify_order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number', order_data.get('name', ''))
        
        logger.info(f"  Processing PAID order #{order_number}")
        
        # =================================================================
        # STEP 1: RECORD FOR SELF-LEARNING
        # =================================================================
        await record_sale_for_learning(order_data)
        
        # =================================================================
        # STEP 2: TRIGGER AUTO-FULFILLMENT
        # =================================================================
        await trigger_auto_fulfillment(order_data)
        
        logger.info(f"  ✅ Paid order #{order_number} fully processed")
        
    except Exception as e:
        logger.error(f"❌ Failed to process paid order: {e}")
        import traceback
        traceback.print_exc()


async def record_sale_for_learning(order_data: dict):
    """
    Record sale data for the self-learning system.
    
    This is the CRITICAL connection between sales and AI learning!
    """
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database import AILearningEvent
        
        shopify_order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number', order_data.get('name', ''))
        total_price = float(order_data.get('total_price', 0))
        currency = order_data.get('currency', 'USD')
        
        line_items = order_data.get('line_items', [])
        
        db = SessionLocal()
        try:
            for item in line_items:
                product_id = str(item.get('product_id', ''))
                product_name = item.get('name', 'Unknown')
                quantity = item.get('quantity', 1)
                price = float(item.get('price', 0))
                item_revenue = price * quantity
                
                # Detect niche from product info
                niche = detect_product_niche(item, order_data)
                
                # Detect price point
                price_point = detect_price_point(price)
                
                # Create learning event
                event = AILearningEvent(
                    user_id=1,  # TODO: Map from store to user
                    event_type="sale",
                    product_id=product_id,
                    details={
                        "product_name": product_name,
                        "niche": niche,
                        "price": price,
                        "price_point": price_point,
                        "quantity": quantity,
                        "revenue": item_revenue,
                        "order_id": shopify_order_id,
                        "order_number": order_number,
                        "currency": currency,
                        "source": "shopify_paid_webhook",
                        "sale_timestamp": datetime.utcnow().isoformat()
                    },
                    timestamp=datetime.utcnow()
                )
                db.add(event)
                
                logger.info(f"    📊 Learning event: {product_name} ({niche}) - ${item_revenue}")
            
            db.commit()
            logger.info(f"  ✅ Recorded {len(line_items)} learning events")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"  ❌ Failed to record learning: {e}")


async def trigger_auto_fulfillment(order_data: dict):
    """
    Trigger automatic order fulfillment.
    
    Uses the AutoFulfillmentEngine to place orders with suppliers.
    """
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
            # Still queue for manual fulfillment
            logger.info("  Auto-fulfillment disabled - queueing for manual")
        
        # Import and run fulfillment engine
        from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
        
        engine = get_fulfillment_engine()
        result = await engine.process_new_order(order_data)
        
        if result.get('success'):
            logger.info(f"  ✅ Fulfillment processed: {result.get('items_successful')}/{result.get('items_processed')} items")
        else:
            logger.warning(f"  ⚠️ Fulfillment issues: {result.get('error', 'Unknown')}")
            
    except Exception as e:
        logger.error(f"  ❌ Failed to trigger fulfillment: {e}")


async def record_cancellation_for_learning(order_data: dict):
    """
    Record order cancellation for learning (negative signal).
    """
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database import AILearningEvent
        
        shopify_order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number', order_data.get('name', ''))
        
        line_items = order_data.get('line_items', [])
        
        db = SessionLocal()
        try:
            for item in line_items:
                product_id = str(item.get('product_id', ''))
                product_name = item.get('name', 'Unknown')
                
                # Create cancellation event (negative signal)
                event = AILearningEvent(
                    user_id=1,
                    event_type="cancellation",
                    product_id=product_id,
                    details={
                        "product_name": product_name,
                        "order_id": shopify_order_id,
                        "order_number": order_number,
                        "cancel_reason": order_data.get('cancel_reason', 'unknown'),
                        "source": "shopify_cancelled_webhook"
                    },
                    timestamp=datetime.utcnow()
                )
                db.add(event)
            
            db.commit()
            logger.info(f"  📊 Recorded cancellation for learning")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"  ❌ Failed to record cancellation: {e}")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def detect_product_niche(item: dict, order_data: dict) -> str:
    """
    Detect product niche from item data.
    
    Uses product type, tags, and name to determine niche.
    """
    # Try to get from vendor or product type
    vendor = item.get('vendor', '').lower()
    product_type = item.get('product_type', '').lower()
    name = item.get('name', '').lower()
    
    # Get tags if available (from full product data)
    tags = item.get('tags', '').lower() if isinstance(item.get('tags'), str) else ''
    
    combined = f"{vendor} {product_type} {name} {tags}"
    
    # Niche detection rules
    niche_keywords = {
        "smart_home": ["smart", "wifi", "alexa", "google home", "iot", "automation", "sensor"],
        "fitness": ["fitness", "gym", "workout", "exercise", "yoga", "sport"],
        "kitchen": ["kitchen", "cooking", "chef", "food", "utensil", "cookware"],
        "tech": ["tech", "gadget", "electronic", "usb", "charger", "cable"],
        "beauty": ["beauty", "skincare", "makeup", "cosmetic", "hair"],
        "home_office": ["office", "desk", "organizer", "work from home", "laptop"],
        "outdoor": ["outdoor", "camping", "hiking", "garden", "patio"],
        "pet": ["pet", "dog", "cat", "animal"]
    }
    
    for niche, keywords in niche_keywords.items():
        for keyword in keywords:
            if keyword in combined:
                return niche
    
    return "general"


def detect_price_point(price: float) -> str:
    """
    Categorize price into price point buckets.
    """
    if price < 20:
        return "under_20"
    elif price < 50:
        return "20_to_50"
    elif price < 100:
        return "50_to_100"
    else:
        return "over_100"


# ============================================================================
# WEBHOOK REGISTRATION HELPER
# ============================================================================

async def register_shopify_webhooks():
    """
    Register all required webhooks with Shopify.
    
    Call this once during setup to ensure webhooks are configured.
    """
    import httpx
    
    store_name = os.getenv("SHOPIFY_STORE_NAME")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
    webhook_url_base = os.getenv("WEBHOOK_URL_BASE", "https://your-domain.com")
    
    if not store_name or not access_token:
        logger.error("Shopify credentials not configured")
        return {"success": False, "error": "Not configured"}
    
    base_url = f"https://{store_name}.myshopify.com/admin/api/2024-10"
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    webhooks_to_register = [
        {"topic": "orders/create", "address": f"{webhook_url_base}/webhooks/shopify/orders/create"},
        {"topic": "orders/paid", "address": f"{webhook_url_base}/webhooks/shopify/orders/paid"},
        {"topic": "orders/fulfilled", "address": f"{webhook_url_base}/webhooks/shopify/orders/fulfilled"},
        {"topic": "orders/cancelled", "address": f"{webhook_url_base}/webhooks/shopify/orders/cancelled"},
    ]
    
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for webhook in webhooks_to_register:
            try:
                response = await client.post(
                    f"{base_url}/webhooks.json",
                    headers=headers,
                    json={
                        "webhook": {
                            "topic": webhook["topic"],
                            "address": webhook["address"],
                            "format": "json"
                        }
                    }
                )
                
                if response.status_code in [200, 201]:
                    results.append({"topic": webhook["topic"], "status": "registered"})
                    logger.info(f"✅ Registered webhook: {webhook['topic']}")
                elif response.status_code == 422:
                    # Already exists
                    results.append({"topic": webhook["topic"], "status": "already_exists"})
                else:
                    results.append({"topic": webhook["topic"], "status": "failed", "error": response.text})
                    logger.error(f"❌ Failed to register {webhook['topic']}: {response.text}")
                    
            except Exception as e:
                results.append({"topic": webhook["topic"], "status": "error", "error": str(e)})
    
    return {"success": True, "webhooks": results}


@router.post("/register")
async def register_webhooks():
    """
    API endpoint to register Shopify webhooks.
    
    Call this once after deployment to set up webhooks.
    """
    result = await register_shopify_webhooks()
    return result


@router.get("/list")
async def list_registered_webhooks():
    """
    List all registered Shopify webhooks.
    """
    import httpx
    
    store_name = os.getenv("SHOPIFY_STORE_NAME")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
    
    if not store_name or not access_token:
        return {"success": False, "error": "Not configured"}
    
    base_url = f"https://{store_name}.myshopify.com/admin/api/2024-10"
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{base_url}/webhooks.json", headers=headers)
        
        if response.status_code == 200:
            webhooks = response.json().get('webhooks', [])
            return {
                "success": True,
                "count": len(webhooks),
                "webhooks": [
                    {
                        "id": w['id'],
                        "topic": w['topic'],
                        "address": w['address'],
                        "created_at": w.get('created_at')
                    }
                    for w in webhooks
                ]
            }
        
        return {"success": False, "error": response.text}
