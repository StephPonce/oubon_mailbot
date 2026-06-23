"""Product Research API routes.

#57: legacy /research/* discovery endpoints retired (find-products, trending,
discover, validate, reddit/trending, twitter-viral, test-aliexpress) — they were
old discovery-v1 paths superseded by /api/discovery/*. Only the lightweight
/research/sources status endpoint is kept (a cheap connector-availability probe).
"""

from fastapi import APIRouter, Depends

from ospra_os.core.settings import Settings, get_settings

from .connectors.trends.google_trends import GoogleTrendsConnector
from .connectors.social.reddit import RedditConnector
from .connectors.suppliers.aliexpress import AliExpressConnector
from .connectors.suppliers.dhgate import DHgateConnector
from .connectors.suppliers.cjdropshipping import CJDropshippingConnector

router = APIRouter(prefix="/research", tags=["Product Research"])


@router.get("/sources")
async def list_sources(settings: Settings = Depends(get_settings)):
    """List available data sources and their configured/available status.

    Note: the X/Twitter and Meta connectors were retired from this probe (#57) —
    X is now an opt-in, off-by-default sentiment source (DISCOVERY_DISABLE_X) and
    Meta's organic Graph API is sunset; Meta signal comes from the Ad Library
    actor in the main discovery pipeline, not from this status endpoint.
    """
    connectors_to_check = [
        ("google_trends", GoogleTrendsConnector(), None),
        ("reddit", RedditConnector(
            client_id=getattr(settings, "REDDIT_CLIENT_ID", None),
            client_secret=getattr(settings, "REDDIT_SECRET", None),
        ), "REDDIT_CLIENT_ID"),
        ("aliexpress", AliExpressConnector(
            api_key=getattr(settings, "ALIEXPRESS_API_KEY", None),
            app_secret=getattr(settings, "ALIEXPRESS_APP_SECRET", None),
        ), "ALIEXPRESS_API_KEY"),
        ("dhgate", DHgateConnector(api_key=getattr(settings, "DHGATE_API_KEY", None)), "DHGATE_API_KEY"),
        ("cjdropshipping", CJDropshippingConnector(api_key=getattr(settings, "CJDROPSHIPPING_TOKEN", None)), "CJDROPSHIPPING_TOKEN"),
    ]

    sources = []
    for source_id, connector, env_var in connectors_to_check:
        sources.append({
            "id": source_id,
            "name": getattr(connector, "name", source_id),
            "available": connector.is_available(),
            "env_var": env_var,
        })

    return {
        "sources": sources,
        "configured_count": sum(1 for s in sources if s["available"]),
        "total_count": len(sources),
    }
