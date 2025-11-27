"""
API routes for customer notifications
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from ospra_os.services.notifications import (
    get_notification_service,
    NotificationType,
    NotificationChannel,
    NotificationPriority
)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class NotificationResponse(BaseModel):
    type: str
    priority: str
    customer_id: str
    customer_name: str
    customer_email: str
    message: Optional[str]
    timestamp: str
    channels: List[str]


class SendNotificationRequest(BaseModel):
    customer_id: str
    customer_name: str
    customer_email: str
    notification_type: NotificationType
    message: str
    priority: NotificationPriority = NotificationPriority.MEDIUM
    channels: List[NotificationChannel] = [NotificationChannel.IN_APP]


@router.get("/recent", response_model=List[NotificationResponse])
async def get_recent_notifications(limit: int = Query(50, ge=1, le=200)):
    """
    Get recent customer notifications
    """
    service = get_notification_service()
    notifications = service.get_recent_notifications(limit=limit)

    return [
        NotificationResponse(
            type=n['type'],
            priority=n['priority'],
            customer_id=n.get('customer_id', ''),
            customer_name=n.get('customer_name', ''),
            customer_email=n.get('customer_email', ''),
            message=n.get('message', ''),
            timestamp=n['timestamp'],
            channels=[str(c) for c in n.get('channels', [])]
        )
        for n in notifications
    ]


@router.get("/by-type/{notification_type}", response_model=List[NotificationResponse])
async def get_notifications_by_type(
    notification_type: NotificationType,
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get notifications filtered by type
    """
    service = get_notification_service()
    notifications = service.get_notifications_by_type(notification_type, limit=limit)

    return [
        NotificationResponse(
            type=n['type'],
            priority=n['priority'],
            customer_id=n.get('customer_id', ''),
            customer_name=n.get('customer_name', ''),
            customer_email=n.get('customer_email', ''),
            message=n.get('message', ''),
            timestamp=n['timestamp'],
            channels=[str(c) for c in n.get('channels', [])]
        )
        for n in notifications
    ]


@router.get("/customer/{customer_id}", response_model=List[NotificationResponse])
async def get_customer_notifications(
    customer_id: str,
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get all notifications for a specific customer
    """
    service = get_notification_service()
    notifications = service.get_notifications_by_customer(customer_id, limit=limit)

    return [
        NotificationResponse(
            type=n['type'],
            priority=n['priority'],
            customer_id=n.get('customer_id', ''),
            customer_name=n.get('customer_name', ''),
            customer_email=n.get('customer_email', ''),
            message=n.get('message', ''),
            timestamp=n['timestamp'],
            channels=[str(c) for c in n.get('channels', [])]
        )
        for n in notifications
    ]


@router.post("/send")
async def send_custom_notification(request: SendNotificationRequest):
    """
    Send a custom notification
    """
    service = get_notification_service()

    notification = {
        "type": request.notification_type,
        "priority": request.priority,
        "customer_id": request.customer_id,
        "customer_name": request.customer_name,
        "customer_email": request.customer_email,
        "message": request.message,
        "timestamp": datetime.now().isoformat(),
        "channels": request.channels
    }

    await service._send_notification(notification)

    return {
        "message": "Notification sent successfully",
        "notification": notification
    }


@router.get("/stats")
async def get_notification_stats():
    """
    Get notification statistics
    """
    service = get_notification_service()
    all_notifications = service.get_recent_notifications(limit=1000)

    # Count by type
    by_type = {}
    for n in all_notifications:
        n_type = n['type']
        by_type[n_type] = by_type.get(n_type, 0) + 1

    # Count by priority
    by_priority = {}
    for n in all_notifications:
        priority = n['priority']
        by_priority[priority] = by_priority.get(priority, 0) + 1

    return {
        "total_notifications": len(all_notifications),
        "by_type": by_type,
        "by_priority": by_priority,
        "recent_count": len(all_notifications)
    }
