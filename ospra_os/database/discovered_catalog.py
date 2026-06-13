"""
Discovered product catalog — the persistent, cross-process store (#56).

The discovery request cache (`ProductDiscoveryCache`) is in-memory only, so it
is wiped on every restart and a background job CANNOT share it with the web
process. This table is the durable catalog: a Render cron
(`ospra_os/tasks/catalog_warm.py`) WRITES graded products here across many
niches on a schedule, and the API READS it so the dashboard shows dozens of
products with a real track record instead of one on-demand result.

"Days of proof" comes from `first_seen_at`: the first warm cycle that surfaced
a product anchors the date; later cycles bump `last_seen_at`/`times_seen` but
never reset `first_seen_at`. So a product that keeps re-surfacing accrues a
provable age — the "we caught this N days ago and it held" trust signal.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text, Index

from ospra_os.database.base import Base


class DiscoveredProduct(Base):
    __tablename__ = "discovered_catalog"

    id = Column(Integer, primary_key=True)

    # Stable identity for upsert/dedupe across warm cycles (hash of title+image).
    product_key = Column(String(64), unique=True, nullable=False, index=True)

    niche = Column(String(64), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    image_url = Column(Text, nullable=True)
    supplier = Column(String(32), nullable=True)  # cj_dropshipping / aliexpress

    # Grading + opportunity signals (surfaced to the UI as badges/filters).
    grade = Column(String(16), nullable=True, index=True)       # recommendation tier
    score = Column(Float, nullable=True, index=True)            # final/oi score 0-100
    saturation_score = Column(Float, nullable=True)             # 0-100 (100 = oversaturated)
    opportunity_score = Column(Float, nullable=True)            # 100 - saturation
    velocity_phase = Column(String(24), nullable=True, index=True)  # discovery/early_spike/growth/maturity/decline
    sentiment_score = Column(Float, nullable=True)

    # Full product dict for the cards (kept verbatim so the UI needs no reshape).
    payload = Column(JSON, nullable=True)

    # Proof-age tracking.
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    times_seen = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    @property
    def days_of_proof(self) -> int:
        """Whole days since this product was first caught."""
        anchor = self.first_seen_at
        if anchor is None:
            return 0
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - anchor).days)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DiscoveredProduct niche={self.niche!r} grade={self.grade!r} "
            f"score={self.score} phase={self.velocity_phase!r} "
            f"days_of_proof={self.days_of_proof}>"
        )


Index("idx_catalog_niche_grade", DiscoveredProduct.niche, DiscoveredProduct.grade)
Index("idx_catalog_score", DiscoveredProduct.score)
