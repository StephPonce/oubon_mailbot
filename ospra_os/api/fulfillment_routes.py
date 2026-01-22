"""
FULFILLMENT API ROUTES
=======================

Auto-fulfillment system endpoints:
- View pending orders
- Add tracking numbers
- Sync supplier tracking
- Configure fulfillment settings

Author: Ospra Intelligence
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import os
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fulfillment", tags=["Fulfillment"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class AddTrackingRequest(BaseModel):
    """Request to add tracking to an order"""
    shopify_order_id: str
    tracking_number: str
    carrier: str = "Other"
    tracking_url: Optional[str] = None


class MarkFulfilledRequest(BaseModel):
    """Request to mark an order as fulfilled"""
    shopify_order_id: str
    tracking_number: str
    carrier: str = "Other"


class FulfillmentSettings(BaseModel):
    """Fulfillment automation settings"""
    auto_fulfill_enabled: bool = False
    preferred_supplier: str = "cj_dropshipping"
    auto_notify_customer: bool = True
    fallback_to_manual: bool = True


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_queue_file_path():
    """Get path to fulfillment queue JSON file"""
    return os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'data', 'fulfillment_queue.json'
    )


def get_settings_file_path():
    """Get path to fulfillment settings JSON file"""
    return os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'data', 'fulfillment_settings.json'
    )


def load_fulfillment_queue() -> List[Dict]:
    """Load fulfillment queue from JSON"""
    queue_file = get_queue_file_path()
    if os.path.exists(queue_file):
        try:
            with open(queue_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return []


def save_fulfillment_queue(queue: List[Dict]):
    """Save fulfillment queue to JSON"""
    queue_file = get_queue_file_path()
    os.makedirs(os.path.dirname(queue_file), exist_ok=True)
    with open(queue_file, 'w') as f:
        json.dump(queue, f, indent=2, default=str)


# ============================================================================
# STATUS & OVERVIEW
# ============================================================================

@router.get("/status")
async def fulfillment_status():
    """
    Get fulfillment system status.
    
    Shows which suppliers are configured and ready.
    """
    return {
        "success": True,
        "engine": "auto_fulfillment_v1",
        "suppliers": {
            "cj_dropshipping": {
                "configured": bool(os.getenv("CJ_API_KEY")),
                "mode": "api",
                "status": "ready" if os.getenv("CJ_API_KEY") else "not_configured"
            },
            "aliexpress": {
                "configured": bool(os.getenv("ALIEXPRESS_DROPSHIP_ACCESS_TOKEN")),
                "mode": "api" if os.getenv("ALIEXPRESS_DROPSHIP_ACCESS_TOKEN") else "manual",
                "status": "ready" if os.getenv("ALIEXPRESS_DROPSHIP_ACCESS_TOKEN") else "manual_mode"
            }
        },
        "features": {
            "auto_order_placement": True,
            "tracking_sync": True,
            "customer_notifications": True,
            "manual_queue": True
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/queue")
async def get_fulfillment_queue():
    """
    Get all pending fulfillment orders.
    
    Returns orders that need manual fulfillment or are awaiting tracking.
    """
    try:
        queue = load_fulfillment_queue()
        pending = [
            order for order in queue
            if order.get('status') in ['manual', 'pending', 'ordered', 'MANUAL_REQUIRED']
        ]
        
        return {
            "success": True,
            "pending_count": len(pending),
            "total_count": len(queue),
            "orders": pending
        }
        
    except Exception as e:
        logger.error(f"Failed to get fulfillment queue: {e}")
        return {
            "success": False,
            "error": str(e),
            "orders": []
        }


@router.get("/queue/stats")
async def get_queue_stats():
    """
    Get fulfillment queue statistics.
    """
    try:
        queue = load_fulfillment_queue()
        
        stats = {
            "total": len(queue),
            "manual_required": 0,
            "awaiting_tracking": 0,
            "shipped": 0,
            "failed": 0,
            "by_supplier": {}
        }
        
        for order in queue:
            status = order.get('status', 'unknown')
            
            if status in ['manual', 'MANUAL_REQUIRED', 'pending']:
                stats['manual_required'] += 1
            elif status == 'ordered':
                stats['awaiting_tracking'] += 1
            elif status == 'shipped':
                stats['shipped'] += 1
            elif status == 'failed':
                stats['failed'] += 1
            
            # Count by supplier
            supplier_url = order.get('supplier_url', '')
            if 'aliexpress' in supplier_url.lower():
                stats['by_supplier']['aliexpress'] = stats['by_supplier'].get('aliexpress', 0) + 1
            elif 'cjdropshipping' in supplier_url.lower():
                stats['by_supplier']['cj_dropshipping'] = stats['by_supplier'].get('cj_dropshipping', 0) + 1
            else:
                stats['by_supplier']['other'] = stats['by_supplier'].get('other', 0) + 1
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# TRACKING MANAGEMENT
# ============================================================================

@router.post("/tracking/add")
async def add_tracking_number(request: AddTrackingRequest):
    """
    Add tracking number to a Shopify order.
    
    Creates fulfillment in Shopify and notifies customer.
    """
    try:
        # Try to use the full fulfillment engine if available
        try:
            from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
            engine = get_fulfillment_engine()
            result = await engine.update_tracking(
                shopify_order_id=request.shopify_order_id,
                tracking_number=request.tracking_number,
                carrier=request.carrier,
                tracking_url=request.tracking_url
            )
            return result
        except ImportError:
            pass
        
        # Fallback: Update local queue
        queue = load_fulfillment_queue()
        
        for order in queue:
            if order.get('shopify_order_id') == request.shopify_order_id:
                order['tracking_number'] = request.tracking_number
                order['carrier'] = request.carrier
                order['tracking_url'] = request.tracking_url
                order['status'] = 'shipped'
                order['fulfilled_at'] = datetime.utcnow().isoformat()
                break
        
        save_fulfillment_queue(queue)
        
        return {
            "success": True,
            "tracking_number": request.tracking_number,
            "carrier": request.carrier,
            "note": "Updated local queue. Run Shopify sync to update fulfillment."
        }
        
    except Exception as e:
        logger.error(f"Failed to add tracking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mark-fulfilled")
async def mark_order_fulfilled(request: MarkFulfilledRequest):
    """
    Mark a manual fulfillment order as completed.
    
    Updates local queue and optionally syncs to Shopify.
    """
    try:
        queue = load_fulfillment_queue()
        
        for order in queue:
            if order.get('shopify_order_id') == request.shopify_order_id:
                order['status'] = 'shipped'
                order['tracking_number'] = request.tracking_number
                order['carrier'] = request.carrier
                order['fulfilled_at'] = datetime.utcnow().isoformat()
                break
        else:
            raise HTTPException(status_code=404, detail="Order not found in queue")
        
        save_fulfillment_queue(queue)
        
        return {
            "success": True,
            "order_id": request.shopify_order_id,
            "status": "shipped",
            "tracking_number": request.tracking_number
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark fulfilled: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SUPPLIER TRACKING CHECK
# ============================================================================

@router.get("/tracking/check/{supplier}/{order_id}")
async def check_supplier_tracking(supplier: str, order_id: str):
    """
    Check tracking status from a supplier.
    
    Supported suppliers:
    - cj: CJ Dropshipping order ID
    """
    try:
        if supplier.lower() == "cj":
            try:
                from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
                engine = get_fulfillment_engine()
                result = await engine.check_cj_tracking(order_id)
                if result:
                    return {
                        "success": True,
                        "supplier": "CJ Dropshipping",
                        "tracking": result
                    }
                else:
                    return {
                        "success": False,
                        "error": "No tracking info found"
                    }
            except ImportError:
                return {
                    "success": False,
                    "error": "Fulfillment engine not available"
                }
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported supplier: {supplier}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check tracking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SYNC TRACKING FROM SUPPLIERS
# ============================================================================

@router.post("/sync-tracking")
async def sync_all_tracking():
    """
    Sync tracking numbers from all suppliers.
    
    Checks CJ Dropshipping orders for tracking updates.
    """
    try:
        try:
            from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
            engine = get_fulfillment_engine()
        except ImportError:
            return {
                "success": False,
                "error": "Fulfillment engine not available",
                "synced": 0
            }
        
        queue = load_fulfillment_queue()
        
        orders_to_check = [
            order for order in queue
            if order.get('status') == 'ordered' and order.get('supplier_type') == 'cj_dropshipping'
        ]
        
        if not orders_to_check:
            return {
                "success": True,
                "message": "No CJ orders to check",
                "synced": 0
            }
        
        synced = 0
        results = []
        
        for order in orders_to_check:
            supplier_order_id = order.get('supplier_order_id')
            if not supplier_order_id:
                continue
            
            tracking = await engine.check_cj_tracking(supplier_order_id)
            
            if tracking and tracking.get('tracking_number'):
                result = await engine.update_tracking(
                    shopify_order_id=order.get('shopify_order_id'),
                    tracking_number=tracking['tracking_number'],
                    carrier=tracking.get('carrier', 'Other')
                )
                
                if result.get('success'):
                    synced += 1
                    order['status'] = 'shipped'
                    order['tracking_number'] = tracking['tracking_number']
                    results.append({
                        "order": order.get('shopify_order_number'),
                        "tracking": tracking['tracking_number'],
                        "status": "synced"
                    })
        
        if synced > 0:
            save_fulfillment_queue(queue)
        
        return {
            "success": True,
            "synced": synced,
            "checked": len(orders_to_check),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to sync tracking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SETTINGS
# ============================================================================

@router.get("/settings")
async def get_fulfillment_settings():
    """Get current fulfillment automation settings"""
    settings_file = get_settings_file_path()
    
    default_settings = {
        "auto_fulfill_enabled": False,
        "preferred_supplier": "cj_dropshipping",
        "auto_notify_customer": True,
        "fallback_to_manual": True
    }
    
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                return json.load(f)
        except:
            pass
    
    return default_settings


@router.post("/settings")
async def update_fulfillment_settings(settings: FulfillmentSettings):
    """Update fulfillment automation settings"""
    settings_file = get_settings_file_path()
    
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    
    with open(settings_file, 'w') as f:
        json.dump(settings.dict(), f, indent=2)
    
    return {
        "success": True,
        "settings": settings.dict()
    }


# ============================================================================
# MANUAL QUEUE MANAGEMENT
# ============================================================================

@router.post("/queue/add")
async def add_to_queue(
    shopify_order_id: str,
    shopify_order_number: str,
    product_name: str,
    supplier_url: str,
    quantity: int = 1,
    shipping_address: Optional[str] = None
):
    """
    Manually add an order to the fulfillment queue.
    
    Useful for testing or manual order processing.
    """
    try:
        queue = load_fulfillment_queue()
        
        new_order = {
            "shopify_order_id": shopify_order_id,
            "shopify_order_number": shopify_order_number,
            "product_name": product_name,
            "supplier_url": supplier_url,
            "quantity": quantity,
            "shipping_address": shipping_address,
            "status": "manual",
            "created_at": datetime.utcnow().isoformat()
        }
        
        queue.append(new_order)
        save_fulfillment_queue(queue)
        
        return {
            "success": True,
            "message": f"Order #{shopify_order_number} added to queue",
            "order": new_order
        }
        
    except Exception as e:
        logger.error(f"Failed to add to queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/queue/{shopify_order_id}")
async def remove_from_queue(shopify_order_id: str):
    """
    Remove an order from the fulfillment queue.
    """
    try:
        queue = load_fulfillment_queue()
        
        original_len = len(queue)
        queue = [o for o in queue if o.get('shopify_order_id') != shopify_order_id]
        
        if len(queue) == original_len:
            raise HTTPException(status_code=404, detail="Order not found in queue")
        
        save_fulfillment_queue(queue)
        
        return {
            "success": True,
            "message": f"Order {shopify_order_id} removed from queue"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove from queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))
