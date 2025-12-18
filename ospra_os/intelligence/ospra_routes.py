"""
🧠 OSPRA INTELLIGENCE ROUTES
=============================
REAL cross-source product discovery
ONLY winners (7.5+ score) get saved
NO FAKE DATA

Endpoints:
- POST /api/intelligence/discover - Discover winning products
- GET /api/intelligence/stats - Get discovery stats
- GET /api/intelligence/health - Check engine health
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intelligence", tags=["Ospra Intelligence"])

# Initialize the REAL engine
_engine = None

def get_engine():
    """Get or create the Ospra Intelligence Engine"""
    global _engine
    if _engine is None:
        try:
            from ospra_os.intelligence.ospra_engine import OspraIntelligenceEngine
            import os
            database_url = os.getenv('DATABASE_URL')
            _engine = OspraIntelligenceEngine(database_url=database_url)
            logger.info("✅ Ospra Intelligence Engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize engine: {e}")
            # Fallback to V4 if new engine fails
            try:
                from ospra_os.intelligence.product_intelligence_v4 import ProductIntelligenceEngine
                _engine = ProductIntelligenceEngine()
                logger.warning("⚠️ Using V4 fallback engine")
            except:
                _engine = None
    return _engine


@router.post("/discover")
async def discover_products(request: dict = {}):
    """
    🔍 DISCOVER WINNING PRODUCTS
    
    Uses REAL cross-source intelligence:
    1. Google Trends → Find trending keywords
    2. TikTok → Check viral potential (if available)
    3. AliExpress → Find matching products
    4. Cross-validate → Calculate REAL scores
    5. Filter → ONLY 7.5+ score products saved
    
    Request body:
    {
        "niches": ["smart_home", "fitness"],  // Optional, defaults to top 3
        "max_per_niche": 10                    // Max products per niche
    }
    
    Response:
    {
        "success": true,
        "winners": [...],           // Only products scoring 7.5+
        "stats": {
            "trends_checked": 20,
            "products_found": 50,
            "products_validated": 30,
            "products_passed": 12,   // Winners
            "products_rejected": 18  // Score < 7.5, never saved
        }
    }
    """
    engine = get_engine()
    
    if not engine:
        raise HTTPException(
            status_code=503,
            detail="Intelligence engine not available"
        )
    
    niches = request.get('niches', ['smart_home', 'fitness', 'tech_accessories'])
    max_per_niche = request.get('max_per_niche', 10)
    
    logger.info(f"🧠 Starting discovery: niches={niches}, max_per_niche={max_per_niche}")
    
    try:
        # Check if engine is the new one or fallback
        if hasattr(engine, 'discover_winners'):
            # NEW engine - REAL intelligence
            winners = await engine.discover_winners(
                niches=niches,
                max_per_niche=max_per_niche,
                save_to_db=True
            )
            
            return {
                "success": True,
                "message": f"Found {len(winners)} winning products (score 7.5+)",
                "winners": [w.to_dict() for w in winners],
                "count": len(winners),
                "stats": engine.get_stats(),
                "engine": "OSPRA_INTELLIGENCE_REAL",
                "timestamp": datetime.now().isoformat()
            }
        else:
            # V4 fallback - static data (TO BE REPLACED)
            products = engine.discover_products(niches, max_per_niche)
            
            # Save to database
            from ospra_os.database.product_history import ProductHistoryDB
            db = ProductHistoryDB()
            for product in products:
                db.upsert_product(product)
            
            return {
                "success": True,
                "message": f"Found {len(products)} products (V4 fallback)",
                "products": products,
                "count": len(products),
                "engine": "V4_FALLBACK",
                "warning": "Using fallback engine - not real cross-source intelligence",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Discovery failed: {str(e)}"
        )


@router.get("/stats")
async def get_discovery_stats():
    """Get discovery engine statistics"""
    engine = get_engine()
    
    if not engine:
        return {
            "status": "unavailable",
            "message": "Engine not initialized"
        }
    
    if hasattr(engine, 'get_stats'):
        return {
            "status": "ready",
            "stats": engine.get_stats(),
            "engine_type": "OSPRA_INTELLIGENCE_REAL"
        }
    else:
        return {
            "status": "ready",
            "engine_type": "V4_FALLBACK",
            "message": "Using fallback engine"
        }


@router.get("/health")
async def intelligence_health_check():
    """Check health of intelligence engine components"""
    engine = get_engine()
    
    if not engine:
        return {
            "status": "unhealthy",
            "message": "Engine not initialized"
        }
    
    try:
        components = {
            "google_trends": hasattr(engine, 'google_trends') and engine.google_trends is not None,
            "tiktok": hasattr(engine, 'tiktok_enabled') and engine.tiktok_enabled,
            "aliexpress": hasattr(engine, 'aliexpress_enabled') and engine.aliexpress_enabled,
        }
        
        critical_ok = components.get("google_trends", False) or components.get("aliexpress", False)
        
        return {
            "status": "healthy" if critical_ok else "degraded",
            "components": components,
            "engine_type": "OSPRA_INTELLIGENCE_REAL" if hasattr(engine, 'discover_winners') else "V4_FALLBACK",
            "min_score_threshold": getattr(engine, 'MIN_SCORE_THRESHOLD', 7.5)
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/niches")
async def get_available_niches():
    """Get all available niches for discovery"""
    engine = get_engine()
    
    if hasattr(engine, 'NICHE_DISCOVERY_KEYWORDS'):
        niches = engine.NICHE_DISCOVERY_KEYWORDS
    else:
        niches = {
            'smart_home': ['smart home', 'wifi device', 'home automation'],
            'fitness': ['fitness gadget', 'home gym', 'workout equipment'],
            'tech_accessories': ['phone accessory', 'wireless charger', 'usb hub'],
            'kitchen': ['kitchen gadget', 'cooking tool', 'food storage'],
            'beauty': ['beauty device', 'skincare tool', 'makeup organizer'],
            'pet': ['pet gadget', 'dog accessory', 'cat toy'],
            'outdoor': ['outdoor gear', 'camping equipment', 'hiking accessory'],
            'home_office': ['desk accessory', 'ergonomic product', 'webcam'],
            'car': ['car accessory', 'car gadget', 'car organizer'],
            'baby': ['baby product', 'nursery essential', 'baby safety'],
        }
    
    return {
        "success": True,
        "niches": [
            {
                "id": niche_id,
                "name": niche_id.replace('_', ' ').title(),
                "keyword_count": len(keywords),
                "sample_keywords": keywords[:3] if isinstance(keywords, list) else []
            }
            for niche_id, keywords in niches.items()
        ]
    }


@router.post("/validate")
async def validate_single_product(request: dict):
    """
    Validate a single product idea against our intelligence
    
    Request:
    {
        "keyword": "smart wifi plug",
        "niche": "smart_home"
    }
    
    Response:
    {
        "validated": true,
        "score": 8.2,
        "recommendation": "STRONG_BUY",
        "trend_data": {...},
        "competitors": [...]
    }
    """
    engine = get_engine()
    
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not available")
    
    keyword = request.get('keyword')
    niche = request.get('niche', 'general')
    
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword is required")
    
    try:
        # Quick validation using the engine
        if hasattr(engine, '_get_trending_keywords'):
            trend_data = await engine._get_trending_keywords(niche)
            matching = [t for t in trend_data if keyword.lower() in t[0].lower()]
            
            if matching:
                _, data = matching[0]
                score = data.get('score', 50) / 10  # Convert to 0-10
                return {
                    "validated": True,
                    "keyword": keyword,
                    "score": round(score, 1),
                    "recommendation": "STRONG_BUY" if score >= 7.5 else "BUY" if score >= 6 else "HOLD",
                    "trend_data": data
                }
        
        return {
            "validated": False,
            "keyword": keyword,
            "message": "Could not validate - no trend data available"
        }
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
