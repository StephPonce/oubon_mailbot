"""
Seed-data purge + read-path provenance guard (fail-if-reverted).

The December-2025 seed batch (scripts/seed_learning_from_shopify.py) put a
year of imported Shopify history into the learning tables as
event_type='historical_sale' + a product_performance snapshot batch dated
2025-12-09 + a derived global_learning_weights baseline. Migration 008
purges that batch; ORGANIC_SALE_EVENT_TYPES guards the read paths so a
re-run of the seeder can never feed the learning system again.

Pins here:
1. The provenance constants themselves (the guard's anchor).
2. Migration 008's exact predicates: seeded rows die, organic rows —
   including first_sale events the public scoreboard depends on — survive.
3. The live aggregation (calculate_global_patterns) derives weights from
   organic events ONLY, even with seeded rows present.
"""

import asyncio
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ospra_os.database.base import Base
from ospra_os.database.performance_models import (
    AILearningEvent,
    GlobalLearningWeights,
    ORGANIC_SALE_EVENT_TYPES,
    ProductPerformance,
    SEEDED_EVENT_TYPES,
)


def _db():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng, tables=[
        ProductPerformance.__table__,
        AILearningEvent.__table__,
        GlobalLearningWeights.__table__,
    ])
    return eng, sessionmaker(bind=eng)


def test_provenance_constants_contract():
    """The guard's anchor: historical_sale is seeded, never organic."""
    assert "historical_sale" in SEEDED_EVENT_TYPES
    assert "historical_sale" not in ORGANIC_SALE_EVENT_TYPES
    assert "sale" in ORGANIC_SALE_EVENT_TYPES
    assert not set(SEEDED_EVENT_TYPES) & set(ORGANIC_SALE_EVENT_TYPES)


def test_migration_008_purges_seed_batch_and_spares_organic():
    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location(
        "_mig008",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions", "20260722_1200_008_purge_seeded_learning.py",
        ),
    )
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    eng, maker = _db()
    s = maker()
    # product_performance: 2 seeded (2025-12-09) + 1 organic (2026-07-01).
    # (product_id, date) is unique, so seeded rows get distinct products.
    for pid, d in ((1, date(2025, 12, 9)), (2, date(2025, 12, 9)), (1, date(2026, 7, 1))):
        s.add(ProductPerformance(
            product_id=pid, store_id=1, user_id=1, date=d,
            orders=1, units_sold=1, gross_revenue=10.0,
        ))
    # events: 2 seeded + 1 organic sale + 1 first_sale (scoreboard depends on it)
    s.add(AILearningEvent(event_type="historical_sale", details={"revenue": 999}))
    s.add(AILearningEvent(event_type="historical_sale", details={"revenue": 999}))
    s.add(AILearningEvent(event_type="sale", details={"revenue": 42}))
    s.add(AILearningEvent(event_type="first_sale", details={"revenue": 42}))
    # the seeder-derived weights baseline
    s.add(GlobalLearningWeights(version="1.0", learning_cycles=1))
    s.commit()

    with eng.begin() as bind:
        assert mig.purge_seeded_product_performance(bind) == 2
        assert mig.purge_seeded_learning_events(bind) == 2
        assert mig.purge_global_learning_weights(bind) == 1

    s = maker()
    # Organic survivors — exactly what must NOT be touched.
    perf = s.query(ProductPerformance).all()
    assert [p.date for p in perf] == [date(2026, 7, 1)]
    kinds = sorted(e.event_type for e in s.query(AILearningEvent).all())
    assert kinds == ["first_sale", "sale"]
    assert s.query(GlobalLearningWeights).count() == 0

    # Idempotent: a re-run deletes nothing further.
    with eng.begin() as bind:
        assert mig.purge_seeded_product_performance(bind) == 0
        assert mig.purge_seeded_learning_events(bind) == 0


def test_global_patterns_derive_from_organic_events_only(monkeypatch):
    """The live aggregation with seeded rows still present (e.g. the seeder
    re-run after the purge) must count ONLY organic sales."""
    from ospra_os.learning import analysis_jobs as aj

    eng, maker = _db()
    monkeypatch.setattr(aj, "SessionLocal", maker)

    s = maker()
    s.add(AILearningEvent(
        user_id=1, event_type="sale",
        details={"niche": "smart_home", "price": 25.0, "quantity": 2, "revenue": 100.0},
        created_at=datetime(2026, 7, 20),
    ))
    for _ in range(3):  # poison attempt: seeded rows with huge revenue
        s.add(AILearningEvent(
            user_id=1, event_type="historical_sale",
            details={"niche": "poisoned_niche", "price": 99.0, "quantity": 50, "revenue": 9999.0},
            created_at=datetime(2025, 12, 9),
        ))
    s.commit()

    asyncio.run(aj.calculate_global_patterns())

    s = maker()
    glw = s.query(GlobalLearningWeights).first()
    assert glw is not None, "aggregation should have written a weights row"
    assert glw.total_sales_analyzed == 1                # organic only
    assert glw.total_revenue_analyzed == pytest.approx(100.0)  # not 30097
    assert "poisoned_niche" not in (glw.niche_confidence or {})
    assert (glw.niche_confidence or {}).get("smart_home") == pytest.approx(1.0)
