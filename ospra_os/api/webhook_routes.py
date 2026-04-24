"""
WEBHOOK API ROUTES
==================

Secure webhook endpoints for external services:
- Shopify order/product webhooks
- LemonSqueezy subscription webhooks
- CJ Dropshipping inventory updates
- AliExpress notifications

All webhooks are verified using HMAC signatures.

Author: OspraOS
Date: December 2024
"""

import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Header
from pydantic import BaseModel

from ospra_os.security.webhook_verification import (
    verify_shopify_webhook,
    verify_lemonsqueezy_webhook,
    webhook_rate_limit,
    get_webhook_status,
)
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


# =============================================================================
# WEBHOOK STATUS
# =============================================================================

@router.get("/status")
async def webhook_configuration_status(current_user: User = Depends(get_current_user)):
    """
    Get webhook configuration status.

    Shows which providers have secrets configured.

    Requires authentication.
    """
    return get_webhook_status()


# =============================================================================
# SHOPIFY WEBHOOKS
# =============================================================================

@router.post("/shopify/orders/create")
async def shopify_order_created(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook)
):
    """
    Handle Shopify order creation webhook.
    
    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
        order_id = data.get("id")
        order_number = data.get("order_number")
        total_price = data.get("total_price")
        
        logger.info(f"[PACKAGE] Shopify order created: #{order_number} (${total_price})")
        
        # TODO: Process order in background
        # background_tasks.add_task(process_new_order, data)
        
        return {
            "success": True,
            "order_id": order_id,
            "message": f"Order #{order_number} received"
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


@router.post("/shopify/orders/updated")
async def shopify_order_updated(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook)
):
    """
    Handle Shopify order update webhook.
    
    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
        order_id = data.get("id")
        financial_status = data.get("financial_status")
        fulfillment_status = data.get("fulfillment_status")
        
        logger.info(f"[NOTE] Shopify order updated: {order_id} - {financial_status}/{fulfillment_status}")
        
        return {
            "success": True,
            "order_id": order_id,
            "financial_status": financial_status,
            "fulfillment_status": fulfillment_status
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


@router.post("/shopify/orders/cancelled")
async def shopify_order_cancelled(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook)
):
    """
    Handle Shopify order cancellation webhook.
    
    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
        order_id = data.get("id")
        order_number = data.get("order_number")
        cancel_reason = data.get("cancel_reason")
        
        logger.warning(f"[ERROR] Shopify order cancelled: #{order_number} - {cancel_reason}")
        
        # TODO: Handle refunds, update inventory
        
        return {
            "success": True,
            "order_id": order_id,
            "cancel_reason": cancel_reason
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


@router.post("/shopify/products/update")
async def shopify_product_updated(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook)
):
    """
    Handle Shopify product update webhook.
    
    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
        product_id = data.get("id")
        title = data.get("title")
        
        logger.info(f"[PACKAGE] Shopify product updated: {title} ({product_id})")
        
        return {
            "success": True,
            "product_id": product_id,
            "title": title
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


@router.post("/shopify/inventory/update")
async def shopify_inventory_updated(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook)
):
    """
    Handle Shopify inventory level update webhook.
    
    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
        inventory_item_id = data.get("inventory_item_id")
        available = data.get("available")
        
        logger.info(f"[STATS] Inventory updated: {inventory_item_id} -> {available} units")
        
        # TODO: Check for low stock alerts
        
        return {
            "success": True,
            "inventory_item_id": inventory_item_id,
            "available": available
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


# =============================================================================
# LEMONSQUEEZY WEBHOOKS (Payments/Subscriptions)
# =============================================================================

async def upgrade_user_tier(user_id: int, tier: str, db_session=None):
    """
    Upgrade user's subscription tier after successful payment.
    """
    from ospra_os.database.connection import get_session
    from ospra_os.database import User, SubscriptionTier
    from datetime import datetime
    
    tier_map = {
        "nest": SubscriptionTier.NEST,
        "flight": SubscriptionTier.FLIGHT,
        "soar": SubscriptionTier.SOAR,
        "stratosphere": SubscriptionTier.STRATOSPHERE,
    }
    
    session = db_session or get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.subscription_tier = tier_map.get(tier.lower(), SubscriptionTier.NEST)
            user.subscription_started = datetime.utcnow()
            user.updated_at = datetime.utcnow()
            session.commit()
            logger.info(f"[SUCCESS] User {user_id} upgraded to {tier}")
            return True
        else:
            logger.error(f"[ERROR] User {user_id} not found for tier upgrade")
            return False
    except Exception as e:
        logger.error(f"[ERROR] Failed to upgrade user {user_id}: {e}")
        session.rollback()
        return False
    finally:
        if not db_session:
            session.close()


@router.post("/lemonsqueezy/subscription")
async def lemonsqueezy_subscription(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_lemonsqueezy_webhook)
):
    """
    Handle LemonSqueezy subscription webhook.
    
    Events: subscription_created, subscription_updated, subscription_cancelled
    
    [SECURE] Verified with X-Signature
    """
    try:
        data = json.loads(body)
        
        meta = data.get("meta", {})
        event_name = meta.get("event_name")
        custom_data = meta.get("custom_data", {})
        
        attributes = data.get("data", {}).get("attributes", {})
        user_email = attributes.get("user_email")
        status = attributes.get("status")
        variant_name = attributes.get("variant_name")  # Tier name
        
        # Get user_id and tier from custom data (sent during checkout)
        user_id = custom_data.get("user_id")
        tier = custom_data.get("tier")
        
        logger.info(f"[PAYMENT] LemonSqueezy {event_name}: user_id={user_id}, email={user_email}, tier={tier}, status={status}")
        
        # Handle different events
        if event_name == "subscription_created" and status == "active":
            # New subscription - upgrade user
            if user_id and tier:
                background_tasks.add_task(upgrade_user_tier, int(user_id), tier)
                logger.info(f"[SUCCESS] Scheduled tier upgrade for user {user_id} to {tier}")
            else:
                logger.warning(f"[WARNING] Missing user_id or tier in custom_data")
        
        elif event_name == "subscription_updated":
            if status == "active" and user_id and tier:
                background_tasks.add_task(upgrade_user_tier, int(user_id), tier)
            elif status in ["cancelled", "expired", "past_due"]:
                # Downgrade to free tier
                if user_id:
                    background_tasks.add_task(upgrade_user_tier, int(user_id), "nest")
                    logger.info(f"[DOWNGRADE] User {user_id} subscription {status}")
        
        elif event_name == "subscription_cancelled":
            # Downgrade to free tier
            if user_id:
                background_tasks.add_task(upgrade_user_tier, int(user_id), "nest")
                logger.info(f"[DOWNGRADE] User {user_id} subscription cancelled")
        
        return {
            "success": True,
            "event": event_name,
            "user_id": user_id,
            "tier": tier,
            "status": status
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


@router.post("/lemonsqueezy/order")
async def lemonsqueezy_order(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_lemonsqueezy_webhook)
):
    """
    Handle LemonSqueezy order webhook.
    
    Events: order_created, order_refunded
    
    [SECURE] Verified with X-Signature
    """
    try:
        data = json.loads(body)
        
        meta = data.get("meta", {})
        event_name = meta.get("event_name")
        custom_data = meta.get("custom_data", {})
        
        attributes = data.get("data", {}).get("attributes", {})
        user_email = attributes.get("user_email")
        total = attributes.get("total_formatted")
        status = attributes.get("status")
        
        # Get user_id and tier from custom data
        user_id = custom_data.get("user_id")
        tier = custom_data.get("tier")
        
        logger.info(f"[PRICE] LemonSqueezy {event_name}: user_id={user_id}, email={user_email}, total={total}, status={status}")
        
        # Handle successful order (one-time or first subscription payment)
        if event_name == "order_created" and status == "paid":
            if user_id and tier:
                background_tasks.add_task(upgrade_user_tier, int(user_id), tier)
                logger.info(f"[SUCCESS] Order paid - upgrading user {user_id} to {tier}")
        
        elif event_name == "order_refunded":
            # Refund - downgrade to free
            if user_id:
                background_tasks.add_task(upgrade_user_tier, int(user_id), "nest")
                logger.warning(f"[REFUND] Order refunded - downgrading user {user_id}")
        
        return {
            "success": True,
            "event": event_name,
            "user_id": user_id,
            "user_email": user_email,
            "total": total
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


# =============================================================================
# CJ DROPSHIPPING WEBHOOKS
# =============================================================================

async def verify_cj_webhook(
    request: Request,
    x_cj_signature: str = Header(..., alias="X-CJ-Signature")
) -> bytes:
    """
    FastAPI dependency for CJ webhook verification.

    SECURITY: Signature verification is REQUIRED.
    """
    import hmac
    import hashlib
    import os

    body = await request.body()
    secret = os.getenv("CJ_WEBHOOK_SECRET")

    if not secret:
        logger.error("CJ_WEBHOOK_SECRET not configured - rejecting webhook")
        raise HTTPException(status_code=500, detail="Webhook verification not configured")

    # CJ uses HMAC-SHA256
    computed = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, x_cj_signature):
        logger.warning(f"Invalid CJ webhook signature from {request.client.host}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return body


@router.post("/cj/inventory")
async def cj_inventory_update(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_cj_webhook)
):
    """
    Handle CJ Dropshipping inventory update webhook.

    [SECURE] Verified with X-CJ-Signature (REQUIRED)
    """
    try:
        data = json.loads(body)

        product_id = data.get("pid")
        available = data.get("inventory", 0)
        warehouse = data.get("warehouse", "unknown")

        logger.info(f"[PACKAGE] CJ inventory update: {product_id} -> {available} units ({warehouse})")

        # TODO: Sync with Shopify inventory

        return {
            "success": True,
            "product_id": product_id,
            "available": available,
            "warehouse": warehouse
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


@router.post("/cj/shipment")
async def cj_shipment_update(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_cj_webhook)
):
    """
    Handle CJ Dropshipping shipment update webhook.

    [SECURE] Verified with X-CJ-Signature (REQUIRED)
    """
    try:
        data = json.loads(body)

        order_id = data.get("orderId")
        tracking_number = data.get("trackingNumber")
        carrier = data.get("carrier")
        status = data.get("status")

        logger.info(f"[SHIPPING] CJ shipment update: {order_id} - {tracking_number} ({status})")

        # TODO: Update Shopify fulfillment, send tracking to customer

        return {
            "success": True,
            "order_id": order_id,
            "tracking_number": tracking_number,
            "carrier": carrier,
            "status": status
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


# =============================================================================
# GDPR WEBHOOKS (Required for Shopify Apps)
# =============================================================================

@router.post("/shopify/gdpr/customers/redact")
async def gdpr_customers_redact(
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook)
):
    """
    Handle GDPR customer data erasure request.
    
    Required for Shopify apps - must remove all customer data.
    
    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
        shop_domain = data.get("shop_domain")
        customer = data.get("customer", {})
        customer_email = customer.get("email")
        
        logger.warning(f"[LOCKED] GDPR customer redact: {customer_email} from {shop_domain}")
        
        # TODO: Delete all customer data
        # await delete_customer_data(customer_email)
        
        return {"success": True, "message": "Customer data scheduled for deletion"}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


@router.post("/shopify/gdpr/shop/redact")
async def gdpr_shop_redact(
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook)
):
    """
    Handle GDPR shop data erasure request.
    
    Required for Shopify apps - must remove all shop data after uninstall.
    
    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
        shop_domain = data.get("shop_domain")
        shop_id = data.get("shop_id")
        
        logger.warning(f"[LOCKED] GDPR shop redact: {shop_domain} ({shop_id})")
        
        # TODO: Delete all shop data
        # await delete_shop_data(shop_id)
        
        return {"success": True, "message": "Shop data scheduled for deletion"}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


@router.post("/shopify/gdpr/customers/data_request")
async def gdpr_data_request(
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook)
):
    """
    Handle GDPR customer data request.
    
    Required for Shopify apps - must provide all customer data.
    
    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
        shop_domain = data.get("shop_domain")
        customer = data.get("customer", {})
        customer_email = customer.get("email")
        data_request = data.get("data_request", {})
        
        logger.info(f"[LIST] GDPR data request: {customer_email} from {shop_domain}")
        
        # TODO: Gather and return all customer data
        # customer_data = await get_customer_data(customer_email)
        
        return {
            "success": True,
            "message": "Data request received",
            "data_request_id": data_request.get("id")
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")


# =============================================================================
# TEST ENDPOINT REMOVED FOR SECURITY
# =============================================================================
# The /test endpoint was removed because it allowed unverified webhook
# submissions, which could be exploited in production.
#
# For webhook testing, use the provider's official testing tools:
# - Shopify: Partner Dashboard webhook testing
# - LemonSqueezy: Test events from dashboard
# - Stripe: CLI with `stripe trigger`
#
# Or create test scripts that include valid signatures.
# =============================================================================
