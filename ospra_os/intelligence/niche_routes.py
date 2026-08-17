"""
Niche Analysis API Routes

Provides REST API endpoints for niche health analysis, lifecycle tracking,
entry timing recommendations, and market intelligence.

Endpoints:
- GET /api/niches/all - Get all tracked niches with health scores
- GET /api/niches/{niche_id} - Get full analysis for specific niche
- POST /api/niches/{niche_id}/analyze - Trigger analysis (manual)
- GET /api/niches/{niche_id}/history - Historical health scores
- GET /api/niches/{niche_id}/predict - Trajectory predictions
- GET /api/niches/trending - Niches with improving scores
- GET /api/niches/declining - Niches with declining scores
- GET /api/niches/emerging - New niches in EMERGING stage
- POST /api/niches/compare - Compare multiple niches
- GET /api/niches/{niche_id}/subcategories - Get subcategories
- GET /api/niches/{niche_id}/entry-timing - Entry timing evaluation

Author: OspraOS
Date: November 2025
"""

from fastapi import Depends, APIRouter, HTTPException, Query, Body
from ospra_os.auth.jwt_auth import get_current_user
from typing import List, Optional, Dict
from pydantic import BaseModel
import logging
import os

from ospra_os.intelligence.niche_analyzer import NicheAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter()

# Get database URL (same as used in main.py for multi-store initialization)
DATABASE_URL = "sqlite:///./oubon_store.db"


# Pydantic models for request/response
class NicheCompareRequest(BaseModel):
    """Request model for comparing niches"""
    niche_ids: List[str]


class AnalyzeNicheRequest(BaseModel):
    """Request model for analyzing a niche"""
    store_snapshot: bool = True


# ===== ENDPOINT 1: GET ALL NICHES =====
@router.get("/api/niches/all")
async def get_all_niches(
    sort_by: str = Query("health_score", description="Sort field: health_score, name, lifecycle_stage")
):
    """
    Get all tracked niches with current health scores.

    Returns list of niches sorted by specified field.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        niches = await analyzer.get_all_niches(sort_by=sort_by)

        return {
            "success": True,
            "niches": niches,
            "total_count": len(niches),
            "sort_by": sort_by
        }

    except Exception as e:
        logger.error(f"Failed to get all niches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINT 2: GET SPECIFIC NICHE ANALYSIS =====
@router.get("/api/niches/{niche_id}")
async def get_niche_analysis(
    niche_id: str,
    store_snapshot: bool = Query(False, description="Store snapshot in database")
):
    """
    Get full analysis for a specific niche.

    Returns comprehensive health score, lifecycle stage, saturation metrics,
    profitability data, entry timing recommendations, and strategic insights.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        analysis = await analyzer.analyze_niche(niche_id, store_snapshot=store_snapshot)

        return {
            "success": True,
            "analysis": analysis
        }

    except Exception as e:
        logger.error(f"Failed to analyze niche {niche_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINT 3: TRIGGER MANUAL ANALYSIS =====
@router.post("/api/niches/{niche_id}/analyze", dependencies=[Depends(get_current_user)])
async def trigger_niche_analysis(
    niche_id: str,
    request: AnalyzeNicheRequest = Body(...)
):
    """
    Manually trigger niche analysis and store snapshot.

    Useful for on-demand analysis or testing.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        analysis = await analyzer.analyze_niche(
            niche_id,
            store_snapshot=request.store_snapshot
        )

        return {
            "success": True,
            "message": f"Analysis complete for {niche_id}",
            "snapshot_stored": request.store_snapshot,
            "analysis": analysis
        }

    except Exception as e:
        logger.error(f"Failed to trigger analysis for {niche_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINT 4: GET NICHE HISTORY =====
@router.get("/api/niches/{niche_id}/history")
async def get_niche_history(
    niche_id: str,
    days: int = Query(90, description="Number of days to look back", ge=1, le=365)
):
    """
    Get historical health scores and metrics for a niche.

    Returns time-series data for charting and trend analysis.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        history = await analyzer.get_niche_history(niche_id, days=days)

        return {
            "success": True,
            "niche_id": niche_id,
            "days": days,
            "data_points": len(history),
            "history": history
        }

    except Exception as e:
        logger.error(f"Failed to get history for {niche_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINT 5: PREDICT NICHE TRAJECTORY =====
@router.get("/api/niches/{niche_id}/predict")
async def predict_niche_trajectory(niche_id: str):
    """
    Predict where this niche will be in 30/60/90 days.

    Uses historical trends to project future health scores and lifecycle stages.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        predictions = await analyzer.predict_niche_trajectory(niche_id)

        return {
            "success": True,
            "predictions": predictions
        }

    except Exception as e:
        logger.error(f"Failed to predict trajectory for {niche_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINT 6: GET TRENDING NICHES =====
@router.get("/api/niches/trending")
async def get_trending_niches(
    limit: int = Query(10, description="Number of niches to return", ge=1, le=50)
):
    """
    Get niches with improving health scores (positive momentum).

    Perfect for identifying emerging opportunities.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        trending = await analyzer.get_trending_niches(limit=limit)

        return {
            "success": True,
            "trending_niches": trending,
            "count": len(trending)
        }

    except Exception as e:
        logger.error(f"Failed to get trending niches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINT 7: GET DECLINING NICHES =====
@router.get("/api/niches/declining")
async def get_declining_niches(
    limit: int = Query(10, description="Number of niches to return", ge=1, le=50)
):
    """
    Get niches with declining health scores (negative momentum).

    Useful for identifying markets to avoid or exit.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        declining = await analyzer.get_dying_niches(limit=limit)

        return {
            "success": True,
            "declining_niches": declining,
            "count": len(declining)
        }

    except Exception as e:
        logger.error(f"Failed to get declining niches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINT 8: GET EMERGING NICHES =====
@router.get("/api/niches/emerging")
async def get_emerging_niches(
    limit: int = Query(10, description="Number of niches to return", ge=1, le=50)
):
    """
    Get new niches in EMERGING stage.

    Low competition, growing interest - prime entry opportunities.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        emerging = await analyzer.get_emerging_niches(limit=limit)

        return {
            "success": True,
            "emerging_niches": emerging,
            "count": len(emerging)
        }

    except Exception as e:
        logger.error(f"Failed to get emerging niches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINT 9: COMPARE NICHES =====
@router.post("/api/niches/compare", dependencies=[Depends(get_current_user)])
async def compare_niches(request: NicheCompareRequest):
    """
    Side-by-side comparison of multiple niches.

    Returns all metrics for each niche plus summary comparisons.
    """
    try:
        if not request.niche_ids:
            raise HTTPException(status_code=400, detail="Must provide at least one niche_id")

        if len(request.niche_ids) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 niches for comparison")

        analyzer = NicheAnalyzer(DATABASE_URL)
        comparison = await analyzer.compare_niches(request.niche_ids)

        return {
            "success": True,
            "comparison": comparison
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare niches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINT 10: GET SUBCATEGORIES =====
@router.get("/api/niches/{niche_id}/subcategories")
async def get_niche_subcategories(niche_id: str):
    """
    Get subcategories for a parent niche with individual health scores.

    Useful for drilling down into niche segments.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        subcategories = await analyzer.get_subcategories(niche_id)

        return {
            "success": True,
            "parent_niche_id": niche_id,
            "subcategories": subcategories,
            "count": len(subcategories)
        }

    except Exception as e:
        logger.error(f"Failed to get subcategories for {niche_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ENDPOINT 11: GET ENTRY TIMING EVALUATION =====
@router.get("/api/niches/{niche_id}/entry-timing")
async def evaluate_entry_timing(niche_id: str):
    """
    Evaluate whether user should enter this niche now.

    Returns entry timing recommendation (EXCELLENT, GOOD, FAIR, POOR, AVOID)
    with risk level, ROI estimates, and reasoning.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        entry_evaluation = await analyzer.evaluate_entry_timing(niche_id)

        return {
            "success": True,
            "evaluation": entry_evaluation
        }

    except Exception as e:
        logger.error(f"Failed to evaluate entry timing for {niche_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== HEALTH CHECK ENDPOINT =====
@router.get("/api/niches/health")
async def niche_analyzer_health():
    """
    Health check endpoint for niche analysis service.
    """
    try:
        analyzer = NicheAnalyzer(DATABASE_URL)
        all_niches = await analyzer.get_all_niches()

        return {
            "success": True,
            "status": "healthy",
            "database_url": "connected",
            "total_niches_tracked": len(all_niches)
        }

    except Exception as e:
        logger.error(f"Niche analyzer health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")


logger.info("Niche Analysis routes loaded successfully")
