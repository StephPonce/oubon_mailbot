"""
Cached Google Trends — pre-warm store (task #47)
================================================

The Apify Google-Trends actor takes ~12 min/run and pytrends 429s
intermittently, so neither belongs on the discovery request path. This table
is the shared store the web process READS; a Render cron job (see
``ospra_os/tasks/trend_warm.py``) WRITES it every 12h.

Demand-driven warming: when the request path misses the cache it records the
term here (``fetched_at`` NULL, ``miss_count`` incremented). The next warm run
fetches pending + stale terms first, so the cache converges on exactly the
vocabulary discovery actually asks for — winner phrases, not just niche seeds.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String

from ospra_os.database.base import Base


class CachedGoogleTrend(Base):
    __tablename__ = "cached_google_trends"

    id = Column(Integer, primary_key=True)

    # Lowercased search phrase — the cache key.
    term = Column(String(255), unique=True, nullable=False, index=True)

    # 0-100 comparable recent-vs-baseline metric (50 = at baseline,
    # 100 = ~2x baseline) — same math as TrendData.current_interest.
    # NULL = pending: requested by the read path, not yet warmed.
    interest = Column(Integer, nullable=True)
    direction = Column(String(16), nullable=True)   # rising / stable / falling
    momentum = Column(Float, nullable=True)         # % change over the window
    source = Column(String(32), nullable=True)      # apify / pytrends
    related_queries = Column(JSON, nullable=True)   # qualitative context for AI

    # Demand signals for the warm job's prioritisation.
    miss_count = Column(Integer, nullable=False, default=0)
    last_requested_at = Column(DateTime, nullable=True)

    # NULL until the first successful warm.
    fetched_at = Column(DateTime, nullable=True, index=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<CachedGoogleTrend term={self.term!r} interest={self.interest} "
            f"direction={self.direction} fetched_at={self.fetched_at}>"
        )
