"""
Amazon Movers & Shakers RSS connector — Task #12 / winner-proof source #3.

================================================================================
WHY THIS EXISTS
================================================================================
Amazon publishes a public RSS feed at:

    https://www.amazon.com/gp/movers-and-shakers/<category-slug>/index.rss

The feed lists the top 100 products in each category with the biggest
RANK GAIN over the past 24 hours — i.e. velocity leaders, products
gaining sales momentum RIGHT NOW. This is one of the strongest
"early-stage trending" signals available, AND it's free.

We already have a paid Apify-based `scrape_movers_and_shakers` method on
`AmazonBestsellersScraper`, but the task description specifically calls
out RSS — free, no auth, no quota, no scraping liability. The RSS feed
also surfaces an explicit `salesRank` change (`#1 → #5`) field which
Apify doesn't normalise the same way.

================================================================================
WHAT WE GET
================================================================================
Per item: title, ASIN, product URL, image URL, price (when shown),
salesRank delta, category position. We map these to a normalised dict
the discovery engine can merge with AE/CJ supplier data and use as a
keyword source for trending-niche queries.

================================================================================
SCOPE
================================================================================
This is intentionally minimal:
  - `fetch(category)` → list of normalised movers
  - 10-minute response cache (Amazon refreshes the feed at most hourly)
  - Polite rate limiting (~1 req/sec across the process)
  - No auth, no env vars required to work
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)

AMAZON_RSS_URL = "https://www.amazon.com/gp/movers-and-shakers/{category}/index.rss"

# Multi-feed support (option A extension). Amazon publishes several public
# RSS feeds under the same URL shape — just different path segments. They
# share identical RSS structure, so the same parser handles all of them.
#
#   movers       — biggest 24h sales-rank gains (velocity leaders)
#   new_releases — products launched in the last 30 days
#   bestsellers  — all-time top sellers in the category (paid Apify path
#                  already exists for this; the RSS version is the free
#                  alternative, useful for redundancy/fallback)
AMAZON_RSS_FEEDS: dict[str, str] = {
    "movers":       "https://www.amazon.com/gp/movers-and-shakers/{category}/index.rss",
    "new_releases": "https://www.amazon.com/gp/new-releases/{category}/index.rss",
    "bestsellers":  "https://www.amazon.com/gp/bestsellers/{category}/index.rss",
}

# Map Ospra niches to Amazon category slugs. The slugs are what appears
# in the URL path of the public Movers page (visit
# amazon.com/gp/movers-and-shakers, copy the URL of a category).
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

# Per-process response cache keyed by category slug. Amazon refreshes the
# RSS hourly; we cache for 10 minutes to keep responses snappy without
# serving stale data.
_RSS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_RSS_CACHE_TTL = int(os.getenv("AMAZON_MOVERS_RSS_TTL_SECONDS", "600"))

# Polite throttling — one request/second across the process. Amazon
# doesn't publish rate limits for the RSS feed but the standard etiquette
# is "don't hammer".
_REQUEST_LOCK: Optional[asyncio.Lock] = None
_LAST_REQUEST_AT = 0.0
_MIN_INTERVAL = float(os.getenv("AMAZON_MOVERS_RSS_MIN_INTERVAL", "1.0"))


def _get_lock() -> asyncio.Lock:
    """Lazy lock so module import doesn't require an event loop."""
    global _REQUEST_LOCK
    if _REQUEST_LOCK is None:
        _REQUEST_LOCK = asyncio.Lock()
    return _REQUEST_LOCK


async def _pace() -> None:
    """Sleep just long enough to honour `_MIN_INTERVAL`. Caller holds lock."""
    global _LAST_REQUEST_AT
    now = time.time()
    elapsed = now - _LAST_REQUEST_AT
    if elapsed < _MIN_INTERVAL:
        await asyncio.sleep(_MIN_INTERVAL - elapsed)
    _LAST_REQUEST_AT = time.time()


# ----------------------------------------------------------------------
# Item parsing
# ----------------------------------------------------------------------
_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")
_PRICE_RE = re.compile(r"\$\s*([0-9,]+\.?[0-9]*)")
_RANK_RE = re.compile(r"#?(\d+)\s*(?:to|→|->)\s*#?(\d+)", re.IGNORECASE)
_IMG_RE = re.compile(
    r'<img[^>]+src=["\'](https?://[^"\']+)["\']', re.IGNORECASE
)


def _extract_asin(url: str) -> Optional[str]:
    """Pull the 10-char ASIN out of an Amazon product URL.
    Returns None if the URL doesn't look like a product page."""
    if not url:
        return None
    m = _ASIN_RE.search(url)
    return m.group(1) if m else None


def _extract_price(text: str) -> Optional[float]:
    """First dollar amount in the RSS description, or None."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _extract_rank_change(text: str) -> Optional[tuple[int, int]]:
    """Amazon's RSS description includes a rank-gain summary like
    'Sales Rank: 1,287 (was 9,041)' or '#42 → #6'. Try to extract a
    (previous, current) pair from whichever format appears."""
    if not text:
        return None
    m = _RANK_RE.search(text)
    if not m:
        return None
    try:
        prev_rank = int(m.group(1))
        curr_rank = int(m.group(2))
        return (prev_rank, curr_rank)
    except (ValueError, TypeError):
        return None


def _extract_image(html_or_text: str) -> Optional[str]:
    """The RSS description embeds an <img src="..."> tag with the
    product thumbnail. Pull the first one."""
    if not html_or_text:
        return None
    m = _IMG_RE.search(html_or_text)
    return m.group(1) if m else None


def _normalize_item(item_el: ET.Element, category: str) -> Optional[dict[str, Any]]:
    """Map one <item> element from the RSS feed into the discovery dict
    shape. Returns None if the item is malformed."""

    def _text(tag: str) -> str:
        el = item_el.find(tag)
        return (el.text or "").strip() if el is not None and el.text else ""

    title = _text("title")
    link = _text("link")
    description = _text("description")
    guid = _text("guid")
    pub_date = _text("pubDate")

    if not title or not link:
        return None

    asin = _extract_asin(link) or _extract_asin(guid)
    image_url = _extract_image(description)
    price = _extract_price(description)
    rank_change = _extract_rank_change(description)

    # Sales rank delta = how many positions the product climbed. Amazon's
    # Movers feed is implicitly sorted by this, so we mostly use it as a
    # tag/feature rather than a score (the list order is the score).
    rank_delta: Optional[int] = None
    if rank_change is not None:
        prev_rank, curr_rank = rank_change
        rank_delta = max(0, prev_rank - curr_rank)

    return {
        "title": title,
        "asin": asin,
        "product_url": link,
        "image_url": image_url,
        "price": price,
        "rank_previous": rank_change[0] if rank_change else None,
        "rank_current": rank_change[1] if rank_change else None,
        "rank_delta": rank_delta,
        "category": category,
        "pub_date": pub_date or None,
        "source": "amazon_movers_rss",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ----------------------------------------------------------------------
# Public connector
# ----------------------------------------------------------------------
class AmazonMoversRSS:
    """Async client for Amazon's public Movers & Shakers RSS feeds.

    Stateless except for the per-process cache + request pace lock. No
    auth required — anybody can fetch the feed.
    """

    def __init__(self, *, timeout_seconds: int = 12):
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        # Identifies us in Amazon's logs — using a real browser UA
        # because some Amazon endpoints return 503 for empty/blank UAs.
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; OspraOS-Discovery/1.0; "
                "+https://ospra.os)"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def is_available(self) -> bool:
        """RSS is public — only "unavailable" if the network itself is."""
        return True

    def resolve_category(self, niche: str) -> Optional[str]:
        """Map an Ospra niche key to an Amazon category slug. Returns
        None for niches that don't have a clean mapping; callers should
        fall through to `electronics` or skip this source."""
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
        """Pull a public Amazon RSS feed for `niche_or_category`.

        `feed_type` controls which Amazon feed to hit:
          - "movers" (default) — biggest 24h sales-rank gains
          - "new_releases" — products launched in the last 30 days
          - "bestsellers" — all-time top sellers (RSS version of the
            paid Apify path — useful as a free fallback)

        Accepts either an Ospra niche key (`smart_home`, `pet`) or a
        raw Amazon slug (`electronics`, `pet-supplies`). Returns:

          {
            "available": bool,
            "category": str,             # Amazon slug used
            "niche": str,                # original input
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

        # Resolve niche → Amazon slug if needed. Raw slugs pass through.
        category = self.resolve_category(niche_or_category) or niche_or_category
        if not category:
            return {
                "available": False,
                "error": f"no category mapping for niche '{niche_or_category}'",
            }

        # Validate feed_type and pick the right URL template
        feed_template = AMAZON_RSS_FEEDS.get(feed_type)
        if feed_template is None:
            return {
                "available": False,
                "category": category,
                "niche": niche_or_category,
                "error": (
                    f"unknown feed_type '{feed_type}'. "
                    f"Valid: {sorted(AMAZON_RSS_FEEDS.keys())}"
                ),
            }

        # Cache key includes feed_type so different feeds don't shadow each other
        cache_key = f"{feed_type}:{category}"

        # Cache check
        if use_cache:
            cached = _RSS_CACHE.get(cache_key)
            if cached and (time.time() - cached[0]) < _RSS_CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["niche"] = niche_or_category
                if max_items < len(payload.get("items") or []):
                    payload["items"] = payload["items"][:max_items]
                    payload["item_count"] = len(payload["items"])
                return payload

        url = feed_template.format(category=quote(category, safe=""))

        # Throttle to be polite — one request/second/process
        async with _get_lock():
            await _pace()
            try:
                async with aiohttp.ClientSession(timeout=self._timeout, headers=self._headers) as session:
                    async with session.get(url) as response:
                        status = response.status
                        body = await response.text()
            except asyncio.TimeoutError:
                return {
                    "available": False,
                    "category": category,
                    "niche": niche_or_category,
                    "error": "timeout",
                }
            except aiohttp.ClientError as exc:
                return {
                    "available": False,
                    "category": category,
                    "niche": niche_or_category,
                    "error": f"http_error: {exc}",
                }

        if status != 200:
            return {
                "available": False,
                "category": category,
                "niche": niche_or_category,
                "error": f"http_{status}",
                "status": status,
            }

        # Parse XML — RSS shape is <rss><channel><item>...</item>...</channel></rss>
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            return {
                "available": False,
                "category": category,
                "niche": niche_or_category,
                "error": f"parse_error: {exc}",
            }

        items_el = root.findall(".//item")
        items: list[dict[str, Any]] = []
        for el in items_el:
            normalised = _normalize_item(el, category)
            if normalised:
                items.append(normalised)
            if len(items) >= max_items:
                break

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

        # Only cache successful, non-empty responses — caching an empty
        # list would suppress retries when the feed briefly hiccups.
        if items:
            _RSS_CACHE[cache_key] = (time.time(), payload)

        return payload

    def extract_keywords(self, payload: dict[str, Any], *, top_n: int = 8) -> list[str]:
        """Pull the most useful trending phrases out of a fetch payload.

        Amazon Movers titles are long ("Apple AirPods Pro (2nd
        Generation) Wireless Earbuds, Up to 2x More Active Noise
        Cancelling..."). We extract the first 3-4 meaningful tokens
        so they're usable as supplier-search queries downstream.
        """
        if not payload or not payload.get("items"):
            return []
        out: list[str] = []
        for item in payload["items"][:top_n]:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            # Drop common Amazon noise tokens
            tokens = []
            for raw_t in title.split():
                t = raw_t.strip(",.()[]:;-")
                if not t:
                    continue
                if len(t) <= 2:
                    continue
                # Skip parenthetical-style noise like "(2nd"
                if t.startswith("(") or t.endswith(")"):
                    continue
                if t.lower() in {
                    "the", "and", "for", "with", "from", "your",
                    "all", "new", "best", "top", "only", "more",
                }:
                    continue
                tokens.append(t)
                if len(tokens) >= 3:
                    break
            if tokens:
                out.append(" ".join(tokens))
        return out


# ----------------------------------------------------------------------
# Singleton — one client per process. RSS has no per-tenant state.
# ----------------------------------------------------------------------
_singleton: Optional[AmazonMoversRSS] = None


def get_amazon_movers_rss() -> AmazonMoversRSS:
    """Return the process-wide RSS client, creating on first use."""
    global _singleton
    if _singleton is None:
        _singleton = AmazonMoversRSS()
    return _singleton
