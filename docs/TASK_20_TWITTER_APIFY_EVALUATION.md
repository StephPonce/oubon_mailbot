# Task #20 — Twitter Sentiment: Grok vs Apify Evaluation

**Status**: Decision memo · Awaiting user go/no-go
**Date**: 2026-04
**Owner**: Intelligence layer / sentiment pipeline
**Related**: Task #18 (Amazon Reviews via Apify), Task #17 (4-hour sentiment refresh)

---

## TL;DR

**Recommendation**: Add an Apify twitter-scraper connector as the *primary* Twitter sentiment source, demote Grok to a qualitative-only fallback. Keep both, gated behind `APIFY_TWITTER_ENABLED=true`.

**Why**: Grok is honest-but-weak — it paraphrases from training data, not live posts.
That's a genuine product truth (the code comment in `xai_twitter.py` already says so),
and it undercuts the stated Ospra differentiator of "live and updated social sentiment."
Apify scraper actors return verbatim live tweets with real engagement counts, for roughly
the same cost per run as Grok.

---

## Current state (post Task #15 fixes)

### What Grok actually does

The Grok integration in `ospra_os/product_research/connectors/social/xai_twitter.py`
calls `grok-3` via the xAI OpenAI-compatible endpoint and asks it to summarize
recent tweets about a product. After the Task #15 evidence-trail work, we're
honest about what comes back:

- `found_real_tweets` flag: usually false for long-tail products
- `sample_tweets`: **paraphrased by the model from training data**, not verbatim
- `engagement`: synthetic / estimated, not live counts
- `sentiment_score`: based on model's internalized priors, not on current tweets
- `source_type: 'grok_paraphrase'` — surfaced in the UI so users don't mistake it for live

This is honest but structurally limited:

1. **Stale**: Grok's training data is weeks or months behind for long-tail SKUs.
2. **No verifiability**: The user cannot click through to the real tweet.
3. **Low signal on new products**: A product that just went viral on TikTok
   won't show up at all because Grok never trained on those recent tweets.

### What the docs claimed

`docs/X_TWITTER_SENTIMENT_API.md` (dated Dec 2025) claims Grok is "real-time"
and marks it as ✅ production-ready. This contradicts the in-code reality.
**Action item** regardless of the Apify decision: update that doc to reflect
the paraphrase caveat.

---

## Apify twitter-scraper landscape

Apify has multiple live twitter-scraper actors; the three worth considering:

| Actor | Type | Approx cost | What it returns |
|-------|------|-------------|-----------------|
| `apidojo/tweet-scraper` | Keyword search | ~$0.40 / 1k tweets | Live verbatim tweets, engagement, author, timestamp |
| `u6ppkmwc7kg8ee/twitter-scraper-lite` | Profile + search | ~$0.30 / 1k tweets | Same shape, slightly older snapshots |
| `gentle_cloud/twitter-scraper-lite` | Keyword | ~$0.25 / 1k tweets | Engagement + some media URLs |

All three return the same core shape: `id`, `text`, `created_at`, `likeCount`,
`retweetCount`, `replyCount`, `viewCount`, `author.username`, `url`. Crucially
they produce **verbatim tweets that the user can click**, not paraphrases.

### Cost math

Current discovery (per niche):
- Amazon Reviews Apify call: ~$0.02-0.05
- Grok Twitter call (if enabled): ~$0.02 per product × 20 products = ~$0.40

Proposed with Apify Twitter:
- Amazon Reviews: unchanged, ~$0.02-0.05
- **ONE** Apify twitter-scraper call per niche pulling ~100 tweets: ~$0.04
- Fuzzy-match each of our 15 supplier products against the tweet pool
  (same pattern as `amazon_reviews.py:match_products`)

Net: **cheaper than Grok** per discovery (~$0.04 vs ~$0.40), and the signal is
live rather than paraphrased.

### Rate limits & reliability

Apify actors can return 429s / empty pools when Twitter's anti-scrape
rotates; mitigation is the same cache-with-TTL + fail-open pattern we already
use for `AmazonReviewsConnector`:

```python
# Proven pattern from amazon_reviews.py
AMAZON_CACHE_TTL_SECONDS = int(os.getenv("AMAZON_CACHE_TTL_SECONDS", "7200"))
# Would become:
TWITTER_CACHE_TTL_SECONDS = int(os.getenv("TWITTER_CACHE_TTL_SECONDS", "3600"))
```

---

## Proposed integration

### New file
`ospra_os/product_research/connectors/social/apify_twitter.py`

Class shape mirrors `AmazonReviewsConnector`:
- `search_niche(niche, max_tweets=100, min_engagement=5)` — one Apify call per niche
- `match_products(our_product, tweet_pool, top_n=3, min_similarity=0.20)` — fuzzy match
- Evidence shape identical to `amazon_evidence` but source-tagged `'apify_twitter'`:

```python
product['twitter_evidence'] = {
    'found_real_tweets': True,
    'search_level': 'product' | 'category',
    'tweet_count': int,
    'sentiment_score': 0-100,  # from verbatim text sentiment, not paraphrase
    'sample_tweets': [
        {
            'text': str,            # VERBATIM
            'url': str,             # clickable https://x.com/...
            'author': str,
            'likes': int, 'retweets': int, 'replies': int,
            'created_at': ISO8601,
        },
        ...
    ],
    'engagement': {'total_likes': int, 'total_retweets': int, 'total_replies': int},
    'fetched_at': ISO8601,
    'source_type': 'apify_live_scrape',  # NOT 'grok_paraphrase'
}
```

### Changes to `product_discovery.py`

In `_init_sentiment_sources`, prefer Apify when `APIFY_TWITTER_ENABLED=true`:

```python
# Prefer live Apify scrape over Grok paraphrase
if os.getenv('APIFY_TWITTER_ENABLED', 'false').lower() == 'true' and self.apify_token:
    self.apify_twitter = ApifyTwitterConnector(api_token=self.apify_token)
    self.twitter_source = 'apify'
    self.xai_available = False  # prevent both firing
elif xai_key:
    self.xai_twitter = XAITwitterDiscovery(api_key=xai_key)
    self.twitter_source = 'grok'
```

And `_enrich_with_twitter_sentiment` branches on `self.twitter_source`.

### UI surface

The existing Task #15 evidence panel already renders `source_type`, so the
caller gets "live" or "paraphrase" labels for free. Users who opt into Apify
get clickable verbatim tweets; users who don't still get the (honest) Grok
paraphrase.

---

## Decision matrix

| Criterion | Keep Grok only | Add Apify (recommended) | Apify only (drop Grok) |
|-----------|---------------|------------------------|-----------------------|
| Live vs paraphrase | Paraphrase only | **Live primary + Grok fallback** | Live only |
| Clickable evidence | No | **Yes for Apify tier** | Yes |
| Cost per discovery | ~$0.40 | ~$0.04 | ~$0.04 |
| Fallback if Apify 429s | N/A | **Grok still available** | Cold for that niche |
| Eng effort | 0 (nothing to do) | ~1d (copy the Amazon pattern) | ~1d + coverage gaps |
| Matches differentiator | Partially (honest about limits) | **Yes** | Yes |

---

## Recommendation

**Proceed with option 2 ("Add Apify, keep Grok as fallback")**:

1. Build `ApifyTwitterConnector` following `amazon_reviews.py` almost verbatim.
2. Gate via `APIFY_TWITTER_ENABLED=true` (default off, roll out behind a flag).
3. When on, it becomes the primary Twitter source; Grok stays wired as a
   graceful fallback for niches where Apify returned an empty pool.
4. Update `docs/X_TWITTER_SENTIMENT_API.md` to reflect the paraphrase caveat
   and the new Apify path.
5. UI: keep the existing evidence panel — `source_type` already differentiates.

This is a **low-risk, high-honesty** change. It extends the same
proven-in-production Apify pattern (Amazon + Google Trends) to Twitter, makes
the sentiment tier live instead of paraphrased, and is *cheaper* than the
current Grok setup while preserving Grok as a safety net.

**Est. effort**: 1 engineering day.

---

## What would stop this?

1. **Apify bans Twitter scraping again**: has happened historically. Mitigation:
   keep Grok as fallback, fail open.
2. **Cost spike on high-niche-churn users**: If a user adds 50 niches, we
   run 50 scrapes per refresh. Mitigation: cache TTL + per-user niche cap
   (already enforced elsewhere).
3. **Legal risk**: Apify markets these actors as compliant with Twitter's public
   data. Not legal advice; flagging for the user to confirm with their counsel
   before enabling in prod.
