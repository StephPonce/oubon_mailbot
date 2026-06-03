"""
AliExpress Reviews via Apify — Phase H.

The AliExpress affiliate API exposes a single ``evaluate_rate`` number
(rolled-up positive-feedback %) but no review TEXT. To do honest social
sentiment we need verbatim reviews. This connector pulls per-product
review prose via Apify so the qualitative agent has actual human
feedback to read instead of a single percentage.

Why Apify and not direct scraping (decision in chat — keep here for
posterity):
  - AE's review endpoint is undocumented and changes frequently
  - Aggressive captcha + IP rate-limiting (~30 req/min)
  - Captcha-solving infra > Apify cost
  - Apify handles pagination, translation, and image attachments

Cost model: ~$0.30 per 1k reviews. At realistic Ospra usage
(top 10 products × 10 reviews × ~10 discoveries/day = 1k reviews/day)
this is ~$9/month — rounding error vs the value.

Output shape matches the other social-evidence dicts so the qualitative
agent can consume it without special-casing.
"""

from __future__ import annotations

import logging
from typing import Any

from .base_apify import ApifyClient

logger = logging.getLogger(__name__)


# Apify actor for AliExpress reviews. ``epctex/aliexpress-reviews-scraper``
# was removed from the Apify store (returns 404). ``epctex/aliexpress-scraper``
# is the alive successor from the same author and returns product data with
# embedded reviews. Override via ``APIFY_ALIEXPRESS_REVIEWS_ACTOR`` if a
# different actor is preferred. The normalizer below tolerates a range of
# field names, so a schema drift from this swap degrades to an empty review
# list rather than an error.
DEFAULT_ACTOR = "epctex/aliexpress-scraper"


class AliExpressReviewsApify:
    """
    Per-product AliExpress review scraper.

    Use it sparingly — calling this for every discovered product would
    burn credits. The discovery flow caps it at the top N products
    by OI score (configurable in the caller).
    """

    def __init__(self, api_token: str | None = None, actor_id: str | None = None):
        import os
        self.client = ApifyClient(api_token=api_token)
        self.actor_id = actor_id or os.getenv(
            "APIFY_ALIEXPRESS_REVIEWS_ACTOR", DEFAULT_ACTOR
        )

    def is_available(self) -> bool:
        return self.client.is_available()

    async def fetch_reviews(
        self,
        product_url: str,
        *,
        max_reviews: int = 25,
        timeout_secs: int = 90,
    ) -> dict[str, Any]:
        """
        Fetch up to ``max_reviews`` reviews for one AliExpress product.

        Returns dict shaped:
          {
            "available": bool,
            "review_count_returned": int,
            "average_rating": float | None,
            "reviews": [
              {"text": "...", "rating": 5, "date": "...", "country": "RU", ...},
              ...
            ],
            "error": str | None,
          }

        Returns ``{"available": False}`` on failure or when no reviews
        are found — never raises.
        """
        if not product_url:
            return {"available": False, "error": "no product_url"}

        if not self.is_available():
            return {"available": False, "error": "apify token not configured"}

        run_input = {
            "startUrls": [{"url": product_url}],
            "maxReviewsPerProduct": int(max_reviews),
            # Most AE-review actors accept a language filter; English is
            # what the qualitative agent reads. Non-English reviews are
            # still valuable though, so we keep "all" by default.
            "language": "all",
        }

        try:
            results = await self.client.run_actor(
                actor_id=self.actor_id,
                run_input=run_input,
                timeout_secs=timeout_secs,
                memory_mbytes=512,
            )
        except Exception as exc:
            logger.warning("aliexpress_reviews: actor run failed: %s", exc)
            return {"available": False, "error": str(exc)}

        if not results:
            return {"available": False, "error": "no reviews returned"}

        # Different actors return different field names. Normalize.
        reviews: list[dict[str, Any]] = []
        for r in results[: max_reviews]:
            text = (
                r.get("review")
                or r.get("text")
                or r.get("comment")
                or r.get("body")
                or ""
            )
            if not text:
                continue
            reviews.append({
                "text": text.strip(),
                "rating": (
                    r.get("rating")
                    or r.get("stars")
                    or r.get("score")
                    or None
                ),
                "date": r.get("date") or r.get("createdAt") or None,
                "country": r.get("country") or r.get("buyerCountry") or None,
                "verified": bool(r.get("verifiedPurchase") or r.get("verified")),
            })

        # Average rating from real review payloads — ignore None/0.
        ratings = [r["rating"] for r in reviews if isinstance(r.get("rating"), (int, float)) and r["rating"]]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        return {
            "available": True,
            "review_count_returned": len(reviews),
            "average_rating": avg_rating,
            "reviews": reviews,
            "error": None,
        }
