"""
Shopify Webhook Handlers
Processes order notifications and other events from Shopify
"""

from fastapi import APIRouter, Request, HTTPException, Header
import hmac
import hashlib
import json
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/shopify", tags=["Shopify Webhooks"])

def verify_shopify_webhook(data: bytes, hmac_header: str) -> bool:
    """Verify webhook came from Shopify"""

    secret = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")

    if not secret:
        logger.warning("No webhook secret configured - skipping verification")
        return True  # Allow in development

    # Calculate HMAC
    computed_hmac = hmac.new(
        secret.encode('utf-8'),
        data,
        hashlib.sha256
    ).hexdigest()

    # Compare with header
    return hmac.compare_digest(computed_hmac, hmac_header)


@router.post("/orders/create")
async def order_created(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """Handle new order from Shopify"""

    # Get raw body for HMAC verification
    body = await request.body()

    # Verify webhook (optional in development)
    if x_shopify_hmac_sha256:
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256):
            logger.error("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse order data
    try:
        order_data = json.loads(body)
    except Exception as e:
        logger.error(f"Failed to parse webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info(f"[PACKAGE] New order received: {order_data.get('order_number', 'unknown')}")

    # Process order
    await process_new_order(order_data)

    return {"status": "success"}


async def process_new_order(order_data: dict):
    """Process new Shopify order"""

    from ospra_os.database.product_history import ProductHistoryDB

    try:
        # Extract order info
        shopify_order_id = str(order_data.get('id'))
        order_number = order_data.get('order_number', order_data.get('name', ''))

        # Extract customer info
        customer = order_data.get('customer', {})
        customer_email = customer.get('email', order_data.get('email', ''))
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()

        # Extract line items (products)
        line_items = order_data.get('line_items', [])

        if not line_items:
            logger.warning(f"Order {order_number} has no line items")
            return

        # Process each product in order
        db = ProductHistoryDB()

        for item in line_items:
            product_name = item.get('name', 'Unknown Product')
            quantity = item.get('quantity', 1)
            price = float(item.get('price', 0))
            total_price = price * quantity

            # Save order to database
            order_record = {
                'shopify_order_id': shopify_order_id,
                'shopify_order_number': order_number,
                'customer_email': customer_email,
                'customer_name': customer_name,
                'product_id': str(item.get('product_id', '')),
                'product_name': product_name,
                'quantity': quantity,
                'total_price': total_price,
                'currency': order_data.get('currency', 'USD')
            }

            db.save_order(order_record)

            # Record learning event for this sale
            try:
                from datetime import datetime
                from ospra_os.database import SessionLocal
                from ospra_os.learning.hybrid_learning_engine import LearningEvent

                # Extract product metadata
                product_id = str(item.get('product_id', ''))
                niche = "unknown"  # TODO: Lookup niche from product database

                # Try to get niche from product tags or type
                if 'product' in item:
                    product = item['product']
                    tags = product.get('tags', '').lower()
                    product_type = product.get('product_type', '').lower()

                    # Simple niche detection from tags/type
                    if 'home' in tags or 'smart' in tags:
                        niche = "smart_home"
                    elif 'fitness' in tags or 'gym' in tags:
                        niche = "fitness"
                    elif 'kitchen' in tags or 'cooking' in tags:
                        niche = "kitchen"
                    elif 'tech' in tags or 'gadget' in tags:
                        niche = "tech"
                    elif 'beauty' in tags or 'skincare' in tags:
                        niche = "beauty"

                # Create learning event
                learning_db = SessionLocal()
                try:
                    event = LearningEvent(
                        user_id=1,  # TODO: Get actual user_id from store mapping
                        event_type="sale",
                        product_id=product_id,
                        details={
                            "product_name": product_name,
                            "niche": niche,
                            "price": price,
                            "quantity": quantity,
                            "revenue": total_price,
                            "order_id": shopify_order_id,
                            "order_number": order_number,
                            "customer_email": customer_email,
                            "source": "shopify_webhook",
                            "currency": order_data.get('currency', 'USD'),
                            "sale_timestamp": datetime.utcnow().isoformat()
                        },
                        timestamp=datetime.utcnow()
                    )
                    learning_db.add(event)
                    learning_db.commit()
                    logger.info(f"[STATS] Learning event recorded for product {product_id}")
                finally:
                    learning_db.close()
            except Exception as e:
                # Don't fail order processing if learning recording fails
                logger.warning(f"Failed to record learning event: {e}")

            # Create notification
            db.create_notification(
                notification_type='order',
                title='New Order Received',
                message=f'Order #{order_number}: {quantity}x {product_name} - ${total_price:.2f}',
                severity='success',
                product_id=str(item.get('product_id', '')),
                metadata={
                    'order_id': shopify_order_id,
                    'order_number': order_number,
                    'customer_email': customer_email
                }
            )

        logger.info(f"[SUCCESS] Order {order_number} processed successfully")

        # Send confirmation email to customer
        await send_order_confirmation_email(order_record)

    except Exception as e:
        logger.error(f"Failed to process order: {e}")
        raise


async def send_order_confirmation_email(order: dict):
    """Send order confirmation email to customer"""

    # TODO: Implement email sending using existing Gmail integration
    # For now, just log the attempt

    try:
        logger.info(f"[EMAIL] Order confirmation email queued for {order['customer_email']}")

        # Future implementation:
        # from ospra_os.gmail_automation.email_sender import send_email
        # await send_email(...)

        subject = f"Order Confirmation - #{order['shopify_order_number']}"

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Thank you for your order!</h2>

            <p>Hi {order['customer_name']},</p>

            <p>We've received your order and will process it shortly.</p>

            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>Order Details</h3>
                <p><strong>Order Number:</strong> #{order['shopify_order_number']}</p>
                <p><strong>Product:</strong> {order['product_name']}</p>
                <p><strong>Quantity:</strong> {order['quantity']}</p>
                <p><strong>Total:</strong> ${order['total_price']:.2f} {order['currency']}</p>
            </div>

            <p><strong>What's Next?</strong></p>
            <ul>
                <li>We'll process your order within 1-2 business days</li>
                <li>You'll receive tracking information via email</li>
                <li>Estimated delivery: 10-25 business days</li>
            </ul>

            <p>Questions? Reply to this email and we'll help!</p>

            <p>Best regards,<br>Oubon Shop Team</p>
        </body>
        </html>
        """

        logger.debug(f"Email template generated for order #{order['shopify_order_number']}")

    except Exception as e:
        logger.error(f"Failed to queue confirmation email: {e}")
