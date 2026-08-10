"""
Composite sentiment scoring — diversity × volume.

Replaces the previous cascade ("first source wins, score = max-with-floor").
The cascade had two broken behaviours:
  1. A single Reddit post (1 mention) got the same baseline floor as 50
     posts. Volume wasn't reflected past tier boundaries.
  2. A product with only Amazon data scored as if Amazon was a complete
     view of social sentiment, when really we'd only consulted ONE source.
     Diversity wasn't reflected at all.

The new model treats sentiment as a weighted average across N independent
sources, weighted by per-source confidence, and then dampened by a
diversity factor that rewards multi-source corroboration.

For any signal source we have:
  - ``score``:  the source's own polarity reading on 0-100
  - ``weight``: how much evidence backs it (log-saturated counts so 1
                review doesn't equal 1000 reviews)

Final sentiment:
  total_w   = sum(weight)
  raw       = sum(score * weight) / total_w
  diversity = 0.40 + 0.20 * (n_sources - 1)   capped at 1.0
  sentiment = raw  (the diversity factor flows separately into
                    ``sentiment_confidence`` so it surfaces in the OI
                    composite via data_confidence rather than silently
                    deflating the polarity number)

Per-source weight curves are deliberately log-saturated so that:
  - 1 piece of evidence is meaningfully less than 10
  - 10 is meaningfully less than 100
  - 100 vs 1000 makes only a small additional difference

This makes "single weak signal" cases honestly weak without making
"already strong signal" cases noisier than they should be.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Per-source contribution
# ---------------------------------------------------------------------------

@dataclass
class SentimentInput:
    """One source's contribution to the composite."""
    name: str          # 'amazon_reviews', 'twitter', 'reddit', 'tiktok', ...
    score: float       # 0-100 polarity reading from this source
    weight: float      # 0.0-1.0 confidence in THIS source (volume-driven)


@dataclass
class CompositeResult:
    """What the composite computer returns."""
    sentiment_score: Optional[int]   # 0-100, or None if no sources had data
    sentiment_confidence: float      # 0.0-1.0 — used by OI data_confidence
    diversity: float                 # 0.0-1.0 — fraction of sources that contributed
    n_sources: int                   # number of sources that contributed
    sources: list = field(default_factory=list)   # [(name, score, weight), ...]
    primary_source: Optional[str] = None          # source with the largest weight


# ---------------------------------------------------------------------------
# Per-source weight curves (volume → 0-1 confidence in this source)
# ---------------------------------------------------------------------------

def amazon_weight(review_count: int) -> float:
    """Amazon: log-saturated to ~1.0 at ~10k reviews.
       1 review → 0.075, 100 → 0.5, 10000 → 1.0."""
    if not review_count or review_count <= 0:
        return 0.0
    return min(1.0, math.log10(1 + review_count) / 4.0)


def twitter_weight(tweet_count: int) -> float:
    """Twitter: log-saturated to ~1.0 at ~1k tweets.
       1 tweet → 0.10, 10 → 0.33, 100 → 0.66, 1000+ → 1.0."""
    if not tweet_count or tweet_count <= 0:
        return 0.0
    return min(1.0, math.log10(1 + tweet_count) / 3.0)


def twitter_weight_v2(tweet_count: int, total_engagement: int = 0,
                      has_citations: bool = False) -> float:
    """Honest Twitter/X confidence (#6, Option A).

    Grok output WITHOUT real citations is paraphrase/recollection from training
    data — not market proof — so it contributes ZERO confidence. Only live
    x_search results with real citations are trusted, and even then the weight
    is driven by REAL engagement (log-scaled likes+retweets+replies) blended
    with tweet volume, so a handful of low-engagement posts barely register
    while a high-engagement cluster carries real weight.

        no citations               → 0.00  (paraphrase is not proof)
        citations, ~0 engagement   → ~0.00-0.10
        citations, ~1k engagement  → ~0.55
        citations, 10k+ engagement → ~0.90-1.0
    """
    if not has_citations:
        return 0.0
    vol = min(1.0, math.log10(1 + max(0, tweet_count)) / 3.0)        # ~1.0 at 1k tweets
    eng = min(1.0, math.log10(1 + max(0, total_engagement)) / 4.0)   # ~1.0 at 10k engagement
    # Engagement is the real proof; volume only supports it.
    return max(0.0, min(1.0, 0.35 * vol + 0.65 * eng))


def reddit_weight(mention_count: int) -> float:
    """Reddit: log-saturated to 1.0 at ~100 posts.
       1 post → 0.15, 5 → 0.39, 20 → 0.66, 100+ → 1.0."""
    if not mention_count or mention_count <= 0:
        return 0.0
    return min(1.0, math.log10(1 + mention_count) / 2.0)


def tiktok_weight(comment_count: int, view_count: int = 0) -> float:
    """TikTok: log-saturated. Comments matter more than views.
       Mostly comments-driven; views as a tie-breaker."""
    score = 0.0
    if comment_count and comment_count > 0:
        score += min(1.0, math.log10(1 + comment_count) / 3.0)
    if view_count and view_count > 0:
        score += 0.1 * min(1.0, math.log10(1 + view_count) / 6.0)
    return min(1.0, score)


def aliexpress_review_weight(review_count: int) -> float:
    """AliExpress reviews: log-saturated to ~1.0 at ~500 reviews.
       1 review → 0.10, 25 → 0.55, 500 → 1.0.
       Lower ceiling than Amazon because AE reviews are translated/
       templated more often (less qualitative substance per row)."""
    if not review_count or review_count <= 0:
        return 0.0
    return min(1.0, math.log10(1 + review_count) / 2.7)


def aliexpress_buyer_weight(recent_sales: int) -> float:
    """AliExpress buyer-rating weight, driven by order volume rather than
    review count. Used by the buyer-rating sentiment branch (see
    score_from_aliexpress_buyer) which kicks in when Western public-social
    is silent.

    Volume saturation: 1 sale → 0.05, 100 → 0.40, 1k → 0.65, 10k → 0.85, 100k → 1.0.

    Lower ceiling than amazon_weight (which caps at 1.0 at ~500 reviews)
    because AE buyer ratings are systemically inflated — 4.5+ stars is the
    de-facto floor on AE — so even a high-volume signal carries less
    information per data point. We compensate with a confidence haircut
    at the call site (~0.6× multiplier) on top of this weight curve.
    """
    if not recent_sales or recent_sales <= 0:
        return 0.0
    # log10(1+1e5)/5 = 1.0 at 100k sales. Floor of 0.05 keeps low-volume
    # products from contributing zero weight while still being audible.
    return max(0.05, min(1.0, math.log10(1 + recent_sales) / 5.0))


def cj_proxy_weight() -> float:
    """CJ supplier-quality proxy weight — the TERTIARY sentiment tier.

    Fixed and deliberately low: unlike every other input this is STRUCTURAL
    metadata (warehouse location, image richness, listing popularity), not a
    buyer voice. It exists so a CJ-only product is gradeable at all rather
    than being auto-binned as INSUFFICIENT_DATA — see the last-resort branch
    in product_discovery's sentiment cascade.

    Restored 2026-08 (decision D6): the tier was computed, displayed, and
    reported in coverage, but the April composite rewrite never re-added the
    branch and this weight function was never written — so it contributed
    exactly nothing to the score for months while looking present.
    """
    return 0.25


def score_from_cj_proxy(proxy_score: float) -> float:
    """CJ structural quality → 0-100 sentiment, capped at 70.

    The cap encodes that structural metadata can never be as strong as an
    actual buyer signal: a CJ-only product can look good, but it can never
    look as validated as one with real review evidence.
    """
    return max(0.0, min(70.0, float(proxy_score or 0)))


# ---------------------------------------------------------------------------
# Per-source score normalizers
# ---------------------------------------------------------------------------

def score_from_amazon_buzz(buzz_score: float) -> float:
    """Amazon Apify buzz_score is already 0-100 (rating × log review count)."""
    return max(0.0, min(100.0, float(buzz_score)))


def score_from_twitter_polarity(polarity_minus1_to_plus1: float) -> float:
    """xAI Grok returns sentiment_score in -1..+1. Map to 20..90:
       -1 → 20, 0 → 55, +1 → 90 (consistent with prior scaling)."""
    p = max(-1.0, min(1.0, float(polarity_minus1_to_plus1)))
    return 55.0 + p * 35.0


def score_from_reddit_mentions(reddit_mentions: int) -> float:
    """Reddit doesn't give us per-post polarity in the current pipeline,
    only mention counts. Use a tiered floor — high-volume mentions are a
    positive signal in themselves on Reddit."""
    if reddit_mentions > 50:
        return 92.0
    if reddit_mentions > 20:
        return 82.0
    if reddit_mentions > 10:
        return 72.0
    if reddit_mentions > 5:
        return 65.0
    if reddit_mentions > 0:
        return 58.0
    return 0.0


def score_from_aliexpress_reviews(reviews: list[dict]) -> float:
    """
    AE reviews → polarity score (0-100) from average per-review rating.

    Different from the rolled-up ``evaluate_rate`` (which we use for
    sourcing, not sentiment): this is computed from VERBATIM per-review
    ratings, with low-rating outliers correctly pulling the score down.

    1★→20, 2★→40, 3★→55 (neutral), 4★→75, 5★→90.
    """
    if not reviews:
        return 0.0
    ratings = [
        r.get("rating") for r in reviews
        if isinstance(r.get("rating"), (int, float)) and r.get("rating")
    ]
    if not ratings:
        return 0.0
    avg = sum(ratings) / len(ratings)
    if avg <= 1:
        return 20.0
    if avg <= 2:
        return 40.0
    if avg <= 3:
        return 55.0
    if avg <= 4:
        return 75.0
    return 90.0


def score_from_aliexpress_buyer(rating_pct: float, rating_stars: float) -> float:
    """AliExpress buyer-rating → 0-100 sentiment score.

    Distinct from score_from_aliexpress_reviews (verbatim-text-based,
    top-10 only). This branch consumes the rolled-up rating_pct and
    rating_stars that AE returns on every product at normalize time —
    so it works for the entire product set, not just the top 10.

    AE ratings are systemically inflated (4.5+ is the floor for almost
    everything), so we anchor the curve so 4.5★ = 65 (decent, not great)
    and only reward 4.7★+ products. rating_pct (positive-review %) acts
    as a tie-breaker to penalize products with high stars but suspicious
    review distribution.

    rating_stars: 0-5 from AE evaluate_rate
    rating_pct:   0-100 — % of reviews that are 4-5★ (positive)

    Score ladder:
       <4.0★ → 35 (genuinely bad — rare on AE)
        4.0★ → 50
        4.3★ → 58
        4.5★ → 65 (the AE baseline; weak signal)
        4.7★ → 75
        4.8★ → 82
        4.9★ → 88
        5.0★ → 92
    """
    stars = float(rating_stars or 0)
    pct = float(rating_pct or 0)
    if stars <= 0:
        return 0.0
    # Star-based base
    if stars < 4.0:
        base = 35.0
    elif stars < 4.3:
        base = 50.0
    elif stars < 4.5:
        base = 58.0
    elif stars < 4.7:
        base = 65.0
    elif stars < 4.8:
        base = 75.0
    elif stars < 4.9:
        base = 82.0
    elif stars < 5.0:
        base = 88.0
    else:
        base = 92.0
    # rating_pct adjusts ±5: 90%+ positive nudges up, <80% nudges down.
    if pct >= 90:
        base += 5
    elif pct >= 80:
        base += 2
    elif pct < 70 and pct > 0:
        base -= 5
    return max(0.0, min(100.0, base))


def score_from_tiktok_engagement(comment_count: int, view_count: int = 0) -> float:
    """TikTok comments + views → polarity proxy. Lots of engagement
    on a product is a positive signal even without polarity from the
    text. (Negative engagement signals would require comment-text
    sentiment analysis — wired separately if available.)"""
    if not comment_count or comment_count <= 0:
        return 0.0
    # Engagement ratio: comments per view if we know views.
    base = 55.0
    if comment_count > 1000:
        base = 85.0
    elif comment_count > 100:
        base = 75.0
    elif comment_count > 20:
        base = 65.0
    elif comment_count > 5:
        base = 60.0
    return base


# ---------------------------------------------------------------------------
# Composite computation
# ---------------------------------------------------------------------------

# Diversity multiplier curve
#   1 source  → 0.40 (low confidence — single-source story)
#   2 sources → 0.60
#   3 sources → 0.80
#   4 sources → 1.00
def diversity_multiplier(n_sources: int) -> float:
    if n_sources <= 0:
        return 0.0
    return min(1.0, 0.40 + 0.20 * (n_sources - 1))


def compose(sources: list[SentimentInput]) -> CompositeResult:
    """
    Combine N sources into a unified sentiment score + confidence.

    ``sources`` should already be filtered to those with weight > 0; an
    empty list returns sentiment_score=None.
    """
    valid = [s for s in sources if s.weight and s.weight > 0]

    if not valid:
        return CompositeResult(
            sentiment_score=None,
            sentiment_confidence=0.0,
            diversity=0.0,
            n_sources=0,
            sources=[],
            primary_source=None,
        )

    total_w = sum(s.weight for s in valid)
    raw_avg = sum(s.score * s.weight for s in valid) / total_w if total_w > 0 else 0.0

    n = len(valid)
    div = diversity_multiplier(n)

    # ``sentiment_confidence`` blends per-source weight ceiling and
    # diversity. A single tweet from one source: low. 50 reviews × 200
    # tweets × 10 reddit posts: high. The OI composite uses this to
    # decide whether the product belongs in INSUFFICIENT_DATA.
    avg_weight = total_w / n
    sentiment_confidence = min(1.0, div * (0.5 + 0.5 * avg_weight))

    primary = max(valid, key=lambda s: s.weight).name

    return CompositeResult(
        sentiment_score=int(round(raw_avg)),
        sentiment_confidence=round(sentiment_confidence, 3),
        diversity=round(div, 3),
        n_sources=n,
        sources=[(s.name, round(s.score, 1), round(s.weight, 3)) for s in valid],
        primary_source=primary,
    )
