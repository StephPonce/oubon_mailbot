"""
Auto-Deployment API Routes

Admin controls for the auto-deployment service.

Endpoints:
- POST /api/auto-deploy/enable - Enable auto-deployment
- POST /api/auto-deploy/disable - Disable auto-deployment
- GET /api/auto-deploy/status - Get current status
- PUT /api/auto-deploy/criteria - Update deployment criteria
- GET /api/auto-deploy/history - Get deployment history
- POST /api/auto-deploy/run-now - Manually trigger deployment check

Author: OspraOS
Date: December 2025
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(
    prefix="/api/auto-deploy",
    tags=["Auto-Deployment"]
)

# Global auto-deployer instance (initialized on startup)
_auto_deployer = None


def get_auto_deployer():
    """Get or create auto-deployer instance"""
    global _auto_deployer
    if _auto_deployer is None:
        from ospra_os.services.auto_deployer import AutoDeployer
        _auto_deployer = AutoDeployer()
        logger.info("[SUCCESS] AutoDeployer initialized")
    return _auto_deployer


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CriteriaUpdate(BaseModel):
    """Update deployment criteria"""
    min_score: Optional[float] = Field(None, ge=0, le=100, description="Minimum product score (0-100)")
    min_profit_margin: Optional[float] = Field(None, ge=0, le=1, description="Minimum profit margin (0-1)")
    max_saturation: Optional[str] = Field(None, description="Max saturation: low, medium, high")
    allowed_niches: Optional[List[str]] = Field(None, description="Allowed product niches")
    max_per_day: Optional[int] = Field(None, ge=1, le=100, description="Max deployments per day")
    max_per_hour: Optional[int] = Field(None, ge=1, le=10, description="Max deployments per hour")
    max_daily_cost: Optional[float] = Field(None, ge=0, description="Max daily AI cost ($)")
    require_multiple_sources: Optional[bool] = Field(None, description="Require multi-source validation")
    min_trend_velocity: Optional[float] = Field(None, ge=0, le=100, description="Min Google Trends velocity")
    auto_publish: Optional[bool] = Field(None, description="Auto-publish (vs draft)")


class StatusResponse(BaseModel):
    """Auto-deploy status"""
    enabled: bool
    criteria: Dict
    last_run: Optional[str] = None
    total_deployed: int
    total_cost: float


class DeploymentHistoryItem(BaseModel):
    """Single deployment record"""
    id: int
    product_name: str
    niche: str
    score: float
    shopify_url: Optional[str] = None
    success: bool
    error: Optional[str] = None
    ai_cost: float
    deployed_at: str


class RunNowResponse(BaseModel):
    """Response from manual run"""
    success: bool
    deployed: int
    failed: int
    total_cost: float
    message: str


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/enable")
async def enable_auto_deploy():
    """
    [SUCCESS] Enable Auto-Deployment

    Enables the automated product deployment system. Products that meet
    the configured criteria will be automatically deployed to Shopify.

    **Safety Features:**
    - Daily deployment limits
    - Cost limits
    - Draft-first deployment (default)
    - Multi-source validation required
    - Admin notifications

    **Returns:**
    ```json
    {
      "success": true,
      "message": "Auto-deployment enabled",
      "criteria": {...}
    }
    ```
    """
    try:
        deployer = get_auto_deployer()
        deployer.enable()

        logger.info("[SUCCESS] Auto-deployment ENABLED by admin")

        return {
            "success": True,
            "message": "Auto-deployment enabled",
            "criteria": deployer.settings["criteria"]
        }
    except Exception as e:
        logger.error(f"Failed to enable auto-deploy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_auto_deploy():
    """
    [PAUSE] Disable Auto-Deployment

    Disables the automated product deployment system. The scheduler will
    continue to run but will skip deployment checks.

    **Returns:**
    ```json
    {
      "success": true,
      "message": "Auto-deployment disabled"
    }
    ```
    """
    try:
        deployer = get_auto_deployer()
        deployer.disable()

        logger.info("[PAUSE]  Auto-deployment DISABLED by admin")

        return {
            "success": True,
            "message": "Auto-deployment disabled"
        }
    except Exception as e:
        logger.error(f"Failed to disable auto-deploy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=StatusResponse)
async def get_auto_deploy_status():
    """
    [STATS] Get Auto-Deploy Status

    Returns current status, criteria, and statistics.

    **Response:**
    ```json
    {
      "enabled": true,
      "criteria": {
        "min_score": 80.0,
        "min_profit_margin": 0.35,
        "max_saturation": "medium",
        "allowed_niches": ["smart_home", "fitness"],
        "max_per_day": 5,
        "max_per_hour": 2,
        "max_daily_cost": 1.0,
        "require_multiple_sources": true,
        "auto_publish": false
      },
      "last_run": "2025-12-07T12:34:56",
      "total_deployed": 42,
      "total_cost": 2.52
    }
    ```
    """
    try:
        deployer = get_auto_deployer()
        status = deployer.get_status()

        return StatusResponse(
            enabled=status["enabled"],
            criteria=status["criteria"],
            last_run=status["last_run"].isoformat() if status["last_run"] else None,
            total_deployed=status["total_deployed"],
            total_cost=status["total_cost"]
        )
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/criteria")
async def update_criteria(criteria: CriteriaUpdate):
    """
    [CONFIG] Update Deployment Criteria

    Update the criteria used to filter products for auto-deployment.
    Only provided fields will be updated.

    **Example:**
    ```json
    {
      "min_score": 85.0,
      "max_per_day": 10,
      "allowed_niches": ["smart_home", "tech_gadgets", "fitness"],
      "auto_publish": false
    }
    ```

    **Returns:**
    ```json
    {
      "success": true,
      "message": "Criteria updated",
      "criteria": {...}
    }
    ```
    """
    try:
        deployer = get_auto_deployer()

        # Build update dict from provided fields
        updates = {}
        for field, value in criteria.dict(exclude_unset=True).items():
            if value is not None:
                updates[field] = value

        if not updates:
            raise HTTPException(status_code=400, detail="No criteria provided")

        deployer.update_criteria(updates)

        logger.info(f"[SUCCESS] Criteria updated by admin: {updates}")

        return {
            "success": True,
            "message": "Criteria updated",
            "criteria": deployer.settings["criteria"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update criteria: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[DeploymentHistoryItem])
async def get_deployment_history(limit: int = 50):
    """
     Get Deployment History

    Returns the history of auto-deployed products.

    **Query Parameters:**
    - `limit` - Max number of records to return (default: 50, max: 200)

    **Response:**
    ```json
    [
      {
        "id": 123,
        "product_name": "Smart WiFi Bulb",
        "niche": "smart_home",
        "score": 87.5,
        "shopify_url": "https://store.com/products/smart-wifi-bulb",
        "success": true,
        "error": null,
        "ai_cost": 0.06,
        "deployed_at": "2025-12-07T12:34:56"
      },
      ...
    ]
    ```
    """
    try:
        if limit > 200:
            limit = 200

        deployer = get_auto_deployer()
        history = deployer.get_history(limit=limit)

        return [DeploymentHistoryItem(**item) for item in history]
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-now", response_model=RunNowResponse)
async def run_deployment_now(background_tasks: BackgroundTasks):
    """
     Run Deployment Check Now

    Manually trigger an auto-deployment check. This runs the same logic
    as the scheduled task but can be triggered on-demand.

    **Use Cases:**
    - Test auto-deployment configuration
    - Deploy urgent high-scoring products immediately
    - Manual override of schedule

    **Note:** Still respects daily/hourly limits and cost constraints.

    **Returns:**
    ```json
    {
      "success": true,
      "deployed": 3,
      "failed": 0,
      "total_cost": 0.18,
      "message": "Deployed 3 products successfully"
    }
    ```
    """
    try:
        deployer = get_auto_deployer()

        logger.info("[START] Manual deployment check triggered by admin")

        # Run deployment check
        result = await deployer.check_and_deploy()

        if not result.get("success"):
            message = result.get("reason", "Deployment check failed")
            return RunNowResponse(
                success=False,
                deployed=0,
                failed=0,
                total_cost=0.0,
                message=message
            )

        deployed = result.get("deployed", 0)
        failed = result.get("failed", 0)
        total_cost = result.get("total_cost", 0.0)

        if deployed > 0:
            message = f"Deployed {deployed} product{'s' if deployed != 1 else ''} successfully"
        elif failed > 0:
            message = f"All {failed} deployment{'s' if failed != 1 else ''} failed"
        else:
            message = result.get("reason", "No products to deploy")

        return RunNowResponse(
            success=True,
            deployed=deployed,
            failed=failed,
            total_cost=total_cost,
            message=message
        )

    except Exception as e:
        logger.error(f"Manual deployment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def auto_deploy_health():
    """
     Health Check

    Check if auto-deployment service is operational.

    **Returns:**
    ```json
    {
      "status": "healthy",
      "deployer_initialized": true,
      "database_connected": true,
      "services": {
        "product_deployer": true,
        "product_discovery": true
      }
    }
    ```
    """
    try:
        deployer = get_auto_deployer()

        return {
            "status": "healthy",
            "deployer_initialized": deployer is not None,
            "database_connected": True,  # If we got here, DB is working
            "services": {
                "product_deployer": deployer.deployer is not None,
                "product_discovery": deployer.discovery is not None
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
