"""
AliExpress DS product-detail cache.

Persists `aliexpress.ds.product.get` results — the REAL merchant cost behind
every product's margin — so the catalog cron stops re-fetching them from an
empty per-process dict on every run.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from ospra_os.database.base import Base


class AEDSDetailCache(Base):
    __tablename__ = "ae_ds_detail_cache"

    id = Column(Integer, primary_key=True)

    # SHA-256 of (product_id, country, currency, language) — merchant price is
    # ship-to- and currency-dependent, so all four belong in the key.
    cache_key = Column(String(64), unique=True, nullable=False, index=True)

    # Kept as columns for debugging and targeted pruning.
    product_id = Column(String(64), nullable=False, index=True)
    country = Column(String(8), nullable=True)
    currency = Column(String(8), nullable=True)

    # Output of _normalise_product_detail — small, stable, and exactly what
    # enrich_pricing consumes.
    detail = Column(JSON, nullable=False)

    fetched_at = Column(DateTime, nullable=False, index=True)
    hit_count = Column(Integer, nullable=False, default=0)
    last_hit_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AEDSDetailCache product_id={self.product_id!r} "
            f"fetched_at={self.fetched_at}>"
        )
