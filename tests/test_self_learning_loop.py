"""
Self-learning loop regression tests (audit T164).

The flagship promise: recorded product outcomes change future recommendation
scores. That loop was severed at a precise seam:

  * discovery scoring (product_discovery._get_learned_niche_adjustment) reads the
    learned delta from the GLOBAL NicheLearning row:
        NicheLearning.niche == niche.lower()  AND  user_id IS NULL
  * but outcome_service only ever wrote a PER-USER row (user_id=user_id) using
    the ORIGINAL-case niche.

So the global row the reader needs was never created, and the case never matched
either. The learned adjustment was computed, stored, and never read.

These tests reproduce the *exact* discovery read query and assert an outcome
measurably reaches it. If someone reverts the global-row maintenance or the niche
normalisation, they fail.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-self-learning-tests")

from ospra_os.database.base import Base  # noqa: E402
from ospra_os.database.performance_models import NicheLearning  # noqa: E402
from ospra_os.services.outcome_service import OutcomeService  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[NicheLearning.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _discovery_reads(db, niche: str) -> float:
    """Reproduce product_discovery._get_learned_niche_adjustment's query exactly."""
    row = (
        db.query(NicheLearning)
        .filter(NicheLearning.niche == niche.lower())
        .filter(NicheLearning.user_id.is_(None))
        .first()
    )
    return float(row.niche_score_adjustment) if row else 0.0


def _record(db, *, outcome: str, n: int = 1, niche: str = "Smart Home", user_id: int = 7):
    svc = OutcomeService(db)
    for i in range(n):
        svc._update_niche_learning(
            user_id=user_id, niche=niche, product_id=1000 + i,
            outcome_classification=outcome, revenue=500.0, profit=200.0, margin=40.0,
        )
    db.commit()


def test_recorded_success_reaches_the_discovery_read_path(db):
    """The core loop: a success outcome must be visible to discovery scoring."""
    assert _discovery_reads(db, "smart home") == 0.0  # nothing learned yet
    _record(db, outcome="success", n=5)
    assert _discovery_reads(db, "smart home") == 10.0  # >80% success -> +10


def test_global_row_is_created_and_lowercased(db):
    """Reader uses user_id IS NULL + lowercase; writer must satisfy both."""
    _record(db, outcome="success", n=3, niche="Smart Home")
    glob = db.query(NicheLearning).filter(NicheLearning.user_id.is_(None)).first()
    assert glob is not None, "global (user_id IS NULL) row was never created"
    assert glob.niche == "smart home", "niche must be normalised to lowercase"


def test_per_user_row_still_maintained(db):
    """Per-user row is kept for future personalization."""
    _record(db, outcome="success", n=3, user_id=42)
    per_user = db.query(NicheLearning).filter(NicheLearning.user_id == 42).first()
    assert per_user is not None
    assert per_user.success_rate == 100.0


def test_failure_outcomes_suppress_the_niche(db):
    """All-failure -> negative adjustment reaches discovery."""
    _record(db, outcome="failure", n=5)
    assert _discovery_reads(db, "smart home") == -10.0


def test_outcome_measurably_changes_a_future_score(db):
    """End-to-end: the adjustment moves a product's score the way discovery applies it."""
    _record(db, outcome="success", n=5)
    adj = _discovery_reads(db, "smart home")
    base = 72.0
    clipped = max(-25.0, min(25.0, adj))          # discovery caps at +/-25
    adjusted = round(base * (1.0 + clipped / 100.0), 1)
    assert adj == 10.0
    assert adjusted == 79.2                         # 72 * 1.10


def test_first_ever_outcome_does_not_crash_on_none_counters(db):
    """A brand-new niche row must not blow up on None += 1 before flush."""
    _record(db, outcome="success", n=1, niche="Totally New Niche")
    assert _discovery_reads(db, "totally new niche") in (0.0, 5.0, 10.0)
