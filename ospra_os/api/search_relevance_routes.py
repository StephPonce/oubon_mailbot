"""
SEARCH RELEVANCE API ROUTES
============================

Endpoints for testing and using the search relevance filter.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Optional
from pydantic import BaseModel

from ospra_os.product_research.search_relevance_filter import (
    SearchRelevanceFilter,
    QueryOptimizer,
    RelevanceScore
)

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

router = APIRouter(prefix="/api/search-relevance", tags=["Search Relevance"])


class ProductToScore(BaseModel):
    """Product to score for relevance."""
    title: str
    id: str = ""
    category: Optional[str] = None


class ScoreRequest(BaseModel):
    """Request to score products against a query."""
    query: str
    products: List[ProductToScore]
    min_relevance_score: float = 30.0
    min_keyword_match: float = 0.2


class FilterRequest(BaseModel):
    """Request to filter a list of products."""
    query: str
    products: List[Dict]
    title_key: str = "name"
    min_results: int = 3
    strict_mode: bool = False


@router.post("/score")
async def score_products(request: ScoreRequest, current_user: User = Depends(get_current_user)):
    """
    Score products for relevance to a search query.
    
    Returns detailed breakdown of why each product is/isn't relevant.
    """
    filter_instance = SearchRelevanceFilter(
        min_relevance_score=request.min_relevance_score,
        min_keyword_match=request.min_keyword_match
    )
    
    results = []
    for product in request.products:
        score = filter_instance.score_product(
            product_title=product.title,
            query=request.query,
            product_id=product.id,
            product_category=product.category
        )
        
        results.append({
            "product_id": score.product_id,
            "product_title": score.product_title,
            "query": score.query,
            "title_similarity": round(score.title_similarity, 3),
            "keyword_match_ratio": round(score.keyword_match_ratio, 3),
            "category_match": score.category_match,
            "has_negative_keywords": score.has_negative_keywords,
            "final_score": round(score.final_score, 1),
            "is_relevant": score.is_relevant,
            "rejection_reason": score.rejection_reason
        })
    
    # Sort by score
    results.sort(key=lambda x: x["final_score"], reverse=True)
    
    relevant_count = sum(1 for r in results if r["is_relevant"])
    
    return {
        "success": True,
        "query": request.query,
        "total_products": len(results),
        "relevant_count": relevant_count,
        "filtered_count": len(results) - relevant_count,
        "results": results
    }


@router.post("/filter")
async def filter_products(request: FilterRequest, current_user: User = Depends(get_current_user)):
    """
    Filter a list of products by relevance.
    
    Returns only products that pass the relevance threshold.
    """
    filter_instance = SearchRelevanceFilter(
        strict_mode=request.strict_mode
    )
    
    filtered = filter_instance.filter_with_fallback(
        products=request.products,
        query=request.query,
        title_key=request.title_key,
        min_results=request.min_results,
        return_scores=True
    )
    
    return {
        "success": True,
        "query": request.query,
        "input_count": len(request.products),
        "output_count": len(filtered),
        "filtered_count": len(request.products) - len(filtered),
        "products": filtered
    }


@router.get("/optimize-query")
async def optimize_query(
    query: str = Query(..., description="Search query to optimize"),
    current_user: User = Depends(get_current_user)
):
    """
    Optimize a search query by removing noise words.
    
    Also returns alternative queries for broader search.
    """
    optimized = QueryOptimizer.optimize_query(query)
    alternatives = QueryOptimizer.generate_alternatives(query)
    
    return {
        "success": True,
        "original_query": query,
        "optimized_query": optimized,
        "alternatives": alternatives,
        "word_reduction": f"{len(query.split())} → {len(optimized.split())} words"
    }


@router.get("/test")
async def test_relevance_filter(current_user: User = Depends(get_current_user)):
    """
    Test the relevance filter with example data.
    
    Demonstrates how the filter catches off-topic results.
    """
    # Real examples from the diagnostic report
    test_cases = [
        {
            "query": "fung's kitchen",
            "product": "Wire Entry Gland Box Solar Panel",
            "expected": False,
            "note": "Clearly irrelevant - solar panel vs kitchen"
        },
        {
            "query": "smart and final christmas hours",
            "product": "SONOFF Zigbee Switch",
            "expected": False,
            "note": "Query is about store hours, not smart switches"
        },
        {
            "query": "nerovet ai smart dentistry",
            "product": "ICY DBS Blyth doll",
            "expected": False,
            "note": "Dental AI vs toy doll - completely unrelated"
        },
        {
            "query": "zebra rs5100 bluetooth ring scanner",
            "product": "Zebra Sarasa pen",
            "expected": False,
            "note": "Scanner vs pen - 'Zebra' brand confusion"
        },
        {
            "query": "smart plug wifi",
            "product": "WiFi Smart Plug Socket Remote Control",
            "expected": True,
            "note": "Should match - relevant product"
        },
        {
            "query": "led strip lights",
            "product": "RGB LED Strip Light 5M WiFi Smart",
            "expected": True,
            "note": "Should match - relevant product"
        }
    ]
    
    filter_instance = SearchRelevanceFilter()
    results = []
    
    for case in test_cases:
        score = filter_instance.score_product(
            product_title=case["product"],
            query=case["query"]
        )
        
        passed = score.is_relevant == case["expected"]
        
        results.append({
            "query": case["query"],
            "product": case["product"],
            "expected_relevant": case["expected"],
            "actual_relevant": score.is_relevant,
            "test_passed": passed,
            "score": round(score.final_score, 1),
            "note": case["note"],
            "rejection_reason": score.rejection_reason
        })
    
    passed_count = sum(1 for r in results if r["test_passed"])
    
    return {
        "success": True,
        "test_results": results,
        "passed": passed_count,
        "total": len(results),
        "pass_rate": f"{(passed_count/len(results))*100:.0f}%"
    }


@router.get("/categories")
async def get_category_patterns(current_user: User = Depends(get_current_user)):
    """
    Get the category detection patterns used by the filter.
    """
    filter_instance = SearchRelevanceFilter()
    
    return {
        "success": True,
        "category_patterns": filter_instance.CATEGORY_PATTERNS,
        "category_negative_keywords": filter_instance.CATEGORY_NEGATIVE_KEYWORDS,
        "global_negative_keywords": list(filter_instance.GLOBAL_NEGATIVE_KEYWORDS)
    }
