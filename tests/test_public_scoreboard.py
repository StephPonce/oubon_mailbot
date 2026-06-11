"""
Tests for the public scoreboard endpoint (task #52).

Seeds a temp sqlite DB with graded products + first-sale learning events and
verifies the anonymization + win-rate aggregation in _build_scoreboard.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ospra_os.database.base import Base, ProductStatus
from ospra_os.database.product_models import Product
from ospra_os.database.performance_models import AILearningEvent
from ospra_os.database.store_models import Store
from ospra_os.database.user_models import User
from ospra_os.api import public_routes


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/scoreboard.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    user = User(email="steph@oubonshop.com", name="Steph", password_hash="x")
    session.add(user)
    session.flush()

    store = Store(
        user_id=user.id,
        store_name="Oubon",
        store_url="https://oubonshop.com",
        platform="shopify",
        credentials={},
    )
    session.add(store)
    session.flush()

    def make_product(name, grade, deployed, sales, revenue, tags=None):
        return Product(
            store_id=store.id,
            product_name=name,
            grade=grade,
            discovery_score=8.2,
            ai_tags=tags or ["smart-home"],
            status=ProductStatus.DEPLOYED if deployed else ProductStatus.DISCOVERED,
            deployed_at=datetime(2026, 6, 1) if deployed else None,
            total_sales=sales,
            total_revenue=revenue,
            source_url="https://supplier.example/SECRET",  # must never leak
        )

    products = [
        make_product("Smart Plug A", "A+", True, 12, 240.0),   # BUY, sold
        make_product("Wifi Cam B", "A", True, 0, 0.0),         # BUY, no sales
        make_product("LED Strip C", "B+", True, 3, 45.0),      # BUY, sold
        make_product("Gadget D", "F", False, 0, 0.0),          # AVOID, never deployed
        make_product("Gizmo E", "D", True, 0, 0.0),            # AVOID, deployed, no sales
        make_product("Pending F", "A", False, 0, 0.0),         # BUY but not deployed
    ]
    session.add_all(products)
    session.flush()

    # first-sale events: product A sold on day 3, product C on day 20
    session.add_all([
        AILearningEvent(
            user_id=user.id,
            event_type="first_sale",
            details={"product_id": str(products[0].id), "days_to_first_sale": 3},
        ),
        AILearningEvent(
            user_id=user.id,
            event_type="first_sale",
            details={"product_id": str(products[2].id), "days_to_first_sale": 20},
        ),
        # different event type — must be ignored
        AILearningEvent(
            user_id=user.id,
            event_type="30_day_performance",
            details={"product_id": str(products[1].id), "days_to_first_sale": 1},
        ),
    ])
    session.commit()

    def fake_get_db():
        yield Session()

    monkeypatch.setattr("ospra_os.auth.jwt_auth.get_db", fake_get_db)
    monkeypatch.setenv("SCOREBOARD_USER_ID", str(user.id))
    # reset the module cache between tests
    public_routes._cache["payload"] = None
    public_routes._cache["expires_at"] = 0.0

    yield session
    session.close()


def test_scoreboard_aggregates(seeded_db):
    payload = public_routes._build_scoreboard()
    stats = payload["stats"]

    assert stats["total_graded"] == 6
    # BUY deployed: A+, A, B+ (3); with sales: A+ and B+ (2)
    assert stats["buy_graded_deployed"] == 3
    assert stats["buy_with_sales"] == 2
    assert stats["buy_win_rate"] == pytest.approx(2 / 3, abs=0.001)
    # AVOID: F + D
    assert stats["avoid_graded"] == 2
    assert stats["avoid_with_sales"] == 0
    # first-sale: days 3 and 20 -> median 20 (upper of two), within-14 = 1
    assert stats["first_sale_sample_size"] == 2
    assert stats["sold_within_14_days"] == 1


def test_scoreboard_anonymization(seeded_db):
    payload = public_routes._build_scoreboard()
    import json
    raw = json.dumps(payload)
    # no supplier/source URLs, store URLs, or emails may leak
    assert "SECRET" not in raw
    assert "supplier.example" not in raw
    assert "oubonshop.com" not in raw.replace("Oubon Shop", "")
    assert "@" not in raw

    pick = payload["picks"][0]
    assert set(pick.keys()) == {
        "title", "niche", "grade", "score", "graded_at",
        "deployed", "units_sold", "revenue_direction", "days_to_first_sale",
    }


def test_scoreboard_undeployed_products_hide_outcomes(seeded_db):
    payload = public_routes._build_scoreboard()
    undeployed = [p for p in payload["picks"] if not p["deployed"]]
    assert undeployed, "expected at least one undeployed pick"
    for pick in undeployed:
        assert pick["units_sold"] is None
        assert pick["revenue_direction"] is None
