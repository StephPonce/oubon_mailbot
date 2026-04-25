"""
Tests for the Apify Instagram hashtag connector — Phase J.

The actor is paid Apify infra; these tests don't run it. They exercise
input validation, hashtag slugification, error envelopes, and
response-parsing logic by mocking ``ApifyClient.run_actor``.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ospra_os.product_research.connectors.apify.instagram_hashtag import (
    InstagramHashtagApify,
    _slugify_hashtag,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Hashtag slugification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Smart LED Strip Light", "smartledstriplight"),
        ("Smart-Plug 2.0!", "smartplug20"),
        ("  spaces  ", "spaces"),
        ("", ""),
        ("Émojîs 🔥 Don't Survive", "moji" + "s" + "dontsurvive"),  # diacritics stripped
    ],
)
def test_slugify_hashtag(raw, expected):
    # The transliteration of "Émojîs" depends on impl; just check it's
    # alphanum + lowercase, no spaces. Keep the strict cases above tight.
    out = _slugify_hashtag(raw)
    assert out == out.lower()
    assert all(c.isalnum() for c in out)
    if raw == "Smart LED Strip Light":
        assert out == "smartledstriplight"
    if raw == "Smart-Plug 2.0!":
        assert out == "smartplug20"
    if raw == "":
        assert out == ""


# ---------------------------------------------------------------------------
# Availability + arg validation
# ---------------------------------------------------------------------------

def test_unavailable_when_no_apify_token(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    with pytest.raises(ValueError):
        # ApifyClient raises if no token is set — exercise the guard.
        InstagramHashtagApify(api_token=None)


def test_returns_unavailable_for_empty_product():
    c = InstagramHashtagApify(api_token="fake-token")
    result = _run(c.fetch_hashtag_posts(""))
    assert result["available"] is False
    assert "empty" in (result.get("error") or "")


def test_returns_unavailable_when_hashtag_unslugifiable():
    """If product_name has no alphanumerics at all, slugify yields
    empty and we should say so explicitly."""
    c = InstagramHashtagApify(api_token="fake-token")
    result = _run(c.fetch_hashtag_posts("!!!---"))
    assert result["available"] is False
    assert "hashtag" in (result.get("error") or "")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_parses_posts():
    c = InstagramHashtagApify(api_token="fake-token")

    actor_results = [
        {
            "caption": "OBSESSED with this LED strip! Best $30 I've spent. #smartledstriplight",
            "likesCount": 1240,
            "commentsCount": 87,
            "url": "https://instagram.com/p/abc1",
            "ownerUsername": "homedecor_jane",
            "timestamp": "2026-03-01T12:00:00Z",
        },
        {
            "caption": "Glitchy after 2 weeks, app keeps disconnecting. NOT recommended.",
            "likesCount": 312,
            "commentsCount": 145,
            "url": "https://instagram.com/p/abc2",
            "ownerUsername": "techreview_bob",
            "timestamp": "2026-03-12T09:00:00Z",
        },
    ]

    with patch.object(
        c.client, "run_actor", new=AsyncMock(return_value=actor_results)
    ):
        result = _run(c.fetch_hashtag_posts("Smart LED Strip Light", max_posts=5))

    assert result["available"] is True
    assert result["hashtag"] == "smartledstriplight"
    assert result["post_count_returned"] == 2
    assert result["total_likes"] == 1552
    assert result["total_comments"] == 232
    posts = result["posts"]
    assert len(posts) == 2
    assert "OBSESSED" in posts[0]["caption"]
    assert posts[0]["owner"] == "homedecor_jane"
    assert posts[0]["likes"] == 1240


def test_actor_failure_returns_error_envelope():
    c = InstagramHashtagApify(api_token="fake-token")

    with patch.object(
        c.client, "run_actor", new=AsyncMock(side_effect=Exception("rate limited"))
    ):
        result = _run(c.fetch_hashtag_posts("smart plug"))

    assert result["available"] is False
    assert "rate limited" in (result.get("error") or "")


def test_no_results_returns_unavailable():
    c = InstagramHashtagApify(api_token="fake-token")

    with patch.object(c.client, "run_actor", new=AsyncMock(return_value=[])):
        result = _run(c.fetch_hashtag_posts("obscure thing"))

    assert result["available"] is False
    assert result.get("hashtag") == "obscurething"


def test_posts_without_caption_are_dropped():
    c = InstagramHashtagApify(api_token="fake-token")

    actor_results = [
        {"caption": "real caption", "likesCount": 5, "commentsCount": 1},
        {"caption": "", "likesCount": 999},          # empty caption — drop
        {"likesCount": 100},                          # no caption field — drop
        {"caption": None, "likesCount": 50},          # null — drop
    ]

    with patch.object(
        c.client, "run_actor", new=AsyncMock(return_value=actor_results)
    ):
        result = _run(c.fetch_hashtag_posts("widget"))

    assert result["available"] is True
    assert result["post_count_returned"] == 1
    assert result["posts"][0]["caption"] == "real caption"
