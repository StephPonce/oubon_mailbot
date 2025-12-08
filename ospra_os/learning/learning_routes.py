"""
HYBRID LEARNING API ROUTES

Endpoints for the AI learning system.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from ospra_os.database.multi_store_models import SessionLocal
from ospra_os.learning.hybrid_learning_engine import get_learning_engine

router = APIRouter(prefix="/api/learning", tags=["Learning"])


# ==================== REQUEST MODELS ====================

class SaleData(BaseModel):
    product_id: str
    product_name: str
    niche: str
    price: float
    units_sold: int
    revenue: float
    predicted_score: float
    date: str


class LearnRequest(BaseModel):
    user_id: int
    sales: List[SaleData]


class ScoreRequest(BaseModel):
    score: float
    niche: str
    price: float
    user_id: Optional[int] = None


class CustomWeightsRequest(BaseModel):
    user_id: int
    weights: Dict[str, float]


# ==================== GLOBAL BRAIN ENDPOINTS ====================

@router.get("/global/weights")
async def get_global_weights():
    """
    Get current Global Brain weights.
    
    Available to ALL tiers - this is the network effect.
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        weights = engine.get_global_weights()
        return weights
    finally:
        db.close()


@router.post("/global/contribute")
async def contribute_to_global(request: LearnRequest):
    """
    Contribute sales data to Global Brain learning.
    
    ALL tiers can contribute (and benefit from) global learning.
    Higher tiers have higher contribution weight.
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        
        sales_data = [sale.dict() for sale in request.sales]
        result = await engine.learn_global(sales_data, request.user_id)
        
        return result
    finally:
        db.close()


# ==================== PERSONAL LAYER ENDPOINTS ====================

@router.get("/personal/{user_id}")
async def get_personal_weights(user_id: int):
    """
    Get personal learning weights for a user.
    
    Requires Soar tier or higher.
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        weights = engine.get_personal_weights(user_id)
        
        if not weights:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return weights
    finally:
        db.close()


@router.post("/personal/learn")
async def learn_personal(request: LearnRequest):
    """
    Update personal learning layer for a user.
    
    Requires Soar tier or higher.
    Stratosphere users get accelerated learning (2x).
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        
        sales_data = [sale.dict() for sale in request.sales]
        result = await engine.learn_personal(request.user_id, sales_data)
        
        return result
    finally:
        db.close()


# ==================== SCORING ENDPOINTS ====================

@router.post("/score/adjusted")
async def get_adjusted_score(request: ScoreRequest):
    """
    Get AI-adjusted score for a product.
    
    Uses Global Brain for all users.
    Uses Personal Layer for Soar+ users (if available).
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        
        product = {
            "score": request.score,
            "niche": request.niche,
            "price": request.price
        }
        
        result = await engine.get_adjusted_score(product, request.user_id)
        
        return result
    finally:
        db.close()


# ==================== STRATOSPHERE ENDPOINTS ====================

@router.post("/custom-weights")
async def set_custom_weights(request: CustomWeightsRequest):
    """
    Set custom scoring weights.
    
    Stratosphere tier ONLY.
    
    Example weights (must sum to 1.0):
    {
        "google_trends_weight": 0.30,
        "reddit_mentions_weight": 0.10,
        "aliexpress_orders_weight": 0.35,
        "price_competitiveness_weight": 0.15,
        "trend_velocity_weight": 0.10
    }
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        
        result = await engine.set_custom_weights(request.user_id, request.weights)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.get("reason", "Failed to set custom weights")
            )
        
        return result
    finally:
        db.close()


# ==================== REPORT ENDPOINTS ====================

@router.get("/report")
async def get_learning_report(user_id: Optional[int] = None):
    """
    Get comprehensive learning report.
    
    Shows Global Brain stats for everyone.
    Shows Personal Layer stats for Soar+ users.
    """
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        report = await engine.get_learning_report(user_id)
        return report
    finally:
        db.close()


@router.get("/health")
async def learning_health():
    """Health check for learning system"""
    db = SessionLocal()
    try:
        engine = get_learning_engine(db)
        weights = engine.get_global_weights()
        
        return {
            "status": "healthy",
            "global_brain": {
                "learning_cycles": weights.get("learning_cycles", 0),
                "users_contributing": weights.get("total_users_contributing", 0),
                "accuracy": weights.get("accuracy", {}).get("accuracy_rate", 0)
            }
        }
    finally:
        db.close()
