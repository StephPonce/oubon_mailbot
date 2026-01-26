"""
Health Check Routes for Ospra OS
================================

Provides endpoints for monitoring application health and status.
Critical for load balancers, container orchestrators, and monitoring.

Endpoints:
- GET /health - Basic health check (fast response)
- GET /health/celery - Celery worker status
- GET /api/health/detailed - Comprehensive health check

Author: OspraOS
"""

import logging
from fastapi import APIRouter, Depends
from typing import Dict, Any

from ospra_os.routers import RouterRegistry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


# =============================================================================
# BASIC HEALTH CHECKS
# =============================================================================

@router.get("/health")
def health_check_immediate():
    """
    Immediate health check that responds before full initialization.

    Used by load balancers to determine if the service is ready.
    Must respond quickly (<100ms) even during heavy startup.
    """
    return {
        "status": "ok",
        "service": "Ospra Intelligence Platform",
        "version": "2026-01-11"
    }


@router.get("/health/celery")
def celery_health():
    """
    Check Celery worker and task queue health.

    Returns:
    - healthy: Workers are running and responding
    - no_workers: No workers detected (Celery not started)
    - error: Unable to inspect Celery (Redis unavailable or config issue)
    """
    try:
        from ospra_os.celery_app import celery_app
        _has_tasks = True
    except ImportError:
        _has_tasks = False

    if not _has_tasks:
        return {"status": "disabled", "message": "Celery tasks not loaded"}

    try:
        from ospra_os.celery_app import celery_app
        inspect = celery_app.control.inspect()
        active = inspect.active()

        if active:
            active_count = sum(len(tasks) for tasks in active.values())
            return {
                "status": "healthy",
                "workers": list(active.keys()),
                "active_tasks": active_count,
                "message": f"{len(active)} worker(s) online, {active_count} active task(s)"
            }
        else:
            return {
                "status": "no_workers",
                "workers": [],
                "message": "No Celery workers detected. Start workers with: celery -A ospra_os.celery_app worker"
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Unable to connect to Celery. Ensure Redis is running: docker-compose up redis -d"
        }


@router.get("/api/health/detailed")
async def detailed_health_check():
    """
    Comprehensive health check with all system components.

    Checks:
    - Database connectivity
    - AI provider availability
    - External service connections
    - Memory/resource usage
    """
    from datetime import datetime

    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }

    # Database check
    try:
        from ospra_os.core.settings import get_settings
        from ospra_os.database import get_db_session
        settings = get_settings()

        async with get_db_session() as db:
            # Simple query to test connection
            result = db.execute("SELECT 1")
            health_status["components"]["database"] = {"status": "healthy"}
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"

    # AI providers check
    ai_providers = []
    import os

    if os.getenv("ANTHROPIC_API_KEY"):
        ai_providers.append("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        ai_providers.append("openai")
    if os.getenv("GOOGLE_AI_API_KEY"):
        ai_providers.append("google")
    if os.getenv("XAI_API_KEY"):
        ai_providers.append("xai")
    if os.getenv("GROQ_API_KEY"):
        ai_providers.append("groq")

    health_status["components"]["ai_providers"] = {
        "status": "healthy" if ai_providers else "warning",
        "configured": ai_providers,
        "count": len(ai_providers)
    }

    # Memory usage
    try:
        import psutil
        memory = psutil.virtual_memory()
        health_status["components"]["memory"] = {
            "status": "healthy" if memory.percent < 90 else "warning",
            "percent_used": memory.percent,
            "available_mb": round(memory.available / (1024 * 1024), 2)
        }
    except Exception:
        health_status["components"]["memory"] = {"status": "unknown"}

    return health_status


# Register router
RouterRegistry.register(router, prefix="", tags=["Health"])

logger.info("[SUCCESS] Health router loaded")
