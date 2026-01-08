"""
A/B Testing API Routes

FastAPI endpoints for creating, managing, and analyzing A/B tests.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from ospra_os.database.multi_store_models import get_multi_store_session
from .ab_test_engine import ABTestEngine, TestType, TestStatus
from .price_test_manager import PriceTestManager
from .content_test_manager import ContentTestManager
from .ad_test_manager import AdTestManager


router = APIRouter(prefix="/api/abtesting", tags=["A/B Testing"])


# ============================================================================
# PYDANTIC MODELS (Request/Response)
# ============================================================================

class VariantConfig(BaseModel):
    """Variant configuration"""
    name: str
    config: Dict[str, Any]


class CreateTestRequest(BaseModel):
    """Request to create a new A/B test"""
    name: str
    test_type: str  # price, product_title, product_description, product_image, ad_creative, ad_copy
    product_id: str
    store_id: str
    variants: List[VariantConfig]
    traffic_split: Optional[List[float]] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    min_sample_size: int = 100
    confidence_level: float = 0.95
    metadata: Optional[Dict[str, Any]] = None


class CreatePriceTestRequest(BaseModel):
    """Simplified price test creation"""
    product_id: str
    store_id: str
    current_price: float
    test_prices: List[float]
    test_name: Optional[str] = None
    duration_days: int = 14
    traffic_split: Optional[List[float]] = None
    min_sample_size: int = 100
    auto_implement_winner: bool = False


class CreateTitleTestRequest(BaseModel):
    """Simplified title test creation"""
    product_id: str
    store_id: str
    current_title: str
    variant_titles: List[str]
    test_name: Optional[str] = None
    duration_days: int = 14
    min_sample_size: int = 100


class CreateDescriptionTestRequest(BaseModel):
    """Simplified description test creation"""
    product_id: str
    store_id: str
    current_description: str
    variant_descriptions: List[str]
    test_name: Optional[str] = None
    duration_days: int = 14
    min_sample_size: int = 100


class CreateImageTestRequest(BaseModel):
    """Simplified image test creation"""
    product_id: str
    store_id: str
    current_image_url: str
    variant_image_urls: List[str]
    test_name: Optional[str] = None
    duration_days: int = 14
    min_sample_size: int = 100


class RecordImpressionRequest(BaseModel):
    """Record impression event"""
    test_id: int
    variant_id: int
    visitor_id: str
    metadata: Optional[Dict[str, Any]] = None


class RecordConversionRequest(BaseModel):
    """Record conversion event"""
    test_id: int
    variant_id: int
    visitor_id: str
    revenue: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class GetVariantRequest(BaseModel):
    """Get variant for visitor"""
    test_id: int
    visitor_id: str


class EndTestRequest(BaseModel):
    """End a test"""
    implement_winner: bool = False
    winner_variant_id: Optional[int] = None


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

def get_db():
    """Get database session"""
    db = get_multi_store_session()
    try:
        yield db
    finally:
        db.close()


def get_ab_engine(db: Session = Depends(get_db)) -> ABTestEngine:
    """Get A/B test engine"""
    return ABTestEngine(db)


def get_price_manager(db: Session = Depends(get_db)) -> PriceTestManager:
    """Get price test manager"""
    return PriceTestManager(db)


def get_content_manager(db: Session = Depends(get_db)) -> ContentTestManager:
    """Get content test manager"""
    return ContentTestManager(db)


def get_ad_manager(db: Session = Depends(get_db)) -> AdTestManager:
    """Get ad test manager"""
    return AdTestManager(db)


# ============================================================================
# TEST MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/tests", status_code=201)
def create_test(
    request: CreateTestRequest,
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """
    Create a new A/B test

    Creates a test with custom variants. For simplified test creation,
    use the specialized endpoints (e.g., /tests/price).
    """
    try:
        # Convert string test_type to enum
        test_type_enum = TestType(request.test_type)

        test = engine.create_test(
            name=request.name,
            test_type=test_type_enum,
            product_id=request.product_id,
            store_id=request.store_id,
            variants=[v.dict() for v in request.variants],
            traffic_split=request.traffic_split,
            scheduled_start=request.scheduled_start,
            scheduled_end=request.scheduled_end,
            min_sample_size=request.min_sample_size,
            confidence_level=request.confidence_level,
            metadata=request.metadata
        )

        return {
            "success": True,
            "test_id": test.id,
            "message": f"Test '{test.name}' created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tests")
def list_tests(
    store_id: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    test_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """
    List all A/B tests with optional filters

    Query parameters:
    - store_id: Filter by store
    - product_id: Filter by product
    - status: Filter by status (draft, running, paused, ended)
    - test_type: Filter by type (price, product_title, etc.)
    - limit: Max results (default 50)
    - offset: Pagination offset
    """
    try:
        # Convert string enums if provided
        status_enum = TestStatus(status) if status else None
        test_type_enum = TestType(test_type) if test_type else None

        tests = engine.list_tests(
            store_id=store_id,
            product_id=product_id,
            status=status_enum,
            test_type=test_type_enum,
            limit=limit,
            offset=offset
        )

        return {
            "success": True,
            "tests": tests,
            "count": len(tests)
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tests/{test_id}")
def get_test(
    test_id: int,
    include_results: bool = Query(True),
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """
    Get test details with current results

    Returns:
    - Test configuration
    - Variant details and metrics
    - Statistical significance (if include_results=true)
    """
    try:
        test = engine.get_test(test_id, include_results=include_results)

        if not test:
            raise HTTPException(status_code=404, detail=f"Test {test_id} not found")

        return {
            "success": True,
            "test": test
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tests/{test_id}/start")
def start_test(
    test_id: int,
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """Start a draft or scheduled test"""
    try:
        test = engine.start_test(test_id)

        return {
            "success": True,
            "test_id": test.id,
            "status": test.status,
            "started_at": test.started_at.isoformat() if test.started_at else None,
            "message": "Test started successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tests/{test_id}/pause")
def pause_test(
    test_id: int,
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """Pause a running test"""
    try:
        test = engine.pause_test(test_id)

        return {
            "success": True,
            "test_id": test.id,
            "status": test.status,
            "message": "Test paused successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tests/{test_id}/resume")
def resume_test(
    test_id: int,
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """Resume a paused test"""
    try:
        test = engine.resume_test(test_id)

        return {
            "success": True,
            "test_id": test.id,
            "status": test.status,
            "message": "Test resumed successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tests/{test_id}/end")
def end_test(
    test_id: int,
    request: EndTestRequest,
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """
    End a test and optionally implement winner

    Body parameters:
    - implement_winner: Whether to apply winning variant (default: false)
    - winner_variant_id: Manual winner selection (overrides auto-detection)
    """
    try:
        test = engine.end_test(
            test_id,
            implement_winner=request.implement_winner,
            winner_variant_id=request.winner_variant_id
        )

        return {
            "success": True,
            "test_id": test.id,
            "status": test.status,
            "ended_at": test.ended_at.isoformat() if test.ended_at else None,
            "winner_variant_id": test.winner_variant_id,
            "message": "Test ended successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/{test_id}/results")
def get_test_results(
    test_id: int,
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """
    Get current test results with statistical analysis

    Returns variant performance, conversion rates, and significance.
    """
    try:
        results = engine.calculate_results(test_id)

        return {
            "success": True,
            "results": results
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/{test_id}/significance")
def check_significance(
    test_id: int,
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """
    Check statistical significance of test results

    Returns whether any variant has statistically significant results.
    """
    try:
        significance = engine.check_statistical_significance(test_id)

        return {
            "success": True,
            "test_id": test_id,
            "significance": significance
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SPECIALIZED TEST CREATION ENDPOINTS
# ============================================================================

@router.post("/tests/price", status_code=201)
def create_price_test(
    request: CreatePriceTestRequest,
    manager: PriceTestManager = Depends(get_price_manager)
):
    """
    Create a price A/B test (simplified)

    Automatically creates control and variant price points.
    """
    try:
        test = manager.create_price_test(
            product_id=request.product_id,
            store_id=request.store_id,
            current_price=request.current_price,
            test_prices=request.test_prices,
            test_name=request.test_name,
            duration_days=request.duration_days,
            traffic_split=request.traffic_split,
            min_sample_size=request.min_sample_size,
            auto_implement_winner=request.auto_implement_winner
        )

        return {
            "success": True,
            "test_id": test.id,
            "test_name": test.name,
            "message": "Price test created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tests/title", status_code=201)
def create_title_test(
    request: CreateTitleTestRequest,
    manager: ContentTestManager = Depends(get_content_manager)
):
    """Create a product title A/B test"""
    try:
        test = manager.create_title_test(
            product_id=request.product_id,
            store_id=request.store_id,
            current_title=request.current_title,
            variant_titles=request.variant_titles,
            test_name=request.test_name,
            duration_days=request.duration_days,
            min_sample_size=request.min_sample_size
        )

        return {
            "success": True,
            "test_id": test.id,
            "test_name": test.name,
            "message": "Title test created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tests/description", status_code=201)
def create_description_test(
    request: CreateDescriptionTestRequest,
    manager: ContentTestManager = Depends(get_content_manager)
):
    """Create a product description A/B test"""
    try:
        test = manager.create_description_test(
            product_id=request.product_id,
            store_id=request.store_id,
            current_description=request.current_description,
            variant_descriptions=request.variant_descriptions,
            test_name=request.test_name,
            duration_days=request.duration_days,
            min_sample_size=request.min_sample_size
        )

        return {
            "success": True,
            "test_id": test.id,
            "test_name": test.name,
            "message": "Description test created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tests/image", status_code=201)
def create_image_test(
    request: CreateImageTestRequest,
    manager: ContentTestManager = Depends(get_content_manager)
):
    """Create a product image A/B test"""
    try:
        test = manager.create_image_test(
            product_id=request.product_id,
            store_id=request.store_id,
            current_image_url=request.current_image_url,
            variant_image_urls=request.variant_image_urls,
            test_name=request.test_name,
            duration_days=request.duration_days,
            min_sample_size=request.min_sample_size
        )

        return {
            "success": True,
            "test_id": test.id,
            "test_name": test.name,
            "message": "Image test created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# EVENT TRACKING ENDPOINTS
# ============================================================================

@router.post("/events/variant")
def get_variant_for_visitor(
    request: GetVariantRequest,
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """
    Get variant assignment for a visitor

    Returns the variant this visitor should see (deterministic).
    """
    try:
        variant = engine.get_variant_for_visitor(
            request.test_id,
            request.visitor_id
        )

        if not variant:
            raise HTTPException(
                status_code=404,
                detail=f"Test {request.test_id} not found or not running"
            )

        return {
            "success": True,
            "variant_id": variant.id,
            "variant_name": variant.name,
            "config": variant.config
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events/impression")
def record_impression(
    request: RecordImpressionRequest,
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """
    Record that a visitor saw a variant

    Track impressions for conversion rate calculation.
    """
    try:
        engine.record_impression(
            test_id=request.test_id,
            variant_id=request.variant_id,
            visitor_id=request.visitor_id,
            metadata=request.metadata
        )

        return {
            "success": True,
            "message": "Impression recorded"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events/conversion")
def record_conversion(
    request: RecordConversionRequest,
    engine: ABTestEngine = Depends(get_ab_engine)
):
    """
    Record a conversion (purchase) event

    Track conversions for each variant.
    """
    try:
        engine.record_conversion(
            test_id=request.test_id,
            variant_id=request.variant_id,
            visitor_id=request.visitor_id,
            revenue=request.revenue,
            metadata=request.metadata
        )

        return {
            "success": True,
            "message": "Conversion recorded"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RECOMMENDATION ENDPOINTS
# ============================================================================

@router.get("/recommendations/price")
def get_price_recommendations(
    product_id: str,
    current_price: float,
    cost: float,
    competitor_prices: Optional[str] = Query(None, description="Comma-separated prices"),
    manager: PriceTestManager = Depends(get_price_manager)
):
    """
    Get AI-powered price optimization recommendations

    Query parameters:
    - product_id: Product ID
    - current_price: Current selling price
    - cost: Product cost
    - competitor_prices: Comma-separated competitor prices (optional)
    """
    try:
        # Parse competitor prices
        competitor_price_list = None
        if competitor_prices:
            competitor_price_list = [float(p.strip()) for p in competitor_prices.split(",")]

        recommendations = manager.recommend_price_points(
            product_id=product_id,
            current_price=current_price,
            cost=cost,
            competitor_prices=competitor_price_list
        )

        return {
            "success": True,
            "recommendations": recommendations
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


print("[SUCCESS] A/B Testing API routes loaded successfully")
