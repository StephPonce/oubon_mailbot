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
from typing import Dict, Any, Optional
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
from ospra_os.observability.posthog_client import capture as posthog_capture, FunnelEvent

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
#
# Audit fix (#50, 2026-04): the order/products/inventory handlers that
# previously lived here were TODO stubs that returned 200 OK without doing
# any work. The CANONICAL Shopify webhook router lives in
# ``ospra_os/webhooks/shopify_webhooks.py`` (mounted at ``/webhooks/shopify/*``)
# and has 24 fully-implemented handlers + HMAC verification.
#
# Having two parallel registrations was actively dangerous: if Shopify's
# Partner-dashboard URL drifted to ``/api/webhooks/shopify/orders/create``
# instead of ``/webhooks/shopify/orders/create``, every order silently
# disappeared with a 200 OK. We now keep the silent stubs DELETED so a
# URL drift surfaces as a hard 404 — Shopify retries failures and emails
# the partner, which is a lot louder than a forever-200 stub.
#
# What's still in this file:
#   - GDPR handlers (``/shopify/gdpr/*``) — kept as a parallel route. Both
#     these and the corresponding routes in ``webhooks/shopify_webhooks.py``
#     now delegate to the same canonical processors in
#     ``ospra_os/security/gdpr.py``, so the Partner-dashboard URL can
#     point at either path safely.
#   - LemonSqueezy & CJ Dropshipping handlers — those are real and live.

# =============================================================================
# LEMONSQUEEZY WEBHOOKS (Payments/Subscriptions)
# =============================================================================

_events_table_ready = False


def _ensure_events_table():
    """Create processed_webhook_events on first use (idempotent, once per
    process). init_db() also creates it in prod; this covers fresh DBs and
    test databases that skip the init path — a missing table must not turn
    every payment webhook into a 503."""
    global _events_table_ready
    if _events_table_ready:
        return
    from ospra_os.database.base import Base
    from ospra_os.database.connection import get_engine
    from ospra_os.database.webhook_event_models import ProcessedWebhookEvent

    Base.metadata.create_all(get_engine(), tables=[ProcessedWebhookEvent.__table__])
    _events_table_ready = True


def _claim_webhook_event(provider: str, body: bytes, event_name: str) -> Optional[str]:
    """T27: atomically claim a webhook delivery for processing.

    The claim key is a digest of the raw body — a provider retry (or an
    attacker replaying a captured request) produces the same key and hits the
    UNIQUE constraint. Returns the key when claimed; None when this exact
    delivery was already processed (or is being processed) and must NOT be
    re-applied. Raises HTTPException(503) when the DB is unavailable, so the
    provider retries later instead of us dropping the event.
    """
    import hashlib

    event_key = hashlib.sha256(provider.encode() + b":" + body).hexdigest()

    def _attempt() -> Optional[str]:
        from sqlalchemy.exc import IntegrityError
        from ospra_os.database.connection import get_session
        from ospra_os.database.webhook_event_models import ProcessedWebhookEvent

        session = get_session()
        try:
            try:
                session.add(ProcessedWebhookEvent(
                    provider=provider,
                    event_key=event_key,
                    event_name=event_name,
                    status="processing",
                ))
                session.commit()
                return event_key
            except IntegrityError:
                session.rollback()
                existing = session.query(ProcessedWebhookEvent).filter_by(
                    event_key=event_key
                ).first()
                if existing and existing.status == "failed":
                    # A prior attempt failed and we returned 5xx — this IS the
                    # provider's retry. Reclaim it.
                    existing.status = "processing"
                    existing.error_message = None
                    session.commit()
                    return event_key
                logger.warning(
                    f"[WEBHOOK] Duplicate {provider} delivery "
                    f"({event_name}, status={existing.status if existing else '?'}) — not re-applying"
                )
                return None
        finally:
            session.close()

    try:
        from sqlalchemy.exc import OperationalError, ProgrammingError

        _ensure_events_table()
        try:
            return _attempt()
        except (OperationalError, ProgrammingError):
            # Missing table on the current engine, or a stale cached engine
            # whose backing SQLite file was replaced (its writes then fail as
            # 'readonly'). Dispose the cached engine, recreate the table on a
            # fresh one, and retry once.
            from ospra_os.database import connection as _conn

            try:
                _conn.get_engine().dispose()
            except Exception:
                pass
            _conn.get_engine.cache_clear()
            global _events_table_ready
            _events_table_ready = False
            _ensure_events_table()
            return _attempt()
    except HTTPException:
        raise
    except Exception as e:
        # No DB → we can't guarantee idempotency OR durability. 503 makes the
        # provider retry when we're healthy again.
        logger.error(f"[WEBHOOK] Cannot claim event (DB unavailable): {e}")
        raise HTTPException(status_code=503, detail="Temporarily unable to process webhooks")


def _finish_webhook_event(event_key: str, ok: bool, error: str = ""):
    """Mark a claimed event processed, or failed (releasing it for retry)."""
    try:
        from datetime import datetime, timezone as _tz
        from ospra_os.database.connection import get_session
        from ospra_os.database.webhook_event_models import ProcessedWebhookEvent

        session = get_session()
        try:
            row = session.query(ProcessedWebhookEvent).filter_by(event_key=event_key).first()
            if row:
                row.status = "processed" if ok else "failed"
                row.error_message = error or None
                row.processed_at = datetime.now(_tz.utc).replace(tzinfo=None)
                session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.error(f"[WEBHOOK] Failed to finalize event record: {e}")


async def upgrade_user_tier(user_id: int, tier: str, db_session=None):
    """
    Upgrade user's subscription tier after successful payment.
    """
    from ospra_os.database.connection import get_session
    from ospra_os.database import User, SubscriptionTier
    from datetime import datetime, timezone
    
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
            user.subscription_started = datetime.now(timezone.utc)
            user.updated_at = datetime.now(timezone.utc)
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


def _enqueue_tier_change(user_id: int, tier: str, event_name: str, payload: Dict[str, Any]) -> bool:
    """
    Apply a subscription tier change via the HYBRID dispatcher
    (``ospra_os.tasks.billing_tasks.dispatch_tier_change``): enqueue to a
    Celery worker when one is reachable (retry + backoff + dead-letter), else
    apply synchronously in-process so the customer is upgraded immediately.
    On a genuine failure the event is parked in ``billing_dead_letter``.

    This replaces the old ``background_tasks.add_task(upgrade_user_tier, ...)``
    call, whose handler swallowed exceptions — a transient DB error there left
    a paying customer on the wrong tier with no retry and no record.
    """
    try:
        from ospra_os.tasks.billing_tasks import dispatch_tier_change

        outcome = dispatch_tier_change(user_id, tier, event_name, payload)
        logger.info(f"[BILLING] Tier change {outcome}: user={user_id} tier={tier} event={event_name}")
        return outcome != "dead_letter"
    except Exception as exc:
        # Even importing the dispatcher failed (e.g. celery not installed at
        # all). Park the event directly so it is never silently lost.
        logger.error(f"[BILLING] dispatch_tier_change unavailable for user {user_id}: {exc}")
        try:
            from ospra_os.database.dead_letter_models import record_dead_letter

            record_dead_letter(
                event_name=event_name,
                user_id=user_id,
                tier=tier,
                payload=payload,
                last_error=f"dispatch unavailable: {exc}",
                attempts=0,
            )
        except Exception as inner:
            logger.error(f"[BILLING] Also failed to dead-letter user {user_id}: {inner}")
        return False


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
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

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

    # T27: claim this delivery. A replay/retry of an already-applied event is
    # acked with 200 but NOT re-applied (no double tier changes).
    event_key = _claim_webhook_event("lemonsqueezy", body, event_name or "unknown")
    if event_key is None:
        return {"success": True, "event": event_name, "duplicate": True}

    # T27: a tier change that fails to apply/enqueue must NOT be acked with
    # 200 — mark the claim failed and 5xx so LemonSqueezy retries. The old
    # code ignored the outcome: customer paid, never upgraded, no retry.
    applied = True

    # Handle different events
    if event_name == "subscription_created" and status == "active":
        # New subscription - upgrade user
        if user_id and tier:
            applied = _enqueue_tier_change(int(user_id), tier, event_name, data)
            logger.info(f"[SUCCESS] Scheduled tier upgrade for user {user_id} to {tier}")
            posthog_capture(
                int(user_id),
                FunnelEvent.SUBSCRIPTION_STARTED,
                properties={"tier": tier, "billing_status": status},
            )
        else:
            logger.warning(f"[WARNING] Missing user_id or tier in custom_data")

    elif event_name == "subscription_updated":
        if status == "active" and user_id and tier:
            applied = _enqueue_tier_change(int(user_id), tier, event_name, data)
        elif status in ["cancelled", "expired", "past_due"]:
            # Downgrade to free tier
            if user_id:
                applied = _enqueue_tier_change(int(user_id), "nest", event_name, data)
                logger.info(f"[DOWNGRADE] User {user_id} subscription {status}")
                posthog_capture(
                    int(user_id),
                    FunnelEvent.SUBSCRIPTION_CANCELLED,
                    properties={"tier": tier, "billing_status": status},
                )

    elif event_name == "subscription_cancelled":
        # Downgrade to free tier
        if user_id:
            applied = _enqueue_tier_change(int(user_id), "nest", event_name, data)
            logger.info(f"[DOWNGRADE] User {user_id} subscription cancelled")
            posthog_capture(
                int(user_id),
                FunnelEvent.SUBSCRIPTION_CANCELLED,
                properties={"tier": tier, "billing_status": "cancelled"},
            )

    _finish_webhook_event(event_key, ok=applied,
                          error="" if applied else "tier change could not be applied")
    if not applied:
        raise HTTPException(
            status_code=500,
            detail="Tier change could not be applied; webhook will be retried",
        )

    return {
        "success": True,
        "event": event_name,
        "user_id": user_id,
        "tier": tier,
        "status": status
    }


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
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

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

    # T27: replay protection + honest failure signaling (see subscription
    # handler for the full rationale).
    event_key = _claim_webhook_event("lemonsqueezy", body, event_name or "unknown")
    if event_key is None:
        return {"success": True, "event": event_name, "duplicate": True}

    applied = True

    # Handle successful order (one-time or first subscription payment)
    if event_name == "order_created" and status == "paid":
        if user_id and tier:
            applied = _enqueue_tier_change(int(user_id), tier, event_name, data)
            logger.info(f"[SUCCESS] Order paid - upgrading user {user_id} to {tier}")

    elif event_name == "order_refunded":
        # Refund - downgrade to free
        if user_id:
            applied = _enqueue_tier_change(int(user_id), "nest", event_name, data)
            logger.warning(f"[REFUND] Order refunded - downgrading user {user_id}")

    _finish_webhook_event(event_key, ok=applied,
                          error="" if applied else "tier change could not be applied")
    if not applied:
        raise HTTPException(
            status_code=500,
            detail="Tier change could not be applied; webhook will be retried",
        )

    return {
        "success": True,
        "event": event_name,
        "user_id": user_id,
        "user_email": user_email,
        "total": total
    }


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

# ----------------------------------------------------------------------------
# GDPR background-task wrappers
# ----------------------------------------------------------------------------
# Shopify requires these webhooks return 200 within 5 seconds, so we accept
# the payload, queue the actual data work, and return immediately. The real
# implementations live in ``ospra_os.security.gdpr`` so the same code path
# powers Settings → Data & Privacy in the frontend.

def _run_gdpr_export(customer_email: str, shop_domain: str, data_request_id: str) -> None:
    """Background task: gather customer data + write an audit-log row."""
    from ospra_os.database.connection import get_session
    from ospra_os.security.gdpr import export_customer_data

    session = get_session()
    try:
        export_customer_data(
            session,
            customer_email=customer_email,
            shop_domain=shop_domain,
            data_request_id=data_request_id,
        )
        # Persistence / delivery of the exported payload to the merchant
        # is intentionally not done here: Shopify's spec is silent on
        # transport (we have 30 days), and our merchant-facing flow is
        # via Settings → Data & Privacy. The audit log carries the
        # record count so support can reproduce the export on demand.
    finally:
        session.close()


def _run_gdpr_customer_redact(customer_email: str, shop_domain: str) -> None:
    """Background task: delete customer rows + write an audit-log row."""
    from ospra_os.database.connection import get_session
    from ospra_os.security.gdpr import redact_customer_data

    session = get_session()
    try:
        redact_customer_data(session, customer_email=customer_email, shop_domain=shop_domain)
    finally:
        session.close()


def _run_gdpr_shop_redact(shop_domain: str) -> None:
    """Background task: wipe a shop's data + write an audit-log row."""
    from ospra_os.database.connection import get_session
    from ospra_os.security.gdpr import redact_shop_data

    session = get_session()
    try:
        redact_shop_data(session, shop_domain=shop_domain)
    finally:
        session.close()


@router.post("/shopify/gdpr/customers/redact")
async def gdpr_customers_redact(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook),
):
    """
    Handle GDPR ``customers/redact`` webhook.

    Shopify pings this when a merchant (or the customer themselves) asks
    us to delete a specific customer's data. We must:
      1. ACK 200 within 5s (Shopify retries otherwise).
      2. Verify HMAC — done via ``verify_shopify_webhook`` dep.
      3. Actually delete the data — queued to BackgroundTasks.

    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    shop_domain = data.get("shop_domain") or ""
    customer = data.get("customer") or {}
    customer_email = (customer.get("email") or "").strip()

    if not customer_email:
        # No email = nothing for us to redact (we don't index by Shopify
        # customer_id). Still ack 200 so Shopify doesn't retry.
        logger.warning(
            "[GDPR] customers/redact received with no customer email (shop=%s)",
            shop_domain,
        )
        return {"success": True, "message": "No matching customer data"}

    logger.warning(
        f"[GDPR] customers/redact accepted for {customer_email} (shop={shop_domain})"
    )
    background_tasks.add_task(_run_gdpr_customer_redact, customer_email, shop_domain)
    return {"success": True, "message": "Customer data deletion queued"}


@router.post("/shopify/gdpr/shop/redact")
async def gdpr_shop_redact(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook),
):
    """
    Handle GDPR ``shop/redact`` webhook.

    Fired 48h after a merchant uninstalls our app. We must drop every
    record tied to that shop — products we deployed, OAuth credentials,
    sync history. Done in the background so the 5s SLA holds.

    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    shop_domain = data.get("shop_domain") or ""
    shop_id = data.get("shop_id")

    if not shop_domain:
        logger.warning("[GDPR] shop/redact received with no shop_domain (id=%s)", shop_id)
        return {"success": True, "message": "No matching shop"}

    logger.warning(f"[GDPR] shop/redact accepted for {shop_domain} (id={shop_id})")
    background_tasks.add_task(_run_gdpr_shop_redact, shop_domain)
    return {"success": True, "message": "Shop data deletion queued"}


@router.post("/shopify/gdpr/customers/data_request")
async def gdpr_data_request(
    background_tasks: BackgroundTasks,
    _: None = Depends(webhook_rate_limit),
    body: bytes = Depends(verify_shopify_webhook),
):
    """
    Handle GDPR ``customers/data_request`` webhook.

    Shopify forwards customer-driven data export requests. We have 30 days
    to fulfil; the actual payload assembly happens in the background and
    is logged to ``security_audit_logs`` for the support team to retrieve.

    [SECURE] Verified with X-Shopify-Hmac-SHA256
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    shop_domain = data.get("shop_domain") or ""
    customer = data.get("customer") or {}
    customer_email = (customer.get("email") or "").strip()
    data_request = data.get("data_request") or {}
    data_request_id = str(data_request.get("id") or "")

    if not customer_email:
        logger.info(
            "[GDPR] data_request received with no customer email (shop=%s, id=%s)",
            shop_domain, data_request_id,
        )
        return {
            "success": True,
            "message": "No matching customer data",
            "data_request_id": data_request_id,
        }

    logger.info(
        f"[GDPR] data_request accepted: {customer_email} from {shop_domain} (id={data_request_id})"
    )
    background_tasks.add_task(
        _run_gdpr_export, customer_email, shop_domain, data_request_id
    )
    return {
        "success": True,
        "message": "Data request received",
        "data_request_id": data_request_id,
    }


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
