"""
Moat Phase 2 step 4 — seeded demand grades LOWER at equal units-sold
(fail-if-reverted). THE moat, proven end-to-end.

Two products with IDENTICAL units-sold history but different comment
authenticity — one seeded (templated text, throwaway handles, one burst), one
organic (diverse voices spread over time) — scored by the REAL _calculate_scores
with the authenticity gate ON. The seeded product must grade lower. Because the
two products are identical in every other field and share the same units-sold
snapshots, the score delta isolates the organic-vs-seeded verdict.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-seeded-grade")
os.environ["DISCOVERY_UNITS_VELOCITY_ENABLED"] = "true"

from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine


@pytest.fixture
def moat_db(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from ospra_os.database.base import Base
    from ospra_os.database.product_timeseries import ProductTimeseries, product_identity_key
    from ospra_os.database.product_comments import ProductComment

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        engine, tables=[ProductTimeseries.__table__, ProductComment.__table__]
    )
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        "ospra_os.database.connection.SessionLocal", factory, raising=False
    )
    # Authenticity gate ON for this test (imported into the discovery namespace).
    monkeypatch.setattr(
        "ospra_os.intelligence.product_discovery.AUTHENTICITY_ENABLED", True, raising=False
    )

    def seed_units(product_id, series=(1000, 1050, 1100)):
        key = product_identity_key({"product_id": str(product_id)})
        today = datetime.utcnow().date()
        n = len(series)
        s = factory()
        for i, sold in enumerate(series):
            s.add(ProductTimeseries(
                product_key=key, snapshot_date=today - timedelta(days=n - 1 - i),
                tiktok_units_sold=sold, signal_count=1,
            ))
        s.commit(); s.close()

    def seed_comments(product_id, comments):
        key = product_identity_key({"product_id": str(product_id)})
        s = factory()
        for i, c in enumerate(comments):
            s.add(ProductComment(
                product_key=key, tiktok_product_id=str(product_id),
                comment_id=f"{product_id}-{i}",
                text=c["text"], digg_count=c.get("digg", 1),
                created_at=c["created_at"],
                author_unique_id=c["handle"], author_uid=c["uid"],
                author_is_default_handle=c["default_handle"],
            ))
        s.commit(); s.close()

    return seed_units, seed_comments


def organic_comment_rows(n=20):
    base = datetime(2026, 7, 1, 12, 0, 0)
    texts = ["ordered one", "needed this", "worth it?", "love mine", "reviews sold me",
             "other colors?", "use it daily", "beats the dupe", "mom wants one", "actually works"]
    return [{
        "text": texts[i % len(texts)] + f" {i}", "handle": f"sarah.cooks{i}",
        "uid": f"real_{i}", "default_handle": False,
        "created_at": base + timedelta(hours=i * 6),
    } for i in range(n)]


def seeded_comment_rows(n=20):
    burst = datetime(2026, 7, 1, 12, 0, 0)
    return [{
        "text": "🔥 BUY NOW link in bio best product 🔥",
        "handle": f"user{9000000000 + (i % 3)}", "uid": f"acct_{i % 3}",
        "default_handle": True, "created_at": burst + timedelta(seconds=i * 20),
    } for i in range(n)]


def _engine():
    eng = ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)
    eng._winner_index_cached = None
    eng._get_learned_signal_weights = lambda: {}
    eng._get_learned_niche_adjustment = lambda niche: 0.0
    eng._extract_meta_winner_index = lambda: {}
    eng._match_product_to_meta_winners = lambda *a, **k: (0, None)
    eng._calculate_relevance = lambda *a, **k: 100
    return eng


def _product(product_id):
    return {
        "title": "Magnetic Phone Mount for Car Vent",
        "product_id": str(product_id),
        "price": 24.99, "cost": 6.0, "profit_margin": 62.0,
        "sourcing_score": 60, "relevance_score": 100,
        "niche": "tech", "data_sources": {},
    }


class TestSeededGradesLower:
    def test_seeded_product_grades_lower_than_organic(self, moat_db):
        seed_units, seed_comments = moat_db
        # IDENTICAL units-sold for both.
        seed_units("SEEDED"); seed_units("ORGANIC")
        # Only the comments differ.
        seed_comments("SEEDED", seeded_comment_rows())
        seed_comments("ORGANIC", organic_comment_rows())

        eng = _engine()
        seeded = eng._calculate_scores([_product("SEEDED")], category_niche="tech")[0]
        organic = eng._calculate_scores([_product("ORGANIC")], category_niche="tech")[0]

        # THE moat: seeded hype loses grade against organic pull at equal sales.
        assert seeded["oi_score"] < organic["oi_score"], (
            f"seeded {seeded['oi_score']} !< organic {organic['oi_score']}"
        )
        # Seeded is explicitly flagged manufactured; organic is not demoted.
        assert seeded.get("authenticity_label") == "manufactured"
        assert seeded.get("authenticity_divergence") is True
        assert organic.get("authenticity_label") in ("organic", "corroborated", "unproven")

    def test_equal_units_boost_isolates_the_comment_effect(self, moat_db):
        """Both products get the SAME units-velocity boost, so the delta is
        purely the authenticity verdict — not a units artifact."""
        seed_units, seed_comments = moat_db
        seed_units("SEEDED"); seed_units("ORGANIC")
        seed_comments("SEEDED", seeded_comment_rows())
        seed_comments("ORGANIC", organic_comment_rows())

        eng = _engine()
        seeded = eng._calculate_scores([_product("SEEDED")], category_niche="tech")[0]
        organic = eng._calculate_scores([_product("ORGANIC")], category_niche="tech")[0]

        assert seeded.get("units_velocity_boost") == organic.get("units_velocity_boost")
        assert seeded.get("units_sold_velocity_7d") == organic.get("units_sold_velocity_7d")

    def test_no_comments_no_authenticity_demote(self, moat_db):
        """A product with sales but no comment data isn't demoted by this layer
        (absence of evidence is not evidence of fakeness)."""
        seed_units, _ = moat_db
        seed_units("NOCOMMENTS")

        eng = _engine()
        p = eng._calculate_scores([_product("NOCOMMENTS")], category_niche="tech")[0]
        # No comment authenticity → label is not 'manufactured'.
        assert p.get("authenticity_label") != "manufactured"
