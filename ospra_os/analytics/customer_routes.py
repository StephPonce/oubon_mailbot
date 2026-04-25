"""
Customer Analytics API Routes

Endpoints for customer analytics, segmentation, LTV, churn prediction, and cohort analysis
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import logging

from ospra_os.analytics.customer_analytics import CustomerAnalytics
from ospra_os.analytics.ltv_calculator import get_ltv_calculator
from ospra_os.analytics.churn_predictor import get_churn_predictor
from ospra_os.analytics.cohort_analyzer import get_cohort_analyzer
from ospra_os.analytics.purchase_patterns import get_purchase_pattern_analyzer
from ospra_os.analytics.customer_sync import create_customer_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/customers", tags=["Customer Analytics"])


# ==================== Mock Data Helper ====================

def get_mock_customers():
    """
    Get customer data from database

    Returns empty list if no customers synced yet.
    Use POST /api/customers/sync/shopify to sync from Shopify.
    """
    # TODO: Query actual database instead of returning empty list
    # For now, return empty list until Shopify sync is triggered
    return []


# ==================== Overview & Dashboard ====================

@router.get("/overview")
async def get_customer_overview():
    """
    Get high-level customer analytics overview

    Returns summary metrics for dashboard
    """
    logger.info("[STATS] GET /api/customers/overview")

    # TODO: Replace with actual database queries
    mock_customers = get_mock_customers()
    analytics = CustomerAnalytics()

    # Calculate overview metrics
    total_customers = len(mock_customers)
    total_ltv = sum(c.get('ltv', 0) for c in mock_customers)
    avg_ltv = total_ltv / total_customers if total_customers > 0 else 0

    # Get segment breakdown
    segments = await analytics.get_segment_breakdown(mock_customers)

    # Get at-risk count
    churn_predictor = get_churn_predictor()
    at_risk = await churn_predictor.get_at_risk_customers(mock_customers, threshold=0.5, limit=100)

    overview = {
        "total_customers": total_customers,
        "total_ltv": round(total_ltv, 2),
        "avg_ltv": round(avg_ltv, 2),
        "at_risk_count": len(at_risk),
        "high_value_count": len([c for c in mock_customers if c.get('ltv', 0) > 300]),
        "segments": segments,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    return overview


@router.get("/segments")
async def get_customer_segments():
    """
    Get customer segmentation breakdown

    Returns RFM segments with customer counts and metrics
    """
    logger.info("[STATS] GET /api/customers/segments")

    mock_customers = get_mock_customers()
    analytics = CustomerAnalytics()

    segments = await analytics.get_segment_breakdown(mock_customers)

    return {
        "segments": segments,
        "total_customers": len(mock_customers),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# ==================== Individual Customer ====================

@router.get("/{customer_id}/profile")
async def get_customer_profile(customer_id: str):
    """
    Get complete customer profile with all metrics

    Includes: RFM scores, segment, LTV, churn risk, purchase patterns
    """
    logger.info(f" GET /api/customers/{customer_id}/profile")

    # TODO: Fetch from database
    mock_customers = get_mock_customers()
    customer_data = next((c for c in mock_customers if c['customer_id'] == customer_id), None)

    if not customer_data:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    analytics = CustomerAnalytics()
    profile = await analytics.get_customer_profile(customer_id, customer_data)

    return profile


@router.get("/{customer_id}/ltv")
async def get_customer_ltv(customer_id: str):
    """
    Get LTV breakdown for customer

    Includes historical, predicted, and confidence scores
    """
    logger.info(f"[PRICE] GET /api/customers/{customer_id}/ltv")

    mock_customers = get_mock_customers()
    customer_data = next((c for c in mock_customers if c['customer_id'] == customer_id), None)

    if not customer_data:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    analytics = CustomerAnalytics()
    profile = await analytics.get_customer_profile(customer_id, customer_data)

    ltv_calculator = get_ltv_calculator()
    ltv_analysis = await ltv_calculator.calculate_predictive_ltv(customer_id, profile)

    return ltv_analysis


@router.get("/{customer_id}/churn-risk")
async def get_customer_churn_risk(customer_id: str):
    """
    Get churn risk analysis for customer

    Includes probability, risk factors, and recommended actions
    """
    logger.info(f"[WARNING]  GET /api/customers/{customer_id}/churn-risk")

    mock_customers = get_mock_customers()
    customer_data = next((c for c in mock_customers if c['customer_id'] == customer_id), None)

    if not customer_data:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    analytics = CustomerAnalytics()
    profile = await analytics.get_customer_profile(customer_id, customer_data)

    churn_predictor = get_churn_predictor()
    churn_analysis = await churn_predictor.get_churn_factors(customer_id, profile)

    return churn_analysis


@router.get("/{customer_id}/purchase-patterns")
async def get_customer_purchase_patterns(customer_id: str):
    """
    Get purchase pattern analysis for customer

    Includes timing patterns, product preferences, cart behavior
    """
    logger.info(f"[SHOP] GET /api/customers/{customer_id}/purchase-patterns")

    mock_customers = get_mock_customers()
    customer_data = next((c for c in mock_customers if c['customer_id'] == customer_id), None)

    if not customer_data:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    pattern_analyzer = get_purchase_pattern_analyzer()
    patterns = await pattern_analyzer.get_complete_pattern_profile(
        customer_id,
        customer_data,
        mock_customers
    )

    return patterns


# ==================== At-Risk Customers ====================

@router.get("/at-risk")
async def get_at_risk_customers(
    threshold: float = Query(0.5, ge=0.0, le=1.0, description="Minimum churn probability"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results")
):
    """
    Get customers at risk of churning

    Sorted by churn probability (high LTV customers first)
    """
    logger.info(f"[WARNING]  GET /api/customers/at-risk (threshold: {threshold}, limit: {limit})")

    mock_customers = get_mock_customers()
    churn_predictor = get_churn_predictor()

    at_risk = await churn_predictor.get_at_risk_customers(mock_customers, threshold, limit)

    return {
        "at_risk_customers": at_risk,
        "total_count": len(at_risk),
        "threshold": threshold,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# ==================== Cohort Analysis ====================

@router.get("/cohorts")
async def get_cohort_analysis(
    cohort_type: str = Query("monthly", pattern="^(monthly|weekly)$"),
    periods: int = Query(12, ge=1, le=24)
):
    """
    Get cohort retention analysis

    Shows retention rates by acquisition cohort over time
    """
    logger.info(f"[STATS] GET /api/customers/cohorts (type: {cohort_type}, periods: {periods})")

    mock_customers = get_mock_customers()
    cohort_analyzer = get_cohort_analyzer()

    cohort_table = await cohort_analyzer.get_cohort_table(mock_customers, cohort_type, periods)

    return cohort_table


@router.get("/cohorts/ltv")
async def get_cohort_ltv():
    """
    Get LTV breakdown by cohort

    Shows average LTV per acquisition cohort
    """
    logger.info("[PRICE] GET /api/customers/cohorts/ltv")

    mock_customers = get_mock_customers()
    cohort_analyzer = get_cohort_analyzer()

    cohort_ltv = await cohort_analyzer.get_cohort_ltv(mock_customers, 'monthly')

    return {
        "cohort_ltv": cohort_ltv,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/cohorts/best")
async def get_best_cohorts():
    """
    Identify best performing cohorts

    Returns cohorts with highest retention and LTV
    """
    logger.info("[TOP] GET /api/customers/cohorts/best")

    mock_customers = get_mock_customers()
    cohort_analyzer = get_cohort_analyzer()

    best_cohorts = await cohort_analyzer.identify_best_cohorts(mock_customers)

    return best_cohorts


# ==================== LTV Analysis ====================

@router.get("/ltv/by-segment")
async def get_ltv_by_segment():
    """
    Get average LTV by customer segment
    """
    logger.info("[STATS] GET /api/customers/ltv/by-segment")

    mock_customers = get_mock_customers()
    ltv_calculator = get_ltv_calculator()

    segment_ltv = ltv_calculator.calculate_ltv_by_segment(mock_customers)

    return {
        "segment_ltv": segment_ltv,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/ltv/by-source")
async def get_ltv_by_source():
    """
    Get average LTV by acquisition source
    """
    logger.info("[STATS] GET /api/customers/ltv/by-source")

    mock_customers = get_mock_customers()
    ltv_calculator = get_ltv_calculator()

    source_ltv = ltv_calculator.calculate_ltv_by_acquisition_source(mock_customers)

    return {
        "source_ltv": source_ltv,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/ltv/top-customers")
async def get_top_customers_by_ltv(
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get top customers by LTV
    """
    logger.info(f"[TOP] GET /api/customers/ltv/top-customers (limit: {limit})")

    mock_customers = get_mock_customers()

    # Sort by LTV
    sorted_customers = sorted(
        mock_customers,
        key=lambda x: x.get('ltv', 0),
        reverse=True
    )

    top_customers = sorted_customers[:limit]

    return {
        "top_customers": top_customers,
        "total_count": len(top_customers),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/ltv/distribution")
async def get_ltv_distribution():
    """
    Get LTV distribution bucketed by ranges
    """
    logger.info("[STATS] GET /api/customers/ltv/distribution")

    mock_customers = get_mock_customers()

    # Define LTV buckets
    buckets = [
        {"range": "$0-50", "min": 0, "max": 50},
        {"range": "$50-100", "min": 50, "max": 100},
        {"range": "$100-200", "min": 100, "max": 200},
        {"range": "$200-300", "min": 200, "max": 300},
        {"range": "$300-500", "min": 300, "max": 500},
        {"range": "$500+", "min": 500, "max": 999999},
    ]

    # Count customers in each bucket
    total_customers = len(mock_customers)
    distribution = []

    for bucket in buckets:
        customers_in_bucket = [
            c for c in mock_customers
            if bucket["min"] <= c.get("ltv", 0) < bucket["max"]
        ]
        count = len(customers_in_bucket)
        total_ltv = sum(c.get("ltv", 0) for c in customers_in_bucket)
        percentage = (count / total_customers * 100) if total_customers > 0 else 0

        distribution.append({
            "range": bucket["range"],
            "min": bucket["min"],
            "max": bucket["max"],
            "count": count,
            "percentage": round(percentage, 1),
            "total_ltv": round(total_ltv, 2)
        })

    return {
        "distribution": distribution,
        "total_customers": total_customers,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# ==================== Purchase Patterns ====================

@router.get("/patterns/timing")
async def get_global_timing_patterns():
    """
    Get global purchase timing patterns

    Shows peak days and hours across all customers
    """
    logger.info("[ALARM] GET /api/customers/patterns/timing")

    mock_customers = get_mock_customers()
    all_orders = []
    for customer in mock_customers:
        all_orders.extend(customer.get('orders', []))

    pattern_analyzer = get_purchase_pattern_analyzer()
    timing_patterns = await pattern_analyzer.get_global_timing_patterns(all_orders)

    return timing_patterns


@router.get("/patterns/product-affinity")
async def get_product_affinity():
    """
    Get product affinity analysis

    Shows which products are frequently bought together
    """
    logger.info("[LINK] GET /api/customers/patterns/product-affinity")

    mock_customers = get_mock_customers()
    all_orders = []
    for customer in mock_customers:
        all_orders.extend(customer.get('orders', []))

    pattern_analyzer = get_purchase_pattern_analyzer()
    affinity = await pattern_analyzer.analyze_product_affinity(all_orders)

    return affinity


# ==================== Sync Operations ====================

@router.post("/sync/shopify")
async def sync_from_shopify(
    shopify_store: str = Query(..., description="Shopify store URL"),
    shopify_token: str = Query(..., description="Shopify API token"),
    full_sync: bool = Query(False, description="Full sync or incremental")
):
    """
    Sync customers from Shopify

    Fetches customers and orders, calculates metrics, saves to database
    """
    logger.info(f"[REFRESH] POST /api/customers/sync/shopify (store: {shopify_store}, full: {full_sync})")

    try:
        sync = create_customer_sync(shopify_store, shopify_token)

        if full_sync:
            customers = await sync.sync_all_customers(
                include_orders=True,
                calculate_metrics=True,
                save_to_db=True
            )
        else:
            # Incremental sync (last 24 hours)
            since = datetime.now(timezone.utc) - timedelta(days=1)
            customers = await sync.sync_updated_customers(since, save_to_db=True)

        return {
            "success": True,
            "customers_synced": len(customers),
            "sync_type": "full" if full_sync else "incremental",
            "synced_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"[ERROR] Sync error: {e}")
        raise HTTPException(status_code=500, detail="Customer sync failed. Please try again.")


@router.post("/sync/shopify/{customer_id}")
async def sync_single_customer(
    customer_id: str,
    shopify_store: str = Query(..., description="Shopify store URL"),
    shopify_token: str = Query(..., description="Shopify API token")
):
    """
    Sync a single customer from Shopify
    """
    logger.info(f"[REFRESH] POST /api/customers/sync/shopify/{customer_id}")

    try:
        sync = create_customer_sync(shopify_store, shopify_token)
        customer = await sync.sync_single_customer(customer_id, save_to_db=True)

        if not customer:
            raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found in Shopify")

        return {
            "success": True,
            "customer": customer,
            "synced_at": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Sync error: {e}")
        raise HTTPException(status_code=500, detail="Customer sync failed. Please try again.")


# ==================== Search & Filter ====================

@router.get("/search")
async def search_customers(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Search customers by email, name, or customer ID
    """
    logger.info(f"[SEARCH] GET /api/customers/search (query: {query})")

    mock_customers = get_mock_customers()

    # Simple search implementation
    query_lower = query.lower()
    results = [
        c for c in mock_customers
        if query_lower in c.get('email', '').lower()
        or query_lower in c.get('first_name', '').lower()
        or query_lower in c.get('last_name', '').lower()
        or query_lower in c.get('customer_id', '').lower()
    ]

    return {
        "results": results[:limit],
        "total_count": len(results),
        "query": query
    }


logger.info("[SUCCESS] Customer Analytics API routes loaded")
