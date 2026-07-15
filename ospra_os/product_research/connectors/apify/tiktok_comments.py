"""
TikTok comments scraper (Apify) — Moat Phase 2, the organic-vs-seeded raw material.

Scrapes comments from the TikTok VIDEOS driving a product's sales and persists
per-comment signals (text, likes, timestamp, author identity) keyed to the
product via the shared ``product_identity_key``. The seeded-vs-organic
classifier reads these to decide if demand is REAL or manufactured.

ACTOR (chosen by store-metadata evidence, 2026-07-15):
  clockworks/tiktok-comments-scraper — 35.8k users, PAY_PER_EVENT
  ~$0.001/comment (BRONZE tier) → 100 comments × 10 top products ≈ $1.00/run.

REAL OUTPUT SHAPE (verified from the actor's documented example, NOT the
README prose):
  input : {"postURLs": ["https://www.tiktok.com/@u/video/123"],
           "commentsPerPost": 100, "maxRepliesPerComment": 2}
  output: {"text", "diggCount", "replyCommentTotal", "createTimeISO",
           "uniqueId", "uid", "cid", "videoWebUrl", "avatarThumbnail"}

FIELD-AVAILABILITY FINDING (report): the actor takes VIDEO URLs (not product
URLs) and its output contains NO author follower count and NO account
age/creation date — those are profile-level fields the comments endpoint
omits. The seeded signals are therefore built from what IS returned: comment
text (duplicate-ratio), createTimeISO (burst-vs-video-age, 48h clustering),
uniqueId/uid (author concentration), and a DERIVED default-handle proxy for
throwaway/new accounts (TikTok auto-assigns userNNNNNNNN handles).

LIVE_VERIFIED = False: the Apify account is over its monthly cap ($45.13/$45,
resets 2026-08-07), so no live run has confirmed the shape. The parser
canonicalizes the documented fields and FAILS CLOSED (returns empty, never
fabricated comments) on an unrecognized shape. Run
scripts/verify_tiktok_comments_actor.py for one capped live run when credits
exist, then flip this flag.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LIVE_VERIFIED = False

DEFAULT_ACTOR = "clockworks/tiktok-comments-scraper"

# TikTok auto-assigns handles like "user6904063862041396225" to accounts that
# never set a username — a strong proxy for throwaway / freshly-minted accounts
# (which seeding rings use). NOT a literal account age (unavailable), a proxy.
_DEFAULT_HANDLE_RE = re.compile(r"^user\d{6,}$", re.IGNORECASE)

# Documented alias tables (first present key wins).
_TEXT_KEYS = ("text", "comment", "commentText")
_DIGG_KEYS = ("diggCount", "digg_count", "likes", "likeCount")
_REPLY_KEYS = ("replyCommentTotal", "replyCount", "reply_count", "replies")
_TIME_KEYS = ("createTimeISO", "createTime", "created_at", "timestamp")
_CID_KEYS = ("cid", "commentId", "comment_id", "id")
_HANDLE_KEYS = ("uniqueId", "unique_id", "username", "authorUniqueId")
_UID_KEYS = ("uid", "userId", "user_id", "authorId", "author_id")
_VERIFIED_KEYS = ("verified", "isVerified", "author_verified")
_VIDEO_KEYS = ("videoWebUrl", "video_url", "videoUrl", "postUrl", "postURL")

# Below this fraction of parseable comments the batch is an unknown shape and
# is rejected (fail-closed) rather than mis-parsed.
MIN_VALID_RATIO = 0.5


@dataclass
class TikTokComment:
    comment_id: str
    text: str
    digg_count: int
    reply_count: int
    created_at: Optional[datetime]
    author_unique_id: Optional[str]
    author_uid: Optional[str]
    author_verified: bool
    author_is_default_handle: bool
    video_url: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "text": self.text,
            "digg_count": self.digg_count,
            "reply_count": self.reply_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "author_unique_id": self.author_unique_id,
            "author_uid": self.author_uid,
            "author_verified": self.author_verified,
            "author_is_default_handle": self.author_is_default_handle,
            "video_url": self.video_url,
        }


def _first(item: Dict, keys, default=None):
    for k in keys:
        if k in item and item[k] not in (None, ""):
            return item[k]
    return default


def _parse_time(value) -> Optional[datetime]:
    if not value:
        return None
    s = str(value)
    try:
        # "2024-08-06T11:21:16.000Z" → naive UTC (matches the DB's naive columns).
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return datetime.utcfromtimestamp(int(float(s)))  # epoch fallback
    except (ValueError, OverflowError, OSError):
        return None


def _to_int(value, default=0) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return default


def parse_comments(items: List[Dict]) -> Dict[str, Any]:
    """Canonicalize raw actor items into TikTokComment records. A comment is
    valid only if it has a comment id AND text. Fails closed below
    MIN_VALID_RATIO (unknown shape → empty, never fabricated)."""
    if not items:
        return {"status": "empty", "comments": [], "invalid_count": 0}

    comments: List[TikTokComment] = []
    invalid = 0
    for item in items:
        if not isinstance(item, dict):
            invalid += 1
            continue
        cid = _first(item, _CID_KEYS)
        text = _first(item, _TEXT_KEYS)
        if cid is None or text is None:
            invalid += 1
            continue
        handle = _first(item, _HANDLE_KEYS)
        comments.append(TikTokComment(
            comment_id=str(cid),
            text=str(text),
            digg_count=_to_int(_first(item, _DIGG_KEYS)),
            reply_count=_to_int(_first(item, _REPLY_KEYS)),
            created_at=_parse_time(_first(item, _TIME_KEYS)),
            author_unique_id=(str(handle) if handle else None),
            author_uid=(str(_first(item, _UID_KEYS)) if _first(item, _UID_KEYS) else None),
            author_verified=bool(_first(item, _VERIFIED_KEYS, False)),
            author_is_default_handle=bool(handle and _DEFAULT_HANDLE_RE.match(str(handle))),
            video_url=_first(item, _VIDEO_KEYS),
        ))

    valid_ratio = len(comments) / len(items)
    if valid_ratio < MIN_VALID_RATIO:
        sample = sorted(items[0].keys()) if isinstance(items[0], dict) else []
        logger.error(
            "[COMMENTS] Unrecognized actor output: %d/%d parseable. First-item "
            "keys: %s — update the alias tables and re-verify.",
            len(comments), len(items), sample,
        )
        return {"status": "unverified_shape", "comments": [], "invalid_count": invalid,
                "sample_keys": sample}

    return {"status": "ok", "comments": comments, "invalid_count": invalid}


class TikTokCommentsScraper:
    """Fetch + persist comments for a product's videos. Cost-capped by
    ``comments_per_post`` (default from TIKTOK_COMMENTS_PER_POST, kept low)."""

    def __init__(self, apify_client=None):
        if apify_client is None:
            from ospra_os.product_research.connectors.apify.base_apify import ApifyClient
            apify_client = ApifyClient()
        self.client = apify_client
        self.actor_id = os.getenv("APIFY_TIKTOK_COMMENTS_ACTOR", DEFAULT_ACTOR)
        self.comments_per_post = int(os.getenv("TIKTOK_COMMENTS_PER_POST", "100"))
        self.max_replies = int(os.getenv("TIKTOK_COMMENTS_MAX_REPLIES", "0"))

    def build_input(self, video_urls: List[str]) -> Dict[str, Any]:
        """Actor input per the documented schema."""
        return {
            "postURLs": video_urls,
            "commentsPerPost": self.comments_per_post,
            "maxRepliesPerComment": self.max_replies,
        }

    async def fetch_comments(self, video_urls: List[str]) -> Dict[str, Any]:
        """Run the actor for the given video URLs and canonicalize. Caps the
        dataset fetch to comments_per_post × urls (credit hygiene)."""
        if not video_urls:
            return {"status": "empty", "comments": [], "actor_id": self.actor_id}
        run_input = self.build_input(video_urls)
        cap = self.comments_per_post * max(1, len(video_urls))

        items = await self.client.run_actor(
            actor_id=self.actor_id,
            run_input=run_input,
            timeout_secs=int(os.getenv("TIKTOK_COMMENTS_TIMEOUT_SECS", "240")),
            memory_mbytes=int(os.getenv("TIKTOK_COMMENTS_MEMORY_MB", "512")),
            max_items=cap,
        )
        parsed = parse_comments(items)
        parsed["actor_id"] = self.actor_id
        parsed["cost_estimate_usd"] = round(0.001 * len(items), 4)  # BRONZE listed rate
        return parsed


def persist_comments(
    tiktok_product_id: str, comments: List[TikTokComment]
) -> Dict[str, int]:
    """Upsert comments into product_comments, keyed to the product via the
    shared product_identity_key. Best-effort: DB issues log + return zeros."""
    stats = {"inserted": 0, "updated": 0}
    if not comments:
        return stats
    try:
        from sqlalchemy.exc import IntegrityError
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.product_comments import ProductComment
        from ospra_os.database.product_timeseries import product_identity_key
    except Exception as e:
        logger.warning(f"[COMMENTS] store unavailable: {e}")
        return stats

    key = product_identity_key({"product_id": str(tiktok_product_id)})
    session = SessionLocal()
    try:
        for c in comments:
            existing = (
                session.query(ProductComment)
                .filter_by(product_key=key, comment_id=c.comment_id)
                .first()
            )
            fields = dict(
                tiktok_product_id=str(tiktok_product_id),
                text=c.text,
                digg_count=c.digg_count,
                reply_count=c.reply_count,
                created_at=c.created_at,
                author_unique_id=c.author_unique_id,
                author_uid=c.author_uid,
                author_verified=c.author_verified,
                author_is_default_handle=c.author_is_default_handle,
                video_url=c.video_url,
            )
            if existing is None:
                session.add(ProductComment(
                    product_key=key, comment_id=c.comment_id,
                    scraped_at=datetime.utcnow(), **fields,
                ))
                stats["inserted"] += 1
            else:
                for k, v in fields.items():
                    setattr(existing, k, v)
                stats["updated"] += 1
        session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"[COMMENTS] persist failed: {e}")
    finally:
        session.close()

    if stats["inserted"] or stats["updated"]:
        logger.info("[COMMENTS] %d inserted, %d updated for product %s",
                    stats["inserted"], stats["updated"], tiktok_product_id)
    return stats
