"""Apify response cache — key stability, TTL policy, stale-serve, failure isolation.

Guards the #57 follow-up: catalog_warm re-asked ~25 DISTINCT Meta sub-queries
~60x/month because nothing survived the cron process, burning the $45 Apify cap
three weeks into a four-week cycle.
"""

from datetime import datetime, timedelta

import pytest


def test_model_roundtrips(engine):
    from sqlalchemy.orm import Session

    from ospra_os.database.apify_cache_models import ApifyResponseCache
    from ospra_os.database.base import Base

    Base.metadata.create_all(bind=engine, tables=[ApifyResponseCache.__table__])
    with Session(engine) as s:
        s.query(ApifyResponseCache).delete()
        s.add(ApifyResponseCache(
            cache_key="k1", actor_id="acme/actor", run_input_summary="{}",
            items=[{"a": 1}], item_count=1, fetched_at=datetime.utcnow(),
        ))
        s.commit()
        row = s.query(ApifyResponseCache).filter_by(cache_key="k1").one()
        assert row.items == [{"a": 1}]
        assert row.item_count == 1
        assert row.hit_count == 0
