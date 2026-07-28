"""
Apify response cache (#57 follow-up)
====================================

Persists Apify actor responses across processes so identical questions stop
costing money. Mirrors the ``cached_google_trends`` pattern: one row per
distinct question, ``fetched_at`` drives staleness.

What this exists to fix: catalog_warm asked ~25 DISTINCT Meta sub-queries
~60 times a month (5 niches x 5 sub-queries x 2 runs/day) because nothing
persisted between cron processes. That exhausted the $45/month Apify cap three
weeks into a four-week cycle, and the resulting 403 blackout blanked the
winner-proof signal on every product.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from ospra_os.database.base import Base


class ApifyResponseCache(Base):
    __tablename__ = "apify_response_cache"

    id = Column(Integer, primary_key=True)

    # SHA-256 of (actor_id, canonical run_input, max_items) — the lookup.
    cache_key = Column(String(64), unique=True, nullable=False, index=True)

    # Kept out of the hash so per-actor TTL and spend reporting can filter and
    # aggregate without decoding keys.
    actor_id = Column(String(128), nullable=False, index=True)

    # Truncated readable input so a human can tell what a row is.
    run_input_summary = Column(String(512), nullable=True)

    # Exactly what run_actor returned.
    items = Column(JSON, nullable=False)
    item_count = Column(Integer, nullable=False, default=0)

    fetched_at = Column(DateTime, nullable=False, index=True)

    # Proves the cache earns its keep.
    hit_count = Column(Integer, nullable=False, default=0)
    last_hit_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ApifyResponseCache actor={self.actor_id!r} "
            f"items={self.item_count} fetched_at={self.fetched_at}>"
        )
