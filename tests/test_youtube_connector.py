"""
Tests for the YouTube Data API v3 connector — Phase I.

These tests don't hit the real API. They exercise the connector's
input validation, error envelopes, and response-parsing logic by
mocking httpx so failures are deterministic.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from ospra_os.product_research.connectors.social.youtube import (
    YouTubeReviewsConnector,
)


def _run(coro):
    # asyncio.run() creates and tears down a fresh event loop each call, so it
    # is immune to a prior test (e.g. a TestClient lifespan) leaving the thread
    # with no current loop — get_event_loop() raised "no current event loop" on
    # 3.12 when that happened, making these tests order-dependent flaky.
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Availability / argument validation
# ---------------------------------------------------------------------------

def test_is_available_requires_api_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    c = YouTubeReviewsConnector(api_key=None)
    assert c.is_available() is False


def test_is_available_true_when_key_present():
    c = YouTubeReviewsConnector(api_key="AIza-test-key")
    assert c.is_available() is True


def test_returns_unavailable_when_no_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    c = YouTubeReviewsConnector(api_key=None)
    result = _run(c.get_product_reviews("smart plug"))
    assert result["available"] is False
    assert "YOUTUBE_API_KEY" in (result.get("error") or "")


def test_returns_unavailable_for_empty_product():
    c = YouTubeReviewsConnector(api_key="AIza-test-key")
    result = _run(c.get_product_reviews(""))
    assert result["available"] is False
    assert "empty" in (result.get("error") or "")


# ---------------------------------------------------------------------------
# Error handling: HTTP failures + timeouts
# ---------------------------------------------------------------------------

def _make_mock_resp(status_code: int, json_data: dict | None = None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def test_search_http_error_returns_error_envelope():
    c = YouTubeReviewsConnector(api_key="AIza-test")

    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_make_mock_resp(403, text="quota"))

        result = _run(c.get_product_reviews("smart plug"))
        assert result["available"] is False
        assert "403" in (result.get("error") or "")


def test_no_videos_returns_zero_count():
    c = YouTubeReviewsConnector(api_key="AIza-test")

    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_make_mock_resp(200, {"items": []}))

        result = _run(c.get_product_reviews("smart plug"))
        assert result["available"] is False
        assert result.get("review_video_count") == 0


# ---------------------------------------------------------------------------
# Happy path: parse search + stats + comments into the documented shape
# ---------------------------------------------------------------------------

def test_happy_path_parses_videos_and_comments():
    c = YouTubeReviewsConnector(api_key="AIza-test")

    search_payload = {
        "items": [
            {
                "id": {"videoId": "vid1"},
                "snippet": {
                    "title": "Smart Plug Review — Worth It?",
                    "channelTitle": "TechReviewer",
                    "publishedAt": "2026-01-15T00:00:00Z",
                },
            },
            {
                "id": {"videoId": "vid2"},
                "snippet": {
                    "title": "Smart Plug Honest Take",
                    "channelTitle": "ChannelTwo",
                    "publishedAt": "2026-02-01T00:00:00Z",
                },
            },
        ]
    }
    stats_payload = {
        "items": [
            {
                "id": "vid1",
                "statistics": {
                    "viewCount": "120000",
                    "likeCount": "5400",
                    "commentCount": "320",
                },
            },
            {
                "id": "vid2",
                "statistics": {
                    "viewCount": "45000",
                    "likeCount": "1800",
                    "commentCount": "90",
                },
            },
        ]
    }
    comments_payload = {
        "items": [
            {
                "snippet": {
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": "Worked great for me — easy to set up.",
                            "authorDisplayName": "BuyerOne",
                            "likeCount": "42",
                        }
                    }
                }
            },
            {
                "snippet": {
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": "Wifi kept dropping after a week.",
                            "authorDisplayName": "BuyerTwo",
                            "likeCount": "11",
                        }
                    }
                }
            },
        ]
    }

    # The connector calls search → videos → commentThreads × N. Use a
    # side_effect list to feed each call its right response in order.
    responses = [
        _make_mock_resp(200, search_payload),  # search.list
        _make_mock_resp(200, stats_payload),   # videos.list
        _make_mock_resp(200, comments_payload),  # commentThreads vid1
        _make_mock_resp(200, comments_payload),  # commentThreads vid2
    ]

    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=responses)

        result = _run(c.get_product_reviews("smart plug", max_videos=2))

    assert result["available"] is True
    assert result["review_video_count"] == 2
    assert result["total_views"] == 165000  # 120k + 45k
    assert result["total_likes"] == 7200    # 5.4k + 1.8k
    assert result["total_comments"] == 410  # 320 + 90

    # Top videos preserved
    titles = [v["title"] for v in result["top_videos"]]
    assert "Smart Plug Review — Worth It?" in titles

    # Comments collected with capped text + linked back to videos
    assert len(result["top_comments"]) >= 2
    sample = result["top_comments"][0]
    assert "text" in sample
    assert "author" in sample
    assert "likes" in sample
    assert "video_title" in sample
    assert "video_id" in sample


def test_disabled_comments_dont_crash():
    """If comment fetch fails (comments disabled per-video, etc.) we still
    return videos."""
    c = YouTubeReviewsConnector(api_key="AIza-test")

    search_payload = {
        "items": [
            {
                "id": {"videoId": "vid1"},
                "snippet": {"title": "T", "channelTitle": "C", "publishedAt": ""},
            }
        ]
    }
    stats_payload = {
        "items": [
            {"id": "vid1", "statistics": {"viewCount": "100", "likeCount": "5", "commentCount": "0"}}
        ]
    }

    responses = [
        _make_mock_resp(200, search_payload),
        _make_mock_resp(200, stats_payload),
        _make_mock_resp(403, {}, text="commentsDisabled"),  # comments fetch fails
    ]

    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=responses)

        result = _run(c.get_product_reviews("widget", max_videos=1))

    assert result["available"] is True
    assert result["review_video_count"] == 1
    assert result["top_comments"] == []  # fallback safe
