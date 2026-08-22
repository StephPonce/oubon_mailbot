"""GET /api/emails/recent must return only the caller's own rows.

Before migration 010 the email_metrics table had NO owner column, so this
endpoint returned every tenant's customer_email + subject to any caller — and
there was nothing to filter on even after auth was added. These tests pin the
two properties that matter: a tenant sees their own rows, and never anyone
else's — including the UNOWNED rows written before the migration.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ospra_os.analytics.email_analytics import Base, EmailMetric


@pytest.fixture()
def metrics_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'m.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    now = datetime.utcnow()
    session.add_all([
        EmailMetric(user_id=1, customer_email="alice@buyer.test",
                    subject="Where is my order", timestamp=now),
        EmailMetric(user_id=2, customer_email="bob@buyer.test",
                    subject="Refund please", timestamp=now - timedelta(minutes=1)),
        # Pre-migration row: owner unknown.
        EmailMetric(user_id=None, customer_email="legacy@buyer.test",
                    subject="Legacy", timestamp=now - timedelta(minutes=2)),
    ])
    session.commit()
    yield session
    session.close()


def _visible_to(session, user_id):
    return [
        m.customer_email
        for m in session.query(EmailMetric)
        .filter(EmailMetric.user_id == user_id)
        .order_by(EmailMetric.timestamp.desc())
        .all()
    ]


def test_tenant_sees_only_own_rows(metrics_session):
    assert _visible_to(metrics_session, 1) == ["alice@buyer.test"]
    assert _visible_to(metrics_session, 2) == ["bob@buyer.test"]


def test_unowned_rows_are_never_served(metrics_session):
    """Rows predating migration 010 have no known owner. Attributing them to
    whoever asks would leak one tenant's customers to another, so they are
    served to nobody."""
    for uid in (1, 2, 999):
        assert "legacy@buyer.test" not in _visible_to(metrics_session, uid)


def test_model_has_owner_column():
    """The column's absence was the root cause — guard against its removal."""
    assert "user_id" in {c.name for c in EmailMetric.__table__.columns}
