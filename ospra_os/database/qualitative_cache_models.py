"""
Qualitative AI read cache (#57 follow-up)
=========================================

The qualitative agent runs on the top 10 ranked products of EVERY discovery
run — 5 niches x 2 crons/day x 10 = ~3,000 grok-3 calls/month, plus every
user-triggered search. There was no cache of any kind, so the same product with
unchanged evidence was re-read twice a day forever.

Keyed on (product identity + the exact evidence fed to the prompt + model), so
"the evidence changed" and "cache miss" are the same event — no separate
invalidation bookkeeping to get wrong.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from ospra_os.database.base import Base


class QualitativeReadCache(Base):
    __tablename__ = "qualitative_read_cache"

    id = Column(Integer, primary_key=True)

    # SHA-256 over (model, product_key, evidence) — the lookup.
    cache_key = Column(String(64), unique=True, nullable=False, index=True)

    # Kept out of the hash for debugging and targeted pruning.
    product_key = Column(String(255), nullable=False, index=True)
    provider = Column(String(32), nullable=True)
    model = Column(String(64), nullable=True)

    # QualitativeAssessment.to_dict()
    assessment = Column(JSON, nullable=False)

    fetched_at = Column(DateTime, nullable=False, index=True)
    hit_count = Column(Integer, nullable=False, default=0)
    last_hit_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<QualitativeReadCache product={self.product_key!r} "
            f"model={self.model!r} fetched_at={self.fetched_at}>"
        )
