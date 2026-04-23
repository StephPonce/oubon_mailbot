"""
Sentiment Audit — Is it real or are we faking it?
===================================================

Task #15, Step 0: prove (or disprove) that our social sentiment enrichment
is actually reading real tweets and real Reddit posts — not just recording
an LLM's confident guess.

What this script does:
    1. Picks 5 test products across a "known-ness" spectrum:
         - 2 famous products (should have RICH real social data)
         - 2 real products from recent discovery (generic CJ dropship titles)
         - 1 made-up nonsense product (Grok should say "no data" — if it
           returns confident sentiment here, it's hallucinating)
    2. For each product:
         - Calls xAI Grok sentiment (current path + an enhanced path that
           explicitly asks for sample tweet snippets)
         - Calls Reddit public JSON API across the niche's subreddits
         - Prints everything in human-readable form so you can eyeball it
    3. Prints a verdict at the end with the key questions answered.

Usage (from repo root):
    python scripts/audit_sentiment.py

Requires XAI_API_KEY in .env. Reddit uses the public JSON API (no auth).
"""

import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from ospra_os.product_research.connectors.social.xai_twitter import (  # noqa: E402
    XAITwitterDiscovery,
)
from ospra_os.product_research.connectors.social.reddit import (  # noqa: E402
    RedditConnector,
)


# =========================================================================
# TEST PRODUCTS — chosen to expose hallucination vs real reading
# =========================================================================

TEST_PRODUCTS = [
    # ---- FAMOUS: should return rich real data ----
    {
        "title": "Govee RGB LED Strip Lights",
        "category": "famous",
        "niche": "smart_home",
        "why": "Extremely popular smart home product with heavy Twitter discussion",
    },
    {
        "title": "Instant Pot Duo 7-in-1 Pressure Cooker",
        "category": "famous",
        "niche": "kitchen",
        "why": "Iconic kitchen gadget — should have years of Twitter chatter",
    },
    # ---- GENERIC CJ-STYLE: typical dropship title, probably sparse ----
    {
        "title": "3-Pack Smart WiFi Plug Mini Timer",
        "category": "generic_cj",
        "niche": "smart_home",
        "why": "Generic unbranded dropship title — Grok probably has nothing specific",
    },
    {
        "title": "AB34-Smart Touch Switch 4-Gang",
        "category": "generic_cj",
        "niche": "smart_home",
        "why": "Obscure SKU-style title — should return empty/low data if Grok is honest",
    },
    # ---- NONSENSE: trap for hallucination ----
    {
        "title": "ZYX9000 Plasma Photon Kettle Deluxe Edition",
        "category": "nonsense",
        "niche": "kitchen",
        "why": "Does not exist. If Grok returns confident sentiment, IT IS FABRICATING.",
    },
]


DIVIDER_THICK = "=" * 78
DIVIDER_THIN = "-" * 78


def hr(thick: bool = False) -> None:
    print(DIVIDER_THICK if thick else DIVIDER_THIN)


def header(text: str) -> None:
    print()
    hr(thick=True)
    print(f"  {text}")
    hr(thick=True)


def subheader(text: str) -> None:
    print()
    print(f"  ── {text} " + "─" * (max(0, 70 - len(text))))


def pretty_json(obj, indent: int = 2) -> str:
    try:
        return json.dumps(obj, indent=indent, ensure_ascii=False, default=str)
    except Exception:
        return repr(obj)


# =========================================================================
# TEST 1 — CURRENT xAI Grok sentiment path (production prompt)
# =========================================================================

async def probe_grok_current(xai: XAITwitterDiscovery, product: dict) -> dict:
    """Hit the EXACT same method product_discovery.py uses in production."""
    title = product["title"]
    print(f"    → Calling xai.analyze_product_sentiment({title!r})")
    try:
        result = await xai.analyze_product_sentiment(title)
    except Exception as e:
        return {"_error": str(e)}
    return result


# =========================================================================
# TEST 2 — ENHANCED Grok prompt that explicitly demands tweet snippets
# =========================================================================

ENHANCED_PROMPT_TEMPLATE = """Analyze Twitter/X sentiment for this product: "{product_name}"

CRITICAL: Only respond based on ACTUAL tweets you can see. If you cannot find
real tweets about this specific product, set tweet_count to 0 and return an
empty sample_tweets array. Do NOT fabricate tweet text. Do NOT give a default
sentiment when no tweets exist.

For each tweet you cite, paraphrase it honestly (you may rephrase slightly to
avoid direct quotation but the sentiment and content MUST reflect a real tweet
you actually observed).

RESPOND IN JSON FORMAT:
{{
    "product": "{product_name}",
    "found_real_tweets": true/false,
    "sentiment": "positive/negative/neutral/mixed/unknown",
    "sentiment_score": -1.0 to 1.0 (or null if no tweets found),
    "tweet_count": integer (0 if no tweets found),
    "engagement": {{
        "total_likes": integer,
        "total_retweets": integer,
        "total_replies": integer
    }},
    "sample_tweets": [
        {{
            "paraphrase": "What a tweet actually said (paraphrased)",
            "estimated_sentiment": "positive/negative/neutral",
            "influencer_handle": "@handle if notable, else null",
            "approximate_likes": integer
        }}
    ],
    "common_praise": ["specific thing people liked"],
    "common_complaints": ["specific thing people disliked"],
    "honest_note": "If you couldn't find tweets, say so here instead of faking data"
}}"""


async def probe_grok_enhanced(xai: XAITwitterDiscovery, product: dict) -> dict:
    """Direct Grok call with a prompt that demands evidence and an honest
    'found_real_tweets' flag. Lets us compare vs the current production prompt."""
    if not xai.is_available():
        return {"_error": "xAI not configured"}

    title = product["title"]
    prompt = ENHANCED_PROMPT_TEMPLATE.format(product_name=title)

    try:
        response = await xai.client.chat.completions.create(
            model="grok-3",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Grok with real-time Twitter/X access. You MUST "
                        "distinguish between tweets you actually observe and "
                        "educated guesses. Be honest when you have no data."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        content = response.choices[0].message.content

        import re
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            return json.loads(json_match.group())
        return {"_raw": content}
    except Exception as e:
        return {"_error": str(e)}


# =========================================================================
# TEST 3 — Reddit public JSON API
# =========================================================================

SUBREDDIT_MAP = {
    "smart_home": ["smarthome", "homeautomation", "HomeKit"],
    "kitchen": ["Cooking", "KitchenConfidential", "MealPrepSunday"],
    "tech": ["gadgets", "technology"],
    "fitness": ["homegym", "fitness"],
}


async def probe_reddit(reddit: RedditConnector, product: dict) -> dict:
    """
    Try to find real Reddit posts that mention this product.
    Returns the raw posts (title, URL, score, comments) for you to eyeball.
    """
    niche = product["niche"]
    subs = SUBREDDIT_MAP.get(niche, ["shutupandtakemymoney"])
    title_lower = product["title"].lower()

    # Tokenize product title into meaningful keywords (drop stopwords + tiny words)
    stopwords = {
        "the", "a", "an", "and", "or", "for", "with", "of", "to", "in", "on",
        "pack", "mini", "set", "pcs", "pc", "pro", "plus", "new",
    }
    tokens = [
        t.strip("-_,.()[]")
        for t in title_lower.split()
        if len(t) > 3 and t.lower() not in stopwords
    ]
    # Keep the first 3 real keywords (brand + category usually)
    keywords = tokens[:3]

    results = {
        "subreddits_checked": subs,
        "keywords_used_for_match": keywords,
        "matches": [],
        "total_posts_scanned": 0,
    }

    for sub in subs:
        posts = await reddit.get_subreddit_products(sub, time_filter="month", limit=50)
        results["total_posts_scanned"] += len(posts)
        for p in posts:
            post_title = (p.name or "").lower()
            # Require at least 2 keyword overlaps — stricter than production
            overlap = [k for k in keywords if k in post_title]
            if len(overlap) >= 2:
                results["matches"].append(
                    {
                        "post_title": p.name,
                        "post_url": p.url,
                        "subreddit": p.category,
                        "reddit_upvotes": p.social_mentions,
                        "reddit_comments": p.social_engagement,
                        "matched_on_keywords": overlap,
                    }
                )
    return results


# =========================================================================
# MAIN
# =========================================================================

async def audit_product(
    xai: XAITwitterDiscovery, reddit: RedditConnector, product: dict
) -> None:
    header(f"[{product['category'].upper()}]  {product['title']}")
    print(f"  Why chosen: {product['why']}")
    print(f"  Niche: {product['niche']}")

    # --- xAI Grok CURRENT production path ---
    subheader("xAI Grok — CURRENT production prompt (aggregate only, no tweet text)")
    grok_current = await probe_grok_current(xai, product)
    print(pretty_json(grok_current))

    # --- xAI Grok ENHANCED path (asks for tweet snippets) ---
    subheader("xAI Grok — ENHANCED prompt (demands real tweet evidence)")
    grok_enhanced = await probe_grok_enhanced(xai, product)
    print(pretty_json(grok_enhanced))

    # --- Reddit real posts ---
    subheader("Reddit — real posts matching this product")
    reddit_result = await probe_reddit(reddit, product)
    print(f"  Subreddits checked: {reddit_result['subreddits_checked']}")
    print(f"  Keywords used for match: {reddit_result['keywords_used_for_match']}")
    print(f"  Total posts scanned:  {reddit_result['total_posts_scanned']}")
    print(f"  Matches found: {len(reddit_result['matches'])}")
    for i, m in enumerate(reddit_result["matches"][:5], 1):
        print(f"    {i}. r/{m['subreddit']} — '{m['post_title'][:70]}'")
        print(f"       {m['post_url']}")
        print(f"       {m['reddit_upvotes']} upvotes, {m['reddit_comments']} comments")
        print(f"       matched on: {m['matched_on_keywords']}")


def print_verdict(all_results: list) -> None:
    header("VERDICT — Is our sentiment real or fabricated?")

    print(
        """
Look at the output above and ask yourself these questions. I can't answer
them for you — you need to eyeball the actual text Grok returned.

  Q1. For the FAMOUS products (Govee, Instant Pot) — did Grok return
      tweet_count in the hundreds or thousands? Did the ENHANCED prompt
      return specific, plausible tweet paraphrases?
      YES → Grok is reading real Twitter. GOOD.
      NO  → Grok is guessing from training data. BAD.

  Q2. For the NONSENSE product (ZYX9000 Plasma Photon Kettle) — did Grok
      admit it couldn't find tweets? Did found_real_tweets=false and
      tweet_count=0?
      YES → Grok is honest about unknowns. GOOD.
      NO  → Grok is fabricating data for products that don't exist. BAD.

  Q3. For the GENERIC CJ dropship products — did Grok return a nearly
      identical low sentiment_score (~0.1 / 0.2) for all of them?
      YES → This is exactly the uniform-58 problem in production.
             Grok has nothing specific and defaults to mild-positive filler.
      NO  → Each got a distinct read. GOOD.

  Q4. Reddit — did the matches actually correspond to the products, or is
      the keyword match too loose/too tight?
      Look at the matched_on_keywords list per match.

Once you've eyeballed this, tell me what you see and I'll:
  - Ship the Grok prompt enhancement (the ENHANCED prompt used above)
  - Start persisting twitter_evidence and reddit_evidence on products
  - Add the 'No social signal yet' null path in scoring
  - Widen Reddit subreddit coverage to the SUBREDDIT_MAP above
"""
    )


async def main() -> int:
    header("SENTIMENT AUDIT — is it real?")

    xai = XAITwitterDiscovery()
    reddit = RedditConnector(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    )

    if not xai.is_available():
        print("  ❌ XAI_API_KEY not set — cannot probe Grok.")
        print("     Add it to .env and rerun.")
        return 1

    print(f"  ✓ xAI Grok: configured (model: grok-3)")
    print(f"  ✓ Reddit:   public JSON API (no auth)")
    print(f"  ✓ Probing {len(TEST_PRODUCTS)} products across 3 honesty categories\n")

    all_results = []
    for product in TEST_PRODUCTS:
        try:
            await audit_product(xai, reddit, product)
            all_results.append(product)
        except Exception as e:
            print(f"  ❌ Audit failed for {product['title']}: {e}")
        # Grok + Reddit both have rate limits; small buffer between probes
        await asyncio.sleep(1.0)

    print_verdict(all_results)
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
