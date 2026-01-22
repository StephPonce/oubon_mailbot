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
from datetime import datetime
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
    FAILED = "failed"             # Fulfillment failed
    CANCELLED = "cancelled"       # Order cancelled
    MANUAL_REQUIRED = "manual"    # Needs manual intervention


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
        
        logger.info("[FULFILLMENT] Auto Fulfillment Engine initialized")
        self._log_supplier_status()
    
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
            
            # Process each line item
            results = []
            for item in shopify_order.get('line_items', []):
                result = await self._fulfill_line_item(
                    order_id=str(order_id),
                    order_number=str(order_number),
                    line_item=item,
                    shipping_address=shipping,
                    customer_email=shopify_order.get('email', '')
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
        customer_email: str
    ) -> Dict[str, Any]:
        """
        Fulfill a single line item from an order.
        
        Looks up the supplier info from product metadata and routes to appropriate fulfillment method.
        """
        product_id = line_item.get('product_id')
        variant_id = line_item.get('variant_id')
        quantity = line_item.get('quantity', 1)
        product_name = line_item.get('name', 'Unknown Product')
        
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
                shipping_address=shipping_address
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
    
    async def _fulfill_via_cj(
        self,
        order_id: str,
        order_number: str,
        product_id: int,
        product_name: str,
        supplier_sku: str,
        quantity: int,
        shipping_address: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fulfill order via CJ Dropshipping API.
        
        CJ has a proper API that supports:
        - Creating orders
        - Getting tracking numbers
        - Checking order status
        """
        if not self.cj_api_key:
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": "CJ Dropshipping API not configured",
                "status": FulfillmentStatus.MANUAL_REQUIRED.value
            }
        
        try:
            logger.info(f"  [CJ] Placing order for SKU: {supplier_sku}")
            
            # Format address for CJ
            cj_order = {
                "orderNumber": f"OSPRA-{order_number}",
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
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/createOrder",
                    headers={
                        'CJ-Access-Token': self.cj_api_key,
                        'Content-Type': 'application/json'
                    },
                    json=cj_order
                )
                
                result = response.json()
                
                if result.get('result') == True and result.get('data'):
                    cj_order_id = result['data'].get('orderId')
                    logger.info(f"  [CJ] ✅ Order placed: {cj_order_id}")
                    
                    # Save to database
                    await self._save_fulfillment_record(
                        shopify_order_id=order_id,
                        shopify_order_number=order_number,
                        product_id=product_id,
                        supplier_type=SupplierType.CJ_DROPSHIPPING.value,
                        supplier_order_id=cj_order_id,
                        status=FulfillmentStatus.ORDERED.value
                    )
                    
                    return {
                        "success": True,
                        "product_id": product_id,
                        "product_name": product_name,
                        "supplier": "CJ Dropshipping",
                        "supplier_order_id": cj_order_id,
                        "status": FulfillmentStatus.ORDERED.value
                    }
                else:
                    error = result.get('message', 'Unknown CJ API error')
                    logger.error(f"  [CJ] ❌ Order failed: {error}")
                    return {
                        "success": False,
                        "product_id": product_id,
                        "product_name": product_name,
                        "error": error,
                        "status": FulfillmentStatus.FAILED.value
                    }
                    
        except Exception as e:
            logger.error(f"  [CJ] Exception: {e}")
            return {
                "success": False,
                "product_id": product_id,
                "product_name": product_name,
                "error": str(e),
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
                "created_at": datetime.utcnow().isoformat()
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
        """Save fulfillment record to database"""
        try:
            from ospra_os.database.connection import SessionLocal
            from ospra_os.fulfillment.models import FulfillmentRecord
            
            db = SessionLocal()
            try:
                record = FulfillmentRecord(**kwargs)
                db.add(record)
                db.commit()
                logger.info(f"  Fulfillment record saved")
            finally:
                db.close()
        except ImportError:
            # Models not yet created - save to JSON as fallback
            import os
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
            
            logger.info(f"  Fulfillment record saved to JSON queue")
        except Exception as e:
            logger.error(f"Failed to save fulfillment record: {e}")
    
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
                            order['fulfilled_at'] = datetime.utcnow().isoformat()
                    
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
