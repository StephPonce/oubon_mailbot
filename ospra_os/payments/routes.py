"""
LEMONSQUEEZY PAYMENT API ROUTES

Endpoints for subscription management and webhook handling.
"""

from fastapi import APIRouter, HTTPException, Request, Header, status
from typing import Dict, Any, Optional
from pydantic import BaseModel

from ospra_os.core.tiers import SubscriptionTier, get_tier_definition
from ospra_os.payments.lemonsqueezy import (
    LemonSqueezyClient,
    verify_webhook_signature,
    handle_webhook_event,
    get_checkout_url_for_tier,
    LEMONSQUEEZY_WEBHOOK_SECRET,
)
from ospra_os.database.multi_store_models import SessionLocal, User

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["Payments"])


# ==================== REQUEST MODELS ====================

class CreateCheckoutRequest(BaseModel):
    tier: str  # "flight", "soar", "stratosphere"
    user_email: str
    user_id: str


class ChangeTierRequest(BaseModel):
    subscription_id: str
    new_tier: str


# ==================== CHECKOUT ENDPOINTS ====================

@router.post("/checkout")
async def create_checkout(request: CreateCheckoutRequest):
    """
    Create a LemonSqueezy checkout session.
    
    Returns a checkout URL to redirect the user to.
    """
    try:
        tier = SubscriptionTier(request.tier)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {request.tier}. Valid: flight, soar, stratosphere"
        )
    
    if tier == SubscriptionTier.NEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nest tier is free - no checkout needed"
        )
    
    try:
        client = LemonSqueezyClient()
        checkout_url, error = await client.create_checkout(
            tier=tier,
            user_email=request.user_email,
            user_id=request.user_id
        )
        
        if error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create checkout: {error}"
            )
        
        tier_info = get_tier_definition(tier)
        
        return {
            "success": True,
            "checkout_url": checkout_url,
            "tier": tier.value,
            "tier_name": tier_info.get("name"),
            "price": tier_info.get("price_monthly")
        }
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


@router.get("/checkout-url/{tier}")
async def get_direct_checkout_url(tier: str):
    """
    Get direct checkout URL for a tier (no API call needed).
    
    These are pre-configured LemonSqueezy checkout links.
    """
    try:
        tier_enum = SubscriptionTier(tier)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {tier}"
        )
    
    url = get_checkout_url_for_tier(tier_enum)
    
    if not url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No checkout URL configured for tier: {tier}"
        )
    
    tier_info = get_tier_definition(tier_enum)
    
    return {
        "tier": tier,
        "checkout_url": url,
        "price": tier_info.get("price_display")
    }


# ==================== SUBSCRIPTION MANAGEMENT ====================

@router.get("/subscription/{subscription_id}")
async def get_subscription(subscription_id: str):
    """Get subscription details"""
    try:
        client = LemonSqueezyClient()
        subscription, error = await client.get_subscription(subscription_id)
        
        if error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error
            )
        
        return subscription
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


@router.post("/subscription/{subscription_id}/cancel")
async def cancel_subscription(subscription_id: str):
    """Cancel subscription at end of billing period"""
    try:
        client = LemonSqueezyClient()
        success, error = await client.cancel_subscription(subscription_id)
        
        if error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error
            )
        
        return {
            "success": True,
            "message": "Subscription will be cancelled at end of billing period"
        }
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


@router.post("/subscription/{subscription_id}/resume")
async def resume_subscription(subscription_id: str):
    """Resume a cancelled subscription"""
    try:
        client = LemonSqueezyClient()
        success, error = await client.resume_subscription(subscription_id)
        
        if error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error
            )
        
        return {
            "success": True,
            "message": "Subscription resumed"
        }
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


@router.post("/subscription/change-tier")
async def change_subscription_tier(request: ChangeTierRequest):
    """Change subscription to a different tier"""
    try:
        tier = SubscriptionTier(request.new_tier)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {request.new_tier}"
        )
    
    try:
        client = LemonSqueezyClient()
        success, error = await client.change_subscription_tier(
            request.subscription_id,
            tier
        )
        
        if error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error
            )
        
        return {
            "success": True,
            "new_tier": tier.value,
            "message": f"Subscription changed to {tier.value}"
        }
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


@router.get("/customer/{customer_id}/portal")
async def get_customer_portal(customer_id: str):
    """Get customer portal URL for self-service billing management"""
    try:
        client = LemonSqueezyClient()
        portal_url, error = await client.get_customer_portal_url(customer_id)
        
        if error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error
            )
        
        return {
            "portal_url": portal_url
        }
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


# ==================== WEBHOOK ENDPOINT ====================

@router.post("/webhook")
async def lemonsqueezy_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature")
):
    """
    LemonSqueezy webhook endpoint.
    
    Handles:
    - subscription_created
    - subscription_updated
    - subscription_cancelled
    - subscription_expired
    - subscription_payment_failed
    """
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify signature
    if LEMONSQUEEZY_WEBHOOK_SECRET and x_signature:
        if not verify_webhook_signature(body, x_signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
    
    # Parse event
    try:
        event = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {e}"
        )
    
    # Handle event
    result = await handle_webhook_event(event)
    
    # Update user in database based on event
    if result.get("handled"):
        await _process_webhook_result(result)
    
    return {"received": True, "result": result}


async def _process_webhook_result(result: Dict[str, Any]):
    """
    Process webhook result and update user in database.
    """
    action = result.get("action")
    
    db = SessionLocal()
    try:
        if action == "activate_subscription":
            user_id = result.get("user_id")
            tier = result.get("tier", "flight")
            subscription_id = result.get("subscription_id")
            customer_id = result.get("customer_id")
            
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    user.subscription_tier = SubscriptionTier(tier)
                    # Store subscription_id and customer_id in user model or separate table
                    logger.info(f"[SUCCESS] Activated {tier} for user {user_id}")
                    db.commit()
        
        elif action == "update_tier":
            subscription_id = result.get("subscription_id")
            tier = result.get("tier")
            # Find user by subscription_id and update tier
            logger.info(f"[NOTE] Tier update to {tier} for subscription {subscription_id}")
        
        elif action == "downgrade_to_nest":
            subscription_id = result.get("subscription_id")
            # Find user by subscription_id and set to NEST
            logger.info(f" Downgraded to Nest for subscription {subscription_id}")
        
        elif action == "payment_failed":
            subscription_id = result.get("subscription_id")
            # Send notification, maybe set grace period
            logger.warning(f"[WARNING] Payment failed for subscription {subscription_id}")
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        db.rollback()
    finally:
        db.close()


# ==================== HEALTH CHECK ====================

@router.get("/health")
async def payments_health():
    """Health check for payment system"""
    from ospra_os.payments.lemonsqueezy import LEMONSQUEEZY_API_KEY
    
    return {
        "status": "healthy" if LEMONSQUEEZY_API_KEY else "unconfigured",
        "api_key_configured": bool(LEMONSQUEEZY_API_KEY),
        "webhook_secret_configured": bool(LEMONSQUEEZY_WEBHOOK_SECRET)
    }
