# 00 — MASTER HANDOFF: Ospra × Oubon
*Source of truth distilled from the full strategy session (Aug 2026). Read this first in every Claude Desktop / Claude Code session. Files 01–05 are the execution specs.*

---

## HOW TO USE THIS PACKAGE

| Session | Load |
|---|---|
| Claude Code — Ospra repo | This file + `01` + `02` (+ `03` when building the feed) |
| Claude Code — Oubon theme repo | This file + `04` + `OUBON-DESIGN-BRIEF.md` (as repo `CLAUDE.md`) |
| Claude Desktop — planning/strategy | This file + `05` |

---

## CONTEXT SNAPSHOT

**Ospra Intelligence** — AI e-commerce automation platform. FastAPI + Celery/Redis, React/Vite UI, JWT auth (48 endpoints), 61/61 system tests passing. 10 data sources: AliExpress (Affiliate 522382 + Dropshipping 520918), CJ Dropshipping, TikTok + Amazon via Apify, xAI sentiment, Reddit, Google Trends. Shopify OAuth + 19 webhooks + 3 GDPR endpoints live. Hybrid GPT-4V + Stability image pipeline deployed. Render production.

**Oubon Shop** (oubonshop.com) — dogfood store. Current state: stock default theme untouched, 3 Ospra test products (one URL literally prefixed `test-`), empty meta description, no branding. Ground zero — which is fine; nothing to untangle.

**Strategy:** dogfood on Oubon → validate the engine → SaaS.

## THE CORE DISTINCTION (drives everything)

**61/61 tests = VERIFICATION (the machine runs). We have zero VALIDATION (the machine is right).**
No grade has ever been compared to a real outcome. The profit calculator has never been audited against a fulfilled order. The self-learning loop has nothing to learn from because outcomes aren't logged. Nothing ships to paying customers until validation gates pass (see `03`).

---

## DECISIONS LEDGER (settled in session — don't relitigate without new data)

- **D1** Oubon stays on the Shopify theme system. NO headless/Hydrogen — Ospra's auto-deploy depends on standard theme product rendering.
- **D2** Brand = umbrella **"smart home essentials"** (v2: "The useful kind of smart."). Launch wedge = **lighting**, with lighting-forward hero copy (v1: "Good light is a tool."). Wedge ≠ identity; store grows into umbrella as data justifies.
- **D3** **App-optional catalog only.** Connected devices requiring apps/hubs/wifi (cams, hubs, wifi plugs) are excluded — firmware/support/ecosystem-trust costs punish dropship. App-dependency = grading penalty.
- **D4** **Repeat-purchase weighting** added to grading (lighting's structural flaw = low repeat purchase; grader must see it).
- **D5** Catalog is built on the **Fit Gate + Slot architecture** (`01`, `02`) — roles, not SKUs. Supplier churn refills slots; store never breaks.
- **D6** **Lighting validates LIVE on Oubon. Pets validates ON PAPER in parallel** (Ospra discovery+grading, deploy disabled, 4–6 wks). Winner earns Store #2. This doubles as the cross-niche SaaS test.
- **D7** First spin-out = the **subscriber feed** (`03`). Subscribers are pre-qualified Ospra leads. HARD-GATED on validation. Launch with a public receipts page, never "trust our AI."
- **D8** **Hero products ≥ $50 AOV.** Sub-$25 items are accessories/add-ons, never heroes. (One-and-done category ⇒ must profit on order #1.)
- **D9** Supplier model: **AE = discovery pool, CJ = fulfillment + kit + branding layer.** Proven winners graduate via CJ sourcing requests (CJ stocks it; we still hold zero inventory). Kits ship single-supplier (CJ consolidation + branded inserts).
- **D10** **The Prediction→Outcome Ledger is the sacred core** (`02` F1, `05`). Every feature must feed it or read it. It is the moat.

## REVENUE-FLAW WORKOUT (lighting's low repeat purchase — the 5 plays)
1. **The Ladder** — Hue's model, merchandising layer only: scenes are rungs; every unowned scene is the next sale.
2. **Bundles/AOV** — soft bundles → hard kits (CJ). Cheapest 15–25% revenue lift.
3. **Consumable Trojan horse** — diffuser-lamps + candle-warmer lamps ⇒ oils/wax melts = repeat SKU inside a lighting brand.
4. **Email = the LTV machine** — Ospra's weekly discovery = permanent drop cadence (competitors go stale; we never do).
5. **Gifting + seasonality** — Q4 outdoor/holiday is the harvest.

## KNOWN ENGINE FLAWS (chat-Claude ≫ Ospra-Claude — same brain, broken harness)
1. No agentic loop (one-shot prompts vs search→read→cross-reference→synthesize)
2. Context assembly failures (truncated/thin data in ⇒ plausible filler out)
3. Silent API failures (`except: data=[]` ⇒ confident garbage downstream) — the mock-data disease, new face
4. No honesty clause ("DATA UNAVAILABLE" > inference — must be in every system prompt)
5. Model/params misallocation (analysis needs Sonnet/Opus tier + adequate max_tokens, never Haiku)
6. No eval gate (prompts have no regression tests)

---

## AUDIT BRIEFS (run these in the Ospra repo FIRST — Sprint 0)

### A. Intelligence/Grading Audit
```
1. GRADE INTEGRITY — trace 0–10 scoring end to end: every factor,
   weight, data source. Hunt mocked/hardcoded/fallback values:
   grep -rn "mock\|placeholder\|TODO\|FIXME\|HACK\|dummy"
2. GRADE LOGGING — do daily grades + factor breakdowns persist?
   If not, spec table + write path (blocks ALL validation → 02/F1).
3. PROFIT CALCULATOR — list every cost assumption; live vs hardcoded.
4. SELF-LEARNING — any code path writing real outcomes back into
   scoring, or design-only?
5. PRODUCTION TRUTH — diff local vs Render env; CJ creds status;
   vars set locally but missing in prod.
6. DELIVERABLE — OPEN_ISSUES.md ranked: (a) blocks validation
   (b) blocks SaaS (c) cosmetic. Flag "looks functional but isn't."
```

### B. LLM Harness Audit
```
1. Dump FULL prompt + raw response for 3 recent analyses —
   what data actually reached the model?
2. Grep exception handlers that swallow API failures and pass
   empty/partial data downstream. Make them LOUD.
3. Check model + max_tokens per analysis endpoint.
4. System prompts: add data-source manifest + "DATA UNAVAILABLE
   over inference" clause.
5. Convert one-shot analysis to multi-step: plan → fetch →
   per-source summary → synthesis. Add Anthropic server-side
   web_search tool.
6. Golden set: 5 known-good analyses; score pipeline output
   against them on every prompt/model change.
```

## OPS CHECKLIST (fast, unblocking)
- [ ] **CJ API token — likely EXPIRED** (was valid until Dec 31, 2025; it is now Aug 2026). Verify/renew before any CJ work.
- [ ] Configure CJ supplier credentials in Render production
- [ ] Shopify Partner app: obtain SHOPIFY_API_KEY / SECRET, release config (SaaS OAuth blocker)
- [ ] oubonshop.com: fix empty meta description; rename/redeploy `test-` prefixed product URLs
- [ ] Create scene collections (see `04`)
- [ ] Flag for SaaS roadmap: Gmail restricted scopes ⇒ CASA assessment required before customer inboxes connect

## SEQUENCING
```
SPRINT 0  Audits A+B · ops checklist · F1 outcome ledger        ← everything waits on this
SPRINT 1  Fit gate (F2) · grading v2 factors (F7) · start pets
          paper-trade (F8) · start lighting calibration clock
SPRINT 2  Theme build (04) · imagery via image pipeline ·
          sourcing graph (F4) · slots (F3)
SPRINT 3  Feed build (03) in parallel with validation window ·
          soft bundles (F5) · ladder emails (F6)
GATE      Validation criteria in 03 pass → feed launches with
          public receipts · Store #2 decision from F8 data
```
