"""
Per-product Amazon review TEXT via Apify — Phase K.

The niche-level connector at
``connectors/social/amazon_reviews.py`` runs ONE Amazon search per
niche and gives us aggregate rating + review count. That's good enough
for the numeric composite (rating × log(review_count) → buzz score) but
it's not what the qualitative agent needs to *read*.

This connector fills that gap: given the ASIN or Amazon product URL of
the closest-matched listing, pull verbatim per-review prose so the
qualitative agent has actual buyer text to read instead of a single
weighted-average rating.

Why a separate actor:
  - The actor used by ``amazon_reviews.py`` (``apify/amazon-crawler``)
    returns listing-level data only — title, price, rating, review count,
    no per-review text.
  - Amazon's per-product reviews endpoint is paginated, captcha-gated,
    and the field shapes change frequently. Apify's review-specific
    actors handle all of that for us.

Default actor: ``axesso_data/amazon-reviews-scraper``. Override with
``APIFY_AMAZON_REVIEWS_ACTOR`` if a different actor is configured.

Cost model: ~$1-2 per 1k reviews depending on actor and Apify plan.
At top-10 products × 15 reviews each × 10 discoveries/day = 1.5k
reviews/day → ~$45-90/month. Cap at top-N in the caller.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from .base_apify import ApifyClient

logger = logging.getLogger(__name__)


DEFAULT_ACTOR = "axesso_data/amazon-reviews-scraper"


def _extract_asin(url: str) -> str | None:
    """Pull an ASIN out of an Amazon URL. ASINs are 10-char
    alphanumeric IDs that appear after ``/dp/`` or ``/gp/product/``."""
    if not url:
        return None
    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url, flags=re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


class AmazonReviewsTextApify:
    """
    Per-product Amazon review-text scraper.

    Use sparingly — top-N ranked products only. The actor charges per
    review fetched, so fanning out to every discovered product would
    burn credits. The discovery flow caps it at top-10 by OI.
    """

    def __init__(self, api_token: str | None = None, actor_id: str | None = None):
        self.client = ApifyClient(api_token=api_token)
        self.actor_id = actor_id or os.getenv(
            "APIFY_AMAZON_REVIEWS_ACTOR", DEFAULT_ACTOR
        )

    def is_available(self) -> bool:
        return self.client.is_available()

    async def fetch_reviews(
        self,
        *,
        asin: str | None = None,
        product_url: str | None = None,
        max_reviews: int = 15,
        timeout_secs: int = 90,
    ) -> dict[str, Any]:
        """
        Fetch up to ``max_reviews`` reviews for one Amazon product.

        Pass either ``asin`` or ``product_url`` (we'll extract the ASIN
        from the URL if needed). Returns dict shaped:

          {
            "available": bool,
            "asin": "B0XXXX",
            "review_count_returned": int,
            "average_rating": float | None,
            "verified_share": float,   # 0-1, fraction of reviews from verified buyers
            "reviews": [
              {"text": "...", "rating": 5, "title": "...", "verified": True, "date": "..."},
              ...
            ],
            "error": str | None,
          }

        Returns ``{"available": False, ...}`` on failure or no reviews —
        never raises.
        """
        if not self.is_available():
            return {"available": False, "error": "apify token not configured"}

        # Normalize: prefer explicit ASIN, otherwise extract from URL.
        asin = (asin or "").strip().upper() if asin else None
        if not asin and product_url:
            asin = _extract_asin(product_url)

        if not asin and not product_url:
            return {"available": False, "error": "no asin or product_url provided"}

        # Most actors accept either a list of ASINs or a list of URLs.
        # Use ASIN where possible (more reliable), URL as fallback.
        run_input: dict[str, Any] = {
            "maxReviewsPerProduct": int(max_reviews),
            "includeReviewerProfile": False,
        }
        if asin:
            run_input["productUrls"] = [
                f"https://www.amazon.com/dp/{asin}"
            ]
            run_input["asins"] = [asin]
        else:
            run_input["productUrls"] = [product_url]

        try:
            results = await self.client.run_actor(
                actor_id=self.actor_id,
                run_input=run_input,
                timeout_secs=timeout_secs,
                memory_mbytes=512,
            )
        except Exception as exc:
            logger.warning("amazon_reviews_text: actor run failed: %s", exc)
            return {"available": False, "error": str(exc), "asin": asin}

        if not results:
            return {
                "available": False,
                "error": "no reviews returned",
                "asin": asin,
            }

        # Field-name normalization across actor versions.
        reviews: list[dict[str, Any]] = []
        for r in results[: max_reviews]:
            text = (
                r.get("reviewDescription")
                or r.get("text")
                or r.get("review")
                or r.get("body")
                or r.get("content")
                or ""
            )
            if not text:
                continue
            reviews.append({
                "text": text.strip()[:400],  # cap for prompt-budget
                "title": (r.get("reviewTitle") or r.get("title") or "").strip()[:120],
                "rating": (
                    r.get("ratingScore")
                    or r.get("rating")
                    or r.get("stars")
                    or None
                ),
                "verified": bool(
                    r.get("verifiedPurchase")
                    or r.get("isVerified")
                    or r.get("verified")
                ),
                "date": r.get("reviewedIn") or r.get("date") or r.get("createdAt") or None,
                "helpful_count": int(r.get("helpfulCount", r.get("helpful", 0)) or 0),
            })

        ratings = [
            float(r["rating"]) for r in reviews
            if isinstance(r.get("rating"), (int, float)) and r["rating"]
        ]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        verified_count = sum(1 for r in reviews if r.get("verified"))
        verified_share = (verified_count / len(reviews)) if reviews else 0.0

        return {
            "available": True,
            "asin": asin,
            "review_count_returned": len(reviews),
            "average_rating": avg_rating,
            "verified_share": round(verified_share, 3),
            "reviews": reviews,
            "error": None,
        }
