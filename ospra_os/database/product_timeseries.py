"""
Product time-series — daily per-product signal snapshots (#56 Phase 1, the moat).

ONE row per (product_key, snapshot_date). The catalog_warm cron writes a row
each day for every product it discovers, capturing the raw demand/competition
signals AND the grade-of-the-day. Over time this becomes the moat: we can see a
product's trajectory — advertiser density filling in, order count accelerating,
trends rising — which is what powers velocity-based saturation grading, the
Emergence/Growth lifecycle classifier, and the outcome scoreboard.

"Lost days are unrecoverable" — this table must start collecting immediately;
no backfill is possible for signals that only exist in the present.

Design notes:
- Keyed by `product_key` (the SAME sha256(title|image) hash discovered_catalog
  uses) so the two join cleanly. discovered_catalog = current state (upserted,
  proof-age); product_timeseries = history (one row per day).
- Signal columns are NULLABLE on purpose. A missing signal stores NULL, never a
  fabricated zero — `signal_count` records how many were actually fresh so the
  confidence gate can mark thin days as low-confidence rather than bad products.
"""

import hashlib
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer, String, UniqueConstraint, Index,
)

from ospra_os.database.base import Base


def product_identity_key(product: dict) -> str:
    """THE product identity for catalog/timeseries joins — single source of truth.

    Re-audit M7: the original key was sha256(title|image), but supplier titles
    and CDN image URLs mutate — any change forked the product's history and
    reset its proof-age, silently undermining the "days of proof" premise.

    Prefer IMMUTABLE supplier IDs (in deterministic priority order); fall back
    to the legacy title|image hash ONLY when no supplier ID exists. The field
    name is baked into the hash so cj_pid=123 and product_id=123 can't collide.

    Used by BOTH catalog_warm (writer) and product_discovery (reader) — do not
    duplicate this logic elsewhere.
    """
    for field in ("cj_pid", "aliexpress_product_id", "product_id", "productId",
                  "supplier_product_id"):
        val = product.get(field)
        if val not in (None, "", 0):
            return hashlib.sha256(f"{field}:{val}".encode()).hexdigest()[:32]
    title = (product.get("title") or product.get("product_name") or "").strip().lower()
    image = (product.get("image_url") or product.get("main_image") or "").strip()
    return hashlib.sha256(f"{title}|{image}".encode()).hexdigest()[:32]


class ProductTimeseries(Base):
    __tablename__ = "product_timeseries"

    id = Column(Integer, primary_key=True)

    # Joins to discovered_catalog.product_key.
    product_key = Column(String(64), nullable=False, index=True)
    niche = Column(String(64), nullable=True, index=True)
    title = Column(String(512), nullable=True)  # denormalized for readability

    # The day this snapshot represents (UTC). One row per product per day.
    snapshot_date = Column(Date, nullable=False, index=True)

    # --- Raw market signals (the moat). NULL = not measured this day. ---
    meta_advertiser_count = Column(Integer, nullable=True)   # Meta Ad Library density
    aliexpress_orders = Column(Integer, nullable=True)       # recent AE order volume
    google_trends_interest = Column(Float, nullable=True)    # 0-100 Trends interest
    tiktok_units_sold = Column(Integer, nullable=True)       # TikTok Shop units_sold_7d
    tiktok_velocity = Column(Float, nullable=True)           # TikTok Shop growth velocity

    # --- Grade-of-the-day snapshot (for slope + outcome scoreboard). ---
    grade = Column(String(16), nullable=True)
    score = Column(Float, nullable=True)
    saturation_score = Column(Float, nullable=True)
    opportunity_score = Column(Float, nullable=True)
    velocity_phase = Column(String(24), nullable=True)
    sentiment_score = Column(Float, nullable=True)

    # How many of the 5 raw signals were fresh this day (confidence gate).
    signal_count = Column(Integer, nullable=False, default=0)

    # Re-audit M2 (survivorship bias): False = the product was in the catalog
    # but did NOT appear in this day's discovery output. These "absence rows"
    # keep dropped products' trajectories alive — the decliners are exactly
    # what the velocity model needs to learn from. Signals are NULL on such
    # rows; presence/absence itself is the datum.
    seen_in_discovery = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        # The core invariant: at most one snapshot per product per day. Re-runs
        # of the cron on the same day UPDATE the row rather than duplicate it.
        UniqueConstraint("product_key", "snapshot_date", name="uq_timeseries_product_day"),
        Index("idx_timeseries_key_date", "product_key", "snapshot_date"),
        Index("idx_timeseries_niche_date", "niche", "snapshot_date"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ProductTimeseries key={self.product_key[:8]} date={self.snapshot_date} "
            f"grade={self.grade} adv={self.meta_advertiser_count} "
            f"orders={self.aliexpress_orders} signals={self.signal_count}>"
        )
