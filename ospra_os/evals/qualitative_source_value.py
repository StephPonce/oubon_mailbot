"""
Qualitative source-value eval — does each verbatim-text source actually
change the agent's BUY/WATCH/SKIP output, or are we paying for noise?

Methodology:
  1. 10 hand-crafted product fixtures that span the realistic spectrum
     of evidence shapes we see in production (single weak source,
     multi-source agreement, multi-source disagreement, all-negative,
     INSUFFICIENT_DATA territory, etc.).
  2. For each fixture, run ``assess_product`` once with the FULL evidence
     set, then again with one source ablated at a time.
  3. Compare the two QualitativeAssessment objects:
       - recommendation flip (BUY → WATCH, WATCH → SKIP, …)
       - polarity flip (positive → mixed → negative)
       - theme overlap (Jaccard on themes set)
       - confidence delta
  4. Print a per-source summary: out of N fixtures, how many had a
     recommendation flip when this source was REMOVED? (High flip
     count = source pulls weight; near-zero = source is decoration.)

Modes:
  - default (mock): doesn't call any real AI provider. A fake provider
    returns deterministic JSON so the harness itself can be developed,
    tested, and demoed without burning credits.
  - --live:         actually call xAI Grok or Claude (whichever the
    qualitative agent's provider routing picks). Costs real tokens.
    Print a cost estimate first; require explicit confirmation if
    costs exceed a threshold.

Run:
  python -m ospra_os.evals.qualitative_source_value
  python -m ospra_os.evals.qualitative_source_value --live --limit 5
  python -m ospra_os.evals.qualitative_source_value --live --json out.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Optional

# The sources we ablate one-at-a-time. Each entry maps a logical source
# name to the product-dict key the qualitative agent reads.
ABLATABLE_SOURCES: list[tuple[str, str]] = [
    ("twitter", "twitter_evidence"),
    ("reddit", "reddit_evidence"),
    ("amazon_aggregate", "amazon_evidence"),
    ("aliexpress_reviews", "aliexpress_reviews"),
    ("youtube", "youtube_evidence"),
    ("amazon_review_text", "amazon_review_text"),
    ("google_trends_context", "data_sources"),  # nested; see _ablate
]


# ---------------------------------------------------------------------------
# Fixtures — 10 realistic product evidence shapes
# ---------------------------------------------------------------------------

def _fixture_strong_multi_source_buy() -> dict:
    """Top-tier: every source is positive. Should be a confident BUY."""
    return {
        "title": "Smart Plug WiFi Energy Monitor",
        "niche": "smart_home",
        "twitter_evidence": {
            "found_real_tweets": True, "search_level": "live",
            "sentiment": "positive", "sentiment_score": 0.7, "tweet_count": 240,
            "sample_tweets": [
                "Just bought 4 of these smart plugs, the energy tracking is GAME CHANGING",
                "Linked these to alexa in 2 min, working perfectly",
                "Cut my standby power usage by 30%",
            ],
            "common_praise": ["easy setup", "energy tracking", "alexa integration"],
            "common_complaints": [],
        },
        "reddit_evidence": [
            {"title": "Best smart plug for energy monitoring?", "selftext_excerpt": "This brand has been rock solid for me", "subreddit": "smarthome", "score": 187, "num_comments": 64, "match_type": "exact"},
            {"title": "Smart plug saved me $40/mo on electric", "selftext_excerpt": "Tracking standby loads helped me identify the worst offenders", "subreddit": "frugal", "score": 92, "num_comments": 31, "match_type": "fuzzy"},
        ],
        "amazon_evidence": {
            "found_matches": True, "aggregate_rating": 4.6, "total_reviews": 18420,
            "top_matches": [{"title": "Smart Plug WiFi", "asin": "B0X1234567", "rating": 4.6, "reviews_count": 18420}],
        },
        "aliexpress_reviews": {
            "available": True, "review_count_returned": 8, "average_rating": 4.5,
            "reviews": [
                {"text": "Works great, easy to set up with the app", "rating": 5, "verified": True},
                {"text": "Compact size, fits perfectly behind furniture", "rating": 5, "verified": True},
                {"text": "Slight delay in app updates but functional", "rating": 4, "verified": True},
            ],
        },
        "youtube_evidence": {
            "available": True, "review_video_count": 12, "total_views": 480000, "total_likes": 14200,
            "top_videos": [{"title": "Best Smart Plugs 2025", "channel": "TechMonkey", "views": 220000, "likes": 6800}],
            "top_comments": [
                {"text": "Got these last week, app is intuitive", "author": "user1", "likes": 89, "video_title": "Best Smart Plugs 2025"},
                {"text": "Energy stats are addictive, in a good way", "author": "user2", "likes": 54, "video_title": "Best Smart Plugs 2025"},
            ],
        },
        "amazon_review_text": {
            "available": True, "asin": "B0X1234567", "review_count_returned": 6,
            "average_rating": 4.7, "verified_share": 1.0,
            "reviews": [
                {"text": "Solid build, easy setup. Working perfectly 6 months in.", "rating": 5, "title": "Just works", "verified": True, "helpful_count": 41},
                {"text": "Energy monitoring is accurate vs my Kill-A-Watt meter.", "rating": 5, "title": "Accurate", "verified": True, "helpful_count": 22},
            ],
        },
    }


def _fixture_strong_multi_source_skip() -> dict:
    """Mirror: every source is negative. Should be a confident SKIP."""
    return {
        "title": "Cheap Bluetooth Earbuds Generic",
        "niche": "tech",
        "twitter_evidence": {
            "found_real_tweets": True, "search_level": "live",
            "sentiment": "negative", "sentiment_score": -0.5, "tweet_count": 60,
            "sample_tweets": [
                "These earbuds DIED after 2 weeks, do not buy",
                "Sound quality is awful, returning",
            ],
            "common_praise": [],
            "common_complaints": ["short battery life", "poor sound quality", "DOA units"],
        },
        "reddit_evidence": [
            {"title": "Avoid these cheap earbuds", "selftext_excerpt": "Battery dies in a week, sound is muddy", "subreddit": "headphones", "score": 245, "num_comments": 89, "match_type": "exact"},
        ],
        "amazon_evidence": {
            "found_matches": True, "aggregate_rating": 2.8, "total_reviews": 1840,
            "top_matches": [{"title": "Cheap BT Earbuds", "asin": "B0Y9999999", "rating": 2.8, "reviews_count": 1840}],
        },
        "aliexpress_reviews": {
            "available": True, "review_count_returned": 6, "average_rating": 2.5,
            "reviews": [
                {"text": "One side stopped working after a week", "rating": 1, "verified": True},
                {"text": "Battery life is half what advertised", "rating": 2, "verified": True},
            ],
        },
        "youtube_evidence": {
            "available": True, "review_video_count": 4, "total_views": 12000, "total_likes": 180,
            "top_videos": [{"title": "DON'T Buy These — review", "channel": "AudioGuy", "views": 8400, "likes": 320}],
            "top_comments": [
                {"text": "Mine broke in the first month", "author": "buyer1", "likes": 24, "video_title": "DON'T Buy These — review"},
            ],
        },
    }


def _fixture_disagreement_amazon_vs_reddit() -> dict:
    """Amazon rating is 4.4 (high), but Reddit is full of complaints. The
    interesting case: which signal does the agent weight?"""
    return {
        "title": "LED Strip Light 16ft RGB",
        "niche": "smart_home",
        "amazon_evidence": {
            "found_matches": True, "aggregate_rating": 4.4, "total_reviews": 9200,
            "top_matches": [{"title": "LED Strip Light 16ft", "asin": "B0L1234567", "rating": 4.4}],
        },
        "amazon_review_text": {
            "available": True, "asin": "B0L1234567", "review_count_returned": 5,
            "average_rating": 4.6, "verified_share": 1.0,
            "reviews": [
                {"text": "Beautiful colors, easy install. Love it.", "rating": 5, "verified": True, "helpful_count": 12},
                {"text": "Wife loves them. App works fine.", "rating": 5, "verified": True, "helpful_count": 8},
            ],
        },
        "reddit_evidence": [
            {"title": "LED strip lights losing colors after 2 months", "selftext_excerpt": "These cheap chinese strips degrade fast — yellow turns green, the controller dies", "subreddit": "diyelectronics", "score": 312, "num_comments": 145, "match_type": "exact"},
            {"title": "Don't buy LED strips off Amazon", "selftext_excerpt": "Survival rate at 1 year is maybe 40%. The reviews are heavily filtered", "subreddit": "BuyItForLife", "score": 198, "num_comments": 67, "match_type": "fuzzy"},
        ],
    }


def _fixture_only_one_reddit_post() -> dict:
    """The user's original complaint: a single Reddit post should NOT
    yield a high-confidence read. Tests the diversity multiplier."""
    return {
        "title": "Niche Hobby Gadget XYZ",
        "niche": "gaming",
        "reddit_evidence": [
            {"title": "Anyone tried this XYZ gadget?", "selftext_excerpt": "Saw it on a store, looks interesting", "subreddit": "gaming", "score": 12, "num_comments": 3, "match_type": "fuzzy"},
        ],
    }


def _fixture_youtube_only() -> dict:
    """Only YouTube viewer comments — measure their weight."""
    return {
        "title": "Pet Camera 360 Auto Tracking",
        "niche": "pet",
        "youtube_evidence": {
            "available": True, "review_video_count": 8, "total_views": 142000, "total_likes": 4100,
            "top_videos": [{"title": "Pet Camera Review — Worth the Money?", "channel": "PetTechTV", "views": 84000, "likes": 2400}],
            "top_comments": [
                {"text": "Mine works great with two dogs in the house", "author": "petowner1", "likes": 67, "video_title": "Pet Camera Review — Worth the Money?"},
                {"text": "App crashes constantly on android", "author": "petowner2", "likes": 32, "video_title": "Pet Camera Review — Worth the Money?"},
                {"text": "Tracking is jerky but treat dispenser is fun", "author": "petowner3", "likes": 28, "video_title": "Pet Camera Review — Worth the Money?"},
            ],
        },
    }


def _fixture_aliexpress_only() -> dict:
    """Only AE reviews — typical for a no-name AE product with no Amazon
    listing or YouTube coverage."""
    return {
        "title": "Mini USB Desk Fan",
        "niche": "office",
        "aliexpress_reviews": {
            "available": True, "review_count_returned": 8, "average_rating": 4.2,
            "reviews": [
                {"text": "Quiet, good for laptop area", "rating": 5, "verified": True},
                {"text": "Plastic feels cheap but works", "rating": 4, "verified": True},
                {"text": "Cable too short", "rating": 3, "verified": True},
                {"text": "Doesn't oscillate enough", "rating": 3, "verified": True},
            ],
        },
    }


def _fixture_amazon_aggregate_only() -> dict:
    """Aggregate rating only — no review TEXT. Tests the data_gap call-out."""
    return {
        "title": "Insulated Water Bottle 32oz",
        "niche": "fitness",
        "amazon_evidence": {
            "found_matches": True, "aggregate_rating": 4.5, "total_reviews": 28400,
            "top_matches": [{"title": "Insulated Water Bottle 32oz", "asin": "B0W1234567", "rating": 4.5}],
        },
    }


def _fixture_twitter_only_paraphrased() -> dict:
    """Only Twitter, in paraphrase mode (no real URLs). Sanity check
    that the agent treats this honestly as low-confidence."""
    return {
        "title": "Trending Skincare Serum",
        "niche": "beauty",
        "twitter_evidence": {
            "found_real_tweets": True, "search_level": "paraphrased",
            "sentiment": "positive", "sentiment_score": 0.4, "tweet_count": 38,
            "sample_tweets": [
                "this serum is making my skin glow",
                "obsessed with this serum, buying again",
            ],
            "common_praise": ["glowing skin", "smooth texture"],
            "common_complaints": [],
        },
    }


def _fixture_trends_with_negative_keywords() -> dict:
    """Trends related queries include 'doesn't work' and 'scam' alongside
    the product name — interest signal with negative-leaning vocabulary.
    Tests Phase G context interpretation."""
    return {
        "title": "Posture Corrector Back Brace",
        "niche": "fitness",
        "amazon_evidence": {
            "found_matches": True, "aggregate_rating": 3.6, "total_reviews": 4200,
            "top_matches": [{"title": "Posture Corrector", "asin": "B0P1234567", "rating": 3.6}],
        },
        "data_sources": {
            "google_trends": {
                "trend_direction": "rising",
                "primary_momentum": "rising",
                "related_queries": {
                    "posture corrector": [
                        {"query": "posture corrector reviews"},
                        {"query": "posture corrector doesn't work"},
                        {"query": "posture corrector scam"},
                        {"query": "posture corrector before after"},
                    ]
                },
            }
        },
    }


def _fixture_insufficient_data() -> dict:
    """No evidence on any source. Should return INSUFFICIENT_DATA cleanly."""
    return {
        "title": "Obscure Product No One Has Reviewed",
        "niche": "general",
    }


def all_fixtures() -> list[dict]:
    return [
        _fixture_strong_multi_source_buy(),
        _fixture_strong_multi_source_skip(),
        _fixture_disagreement_amazon_vs_reddit(),
        _fixture_only_one_reddit_post(),
        _fixture_youtube_only(),
        _fixture_aliexpress_only(),
        _fixture_amazon_aggregate_only(),
        _fixture_twitter_only_paraphrased(),
        _fixture_trends_with_negative_keywords(),
        _fixture_insufficient_data(),
    ]


# ---------------------------------------------------------------------------
# Mock provider — used in default mode so the harness can be developed
# without burning AI credits.
# ---------------------------------------------------------------------------

class _MockProvider:
    """Deterministic stand-in for the qualitative AI agent.

    Returns plausible JSON shaped like the real agent's output, with
    rules that:
      - Strong-positive evidence → BUY
      - Strong-negative evidence → SKIP
      - Mixed/contradictory → WATCH
      - Empty → INSUFFICIENT_DATA
    """
    name = "mock"

    async def chat(self, message: str) -> str:
        msg = message.lower()
        positive_count = sum(
            msg.count(token) for token in
            ("worked great", "love", "easy setup", "best", "obsessed", "rock solid", "energy tracking")
        )
        negative_count = sum(
            msg.count(token) for token in
            ("died", "broke", "doesn't work", "scam", "muddy", "awful", "do not buy", "avoid")
        )
        # Count actual evidence-section markers in the prompt body, not
        # mentions of source words inside instructions/preamble.
        sources_present = (
            ("--- twitter" in msg) + ("--- reddit" in msg)
            + ("--- amazon" in msg) + ("--- aliexpress reviews" in msg)
            + ("--- youtube" in msg)
        )

        # Hard signal: the prompt builder writes
        # "SOURCES PRESENT: (none — return INSUFFICIENT_DATA)"
        # when no sources fired. Detect that exact string.
        if "(none — return insufficient_data)" in msg or sources_present == 0:
            return json.dumps({
                "polarity": "unknown",
                "themes": [],
                "top_wins": [],
                "top_objections": [],
                "data_gaps": ["no evidence"],
                "recommendation": "INSUFFICIENT_DATA",
                "confidence": 0,
            })

        if positive_count >= 3 and negative_count == 0 and sources_present >= 3:
            return json.dumps({
                "polarity": "positive",
                "themes": ["easy setup", "reliable", "good value"],
                "top_wins": ["easy setup", "reliable build"],
                "top_objections": [],
                "data_gaps": [],
                "recommendation": "BUY",
                "confidence": 78,
            })

        if negative_count >= 3 and positive_count <= 1:
            return json.dumps({
                "polarity": "negative",
                "themes": ["build quality issues", "short battery life"],
                "top_wins": [],
                "top_objections": ["fragile build", "DOA units"],
                "data_gaps": [],
                "recommendation": "SKIP",
                "confidence": 70,
            })

        if sources_present == 1 and positive_count + negative_count <= 2:
            return json.dumps({
                "polarity": "neutral",
                "themes": ["limited evidence"],
                "top_wins": [],
                "top_objections": [],
                "data_gaps": ["only one source"],
                "recommendation": "WATCH",
                "confidence": 35,
            })

        return json.dumps({
            "polarity": "mixed",
            "themes": ["mixed signals", "rating-vs-reviews disagreement"],
            "top_wins": ["aesthetic appeal"],
            "top_objections": ["quality concerns"],
            "data_gaps": [],
            "recommendation": "WATCH",
            "confidence": 55,
        })


# ---------------------------------------------------------------------------
# Eval core
# ---------------------------------------------------------------------------

@dataclass
class FixtureResult:
    fixture_title: str
    full_recommendation: str
    full_polarity: str
    full_confidence: int
    full_themes: list[str]
    ablations: dict[str, dict[str, Any]]


def _ablate(product: dict, source_key: str) -> dict:
    """Return a deep copy of ``product`` with the named source removed.

    For top-level keys we just delete. For ``data_sources`` we drop the
    ``google_trends`` sub-key so the rest of the data_sources dict stays.
    """
    p = deepcopy(product)
    if source_key == "data_sources":
        ds = p.get("data_sources") or {}
        ds.pop("google_trends", None)
        if not ds:
            p.pop("data_sources", None)
        else:
            p["data_sources"] = ds
        return p
    p.pop(source_key, None)
    return p


def _theme_overlap(a: list[str], b: list[str]) -> float:
    sa, sb = set(a or []), set(b or [])
    if not sa and not sb:
        return 1.0
    if not (sa | sb):
        return 0.0
    return round(len(sa & sb) / len(sa | sb), 3)


async def _assess(product: dict, *, mock: bool):
    """Run the qualitative agent on a single product, optionally swapping
    the real provider for the mock."""
    from ospra_os.intelligence import sentiment_qualitative as sq

    if mock:
        original = sq._select_provider
        sq._select_provider = lambda: ("mock", _MockProvider())
        try:
            return await sq.assess_product(product)
        finally:
            sq._select_provider = original
    return await sq.assess_product(product)


async def evaluate(*, mock: bool, limit: Optional[int] = None) -> list[FixtureResult]:
    fixtures = all_fixtures()
    if limit:
        fixtures = fixtures[:limit]

    results: list[FixtureResult] = []
    for f in fixtures:
        full = await _assess(f, mock=mock)
        ablations: dict[str, dict[str, Any]] = {}
        for source_label, source_key in ABLATABLE_SOURCES:
            ablated = _ablate(f, source_key)
            ar = await _assess(ablated, mock=mock)
            ablations[source_label] = {
                "recommendation": ar.recommendation,
                "polarity": ar.polarity,
                "confidence": ar.confidence,
                "themes": ar.themes,
                "rec_flipped": ar.recommendation != full.recommendation,
                "polarity_flipped": ar.polarity != full.polarity,
                "theme_overlap": _theme_overlap(full.themes, ar.themes),
                "confidence_delta": ar.confidence - full.confidence,
            }
        results.append(FixtureResult(
            fixture_title=f.get("title", "?"),
            full_recommendation=full.recommendation,
            full_polarity=full.polarity,
            full_confidence=full.confidence,
            full_themes=full.themes,
            ablations=ablations,
        ))
    return results


def summarize(results: list[FixtureResult]) -> dict[str, Any]:
    """Aggregate per-source: how many fixtures had a rec/polarity flip
    when this source was removed?"""
    n = len(results)
    per_source: dict[str, dict[str, Any]] = {
        s: {"rec_flips": 0, "polarity_flips": 0, "avg_theme_overlap": [], "avg_confidence_delta": []}
        for s, _ in ABLATABLE_SOURCES
    }
    for r in results:
        for source_label, ablation in r.ablations.items():
            if ablation["rec_flipped"]:
                per_source[source_label]["rec_flips"] += 1
            if ablation["polarity_flipped"]:
                per_source[source_label]["polarity_flips"] += 1
            per_source[source_label]["avg_theme_overlap"].append(ablation["theme_overlap"])
            per_source[source_label]["avg_confidence_delta"].append(ablation["confidence_delta"])

    summary: dict[str, Any] = {}
    for source_label, agg in per_source.items():
        overlaps = agg["avg_theme_overlap"] or [1.0]
        deltas = agg["avg_confidence_delta"] or [0]
        summary[source_label] = {
            "rec_flip_rate": round(agg["rec_flips"] / n, 3) if n else 0,
            "polarity_flip_rate": round(agg["polarity_flips"] / n, 3) if n else 0,
            "avg_theme_overlap": round(sum(overlaps) / len(overlaps), 3),
            "avg_confidence_delta": round(sum(deltas) / len(deltas), 1),
        }
    return {"n_fixtures": n, "per_source": summary}


def render_text_report(results: list[FixtureResult], summary: dict) -> str:
    n = summary["n_fixtures"]
    out = []
    out.append("=" * 72)
    out.append(f"QUALITATIVE SOURCE-VALUE EVAL — {n} fixtures")
    out.append("=" * 72)
    out.append("")
    out.append("Per-fixture full-evidence recommendations:")
    for r in results:
        out.append(
            f"  [{r.full_recommendation:>17}] {r.full_polarity:<9} "
            f"conf={r.full_confidence:>3} — {r.fixture_title[:52]}"
        )
    out.append("")
    out.append("-" * 72)
    out.append("PER-SOURCE ABLATION (remove source → does the rec change?)")
    out.append("-" * 72)
    out.append(
        f"  {'source':<22}  {'rec_flip':>8}  {'pol_flip':>8}  "
        f"{'theme_∩':>8}  {'Δ_conf':>7}"
    )
    out.append(
        f"  {'(higher = more value)':<22}  {'rate':>8}  {'rate':>8}  "
        f"{'avg':>8}  {'avg':>7}"
    )
    out.append("")
    sorted_sources = sorted(
        summary["per_source"].items(),
        key=lambda kv: kv[1]["rec_flip_rate"],
        reverse=True,
    )
    for source_label, agg in sorted_sources:
        out.append(
            f"  {source_label:<22}  {agg['rec_flip_rate']:>8.1%}  "
            f"{agg['polarity_flip_rate']:>8.1%}  "
            f"{agg['avg_theme_overlap']:>8.2f}  "
            f"{agg['avg_confidence_delta']:>+7.1f}"
        )
    out.append("")
    out.append("INTERPRETATION:")
    out.append("  - rec_flip rate: fraction of fixtures where removing this source")
    out.append("    changed BUY/WATCH/SKIP. High = source is load-bearing.")
    out.append("    Near zero = source is decoration; consider cutting cost.")
    out.append("  - theme_∩ (Jaccard): how much the agent's themes overlap with")
    out.append("    and without the source. Lower = source contributes unique themes.")
    out.append("  - Δ_conf: average confidence delta when source is removed.")
    out.append("    Negative = removing the source HURTS the agent's confidence.")
    out.append("=" * 72)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _estimate_cost(n_fixtures: int) -> str:
    """Rough estimate. Each fixture runs (1 + N_sources) agent calls.
    Actual cost depends on provider + token volume — this is a
    ballpark before any --live run."""
    n_sources = len(ABLATABLE_SOURCES)
    calls = n_fixtures * (1 + n_sources)
    # ~$0.005-$0.02 per call at typical Grok / Claude pricing.
    low = calls * 0.005
    high = calls * 0.02
    return (
        f"~{calls} agent calls "
        f"(~${low:.2f}–${high:.2f} on xAI Grok / Claude pricing)"
    )


async def _async_main(args) -> int:
    if args.live:
        if not (os.getenv("XAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
            print(
                "[error] --live requires XAI_API_KEY or ANTHROPIC_API_KEY in env.",
                file=sys.stderr,
            )
            return 2
        n = len(all_fixtures()) if not args.limit else min(args.limit, len(all_fixtures()))
        print(f"[live] Cost estimate: {_estimate_cost(n)}")
        if not args.yes:
            answer = input("Proceed? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("[abort] No changes made.")
                return 0

    print(f"[mode] {'live' if args.live else 'mock'}; running eval...")
    results = await evaluate(mock=not args.live, limit=args.limit)
    summary = summarize(results)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(
                {"results": [asdict(r) for r in results], "summary": summary},
                fh,
                indent=2,
            )
        print(f"[ok] Wrote JSON report to {args.json}")

    print()
    print(render_text_report(results, summary))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Measure how much each verbatim-text source moves the qualitative agent's BUY/WATCH/SKIP output."
    )
    parser.add_argument("--live", action="store_true",
                        help="Hit the real AI provider (xAI/Claude). Costs tokens.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Run only the first N fixtures.")
    parser.add_argument("--json", type=str, default=None,
                        help="Write a structured JSON report to this path.")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Skip the cost-confirmation prompt under --live.")
    args = parser.parse_args()

    rc = asyncio.run(_async_main(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
