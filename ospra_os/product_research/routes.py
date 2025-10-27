"""Product Research API routes."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from ospra_os.core.settings import Settings, get_settings

from .scorer import ProductScorer
from .connectors.trends.google_trends import GoogleTrendsConnector
from .connectors.social.meta import MetaConnector
from .connectors.social.twitter import TwitterConnector
from .connectors.social.reddit import RedditConnector
from .connectors.suppliers.aliexpress import AliExpressConnector
from .connectors.suppliers.dhgate import DHgateConnector
from .connectors.suppliers.cjdropshipping import CJDropshippingConnector

router = APIRouter(prefix="/research", tags=["Product Research"])


class FindProductsRequest(BaseModel):
    """Request for finding product candidates."""

    query: Optional[str] = None  # Search term or category
    category: Optional[str] = None
    max_results: int = 10
    sources: List[str] = ["google_trends"]  # Which connectors to use
    min_score: float = 5.0  # Minimum score to return


class ProductResponse(BaseModel):
    """Product candidate response."""

    name: str
    score: float
    recommendation: str
    source: str
    details: dict


@router.post("/find-products", response_model=List[ProductResponse])
async def find_products(request: FindProductsRequest, settings: Settings = Depends(get_settings)):
    """
    Find and rank product candidates.

    Sources available:
    - google_trends: Google Trends (no API key needed)
    - meta: Facebook/Instagram (requires META_ACCESS_TOKEN)
    - twitter: Twitter/X (requires X_API_KEY)
    - reddit: Reddit (requires REDDIT_CLIENT_ID)
    - aliexpress: AliExpress (requires ALIEXPRESS_API_KEY)
    - dhgate: DHgate (requires DHGATE_API_KEY)
    - cjdropshipping: CJ Dropshipping (requires CJDROPSHIPPING_TOKEN)

    Example:
        {
            "query": "home decor",
            "category": "home_and_garden",
            "max_results": 10,
            "sources": ["google_trends", "aliexpress"],
            "min_score": 6.0
        }
    """
    # Initialize connectors based on requested sources
    connectors = []

    if "google_trends" in request.sources:
        connectors.append(GoogleTrendsConnector())

    if "meta" in request.sources:
        meta_token = getattr(settings, "META_ACCESS_TOKEN", None)
        connectors.append(MetaConnector(api_key=meta_token))

    if "twitter" in request.sources:
        twitter_key = getattr(settings, "X_API_KEY", None)
        connectors.append(TwitterConnector(api_key=twitter_key))

    if "reddit" in request.sources:
        reddit_id = getattr(settings, "REDDIT_CLIENT_ID", None)
        connectors.append(RedditConnector(api_key=reddit_id))

    if "aliexpress" in request.sources:
        ali_key = getattr(settings, "ALIEXPRESS_API_KEY", None)
        ali_secret = getattr(settings, "ALIEXPRESS_APP_SECRET", None)
        connectors.append(AliExpressConnector(api_key=ali_key, app_secret=ali_secret))

    if "dhgate" in request.sources:
        dh_key = getattr(settings, "DHGATE_API_KEY", None)
        connectors.append(DHgateConnector(api_key=dh_key))

    if "cjdropshipping" in request.sources:
        cj_token = getattr(settings, "CJDROPSHIPPING_TOKEN", None)
        connectors.append(CJDropshippingConnector(api_key=cj_token))

    if not connectors:
        raise HTTPException(status_code=400, detail="No valid sources specified")

    # Collect candidates from all connectors
    all_candidates = []

    for connector in connectors:
        if not connector.is_available():
            print(f"⚠️  {connector.name} not available (missing API key)")
            continue

        try:
            if request.query:
                # Search for specific query
                candidates = await connector.search(request.query, category=request.category)
            else:
                # Get trending products
                candidates = await connector.get_trending(category=request.category, limit=request.max_results)

            all_candidates.extend(candidates)
            print(f"✅ {connector.name}: Found {len(candidates)} candidates")

        except Exception as e:
            print(f"❌ {connector.name} error: {e}")
            continue

    if not all_candidates:
        return []

    # Score and rank candidates
    scorer = ProductScorer()
    ranked = scorer.rank(all_candidates, limit=request.max_results)

    # Filter by minimum score
    filtered = [r for r in ranked if r["score"] >= request.min_score]

    # Convert to response format
    return [
        ProductResponse(
            name=r["product"]["name"],
            score=r["score"],
            recommendation=r["recommendation"],
            source=r["product"]["source"],
            details=r["product"],
        )
        for r in filtered
    ]


@router.get("/trending")
async def get_trending_products(
    category: Optional[str] = None,
    source: str = "google_trends",
    limit: int = 10,
    settings: Settings = Depends(get_settings),
):
    """
    Get trending products from a specific source.

    Args:
        category: Product category filter
        source: Data source (google_trends, meta, twitter, reddit, aliexpress, etc.)
        limit: Max results

    Returns:
        List of trending products with scores
    """
    # Initialize the requested connector
    connector = None

    if source == "google_trends":
        connector = GoogleTrendsConnector()
    elif source == "meta":
        connector = MetaConnector(api_key=getattr(settings, "META_ACCESS_TOKEN", None))
    elif source == "twitter":
        connector = TwitterConnector(api_key=getattr(settings, "X_API_KEY", None))
    elif source == "reddit":
        connector = RedditConnector(api_key=getattr(settings, "REDDIT_CLIENT_ID", None))
    elif source == "aliexpress":
        connector = AliExpressConnector(
            api_key=getattr(settings, "ALIEXPRESS_API_KEY", None),
            app_secret=getattr(settings, "ALIEXPRESS_APP_SECRET", None)
        )
    elif source == "dhgate":
        connector = DHgateConnector(api_key=getattr(settings, "DHGATE_API_KEY", None))
    elif source == "cjdropshipping":
        connector = CJDropshippingConnector(api_key=getattr(settings, "CJDROPSHIPPING_TOKEN", None))
    else:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")

    if not connector.is_available():
        raise HTTPException(status_code=400, detail=f"{connector.name} API key not configured")

    # Get trending products
    candidates = await connector.get_trending(category=category, limit=limit)

    # Score them
    scorer = ProductScorer()
    ranked = scorer.rank(candidates, limit=limit)

    return ranked


@router.get("/sources")
async def list_sources(settings: Settings = Depends(get_settings)):
    """
    List all available data sources and their status.

    Returns which connectors are configured and ready to use.
    """
    sources = []

    # Check each connector
    connectors_to_check = [
        ("google_trends", GoogleTrendsConnector(), None),
        ("meta", MetaConnector(api_key=getattr(settings, "META_ACCESS_TOKEN", None)), "META_ACCESS_TOKEN"),
        ("twitter", TwitterConnector(api_key=getattr(settings, "X_API_KEY", None)), "X_API_KEY"),
        ("reddit", RedditConnector(api_key=getattr(settings, "REDDIT_CLIENT_ID", None)), "REDDIT_CLIENT_ID"),
        ("aliexpress", AliExpressConnector(
            api_key=getattr(settings, "ALIEXPRESS_API_KEY", None),
            app_secret=getattr(settings, "ALIEXPRESS_APP_SECRET", None)
        ), "ALIEXPRESS_API_KEY"),
        ("dhgate", DHgateConnector(api_key=getattr(settings, "DHGATE_API_KEY", None)), "DHGATE_API_KEY"),
        ("cjdropshipping", CJDropshippingConnector(api_key=getattr(settings, "CJDROPSHIPPING_TOKEN", None)), "CJDROPSHIPPING_TOKEN"),
    ]

    for source_id, connector, env_var in connectors_to_check:
        sources.append({
            "id": source_id,
            "name": connector.name,
            "available": connector.is_available(),
            "env_var": env_var,
        })

    return {
        "sources": sources,
        "configured_count": sum(1 for s in sources if s["available"]),
        "total_count": len(sources),
    }
