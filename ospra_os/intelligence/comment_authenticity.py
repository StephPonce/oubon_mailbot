"""
Seeded-vs-organic comment classifier — Moat Phase 2, the truth filter.

Reads a product's persisted TikTok comments (Moat P2-S1) and decides whether the
engagement around it looks ORGANIC (real people, diverse voices, spread over the
video's life) or SEEDED (coordinated bursts of templated text from throwaway
accounts). The verdict feeds the EXISTING demote-only authenticity framework
(intelligence/demand_authenticity.py) so a seeded product loses grade against an
organic one at the same units-sold — never inflates.

SIGNALS (all derivable from the real comment output — follower count / account
age are NOT available from the comments actor; see the connector's findings):

  1. duplicate_text_ratio   — share of comments whose normalized text repeats
                              another's (bot rings post templated copy).
  2. author_concentration   — 1 - unique_authors/total: a few accounts flooding
                              (the 48h creator-cluster tell, measured on identity).
  3. default_handle_share    — share of commenters on auto-assigned userNNNN
                              handles (proxy for throwaway/new accounts).
  4. burst_concentration     — share of comments packed into the single densest
                              1-hour window (a coordinated post burst vs organic
                              spread over the video's life).

seeded_score is their weighted blend (0=organic, 1=seeded); organic_score is
its complement. THIN DATA GATE: below MIN_COMMENTS the profile is too small to
judge and the classifier returns None — no signal, no demote (matches the rest
of the moat's no-fabrication posture).

PURE: ``classify_comments`` does no I/O and is deterministically unit-testable.
``load_comment_authenticity_for_product`` is the thin DB adapter.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Below this many comments the engagement profile is too small to judge.
MIN_COMMENTS = int(os.getenv("COMMENT_AUTHENTICITY_MIN_COMMENTS", "8"))

# Signal weights (env-overridable; tune against real seeded/organic examples).
_W_DUPLICATE = float(os.getenv("COMMENT_W_DUPLICATE", "0.35"))
_W_AUTHOR = float(os.getenv("COMMENT_W_AUTHOR_CONCENTRATION", "0.25"))
_W_HANDLE = float(os.getenv("COMMENT_W_DEFAULT_HANDLE", "0.20"))
_W_BURST = float(os.getenv("COMMENT_W_BURST", "0.20"))

_DEFAULT_HANDLE_RE = re.compile(r"^user\d{6,}$", re.IGNORECASE)
_NORM_RE = re.compile(r"[^a-z0-9 ]+")


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _norm_text(text: str) -> str:
    """Normalize for duplicate detection: lowercase, strip non-alphanumerics,
    collapse whitespace. Templated seeding ('🔥 need this!!!' vs 'need this 🔥')
    collapses to the same key."""
    return " ".join(_NORM_RE.sub(" ", (text or "").lower()).split())


@dataclass
class CommentAuthenticity:
    seeded_score: float          # 0=organic .. 1=seeded
    organic_score: float         # complement
    n_comments: int
    duplicate_text_ratio: float
    author_concentration: float
    default_handle_share: float
    burst_concentration: float
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seeded_score": self.seeded_score,
            "organic_score": self.organic_score,
            "n_comments": self.n_comments,
            "duplicate_text_ratio": self.duplicate_text_ratio,
            "author_concentration": self.author_concentration,
            "default_handle_share": self.default_handle_share,
            "burst_concentration": self.burst_concentration,
            "reasons": self.reasons,
        }


def _get(c, key):
    """Access a field on either a dict or a ProductComment/TikTokComment row."""
    if isinstance(c, dict):
        return c.get(key)
    return getattr(c, key, None)


def _burst_concentration(times: List) -> float:
    """Share of comments falling in the single densest 1-hour window. Organic
    engagement spreads over the video's life (low); a seeding burst packs many
    comments into a tight window (high). Needs ≥2 timestamps."""
    epochs = []
    for t in times:
        if t is None:
            continue
        try:
            epochs.append(t.timestamp())
        except AttributeError:
            continue
    if len(epochs) < 2:
        return 0.0
    epochs.sort()
    window = 3600.0  # 1 hour
    best = 1
    j = 0
    for i in range(len(epochs)):
        while epochs[i] - epochs[j] > window:
            j += 1
        best = max(best, i - j + 1)
    return best / len(epochs)


def classify_comments(comments: List) -> Optional[CommentAuthenticity]:
    """Classify a product's comments as organic vs seeded. Returns None when
    there are fewer than MIN_COMMENTS (too thin to judge)."""
    comments = [c for c in comments if c is not None]
    n = len(comments)
    if n < MIN_COMMENTS:
        return None

    # 1. Duplicate text ratio.
    norms = [_norm_text(_get(c, "text") or "") for c in comments]
    counts = Counter(t for t in norms if t)
    dup_comments = sum(cnt for t, cnt in counts.items() if cnt > 1)
    duplicate_text_ratio = _clamp01(dup_comments / n)

    # 2. Author concentration (repeat commenters). Identity by uid, else handle.
    authors = [
        _get(c, "author_uid") or _get(c, "author_unique_id") or f"_anon_{i}"
        for i, c in enumerate(comments)
    ]
    unique_authors = len(set(authors))
    author_concentration = _clamp01(1.0 - unique_authors / n)

    # 3. Default-handle share (throwaway-account proxy).
    def _is_default(c) -> bool:
        flag = _get(c, "author_is_default_handle")
        if flag is not None:
            return bool(flag)
        handle = _get(c, "author_unique_id")
        return bool(handle and _DEFAULT_HANDLE_RE.match(str(handle)))
    default_handle_share = _clamp01(sum(1 for c in comments if _is_default(c)) / n)

    # 4. Burst concentration.
    burst_concentration = _burst_concentration([_get(c, "created_at") for c in comments])

    seeded_score = _clamp01(
        _W_DUPLICATE * duplicate_text_ratio
        + _W_AUTHOR * author_concentration
        + _W_HANDLE * default_handle_share
        + _W_BURST * burst_concentration
    )
    organic_score = _clamp01(1.0 - seeded_score)

    reasons: List[str] = []
    if duplicate_text_ratio >= 0.3:
        reasons.append(f"{duplicate_text_ratio:.0%} of comments repeat templated text")
    if author_concentration >= 0.3:
        reasons.append(f"engagement concentrated in few accounts ({author_concentration:.2f})")
    if default_handle_share >= 0.3:
        reasons.append(f"{default_handle_share:.0%} throwaway-handle accounts")
    if burst_concentration >= 0.5:
        reasons.append(f"{burst_concentration:.0%} of comments in one 1h burst")
    if not reasons:
        reasons.append("diverse authors, varied text, spread over time — organic-looking")

    return CommentAuthenticity(
        seeded_score=round(seeded_score, 3),
        organic_score=round(organic_score, 3),
        n_comments=n,
        duplicate_text_ratio=round(duplicate_text_ratio, 3),
        author_concentration=round(author_concentration, 3),
        default_handle_share=round(default_handle_share, 3),
        burst_concentration=round(burst_concentration, 3),
        reasons=reasons,
    )


def load_comment_authenticity_for_product(product: dict, session=None) -> Optional[CommentAuthenticity]:
    """Load a product's persisted comments (keyed by the shared
    product_identity_key) and classify them. None when thin/absent."""
    try:
        from ospra_os.database.connection import SessionLocal
        from ospra_os.database.product_comments import ProductComment
        from ospra_os.database.product_timeseries import product_identity_key
    except Exception:
        return None

    key = product_identity_key(product)
    owns = session is None
    if owns:
        session = SessionLocal()
    try:
        rows = session.query(ProductComment).filter(ProductComment.product_key == key).all()
    except Exception as e:
        logger.debug(f"[COMMENTS] authenticity load failed: {e}")
        return None
    finally:
        if owns:
            session.close()
    return classify_comments(rows)
