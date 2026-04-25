"""
YouTube Data API v3 connector — Phase I.

Replaces the placeholder ``YouTubeIntegration`` in
``intelligence_engine.py`` (which returned hard-coded zeros) with real
YouTube search + video stats + top-comments fetching.

Free tier: 10,000 quota units / day.
Cost per product:
  - search.list        : 100 units (returns up to N videos for a query)
  - videos.list        :   1 unit per call (batched up to 50 IDs)
  - commentThreads.list:   1 unit per call (per video)

Conservative budget: 1 search + 1 video-stats batch + 3 comment-thread
fetches = ~104 units per product. With top-10 product cap that's ~1,040
units per discovery — well within the daily 10k quota even at 10
discoveries/day.

Output shape mirrors the other social-evidence dicts so the qualitative
agent can read it without special-casing.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeReviewsConnector:
    """
    YouTube product-review data via the Data API v3.

    Returns:
      - review_video_count: how many videos match "<product> review"
      - total_views: sum of view counts across matched videos
      - total_likes: sum of like counts
      - total_comments: sum of comment counts
      - top_videos: [{title, channel, views, likes, url}, ...]
      - top_comments: [{text, author, likes, video_title}, ...]

    Use top_comments as qualitative-agent input — it's actual viewer
    feedback prose.
    """

    def __init__(self, api_key: Optional[str] = None, *, region: str = "US"):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.region = region

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def get_product_reviews(
        self,
        product_name: str,
        *,
        max_videos: int = 5,
        max_comments_per_video: int = 5,
        timeout_secs: float = 15.0,
    ) -> dict[str, Any]:
        """
        Search YouTube for "<product> review", pull stats + top comments.

        Returns ``{"available": False, "error": ...}`` on any failure —
        never raises. The default ``max_videos=5`` keeps quota cost
        ~107 units per product.
        """
        if not self.is_available():
            return {"available": False, "error": "YOUTUBE_API_KEY not set"}
        if not product_name or not product_name.strip():
            return {"available": False, "error": "empty product_name"}

        query = f"{product_name} review"

        try:
            async with httpx.AsyncClient(timeout=timeout_secs) as client:
                # 1. Search for review videos (cost: 100 units)
                search_resp = await client.get(
                    f"{YOUTUBE_API_BASE}/search",
                    params={
                        "key": self.api_key,
                        "part": "snippet",
                        "q": query,
                        "type": "video",
                        "maxResults": max_videos,
                        "regionCode": self.region,
                        "relevanceLanguage": "en",
                        "videoCategoryId": "26",  # How-to & Style
                    },
                )
                if search_resp.status_code != 200:
                    return {
                        "available": False,
                        "error": f"search HTTP {search_resp.status_code}: {search_resp.text[:200]}",
                    }
                search_data = search_resp.json()
                items = search_data.get("items") or []
                if not items:
                    return {
                        "available": False,
                        "error": "no review videos found",
                        "review_video_count": 0,
                    }

                video_ids = [
                    it.get("id", {}).get("videoId")
                    for it in items
                    if it.get("id", {}).get("videoId")
                ]
                videos_by_id = {
                    it["id"]["videoId"]: {
                        "title": (it.get("snippet") or {}).get("title", ""),
                        "channel": (it.get("snippet") or {}).get("channelTitle", ""),
                        "published_at": (it.get("snippet") or {}).get("publishedAt", ""),
                    }
                    for it in items
                    if it.get("id", {}).get("videoId")
                }

                if not video_ids:
                    return {
                        "available": False,
                        "error": "no video IDs in search response",
                    }

                # 2. Stats for those videos (cost: 1 unit)
                stats_resp = await client.get(
                    f"{YOUTUBE_API_BASE}/videos",
                    params={
                        "key": self.api_key,
                        "part": "statistics,snippet",
                        "id": ",".join(video_ids),
                    },
                )
                if stats_resp.status_code == 200:
                    for v in (stats_resp.json().get("items") or []):
                        vid = v.get("id")
                        if vid and vid in videos_by_id:
                            stats = v.get("statistics") or {}
                            videos_by_id[vid]["views"] = int(stats.get("viewCount", 0) or 0)
                            videos_by_id[vid]["likes"] = int(stats.get("likeCount", 0) or 0)
                            videos_by_id[vid]["comments_total"] = int(
                                stats.get("commentCount", 0) or 0
                            )

                # 3. Top comments for the top-N videos (cost: 1 unit each)
                top_comments: list[dict[str, Any]] = []
                # Pull comments only for the first 3 videos to stay
                # well under quota even on heavy days.
                for vid in video_ids[:3]:
                    try:
                        comments_resp = await client.get(
                            f"{YOUTUBE_API_BASE}/commentThreads",
                            params={
                                "key": self.api_key,
                                "part": "snippet",
                                "videoId": vid,
                                "order": "relevance",
                                "maxResults": max_comments_per_video,
                                "textFormat": "plainText",
                            },
                        )
                        if comments_resp.status_code != 200:
                            continue
                        for thread in (comments_resp.json().get("items") or []):
                            top = (
                                thread.get("snippet", {})
                                .get("topLevelComment", {})
                                .get("snippet", {})
                            )
                            text = (top.get("textOriginal") or top.get("textDisplay") or "").strip()
                            if not text:
                                continue
                            top_comments.append({
                                "text": text[:400],  # cap for prompt-budget
                                "author": top.get("authorDisplayName"),
                                "likes": int(top.get("likeCount", 0) or 0),
                                "video_title": videos_by_id.get(vid, {}).get("title", ""),
                                "video_id": vid,
                            })
                    except Exception:
                        # Comments can be disabled per-video; skip and continue.
                        continue

                videos_list = [
                    {
                        "title": v.get("title"),
                        "channel": v.get("channel"),
                        "views": v.get("views", 0),
                        "likes": v.get("likes", 0),
                        "comments_total": v.get("comments_total", 0),
                        "url": f"https://www.youtube.com/watch?v={vid}",
                    }
                    for vid, v in videos_by_id.items()
                ]

                total_views = sum(v.get("views", 0) for v in videos_list)
                total_likes = sum(v.get("likes", 0) for v in videos_list)
                total_comments = sum(v.get("comments_total", 0) for v in videos_list)

                return {
                    "available": True,
                    "review_video_count": len(videos_list),
                    "total_views": total_views,
                    "total_likes": total_likes,
                    "total_comments": total_comments,
                    "top_videos": videos_list,
                    "top_comments": top_comments[:15],
                    "query": query,
                    "error": None,
                }
        except httpx.TimeoutException:
            return {"available": False, "error": f"timeout after {timeout_secs}s"}
        except Exception as exc:
            logger.warning("youtube: get_product_reviews failed: %s", exc)
            return {"available": False, "error": str(exc)}
