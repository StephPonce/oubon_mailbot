# 02 — OSPRA FEATURE SPEC (Sprint Backlog)
*Eight features. Nearly all are extensions of components that already exist (pipeline, price tracking, deploy engine, webhooks, email infra, GPT-4V). Build order at bottom. F1 is sacred — everything feeds it or reads it.*

---

## F1 · PREDICTION→OUTCOME LEDGER ⭐ (the moat — see 05)
**What:** persist every grade, then join it to what actually happened.
- `grade_snapshots(id, product_id, ts, grade, factor_breakdown JSONB, model_version, prompt_version, pipeline_run_id)` — written by the daily discovery/grading run. Cheap. Do this FIRST.
- `product_outcomes(product_id, period_start, period_end, sessions, orders, revenue, ad_spend, refunds, returns, margin_projected, margin_actual)` — aggregated from Shopify order webhooks (already flowing) + ad APIs.
- `calibration_report` weekly Celery beat: Spearman rank correlation of grades vs outcome proxies (order velocity, sessions→order CVR, AE order velocity for undeployed items). Output to dashboard + logged.
**Touches:** daily pipeline, webhook handlers, new tables, one beat job. **Effort: S–M.** **Everything else depends on this.**

## F2 · FIT GATE (implements `01`)
**What:** deterministic checks (power/control/supplier/economics from listing data) + GPT-4V vision check (finish palette, photo quality, gamer-styling veto) → `fit_pass`, `fit_notes`, `role_assignment`, `scene_candidates`. Runs BEFORE grading; failures logged with reasons.
**Touches:** pipeline stage, existing GPT-4V integration, product model fields. **Effort: M.**

## F3 · SLOT ARCHITECTURE
**What:** the store is roles, not SKUs.
- `scenes(id, handle, title)` seeded from `01` taxonomy.
- `slots(id, scene_id, role, current_product_id, backup_product_ids[], auto_refill bool)`
- Deploy engine (exists) assigns Shopify collection + `scene`/`role` metafields on deploy (**must match metafield schema in `04` — single source of truth**).
- Refill job: supplier health fails (F4) → promote top graded, fit-passing backup → notify admin as a proposed executable action (auto if `auto_refill`). This is the "recommend replacement" behavior from the vision doc, made structural.
**Touches:** deploy engine, new models, notification/action system. **Effort: M.**

## F4 · SUPPLIER SOURCING GRAPH
**What:** extend existing price-tracking into per-product multi-supplier health.
- `supplier_listings(product_id, source ENUM(ae,cj), external_id, url, price, stock, rating, ship_days, last_ok_at, health ENUM(ok,degraded,dead))`
- Health checker beat (reuse price-tracker cadence): price drift %, stockouts, listing 404s, rating drops → events feed F3 refill + dashboard alerts.
- **Graduation tracker:** `sourcing_status ENUM(discovered → validated → cj_requested → cj_stocked)`. When Oubon sales validate a product, submit CJ sourcing request (CJ stocks it; we hold nothing) — CJ becomes the kit/branding fulfillment layer (D9).
**Touches:** price tracker, CJ API client (⚠️ renew token — see ops checklist), new table. **Effort: M.**

## F5 · KIT / BUNDLE ENGINE
- **Phase 1 — soft bundles (ship first, zero risk):** "complete the scene" cross-sells via metafield references + Shopify discount API (buy-2-save-12%) + post-purchase upsell. Pure merchandising; suppliers uninvolved.
- **Phase 2 — hard kits:** validator enforces single-supplier=CJ (consolidated box), kit profit calc = existing profit calculator, multi-item + consolidated shipping; insert-card copy generator ("You lit the desk. The bedroom's next — 15% off") for CJ branded inserts.
**Touches:** profit calc, deploy engine, Shopify Admin API. **Effort: S (P1) / M (P2).**

## F6 · LADDER EMAIL FLOWS
**What:** marketing sibling of the (built) support email system — strictly separate logic/labels from support.
- Order webhook (exists) → tag customer with scenes owned.
- Flows: welcome → post-purchase next-scene (T+14d, excludes owned scenes) → weekly drop (content auto-drafted from discovery pipeline = permanent cadence) → seasonal (Q4 outdoor/holiday) → winback.
**Touches:** webhook handlers, email infra, templates. **Effort: M.**

## F7 · GRADING v2 FACTORS
Add, with versioned weights logged in every snapshot (F1):
- `app_dependency_penalty` (D3) — from F2 control check
- `repeat_purchase_potential` (D4) — category priors + consumable-host bonus
- `brand_fit_score` — from F2 GPT-4V (differentiator: no competitor scores aesthetic fit)
- `supplier_resilience` — count of healthy sources in F4
**Effort: S** (once F2/F4 exist). Never change weights without a calibration-report comparison before/after.

## F8 · NICHE PAPER-TRADING (the pets test — D6)
**What:** run discovery + fit + grading against a niche config with **deploy disabled**; log everything to F1; niche comparison dashboard (avg grade, trend velocity, sentiment, supplier density, projected margins) → 4–6 wk lighting-vs-pets report decides Store #2.
This is also the cross-niche SaaS proof AND a future product ("backtest your store idea").
**Touches:** pipeline config (niche param), dashboard view. **Effort: S** once F1 exists — **start it early.**

---

## BUILD ORDER
```
F1 ledger  →  F2 fit gate + F7 factors  →  F8 pets paper-trade (start clock)
           →  F4 sourcing graph  →  F3 slots  →  F5 P1 soft bundles  →  F6 emails  →  F5 P2 kits
```
## RULES FOR EVERY FEATURE
- Loud failures only — no `except: pass`, no empty-data fallthrough (harness audit B).
- Analysis calls: Sonnet/Opus tier, multi-step, data-source manifest + "DATA UNAVAILABLE" clause in system prompt.
- Migration scripts per model change; tests per endpoint (existing pattern); everything writes to or reads from F1.
