# Competitive Landscape

Who's in the market, what they do, and where our wedge is. Update quarterly or when someone ships a major feature.

---

## Direct competitors — product research / discovery

| Tool | Price | What it does well | What it misses |
|---|---|---|---|
| **Dropship.io** | $29–$99 | Large product catalog, decent trend signals, clean UI | No deploy, no support AI, no sentiment analysis — just a search engine |
| **Minea** | $49–$399 | Strong ad-spy (Facebook, TikTok, Pinterest ads), influencer tracking | Expensive for what it is, no Shopify deploy, no support layer |
| **PPSpy** | $24–$70 | Shopify-store spying (what are my competitors selling?) | Spy only, zero workflow |
| **Shine Ranker** | $67 | SEO + keyword angle on product research | Not Shopify-native, weak supplier layer |
| **Niche Scraper** | $49 | Fast catalog scraping, product reviews aggregation | No grading or scoring, raw-data feel |

## Direct competitors — deploy / automation

| Tool | Price | What it does well | What it misses |
|---|---|---|---|
| **AutoDS** | $17–$297 | Mature fulfillment integrations, auto-order routing | Shallow discovery, no sentiment layer, no AI grading |
| **Spocket** | $39–$299 | US/EU suppliers curated | Supplier catalog is a walled garden, no broader discovery |
| **DSers** | $19–$499 | AliExpress bulk-order management | Pure fulfillment, no intelligence layer |
| **Zendrop** | $49–$199 | Product catalog + semi-private US warehouse | No social sentiment, no support AI |

## Direct competitors — support automation

| Tool | Price | What it does well | What it misses |
|---|---|---|---|
| **Gorgias** | $10–$360+ | Shopify-native helpdesk, macro automations | Rule-based, not truly AI-drafted; enterprise-flavored pricing |
| **Tidio** | $29–$749 | Live chat + chatbot, AI replies | Not dropshipping-aware; doesn't know about AliExpress tracking quirks |
| **Re:amaze** | $29–$79 | Multi-channel inbox | Thin AI layer, no tenant fine-tune |

## Adjacent / watchlist

- **Shopify Magic / Sidekick** (Shopify's built-in AI). Free. Could eat part of our deploy+support layer if it ships product discovery. **Threat level: high.** Monitoring.
- **TikTok Shop's own analytics**. Free to TikTok Shop sellers. Threat to a Pinterest/TikTok-signal-only play.
- **Klaviyo + AI (2025 launch)**. Email/SMS heavy — complementary, not competitive. Could partner.

---

## Our five edges (Pass 4 positioning)

These are our durable differentiators. Each should stay on the roadmap until a competitor matches it.

1. **Sentiment-layered opportunity scoring** — Amazon reviews (Apify) → AliExpress reviews → CJ supplier-quality proxy. No other tool combines all three into a single score. See `memory/decisions.md#D6`.

2. **"Why we scored this" explainer** — every graded product ships with a plain-English breakdown of the margin, trend, saturation, and sentiment components. Competitors show a score; we show the math. Visible on grading detail pages.

3. **Refund-risk predictor** — roadmap. Predict refund rate from supplier history + product category + sentiment spread before the merchant commits inventory. Nothing in the market does this today.

4. **Tenant-fine-tuned support replies** — Gmail automation learns each tenant's policy, voice, and refund rules (stored per-tenant in `ospra_os/tenancy/policies.py`). Gorgias rules are generic macros; ours are drafted by a tenant-scoped prompt.

5. **Agency mode + embed mode** — roadmap (#38+). Multi-tenant dashboard for agencies (manage 3–15 clients from one login) + white-label embed (our discovery widget on your consultancy's website). Unlocks the tertiary segment.

---

## What we DON'T try to beat

- **Shopify's native ecosystem fit.** We integrate, we don't compete.
- **Gorgias at the enterprise end.** $10k+/yr merchants are not our buyer.
- **AutoDS's fulfillment depth.** They have 5 years of order-routing logic we won't match — we stop at "deploy to Shopify" and let them or DSers handle the fulfillment side if needed.

---

## Trigger conditions — when to escalate response

- Dropship.io ships a deploy pipeline → accelerate our support-AI marketing (it's the moat they can't copy in a quarter).
- Shopify Magic ships product discovery → pivot Nest tier's pitch to "we do what Shopify can't: sentiment + supplier grading."
- Gorgias drops tenant-fine-tuned AI replies → ship refund-risk predictor faster; that's the next wedge.
