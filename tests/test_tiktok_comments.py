"""
Moat Phase 2 step 1 — TikTok comments connector + persistence (fail-if-reverted).

Parses the actor's DOCUMENTED output shape (verified 2026-07-15), fails closed
on anything else, and persists per-comment signals keyed to the product via the
shared product_identity_key.
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest

os.environ.setdefault("APIFY_API_TOKEN", "test-token-comments")

from ospra_os.product_research.connectors.apify.tiktok_comments import (
    DEFAULT_ACTOR,
    TikTokCommentsScraper,
    parse_comments,
    persist_comments,
)


def real_comment(**overrides):
    """A comment in clockworks' DOCUMENTED output shape."""
    item = {
        "text": "omg I need this for my kitchen",
        "diggCount": 246,
        "replyCommentTotal": 3,
        "createTimeISO": "2026-07-14T11:21:16.000Z",
        "uniqueId": "rizqirxq",
        "uid": "6904063862041396225",
        "cid": "7399984975553086214",
        "videoWebUrl": "https://www.tiktok.com/@shop/video/7399",
    }
    item.update(overrides)
    return item


class TestParserDocumentedShape:
    def test_real_shape_parses(self):
        result = parse_comments([real_comment()])
        assert result["status"] == "ok"
        c = result["comments"][0]
        assert c.comment_id == "7399984975553086214"
        assert c.digg_count == 246
        assert c.reply_count == 3
        assert c.author_unique_id == "rizqirxq"
        assert c.author_uid == "6904063862041396225"
        assert c.created_at == datetime(2026, 7, 14, 11, 21, 16)
        assert c.author_is_default_handle is False

    def test_default_handle_proxy_detected(self):
        """Auto-assigned userNNNN handles flag as throwaway-account proxy."""
        result = parse_comments([real_comment(uniqueId="user6904063862041396225")])
        assert result["comments"][0].author_is_default_handle is True

    def test_real_handle_is_not_default(self):
        result = parse_comments([real_comment(uniqueId="sarah.cooks")])
        assert result["comments"][0].author_is_default_handle is False

    def test_epoch_timestamp_fallback(self):
        result = parse_comments([real_comment(createTimeISO=None, createTime=1752492076)])
        assert result["comments"][0].created_at is not None


class TestParserFailsClosed:
    def test_unknown_shape_rejected(self):
        """A profile/video-shaped payload must be refused, not mis-parsed."""
        weird = [{"followerCount": 100, "nickname": "x"}, {"bio": "hi", "region": "US"}]
        result = parse_comments(weird)
        assert result["status"] == "unverified_shape"
        assert result["comments"] == []
        assert "sample_keys" in result

    def test_comment_without_id_or_text_dropped(self):
        result = parse_comments([
            real_comment(),                       # valid
            {"diggCount": 5},                     # no cid/text
        ])
        # 1/2 = 0.5 == MIN_VALID_RATIO → still ok, but only the valid one kept.
        assert result["status"] == "ok"
        assert len(result["comments"]) == 1
        assert result["invalid_count"] == 1

    def test_empty(self):
        assert parse_comments([])["status"] == "empty"


class TestScraperContract:
    def test_default_actor_and_input_schema(self):
        scraper = TikTokCommentsScraper(apify_client=object())
        assert scraper.actor_id == DEFAULT_ACTOR
        run_input = scraper.build_input(["https://www.tiktok.com/@u/video/1"])
        assert run_input["postURLs"] == ["https://www.tiktok.com/@u/video/1"]
        assert "commentsPerPost" in run_input
        assert "memory" not in run_input  # run options never leak into input

    @pytest.mark.asyncio
    async def test_fetch_caps_and_canonicalizes(self):
        captured = {}

        class FakeClient:
            async def run_actor(self, actor_id, run_input, timeout_secs=0,
                                memory_mbytes=0, max_items=None):
                captured["max_items"] = max_items
                captured["input"] = run_input
                return [real_comment(), real_comment(cid="222")]

        scraper = TikTokCommentsScraper(apify_client=FakeClient())
        scraper.comments_per_post = 50
        result = await scraper.fetch_comments(["https://www.tiktok.com/@u/video/1"])
        assert captured["max_items"] == 50   # credit cap threads through
        assert result["status"] == "ok"
        assert len(result["comments"]) == 2


class TestPersistence:
    @pytest.fixture
    def comments_db(self, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from ospra_os.database.base import Base
        from ospra_os.database.product_comments import ProductComment

        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine, tables=[ProductComment.__table__])
        factory = sessionmaker(bind=engine)
        monkeypatch.setattr(
            "ospra_os.database.connection.SessionLocal", factory, raising=False
        )
        return factory

    def test_persist_keys_by_product_identity(self, comments_db):
        from ospra_os.database.product_comments import ProductComment
        from ospra_os.database.product_timeseries import product_identity_key

        parsed = parse_comments([real_comment(), real_comment(cid="222", uniqueId="user999999999")])
        stats = persist_comments("PROD-1", parsed["comments"])
        assert stats["inserted"] == 2

        session = comments_db()
        rows = session.query(ProductComment).all()
        session.close()
        assert {r.product_key for r in rows} == {product_identity_key({"product_id": "PROD-1"})}
        assert {r.comment_id for r in rows} == {"7399984975553086214", "222"}
        assert any(r.author_is_default_handle for r in rows)

    def test_rescrape_updates_not_duplicates(self, comments_db):
        from ospra_os.database.product_comments import ProductComment

        parsed = parse_comments([real_comment(diggCount=10)])
        persist_comments("PROD-1", parsed["comments"])
        parsed2 = parse_comments([real_comment(diggCount=99)])
        stats = persist_comments("PROD-1", parsed2["comments"])
        assert stats["updated"] == 1

        session = comments_db()
        rows = session.query(ProductComment).all()
        session.close()
        assert len(rows) == 1
        assert rows[0].digg_count == 99
