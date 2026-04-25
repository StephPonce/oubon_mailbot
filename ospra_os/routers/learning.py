"""
Learning Routes for Ospra OS
============================

Machine learning and AI training endpoints.

SECURITY: All endpoints require JWT authentication.
User ID is extracted from verified JWT tokens, not query parameters.

Endpoints:
- POST /api/learning/train - Trigger learning job
- GET /api/learning/report - Get learning report
- GET /api/learning/velocity - Get learning velocity stats
- POST /api/learning/demo - Run demo learning cycle

Author: OspraOS
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from ospra_os.routers import RouterRegistry
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/learning", tags=["Learning"])


@router.post("/train")
async def trigger_learning(current_user: User = Depends(get_current_user)):
    """
    Trigger AI learning job.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Learning endpoint - full implementation in main.py",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": current_user.id
    }


@router.get("/report")
async def learning_report(current_user: User = Depends(get_current_user)):
    """
    Get learning report.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Learning report endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.get("/velocity")
async def learning_velocity(current_user: User = Depends(get_current_user)):
    """
    Get learning velocity statistics.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Learning velocity endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


@router.post("/demo")
async def demo_learning(current_user: User = Depends(get_current_user)):
    """
    Run demo learning cycle.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Demo learning endpoint - full implementation in main.py",
        "user_id": current_user.id
    }


# Register router
RouterRegistry.register(router, prefix="", tags=["Learning"])

logger.info("[SUCCESS] Learning router loaded")
