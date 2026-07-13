"""
Auto Order Fulfillment System
==============================

THE KILLER FEATURE - Automatically fulfills Shopify orders on AliExpress/CJ Dropshipping.

Flow:
1. Customer orders on Shopify
2. Shopify webhook triggers this system
3. System looks up supplier info from product metadata
4. Places order automatically on AliExpress or CJ Dropshipping
5. Captures tracking number
6. Updates Shopify order with tracking
7. Notifies customer

Supported Suppliers:
- CJ Dropshipping (API - preferred, reliable)
- AliExpress (API for Dropshipping API users, otherwise manual queue)

Author: Ospra Intelligence
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


class FulfillmentStatus(str, Enum):
    """Order fulfillment status"""
    PENDING = "pending"           # Waiting to be processed
    QUEUED = "queued"             # In fulfillment queue
    PROCESSING = "processing"     # Being placed with supplier
    ORDERED = "ordered"           # Order placed, awaiting shipment
    SHIPPED = "shipped"           # Tracking number received
    DELIVERED = "delivered"       # Delivered to customer
    FAILED = "failed"             # Fulfillment failed (supplier call never went out)
    CANCELLED = "cancelled"       # Order cancelled
    MANUAL_REQUIRED = "manual"    # Needs manual intervention
    # T18: the supplier call went out but the outcome is unknown (timeout after
    # send, unparseable response). The order MAY exist at the supplier — must
    # be reviewed by a human and must NEVER be blind-retried.
    POSSIBLY_PLACED = "possibly_placed"


class SupplierType(str, Enum):
    """Supported supplier types"""
    ALIEXPRESS = "aliexpress"
    CJ_DROPSHIPPING = "cj_dropshipping"
    MANUAL = "manual"


@dataclass
class FulfillmentOrder:
    """Represents an order to be fulfilled"""
    shopify_order_id: str
    shopify_order_number: str
    customer_name: str
    customer_email: str
    shipping_address: Dict[str, Any]
    line_items: List[Dict[str, Any]]
    status: FulfillmentStatus = FulfillmentStatus.PENDING
    supplier_order_id: Optional[str] = None
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    carrier: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None


class AutoFulfillmentEngine:
    """
    Automatic order fulfillment engine.
    
    Processes Shopify orders and places them with suppliers automatically.
    """
    
    def __init__(self):
        # Shopify credentials
        self.shopify_store = os.getenv("SHOPIFY_STORE_NAME")
        self.shopify_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.shopify_base_url = f"https://{self.shopify_store}.myshopify.com/admin/api/2024-10"
        
        # CJ Dropshipping credentials
        self.cj_api_key = os.getenv("CJ_API_KEY")
        self.cj_email = os.getenv("CJ_EMAIL")
        
        # AliExpress Dropshipping API credentials
        self.aliexpress_app_key = os.getenv("ALIEXPRESS_DROPSHIP_APP_KEY")
        self.aliexpress_app_secret = os.getenv("ALIEXPRESS_DROPSHIP_APP_SECRET")
        self.aliexpress_access_token = os.getenv("ALIEXPRESS_DROPSHIP_ACCESS_TOKEN")
        
        # Fulfillment queue (in production, use Redis/Celery)
        self._fulfillment_queue: List[FulfillmentOrder] = []

        # Section B safety settings (T17/T19)
        from ospra_os.core.settings import get_settings
        self.settings = get_settings()

        logger.info("[FULFILLMENT] Auto Fulfillment Engine initialized")
        self._log_supplier_status()

    # =========================================================================
    # SAFETY RAILS (Section B band 2)
    # =========================================================================

    def _dashboard_auto_fulfill_enabled(self) -> bool:
        """Read the dashboard toggle (data/fulfillment_settings.json)."""
        try:
            settings_file = os.path.join(
                os.path.dirname(__file__), '..', '..', 'data', 'fulfillment_settings.json'
            )
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    return bool(json.load(f).get('auto_fulfill_enabled', False))
        except Exception as e:
            logger.warning(f"[FULFILLMENT] Could not read dashboard toggle: {e}")
        return False

    def auto_fulfill_enabled(self) -> bool:
        """T17: the kill switch the ENGINE itself honors.

        Requires BOTH the env master switch (AUTO_FULFILL_ENABLED, default
        False) and the dashboard toggle. Previously only one webhook caller
        checked the toggle — any other path into process_new_order() placed
        real supplier orders with no gate at all.
        """
        return bool(self.settings.AUTO_FULFILL_ENABLED) and self._dashboard_auto_fulfill_enabled()

    @staticmethod
    def _validate_shipping_address(shipping: Dict[str, Any]) -> Optional[str]:
        """T19: refuse to auto-place orders with obviously unusable addresses.

        Returns None when valid, else a human-readable reason.
        """
        required = {
            'address1': "street address",
            'city': "city",
            'country_code': "country code",
        }
        missing = [label for key, label in required.items() if not (shipping.get(key) or '').strip()]
        name = f"{shipping.get('first_name', '')}{shipping.get('last_name', '')}".strip()
        if not name and not (shipping.get('name') or '').strip():
            missing.append("recipient name")
        # ZIP is required for countries that use it; be conservative and
        # require it everywhere except the few zipless countries.
        zipless = {'AE', 'HK', 'IE', 'PA'}
        if not (shipping.get('zip') or '').strip() and (shipping.get('country_code') or '').upper() not in zipless:
            missing.append("postal code")
        if missing:
            return f"Shipping address missing: {', '.join(missing)}"
        return None

    @staticmethod
    def _order_value(shopify_order: Dict[str, Any]) -> float:
        """Customer-facing order total, for the T19 value ceiling."""
        total = shopify_order.get('total_price')
        if total is not None:
            try:
                return float(total)
            except (TypeError, ValueError):
                pass
        value = 0.0
        for item in shopify_order.get('line_items', []):
            try:
                value += float(item.get('price', 0)) * int(item.get('quantity', 1))
            except (TypeError, ValueError):
                continue
        return value

    def _count_todays_auto_orders(self) -> Optional[int]:
        """T19: how many supplier orders were auto-placed (or possibly placed)
        today. Returns None when the DB is unavailable (callers fail closed)."""
        try:
            from ospra_os.database.connection import SessionLocal
            from ospra_os.fulfillment.models import FulfillmentRecord

            db = SessionLocal()
            try:
                start_of_day = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ).replace(tzinfo=None)
                return db.query(FulfillmentRecord).filter(
                    FulfillmentRecord.created_at >= start_of_day,
                    FulfillmentRecord.status.in_((
                        FulfillmentStatus.PROCESSING.value,
                        FulfillmentStatus.ORDERED.value,
                        FulfillmentStatus.POSSIBLY_PLACED.value,
                    )),
                ).count()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[FULFILLMENT] Daily-cap count unavailable: {e}")
            return None

    def _claim_line_item(
        self,
        order_id: str,
        order_number: str,
        line_item_id: str,
        product_id,
        product_name: str,
        quantity: int,
        order_value: float,
        supplier_type: str,
        shipping_address: Dict[str, Any],
    ) -> Optional[str]:
        """T16: atomically claim a line item before placing the supplier order.

        Inserts a PROCESSING FulfillmentRecord whose UNIQUE idempotency_key is
        ``{order_id}:{line_item_id}``. Returns the key on success. Returns
        None when the row already exists (webhook retry / duplicate delivery)
        or when the DB is unavailable — in both cases the caller must NOT
        place a supplier order.
        """
        key = f"{order_id}:{line_item_id}"
        try:
            from sqlalchemy.exc import IntegrityError
            from ospra_os.database.connection import SessionLocal
            from ospra_os.fulfillment.models import FulfillmentRecord

            db = SessionLocal()
            try:
                record = FulfillmentRecord(
                    idempotency_key=key,
                    shopify_order_id=str(order_id),
                    shopify_order_number=str(order_number),
                    line_item_id=str(line_item_id),
                    product_id=str(product_id),
                    product_name=product_name,
                    quantity=quantity,
                    order_value=order_value,
                    supplier_type=supplier_type,
                    status=FulfillmentStatus.PROCESSING.value,
                    shipping_address=shipping_address,
                )
                db.add(record)
                db.commit()
                return key
            except IntegrityError:
                db.rollback()
                existing = db.query(FulfillmentRecord).filter_by(idempotency_key=key).first()
                logger.warning(
                    f"[FULFILLMENT] Duplicate delivery for {key} "
                    f"(existing status: {existing.status if existing else 'unknown'}) — skipping"
                )
                return None
            finally:
                db.close()
        except Exception as e:
            # DB unavailable → we cannot guarantee idempotency → do not place.
            logger.error(f"[FULFILLMENT] Cannot claim {key} (DB unavailable: {e}) — refusing to place")
            return None

    def _update_claim(self, key: str, status: str, supplier_order_id: Optional[str] = None,
                      error_message: Optional[str] = None):
        """Update the claimed record with the supplier-call outcome."""
        try:
            from ospra_os.database.connection import SessionLocal
            from ospra_os.fulfillment.models import FulfillmentRecord

            db = SessionLocal()
            try:
                record = db.query(FulfillmentRecord).filter_by(idempotency_key=key).first()
                if record:
                    record.status = status
                    if supplier_order_id:
                        record.supplier_order_id = supplier_order_id
                    if error_message:
                        record.error_message = error_message
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[FULFILLMENT] Failed to update claim {key}: {e}")

    def _alert(self, title: str, message: str, metadata: Optional[Dict] = None):
        """Raise a dashboard notification for events needing human review."""
        try:
            from ospra_os.database.product_history import ProductHistoryDB
            ProductHistoryDB().create_notification(
                notification_type='fulfillment',
                title=title,
                message=message,
                severity='critical',
                metadata=metadata or {},
            )
        except Exception as e:
            logger.warning(f"[FULFILLMENT] Failed to create alert: {e}")
    
    def _log_supplier_status(self):
        """Log which suppliers are configured"""
        logger.info(f"  CJ Dropshipping: {'✅ Configured' if self.cj_api_key else '❌ Not configured'}")
        logger.info(f"  AliExpress Dropship: {'✅ Configured' if self.aliexpress_access_token else '❌ Not configured'}")
    
    # =========================================================================
    # MAIN FULFILLMENT FLOW
    # =========================================================================
    
    async def process_new_order(self, shopify_order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point - process a new Shopify order for fulfillment.
        
        Args:
            shopify_order: Raw order data from Shopify webhook
            
        Returns:
            Fulfillment result with status and details
        """
        try:
            order_id = shopify_order.get('id')
            order_number = shopify_order.get('order_number', shopify_order.get('name', ''))

            logger.info(f"[FULFILLMENT] Processing order #{order_number}")

            # T17: the engine itself hard-returns when auto-fulfillment is off.
            # Previously only one webhook caller checked the toggle; any other
            # path into this method placed real supplier orders ungated.
            if not self.auto_fulfill_enabled():
                logger.info("[FULFILLMENT] Auto-fulfillment disabled — not placing supplier orders")
                return {
                    "success": False,
                    "order_id": str(order_id),
                    "order_number": str(order_number),
                    "error": "Auto-fulfillment is disabled",
                    "status": FulfillmentStatus.MANUAL_REQUIRED.value,
                }

            # Extract shipping address
            shipping = shopify_order.get('shipping_address', {})
            if not shipping:
                # Fall back to billing address
                shipping = shopify_order.get('billing_address', {})

            if not shipping:
                return {
                    "success": False,
                    "error": "No shipping address found",
                    "status": FulfillmentStatus.FAILED.value
                }

            # T19: address must be usable before any supplier order is placed.
            address_problem = self._validate_shipping_address(shipping)
            if address_problem:
                logger.warning(f"[FULFILLMENT] {address_problem} — routing to manual review")
                return {
                    "success": False,
                    "order_id": str(order_id),
                    "order_number": str(order_number),
                    "error": address_problem,
                    "status": FulfillmentStatus.MANUAL_REQUIRED.value,
                }

            # T19: per-order value ceiling.
            order_value = self._order_value(shopify_order)
            max_value = self.settings.FULFILL_MAX_ORDER_VALUE
            if order_value > max_value:
                logger.warning(
                    f"[FULFILLMENT] Order #{order_number} value ${order_value:.2f} exceeds "
                    f"ceiling ${max_value:.2f} — routing to manual review"
                )
                self._alert(
                    "High-value order needs manual fulfillment",
                    f"Order #{order_number} (${order_value:.2f}) exceeds the "
                    f"${max_value:.2f} auto-fulfillment ceiling.",
                    {"order_id": str(order_id), "order_value": order_value},
                )
                return {
                    "success": False,
                    "order_id": str(order_id),
                    "order_number": str(order_number),
                    "error": f"Order value ${order_value:.2f} exceeds auto-fulfill ceiling",
                    "status": FulfillmentStatus.MANUAL_REQUIRED.value,
                }

            # T19: daily auto-order cap. Fail closed if the count is unknown.
            todays = self._count_todays_auto_orders()
            if todays is None or todays >= self.settings.FULFILL_MAX_ORDERS_PER_DAY:
                reason = (
                    "daily order-count unavailable (DB down)" if todays is None
                    else f"daily cap of {self.settings.FULFILL_MAX_ORDERS_PER_DAY} auto-orders reached"
                )
                logger.warning(f"[FULFILLMENT] {reason} — routing to manual review")
                self._alert(
                    "Auto-fulfillment halted",
                    f"Order #{order_number} routed to manual review: {reason}.",
                    {"order_id": str(order_id)},
                )
                return {
                    "success": False,
                    "order_id": str(order_id),
                    "order_number": str(order_number),
                    "error": reason,
                    "status": FulfillmentStatus.MANUAL_REQUIRED.value,
                }

            # Process each line item
            results = []
            for item in shopify_order.get('line_items', []):
                result = await self._fulfill_line_item(
                    order_id=str(order_id),
                    order_number=str(order_number),
                    line_item=item,
                    shipping_address=shipping,
                    customer_email=shopify_order.get('email', ''),
                    order_value=order_value,
                )
                results.append(result)
            
            # Aggregate results
            all_success = all(r.get('success', False) for r in results)
            
            return {
                "success": all_success,
                "order_id": str(order_id),
                "order_number": str(order_number),
                "items_processed": len(results),
                "items_successful": sum(1 for r in results if r.get('success')),
                "results": results,
                "status": FulfillmentStatus.ORDERED.value if all_success else FulfillmentStatus.MANUAL_REQUIRED.value
            }
            
        except Exception as e:
            logger.error(f"[FULFILLMENT] Failed to process order: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "status": FulfillmentStatus.FAILED.value
            }
    
    async def _fulfill_line_item(
        self,
        order_id: str,
        order_number: str,
        line_item: Dict[str, Any],
        shipping_address: Dict[str, Any],
        customer_email: str,
        order_value: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Fulfill a single line item from an order.

        Looks up the supplier info from product metadata and routes to appropriate fulfillment method.
        """
        product_id = line_item.get('product_id')
        variant_id = line_item.get('variant_id')
        quantity = line_item.get('quantity', 1)
        product_name = line_item.get('name', 'Unknown Product')
        # T16: the idempotency key needs a stable per-line identifier. Shopify
        # line items always carry an id; fall back to variant/product so a
        # malformed payload still can't bypass dedup by omitting it.
        line_item_id = line_item.get('id') or variant_id or product_id

        logger.info(f"  Fulfilling: {quantity}x {product_name}")

        # Get supplier info from product metafields
        supplier_info = await self._get_supplier_info(product_id)

        if not supplier_info:
            logger.warning(f"  No supplier info found for product {product_id}")
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": "No supplier info found",
                "status": FulfillmentStatus.MANUAL_REQUIRED.value,
                "action_required": "Add supplier URL to product metafields"
            }

        supplier_type = supplier_info.get('type', SupplierType.MANUAL.value)
        supplier_url = supplier_info.get('url', '')
        supplier_sku = supplier_info.get('sku', '')

        # Route to appropriate fulfillment method
        if supplier_type == SupplierType.CJ_DROPSHIPPING.value:
            return await self._fulfill_via_cj(
                order_id=order_id,
                order_number=order_number,
                product_id=product_id,
                product_name=product_name,
                supplier_sku=supplier_sku,
                quantity=quantity,
                shipping_address=shipping_address,
                line_item_id=str(line_item_id),
                order_value=order_value,
                expected_cost=supplier_info.get('cost'),
            )
        
        elif supplier_type == SupplierType.ALIEXPRESS.value:
            return await self._fulfill_via_aliexpress(
                order_id=order_id,
                order_number=order_number,
                product_id=product_id,
                product_name=product_name,
                supplier_url=supplier_url,
                quantity=quantity,
                shipping_address=shipping_address
            )
        
        else:
            # Manual fulfillment required
            return await self._queue_manual_fulfillment(
                order_id=order_id,
                order_number=order_number,
                product_id=product_id,
                product_name=product_name,
                supplier_url=supplier_url,
                quantity=quantity,
                shipping_address=shipping_address
            )
    
    # =========================================================================
    # SUPPLIER INFO LOOKUP
    # =========================================================================
    
    async def _get_supplier_info(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Get supplier info from Shopify product metafields.
        
        Looks for metafields in the 'ospra' namespace:
        - fulfillment_url: AliExpress/CJ product URL
        - fulfillment_type: 'aliexpress' or 'cj_dropshipping'
        - fulfillment_sku: Supplier SKU
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.shopify_base_url}/products/{product_id}/metafields.json",
                    headers={
                        'X-Shopify-Access-Token': self.shopify_token,
                        'Content-Type': 'application/json'
                    }
                )
                
                if response.status_code != 200:
                    logger.warning(f"Failed to get metafields: {response.status_code}")
                    return None
                
                metafields = response.json().get('metafields', [])
                
                # Extract ospra namespace metafields
                supplier_info = {}
                for mf in metafields:
                    if mf.get('namespace') == 'ospra':
                        key = mf.get('key', '')
                        value = mf.get('value', '')
                        
                        if key == 'fulfillment_url':
                            supplier_info['url'] = value
                            # Auto-detect supplier type from URL
                            if 'aliexpress.com' in value.lower():
                                supplier_info['type'] = SupplierType.ALIEXPRESS.value
                            elif 'cjdropshipping.com' in value.lower():
                                supplier_info['type'] = SupplierType.CJ_DROPSHIPPING.value
                        elif key == 'fulfillment_type':
                            supplier_info['type'] = value
                        elif key == 'fulfillment_sku':
                            supplier_info['sku'] = value
                        elif key == 'supplier_cost':
                            supplier_info['cost'] = float(value)
                
                return supplier_info if supplier_info else None
                
        except Exception as e:
            logger.error(f"Failed to get supplier info: {e}")
            return None
    
    # =========================================================================
    # CJ DROPSHIPPING FULFILLMENT
    # =========================================================================
    
    async def _cj_api_post(self, url: str, payload: Dict[str, Any]) -> "httpx.Response":
        """Single seam for CJ POSTs (tests stub this). Raises httpx errors."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            return await client.post(
                url,
                headers={
                    'CJ-Access-Token': self.cj_api_key,
                    'Content-Type': 'application/json'
                },
                json=payload,
            )

    async def _check_cj_variant(
        self, supplier_sku: str, quantity: int, expected_cost: Optional[float]
    ) -> Optional[str]:
        """T19: live stock/price check before placing. Returns None when OK,
        else the reason to route to manual review. Fails CLOSED: if the check
        itself errors, we don't place the order."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://developers.cjdropshipping.com/api2.0/v1/product/variant/queryByVid",
                    headers={'CJ-Access-Token': self.cj_api_key},
                    params={"vid": supplier_sku},
                )
            data = response.json()
            if not data.get('result') or not data.get('data'):
                return f"CJ variant lookup failed: {data.get('message', 'no data')}"

            variant = data['data']

            # Stock — CJ has used a few field names across API revisions.
            stock = None
            for field in ('variantStock', 'stockNum', 'inventoryNum', 'storageNum'):
                if variant.get(field) is not None:
                    stock = variant[field]
                    break
            if stock is not None and int(stock) < quantity:
                return f"Insufficient CJ stock ({stock} < {quantity})"

            # Price drift — if we know what the product should cost, refuse
            # silently paying >25% more than expected.
            if expected_cost:
                price = variant.get('variantSellPrice') or variant.get('sellPrice')
                if price is not None and float(price) > float(expected_cost) * 1.25:
                    return (
                        f"CJ price ${float(price):.2f} exceeds expected "
                        f"${float(expected_cost):.2f} by >25%"
                    )
            return None
        except Exception as e:
            return f"CJ stock/price check errored ({e})"

    async def _fulfill_via_cj(
        self,
        order_id: str,
        order_number: str,
        product_id: int,
        product_name: str,
        supplier_sku: str,
        quantity: int,
        shipping_address: Dict[str, Any],
        line_item_id: str = "",
        order_value: float = 0.0,
        expected_cost: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Fulfill order via CJ Dropshipping API.

        Safety order of operations (Section B band 2):
          1. T19 pre-flight: live stock/price check — fail closed to manual.
          2. T16 claim: atomically insert the idempotency record BEFORE the
             supplier call. A webhook retry can't claim twice, so it can't
             order twice. (The old code saved AFTER placing, so a retry that
             raced or followed a crash double-ordered.)
          3. T18 outcome discrimination: only report FAILED when we KNOW the
             order was not created (connect error before send, or CJ said no).
             A timeout after send or an unparseable response is
             POSSIBLY_PLACED — alert a human, never blind-retry.
        """
        if not self.cj_api_key:
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": "CJ Dropshipping API not configured",
                "status": FulfillmentStatus.MANUAL_REQUIRED.value
            }

        # T19: pre-flight stock/price check (fail closed).
        preflight_problem = await self._check_cj_variant(supplier_sku, quantity, expected_cost)
        if preflight_problem:
            logger.warning(f"  [CJ] Pre-flight failed: {preflight_problem} — manual review")
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": preflight_problem,
                "status": FulfillmentStatus.MANUAL_REQUIRED.value,
            }

        # T16: atomic idempotency claim BEFORE the supplier call.
        claim_key = self._claim_line_item(
            order_id=order_id,
            order_number=order_number,
            line_item_id=line_item_id,
            product_id=product_id,
            product_name=product_name,
            quantity=quantity,
            order_value=order_value,
            supplier_type=SupplierType.CJ_DROPSHIPPING.value,
            shipping_address=shipping_address,
        )
        if claim_key is None:
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": "Line item already processed (duplicate delivery) or DB unavailable",
                "status": FulfillmentStatus.MANUAL_REQUIRED.value,
                "duplicate": True,
            }

        logger.info(f"  [CJ] Placing order for SKU: {supplier_sku}")

        # Format address for CJ
        cj_order = {
            "orderNumber": f"OSPRA-{order_number}-{line_item_id}",
            "shippingName": f"{shipping_address.get('first_name', '')} {shipping_address.get('last_name', '')}".strip(),
            "shippingCountry": shipping_address.get('country', ''),
            "shippingCountryCode": shipping_address.get('country_code', ''),
            "shippingProvince": shipping_address.get('province', ''),
            "shippingCity": shipping_address.get('city', ''),
            "shippingAddress": shipping_address.get('address1', ''),
            "shippingAddress2": shipping_address.get('address2', ''),
            "shippingZip": shipping_address.get('zip', ''),
            "shippingPhone": shipping_address.get('phone', ''),
            "products": [
                {
                    "vid": supplier_sku,
                    "quantity": quantity
                }
            ]
        }

        # --- the supplier call, with T18 outcome discrimination -------------
        try:
            response = await self._cj_api_post(
                "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/createOrder",
                cj_order,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            # Never reached CJ — safe to call FAILED (retryable).
            logger.error(f"  [CJ] Connection failed before send: {e}")
            self._update_claim(claim_key, FulfillmentStatus.FAILED.value,
                               error_message=f"connect error: {e}")
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": f"CJ unreachable: {e}",
                "status": FulfillmentStatus.FAILED.value,
            }
        except Exception as e:
            # Sent (or unknown) — the order MAY exist at CJ. T18: possibly
            # placed, human review, never blind-retry.
            logger.error(f"  [CJ] Request failed AFTER send (outcome unknown): {e}")
            self._update_claim(claim_key, FulfillmentStatus.POSSIBLY_PLACED.value,
                               error_message=f"post-send failure: {e}")
            self._alert(
                "CJ order outcome UNKNOWN — check before retrying",
                f"Order #{order_number} ({product_name}) may or may not exist at CJ "
                f"(request failed after send: {e}). Verify in the CJ dashboard "
                f"(reference OSPRA-{order_number}-{line_item_id}) before any retry.",
                {"order_id": order_id, "claim_key": claim_key},
            )
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": f"CJ call outcome unknown: {e}",
                "status": FulfillmentStatus.POSSIBLY_PLACED.value,
            }

        try:
            result = response.json()
        except Exception as e:
            # HTTP round-trip completed but the body is unparseable. The old
            # code reported FAILED here even though CJ may well have created
            # the order — with no idempotency that meant a retry double-ordered.
            logger.error(f"  [CJ] Unparseable response (HTTP {response.status_code}): {e}")
            self._update_claim(claim_key, FulfillmentStatus.POSSIBLY_PLACED.value,
                               error_message=f"unparseable response: {e}")
            self._alert(
                "CJ order outcome UNKNOWN — unparseable response",
                f"Order #{order_number} ({product_name}): CJ returned HTTP "
                f"{response.status_code} with an unparseable body. Verify in the CJ "
                f"dashboard (reference OSPRA-{order_number}-{line_item_id}) before any retry.",
                {"order_id": order_id, "claim_key": claim_key},
            )
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": "CJ response unparseable — order possibly placed",
                "status": FulfillmentStatus.POSSIBLY_PLACED.value,
            }

        if result.get('result') is True and result.get('data'):
            cj_order_id = result['data'].get('orderId')
            logger.info(f"  [CJ] ✅ Order placed: {cj_order_id}")
            self._update_claim(claim_key, FulfillmentStatus.ORDERED.value,
                               supplier_order_id=cj_order_id)
            return {
                "success": True,
                "product_id": product_id,
                "product_name": product_name,
                "supplier": "CJ Dropshipping",
                "supplier_order_id": cj_order_id,
                "status": FulfillmentStatus.ORDERED.value
            }
        else:
            # CJ answered and said NO — the one case a clean FAILED is honest.
            error = result.get('message', 'Unknown CJ API error')
            logger.error(f"  [CJ] ❌ Order rejected by CJ: {error}")
            self._update_claim(claim_key, FulfillmentStatus.FAILED.value,
                               error_message=error)
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": error,
                "status": FulfillmentStatus.FAILED.value
            }
    
    # =========================================================================
    # ALIEXPRESS FULFILLMENT
    # =========================================================================
    
    async def _fulfill_via_aliexpress(
        self,
        order_id: str,
        order_number: str,
        product_id: int,
        product_name: str,
        supplier_url: str,
        quantity: int,
        shipping_address: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fulfill order via AliExpress.
        
        AliExpress Dropshipping API (if configured) allows automated ordering.
        Otherwise, queues for manual fulfillment with details.
        """
        if self.aliexpress_access_token:
            # Use AliExpress Dropshipping API
            return await self._fulfill_via_aliexpress_api(
                order_id=order_id,
                order_number=order_number,
                product_id=product_id,
                product_name=product_name,
                supplier_url=supplier_url,
                quantity=quantity,
                shipping_address=shipping_address
            )
        else:
            # Queue for manual fulfillment
            return await self._queue_manual_fulfillment(
                order_id=order_id,
                order_number=order_number,
                product_id=product_id,
                product_name=product_name,
                supplier_url=supplier_url,
                quantity=quantity,
                shipping_address=shipping_address
            )
    
    async def _fulfill_via_aliexpress_api(
        self,
        order_id: str,
        order_number: str,
        product_id: int,
        product_name: str,
        supplier_url: str,
        quantity: int,
        shipping_address: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Place order using AliExpress Dropshipping API.
        
        Note: AliExpress Dropshipping API requires special approval.
        Most users will need manual fulfillment.
        """
        try:
            # Extract product ID from AliExpress URL
            import re
            match = re.search(r'/item/(\d+)\.html', supplier_url)
            if not match:
                match = re.search(r'item/(\d+)', supplier_url)
            
            if not match:
                return {
                    "success": False,
                    "product_id": product_id,
                    "error": "Could not extract AliExpress product ID from URL",
                    "status": FulfillmentStatus.MANUAL_REQUIRED.value
                }
            
            aliexpress_product_id = match.group(1)
            
            logger.info(f"  [AliExpress] Placing order for product: {aliexpress_product_id}")
            
            # AliExpress Dropshipping API order placement
            # Note: This requires ds.order.create API access
            order_data = {
                "param_place_order_request4_open_api_d_t_o": json.dumps({
                    "product_items": [{
                        "product_id": int(aliexpress_product_id),
                        "product_count": quantity,
                        "sku_id": ""  # Would need to look this up
                    }],
                    "logistics_address": {
                        "contact_person": f"{shipping_address.get('first_name', '')} {shipping_address.get('last_name', '')}".strip(),
                        "country": shipping_address.get('country_code', 'US'),
                        "province": shipping_address.get('province', ''),
                        "city": shipping_address.get('city', ''),
                        "address": shipping_address.get('address1', ''),
                        "address2": shipping_address.get('address2', ''),
                        "zip": shipping_address.get('zip', ''),
                        "mobile_no": shipping_address.get('phone', '')
                    }
                })
            }
            
            # TODO: Implement full AliExpress API call
            # For now, queue for manual fulfillment since most won't have API access
            
            logger.warning("  [AliExpress] Full API integration pending - queuing for manual")
            return await self._queue_manual_fulfillment(
                order_id=order_id,
                order_number=order_number,
                product_id=product_id,
                product_name=product_name,
                supplier_url=supplier_url,
                quantity=quantity,
                shipping_address=shipping_address
            )
            
        except Exception as e:
            logger.error(f"  [AliExpress] Exception: {e}")
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": str(e),
                "status": FulfillmentStatus.FAILED.value
            }
    
    # =========================================================================
    # MANUAL FULFILLMENT QUEUE
    # =========================================================================
    
    async def _queue_manual_fulfillment(
        self,
        order_id: str,
        order_number: str,
        product_id: int,
        product_name: str,
        supplier_url: str,
        quantity: int,
        shipping_address: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Queue order for manual fulfillment.
        
        Creates a notification with all details needed to manually place the order.
        This is the fallback when API fulfillment isn't available.
        """
        try:
            # Format shipping address for display
            formatted_address = f"""
{shipping_address.get('first_name', '')} {shipping_address.get('last_name', '')}
{shipping_address.get('address1', '')}
{shipping_address.get('address2', '')}
{shipping_address.get('city', '')}, {shipping_address.get('province', '')} {shipping_address.get('zip', '')}
{shipping_address.get('country', '')}
Phone: {shipping_address.get('phone', 'N/A')}
            """.strip()
            
            # Save to fulfillment queue
            fulfillment_record = {
                "shopify_order_id": order_id,
                "shopify_order_number": order_number,
                "product_id": str(product_id),
                "product_name": product_name,
                "supplier_url": supplier_url,
                "quantity": quantity,
                "shipping_address": formatted_address,
                "shipping_address_raw": shipping_address,
                "status": FulfillmentStatus.MANUAL_REQUIRED.value,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self._save_fulfillment_record(**fulfillment_record)
            
            # Create notification
            try:
                from ospra_os.database.product_history import ProductHistoryDB
                db = ProductHistoryDB()
                db.create_notification(
                    notification_type='fulfillment',
                    title='Manual Fulfillment Required',
                    message=f'Order #{order_number}: {quantity}x {product_name}',
                    severity='warning',
                    product_id=str(product_id),
                    metadata={
                        'order_id': order_id,
                        'order_number': order_number,
                        'supplier_url': supplier_url,
                        'quantity': quantity,
                        'shipping_address': formatted_address
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to create notification: {e}")
            
            logger.info(f"  [QUEUE] Order queued for manual fulfillment")
            
            return {
                "success": True,  # Queued successfully
                "product_id": product_id,
                "product_name": product_name,
                "supplier_url": supplier_url,
                "quantity": quantity,
                "shipping_address": formatted_address,
                "status": FulfillmentStatus.MANUAL_REQUIRED.value,
                "action_required": "Place order manually at supplier URL",
                "note": "Once shipped, add tracking number via dashboard"
            }
            
        except Exception as e:
            logger.error(f"Failed to queue manual fulfillment: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": FulfillmentStatus.FAILED.value
            }
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_fulfillment_record(self, **kwargs):
        """Save a fulfillment record.

        Historical note: this used to try importing FulfillmentRecord — which
        did not exist — so EVERY record went to the JSON fallback. The model is
        real now (T16), but the manual-fulfillment dashboard queue still reads
        the JSON file, so manual records are written to BOTH: the JSON queue
        (operator visibility) and the DB (durable audit trail).
        """
        # JSON queue first — this is what /api/fulfillment/queue serves.
        try:
            queue_file = os.path.join(
                os.path.dirname(__file__),
                '..', '..', 'data', 'fulfillment_queue.json'
            )
            os.makedirs(os.path.dirname(queue_file), exist_ok=True)

            queue = []
            if os.path.exists(queue_file):
                with open(queue_file, 'r') as f:
                    queue = json.load(f)

            queue.append(kwargs)

            with open(queue_file, 'w') as f:
                json.dump(queue, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to write JSON fulfillment queue: {e}")

        # Durable DB record (best-effort; duplicates are skipped, not errors).
        try:
            from sqlalchemy.exc import IntegrityError
            from ospra_os.database.connection import SessionLocal
            from ospra_os.fulfillment.models import FulfillmentRecord

            allowed = {c.name for c in FulfillmentRecord.__table__.columns}
            data = {}
            for key, value in kwargs.items():
                if key == 'shipping_address_raw':
                    data['shipping_address'] = value
                elif key in allowed and key not in ('id', 'created_at', 'updated_at'):
                    data[key] = value
            if 'shopify_order_id' in data:
                data.setdefault(
                    'idempotency_key',
                    f"{data['shopify_order_id']}:{data.get('product_id', '')}:manual",
                )
            else:
                return  # not enough to key on; JSON queue already has it

            db = SessionLocal()
            try:
                db.add(FulfillmentRecord(**data))
                db.commit()
                logger.info("  Fulfillment record saved")
            except IntegrityError:
                db.rollback()  # already recorded — fine
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to save fulfillment record to DB: {e}")
    
    # =========================================================================
    # TRACKING NUMBER UPDATE
    # =========================================================================
    
    async def update_tracking(
        self,
        shopify_order_id: str,
        tracking_number: str,
        carrier: str = "Other",
        tracking_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update Shopify order with tracking information.
        
        Called when tracking is received from supplier.
        """
        try:
            logger.info(f"[TRACKING] Updating order {shopify_order_id} with tracking: {tracking_number}")
            
            # First, get the order to find the fulfillment
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get order details
                order_response = await client.get(
                    f"{self.shopify_base_url}/orders/{shopify_order_id}.json",
                    headers={
                        'X-Shopify-Access-Token': self.shopify_token,
                        'Content-Type': 'application/json'
                    }
                )
                
                if order_response.status_code != 200:
                    return {"success": False, "error": f"Order not found: {order_response.status_code}"}
                
                order = order_response.json().get('order', {})
                
                # Get line items for fulfillment
                line_items = order.get('line_items', [])
                
                if not line_items:
                    return {"success": False, "error": "No line items to fulfill"}
                
                # Create fulfillment with tracking
                fulfillment_data = {
                    "fulfillment": {
                        "location_id": await self._get_location_id(),
                        "tracking_number": tracking_number,
                        "tracking_company": carrier,
                        "tracking_url": tracking_url,
                        "notify_customer": True,
                        "line_items": [
                            {"id": item['id']} for item in line_items
                        ]
                    }
                }
                
                # Create fulfillment
                fulfill_response = await client.post(
                    f"{self.shopify_base_url}/orders/{shopify_order_id}/fulfillments.json",
                    headers={
                        'X-Shopify-Access-Token': self.shopify_token,
                        'Content-Type': 'application/json'
                    },
                    json=fulfillment_data
                )
                
                if fulfill_response.status_code in [200, 201]:
                    fulfillment = fulfill_response.json().get('fulfillment', {})
                    logger.info(f"[TRACKING] ✅ Fulfillment created: {fulfillment.get('id')}")
                    
                    return {
                        "success": True,
                        "fulfillment_id": fulfillment.get('id'),
                        "tracking_number": tracking_number,
                        "carrier": carrier,
                        "status": "shipped",
                        "customer_notified": True
                    }
                else:
                    error = fulfill_response.json()
                    logger.error(f"[TRACKING] ❌ Failed: {error}")
                    return {
                        "success": False,
                        "error": str(error)
                    }
                    
        except Exception as e:
            logger.error(f"[TRACKING] Exception: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_location_id(self) -> int:
        """Get the default Shopify location ID for fulfillment"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.shopify_base_url}/locations.json",
                    headers={
                        'X-Shopify-Access-Token': self.shopify_token,
                        'Content-Type': 'application/json'
                    }
                )
                
                if response.status_code == 200:
                    locations = response.json().get('locations', [])
                    if locations:
                        return locations[0]['id']
                
                return None
        except Exception as e:
            logger.error(f"Failed to get location: {e}")
            return None
    
    # =========================================================================
    # CHECK SUPPLIER TRACKING
    # =========================================================================
    
    async def check_cj_tracking(self, cj_order_id: str) -> Optional[Dict[str, Any]]:
        """
        Check CJ Dropshipping order status and tracking.
        
        Should be run periodically to get tracking updates.
        """
        if not self.cj_api_key:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"https://developers.cjdropshipping.com/api2.0/v1/shopping/order/getOrderDetail",
                    headers={
                        'CJ-Access-Token': self.cj_api_key,
                        'Content-Type': 'application/json'
                    },
                    params={"orderId": cj_order_id}
                )
                
                result = response.json()
                
                if result.get('result') and result.get('data'):
                    data = result['data']
                    return {
                        "status": data.get('orderStatus'),
                        "tracking_number": data.get('trackNumber'),
                        "carrier": data.get('logisticName'),
                        "shipped_date": data.get('shipDate')
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to check CJ tracking: {e}")
            return None
    
    # =========================================================================
    # FULFILLMENT QUEUE MANAGEMENT
    # =========================================================================
    
    async def get_pending_fulfillments(self) -> List[Dict[str, Any]]:
        """Get all orders pending manual fulfillment"""
        try:
            queue_file = os.path.join(
                os.path.dirname(__file__),
                '..', '..', 'data', 'fulfillment_queue.json'
            )
            
            if os.path.exists(queue_file):
                with open(queue_file, 'r') as f:
                    queue = json.load(f)
                return [
                    order for order in queue 
                    if order.get('status') == FulfillmentStatus.MANUAL_REQUIRED.value
                ]
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get pending fulfillments: {e}")
            return []
    
    async def mark_fulfilled(
        self,
        shopify_order_id: str,
        tracking_number: str,
        carrier: str = "Other"
    ) -> Dict[str, Any]:
        """
        Mark a manual fulfillment as completed.
        
        Updates the queue and adds tracking to Shopify.
        """
        # Update Shopify with tracking
        result = await self.update_tracking(
            shopify_order_id=shopify_order_id,
            tracking_number=tracking_number,
            carrier=carrier
        )
        
        if result.get('success'):
            # Update queue
            try:
                queue_file = os.path.join(
                    os.path.dirname(__file__),
                    '..', '..', 'data', 'fulfillment_queue.json'
                )
                
                if os.path.exists(queue_file):
                    with open(queue_file, 'r') as f:
                        queue = json.load(f)
                    
                    for order in queue:
                        if order.get('shopify_order_id') == shopify_order_id:
                            order['status'] = FulfillmentStatus.SHIPPED.value
                            order['tracking_number'] = tracking_number
                            order['carrier'] = carrier
                            order['fulfilled_at'] = datetime.now(timezone.utc).isoformat()
                    
                    with open(queue_file, 'w') as f:
                        json.dump(queue, f, indent=2)
                        
            except Exception as e:
                logger.warning(f"Failed to update queue: {e}")
        
        return result


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_fulfillment_engine: Optional[AutoFulfillmentEngine] = None


def get_fulfillment_engine() -> AutoFulfillmentEngine:
    """Get or create the fulfillment engine singleton"""
    global _fulfillment_engine
    if _fulfillment_engine is None:
        _fulfillment_engine = AutoFulfillmentEngine()
    return _fulfillment_engine
