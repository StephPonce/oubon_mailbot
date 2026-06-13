"""
Catalog warm + persistent discovered_catalog tests (#56).

Pins the durable catalog the scheduled discovery cron writes and the API reads:
upsert/dedupe, proof-age accrual (first_seen preserved, times_seen bumped),
saturation→opportunity normalization, and grade/score extraction.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ospra_os.database.base import Base
from ospra_os.database.discovered_catalog import DiscoveredProduct
from ospra_os.tasks import catalog_warm as cw


@pytest.fixture()
def session():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng, tables=[DiscoveredProduct.__table__])
    yield sessionmaker(bind=eng)()


PLUG = {
    "title": "WiFi Smart Plug Energy Monitor", "image_url": "http://img/1.jpg",
    "source": "cj_dropshipping", "tier": "BUY", "final_score": 82.0,
    "saturation_score": 0.28, "sentiment_score": 71, "velocity_phase": "early_spike",
}
SINK = {
    "title": "Basin Sink Plug", "image_url": "http://img/3.jpg",
    "source": "cj_dropshipping", "tier": "AVOID", "final_score": 16.0, "saturation_score": 0.9,
}


def test_insert_then_read(session):
    assert cw.upsert_product(session, PLUG, "smart_home") == "new"
    session.commit()
    row = session.query(DiscoveredProduct).one()
    assert row.title == PLUG["title"]
    assert row.grade == "BUY"
    assert row.score == 82.0
    assert row.times_seen == 1


def test_saturation_normalized_to_opportunity(session):
    # 0.28 (0-1 scale) -> 28.0 saturation, 72.0 opportunity
    cw.upsert_product(session, PLUG, "smart_home")
    session.commit()
    row = session.query(DiscoveredProduct).one()
    assert row.saturation_score == 28.0
    assert row.opportunity_score == 72.0


def test_resurface_preserves_first_seen_and_bumps_proof(session):
    cw.upsert_product(session, PLUG, "smart_home")
    session.commit()
    first_seen = session.query(DiscoveredProduct).one().first_seen_at

    assert cw.upsert_product(session, PLUG, "smart_home") == "seen"
    session.commit()
    row = session.query(DiscoveredProduct).one()
    assert row.times_seen == 2
    assert row.first_seen_at == first_seen  # proof anchor never resets


def test_dedupe_by_identity_not_row_count(session):
    cw.upsert_product(session, PLUG, "smart_home")
    cw.upsert_product(session, PLUG, "smart_home")  # same product
    cw.upsert_product(session, SINK, "smart_home")  # different
    session.commit()
    assert session.query(DiscoveredProduct).count() == 2


def test_score_filter_excludes_avoid_grade(session):
    for p in (PLUG, SINK):
        cw.upsert_product(session, p, "smart_home")
    session.commit()
    buys = session.query(DiscoveredProduct).filter(DiscoveredProduct.score >= 50).all()
    titles = {r.title for r in buys}
    assert titles == {PLUG["title"]}  # AVOID-grade sink plug excluded


def test_product_key_stable_and_title_sensitive():
    assert cw._product_key(PLUG) == cw._product_key(dict(PLUG))
    assert cw._product_key(PLUG) != cw._product_key(SINK)
