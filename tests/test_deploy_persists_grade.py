"""
Deploy must persist the discovery grade onto the Product row (#54).

The public scoreboard filters `Product.grade IS NOT NULL`, so a deploy that
drops the grade leaves the scoreboard permanently empty. This pins that a
graded discovery product, once deployed, lands in the products table with
grade / discovery_score / deployed_at set.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ospra_os.database.base import Base, ProductStatus
from ospra_os.database.product_models import Product
from ospra_os.database.store_models import Store
from ospra_os.database.user_models import User
import ospra_os.database as ospra_db
from ospra_os.api import deployment_routes


@pytest.fixture()
def session_factory(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/deploy.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    s = Session()
    user = User(email="steph@oubonshop.com", name="Steph", password_hash="x")
    s.add(user)
    s.flush()
    s.add(Store(user_id=user.id, store_name="Oubon", store_url="https://oubonshop.com",
                platform="shopify", credentials={}))
    s.commit()
    uid = user.id
    s.close()

    # _record_product_deploy_outcome opens `with next(get_session()) as db:`
    class _CtxSession:
        def __init__(self):
            self._s = Session()

        def __enter__(self):
            return self._s

        def __exit__(self, *a):
            self._s.close()

    monkeypatch.setattr(ospra_db, "get_session", lambda: iter([_CtxSession()]))
    return Session, uid


@pytest.mark.asyncio
async def test_deploy_persists_grade_and_marks_deployed(session_factory):
    Session, uid = session_factory
    source_product = {
        "title": "WiFi Smart Plug",
        "grade": "A",
        "oi_score": 82,
        "price": 9.99,
        "suggested_price": 29.99,
        "ai_tags": ["smart_home"],
        "winner_source": "meta_ads",
        "winner_provenance": {"source_winner": "meta_ads", "source_winner_name": "Acme"},
        "source": "cj_dropshipping",
        "product_id": "cj-123",
    }

    await deployment_routes._record_product_deploy_outcome(
        user_id=uid,
        source_product=source_product,
        niche="smart_home",
        deploy_result={"shopify_product_id": "gid://1", "pricing": {"selling_price": 29.99}},
    )

    s = Session()
    product = s.query(Product).filter(Product.grade.isnot(None)).first()
    assert product is not None, "deployed product must carry a grade"
    assert product.grade == "A"
    assert product.discovery_score == pytest.approx(8.2)  # oi_score 82 -> 0-10 scale
    assert product.status == ProductStatus.DEPLOYED
    assert product.deployed_at is not None
    assert product.ai_tags == ["smart_home"]
    s.close()


@pytest.mark.asyncio
async def test_deploy_without_grade_still_records(session_factory):
    """A product with no grade still deploys (grade stays None) — no crash."""
    Session, uid = session_factory
    await deployment_routes._record_product_deploy_outcome(
        user_id=uid,
        source_product={"title": "Mystery Item", "price": 5, "suggested_price": 15},
        niche="smart_home",
        deploy_result={},
    )
    s = Session()
    product = s.query(Product).first()
    assert product is not None
    assert product.grade is None
    assert product.status == ProductStatus.DEPLOYED
    s.close()
