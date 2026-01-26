"""
Dashboard Routes for Ospra OS
=============================

Main dashboard endpoints for the frontend application.

Endpoints:
- GET /api/dashboard/overview - Dashboard summary stats
- GET /api/dashboard/products - Product performance data
- GET /api/dashboard/emails - Email automation stats
- GET /api/dashboard/shopify - Shopify store metrics
- GET /api/dashboard/api-status - External API status

Author: OspraOS
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException

from ospra_os.routers import RouterRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# =============================================================================
# DASHBOARD OVERVIEW
# =============================================================================

@router.get("/overview")
async def dashboard_overview():
    """
    Get dashboard overview with key metrics.

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
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/products")
async def dashboard_products():
    """Get product performance data for dashboard."""
    return {
        "status": "ok",
        "message": "Dashboard products endpoint - implementation in main.py",
        "products": []
    }


@router.get("/emails")
async def dashboard_emails():
    """Get email automation statistics."""
    return {
        "status": "ok",
        "message": "Dashboard emails endpoint - implementation in main.py",
        "stats": {}
    }


@router.get("/shopify")
async def dashboard_shopify():
    """Get Shopify store metrics."""
    return {
        "status": "ok",
        "message": "Dashboard shopify endpoint - implementation in main.py",
        "metrics": {}
    }


@router.get("/api-status")
async def dashboard_api_status():
    """
    Get external API connection status.

    Checks connectivity to:
    - AI providers
    - Shopify
    - AliExpress
    - Payment providers
    """
    import os

    status = {
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
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
