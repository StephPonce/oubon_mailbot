"""
Moat Phase 3 step 1 — store-carry detector (fail-if-reverted).

Catalog fixtures mirror the REAL public products.json shape captured live
2026-07-15 from oubonshop.com (fields: id, title, handle, body_html, images
[].src, variants[].price — see store_carry.py docstring). Live behavior also
verified against colourpop.com (250-item catalog, no false match) and
gymshark.com / example.com (403/404 → unknown, never zero).
"""

from __future__ import annotations

import pytest

from ospra_os.intelligence.store_carry import (
    best_catalog_match,
    candidate_store_urls,
    clear_catalog_cache,
    extract_tiktok_video_urls,
    fetch_store_catalog,
    product_store_carry,
    _title_similarity,
)

# Real shape: subset of a live oubonshop.com products.json response.
OUBON_STYLE_CATALOG = [
    {
        "title": "A3 LED Light Pad - 3-Level Dimmable Drawing Board",
        "handle": "a3-led-light-pad-3-level-dimmable-drawing-board",
        "body_html": "<h3>Illuminate Your Creativity</h3><p>as seen on "
                     "https://www.tiktok.com/@artist/video/7301234567890123456 !</p>",
        "image": "https://cdn.shopify.com/s/files/1/0693/x.jpg",
        "price": "64.38",
    },
    {
        "title": "Mini Portable Blender Bottle",
        "handle": "mini-portable-blender",
        "body_html": "",
        "image": None,
        "price": "19.99",
    },
]

UNRELATED_CATALOG = [
    {"title": "Balm Besties", "handle": "balm-besties", "body_html": "", "image": None, "price": "24.00"},
    {"title": "Lippie Stix Set", "handle": "lippie-stix", "body_html": "", "image": None, "price": "8.50"},
]

PRODUCT = {"title": "A3 LED Light Pad Dimmable Drawing Board", "product_id": "tk1"}


def fake_fetch_factory(mapping):
    def fetch(store_url):
        return mapping.get(store_url)
    return fetch


class TestStoreCarry:
    def test_carry_counts_distinct_matching_stores(self):
        fetch = fake_fetch_factory({
            "https://storea.com": OUBON_STYLE_CATALOG,
            "https://storeb.com": OUBON_STYLE_CATALOG,
            "https://storec.com": UNRELATED_CATALOG,
        })
        res = product_store_carry(
            PRODUCT, ["https://storea.com", "https://storeb.com", "https://storec.com"],
            fetch=fetch,
        )
        assert res["store_carry_count"] == 2
        assert res["stores_checked"] == 3
        assert {m["store"] for m in res["carried_by"]} == {"https://storea.com", "https://storeb.com"}
        # step 3 linkage: video URL extracted from the MATCHED product's body_html
        assert res["tiktok_video_urls"] == [
            "https://www.tiktok.com/@artist/video/7301234567890123456"
        ]

    def test_unreachable_stores_never_count_as_not_carrying(self):
        fetch = fake_fetch_factory({
            "https://dead1.com": None,
            "https://alive.com": UNRELATED_CATALOG,
        })
        res = product_store_carry(PRODUCT, ["https://dead1.com", "https://alive.com"], fetch=fetch)
        assert res["store_carry_count"] == 0          # one real catalog checked, no match
        assert res["stores_unreachable"] == 1

    def test_all_unreachable_is_unknown_not_zero(self):
        """THE invariant: no readable catalog → None (unknown), never 0."""
        fetch = fake_fetch_factory({})  # everything → None
        res = product_store_carry(PRODUCT, ["https://dead1.com", "https://dead2.com"], fetch=fetch)
        assert res["store_carry_count"] is None
        assert res["stores_checked"] == 0

    def test_candidate_urls_dedupe_and_denylist(self):
        product = {
            "winner_provenance": {"sample_url": "https://coolgadgets.com/products/led?utm=x"},
            "sample_landing_urls": [
                "https://coolgadgets.com/pages/about",   # same domain → dedup
                "https://shopx.io/products/abc",
                "https://www.aliexpress.com/item/1.html",  # marketplace → excluded
                "https://www.tiktok.com/@x/video/1",       # platform → excluded
            ],
        }
        assert candidate_store_urls(product) == ["https://coolgadgets.com", "https://shopx.io"]

    def test_title_similarity_verbose_vs_short_dropship_titles(self):
        # Live-observed pair: 0.886 — must clear the 0.60 threshold
        assert _title_similarity(
            "A3 LED Light Pad Dimmable Drawing Board",
            "A3 LED Light Pad - 3-Level Dimmable Drawing Board",
        ) > 0.6
        assert _title_similarity("A3 LED Light Pad", "Balm Besties") < 0.3

    def test_best_catalog_match_shape(self):
        best = best_catalog_match(PRODUCT["title"], OUBON_STYLE_CATALOG)
        assert best["handle"] == "a3-led-light-pad-3-level-dimmable-drawing-board"
        assert best["similarity"] > 0.8


class TestVideoExtraction:
    def test_extracts_canonical_and_short_links_deduped(self):
        html = (
            'x https://www.tiktok.com/@user1/video/7301234567890123456 y '
            '<a href="https://vm.tiktok.com/ZMabcdef/">clip</a> '
            'https://www.tiktok.com/@user1/video/7301234567890123456 again'
        )
        assert extract_tiktok_video_urls(html) == [
            "https://www.tiktok.com/@user1/video/7301234567890123456",
            "https://vm.tiktok.com/ZMabcdef",
        ]

    def test_empty_and_plain_html(self):
        assert extract_tiktok_video_urls("") == []
        assert extract_tiktok_video_urls("<p>no videos here</p>") == []


class TestCatalogFetchParsing:
    def test_non_json_and_http_error_return_none(self, monkeypatch):
        clear_catalog_cache()

        class FakeResp:
            status_code = 200
            def json(self):
                raise ValueError("not json")

        import requests
        monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp())
        assert fetch_store_catalog("https://htmlsite.com") is None

        clear_catalog_cache()
        FakeResp.status_code = 403
        assert fetch_store_catalog("https://blocked.com") is None

    def test_real_shape_parsed_and_result_cached(self, monkeypatch):
        clear_catalog_cache()
        calls = {"n": 0}

        class FakeResp:
            status_code = 200
            def json(self):
                calls["n"] += 1
                return {"products": [{
                    "id": 7787443781710,
                    "title": "A3 LED Light Pad - 3-Level Dimmable Drawing Board",
                    "handle": "a3-led-light-pad",
                    "body_html": "<p>x</p>",
                    "images": [{"src": "https://cdn.shopify.com/x.jpg", "width": 800}],
                    "variants": [{"price": "64.38", "sku": ""}],
                }]}

        import requests
        monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp())
        cat = fetch_store_catalog("https://mystore.com")
        assert cat == [{
            "title": "A3 LED Light Pad - 3-Level Dimmable Drawing Board",
            "handle": "a3-led-light-pad",
            "body_html": "<p>x</p>",
            "image": "https://cdn.shopify.com/x.jpg",
            "price": "64.38",
        }]
        # second call served from the one-run cache (rate-limit protection)
        fetch_store_catalog("https://mystore.com")
        assert calls["n"] == 1
        clear_catalog_cache()


class TestPersistence:
    @pytest.fixture
    def timeseries_session(self, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from ospra_os.database.base import Base
        from ospra_os.database.product_timeseries import ProductTimeseries

        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine, tables=[ProductTimeseries.__table__])
        factory = sessionmaker(bind=engine)
        monkeypatch.setattr(
            "ospra_os.database.connection.SessionLocal", factory, raising=False
        )
        return factory

    def test_persist_and_load_roundtrip(self, timeseries_session):
        from ospra_os.intelligence.store_carry import (
            load_store_carry_for_product, persist_store_carry,
        )
        product = {"title": "A3 LED Light Pad", "product_id": "tk9"}
        assert persist_store_carry(product, 3) is True
        assert load_store_carry_for_product(product) == 3
        # upsert, not duplicate
        assert persist_store_carry(product, 5) is True
        assert load_store_carry_for_product(product) == 5

    def test_unknown_is_never_persisted(self, timeseries_session):
        from ospra_os.intelligence.store_carry import (
            load_store_carry_for_product, persist_store_carry,
        )
        product = {"title": "X", "product_id": "tk10"}
        assert persist_store_carry(product, None) is False
        assert load_store_carry_for_product(product) is None
