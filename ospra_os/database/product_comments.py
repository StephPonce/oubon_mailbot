"""
Per-comment engagement store — the raw material for the organic-vs-seeded moat
(Moat Phase 2). ONE row per (product_key, comment_id).

Comments are scraped from the TikTok VIDEOS driving a product's sales
(clockworks/tiktok-comments-scraper) and keyed to the product via the SHARED
``product_identity_key`` on the TikTok product id — the same identity the
Phase-1 units-sold snapshots use, so a product's sales trajectory and its
engagement authenticity join cleanly.

The seeded-vs-organic classifier (intelligence/comment_authenticity.py) reads
these rows to decide whether a product's demand is REAL or manufactured. That
verdict can only ever DEMOTE a grade (never inflate) — a product with seeded
hype should lose grade against one with organic pull at the same units-sold.

FIELD REALITY (verified against the actor's documented output, 2026-07-15):
the comments actor returns per comment: text, diggCount, replyCommentTotal,
createTimeISO, uniqueId (author handle), uid (author id), cid (comment id),
videoWebUrl, avatarThumbnail. It does NOT return author follower count or
account creation date — those are profile-level fields the comments endpoint
omits. ``author_is_default_handle`` is therefore a DERIVED proxy for
throwaway/new accounts (TikTok auto-assigns userNNNNNNNN handles to accounts
that never set a username), not a literal account age.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint, Index,
)

from ospra_os.database.base import Base


class ProductComment(Base):
    __tablename__ = "product_comments"

    id = Column(Integer, primary_key=True)

    # Joins to the Phase-1 units-sold snapshots (same product_identity_key).
    product_key = Column(String(64), nullable=False, index=True)
    tiktok_product_id = Column(String(64), nullable=True, index=True)

    # Comment identity (cid) — the dedup/upsert key within a product.
    comment_id = Column(String(64), nullable=False)

    # --- Raw comment signals (the moat's inputs). ---
    text = Column(Text, nullable=True)
    digg_count = Column(Integer, nullable=True)          # comment likes
    reply_count = Column(Integer, nullable=True)         # replyCommentTotal
    created_at = Column(DateTime, nullable=True)         # parsed from createTimeISO (UTC, naive)

    # Author identity (NO follower count / account age — not in the actor output).
    author_unique_id = Column(String(128), nullable=True)  # handle, e.g. "rizqirxq"
    author_uid = Column(String(64), nullable=True)         # stable author id
    author_verified = Column(Boolean, nullable=True)
    # DERIVED proxy for a throwaway/new account: an auto-assigned userNNNN handle.
    author_is_default_handle = Column(Boolean, nullable=True)

    video_url = Column(String(512), nullable=True)         # source video (videoWebUrl)
    scraped_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("product_key", "comment_id", name="uq_comment_product_cid"),
        Index("idx_comment_product", "product_key"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ProductComment key={self.product_key[:8]} cid={self.comment_id} "
            f"digg={self.digg_count} author={self.author_unique_id}>"
        )
