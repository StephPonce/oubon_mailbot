"""
Meta Ad Library scraper via Apify — Task #10 / winner-proof source #1.

================================================================================
WHY APIFY AND NOT META'S OFFICIAL GRAPH API
================================================================================
The official Meta Ad Library endpoint (`/ads_archive`) gates commerce ads
behind region-specific rules. In the EU all ads are returned under DSA;
in the US it filters to political/issue ads only. For dropshipper-style
discovery (commerce ads in the US) the official API returns essentially
nothing useful.

Apify exposes a publicly-funded scraper that walks the same Ad Library
web UI a logged-out user sees, including commerce ads. Cost is metered
per ad scraped (~$0.30-$1.00 / 1k ads on the default actor). This is the
established pattern in this repo for "Meta won't give us the API we need"
problems — see instagram_hashtag.py for an analogous case (IG hashtag
search was deprecated, we use the same Apify fall-back).

================================================================================
WINNER-PROOF SIGNAL
================================================================================
The reason this source is the most valuable Ospra has is the heuristic:

    proven_winner = (days_active >= 14) AND
                    (variant_count >= 3) AND
                    (landing_url maps to a Shopify domain)

When a dropshipper is running 3+ creatives for 2+ weeks against the
same product page, the product is paying for its ad spend. That is a
much harder signal to fake than view counts or hashtag chatter — the
advertiser is voting with their money.

================================================================================
SCOPE
================================================================================
This module ONLY scrapes the Ad Library. It does not score products,
match them to suppliers, or extract Shopify metadata — that's the
discovery engine's job. We return a normalised dict per ad that
downstream code can merge with AE/CJ supplier data.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

from .base_apify import ApifyClient

logger = logging.getLogger(__name__)

# Apify marketplace exposes several Ad Library scrapers. The "curious_coder"
# actor returns the richest payload (creative bodies, snapshots, run dates,
# landing URLs). `apify/facebook-ads-scraper` is the official fallback —
# similar shape, fewer fields. Override via env var if a better actor
# emerges or pricing shifts.
DEFAULT_ACTOR = "curious_coder/facebook-ads-library-scraper"


def _parse_iso_date(value: Any) -> Optional[datetime]:
    """Best-effort parse of Apify's various date string shapes into a
    timezone-aware datetime. Returns None on miss."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).strip()
        # Trailing Z → +00:00 for fromisoformat compat
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _looks_like_shopify(url: str) -> bool:
    """Heuristic: does this destination URL look like a Shopify store?
    Used by the winner-heuristic — Shopify is the dominant dropshipper
    platform. Both `*.myshopify.com` and `*/products/<handle>` URL
    structures count."""
    if not url:
        return False
    u = url.lower()
    if "myshopify.com" in u:
        return True
    if "/products/" in u and any(
        u.startswith(scheme) for scheme in ("http://", "https://")
    ):
        # Shopify product URLs are typically /products/<handle>. Many
        # custom domains use Shopify under the hood. This is a
        # heuristic — false positives are tolerable since downstream
        # code re-validates supplier match.
        return True
    return False


class MetaAdsLibraryApify:
    """Pull active Meta (Facebook + Instagram) ads matching a keyword
    via Apify's Ad Library scraper.

    Designed as a "winner-proof" discovery source: the products with the
    most active ads, run for the longest, in the most variants, are the
    ones already paying for themselves in the market today.
    """

    def __init__(
        self,
        api_token: str | None = None,
        actor_id: str | None = None,
    ):
        self.client = ApifyClient(api_token=api_token) if api_token or os.getenv("APIFY_API_TOKEN") else None
        self.actor_id = actor_id or os.getenv(
            "APIFY_META_ADS_LIBRARY_ACTOR", DEFAULT_ACTOR
        )

    def is_available(self) -> bool:
        return self.client is not None and self.client.is_available()

    async def search_active_ads(
        self,
        keyword: str,
        *,
        country: str = "US",
        max_ads: int = 50,
        active_only: bool = True,
        timeout_secs: int = 120,
    ) -> dict[str, Any]:
        """Search for ads matching `keyword` and return a normalised
        payload the discovery engine can merge.

        Args:
            keyword: Free-text search term, e.g. "smart plug",
                "pet grooming brush". Apify hits the Ad Library's own
                full-text search.
            country: ISO 3166-1 alpha-2 (default US).
            max_ads: Cap on number of ads returned. Apify is per-result
                billed; this is the cost control.
            active_only: When True, request only currently-running ads.
                `False` lets historical ads through (useful for trend
                research, but most callers want active-only).
            timeout_secs: Max wall-clock for the Apify run.

        Returns:
            {
              "available": bool,
              "keyword": str,
              "country": str,
              "ad_count": int,
              "ads": [
                {
                  "ad_id": str,
                  "page_id": str,
                  "page_name": str,
                  "page_url": str | None,
                  "creative_body": str,
                  "creative_title": str | None,
                  "landing_url": str | None,
                  "snapshot_url": str | None,
                  "started_at": ISO str | None,
                  "stopped_at": ISO str | None,
                  "days_active": int | None,
                  "is_active": bool,
                  "publisher_platforms": list[str],
                  "looks_shopify": bool,
                },
                ...
              ],
              "advertisers": [
                {"page_id": str, "page_name": str, "ad_count": int,
                 "variant_count": int, "max_days_active": int},
                ...
              ],
              "winners": [
                # Subset of `advertisers` that pass the winner heuristic
                # (days_active >= 14 AND variant_count >= 3 AND has
                # Shopify-shaped landing URL on at least one ad).
              ],
              "error": str | None,
            }

        Never raises — returns `{"available": False, "error": ...}` on
        failure. Caller policy: if `available=False`, skip the source.
        """
        if not keyword or not keyword.strip():
            return {"available": False, "error": "empty keyword"}
        if not self.is_available():
            return {"available": False, "error": "apify token not configured"}

        run_input = {
            "searchTerms": [keyword],
            "country": country,
            "active": "active" if active_only else "all",
            "maxResults": int(max_ads),
            "scrapePageAds": False,  # only Ad Library search, not per-page deep dive
        }

        try:
            results = await self.client.run_actor(
                actor_id=self.actor_id,
                run_input=run_input,
                timeout_secs=timeout_secs,
                memory_mbytes=1024,
            )
        except Exception as exc:
            logger.warning("meta_ads_library: actor run failed: %s", exc)
            return {"available": False, "error": str(exc), "keyword": keyword}

        if not results:
            return {
                "available": False,
                "error": "no ads returned",
                "keyword": keyword,
                "country": country,
            }

        ads = [
            ad for ad in (self._normalise_ad(r) for r in results) if ad is not None
        ]
        if not ads:
            return {
                "available": False,
                "error": "no ads parseable",
                "keyword": keyword,
                "country": country,
            }

        advertisers = self._aggregate_advertisers(ads)
        winners = self._select_winners(advertisers, ads)

        return {
            "available": True,
            "keyword": keyword,
            "country": country,
            "ad_count": len(ads),
            "ads": ads,
            "advertisers": advertisers,
            "winners": winners,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------
    def _normalise_ad(self, raw: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Different Ad Library scrapers return different field names —
        flatten everything to one shape so downstream code doesn't have
        to know which actor was used. Returns None on parse failure."""
        if not isinstance(raw, dict):
            return None

        ad_id = (
            raw.get("ad_id")
            or raw.get("adArchiveID")
            or raw.get("adId")
            or raw.get("id")
        )
        page_id = (
            raw.get("page_id")
            or raw.get("pageId")
            or raw.get("page_id_str")
        )
        page_name = raw.get("page_name") or raw.get("pageName") or ""
        if not ad_id or not page_id:
            return None

        # Creative body — sometimes a string, sometimes an array of strings
        body = (
            raw.get("ad_creative_body")
            or raw.get("ad_creative_bodies")
            or raw.get("body")
            or raw.get("text")
            or ""
        )
        if isinstance(body, list):
            body = " ".join(str(b) for b in body if b)

        title = (
            raw.get("ad_creative_link_title")
            or raw.get("ad_creative_link_titles")
            or raw.get("title")
        )
        if isinstance(title, list):
            title = title[0] if title else None

        # Landing / destination URL — the dropshipper's product page
        landing_url = (
            raw.get("link_url")
            or raw.get("linkUrl")
            or raw.get("destination_url")
            or raw.get("destinationUrl")
            or raw.get("ad_creative_link_caption")
            or None
        )

        # Snapshot URL = the Meta Ad Library page for this ad. Useful
        # for the UI to link to the actual creative.
        snapshot_url = raw.get("ad_snapshot_url") or raw.get("snapshotUrl")

        started = _parse_iso_date(
            raw.get("ad_delivery_start_time")
            or raw.get("startDate")
            or raw.get("start_date")
            or raw.get("ad_creation_time")
        )
        stopped = _parse_iso_date(
            raw.get("ad_delivery_stop_time")
            or raw.get("endDate")
            or raw.get("end_date")
        )

        # `is_active`: ad currently running. Apify either returns this
        # explicitly or it's inferable from stop_date being None.
        is_active_raw = raw.get("is_active")
        if is_active_raw is None:
            is_active = stopped is None
        else:
            is_active = bool(is_active_raw)

        days_active: Optional[int] = None
        if started is not None:
            end = stopped if stopped else datetime.now(timezone.utc)
            delta = end - started
            days_active = max(0, delta.days)

        platforms = raw.get("publisher_platforms") or raw.get("publisherPlatforms") or []
        if isinstance(platforms, str):
            platforms = [platforms]

        return {
            "ad_id": str(ad_id),
            "page_id": str(page_id),
            "page_name": page_name,
            "page_url": raw.get("page_url") or raw.get("pageUrl") or (
                f"https://www.facebook.com/{page_id}" if page_id else None
            ),
            "creative_body": (str(body) if body else "")[:600],
            "creative_title": (str(title) if title else None),
            "landing_url": landing_url,
            "snapshot_url": snapshot_url,
            "started_at": started.isoformat() if started else None,
            "stopped_at": stopped.isoformat() if stopped else None,
            "days_active": days_active,
            "is_active": is_active,
            "publisher_platforms": list(platforms) if platforms else [],
            "looks_shopify": _looks_like_shopify(str(landing_url or "")),
        }

    def _aggregate_advertisers(
        self, ads: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Roll ads up by advertiser (page_id). Each advertiser entry
        carries the aggregate signals — ad count, variant count
        (distinct creative bodies), max days active, has-shopify flag."""
        buckets: dict[str, dict[str, Any]] = {}
        for ad in ads:
            page_id = ad["page_id"]
            bucket = buckets.setdefault(page_id, {
                "page_id": page_id,
                "page_name": ad.get("page_name", ""),
                "page_url": ad.get("page_url"),
                "ad_count": 0,
                "creative_bodies": set(),
                "max_days_active": 0,
                "has_shopify_landing": False,
                "landing_urls": [],
            })
            bucket["ad_count"] += 1
            if ad.get("creative_body"):
                bucket["creative_bodies"].add(ad["creative_body"][:120])
            if ad.get("days_active") is not None:
                bucket["max_days_active"] = max(
                    bucket["max_days_active"], int(ad["days_active"])
                )
            if ad.get("looks_shopify"):
                bucket["has_shopify_landing"] = True
            if ad.get("landing_url"):
                bucket["landing_urls"].append(ad["landing_url"])

        out: list[dict[str, Any]] = []
        for b in buckets.values():
            out.append({
                "page_id": b["page_id"],
                "page_name": b["page_name"],
                "page_url": b["page_url"],
                "ad_count": b["ad_count"],
                "variant_count": len(b["creative_bodies"]),
                "max_days_active": b["max_days_active"],
                "has_shopify_landing": b["has_shopify_landing"],
                "sample_landing_urls": b["landing_urls"][:3],
            })
        # Strongest advertisers first — by max_days_active × variant_count
        out.sort(
            key=lambda a: (a["max_days_active"] * (a["variant_count"] or 1)),
            reverse=True,
        )
        return out

    def _select_winners(
        self,
        advertisers: list[dict[str, Any]],
        ads: list[dict[str, Any]],
        *,
        min_days_active: int = 14,
        min_variants: int = 3,
    ) -> list[dict[str, Any]]:
        """Apply the proven-winner heuristic. Defaults follow the rule
        of thumb in the Phase 1 spec: 14-day age + 3 variants + Shopify
        landing. Each threshold is overridable so future tuning lives
        in one place."""
        winners: list[dict[str, Any]] = []
        for adv in advertisers:
            if adv["max_days_active"] < min_days_active:
                continue
            if adv["variant_count"] < min_variants:
                continue
            if not adv["has_shopify_landing"]:
                continue
            winners.append({
                **adv,
                "winner_reason": (
                    f"{adv['max_days_active']}d active × "
                    f"{adv['variant_count']} variants × Shopify landing"
                ),
            })
        return winners


# Module-level singleton mirrors the pattern used elsewhere in the
# connectors package. Lazy init so importing the module doesn't trigger
# token validation if the caller never uses it.
_singleton: Optional[MetaAdsLibraryApify] = None


def get_meta_ads_library() -> MetaAdsLibraryApify:
    """Process-wide instance. Reads `APIFY_API_TOKEN` and
    `APIFY_META_ADS_LIBRARY_ACTOR` from env at first call."""
    global _singleton
    if _singleton is None:
        _singleton = MetaAdsLibraryApify()
    return _singleton
