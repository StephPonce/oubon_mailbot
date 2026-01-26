"""
Fulfillment API Routes
======================

Endpoints for auto-fulfillment management:
- View pending fulfillments
- Manually mark orders as fulfilled
- Add tracking numbers
- Check fulfillment status
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

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
    preferred_supplier: str = "cj_dropshipping"  # or "aliexpress"
    auto_notify_customer: bool = True
    fallback_to_manual: bool = True


# ============================================================================
# STATUS & OVERVIEW
# ============================================================================

@router.get("/status")
async def fulfillment_status(current_user: User = Depends(get_current_user)):
    """
    Get fulfillment system status.
    
    Shows which suppliers are configured and ready.
    """
    import os
    
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
        }
    }


@router.get("/queue")
async def get_fulfillment_queue(current_user: User = Depends(get_current_user)):
    """
    Get all pending fulfillment orders.
    
    Returns orders that need manual fulfillment or are awaiting tracking.
    """
    try:
        from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
        
        engine = get_fulfillment_engine()
        pending = await engine.get_pending_fulfillments()
        
        return {
            "success": True,
            "pending_count": len(pending),
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
async def get_queue_stats(current_user: User = Depends(get_current_user)):
    """
    Get fulfillment queue statistics.
    """
    try:
        from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
        
        engine = get_fulfillment_engine()
        pending = await engine.get_pending_fulfillments()
        
        # Count by status
        stats = {
            "total_pending": len(pending),
            "manual_required": 0,
            "awaiting_tracking": 0,
            "by_supplier": {}
        }
        
        for order in pending:
            status = order.get('status', 'unknown')
            if status == 'manual':
                stats['manual_required'] += 1
            elif status == 'ordered':
                stats['awaiting_tracking'] += 1
            
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
async def add_tracking_number(request: AddTrackingRequest, current_user: User = Depends(get_current_user)):
    """
    Add tracking number to a Shopify order.
    
    Creates fulfillment in Shopify and notifies customer.
    """
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
        
    except Exception as e:
        logger.error(f"Failed to add tracking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mark-fulfilled")
async def mark_order_fulfilled(request: MarkFulfilledRequest, current_user: User = Depends(get_current_user)):
    """
    Mark a manual fulfillment order as completed.
    
    Updates Shopify with tracking and removes from manual queue.
    """
    try:
        from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
        
        engine = get_fulfillment_engine()
        result = await engine.mark_fulfilled(
            shopify_order_id=request.shopify_order_id,
            tracking_number=request.tracking_number,
            carrier=request.carrier
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to mark fulfilled: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SUPPLIER TRACKING CHECK
# ============================================================================

@router.get("/tracking/check/{supplier}/{order_id}")
async def check_supplier_tracking(supplier: str, order_id: str, current_user: User = Depends(get_current_user)):
    """
    Check tracking status from a supplier.
    
    Supported suppliers:
    - cj: CJ Dropshipping order ID
    """
    try:
        from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
        
        engine = get_fulfillment_engine()
        
        if supplier.lower() == "cj":
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
async def sync_all_tracking(current_user: User = Depends(get_current_user)):
    """
    Sync tracking numbers from all suppliers.
    
    Checks CJ Dropshipping orders for tracking updates
    and syncs them to Shopify.
    """
    try:
        from ospra_os.fulfillment.auto_fulfillment import get_fulfillment_engine
        import json
        import os
        
        engine = get_fulfillment_engine()
        
        # Load fulfillment queue
        queue_file = os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'data', 'fulfillment_queue.json'
        )
        
        if not os.path.exists(queue_file):
            return {
                "success": True,
                "message": "No orders in queue",
                "synced": 0
            }
        
        with open(queue_file, 'r') as f:
            queue = json.load(f)
        
        synced = 0
        results = []
        
        for order in queue:
            if order.get('status') != 'ordered':
                continue
            
            supplier_order_id = order.get('supplier_order_id')
            supplier_type = order.get('supplier_type')
            
            if supplier_type == 'cj_dropshipping' and supplier_order_id:
                tracking = await engine.check_cj_tracking(supplier_order_id)
                
                if tracking and tracking.get('tracking_number'):
                    # Update Shopify
                    result = await engine.update_tracking(
                        shopify_order_id=order.get('shopify_order_id'),
                        tracking_number=tracking['tracking_number'],
                        carrier=tracking.get('carrier', 'Other')
                    )
                    
                    if result.get('success'):
                        synced += 1
                        results.append({
                            "order": order.get('shopify_order_number'),
                            "tracking": tracking['tracking_number'],
                            "status": "synced"
                        })
        
        return {
            "success": True,
            "synced": synced,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to sync tracking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SETTINGS
# ============================================================================

@router.get("/settings")
async def get_fulfillment_settings(current_user: User = Depends(get_current_user)):
    """Get current fulfillment automation settings"""
    import os
    import json
    
    settings_file = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'data', 'fulfillment_settings.json'
    )
    
    default_settings = {
        "auto_fulfill_enabled": False,
        "preferred_supplier": "cj_dropshipping",
        "auto_notify_customer": True,
        "fallback_to_manual": True
    }
    
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            return json.load(f)
    
    return default_settings


@router.post("/settings")
async def update_fulfillment_settings(settings: FulfillmentSettings, current_user: User = Depends(get_current_user)):
    """Update fulfillment automation settings"""
    import os
    import json
    
    settings_file = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'data', 'fulfillment_settings.json'
    )
    
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    
    with open(settings_file, 'w') as f:
        json.dump(settings.dict(), f, indent=2)
    
    return {
        "success": True,
        "settings": settings.dict()
    }
