# Target Customer (Pass 4 — broadened)

We broadened this in Pass 4. The old framing ("scaling dropshippers doing $50k+/mo") was the top 0.1% — ~5k merchants globally. Real TAM is ~400k merchants. Theoretical ARR ceiling at 1% capture + $50/mo blended ARPU ≈ $24M/yr.

---

## Who we're building for

**Primary — "The Overloaded Operator"**
- Runs a Shopify or WooCommerce store doing $2k–$50k/month.
- 1–3 person operation (often solo + VA).
- Spends **>4 hrs/week** on product sourcing OR **>4 hrs/week** on customer support.
- Has tried one of: Dropship.io, Minea, PPSpy, AutoDS, Shine Ranker — found them either too shallow (just trending feeds) or too broad (scraper dumps with no grading).
- Buys tools. Has an existing $50–$300/mo stack.

**Secondary — "The Aspiring Seller"**
- Pre-launch or <$2k/mo.
- Wants a done-for-you store or heavy guidance — this is the white-glove tier ($499).
- NOT the $29 Flight tier's user — that's a graduation path for the primary persona.

**Tertiary — "The Agency Operator"**
- Runs stores for 3–15 clients.
- Needs multi-store management, white-label dashboards, tenant-level fine-tuning.
- Maps to the future "Agency Mode" on the Stratosphere tier.

---

## Who we're NOT for

- **TikTok-first social sellers** who don't operate a Shopify store. They live in TikTok Shop natively and don't need our deploy pipeline. (We'll read their data via the TikTok Shop API — task #36 — but they're not our buyer.)
- **Brand-owned D2C doing >$500k/mo.** They hire agencies and buy Gorgias / Klaviyo enterprise. Our discovery layer is anti-pattern for them — they don't pivot products weekly.
- **Arbitrage/liquidation resellers** (eBay, Mercari). Fundamentally different workflow — no catalog, no supplier integration.

---

## Pains we solve (ranked by session-one observation frequency)

1. **"I don't know which product to try next."** → discovery + sentiment scoring + grading lock.
2. **"I'm drowning in support tickets."** → Gmail automation + AI reply drafts (tenant-fine-tuned per policy).
3. **"My supplier quality is a black box until refunds roll in."** → CJ supplier-quality proxy + refund-risk predictor (roadmap).
4. **"I can't tell my winners from my coin-flips before buying inventory."** → opportunity scoring + variance-locked grading.
5. **"Setting up a new store is 2 weeks of setup work."** → white-glove tier.

---

## Where they hang out (for GTM)

- r/dropship, r/shopify, r/ecommerce (reddit)
- Shopify App Store reviews of competitor apps
- YouTube: channels in the "realistic dropshipping" niche (not the "I made $10k in a day" clickbait)
- TikTok: #ecommercetips, #shopifyseller
- Discord: "Dropship Lifestyle", "Ecom Empires"
- NOT: LinkedIn (the aspirational-founder crowd is a bad signal)

---

## Things that change once we ship #36–#38

- TikTok Shop API integration pulls the tertiary into primary — agencies managing TikTok Shop clients become a real segment.
- PostHog funnel data will replace half of this file with actual observed behavior. Rewrite this doc quarterly once we have it.
