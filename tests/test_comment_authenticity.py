"""
Moat Phase 2 step 2 — seeded-vs-organic classifier (fail-if-reverted).

Proves the classifier separates coordinated-fake engagement from organic, and
that its verdict flows through the EXISTING demote-only authenticity framework
(signals_from_product → compute_authenticity) to punish seeded demand.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-comment-auth")

from ospra_os.intelligence.comment_authenticity import (
    MIN_COMMENTS, classify_comments,
)
from ospra_os.intelligence.demand_authenticity import (
    compute_authenticity, signals_from_product,
)


def organic_comments(n=20):
    """Diverse authors, varied text, spread over the video's life."""
    base = datetime(2026, 7, 1, 12, 0, 0)
    texts = [
        "just ordered one, can't wait", "my kitchen needed this so bad",
        "is it worth the price though?", "got mine last week, love it",
        "the reviews sold me honestly", "does it come in other colors",
        "using it every morning now", "way better than the amazon dupe",
        "my mom wants one too lol", "finally something that actually works",
    ]
    return [
        {
            "text": texts[i % len(texts)] + f" ({i})",
            "author_uid": f"real_user_{i}",
            "author_unique_id": f"sarah.cooks{i}",
            "author_is_default_handle": False,
            "created_at": base + timedelta(hours=i * 6),  # spread over days
        }
        for i in range(n)
    ]


def seeded_comments(n=20):
    """Templated text, throwaway handles, few accounts, one tight burst."""
    burst = datetime(2026, 7, 1, 12, 0, 0)
    template = "🔥🔥 BUY NOW link in bio best product 2026 🔥🔥"
    return [
        {
            "text": template,                                  # identical text
            "author_uid": f"acct_{i % 3}",                     # only 3 accounts
            "author_unique_id": f"user{9000000000 + (i % 3)}", # default handles
            "author_is_default_handle": True,
            "created_at": burst + timedelta(seconds=i * 20),   # all within minutes
        }
        for i in range(n)
    ]


class TestClassifierSeparatesSeededFromOrganic:
    def test_organic_scores_low_seeded(self):
        ca = classify_comments(organic_comments())
        assert ca is not None
        assert ca.seeded_score < 0.3
        assert ca.organic_score > 0.7
        assert ca.duplicate_text_ratio < 0.2
        assert ca.default_handle_share == 0.0

    def test_seeded_scores_high_seeded(self):
        ca = classify_comments(seeded_comments())
        assert ca is not None
        assert ca.seeded_score > 0.6
        assert ca.duplicate_text_ratio > 0.8      # all templated
        assert ca.author_concentration > 0.7      # 3 accounts / 20 comments
        assert ca.default_handle_share == 1.0
        assert ca.burst_concentration > 0.9       # all in one window

    def test_thin_comment_set_returns_none(self):
        """Below MIN_COMMENTS → no verdict (too thin to judge)."""
        assert classify_comments(seeded_comments(n=MIN_COMMENTS - 1)) is None

    def test_near_duplicate_text_detected(self):
        """Templated text with emoji/whitespace variation still collapses."""
        variants = [
            {"text": "🔥 NEED this!!!", "author_uid": f"u{i}", "created_at": None}
            for i in range(10)
        ] + [
            {"text": "need this 🔥", "author_uid": f"v{i}", "created_at": None}
            for i in range(10)
        ]
        ca = classify_comments(variants)
        assert ca.duplicate_text_ratio > 0.9  # 'need this' normalizes identically


class TestFeedsDemoteFramework:
    """The verdict must reach the grade through the existing demote-only path."""

    def test_seeded_comments_produce_manufactured_demote(self):
        ca = classify_comments(seeded_comments())
        product = {"comment_authenticity": ca.to_dict()}
        org, promo, n_org = signals_from_product(product)
        auth = compute_authenticity(
            organic_strength=org, promoted_strength=promo, n_organic_sources=n_org
        )
        # Seeded → promoted high, organic low+measured → manufactured, heavy demote.
        assert auth.label == "manufactured"
        assert auth.multiplier < 1.0

    def test_organic_comments_do_not_demote(self):
        ca = classify_comments(organic_comments())
        product = {"comment_authenticity": ca.to_dict()}
        org, promo, n_org = signals_from_product(product)
        auth = compute_authenticity(
            organic_strength=org, promoted_strength=promo, n_organic_sources=n_org
        )
        assert auth.multiplier == 1.0  # never demoted for organic engagement

    def test_seeded_demoted_more_than_organic(self):
        """THE core relationship: at otherwise-equal signals, seeded < organic."""
        def mult(comments):
            ca = classify_comments(comments)
            org, promo, n_org = signals_from_product({"comment_authenticity": ca.to_dict()})
            return compute_authenticity(
                organic_strength=org, promoted_strength=promo, n_organic_sources=n_org
            ).multiplier

        assert mult(seeded_comments()) < mult(organic_comments())

    def test_no_comments_leaves_signals_untouched(self):
        """A product with no comment authenticity is unaffected by this layer."""
        org, promo, n_org = signals_from_product({})
        assert org == 0.0 and promo == 0.0 and n_org == 0
