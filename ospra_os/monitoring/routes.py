"""
Health Monitoring API Routes
All 24 health monitoring endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel

from ospra_os.monitoring.health_monitor import health_monitor
from ospra_os.monitoring.metrics_collector import metrics_collector
from ospra_os.monitoring.error_tracker import error_tracker
from ospra_os.monitoring.job_monitor import job_monitor

router = APIRouter(prefix="/api/health", tags=["health"])


# ================================================================
# REQUEST/RESPONSE MODELS
# ================================================================

class AcknowledgeRequest(BaseModel):
    notes: Optional[str] = None


class ResolveRequest(BaseModel):
    resolution: Optional[str] = None


# ================================================================
# SYSTEM HEALTH ENDPOINTS (1-3)
# ================================================================

@router.get("")
async def get_overall_health():
    """
    1. GET /api/health
    Returns: Overall system health status with service details
    """
    from datetime import datetime, timezone  # T87: timezone was missing → NameError on /api/health

    integrations = await health_monitor.check_all_integrations()
    overall_status = await health_monitor.get_overall_status()

    # Identify which services are degraded/disconnected
    critical_issues = []
    warnings = []

    for name, status in integrations.items():
        if status['status'] == 'DISCONNECTED':
            # Skip if not configured (optional service)
            if 'not configured' not in status.get('error', '').lower():
                critical_issues.append(f"{name}: {status.get('error', 'Connection failed')}")
        elif status['status'] == 'DEGRADED':
            warnings.append(f"{name}: {status.get('error', 'Performance issues')}")

    # Build service summary
    services = {}
    for name, status in integrations.items():
        services[name] = {
            "healthy": status['status'] in ['CONNECTED', 'HEALTHY'],
            "status": status['status'],
            "message": status.get('error') or status.get('note') or "Connected"
        }

    response = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_since": health_monitor.uptime_start.isoformat(),
        "services": services
    }

    # Add issues if any
    if critical_issues:
        response["critical_issues"] = critical_issues
    if warnings:
        response["warnings"] = warnings

    return response


@router.get("/detailed")
async def get_detailed_health():
    """
    2. GET /api/health/detailed
    Returns: Complete health snapshot
    """
    return await health_monitor.get_system_health()


@router.get("/summary")
async def get_health_summary():
    """
    3. GET /api/health/summary
    Returns: Dashboard summary cards
    """
    return await health_monitor.get_health_summary()


# ================================================================
# INTEGRATION HEALTH ENDPOINTS (4-7)
# ================================================================

@router.get("/integrations")
async def get_all_integrations():
    """
    4. GET /api/health/integrations
    Returns: All integration statuses
    """
    return await health_monitor.check_all_integrations()


@router.get("/integrations/{name}")
async def get_integration_status(name: str):
    """
    5. GET /api/health/integrations/{name}
    Returns: Specific integration status
    """
    result = await health_monitor.check_integration(name)
    if not result or result.get('status') == 'UNKNOWN':
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")
    return result


@router.post("/integrations/{name}/test")
async def test_integration(name: str):
    """
    6. POST /api/health/integrations/{name}/test
    Triggers: Connection test
    Returns: Test results
    """
    # Clear cache to force fresh test
    if name in health_monitor.integration_cache:
        del health_monitor.integration_cache[name]

    result = await health_monitor.check_integration(name)
    if result.get('status') == 'UNKNOWN':
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")

    return {
        "integration": name,
        "test_result": result,
        "tested_at": result.get('last_check')
    }


@router.get("/integrations/{name}/history")
async def get_integration_history(
    name: str,
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    7. GET /api/health/integrations/{name}/history
    Query params: hours
    Returns: Health check history (placeholder - would implement with DB)
    """
    return {
        "integration": name,
        "hours": hours,
        "history": []  # Would query from IntegrationHealthLog table
    }


# ================================================================
# JOB MONITORING ENDPOINTS (8-13)
# ================================================================

@router.get("/jobs")
async def get_all_jobs():
    """
    8. GET /api/health/jobs
    Returns: All job statuses
    """
    return await job_monitor.get_all_jobs()


@router.get("/jobs/{job_name}")
async def get_job_status(job_name: str):
    """
    9. GET /api/health/jobs/{job_name}
    Returns: Specific job status
    """
    result = await job_monitor.get_job_status(job_name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found")
    return result


@router.get("/jobs/{job_name}/history")
async def get_job_history(
    job_name: str,
    days: int = Query(default=7, ge=1, le=30)
):
    """
    10. GET /api/health/jobs/{job_name}/history
    Query params: days
    Returns: Job run history
    """
    history = await job_monitor.get_job_history(job_name, days)
    return {
        "job_name": job_name,
        "days": days,
        "runs": history
    }


@router.post("/jobs/{job_name}/trigger")
async def trigger_job(job_name: str):
    """
    11. POST /api/health/jobs/{job_name}/trigger
    Triggers: Manual job run
    """
    result = await job_monitor.trigger_job(job_name)
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('message'))
    return result


@router.post("/jobs/{job_name}/disable")
async def disable_job(job_name: str):
    """
    12. POST /api/health/jobs/{job_name}/disable
    Disables job
    """
    await job_monitor.disable_job(job_name)
    return {
        "success": True,
        "message": f"Job '{job_name}' disabled successfully"
    }


@router.post("/jobs/{job_name}/enable")
async def enable_job(job_name: str):
    """
    13. POST /api/health/jobs/{job_name}/enable
    Enables job
    """
    await job_monitor.enable_job(job_name)
    return {
        "success": True,
        "message": f"Job '{job_name}' enabled successfully"
    }


# ================================================================
# API PERFORMANCE ENDPOINTS (14-16)
# ================================================================

@router.get("/api-performance")
async def get_api_performance(
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    14. GET /api/health/api-performance
    Query params: hours
    Returns: API performance metrics
    """
    stats = metrics_collector.get_all_stats(hours)
    return {
        "hours": hours,
        **stats
    }


@router.get("/api-performance/endpoints")
async def get_endpoint_performance(
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    15. GET /api/health/api-performance/endpoints
    Returns: Per-endpoint performance
    """
    endpoints = {}
    for endpoint in metrics_collector.metrics.keys():
        stats = metrics_collector.get_endpoint_stats(endpoint, hours)
        if stats:
            endpoints[endpoint] = stats

    return {
        "hours": hours,
        "endpoints": endpoints
    }


@router.get("/api-performance/slowest")
async def get_slowest_endpoints(
    limit: int = Query(default=10, ge=1, le=50),
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    16. GET /api/health/api-performance/slowest
    Returns: Slowest endpoints
    """
    slowest = metrics_collector.get_slowest_endpoints(limit, hours)
    return {
        "hours": hours,
        "limit": limit,
        "endpoints": slowest
    }


# ================================================================
# ERROR ENDPOINTS (17-21)
# ================================================================

@router.get("/errors")
async def get_errors(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500)
):
    """
    17. GET /api/health/errors
    Query params: category, severity, hours
    Returns: Recent errors
    """
    errors = await error_tracker.get_errors(category, severity, hours, limit)
    return {
        "filters": {
            "category": category,
            "severity": severity,
            "hours": hours
        },
        "count": len(errors),
        "errors": errors
    }


@router.get("/errors/{error_id}")
async def get_error(error_id: str):
    """
    18. GET /api/health/errors/{error_id}
    Returns: Error details
    """
    error = await error_tracker.get_error(error_id)
    if not error:
        raise HTTPException(status_code=404, detail=f"Error '{error_id}' not found")
    return error


@router.post("/errors/{error_id}/acknowledge")
async def acknowledge_error(error_id: str, request: AcknowledgeRequest):
    """
    19. POST /api/health/errors/{error_id}/acknowledge
    Acknowledges error
    """
    error = await error_tracker.get_error(error_id)
    if not error:
        raise HTTPException(status_code=404, detail=f"Error '{error_id}' not found")

    await error_tracker.acknowledge_error(error_id, request.notes)
    return {
        "success": True,
        "error_id": error_id,
        "message": "Error acknowledged"
    }


@router.post("/errors/{error_id}/resolve")
async def resolve_error(error_id: str, request: ResolveRequest):
    """
    20. POST /api/health/errors/{error_id}/resolve
    Body: { resolution }
    Resolves error
    """
    error = await error_tracker.get_error(error_id)
    if not error:
        raise HTTPException(status_code=404, detail=f"Error '{error_id}' not found")

    await error_tracker.resolve_error(error_id, request.resolution)
    return {
        "success": True,
        "error_id": error_id,
        "message": "Error resolved"
    }


@router.get("/errors/trends")
async def get_error_trends(
    days: int = Query(default=7, ge=1, le=30)
):
    """
    21. GET /api/health/errors/trends
    Query params: days
    Returns: Error trends
    """
    trends = await error_tracker.get_error_trends(days)
    return {
        "days": days,
        "trends": trends
    }


# ================================================================
# ALERT ENDPOINTS (22-24)
# ================================================================

@router.get("/alerts")
async def get_alerts(
    active_only: bool = Query(default=True)
):
    """
    22. GET /api/health/alerts
    Query params: active_only
    Returns: System alerts
    """
    if active_only:
        alerts = await health_monitor.get_active_alerts()
    else:
        alerts = list(health_monitor.alerts.values())

    return {
        "active_only": active_only,
        "count": len(alerts),
        "alerts": alerts
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """
    23. POST /api/health/alerts/{alert_id}/acknowledge
    Acknowledges alert
    """
    if alert_id not in health_monitor.alerts:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")

    await health_monitor.acknowledge_alert(alert_id)
    return {
        "success": True,
        "alert_id": alert_id,
        "message": "Alert acknowledged"
    }


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """
    24. POST /api/health/alerts/{alert_id}/resolve
    Resolves alert
    """
    if alert_id not in health_monitor.alerts:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")

    await health_monitor.resolve_alert(alert_id)
    return {
        "success": True,
        "alert_id": alert_id,
        "message": "Alert resolved"
    }
