"""
Amazon Movers / New-Releases / Bestsellers connector — Task #28 / #31.

================================================================================
WHY THIS EXISTS (and why it's no longer "RSS")
================================================================================
Originally hit Amazon's public RSS feeds at:

    https://www.amazon.com/gp/movers-and-shakers/<category>/index.rss

In May 2026 Amazon retired RSS feed functionality globally — every RSS
endpoint now returns 404. Confirmed via multiple third-party docs
(ASA2 affiliate plugin, RSS aggregator services). This is not a URL
change — the feature is gone. See Task #28 resolution notes.

The connector has been re-platformed onto the Apify
`junglee/amazon-bestsellers` actor (already wired in `base_apify.py`)
which scrapes the equivalent HTML pages. The actor is paid-per-result
(~$0.30/1k items) but Ospra already has an active subscription used
for other connectors.

The public interface (.fetch, .extract_keywords, .resolve_category)
is unchanged — discovery engine + sources-health probe consume this
the same way they did the RSS version.

================================================================================
WHAT WE GET
================================================================================
Per item: title, ASIN, product URL, image URL, price, rating,
reviews_count, bestseller_rank. The Apify actor doesn't expose
rank-delta the way RSS did, so movers/new-releases vs bestsellers
distinction is mostly cosmetic until we wire a dedicated movers actor
(future work — Task #31 follow-up).

================================================================================
LIMITATIONS
================================================================================
- The `junglee/amazon-bestsellers` actor is best-tuned for the
  `/Best-Sellers-*/zgbs/` URL pattern. Movers and New-Releases pages
  have similar HTML structure so the actor mostly works on them, but
  some fields (rank-delta) won't populate. If we find a dedicated
  Amazon Movers actor later, swap in `APIFY_AMAZON_MOVERS_ACTOR` env.
- Apify is paid per result. The default `max_items=20` keeps spend low.
- Apify has a cold-start time (5-30s); we keep the 10-minute response
  cache from the RSS version to avoid repeat costs.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# HTML page URLs. The Apify actor scrapes these directly.
# Movers and New-Releases use the standard /gp/ path; Bestsellers
# can use either /gp/bestsellers/ or /Best-Sellers-*/zgbs/ (the
# bestsellers actor was built around the latter).
AMAZON_PAGE_URLS: dict[str, str] = {
    "movers":       "https://www.amazon.com/gp/movers-and-shakers/{category}/",
    "new_releases": "https://www.amazon.com/gp/new-releases/{category}/",
    "bestsellers":  "https://www.amazon.com/gp/bestsellers/{category}/",
}

# Map Ospra niches → Amazon category slugs. These are what appear in
# the URL path segment of each Amazon category page. To add a new
# niche, visit amazon.com/gp/bestsellers, drill into the category, and
# copy the slug from the URL.
DEFAULT_CATEGORY_MAP: dict[str, str] = {
    "smart_home": "electronics",
    "tech": "electronics",
    "electronics": "electronics",
    "gaming": "videogames",
    "phone": "electronics",
    "kitchen": "kitchen",
    "home_decor": "home-garden",
    "fitness": "sporting-goods",
    "outdoor": "sporting-goods",
    "beauty": "beauty",
    "skincare": "beauty",
    "pet": "pet-supplies",
    "baby": "baby-products",
    "office": "office-products",
    "toys": "toys-and-games",
    "car": "automotive",
    "jewelry": "jewelry",
    "watches": "watches",
    "bags": "fashion-handbags",
    "led": "tools",
}

# Per-process response cache keyed by feed_type:category. Apify is
# paid per result — the cache prevents repeat charges for the same
# query within the TTL window.
_RESPONSE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL = int(os.getenv("AMAZON_MOVERS_CACHE_TTL_SECONDS", "600"))

# Default actor. Override with APIFY_AMAZON_MOVERS_ACTOR if a
# better one becomes available (e.g. a dedicated movers scraper).
DEFAULT_ACTOR = os.getenv(
    "APIFY_AMAZON_MOVERS_ACTOR",
    "junglee/amazon-bestsellers",
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_apify_item(raw: dict[str, Any], category: str, feed_type: str) -> Optional[dict[str, Any]]:
    """Map one item from the Apify amazon-bestsellers actor's dataset
    into the discovery dict shape the consuming code expects.

    The actor returns slightly different field names depending on which
    Amazon page it's pointed at; we read each field with a small
    cascade of aliases so the parser handles all three page types
    (movers / new-releases / bestsellers) from the same code.
    """
    if not isinstance(raw, dict):
        return None

    title = (raw.get("title") or raw.get("name") or "").strip()
    if not title:
        return None

    # ASIN: try direct field, then extract from URL
    asin = (raw.get("asin") or "").strip() or None
    url = (raw.get("url") or raw.get("productUrl") or raw.get("link") or "").strip() or None
    if not asin and url and "/dp/" in url:
        try:
            asin = url.split("/dp/", 1)[1].split("/", 1)[0].split("?", 1)[0][:10]
        except Exception:
            asin = None

    # Price: actor sometimes returns dict {value, currency}, sometimes float, sometimes "$12.34" string
    price_raw = raw.get("price")
    if isinstance(price_raw, dict):
        price = _safe_float(price_raw.get("value"))
    elif isinstance(price_raw, str):
        cleaned = price_raw.replace("$", "").replace(",", "").strip()
        price = _safe_float(cleaned)
    else:
        price = _safe_float(price_raw)

    image_url = (
        raw.get("image")
        or raw.get("imageUrl")
        or raw.get("thumbnailImage")
        or None
    )

    rating = _safe_float(raw.get("rating") or raw.get("stars"))
    reviews_count = _safe_int(raw.get("reviewsCount") or raw.get("reviews") or 0)
    current_rank = _safe_int(raw.get("rank") or raw.get("bestsellersRank") or raw.get("position") or 0) or None

    return {
        "title": title,
        "asin": asin,
        "product_url": url,
        "image_url": image_url,
        "price": price,
        "rating": rating,
        "reviews_count": reviews_count,
        # The Apify actor doesn't expose rank-delta the way RSS did; surface
        # the current rank only. Discovery engine treats "in the top N of a
        # movers page" as the velocity signal — order alone carries it.
        "rank_previous": None,
        "rank_current": current_rank,
        "rank_delta": None,
        "category": category,
        "feed_type": feed_type,
        "in_stock": bool(raw.get("inStock", True)),
        "source": f"amazon_apify_{feed_type}",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


class AmazonMoversRSS:
    """Async client for Amazon Movers / New-Releases / Bestsellers via Apify.

    Class name kept as `AmazonMoversRSS` for backward compatibility — the
    consuming code (discovery engine, sources-health probe) imports this
    name. Internally we're now hitting Apify, not RSS.
    """

    def __init__(self, *, timeout_seconds: int = 90):
        # Apify cold-starts can be slow; a 12s timeout would not be enough.
        # The cache absorbs the cold-start cost on subsequent calls.
        self._timeout_secs = timeout_seconds
        self._apify_client = None  # lazy-init on first call

    def _get_apify_client(self):
        """Lazy-instantiate the Apify client. Returns None if no token
        is configured — caller treats that as unavailable."""
        if self._apify_client is not None:
            return self._apify_client

        try:
            from ospra_os.product_research.connectors.apify.base_apify import (
                ApifyClient,
            )
        except Exception as exc:
            logger.warning(f"[amazon] ApifyClient import failed: {exc}")
            return None

        if not os.getenv("APIFY_API_TOKEN"):
            return None

        try:
            self._apify_client = ApifyClient()
        except Exception as exc:
            logger.warning(f"[amazon] ApifyClient init failed: {exc}")
            return None
        return self._apify_client

    def is_available(self) -> bool:
        """Available iff APIFY_API_TOKEN is set. Was True for the RSS
        version (no auth needed) — now False without Apify."""
        return bool(os.getenv("APIFY_API_TOKEN"))

    def resolve_category(self, niche: str) -> Optional[str]:
        """Map an Ospra niche key to an Amazon category slug.
        Returns None if no clean mapping exists; callers should
        fall through to a default (`electronics`) or skip this source.
        """
        if not niche:
            return None
        return DEFAULT_CATEGORY_MAP.get(niche.lower())

    async def fetch(
        self,
        niche_or_category: str,
        *,
        feed_type: str = "movers",
        max_items: int = 30,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Pull Amazon trending products for `niche_or_category` via Apify.

        `feed_type` controls which Amazon page to scrape:
          - "movers"       — biggest 24h sales-rank gains (velocity leaders)
          - "new_releases" — products launched in the last 30 days
          - "bestsellers"  — all-time top sellers

        Accepts either an Ospra niche key (`smart_home`, `pet`) or a
        raw Amazon slug (`electronics`, `pet-supplies`). Returns the same
        payload shape the RSS connector used:

          {
            "available": bool,
            "category": str,             # Amazon slug used
            "niche": str,                # original input
            "feed_type": str,
            "items": [normalised, ...],
            "item_count": int,
            "fetched_at": ISO str,
            "cached": bool,
            "error": str | None,
          }

        Never raises — failures return `{"available": False, "error": ...}`.
        """
        if not niche_or_category:
            return {"available": False, "error": "empty niche/category"}

        category = self.resolve_category(niche_or_category) or niche_or_category
        if not category:
            return {
                "available": False,
                "error": f"no category mapping for niche '{niche_or_category}'",
            }

        # Validate feed_type
        if feed_type not in AMAZON_PAGE_URLS:
            return {
                "available": False,
                "category": category,
                "niche": niche_or_category,
                "error": (
                    f"unknown feed_type '{feed_type}'. "
                    f"Valid: {sorted(AMAZON_PAGE_URLS.keys())}"
                ),
            }

        # Cache check — same TTL strategy as the RSS version
        cache_key = f"{feed_type}:{category}"
        if use_cache:
            cached = _RESPONSE_CACHE.get(cache_key)
            if cached and (time.time() - cached[0]) < _CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["niche"] = niche_or_category
                if max_items < len(payload.get("items") or []):
                    payload["items"] = payload["items"][:max_items]
                    payload["item_count"] = len(payload["items"])
                return payload

        client = self._get_apify_client()
        if client is None:
            return {
                "available": False,
                "category": category,
                "niche": niche_or_category,
                "error": "apify_not_configured",
            }

        url = AMAZON_PAGE_URLS[feed_type].format(category=category)

        # The junglee/amazon-bestsellers actor accepts a categoryUrls
        # array and a maxItems cap. It uses residential proxies by default
        # which is appropriate for Amazon (which blocks datacenter IPs
        # aggressively).
        run_input = {
            "categoryUrls": [{"url": url}],
            "maxItems": int(max_items),
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        }

        try:
            results = await client.run_actor(
                actor_id=DEFAULT_ACTOR,
                run_input=run_input,
                timeout_secs=self._timeout_secs,
                memory_mbytes=1024,
            )
        except Exception as exc:
            logger.warning(f"[amazon:{feed_type}] actor run failed: {exc}")
            return {
                "available": False,
                "category": category,
                "niche": niche_or_category,
                "feed_type": feed_type,
                "error": f"apify_error: {exc}",
            }

        if not results:
            return {
                "available": False,
                "category": category,
                "niche": niche_or_category,
                "feed_type": feed_type,
                "error": "apify_returned_no_items",
            }

        items: list[dict[str, Any]] = []
        for raw in results:
            norm = _normalise_apify_item(raw, category, feed_type)
            if norm is not None:
                items.append(norm)
            if len(items) >= max_items:
                break

        if not items:
            return {
                "available": False,
                "category": category,
                "niche": niche_or_category,
                "feed_type": feed_type,
                "error": "no_items_parseable",
            }

        payload = {
            "available": True,
            "category": category,
            "niche": niche_or_category,
            "feed_type": feed_type,
            "items": items,
            "item_count": len(items),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
            "error": None,
        }

        # Only cache successful, non-empty responses
        _RESPONSE_CACHE[cache_key] = (time.time(), payload)
        return payload

    def extract_keywords(self, payload: dict[str, Any], *, top_n: int = 8) -> list[str]:
        """Pull the most useful trending phrases out of a fetch payload.

        Amazon titles are long ("Apple AirPods Pro (2nd Generation)
        Wireless Earbuds, Up to 2x More Active Noise Cancelling...").
        We extract the first 3 meaningful tokens of each so they're
        usable as supplier-search queries downstream.
        """
        if not payload or not payload.get("items"):
            return []
        out: list[str] = []
        noise = {
            "the", "and", "for", "with", "from", "your",
            "all", "new", "best", "top", "only", "more",
            "pro", "plus", "mini", "max",
        }
        for item in payload["items"][:top_n]:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            tokens: list[str] = []
            for raw_t in title.split():
                t = raw_t.strip(",.()[]:;-")
                if not t or len(t) <= 2:
                    continue
                if t.startswith("(") or t.endswith(")"):
                    continue
                if t.lower() in noise:
                    continue
                tokens.append(t)
                if len(tokens) >= 3:
                    break
            if tokens:
                out.append(" ".join(tokens))
        return out


# ----------------------------------------------------------------------
# Singleton — one client per process.
# ----------------------------------------------------------------------
_singleton: Optional[AmazonMoversRSS] = None


def get_amazon_movers_rss() -> AmazonMoversRSS:
    """Return the process-wide client, creating on first use.
    Function name kept for backward compatibility with importers."""
    global _singleton
    if _singleton is None:
        _singleton = AmazonMoversRSS()
    return _singleton
