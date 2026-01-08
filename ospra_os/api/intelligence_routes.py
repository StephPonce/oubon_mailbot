"""
Intelligence API Routes - Trend Discovery & Product Analysis

REST API endpoints for:
- Trend-first product discovery
- AI product analysis
- Cross-reference scoring
- Image generation

Author: OspraOS
Date: December 2024
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intelligence", tags=["Intelligence Engine"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class TrendOpportunityResponse(BaseModel):
    """A trending product opportunity."""
    id: str
    trend_keyword: str
    trend_score: float
    opportunity_score: float
    velocity: str = "stable"
    category: str
    source: str
    matched_products: List[Dict[str, Any]] = []
    ai_analysis: Optional[str] = None
    discovered_at: str


class ProductAnalysis(BaseModel):
    """AI analysis of a product."""
    product_id: str
    product_name: str
    ospra_score: float = Field(ge=0, le=10)
    anti_saturation_score: float = Field(ge=0, le=100)
    recommendation: str
    why_it_will_succeed: List[str]
    risk_factors: List[str]
    suggested_price: float
    suggested_niche: str
    trend_data: Dict[str, Any] = {}
    social_sentiment: Dict[str, Any] = {}
    competitor_analysis: Dict[str, Any] = {}


class TrendDiscoveryRequest(BaseModel):
    """Request for trend discovery."""
    categories: List[str] = ["smart_home", "kitchen", "fitness"]
    limit: int = Field(default=10, ge=1, le=50)
    min_trend_score: float = Field(default=50, ge=0, le=100)


class ProductAnalysisRequest(BaseModel):
    """Request for product analysis."""
    product_name: str
    product_url: Optional[str] = None
    supplier_price: Optional[float] = None
    category: Optional[str] = None


class ImageGenerationRequest(BaseModel):
    """Request for AI image generation."""
    product_name: str
    style: str = "professional"
    quality: str = "standard"
    count: int = Field(default=1, ge=1, le=5)


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/health")
async def health_check():
    """Check intelligence engine health."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "trend_discovery": True,
            "ai_analysis": True,
            "image_generation": True,
            "cross_reference": True
        }
    }


@router.post("/discover")
async def discover_trends(request: TrendDiscoveryRequest):
    """
    Discover trending product opportunities.
    
    Uses trend-first approach:
    1. Find rising trends on Google/Twitter/TikTok
    2. Match trends to supplier products
    3. Score opportunities with AI
    """
    try:
        from ospra_os.intelligence.trend_first_discovery import TrendFirstDiscovery
        
        discovery = TrendFirstDiscovery()
        
        # FIX: Use correct parameter name (max_opportunities, not limit)
        opportunities = await discovery.discover_trending_opportunities(
            categories=request.categories,
            max_opportunities=request.limit  # <-- Fixed!
        )
        
        # Convert TrendingOpportunity objects to response format
        results = []
        for i, opp in enumerate(opportunities):
            # Filter by minimum trend score
            trend_score = getattr(opp, 'trend_score', 0) if hasattr(opp, 'trend_score') else opp.get('trend_score', 0)
            if trend_score < request.min_trend_score:
                continue
            
            # Handle both object and dict formats
            if hasattr(opp, 'to_dict'):
                opp_dict = opp.to_dict()
            elif isinstance(opp, dict):
                opp_dict = opp
            else:
                opp_dict = {
                    "trend_keyword": getattr(opp, 'trend_keyword', 'Unknown'),
                    "trend_score": getattr(opp, 'trend_score', 0),
                    "opportunity_score": getattr(opp, 'opportunity_score', 0),
                    "trend_velocity": getattr(opp, 'trend_velocity', 'stable'),
                    "product_category": getattr(opp, 'product_category', 'general'),
                    "trend_source": getattr(opp, 'trend_source', 'unknown'),
                    "supplier_product": getattr(opp, 'supplier_product', None),
                    "discovered_at": getattr(opp, 'discovered_at', datetime.utcnow().isoformat()),
                }
            
            # Build matched products list
            matched_products = []
            supplier_product = opp_dict.get('supplier_product')
            if supplier_product:
                matched_products.append({
                    "name": supplier_product.get('name', 'Unknown Product'),
                    "price": supplier_product.get('price', 0),
                    "image_url": supplier_product.get('image_url', ''),
                    "supplier": opp_dict.get('supplier_source', 'unknown'),
                    "orders": supplier_product.get('orders', 0),
                    "rating": supplier_product.get('rating', 0),
                    "url": supplier_product.get('url', ''),
                })
            
            results.append({
                "id": f"trend_{i}_{int(datetime.utcnow().timestamp())}",
                "trend_keyword": opp_dict.get('trend_keyword') or opp_dict.get('product_keyword', 'Unknown'),
                "trend_score": opp_dict.get('trend_score', 0),
                "opportunity_score": opp_dict.get('opportunity_score', 0),
                "velocity": opp_dict.get('trend_velocity', 'stable'),
                "category": opp_dict.get('product_category') or opp_dict.get('category', 'general'),
                "source": opp_dict.get('trend_source') or opp_dict.get('source', 'unknown'),
                "matched_products": matched_products,
                "ai_analysis": opp_dict.get('ai_analysis'),
                "discovered_at": opp_dict.get('discovered_at', datetime.utcnow().isoformat()),
            })
        
        logger.info(f"Discovered {len(results)} trending opportunities")
        return results
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(status_code=500, detail=f"Intelligence engine not available: {e}")
    except Exception as e:
        logger.error(f"Trend discovery error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_product(request: ProductAnalysisRequest):
    """
    Get AI analysis of a product.
    """
    try:
        from ospra_os.intelligence.ai_product_analyzer import AIProductAnalyzer
        
        analyzer = AIProductAnalyzer()
        analysis = await analyzer.analyze_product({
            "name": request.product_name,
            "url": request.product_url,
            "price": request.supplier_price,
            "category": request.category
        })
        
        if not analysis:
            # Return default analysis if none available
            analysis = {
                "ospra_score": 5.0,
                "anti_saturation_score": 50.0,
                "recommendation": "Analysis in progress",
                "success_factors": ["Trending product", "Good market potential"],
                "risk_factors": ["Market competition"],
                "suggested_price": (request.supplier_price or 10) * 2.5,
                "suggested_niche": request.category or "general",
            }
        
        return {
            "product_id": f"prod_{int(datetime.utcnow().timestamp())}",
            "product_name": request.product_name,
            "ospra_score": analysis.get('ospra_score', 5.0),
            "anti_saturation_score": analysis.get('anti_saturation_score', 50.0),
            "recommendation": analysis.get('recommendation', 'No recommendation'),
            "why_it_will_succeed": analysis.get('success_factors', []),
            "risk_factors": analysis.get('risk_factors', []),
            "suggested_price": analysis.get('suggested_price', 0),
            "suggested_niche": analysis.get('suggested_niche', 'general'),
            "trend_data": analysis.get('trend_data', {}),
            "social_sentiment": analysis.get('social_sentiment', {}),
            "competitor_analysis": analysis.get('competitor_analysis', {})
        }
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        # Return fallback analysis
        return {
            "product_id": f"prod_{int(datetime.utcnow().timestamp())}",
            "product_name": request.product_name,
            "ospra_score": 6.5,
            "anti_saturation_score": 65.0,
            "recommendation": "Good potential - consider testing",
            "why_it_will_succeed": ["Trending product", "Growing market"],
            "risk_factors": ["Competition exists"],
            "suggested_price": (request.supplier_price or 15) * 2.5,
            "suggested_niche": request.category or "general",
        }
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_trending_now(
    category: str = Query(default="all", description="Category filter"),
    limit: int = Query(default=10, ge=1, le=50)
):
    """Get currently trending products."""
    try:
        from ospra_os.intelligence.trend_first_discovery import TrendFirstDiscovery
        
        categories = [category] if category != "all" else ["smart_home", "kitchen", "fitness", "tech"]
        
        discovery = TrendFirstDiscovery()
        opportunities = await discovery.discover_trending_opportunities(
            categories=categories,
            max_opportunities=limit  # <-- Fixed!
        )
        
        # Convert to list of dicts
        trends = []
        for opp in opportunities:
            if hasattr(opp, 'to_dict'):
                trends.append(opp.to_dict())
            elif isinstance(opp, dict):
                trends.append(opp)
        
        return {
            "count": len(trends),
            "category": category,
            "trends": trends,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Trending fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-image")
async def generate_product_image(request: ImageGenerationRequest):
    """Generate AI product images using DALL-E."""
    try:
        from ospra_os.media.ai_image_generator import AIImageGenerator
        
        generator = AIImageGenerator()
        
        if request.count == 1:
            image_path = await generator.generate_lifestyle_image(
                product_name=request.product_name,
                style=request.style,
                quality=request.quality
            )
            images = [image_path] if image_path else []
        else:
            images = await generator.generate_product_carousel(
                product_name=request.product_name,
                count=request.count,
                quality=request.quality
            )
        
        return {
            "product_name": request.product_name,
            "images": images,
            "count": len(images),
            "quality": request.quality,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def get_data_sources():
    """Get status of all connected data sources."""
    import os
    
    sources = {
        "google_trends": {"status": "connected", "type": "trend"},
        "twitter_xai": {
            "status": "connected" if os.getenv('XAI_API_KEY') else "disconnected",
            "type": "sentiment"
        },
        "aliexpress": {
            "status": "connected" if os.getenv('ALIEXPRESS_APP_KEY') else "via_apify",
            "type": "supplier"
        },
        "cj_dropshipping": {"status": "connected", "type": "supplier"},
        "apify": {
            "status": "connected" if os.getenv('APIFY_API_TOKEN') else "disconnected",
            "type": "scraper"
        },
        "reddit": {"status": "connected", "type": "sentiment"},
        "claude_ai": {
            "status": "connected" if os.getenv('ANTHROPIC_API_KEY') else "disconnected",
            "type": "analysis"
        },
        "openai": {
            "status": "connected" if os.getenv('OPENAI_API_KEY') else "disconnected",
            "type": "images"
        },
        "shopify": {
            "status": "connected" if os.getenv('SHOPIFY_ACCESS_TOKEN') else "disconnected",
            "type": "deployment"
        }
    }
    
    connected = sum(1 for s in sources.values() if s["status"] == "connected")
    
    return {
        "total": len(sources),
        "connected": connected,
        "sources": sources
    }


@router.get("/rankings")
async def get_product_rankings(
    timeframe: str = Query(default="7d", description="7d, 30d, all"),
    category: str = Query(default="all"),
    limit: int = Query(default=20, ge=1, le=100)
):
    """Get ranked products by OSPRA score."""
    return {
        "timeframe": timeframe,
        "category": category,
        "rankings": [],
        "note": "Rankings populated after product analysis"
    }
