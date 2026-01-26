"""
Dashboard Routes for Ospra OS
=============================

Main dashboard endpoints for the frontend application.

SECURITY: All endpoints require JWT authentication.
User ID is extracted from verified JWT tokens, not query parameters.

Endpoints:
- GET /api/dashboard/overview - Dashboard summary stats
- GET /api/dashboard/products - Product performance data
- GET /api/dashboard/emails - Email automation stats
- GET /api/dashboard/shopify - Shopify store metrics
- GET /api/dashboard/api-status - External API status

Author: OspraOS
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException

from ospra_os.routers import RouterRegistry
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# =============================================================================
# DASHBOARD OVERVIEW
# =============================================================================

@router.get("/overview")
async def dashboard_overview(current_user: User = Depends(get_current_user)):
    """
    Get dashboard overview with key metrics.

    SECURITY: Requires JWT authentication.

    Returns summary statistics for:
    - Active products
    - Recent orders
    - Email activity
    - AI actions pending
    """
    # This is a placeholder - the actual implementation
    # will be migrated from main.py
    return {
        "status": "ok",
        "message": "Dashboard overview endpoint - implementation in main.py",
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": current_user.id
    }


@router.get("/products")
async def dashboard_products(current_user: User = Depends(get_current_user)):
    """
    Get product performance data for dashboard.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Dashboard products endpoint - implementation in main.py",
        "products": [],
        "user_id": current_user.id
    }


@router.get("/emails")
async def dashboard_emails(current_user: User = Depends(get_current_user)):
    """
    Get email automation statistics.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Dashboard emails endpoint - implementation in main.py",
        "stats": {},
        "user_id": current_user.id
    }


@router.get("/shopify")
async def dashboard_shopify(current_user: User = Depends(get_current_user)):
    """
    Get Shopify store metrics.

    SECURITY: Requires JWT authentication.
    """
    return {
        "status": "ok",
        "message": "Dashboard shopify endpoint - implementation in main.py",
        "metrics": {},
        "user_id": current_user.id
    }


@router.get("/api-status")
async def dashboard_api_status(current_user: User = Depends(get_current_user)):
    """
    Get external API connection status.

    SECURITY: Requires JWT authentication.

    Checks connectivity to:
    - AI providers
    - Shopify
    - AliExpress
    - Payment providers
    """
    status = {
        "timestamp": datetime.utcnow().isoformat(),
        "services": {},
        "user_id": current_user.id
    }

    # Check AI providers
    ai_providers = {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "google": bool(os.getenv("GOOGLE_AI_API_KEY")),
        "xai": bool(os.getenv("XAI_API_KEY")),
        "groq": bool(os.getenv("GROQ_API_KEY")),
    }
    status["services"]["ai_providers"] = {
        "configured": [k for k, v in ai_providers.items() if v],
        "status": "configured" if any(ai_providers.values()) else "not_configured"
    }

    # Check e-commerce
    status["services"]["shopify"] = {
        "status": "configured" if os.getenv("SHOPIFY_API_KEY") else "not_configured"
    }

    status["services"]["aliexpress"] = {
        "status": "configured" if os.getenv("ALIEXPRESS_APP_KEY") else "not_configured"
    }

    # Check payments
    status["services"]["lemonsqueezy"] = {
        "status": "configured" if os.getenv("LEMONSQUEEZY_API_KEY") else "not_configured"
    }

    return status


# Register router
RouterRegistry.register(router, prefix="", tags=["Dashboard"])

logger.info("[SUCCESS] Dashboard router loaded")
