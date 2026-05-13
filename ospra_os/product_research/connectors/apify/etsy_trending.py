"""
Etsy trending products via Apify — Option B / supplementary signal.

================================================================================
WHY ETSY MATTERS FOR OSPRA
================================================================================
Etsy is the dominant marketplace for handmade, vintage, and lifestyle
products — categories where Amazon's bestseller signal is weak. Pinterest
gives us "what people want to imagine"; Etsy gives us "what they're
willing to pay for". For niches like home decor, jewelry, beauty
accessories, and craft goods, Etsy trending data fills a gap.

This is a supplementary signal — Etsy isn't a dropshipping supplier
(no AliExpress-style supply chain), so we use trending product titles
as KEYWORDS that feed back into AE/CJ search. The goal isn't to source
from Etsy; it's to learn which product categories are growing.

================================================================================
WHY APIFY AND NOT ETSY'S OFFICIAL API
================================================================================
Etsy's official Open API (v3) requires OAuth approval and is gated to
applications that demonstrate Etsy-seller use cases. For a discovery
engine that wants public marketplace data ("what's trending?") and
doesn't sell on Etsy, the approval process is slow and uncertain.

Apify offers several Etsy scrapers (`epctex/etsy-trending-scraper`,
`apify/etsy-scraper`, etc.) that walk the public Etsy "Trending Now"
and category pages — the same content a logged-out browser sees. Cost
is metered per result (~$0.50-$1.00 per 1k products). This mirrors the
pattern we already use for Meta Ad Library (#10), Pinterest Trends,
and TikTok Shop.

================================================================================
SCOPE
================================================================================
Minimal connector:
  - `fetch_trending(category, max_items)` — pull Etsy's trending listings
    for a category
  - Normalised output shape compatible with the discovery engine's
    trend-keyword merge loop
  - Graceful no-op when APIFY_API_TOKEN is missing
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from .base_apify import ApifyClient

logger = logging.getLogger(__name__)

# Default Apify actor. Configurable via env var so we can swap to a
# better-maintained actor without code changes if this one falls behind.
DEFAULT_ACTOR = "epctex/etsy-trending-scraper"

# Etsy doesn't use clean category slugs the way Amazon does — it uses
# "category pages" with longer URLs. The Apify trending actors typically
# accept a high-level category name like "home_living" or "jewelry". We
# expose a tiny mapping so Ospra niches translate cleanly.
NICHE_TO_ETSY_CATEGORY: dict[str, str] = {
    "smart_home": "home_living",
    "home_decor": "home_living",
    "kitchen":    "home_living",
    "beauty":     "bath_beauty",
    "skincare":   "bath_beauty",
    "jewelry":    "jewelry",
    "watches":    "jewelry",
    "bags":       "bags_purses",
    "fashion":    "clothing",
    "toys":       "toys_games",
    "baby":       "toys_games",
    "pet":        "pet_supplies",
    "office":     "paper_party_supplies",
    "outdoor":    "weddings",
    # Niches Etsy doesn't really cover (tech, fitness, gaming) get None
    # — caller will skip this source for those niches.
}


def _looks_like_product_title(text: str) -> bool:
    """Lightweight filter — drop obvious garbage strings before we hand
    them off to the keyword extractor."""
    if not text or len(text) < 5:
        return False
    # Etsy titles often start with seller-promo prefixes like "SALE 50% off"
    # which we want to keep, but pure-numeric or single-word titles aren't useful
    if text.isdigit():
        return False
    return True


class EtsyTrendingApify:
    """Pull trending Etsy products by category via Apify.

    Etsy is a SUPPLEMENTARY signal for Ospra — useful for lifestyle /
    handmade niches that Amazon and AE don't surface well. Returns
    product titles which the discovery engine uses as keyword seeds for
    its AE/CJ supplier search.
    """

    def __init__(
        self,
        api_token: str | None = None,
        actor_id: str | None = None,
    ):
        # Match the pattern used by meta_ads_library — fail soft if no
        # token rather than raising at construction.
        self.client = ApifyClient(api_token=api_token) if (
            api_token or os.getenv("APIFY_API_TOKEN")
        ) else None
        self.actor_id = actor_id or os.getenv(
            "APIFY_ETSY_TRENDING_ACTOR", DEFAULT_ACTOR
        )

    def is_available(self) -> bool:
        return self.client is not None and self.client.is_available()

    def resolve_category(self, niche: str) -> Optional[str]:
        """Map an Ospra niche key to an Etsy category slug. Returns
        None for niches Etsy doesn't cover well — caller should skip
        Etsy for those niches rather than feeding it garbage."""
        if not niche:
            return None
        return NICHE_TO_ETSY_CATEGORY.get(niche.lower())

    async def fetch_trending(
        self,
        niche: str,
        *,
        max_items: int = 30,
        timeout_secs: int = 90,
    ) -> dict[str, Any]:
        """Pull trending Etsy products for the niche's mapped category.

        Returns:
          {
            "available": bool,
            "niche": str,
            "category": str | None,    # Etsy slug used
            "item_count": int,
            "items": [
              {"title", "url", "image", "price", "currency",
               "favorites", "shop", "shop_url"},
              ...
            ],
            "error": str | None,
          }

        Never raises — failures return `{"available": False, "error": ...}`.
        Niches without an Etsy mapping return `{"available": False,
        "error": "no_etsy_category_for_niche"}` so the caller can skip
        cleanly.
        """
        if not niche or not niche.strip():
            return {"available": False, "error": "empty niche"}
        if not self.is_available():
            return {"available": False, "error": "apify token not configured"}

        category = self.resolve_category(niche)
        if not category:
            return {
                "available": False,
                "niche": niche,
                "error": "no_etsy_category_for_niche",
            }

        run_input = {
            "category": category,
            "maxItems": int(max_items),
            "country": "US",
            "sort": "trending",
        }

        try:
            results = await self.client.run_actor(
                actor_id=self.actor_id,
                run_input=run_input,
                timeout_secs=timeout_secs,
                memory_mbytes=512,
            )
        except Exception as exc:
            logger.warning("etsy_trending: actor run failed: %s", exc)
            return {
                "available": False,
                "niche": niche,
                "category": category,
                "error": str(exc),
            }

        if not results:
            return {
                "available": False,
                "niche": niche,
                "category": category,
                "error": "no_items_returned",
            }

        items: list[dict[str, Any]] = []
        for raw in results[: max_items]:
            normalised = self._normalise_item(raw)
            if normalised:
                items.append(normalised)

        return {
            "available": True,
            "niche": niche,
            "category": category,
            "item_count": len(items),
            "items": items,
            "error": None,
        }

    def _normalise_item(self, raw: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Apify's Etsy actors return varying field names. Flatten to
        one shape."""
        if not isinstance(raw, dict):
            return None

        title = (
            raw.get("title")
            or raw.get("product_title")
            or raw.get("name")
            or ""
        )
        title = title.strip()
        if not _looks_like_product_title(title):
            return None

        # Price — Etsy returns it sometimes as a dict, sometimes a string
        price_obj = raw.get("price") or raw.get("listing_price") or {}
        price = None
        currency = "USD"
        if isinstance(price_obj, dict):
            try:
                price = float(price_obj.get("amount", 0)) / 100 if price_obj.get("amount") else None
                currency = price_obj.get("currency_code") or "USD"
            except (TypeError, ValueError):
                price = None
        elif isinstance(price_obj, (int, float)):
            price = float(price_obj)
        elif isinstance(price_obj, str):
            # "$24.99" → 24.99
            m = re.search(r"(\d+\.?\d*)", price_obj)
            if m:
                try:
                    price = float(m.group(1))
                except ValueError:
                    pass

        # Image
        image = raw.get("image") or raw.get("main_image") or raw.get("image_url")
        if isinstance(image, dict):
            image = image.get("url") or image.get("src")
        elif isinstance(image, list) and image:
            first = image[0]
            image = first.get("url") if isinstance(first, dict) else first

        return {
            "title": title[:200],
            "url": raw.get("url") or raw.get("product_url") or raw.get("link"),
            "image": image,
            "price": price,
            "currency": currency,
            "favorites": int(raw.get("favorites") or raw.get("favorers") or 0),
            "shop": raw.get("shop_name") or raw.get("shop"),
            "shop_url": raw.get("shop_url"),
        }

    def extract_keywords(
        self,
        payload: dict[str, Any],
        *,
        top_n: int = 8,
    ) -> list[str]:
        """Pull short trending phrases from item titles. Etsy titles are
        often noun-rich ("Personalized Leather Keychain Custom Date"),
        so we take the first 3 capitalized or alphanumeric words after
        stripping seller-promo prefixes."""
        if not payload or not payload.get("items"):
            return []
        out: list[str] = []
        # Common Etsy seller prefixes to strip
        promo_prefixes = re.compile(
            r"^(SALE|NEW|FREE SHIPPING|BESTSELLER|LIMITED|HOT)\s+\d*%?\s*",
            re.IGNORECASE,
        )
        for item in payload["items"][:top_n]:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            title = promo_prefixes.sub("", title).strip()
            tokens = []
            for raw_t in title.split():
                t = raw_t.strip(",.()[]:;-\"'!")
                if not t:
                    continue
                if len(t) <= 2:
                    continue
                # Skip Etsy noise tokens
                if t.lower() in {
                    "the", "and", "for", "with", "from", "your", "you",
                    "custom", "personalized", "made", "gift", "perfect",
                    "great", "best", "new", "set", "pcs",
                }:
                    continue
                tokens.append(t)
                if len(tokens) >= 3:
                    break
            if tokens:
                out.append(" ".join(tokens))
        return out


# Singleton pattern matches other connectors
_singleton: Optional[EtsyTrendingApify] = None


def get_etsy_trending() -> EtsyTrendingApify:
    """Return the process-wide Etsy trending client, creating on first use."""
    global _singleton
    if _singleton is None:
        _singleton = EtsyTrendingApify()
    return _singleton
