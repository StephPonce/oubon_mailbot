# Pricing (Pass 4 ladder)

Three things live here: the SaaS tier ladder, the standalone module SKUs, and the white-glove tier. These are design decisions — LemonSqueezy variant IDs are env-configured.

---

## SaaS tier ladder

| Tier | Monthly | Yearly | Products/week | Per-request ceiling | Stores | Support AI |
|---|---|---|---|---|---|---|
| **Nest** | $0 | — | 10 | 10 | 1 | preview only |
| **Flight** | $29 | $290 (save 2 mo) | 50 | 25 | 1 | 100 replies/mo |
| **Soar** | $79 | $790 | 250 | 50 | 3 | 1,000 replies/mo |
| **Stratosphere** | $199 | $1,990 | 1,500 | 100 | 10 | unlimited |

- `products_per_week` is the weekly cap (enforced by middleware).
- `per-request ceiling` (Task #6, locked Pass 4) caps a single `/api/discovery/products` call so Nest can't chain-request a week's quota in 30 seconds.
- "Support AI" = Gmail automation. Preview = drafts shown but not sent.

### Upgrade nudges (to wire in Pass 5)
- Clamp event (`tier_meta.clamped = true`) → toast: "You asked for N, your tier caps at M. Upgrade to see the rest."
- Weekly quota 80% consumed → banner at top of dashboard.
- Hitting store limit → inline upsell on the "Add Store" button.

---

## Standalone modules ($49 / $149)

Sold separately, API-gated, no dashboard. For merchants who already run their own stack and just want our outputs piped in.

| SKU | Price | What you get |
|---|---|---|
| **Discovery API** | $49/mo | `/api/discovery/products` with Soar-tier ceilings, no deploy pipeline. |
| **Discovery + Support API** | $149/mo | Above + Gmail automation endpoints, BYO OAuth. |

- Same underlying tenant model — just a different subscription SKU on the tenant.
- Rate-limited per-API-key, billed by LemonSqueezy.

---

## White-glove onboarding — $499

**This is a SIGNUP tier, not a sales upsell.** New merchants see it as the fourth option on the pricing page.

What they get in month one:
- Human-managed Shopify store setup (theme, pages, domain, legal templates).
- First 30 days of discovery curation — we hand-pick 10 products for them each week.
- 1:1 weekly check-in call (30 min).
- Full Stratosphere access during the 30 days.

After month one: they roll onto Stratosphere ($199/mo) automatically, or cancel.

**Why it's priced at $499, not $2k+:**
- Target persona has $500–$2k in liquid ecomm budget. $2k tier would be 4x their willingness to pay.
- We're betting that onboarding quality is the #1 predictor of 6-month retention.

---

## Rules of thumb (the user's explicit ones — don't override)

1. **Never quietly raise prices.** Grandfather existing subs forever.
2. **Annual always saves 2 months** — no fancier math.
3. **No trials that auto-charge.** Nest is free forever, and the paid tiers are month-to-month. White-glove is 30 days then auto-rolls to Stratosphere — we make that explicit at signup.
4. **No "Enterprise — call us".** Every tier has a number on it. If someone needs custom, we quote them on a 3-month SOW outside of the subscription product.

---

## Competitive frame (cross-ref `competitors.md`)

- Dropship.io: $29–$99 — product research only, no deploy, no support AI.
- Minea: $49–$399 — ad-spy + product research, no deploy, no support AI.
- AutoDS: $17–$297 — deploy + fulfillment, thin discovery, no sentiment layer.
- Shine Ranker: $67/mo — SEO-flavored, not Shopify-native.

**Our wedge:** Soar at $79 beats everyone on the discovery+deploy+support combo. Stratosphere at $199 is the only tier on the market that includes tenant-fine-tuned support replies.
