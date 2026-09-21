---
name: ospra-niche-analysis
description: Scores and compares niches or sub-niches for a store (demand trend, saturation, supplier density, margins, repeat-purchase potential, app-dependency, ad-demo-ability, seasonality, brand fit) and runs the paper-trade protocol for validating a niche before committing. Use this whenever asked whether a niche/category/market is worth entering, to compare niches (e.g., lighting vs pets), to produce a weekly niche pulse (rising / stagnant / dying), or to set up or interpret a niche paper-trade — even for a casual "is X a good niche?"
---

# Ospra Niche Analysis

Listicle market sizes are vanity metrics: most of a "$165B pet market" is food, vet care, and services no dropship store can touch. Judge a niche by the slice a specific store can actually address and by the operational physics of selling in it — not by the headline number. Guts pick candidates; data picks winners.

## Metrics (score each 0–10, show the evidence)
1. **Demand trend** — 12-month + 90-day direction and velocity (Trends, TikTok, search)
2. **Addressable slice** — what share of the market is dropship-sellable at ≥ 60% gross margin
3. **Saturation** — count of stores/ads/listicles pushing the same products; "most recommended niche" is a penalty, not a bonus
4. **Supplier density & quality** — number of suppliers meeting the fit-gate G5 floor
5. **Margin reality** — landed cost vs. retail after 10–25% true-net assumptions
6. **Repeat-purchase potential** — structural repeaters (consumables, destructibles) vs. one-and-done
7. **App-dependency share** — how much of the category needs apps/hubs (penalty)
8. **Ad demo-ability** — can the product prove itself in 3 seconds of video?
9. **Seasonality** — peaks/troughs and what they do to cash flow
10. **Brand fit** — coherence with the store's identity (a niche that breaks brand is a Store #2 candidate, not a pivot)
Also note **liability class** explicitly: ingestibles, topicals, and safety-critical items cap the niche's best features.

## Method
Run the same source loop as `ospra-product-intel`, at category level: plan sources → fetch one at a time → per-source summary → cross-reference → score → verdict. Open with a source manifest; mark `DATA UNAVAILABLE` where a source failed; grade `PROVISIONAL` if 3+ sources are missing. Never infer numbers you did not retrieve.

## Weekly pulse format (feature #9)
```
NICHE: … | STATUS: rising | stagnant | dying
EVIDENCE: 3 bullets with retrieved figures
MOVERS: sub-niches/products gaining or losing rank vs last week
ACTION: expand / hold / trim / paper-trade
```

## Paper-trade protocol (validate before committing)
1. Configure discovery + fit gate + grading for the candidate niche with deploy DISABLED
2. Log every grade + source manifest to the ledger daily for 4–6 weeks
3. Track observable proxies weekly: trend delta, TikTok velocity, AE order velocity, supplier health
4. Compare against the live niche on the same metrics, same window
5. Verdict: the niche earns a store only if its proxies and calibration beat the incumbent AND its liability class is acceptable

## Verdict format
`SCORECARD (10 metrics)` → `VERDICT: enter / paper-trade / pass` → `WHY (evidence-anchored)` → `WHAT WOULD CHANGE THE VERDICT` → `LIABILITY NOTES`
