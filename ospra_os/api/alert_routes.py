"""
OSPRA INTELLIGENCE - OI ALERT API ROUTES
=========================================

REST API and WebSocket endpoints for Oi alerts.

@author OspraOS
@date January 2025
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging

from ..services.oi_alerts import (
    alert_store, 
    oi_alert_service, 
    Alert, 
    AlertPreferences,
    AlertType,
    AlertPriority,
)
from ..auth.jwt_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oi/alerts", tags=["oi-alerts"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AlertActionRequest(BaseModel):
    action: str
    params: Dict[str, Any] = {}


class AlertPreferencesUpdate(BaseModel):
    enabled: Optional[bool] = None
    types: Optional[List[str]] = None
    min_priority: Optional[str] = None
    email_notifications: Optional[bool] = None
    quiet_hours: Optional[Dict[str, str]] = None
    max_alerts_per_hour: Optional[int] = None


class AlertsResponse(BaseModel):
    alerts: List[Dict[str, Any]]
    unread_count: int
    total_count: int


# =============================================================================
# REST ENDPOINTS
# =============================================================================

@router.get("", response_model=AlertsResponse)
async def get_alerts(
    status: str = Query("all", description="Filter: all, read, unread"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Get alerts for the current user"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    
    alerts = alert_store.get_user_alerts(
        user_id=user_id,
        status=status,
        priority=priority,
        alert_type=type,
        limit=limit,
    )
    
    return AlertsResponse(
        alerts=[a.dict() for a in alerts],
        unread_count=alert_store.get_unread_count(user_id),
        total_count=len(alert_store.get_user_alerts(user_id, limit=1000)),
    )


@router.post("/{alert_id}/read")
async def mark_alert_read(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Mark an alert as read"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    
    if alert_store.mark_read(user_id, alert_id):
        return {"success": True, "message": "Alert marked as read"}
    
    raise HTTPException(status_code=404, detail="Alert not found")


@router.post("/read-all")
async def mark_all_alerts_read(
    current_user: dict = Depends(get_current_user),
):
    """Mark all alerts as read"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    count = alert_store.mark_all_read(user_id)
    return {"success": True, "count": count, "message": f"Marked {count} alerts as read"}


@router.delete("/{alert_id}")
async def dismiss_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Dismiss/delete an alert"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    
    if alert_store.dismiss(user_id, alert_id):
        return {"success": True, "message": "Alert dismissed"}
    
    raise HTTPException(status_code=404, detail="Alert not found")


@router.post("/{alert_id}/action")
async def execute_alert_action(
    alert_id: str,
    request: AlertActionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Execute an action from an alert"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    
    # Get the alert first
    alerts = alert_store.get_user_alerts(user_id, limit=100)
    alert = next((a for a in alerts if a.id == alert_id), None)
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Execute the action based on type
    action = request.action
    params = request.params
    result = None
    
    try:
        if action == "deploy":
            # TODO: Call deployment service
            result = f"Queued deployment for product {params.get('product_id', 'unknown')}"
            
        elif action == "add_to_watchlist":
            # TODO: Add to watchlist
            result = f"Added to watchlist"
            
        elif action == "analyze":
            # TODO: Trigger analysis
            result = f"Analysis started for product {params.get('product_id', 'unknown')}"
            
        elif action == "approve":
            # TODO: Approve action
            result = f"Action {params.get('action_id', 'unknown')} approved"
            
        elif action == "decline":
            # TODO: Decline action
            result = f"Action {params.get('action_id', 'unknown')} declined"
            
        elif action == "view":
            result = f"View product {params.get('product_id', 'unknown')}"
            
        elif action == "search_niche":
            result = f"Searching niche: {params.get('niche', 'unknown')}"
            
        else:
            result = f"Action '{action}' acknowledged"
        
        # Mark alert as actioned
        alert_store.mark_actioned(user_id, alert_id, result)
        
        return {
            "success": True,
            "action": action,
            "result": result,
            "message": result,
        }
        
    except Exception as e:
        logger.error(f"Failed to execute alert action: {e}")
        raise HTTPException(status_code=500, detail="Alert action failed. Please try again.")


@router.get("/preferences")
async def get_alert_preferences(
    current_user: dict = Depends(get_current_user),
):
    """Get user's alert preferences"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    prefs = alert_store.get_preferences(user_id)
    return prefs.dict()


@router.put("/preferences")
async def update_alert_preferences(
    request: AlertPreferencesUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update user's alert preferences"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    
    # Get current preferences
    current = alert_store.get_preferences(user_id)
    
    # Update only provided fields
    update_data = request.dict(exclude_unset=True)
    
    if "types" in update_data:
        update_data["types"] = [AlertType(t) for t in update_data["types"]]
    
    if "min_priority" in update_data:
        update_data["min_priority"] = AlertPriority(update_data["min_priority"])
    
    for key, value in update_data.items():
        if value is not None:
            setattr(current, key, value)
    
    alert_store.set_preferences(user_id, current)
    
    return {"success": True, "preferences": current.dict()}


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

@router.websocket("/ws")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alerts"""
    await websocket.accept()
    
    user_id = None
    
    try:
        # Wait for authentication message
        auth_data = await websocket.receive_json()
        
        if auth_data.get("type") != "auth":
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close()
            return
        
        # TODO: Validate token
        token = auth_data.get("token")
        user_id = auth_data.get("user_id")  # For now, trust the client
        
        if not user_id:
            await websocket.send_json({"type": "error", "message": "Invalid authentication"})
            await websocket.close()
            return
        
        # Register connection
        alert_store.add_connection(user_id, websocket)
        
        # Send confirmation
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Oi alerts",
            "unread_count": alert_store.get_unread_count(user_id),
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif data.get("type") == "mark_read":
                alert_id = data.get("alert_id")
                if alert_id:
                    alert_store.mark_read(user_id, alert_id)
                    await websocket.send_json({
                        "type": "read_confirmed",
                        "alert_id": alert_id,
                        "unread_count": alert_store.get_unread_count(user_id),
                    })
            
            elif data.get("type") == "dismiss":
                alert_id = data.get("alert_id")
                if alert_id:
                    alert_store.dismiss(user_id, alert_id)
                    await websocket.send_json({
                        "type": "dismissed",
                        "alert_id": alert_id,
                    })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    
    finally:
        if user_id:
            alert_store.remove_connection(user_id, websocket)


# =============================================================================
# ALTERNATIVE WS ROUTE (simpler path)
# =============================================================================

# Create a separate router for the WebSocket at a simpler path
ws_router = APIRouter()

@ws_router.websocket("/ws/oi/alerts")
async def websocket_alerts_root(websocket: WebSocket):
    """WebSocket endpoint at root path for easier access"""
    await websocket.accept()
    
    user_id = None
    
    try:
        # For now, use a simpler auth approach
        # In production, validate JWT from query param or first message
        
        # Wait for any message to get user_id
        try:
            auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
            user_id = auth_data.get("user_id")
        except asyncio.TimeoutError:
            # Use a default/anonymous connection for demo
            user_id = "anonymous"
        
        # Register connection
        alert_store.add_connection(user_id, websocket)
        
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Oi alerts",
            "unread_count": alert_store.get_unread_count(user_id),
        })
        
        # Keep alive
        while True:
            try:
                data = await websocket.receive_json()
                
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
            except Exception:
                break
    
    except WebSocketDisconnect:
        pass
    
    finally:
        if user_id:
            alert_store.remove_connection(user_id, websocket)


import asyncio
