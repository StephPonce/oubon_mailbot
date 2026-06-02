"""
Tests for the winner-first STRICT decision (Option A keystone).

`_should_skip_keyword_search` is the lever that enforces "suppliers are
sourcing, not discovery": in strict mode STEP 2b (keyword supplier-candidate
search) never runs, so only trend/sentiment-validated winners are eligible.
"""

from __future__ import annotations

from ospra_os.intelligence.product_discovery import _should_skip_keyword_search


def test_strict_always_skips_keyword_candidates():
    # Strict mode: 2b never runs regardless of how many (or few) winners exist.
    assert _should_skip_keyword_search(winner_count=0, max_products=10, strict=True) is True
    assert _should_skip_keyword_search(winner_count=3, max_products=50, strict=True) is True
    assert _should_skip_keyword_search(winner_count=100, max_products=10, strict=True) is True


def test_non_strict_skips_only_when_winners_fill_half_page():
    # Default behaviour: skip 2b only when winner-first produced >= half a page.
    # threshold = max(int(max_products*0.5), 5)
    assert _should_skip_keyword_search(winner_count=5, max_products=10, strict=False) is True   # 5 >= 5
    assert _should_skip_keyword_search(winner_count=4, max_products=10, strict=False) is False  # 4 < 5
    # max_products=20 → threshold 10
    assert _should_skip_keyword_search(winner_count=10, max_products=20, strict=False) is True
    assert _should_skip_keyword_search(winner_count=9, max_products=20, strict=False) is False
    # Small max_products still floors threshold at 5
    assert _should_skip_keyword_search(winner_count=4, max_products=2, strict=False) is False
    assert _should_skip_keyword_search(winner_count=5, max_products=2, strict=False) is True
