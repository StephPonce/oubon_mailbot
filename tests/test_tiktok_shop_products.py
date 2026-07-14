"""
Phase 1 step 2 — TikTok Shop product connector (fail-if-reverted).

The canonicalizer parses the actors' DOCUMENTED shapes and FAILS CLOSED on
anything else (never fabricates products) — that posture is load-bearing while
LIVE verification is blocked by the Apify usage cap.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("APIFY_API_TOKEN", "test-token-tts")

from ospra_os.product_research.connectors.apify.tiktok_shop_products import (
    DEFAULT_ACTOR,
    TikTokShopProductsScraper,
    parse_items,
)


def trakk_item(**overrides):
    """An item in trakk's DOCUMENTED output shape."""
    item = {
        "productId": "1729382546789",
        "title": "Portable Blender Bottle",
        "productUrl": "https://www.tiktok.com/shop/pdp/1729382546789",
        "currentPrice": 19.99,
        "originalPrice": 39.99,
        "currency": "USD",
        "soldCount": 5400,
        "soldText": "5.4k sold",
        "rating": 4.7,
        "reviewCount": 321,
        "shopName": "BlendCo Official",
    }
    item.update(overrides)
    return item


class TestParserDocumentedShapes:
    def test_trakk_shape_parses(self):
        result = parse_items([trakk_item()])
        assert result["status"] == "ok"
        p = result["products"][0]
        assert p.tiktok_product_id == "1729382546789"
        assert p.sold_count == 5400
        assert p.price == 19.99
        assert p.rating == 4.7
        assert p.review_count == 321
        assert p.shop_name == "BlendCo Official"

    def test_pro100chok_style_fields_parse(self):
        """Fallback actor's documented sold field (salesVolume)."""
        result = parse_items([{
            "product_id": "999", "name": "Hair Dryer Brush",
            "salesVolume": 12000, "price": "$24.99",
        }])
        assert result["status"] == "ok"
        p = result["products"][0]
        assert p.sold_count == 12000
        assert p.price == 24.99

    def test_sold_text_kilo_notation(self):
        """soldText-only items ('12.3k sold') parse to integers."""
        result = parse_items([trakk_item(soldCount=None, soldText="12.3k sold")])
        assert result["status"] == "ok"
        assert result["products"][0].sold_count == 12300

    def test_zero_sold_is_valid_not_missing(self):
        """0 units is a real observation — distinguishable from absent."""
        result = parse_items([trakk_item(soldCount=0)])
        assert result["status"] == "ok"
        assert result["products"][0].sold_count == 0


class TestParserFailsClosed:
    def test_unknown_shape_is_rejected_not_fabricated(self):
        """A video-actor-like payload (the old default's shape) must be
        refused wholesale — no products invented from wrong fields."""
        video_items = [
            {"id": "v1", "text": "check this gadget", "playCount": 100000, "diggCount": 5000},
            {"id": "v2", "text": "viral thing", "playCount": 90000, "diggCount": 4000},
        ]
        result = parse_items(video_items)
        assert result["status"] == "unverified_shape"
        assert result["products"] == []
        assert "sample_keys" in result

    def test_items_without_sold_count_do_not_default_to_zero(self):
        """Missing sold data must NOT become sold_count=0 (fabrication)."""
        result = parse_items([
            {"productId": "1", "title": "Thing A"},  # no sold fields at all
        ])
        assert result["status"] == "unverified_shape"
        assert result["products"] == []

    def test_mixed_batch_above_threshold_keeps_valid_only(self):
        items = [trakk_item(), trakk_item(productId="2"), {"garbage": True}]
        result = parse_items(items)
        assert result["status"] == "ok"
        assert len(result["products"]) == 2
        assert result["invalid_count"] == 1

    def test_empty_batch(self):
        assert parse_items([])["status"] == "empty"


class TestScraperContract:
    def test_default_actor_is_the_product_actor(self, monkeypatch):
        """The video actor (clockworks) is retired as the TikTok Shop source."""
        monkeypatch.delenv("APIFY_TIKTOK_SHOP_ACTOR", raising=False)
        scraper = TikTokShopProductsScraper(apify_client=object())
        assert scraper.actor_id == DEFAULT_ACTOR
        assert "clockworks" not in scraper.actor_id

    def test_build_input_matches_documented_schema(self):
        scraper = TikTokShopProductsScraper(apify_client=object())
        run_input = scraper.build_input(["water bottle"], 40)
        # Pinned to trakk's documented input contract.
        assert run_input["country_code"] == "US"
        assert run_input["keywords"] == ["water bottle"]
        assert run_input["maxItems"] == 40
        assert run_input["sortBy"] == "best_sellers"
        assert "memory" not in run_input  # run options never leak into input

    @pytest.mark.asyncio
    async def test_fetch_products_caps_items_and_canonicalizes(self, monkeypatch):
        captured = {}

        class FakeClient:
            async def run_actor(self, actor_id, run_input, timeout_secs=0,
                                memory_mbytes=0, max_items=None):
                captured["actor_id"] = actor_id
                captured["max_items"] = max_items
                captured["run_input"] = run_input
                return [trakk_item()]

        scraper = TikTokShopProductsScraper(apify_client=FakeClient())
        result = await scraper.fetch_products(["kitchen"], max_items=20)

        assert captured["max_items"] == 20          # credit cap threads through
        assert captured["run_input"]["maxItems"] == 20
        assert result["status"] == "ok"
        assert result["products"][0].sold_count == 5400
        assert result["actor_id"] == scraper.actor_id
