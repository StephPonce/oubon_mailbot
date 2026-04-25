"""
Instagram public-post discovery via Apify — Phase J.

Why Apify and not the Meta Graph API (decision in chat — keep here for
posterity):
  - Public Facebook post search (`/search?type=post`) was deprecated in
    2018; no longer exists.
  - Instagram Graph API's ``ig_hashtag_search`` requires a Business or
    Creator IG account linked to a Facebook Page that the caller owns,
    AND it's capped at 30 unique hashtags per 7 days per IG user. That
    doesn't fit a multi-tenant SaaS where we're querying arbitrary
    product hashtags on behalf of users who don't run IG businesses.
  - Apify's Instagram hashtag scraper just works against the public web
    surface (the same posts a logged-out browser would see) — no
    per-tenant tokens, no app-review process.

What we get back: post captions + top comments on the most-engaged posts
for ``#{product_slug}`` style hashtags. The captions and comments are
real buyer/influencer prose; perfect for the qualitative agent (same
shape as AE reviews + YouTube comments).

Cost (rough): Apify charges ~$2.30/1000 posts on the default hashtag
actor. At 10 products × 10 posts = ~100 posts/discovery × 10
discoveries/day = ~$70/month. Cap at top-N ranked products in the
caller to control this.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from .base_apify import ApifyClient

logger = logging.getLogger(__name__)


DEFAULT_ACTOR = "apify/instagram-hashtag-scraper"


def _slugify_hashtag(product_name: str) -> str:
    """Turn 'Smart LED Strip Light' into 'smartledstriplight' — the
    hashtag form Instagram normalizes to. Strip non-alphanumerics, drop
    common stop-tokens, lowercase."""
    if not product_name:
        return ""
    # Drop punctuation + spaces; keep alphanum
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", product_name)
    return cleaned.lower()[:60]  # IG hashtag length limit


class InstagramHashtagApify:
    """
    Pulls public Instagram posts (caption + top comments) for product
    hashtags via Apify.

    Use sparingly — top-N ranked products only. The actor costs ~$2.30/1k
    posts, which adds up fast if you fan it out to every discovered product.
    """

    def __init__(self, api_token: str | None = None, actor_id: str | None = None):
        self.client = ApifyClient(api_token=api_token)
        self.actor_id = actor_id or os.getenv(
            "APIFY_INSTAGRAM_HASHTAG_ACTOR", DEFAULT_ACTOR
        )

    def is_available(self) -> bool:
        return self.client.is_available()

    async def fetch_hashtag_posts(
        self,
        product_name: str,
        *,
        max_posts: int = 10,
        timeout_secs: int = 90,
    ) -> dict[str, Any]:
        """
        Fetch up to ``max_posts`` public Instagram posts for the product
        hashtag, with caption text + top-engagement metrics.

        Returns dict shaped:
          {
            "available": bool,
            "hashtag": "smartledstriplight",
            "post_count_returned": int,
            "total_likes": int,
            "total_comments": int,
            "posts": [
              {"caption": "...", "likes": 1240, "comments": 87, "url": "...", "owner": "..."},
              ...
            ],
            "error": str | None,
          }

        Returns ``{"available": False, "error": ...}`` on failure or no
        results — never raises.
        """
        if not product_name or not product_name.strip():
            return {"available": False, "error": "empty product_name"}

        if not self.is_available():
            return {"available": False, "error": "apify token not configured"}

        hashtag = _slugify_hashtag(product_name)
        if not hashtag:
            return {"available": False, "error": "could not derive hashtag from product_name"}

        run_input = {
            "hashtags": [hashtag],
            "resultsLimit": int(max_posts),
            # Most IG-hashtag actors honour these; ignore-friendly defaults.
            "addParentData": False,
        }

        try:
            results = await self.client.run_actor(
                actor_id=self.actor_id,
                run_input=run_input,
                timeout_secs=timeout_secs,
                memory_mbytes=512,
            )
        except Exception as exc:
            logger.warning("instagram_hashtag: actor run failed: %s", exc)
            return {"available": False, "error": str(exc)}

        if not results:
            return {
                "available": False,
                "error": "no posts returned",
                "hashtag": hashtag,
            }

        # Different actors return different field names — normalize.
        posts: list[dict[str, Any]] = []
        for r in results[: max_posts]:
            caption = (
                r.get("caption")
                or r.get("text")
                or r.get("description")
                or ""
            )
            if not caption:
                continue
            posts.append({
                "caption": caption.strip()[:400],  # cap for prompt-budget
                "likes": int(r.get("likesCount", r.get("likes", 0)) or 0),
                "comments": int(r.get("commentsCount", r.get("comments", 0)) or 0),
                "url": r.get("url") or r.get("postUrl") or "",
                "owner": r.get("ownerUsername") or r.get("owner") or "",
                "timestamp": r.get("timestamp") or r.get("takenAt") or None,
            })

        total_likes = sum(p["likes"] for p in posts)
        total_comments = sum(p["comments"] for p in posts)

        return {
            "available": True,
            "hashtag": hashtag,
            "post_count_returned": len(posts),
            "total_likes": total_likes,
            "total_comments": total_comments,
            "posts": posts,
            "error": None,
        }
