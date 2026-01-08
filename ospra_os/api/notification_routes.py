"""
Notification API Routes - REAL DATA ONLY
=========================================

Endpoints:
- GET /api/notifications - Get all notifications
- POST /api/notifications/{id}/read - Mark as read
- POST /api/notifications/read-all - Mark all as read
- DELETE /api/notifications/{id} - Delete notification
- POST /api/notifications/create - Create notification (for system use)
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import uuid

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database.multi_store_models import User

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

# In-memory storage (replace with DB table in production)
_notifications_store: dict[int, list] = {}


class NotificationCreate(BaseModel):
    type: str = "system"  # trend, price_drop, alert, product, system, ai
    title: str
    message: str
    action_url: Optional[str] = None
    action_tab: Optional[str] = None


def get_user_notifications(user_id: int) -> list:
    """Get notifications for a user. Returns empty list if none exist."""
    if user_id not in _notifications_store:
        _notifications_store[user_id] = []
    return _notifications_store[user_id]


def add_notification(user_id: int, notification: dict) -> dict:
    """Add a notification for a user."""
    if user_id not in _notifications_store:
        _notifications_store[user_id] = []
    
    notification["id"] = str(uuid.uuid4())
    notification["timestamp"] = datetime.utcnow().isoformat()
    notification["read"] = False
    
    # Add to front of list (newest first)
    _notifications_store[user_id].insert(0, notification)
    
    # Keep only last 100 notifications
    _notifications_store[user_id] = _notifications_store[user_id][:100]
    
    return notification


@router.get("")
async def get_notifications(user: User = Depends(get_current_user), limit: int = 50):
    """Get user's notifications."""
    notifications = get_user_notifications(user.id)
    return {
        "success": True,
        "notifications": notifications[:limit],
        "unread_count": sum(1 for n in notifications if not n.get("read", False)),
        "total": len(notifications)
    }


@router.post("/{notification_id}/read")
async def mark_as_read(notification_id: str, user: User = Depends(get_current_user)):
    """Mark a notification as read."""
    notifications = get_user_notifications(user.id)
    
    for n in notifications:
        if n["id"] == notification_id:
            n["read"] = True
            return {"success": True}
    
    raise HTTPException(status_code=404, detail="Notification not found")


@router.post("/read-all")
async def mark_all_as_read(user: User = Depends(get_current_user)):
    """Mark all notifications as read."""
    notifications = get_user_notifications(user.id)
    for n in notifications:
        n["read"] = True
    return {"success": True, "message": "All notifications marked as read"}


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str, user: User = Depends(get_current_user)):
    """Delete a notification."""
    if user.id not in _notifications_store:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    original_len = len(_notifications_store[user.id])
    _notifications_store[user.id] = [n for n in _notifications_store[user.id] if n["id"] != notification_id]
    
    if len(_notifications_store[user.id]) == original_len:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"success": True}


@router.post("/create")
async def create_notification(notification: NotificationCreate, user: User = Depends(get_current_user)):
    """Create a new notification (for testing or manual creation)."""
    new_notification = add_notification(user.id, {
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "action_url": notification.action_url,
        "action_tab": notification.action_tab,
    })
    return {"success": True, "notification": new_notification}


# ============================================================================
# UTILITY FUNCTIONS - Call these from other modules to create real notifications
# ============================================================================

def notify_user(user_id: int, type: str, title: str, message: str, 
                action_url: str = None, action_tab: str = None) -> dict:
    """
    Send a notification to a user. Call this from anywhere in the app.
    
    Example:
        from ospra_os.api.notification_routes import notify_user
        notify_user(user.id, "trend", "Hot Product Found!", "LED strips trending +340%", "/products")
    """
    return add_notification(user_id, {
        "type": type,
        "title": title,
        "message": message,
        "action_url": action_url,
        "action_tab": action_tab,
    })


def notify_trend_discovery(user_id: int, count: int, category: str = None) -> dict:
    """Notify user when Oi discovers new trending products."""
    msg = f"{count} high-potential products found"
    if category:
        msg += f" in {category}"
    return notify_user(user_id, "ai", "Oi discovered new trends", msg, "/products")


def notify_price_drop(user_id: int, product_name: str, old_price: float, new_price: float) -> dict:
    """Notify user about a supplier price drop."""
    savings = ((old_price - new_price) / old_price) * 100
    return notify_user(
        user_id, 
        "price_drop", 
        "Price Drop Alert", 
        f"{product_name} dropped {savings:.0f}% (${old_price:.2f} → ${new_price:.2f})",
        "/products"
    )


def notify_product_deployed(user_id: int, product_name: str, store_name: str) -> dict:
    """Notify user when a product is deployed to their store."""
    return notify_user(
        user_id,
        "product",
        "Product Deployed",
        f"{product_name} is now live on {store_name}",
        "/products"
    )


def notify_system_alert(user_id: int, title: str, message: str, action_url: str = None) -> dict:
    """Send a system notification."""
    return notify_user(user_id, "system", title, message, action_url)


def notify_ai_insight(user_id: int, title: str, message: str, action_url: str = "/") -> dict:
    """Send an AI insight notification."""
    return notify_user(user_id, "ai", title, message, action_url)
