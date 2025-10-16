"""
Utilities for pulling external market signals (Google Trends + Amazon catalog).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential

from app.settings import get_settings
from app.ai_client import ai_client, extract_message_content, validate_ai_response

logger = logging.getLogger(__name__)

try:
    from python_amazon_paapi import AmazonApi  # type: ignore
except ImportError as exc:  # pragma: no cover - optional dependency
    AmazonApi = None  # type: ignore
    _AMAZON_IMPORT_ERROR = exc
else:
    _AMAZON_IMPORT_ERROR = None


async def _fetch_trends(keyword: str) -> Dict[str, Any]:
    """
    Fetch Google Trends data for the keyword. Falls back to empty dict if pytrends is missing.
    """

    try:
        from pytrends.request import TrendReq  # type: ignore
    except ImportError:
        logger.warning("pytrends not installed; skipping Google Trends fetch for '%s'.", keyword)
        return {}

    def _build_payload() -> Dict[str, Any]:
        try:
            pytrends = TrendReq(hl="en-US", tz=360)
            pytrends.build_payload([keyword], timeframe="today 3-m")
            data = pytrends.interest_over_time()
            if data is None:
                return {}
            if hasattr(data, "columns") and "isPartial" in data.columns:
                data = data.drop(columns=["isPartial"])
            return data.to_dict()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Google Trends fetch failed for '%s': %s", keyword, exc)
            return {}

    return await asyncio.to_thread(_build_payload)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=10), reraise=True)
async def get_external_trends(keyword: str) -> Dict[str, Any]:
    """
    Pull Google Trends metrics and related Amazon catalog listings for the supplied keyword.
    """
    trends = await _fetch_trends(keyword)

    if AmazonApi is None:
        raise ImportError(
            "python-amazon-paapi is required for Amazon lookups. Install via `pip install python-amazon-paapi`."
        ) from _AMAZON_IMPORT_ERROR

    settings = get_settings()
    if not settings.AMAZON_ACCESS_KEY:
        raise ValueError("Amazon creds missing in .env—signup amazon.com/associates for keys")
    if not settings.AMAZON_SECRET_KEY or not settings.AMAZON_ASSOC_TAG:
        raise ValueError("Amazon creds missing in .env—signup amazon.com/associates for keys")

    amazon_items: List[Dict[str, Any]] = []
    try:
        amazon = AmazonApi(
            settings.AMAZON_ACCESS_KEY,
            settings.AMAZON_SECRET_KEY,
            settings.AMAZON_ASSOC_TAG,
            (settings.AMAZON_COUNTRY or "us"),
        )
        amazon_results = amazon.search_keywords(
            keyword=keyword,
            resources=["ItemInfo.Title", "Offers.Listings.Price"],
        )
        items = getattr(amazon_results, "items", None)
        if items:
            amazon_items = [item.as_dict() for item in items]
    except Exception as exc:  # pragma: no cover - network/service faults
        logger.warning("Amazon PA-API lookup failed for '%s': %s", keyword, exc)

    ai_suggestions = ""
    prompt = (
        "Provide 3 concise ecommerce product ideas for the keyword '{kw}'. "
        "Use bullet points with price ranges between $15 and $800."
    ).format(kw=keyword)
    try:
        client = ai_client()

        def _create_completion() -> Any:
            model_name = "grok-beta" if settings.GROK_API_KEY else "gpt-4o"
            return client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
            )

        completion = await asyncio.to_thread(_create_completion)
        ai_content = extract_message_content(completion)
        if ai_content:
            ai_suggestions = validate_ai_response(ai_content, reasonable_prices=True)
    except ValueError as exc:
        logger.warning("AI suggestion rejected for '%s': %s", keyword, exc)
    except Exception as exc:
        logger.warning("AI suggestion generation failed for '%s': %s", keyword, exc)

    return {"trends": trends, "amazon": amazon_items, "ai_suggestions": ai_suggestions}


async def get_tiktok_research(keyword: str) -> Any:
    """Attempt to summarize public TikTok trends without using private APIs."""
    url = f"https://www.tiktok.com/search?q={keyword}"
    instructions = (
        f"Summarize public TikTok search results for '{keyword}'. Extract up to 5 relevant product or niche ideas "
        "without scraping gated content."
    )
    browse_page_fn = globals().get("browse_page")
    if browse_page_fn is None:
        return "TikTok research helper unavailable—add browse_page integration."
    try:
        result = await browse_page_fn(url, instructions)  # type: ignore[func-returns-value]
        return result
    except Exception as exc:
        logger.warning("TikTok research failed for '%s': %s", keyword, exc)
        return f"TikTok research error: {exc}—fallback to cached"


async def get_x_research(keyword: str) -> Any:
    """Leverage semantic search on X (Twitter) if available; otherwise return a stub."""
    x_search_fn = globals().get("x_semantic_search")
    if x_search_fn is None:
        return "X research helper unavailable—add x_semantic_search integration."
    try:
        result = await x_search_fn(keyword, limit=10)  # type: ignore[func-returns-value]
        return result
    except Exception as exc:
        logger.warning("X research failed for '%s': %s", keyword, exc)
        return f"X research error: {exc}—fallback to cached"


def product_research(keyword: str, store_token: str | None = None) -> Dict[str, Any]:
    """
    Synchronous helper that wraps get_external_trends for scheduled jobs or webhook triggers.
    The store_token parameter is reserved for future per-store personalization.
    """

    async def _runner() -> Dict[str, Any]:
        return await get_external_trends(keyword)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_runner())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:  # pragma: no cover
            pass
        asyncio.set_event_loop(None)
        loop.close()


__all__ = [
    "get_external_trends",
    "get_tiktok_research",
    "get_x_research",
    "product_research",
]
