# 03 — "THE OSPRA SIGNAL" SHIP SPEC (working name — rename freely)
*The first spin-out: sell the grading engine's OUTPUT as a weekly subscriber drop. Every subscriber is a pre-qualified Ospra SaaS lead (D7). Build now, in parallel — LAUNCH ONLY AFTER THE GATE.*

## PRODUCT
Weekly email + gated web archive. Each issue:
1. **Top 10 graded products** (smart-home/lighting niche to start): grade 0–10, factor breakdown, net-profit calc (AE cost, shipping, platform fees), AE + CJ source links, and the cited "why this wins" analysis.
2. **Movers & fallers** — rank changes vs last week ("#5 → #16") — vision feature #11, productized.
3. **Niche pulse** — one paragraph: rising/stagnant/dying (vision feature #9).
4. Footer, every issue: *"These picks run live on a real store, deployed by Ospra. → Join the Ospra waitlist."*

**Positioning:** the $29–49/mo product-research category (Sell The Trend, Minea, Dropship.io, Ecomhunt) sells static lists from thin data. We sell cross-referenced 10-source scoring + cited reasoning + **a public track record**. Niched (smart home) beats generic in a crowded category; new niches become tiers later (pets tier if F8 wins).

## 🚫 THE LAUNCH GATE (non-negotiable — no exceptions, no soft-launch)
1. ≥ 4 weeks of grade logging (F1) complete
2. Calibration: positive rank correlation grades↔outcome proxies (target Spearman ≥ 0.4; if lower, tune F7 weights and restart the clock)
3. Profit calculator audited against ≥ 10 real fulfilled Oubon orders (projected vs actual margin within ±10%)
4. Harness audits A + B clean: zero silent-failure paths, zero mock-data paths
5. **Receipts page live with ≥ 30 days of public history before the first paid subscriber**

Selling unvalidated grades = the mock-data sin with paying victims + torches the Ospra brand pre-launch. The validation window IS the marketing asset: *"Here's everything we graded 8+ in September. Here's what happened."* Competitors say "trust our AI." We show receipts.

## BUILD (parallel with validation window)
| Piece | What | Effort |
|---|---|---|
| Formatter | Pipeline JSON → branded HTML email + web issue. Reuse Oubon design tokens (dusk/paper/mono). | M |
| Receipts page | Auto-generated from F1 ledger: past grades vs observed outcomes, wins AND misses (honesty = the differentiator). | S (needs F1) |
| Payments | Stripe Payment Link (zero code) → webhook → `subscribers` table. $29/mo, $290/yr. Founding cohort: $19/mo locked for life, first 100. | S |
| Gated archive | Reuse existing JWT auth for subscriber login to back-issues. | S |
| Delivery | Existing email infra, new sender identity — **fully separated from Oubon customer support labeling/loops.** | S |
| Lead magnet | Free dropship profit calculator (the calc, standalone, email-gated) on the landing page. | S |
| Landing page | v0 + Vercel (already connected). Copy: track record first, features second. | S |

## FUNNEL (subscriber → prospect)
```
Free calculator → email list → Signal trial/founding offer
→ weekly value + receipts → Ospra waitlist CTA every issue
→ Ospra SaaS launch: subscribers get founding-user upgrade offer
```
Metrics to log from day one: list growth, trial→paid, churn, waitlist CTR, issue open rate.

## OPS
- **15-min human QA before every send** — checklist: no empty analyses, no "DATA UNAVAILABLE" leaks, links resolve, math sane, no niche-drift picks.
- Cadence: weekly (daily later only if churn data demands it).
- Content framing: our analysis, scores, and links = editorial product. Never republish raw scraped data dumps.
- Churn reality: dropshippers churn hard → push annual, and the Ospra upsell is the real LTV.
