"""
LEMONSQUEEZY PAYMENT API ROUTES

Endpoints for subscription management and webhook handling.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from typing import Dict, Any, Optional
from pydantic import BaseModel

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.core.tiers import SubscriptionTier, get_tier_definition
from ospra_os.payments.lemonsqueezy import (
    LemonSqueezyClient,
    verify_webhook_signature,
    handle_webhook_event,
    get_checkout_url_for_tier,
    LEMONSQUEEZY_WEBHOOK_SECRET,
)
from ospra_os.database import SessionLocal, User

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["Payments"])


# ==================== REQUEST MODELS ====================

class CreateCheckoutRequest(BaseModel):
    tier: str  # "flight", "soar", "stratosphere"
    # T43: user_email/user_id are IGNORED — identity comes from the JWT.
    # (They used to be trusted, letting a caller create a checkout whose
    # webhook would re-tier an arbitrary user_id.) Kept optional so existing
    # clients that still send them don't get validation errors.
    user_email: Optional[str] = None
    user_id: Optional[str] = None


class ChangeTierRequest(BaseModel):
    subscription_id: str
    new_tier: str


# ==================== OWNERSHIP VERIFICATION (T43) ====================

async def _assert_subscription_owner(
    client: LemonSqueezyClient, subscription_id: str, current_user: User
) -> Dict[str, Any]:
    """Verify the LemonSqueezy subscription belongs to the calling user.

    There is no local subscription↔user table, so ownership is checked
    against LemonSqueezy itself: the subscription's user_email must match the
    authenticated user's email. 404 (not 403) so subscription ids can't be
    enumerated. Fails CLOSED on any lookup problem.
    """
    subscription, error = await client.get_subscription(subscription_id)
    if error or not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Subscription not found")

    attributes = (subscription.get("data") or {}).get("attributes") or {}
    sub_email = (attributes.get("user_email") or "").strip().lower()
    caller_email = (current_user.email or "").strip().lower()
    if not sub_email or sub_email != caller_email:
        logger.warning(
            f"[PAYMENTS] User {current_user.id} attempted to access "
            f"subscription {subscription_id} they don't own"
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Subscription not found")
    return subscription


# ==================== CHECKOUT ENDPOINTS ====================

@router.post("/checkout")
async def create_checkout(
    request: CreateCheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Create a LemonSqueezy checkout session.

    Returns a checkout URL to redirect the user to.

    T43: requires auth, and the checkout's custom_data (which the payment
    webhook later uses to decide WHO gets the tier) comes from the JWT — the
    client-supplied user_email/user_id are ignored.
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
            user_email=current_user.email,
            user_id=str(current_user.id)
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
        logger.error(f"Payment service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service unavailable. Please try again later."
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
async def get_subscription(
    subscription_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get subscription details (T43: auth + ownership required)."""
    try:
        client = LemonSqueezyClient()
        return await _assert_subscription_owner(client, subscription_id, current_user)
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"Payment service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service unavailable. Please try again later."
        )


@router.post("/subscription/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    current_user: User = Depends(get_current_user),
):
    """Cancel subscription at end of billing period (T43: owner only)."""
    try:
        client = LemonSqueezyClient()
        await _assert_subscription_owner(client, subscription_id, current_user)
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
        logger.error(f"Payment service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service unavailable. Please try again later."
        )


@router.post("/subscription/{subscription_id}/resume")
async def resume_subscription(
    subscription_id: str,
    current_user: User = Depends(get_current_user),
):
    """Resume a cancelled subscription (T43: owner only)."""
    try:
        client = LemonSqueezyClient()
        await _assert_subscription_owner(client, subscription_id, current_user)
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
        logger.error(f"Payment service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service unavailable. Please try again later."
        )


@router.post("/subscription/change-tier")
async def change_subscription_tier(
    request: ChangeTierRequest,
    current_user: User = Depends(get_current_user),
):
    """Change subscription to a different tier.

    T43: requires auth AND verified ownership of the subscription. This was
    fully open — anyone could re-tier any subscription_id, including other
    paying customers'.
    """
    try:
        tier = SubscriptionTier(request.new_tier)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {request.new_tier}"
        )

    try:
        client = LemonSqueezyClient()
        await _assert_subscription_owner(client, request.subscription_id, current_user)
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
        logger.error(f"Payment service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service unavailable. Please try again later."
        )


@router.get("/customer/{customer_id}/portal")
async def get_customer_portal(
    customer_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get customer portal URL for self-service billing management.

    T43: auth + ownership — the LS customer's email must match the caller
    (the portal URL grants billing self-service for that customer).
    """
    try:
        client = LemonSqueezyClient()

        customer, cust_err = await client._request("GET", f"customers/{customer_id}")
        if cust_err or not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Customer not found")
        cust_email = (
            ((customer.get("data") or {}).get("attributes") or {}).get("email") or ""
        ).strip().lower()
        if not cust_email or cust_email != (current_user.email or "").strip().lower():
            logger.warning(
                f"[PAYMENTS] User {current_user.id} attempted portal access "
                f"for customer {customer_id} they don't own"
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Customer not found")

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
        logger.error(f"Payment service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service unavailable. Please try again later."
        )


# ==================== WEBHOOK ENDPOINT ====================

@router.post("/webhook")
async def lemonsqueezy_webhook(
    request: Request,
    x_signature: str = Header(..., alias="X-Signature")
):
    """
    LemonSqueezy webhook endpoint.

    SECURITY: Signature verification is REQUIRED.

    Handles:
    - subscription_created
    - subscription_updated
    - subscription_cancelled
    - subscription_expired
    - subscription_payment_failed
    """
    # Get raw body for signature verification
    body = await request.body()

    # SECURITY: Webhook secret MUST be configured in production
    if not LEMONSQUEEZY_WEBHOOK_SECRET:
        logger.error("LEMONSQUEEZY_WEBHOOK_SECRET not configured - rejecting webhook")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook verification not configured"
        )

    # SECURITY: Always verify signature
    if not verify_webhook_signature(body, x_signature):
        logger.warning(f"Invalid LemonSqueezy webhook signature from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

    # Parse event
    try:
        import json
        event = json.loads(body)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
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
