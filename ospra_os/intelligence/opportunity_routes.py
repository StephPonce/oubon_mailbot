"""
Opportunity Scoring API Routes
==============================
RESTful endpoints for the opportunity scoring engine.

Endpoints:
- POST /api/opportunities/score - Score a single product
- POST /api/opportunities/batch - Score multiple products
- GET /api/opportunities/discover/{niche} - Discover and score products
- GET /api/opportunities/stats - Get scoring statistics
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import logging

from ospra_os.intelligence.opportunity_scorer import (
    OpportunityScorer,
    get_opportunity_scorer,
    score_opportunity,
    find_opportunities,
    OpportunityTier
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/opportunities", tags=["Opportunity Scoring"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ScoreProductRequest(BaseModel):
    """Request to score a single product"""
    product_name: str = Field(..., description="Name of the product to score")
    niche: str = Field(default="smart_home", description="Product niche")
    keywords: Optional[List[str]] = Field(default=None, description="Search keywords")
    cost_price: float = Field(default=0.0, description="Cost to acquire product")


class BatchScoreRequest(BaseModel):
    """Request to score multiple products"""
    products: List[Dict] = Field(..., description="List of product dicts")
    niche: str = Field(default="smart_home", description="Product niche")


class OpportunityResponse(BaseModel):
    """Response for a scored product"""
    success: bool
    product_id: str
    product_name: str
    niche: str
    opportunity_score: float
    opportunity_tier: str
    demand_score: float
    competition_score: float
    recommendation: str
    key_reasons: List[str]
    risks: List[str]
    timing_advice: str
    profit_estimate: Dict
    confidence: float
    data_freshness: str


class BatchOpportunityResponse(BaseModel):
    """Response for batch scoring"""
    success: bool
    total_scored: int
    tier_breakdown: Dict[str, int]
    opportunities: List[Dict]


class DiscoverResponse(BaseModel):
    """Response for discovery endpoint"""
    success: bool
    niche: str
    total_discovered: int
    total_opportunities: int
    min_score_used: float
    opportunities: List[Dict]


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/score", response_model=OpportunityResponse)
async def score_single_product(request: ScoreProductRequest):
    """
    Score a single product's opportunity potential.
    
    Returns demand/competition analysis and actionable recommendation.
    
    Example:
    ```json
    {
        "product_name": "LED Strip Lights RGB",
        "niche": "smart_home",
        "cost_price": 8.50
    }
    ```
    """
    try:
        scorer = get_opportunity_scorer()
        
        keywords = request.keywords or request.product_name.split()[:5]
        
        result = await scorer.score_product(
            product_id=f"api_{hash(request.product_name) % 100000}",
            product_name=request.product_name,
            niche=request.niche,
            search_keywords=keywords,
            cost_price=request.cost_price
        )
        
        return OpportunityResponse(
            success=True,
            product_id=result.product_id,
            product_name=result.product_name,
            niche=result.niche,
            opportunity_score=result.opportunity_score,
            opportunity_tier=result.opportunity_tier.value,
            demand_score=result.demand.demand_score,
            competition_score=result.competition.competition_score,
            recommendation=result.recommendation,
            key_reasons=result.key_reasons,
            risks=result.risks,
            timing_advice=result.timing_advice,
            profit_estimate={
                "suggested_price": result.suggested_price,
                "estimated_margin": result.estimated_margin,
                "monthly_volume": result.monthly_volume_estimate,
                "monthly_profit": result.monthly_profit_estimate
            },
            confidence=result.overall_confidence,
            data_freshness=result.data_freshness.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error scoring product: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=BatchOpportunityResponse)
async def score_batch_products(request: BatchScoreRequest):
    """
    Score multiple products in batch.
    
    More efficient than scoring individually. Products should include
    at minimum: title, product_id, price.
    
    Example:
    ```json
    {
        "products": [
            {"product_id": "123", "title": "LED Strip Lights", "price": 9.99},
            {"product_id": "456", "title": "Smart Plug WiFi", "price": 7.99}
        ],
        "niche": "smart_home"
    }
    ```
    """
    try:
        scorer = get_opportunity_scorer()
        
        results = await scorer.score_products_batch(
            products=request.products,
            niche=request.niche
        )
        
        # Calculate tier breakdown
        tier_breakdown = {}
        for result in results:
            tier = result.opportunity_tier.value
            tier_breakdown[tier] = tier_breakdown.get(tier, 0) + 1
        
        # Convert to dicts
        opportunities = [r.to_dict() for r in results]
        
        return BatchOpportunityResponse(
            success=True,
            total_scored=len(results),
            tier_breakdown=tier_breakdown,
            opportunities=opportunities
        )
        
    except Exception as e:
        logger.error(f"Error in batch scoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discover/{niche}", response_model=DiscoverResponse)
async def discover_opportunities(
    niche: str,
    limit: int = Query(default=20, ge=1, le=100, description="Max products to return"),
    min_score: float = Query(default=55.0, ge=0, le=100, description="Minimum opportunity score")
):
    """
    Discover trending products and score them for opportunities.
    
    This is the main endpoint for finding sellable products.
    Returns only products that meet the minimum opportunity score.
    
    Supported niches:
    - smart_home
    - fitness
    - kitchen
    - beauty
    - pet
    - tech
    
    Example: GET /api/opportunities/discover/smart_home?limit=20&min_score=60
    """
    try:
        opportunities = await find_opportunities(
            niche=niche,
            limit=limit,
            min_score=min_score
        )
        
        return DiscoverResponse(
            success=True,
            niche=niche,
            total_discovered=limit * 2,  # We discover more than we return
            total_opportunities=len(opportunities),
            min_score_used=min_score,
            opportunities=[o.to_dict() for o in opportunities]
        )
        
    except Exception as e:
        logger.error(f"Error discovering opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tiers")
async def get_opportunity_tiers():
    """
    Get information about opportunity tier classifications.
    
    Returns the scoring thresholds and what each tier means.
    """
    return {
        "tiers": {
            "golden": {
                "min_score": 85,
                "emoji": "[NEW]",
                "description": "Rare gems - act immediately",
                "recommendation": "Deploy now before competition increases"
            },
            "excellent": {
                "min_score": 70,
                "emoji": "[TARGET]",
                "description": "Strong opportunity with favorable conditions",
                "recommendation": "Proceed with deployment"
            },
            "good": {
                "min_score": 55,
                "emoji": "[GOOD]",
                "description": "Worth considering with monitoring",
                "recommendation": "Test with limited inventory"
            },
            "fair": {
                "min_score": 40,
                "emoji": "[WARNING]",
                "description": "Marginal opportunity",
                "recommendation": "Only with strong differentiation"
            },
            "poor": {
                "min_score": 25,
                "emoji": "[BLOCKED]",
                "description": "Risk outweighs reward",
                "recommendation": "Skip and find alternatives"
            },
            "avoid": {
                "min_score": 0,
                "emoji": "[ERROR]",
                "description": "Does not meet criteria",
                "recommendation": "Do not pursue"
            }
        },
        "formula": "OPPORTUNITY = DEMAND × (1 - COMPETITION × 0.7)",
        "demand_factors": [
            "Google Trends velocity (40%)",
            "Search volume (35%)",
            "Momentum / acceleration (25%)"
        ],
        "competition_factors": [
            "Seller density (35%)",
            "Ad saturation (30%)",
            "Trend timing (20%)",
            "Internal saturation (15%)"
        ]
    }


@router.get("/quick-score")
async def quick_score(
    product: str = Query(..., description="Product name to score"),
    niche: str = Query(default="smart_home", description="Product niche")
):
    """
    Quick score endpoint for simple queries.
    
    Example: GET /api/opportunities/quick-score?product=LED%20Strip%20Lights&niche=smart_home
    """
    try:
        result = await score_opportunity(product, niche)
        
        return {
            "success": True,
            "product": product,
            "niche": niche,
            "opportunity_score": round(result.opportunity_score, 1),
            "tier": result.opportunity_tier.value,
            "demand": round(result.demand.demand_score, 1),
            "competition": round(result.competition.competition_score, 1),
            "recommendation": result.recommendation,
            "confidence": round(result.overall_confidence, 2)
        }
        
    except Exception as e:
        logger.error(f"Error in quick score: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare")
async def compare_products(
    products: str = Query(..., description="Comma-separated product names"),
    niche: str = Query(default="smart_home", description="Product niche")
):
    """
    Compare opportunity scores for multiple products.
    
    Example: GET /api/opportunities/compare?products=LED%20Strip,Smart%20Plug,Motion%20Sensor&niche=smart_home
    """
    try:
        product_names = [p.strip() for p in products.split(",")]
        
        if len(product_names) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 products for comparison")
        
        results = []
        for name in product_names:
            score = await score_opportunity(name, niche)
            results.append({
                "product": name,
                "opportunity_score": round(score.opportunity_score, 1),
                "tier": score.opportunity_tier.value,
                "demand": round(score.demand.demand_score, 1),
                "competition": round(score.competition.competition_score, 1),
                "recommendation": score.recommendation
            })
        
        # Sort by opportunity score
        results.sort(key=lambda x: x["opportunity_score"], reverse=True)
        
        return {
            "success": True,
            "niche": niche,
            "comparison": results,
            "winner": results[0]["product"] if results else None,
            "winner_score": results[0]["opportunity_score"] if results else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))
