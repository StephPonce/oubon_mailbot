"""
OSPRA INTELLIGENCE - OI ALERT SERVICE
======================================

Real-time alerts from Oi to users.
Proactive notifications for:
- Trending products discovered
- Price changes on tracked products
- Action recommendations
- Market opportunities
- Competitor movements

@author OspraOS
@date January 2025
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MODELS
# =============================================================================

class AlertType(str, Enum):
    TRENDING_PRODUCT = "trending_product"
    PRICE_DROP = "price_drop"
    PRICE_INCREASE = "price_increase"
    ACTION_NEEDED = "action_needed"
    OPPORTUNITY = "opportunity"
    WARNING = "warning"
    PRODUCT_FOUND = "product_found"
    COMPETITOR_ALERT = "competitor_alert"
    STOCK_LOW = "stock_low"
    MARKET_SHIFT = "market_shift"


class AlertPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertAction(BaseModel):
    """An action that can be taken from an alert"""
    id: str
    label: str
    action: str  # 'deploy', 'add_to_watchlist', 'approve', 'decline', 'analyze', etc.
    primary: bool = False
    params: Dict[str, Any] = {}


class Alert(BaseModel):
    """A single alert from Oi"""
    id: str
    user_id: str
    type: AlertType
    priority: AlertPriority
    title: str
    message: str
    data: Dict[str, Any] = {}
    actions: List[AlertAction] = []
    read: bool = False
    actioned: bool = False
    action_result: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    
    # For product alerts
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    score: Optional[int] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AlertPreferences(BaseModel):
    """User's alert preferences"""
    enabled: bool = True
    types: List[AlertType] = list(AlertType)
    min_priority: AlertPriority = AlertPriority.LOW
    email_notifications: bool = False
    quiet_hours: Optional[Dict[str, str]] = None  # {"start": "22:00", "end": "08:00"}
    max_alerts_per_hour: int = 10


# =============================================================================
# ALERT STORAGE (In-memory for now, can move to Redis/DB)
# =============================================================================

class AlertStore:
    """In-memory alert storage with user separation"""
    
    def __init__(self):
        self._alerts: Dict[str, List[Alert]] = {}  # user_id -> alerts
        self._preferences: Dict[str, AlertPreferences] = {}  # user_id -> prefs
        self._connections: Dict[str, List[WebSocket]] = {}  # user_id -> websockets
    
    def get_user_alerts(
        self, 
        user_id: str, 
        status: str = "all",
        priority: Optional[str] = None,
        alert_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Alert]:
        """Get alerts for a user with optional filters"""
        alerts = self._alerts.get(user_id, [])
        
        # Filter by status
        if status == "unread":
            alerts = [a for a in alerts if not a.read]
        elif status == "read":
            alerts = [a for a in alerts if a.read]
        
        # Filter by priority
        if priority:
            alerts = [a for a in alerts if a.priority == priority]
        
        # Filter by type
        if alert_type:
            alerts = [a for a in alerts if a.type == alert_type]
        
        # Remove expired
        now = datetime.utcnow()
        alerts = [a for a in alerts if not a.expires_at or a.expires_at > now]
        
        # Sort by created_at descending
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        
        return alerts[:limit]
    
    def get_unread_count(self, user_id: str) -> int:
        """Get count of unread alerts"""
        alerts = self._alerts.get(user_id, [])
        return len([a for a in alerts if not a.read])
    
    def add_alert(self, alert: Alert) -> bool:
        """Add an alert and notify via WebSocket"""
        user_id = alert.user_id
        
        # Check preferences
        prefs = self._preferences.get(user_id, AlertPreferences())
        if not prefs.enabled:
            return False
        
        if alert.type not in prefs.types:
            return False
        
        priority_order = {AlertPriority.LOW: 0, AlertPriority.MEDIUM: 1, AlertPriority.HIGH: 2}
        if priority_order[alert.priority] < priority_order[prefs.min_priority]:
            return False
        
        # Check quiet hours
        if prefs.quiet_hours and alert.priority != AlertPriority.HIGH:
            now = datetime.utcnow()
            start = datetime.strptime(prefs.quiet_hours.get("start", "22:00"), "%H:%M").time()
            end = datetime.strptime(prefs.quiet_hours.get("end", "08:00"), "%H:%M").time()
            if start <= now.time() <= end:
                return False
        
        # Add to store
        if user_id not in self._alerts:
            self._alerts[user_id] = []
        
        self._alerts[user_id].insert(0, alert)
        
        # Trim old alerts (keep last 100)
        self._alerts[user_id] = self._alerts[user_id][:100]
        
        # Notify via WebSocket
        asyncio.create_task(self._notify_user(user_id, alert))
        
        return True
    
    def mark_read(self, user_id: str, alert_id: str) -> bool:
        """Mark an alert as read"""
        alerts = self._alerts.get(user_id, [])
        for alert in alerts:
            if alert.id == alert_id:
                alert.read = True
                return True
        return False
    
    def mark_all_read(self, user_id: str) -> int:
        """Mark all alerts as read, return count"""
        alerts = self._alerts.get(user_id, [])
        count = 0
        for alert in alerts:
            if not alert.read:
                alert.read = True
                count += 1
        return count
    
    def dismiss(self, user_id: str, alert_id: str) -> bool:
        """Remove an alert"""
        if user_id in self._alerts:
            self._alerts[user_id] = [a for a in self._alerts[user_id] if a.id != alert_id]
            return True
        return False
    
    def mark_actioned(self, user_id: str, alert_id: str, result: str) -> bool:
        """Mark an alert as actioned"""
        alerts = self._alerts.get(user_id, [])
        for alert in alerts:
            if alert.id == alert_id:
                alert.actioned = True
                alert.action_result = result
                alert.read = True
                return True
        return False
    
    def get_preferences(self, user_id: str) -> AlertPreferences:
        """Get user's alert preferences"""
        return self._preferences.get(user_id, AlertPreferences())
    
    def set_preferences(self, user_id: str, prefs: AlertPreferences):
        """Set user's alert preferences"""
        self._preferences[user_id] = prefs
    
    # WebSocket management
    def add_connection(self, user_id: str, websocket: WebSocket):
        """Add a WebSocket connection for a user"""
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
    
    def remove_connection(self, user_id: str, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]
    
    async def _notify_user(self, user_id: str, alert: Alert):
        """Send alert to user via WebSocket"""
        connections = self._connections.get(user_id, [])
        
        message = {
            "type": "alert",
            "alert": alert.dict()
        }
        
        dead_connections = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send alert via WebSocket: {e}")
                dead_connections.append(ws)
        
        # Clean up dead connections
        for ws in dead_connections:
            self.remove_connection(user_id, ws)


# Global store instance
alert_store = AlertStore()


# =============================================================================
# ALERT SERVICE
# =============================================================================

class OiAlertService:
    """Service for creating and managing Oi alerts"""
    
    def __init__(self, store: AlertStore = None):
        self.store = store or alert_store
    
    def create_alert(
        self,
        user_id: str,
        type: AlertType,
        title: str,
        message: str,
        priority: AlertPriority = AlertPriority.MEDIUM,
        data: Dict[str, Any] = None,
        actions: List[Dict[str, Any]] = None,
        product_id: str = None,
        product_name: str = None,
        score: int = None,
        expires_in_hours: int = 24,
    ) -> Optional[Alert]:
        """Create and send an alert to a user"""
        
        alert_actions = []
        if actions:
            for action in actions:
                alert_actions.append(AlertAction(
                    id=action.get("id", str(uuid.uuid4())),
                    label=action.get("label", "Action"),
                    action=action.get("action", "unknown"),
                    primary=action.get("primary", False),
                    params=action.get("params", {}),
                ))
        
        alert = Alert(
            id=str(uuid.uuid4()),
            user_id=user_id,
            type=type,
            priority=priority,
            title=title,
            message=message,
            data=data or {},
            actions=alert_actions,
            product_id=product_id,
            product_name=product_name,
            score=score,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours) if expires_in_hours else None,
        )
        
        if self.store.add_alert(alert):
            logger.info(f"Alert created for user {user_id}: {title}")
            return alert
        
        return None
    
    # Convenience methods for common alert types
    
    def alert_trending_product(
        self,
        user_id: str,
        product_id: str,
        product_name: str,
        score: int,
        niche: str = None,
        reason: str = None,
    ) -> Optional[Alert]:
        """Alert user about a trending product"""
        return self.create_alert(
            user_id=user_id,
            type=AlertType.TRENDING_PRODUCT,
            priority=AlertPriority.HIGH if score >= 90 else AlertPriority.MEDIUM,
            title=f"[HOT] Trending: {product_name[:30]}",
            message=reason or f"Score {score}/100 in {niche or 'your niche'}. High demand detected.",
            product_id=product_id,
            product_name=product_name,
            score=score,
            data={"niche": niche},
            actions=[
                {"id": "deploy", "label": "Deploy", "action": "deploy", "primary": True, "params": {"product_id": product_id}},
                {"id": "watchlist", "label": "Watch", "action": "add_to_watchlist", "params": {"product_id": product_id}},
                {"id": "analyze", "label": "Analyze", "action": "analyze", "params": {"product_id": product_id}},
            ],
        )
    
    def alert_price_change(
        self,
        user_id: str,
        product_id: str,
        product_name: str,
        old_price: float,
        new_price: float,
        is_drop: bool = True,
    ) -> Optional[Alert]:
        """Alert user about a price change"""
        change_pct = abs((new_price - old_price) / old_price * 100)
        
        return self.create_alert(
            user_id=user_id,
            type=AlertType.PRICE_DROP if is_drop else AlertType.PRICE_INCREASE,
            priority=AlertPriority.HIGH if change_pct >= 20 else AlertPriority.MEDIUM,
            title=f"{'[DECLINE]' if is_drop else '[TREND]'} Price {'drop' if is_drop else 'increase'}: {product_name[:25]}",
            message=f"${old_price:.2f} → ${new_price:.2f} ({change_pct:.1f}% {'down' if is_drop else 'up'})",
            product_id=product_id,
            product_name=product_name,
            data={"old_price": old_price, "new_price": new_price, "change_pct": change_pct},
            actions=[
                {"id": "view", "label": "View Product", "action": "view", "primary": True, "params": {"product_id": product_id}},
            ] if not is_drop else [
                {"id": "deploy", "label": "Deploy Now", "action": "deploy", "primary": True, "params": {"product_id": product_id}},
                {"id": "watchlist", "label": "Watch", "action": "add_to_watchlist", "params": {"product_id": product_id}},
            ],
        )
    
    def alert_action_recommended(
        self,
        user_id: str,
        action_id: str,
        action_type: str,
        title: str,
        description: str,
        confidence: float,
    ) -> Optional[Alert]:
        """Alert user about a recommended action"""
        return self.create_alert(
            user_id=user_id,
            type=AlertType.ACTION_NEEDED,
            priority=AlertPriority.HIGH if confidence >= 0.9 else AlertPriority.MEDIUM,
            title=f"[FAST] {title}",
            message=f"{description} ({int(confidence * 100)}% confidence)",
            data={"action_id": action_id, "action_type": action_type, "confidence": confidence},
            actions=[
                {"id": "approve", "label": "Approve", "action": "approve", "primary": True, "params": {"action_id": action_id}},
                {"id": "decline", "label": "Decline", "action": "decline", "params": {"action_id": action_id}},
                {"id": "details", "label": "Details", "action": "view_action", "params": {"action_id": action_id}},
            ],
        )
    
    def alert_market_opportunity(
        self,
        user_id: str,
        niche: str,
        opportunity: str,
        confidence: float,
    ) -> Optional[Alert]:
        """Alert user about a market opportunity"""
        return self.create_alert(
            user_id=user_id,
            type=AlertType.OPPORTUNITY,
            priority=AlertPriority.MEDIUM,
            title=f"[TIP] Opportunity in {niche}",
            message=opportunity,
            data={"niche": niche, "confidence": confidence},
            actions=[
                {"id": "explore", "label": "Explore", "action": "search_niche", "primary": True, "params": {"niche": niche}},
            ],
        )
    
    def alert_warning(
        self,
        user_id: str,
        title: str,
        message: str,
        severity: str = "medium",
    ) -> Optional[Alert]:
        """Send a warning alert"""
        return self.create_alert(
            user_id=user_id,
            type=AlertType.WARNING,
            priority=AlertPriority.HIGH if severity == "high" else AlertPriority.MEDIUM,
            title=f"[WARNING] {title}",
            message=message,
        )


# Global service instance
oi_alert_service = OiAlertService()
