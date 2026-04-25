"""
Qualitative sentiment agent — actual AI "eyes" on social content.

The numeric composite in ``sentiment_composite.py`` answers *how strong*
the signal is. This module answers *what the signal is saying.*

Architecture (the user's mandate):
  - Each AI provider is used for the task it's actually meant for
  - xAI Grok = real-time social search → primary qualitative agent
    (its strength: live X/Twitter knowledge, current events)
  - Claude = synthesis when xAI is unavailable, OR for products that
    already have rich evidence and don't need fresh search
  - No cross-purposing. No silently calling OpenAI for tasks Claude
    or xAI is mapped to.

What the agent reads (when present):
  - ``twitter_evidence.sample_tweets[]`` — Grok live-search citations + tweets
  - ``twitter_evidence.common_praise[]`` / ``common_complaints[]``
  - ``reddit_evidence[].title`` + ``selftext_excerpt``
  - ``aliexpress_reviews.reviews[]`` — verbatim AE buyer prose (Phase H)
  - ``youtube_evidence.top_comments[]`` — verbatim viewer comments (Phase I)
  - ``youtube_evidence.top_videos[]`` — review-video titles for context
  - ``amazon_review_text.reviews[]`` — verbatim per-product Amazon review
    prose (Phase K; on-demand fetch only — populated when a frontend
    route or qualitative-refresh action calls
    ``ProductDiscovery.fetch_amazon_review_text(product)``)
  - ``google_trends_context.related_queries`` — interest-side vocabulary

What the agent produces:
  - ``polarity`` ('positive' | 'negative' | 'mixed' | 'neutral' | 'unknown')
  - ``themes[]`` — key themes from the actual content
  - ``top_wins[]`` — what people praise
  - ``top_objections[]`` — what people complain about
  - ``data_gaps[]`` — sources we lack but should have
  - ``recommendation`` ('BUY' | 'WATCH' | 'SKIP' | 'INSUFFICIENT_DATA')
  - ``confidence`` (0-100) — agent's stated confidence in its read

Why this is separate from numeric scoring:
  Quant tells you the SIZE of the signal. Qual tells you the SHAPE.
  The dashboard surfaces both: "OI 72 (data confidence 68%) · AI read:
  WATCH — buyers love it but ship times draw heat".
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

@dataclass
class QualitativeAssessment:
    polarity: str = "unknown"        # positive | negative | mixed | neutral | unknown
    themes: list[str] = field(default_factory=list)
    top_wins: list[str] = field(default_factory=list)
    top_objections: list[str] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    recommendation: str = "INSUFFICIENT_DATA"  # BUY | WATCH | SKIP | INSUFFICIENT_DATA
    confidence: int = 0              # 0-100
    provider: Optional[str] = None   # which AI did the read
    error: Optional[str] = None      # populated when the agent failed

    def to_dict(self) -> dict:
        return {
            "polarity": self.polarity,
            "themes": self.themes,
            "top_wins": self.top_wins,
            "top_objections": self.top_objections,
            "data_gaps": self.data_gaps,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "provider": self.provider,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Evidence aggregation
# ---------------------------------------------------------------------------

def _collect_evidence(product: dict) -> dict:
    """
    Pull every text-bearing piece of social evidence we have on a product
    into a single, AI-readable structure. Returns a dict the agent can
    paste straight into its prompt.
    """
    evidence: dict[str, Any] = {
        "title": product.get("title", ""),
        "niche": product.get("niche", "general"),
        "twitter": None,
        "reddit": None,
        "amazon": None,
        "tiktok": None,
        "google_trends_context": None,  # Phase G: interest signal, NOT sentiment
        "data_sources_available": [],
    }

    twitter = product.get("twitter_evidence") or {}
    if twitter.get("found_real_tweets"):
        evidence["twitter"] = {
            "search_level": twitter.get("search_level"),
            "sentiment_label": twitter.get("sentiment"),
            "sentiment_score": twitter.get("sentiment_score"),
            "tweet_count": twitter.get("tweet_count"),
            "sample_tweets": (twitter.get("sample_tweets") or [])[:8],
            "common_praise": twitter.get("common_praise") or [],
            "common_complaints": twitter.get("common_complaints") or [],
        }
        evidence["data_sources_available"].append("twitter")

    reddit = product.get("reddit_evidence")
    if isinstance(reddit, list) and reddit:
        evidence["reddit"] = [
            {
                "title": r.get("title", ""),
                "excerpt": r.get("selftext_excerpt", "")[:300],
                "subreddit": r.get("subreddit", ""),
                "score": r.get("score", 0),
                "num_comments": r.get("num_comments", 0),
                "match_type": r.get("match_type", ""),
            }
            for r in reddit[:5]
        ]
        evidence["data_sources_available"].append("reddit")

    # Phase G: Google Trends related queries — interest-side context.
    # Trends gives us what people SEARCH alongside the product (e.g.,
    # "smart plug reviews", "smart plug doesn't work", "smart plug vs
    # alexa"). The vocabulary itself is a qualitative signal even though
    # search volume is just interest, not approval. Lands as
    # ``data_sources.google_trends.related_queries`` upstream — also tolerate
    # the legacy direct-on-product field shape.
    gt = (product.get("data_sources") or {}).get("google_trends") or {}
    related = gt.get("related_queries") or product.get("google_trends_related_queries") or {}
    if related:
        # Flatten across all matched keywords; cap to keep the prompt tight.
        flat: list[str] = []
        for kw, qs in (related.items() if isinstance(related, dict) else []):
            for q in (qs or [])[:5]:
                qstr = q.get("query") if isinstance(q, dict) else q
                if qstr:
                    flat.append(str(qstr))
        if flat:
            evidence["google_trends_context"] = {
                "trend_direction": gt.get("trend_direction"),
                "primary_momentum": gt.get("primary_momentum"),
                "related_queries": flat[:15],
            }
            # Note: NOT appended to ``data_sources_available`` because
            # Trends is interest, not opinion. The qualitative agent
            # treats it as context only, never as a sentiment input.

    # Phase H: AliExpress review text (verbatim per-product reviews via Apify).
    # This gives the qualitative agent actual buyer prose to read instead of
    # a single rolled-up rating number.
    ae_reviews = product.get("aliexpress_reviews") or {}
    if ae_reviews.get("available") and ae_reviews.get("reviews"):
        evidence["aliexpress_reviews"] = {
            "average_rating": ae_reviews.get("average_rating"),
            "count": ae_reviews.get("review_count_returned", 0),
            "samples": [
                {
                    "text": r.get("text", "")[:280],  # cap length to keep prompt tight
                    "rating": r.get("rating"),
                    "country": r.get("country"),
                    "verified": r.get("verified"),
                }
                for r in (ae_reviews.get("reviews") or [])[:8]  # top 8 reviews
                if r.get("text")
            ],
        }
        evidence["data_sources_available"].append("aliexpress_reviews")

    # Phase J (Instagram captions) was disabled per cost-cut decision.
    # Connector is still on disk if we want to revisit, but discovery no
    # longer attaches ``instagram_evidence`` so this block became dead.

    # Phase I: YouTube — top review videos + verbatim viewer comments.
    # The comments are the qualitative gold here: real buyers reacting
    # to a real reviewer's hands-on take. The agent should weigh them
    # like Reddit comments.
    yt = product.get("youtube_evidence") or {}
    if yt.get("available") and (yt.get("top_comments") or yt.get("top_videos")):
        evidence["youtube"] = {
            "review_video_count": yt.get("review_video_count", 0),
            "total_views": yt.get("total_views", 0),
            "total_likes": yt.get("total_likes", 0),
            "top_videos": [
                {
                    "title": v.get("title"),
                    "channel": v.get("channel"),
                    "views": v.get("views", 0),
                    "likes": v.get("likes", 0),
                }
                for v in (yt.get("top_videos") or [])[:5]
                if v.get("title")
            ],
            "top_comments": [
                {
                    "text": (c.get("text") or "")[:280],
                    "author": c.get("author"),
                    "likes": c.get("likes", 0),
                    "video_title": c.get("video_title"),
                }
                for c in (yt.get("top_comments") or [])[:10]
                if c.get("text")
            ],
        }
        evidence["data_sources_available"].append("youtube")

    amazon = product.get("amazon_evidence") or {}
    amazon_text = product.get("amazon_review_text") or {}
    if amazon.get("found_matches") or (amazon_text.get("available") and amazon_text.get("reviews")):
        # Phase K: per-product review TEXT (verbatim buyer prose) is now
        # fetched by the discovery flow via a dedicated Apify actor.
        # When it's available we feed both the niche-level aggregate
        # signal AND the per-product samples to the agent.
        amazon_block: dict[str, Any] = {
            "aggregate_rating": amazon.get("aggregate_rating"),
            "total_reviews": amazon.get("total_reviews"),
            "top_match_titles": [
                m.get("title") for m in (amazon.get("top_matches") or [])[:5]
                if m.get("title")
            ],
            "review_text_available": False,
        }
        if amazon_text.get("available") and amazon_text.get("reviews"):
            amazon_block["review_text_available"] = True
            amazon_block["asin"] = amazon_text.get("asin")
            amazon_block["per_product_avg"] = amazon_text.get("average_rating")
            amazon_block["verified_share"] = amazon_text.get("verified_share")
            amazon_block["samples"] = [
                {
                    "text": (r.get("text") or "")[:280],
                    "title": r.get("title"),
                    "rating": r.get("rating"),
                    "verified": r.get("verified"),
                    "helpful_count": r.get("helpful_count", 0),
                }
                for r in (amazon_text.get("reviews") or [])[:8]
                if r.get("text")
            ]
        evidence["amazon"] = amazon_block
        evidence["data_sources_available"].append("amazon")

    return evidence


# ---------------------------------------------------------------------------
# Provider selection (strict — no cross-purposing)
# ---------------------------------------------------------------------------

def _select_provider() -> tuple[Optional[str], Optional[Any]]:
    """
    Strict task→provider routing per AIFactory.TASK_RECOMMENDATIONS.

    ``sentiment_analysis`` is mapped to xAI Grok in
    ``ospra_os/ai/factory.py`` for a real reason — Grok has live X
    integration, which is exactly what "AI eyes on social sentiment"
    requires. Falling back to Claude is acceptable when xAI is
    unconfigured (Claude can still synthesize evidence we already
    have); but we explicitly do NOT silently fall through to OpenAI
    or Gemini, both of which are mapped to other tasks.
    """
    try:
        from ospra_os.ai.factory import AIFactory
    except Exception as exc:
        logger.warning("sentiment_qualitative: AIFactory unavailable: %s", exc)
        return None, None

    # Honour the explicit task recommendation.
    if os.getenv("XAI_API_KEY"):
        try:
            return "xai", AIFactory.get_provider("xai")
        except Exception as exc:
            logger.warning("sentiment_qualitative: xAI provider failed: %s", exc)

    # Claude is the only acceptable fallback — it's mapped to
    # ``product_analysis`` and ``market_research`` and can do qualitative
    # synthesis of evidence we already have. We don't reach for OpenAI
    # (description_gen) or Gemini (high_volume) here because using them
    # for sentiment would be exactly the cross-purposing the user told
    # us to stop doing.
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return "claude", AIFactory.get_provider("claude")
        except Exception as exc:
            logger.warning("sentiment_qualitative: Claude provider failed: %s", exc)

    return None, None


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a senior e-commerce analyst grading dropshipping products by "
    "reading the actual social evidence available, not numbers. You will be "
    "shown the social evidence we have for ONE product and asked to summarize "
    "the qualitative picture. Be precise. Quote evidence when possible. "
    "Acknowledge data gaps explicitly. If the evidence is too thin to grade, "
    "return polarity='unknown', recommendation='INSUFFICIENT_DATA' rather than "
    "fabricating themes."
)


def _build_prompt(evidence: dict) -> str:
    title = evidence.get("title") or "(unknown)"
    niche = evidence.get("niche") or "general"
    sources = evidence.get("data_sources_available") or []

    prompt_parts = [
        f"PRODUCT: {title}",
        f"NICHE: {niche}",
        f"SOURCES PRESENT: {', '.join(sources) if sources else '(none — return INSUFFICIENT_DATA)'}",
        "",
        "EVIDENCE:",
    ]

    twitter = evidence.get("twitter") or {}
    if twitter:
        prompt_parts.append(
            f"\n--- TWITTER (search_level={twitter.get('search_level')}, "
            f"~{twitter.get('tweet_count', '?')} tweets, polarity {twitter.get('sentiment_label')}/{twitter.get('sentiment_score')}) ---"
        )
        for t in twitter.get("sample_tweets") or []:
            prompt_parts.append(f"  • {t}")
        if twitter.get("common_praise"):
            prompt_parts.append(f"  PRAISE: {', '.join(twitter['common_praise'])}")
        if twitter.get("common_complaints"):
            prompt_parts.append(f"  COMPLAINTS: {', '.join(twitter['common_complaints'])}")

    reddit = evidence.get("reddit") or []
    if reddit:
        prompt_parts.append(f"\n--- REDDIT ({len(reddit)} matches) ---")
        for r in reddit:
            prompt_parts.append(
                f"  • [{r.get('subreddit', '?')} score={r.get('score', 0)} "
                f"comments={r.get('num_comments', 0)} match={r.get('match_type', '')}]: "
                f"{r.get('title', '')}"
            )
            if r.get("excerpt"):
                prompt_parts.append(f"    \"{r['excerpt']}\"")

    amazon = evidence.get("amazon") or {}
    if amazon:
        if amazon.get("review_text_available"):
            # Phase K: per-product review TEXT is present.
            prompt_parts.append(
                f"\n--- AMAZON (aggregate rating {amazon.get('aggregate_rating', '?')} from "
                f"{amazon.get('total_reviews', '?')} reviews; per-product avg "
                f"{amazon.get('per_product_avg', '?')} on ASIN {amazon.get('asin', '?')}, "
                f"verified-share {amazon.get('verified_share', 0):.0%}) ---"
            )
            for t in amazon.get("top_match_titles") or []:
                prompt_parts.append(f"  • Listing: {t}")
            for r in amazon.get("samples") or []:
                rating = r.get("rating")
                stars = f"{rating}★" if rating else "?★"
                verified = " ✓" if r.get("verified") else ""
                helpful = f" (+{r.get('helpful_count', 0)} helpful)" if r.get("helpful_count") else ""
                title_part = f"\"{r.get('title')}\" — " if r.get("title") else ""
                prompt_parts.append(
                    f"  • {stars}{verified}{helpful}: {title_part}\"{r.get('text', '')}\""
                )
        else:
            prompt_parts.append(
                f"\n--- AMAZON (aggregate rating {amazon.get('aggregate_rating', '?')} from "
                f"{amazon.get('total_reviews', '?')} reviews — review TEXT not available, only counts) ---"
            )
            for t in amazon.get("top_match_titles") or []:
                prompt_parts.append(f"  • Listing: {t}")

    # Phase H: actual AliExpress review prose. This is verbatim buyer
    # text, not a paraphrase — quote it sparingly and faithfully.
    ae = evidence.get("aliexpress_reviews") or {}
    if ae:
        prompt_parts.append(
            f"\n--- ALIEXPRESS REVIEWS ({ae.get('count', 0)} reviews, "
            f"avg rating {ae.get('average_rating', '?')}) ---"
        )
        for r in ae.get("samples") or []:
            country = f" [{r.get('country')}]" if r.get('country') else ""
            verified = " ✓" if r.get('verified') else ""
            rating = r.get("rating")
            stars = f"{rating}★" if rating else "?★"
            prompt_parts.append(f"  • {stars}{country}{verified}: \"{r.get('text', '')}\"")

    # Phase J (Instagram) — disabled. No prompt section to render.

    # Phase I: YouTube review videos + viewer comments. Comments are
    # verbatim viewer feedback — quote sparingly and faithfully.
    yt = evidence.get("youtube") or {}
    if yt:
        prompt_parts.append(
            f"\n--- YOUTUBE ({yt.get('review_video_count', 0)} review videos, "
            f"{yt.get('total_views', 0):,} total views, "
            f"{yt.get('total_likes', 0):,} likes) ---"
        )
        for v in yt.get("top_videos") or []:
            prompt_parts.append(
                f"  • Video: \"{v.get('title', '')}\" — {v.get('channel', '?')} "
                f"({v.get('views', 0):,} views, {v.get('likes', 0):,} likes)"
            )
        for c in yt.get("top_comments") or []:
            author = c.get("author") or "?"
            likes = c.get("likes", 0)
            prompt_parts.append(
                f"  • Viewer comment ({author}, {likes} likes): "
                f"\"{c.get('text', '')}\""
            )

    # Phase G: Google Trends context — INTEREST signal, not sentiment.
    # The agent should use these terms to *interpret* sentiment evidence
    # (e.g., if a related search is "smart plug doesn't work" that's a
    # negative-leaning interest signal worth noting), but the agent must
    # NOT treat search volume as polarity.
    gt = evidence.get("google_trends_context")
    if gt:
        prompt_parts.append(
            f"\n--- GOOGLE TRENDS CONTEXT (interest signal, NOT sentiment) ---"
        )
        if gt.get("trend_direction"):
            prompt_parts.append(
                f"  trend_direction: {gt['trend_direction']} "
                f"(primary momentum: {gt.get('primary_momentum', '?')})"
            )
        rqs = gt.get("related_queries") or []
        if rqs:
            prompt_parts.append("  Related searches (people searching for these alongside the product):")
            for q in rqs:
                prompt_parts.append(f"    - {q}")
        prompt_parts.append(
            "  NOTE: search volume = interest, NOT approval. Use the related-query "
            "VOCABULARY as context (e.g. presence of 'doesn't work', 'scam', 'review' "
            "is negative-leaning interest); do NOT treat momentum as polarity."
        )

    prompt_parts.append(
        "\nReturn ONLY valid JSON in this exact shape:\n"
        '{\n'
        '  "polarity": "positive" | "negative" | "mixed" | "neutral" | "unknown",\n'
        '  "themes": ["short specific theme 1", "..."],\n'
        '  "top_wins": ["one-line praise theme", "..."],\n'
        '  "top_objections": ["one-line complaint theme", "..."],\n'
        '  "data_gaps": ["what evidence we lack that would change this read"],\n'
        '  "recommendation": "BUY" | "WATCH" | "SKIP" | "INSUFFICIENT_DATA",\n'
        '  "confidence": 0-100\n'
        '}\n'
        "Be honest about confidence. ONE Reddit post or 5 generic praise tokens "
        "is NOT high confidence. Set 'INSUFFICIENT_DATA' freely."
    )

    return "\n".join(prompt_parts)


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------

async def assess_product(product: dict) -> QualitativeAssessment:
    """
    Run the qualitative agent on one product.

    Safe to call for every discovered product (the caller can cap
    fan-out — this function does not). Returns an assessment with
    ``error`` populated if the AI call failed; never raises.
    """
    evidence = _collect_evidence(product)
    if not evidence["data_sources_available"]:
        return QualitativeAssessment(
            polarity="unknown",
            recommendation="INSUFFICIENT_DATA",
            confidence=0,
            data_gaps=["no social evidence available — twitter, reddit, and amazon all empty"],
        )

    provider_name, provider = _select_provider()
    if provider is None:
        return QualitativeAssessment(
            polarity="unknown",
            recommendation="INSUFFICIENT_DATA",
            confidence=0,
            data_gaps=["AI provider unconfigured — set XAI_API_KEY or ANTHROPIC_API_KEY"],
            error="no provider available",
        )

    prompt = _build_prompt(evidence)

    try:
        # Both Claude and xAI providers expose ``chat`` as the generic
        # text-in / text-out method. We pass system context via the
        # message body since not every provider supports a system field
        # consistently.
        full_prompt = _SYSTEM_PROMPT + "\n\n" + prompt
        raw = await provider.chat(message=full_prompt)
    except Exception as exc:
        logger.warning("sentiment_qualitative: %s call failed: %s", provider_name, exc)
        return QualitativeAssessment(
            polarity="unknown",
            recommendation="INSUFFICIENT_DATA",
            confidence=0,
            provider=provider_name,
            error=f"{type(exc).__name__}: {exc}",
        )

    # Strip markdown code fences if present (Claude sometimes adds them).
    text = (raw or "").strip()
    if text.startswith("```"):
        # Drop leading ```json or ``` and trailing ```
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("sentiment_qualitative: %s returned non-JSON: %s", provider_name, exc)
        return QualitativeAssessment(
            polarity="unknown",
            recommendation="INSUFFICIENT_DATA",
            confidence=0,
            provider=provider_name,
            error="agent returned non-JSON output",
        )

    return QualitativeAssessment(
        polarity=str(parsed.get("polarity", "unknown")),
        themes=list(parsed.get("themes") or [])[:8],
        top_wins=list(parsed.get("top_wins") or [])[:5],
        top_objections=list(parsed.get("top_objections") or [])[:5],
        data_gaps=list(parsed.get("data_gaps") or [])[:5],
        recommendation=str(parsed.get("recommendation", "INSUFFICIENT_DATA")),
        confidence=int(parsed.get("confidence", 0)),
        provider=provider_name,
    )
