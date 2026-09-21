---
name: ospra-product-intel
description: Runs Ospra's multi-source research loop to grade a product 0–10 and write the cited "why this will or won't win" analysis, with an explicit data-source manifest and a hard honesty clause. Use this whenever asked to research, analyze, score, grade, rank, or explain a product's potential, produce an "AI analysis" or market analysis for a product, or write/modify the analysis pipeline, prompts, or grading code — even for casual asks like "what do you think of this product?"
---

# Ospra Product Intelligence

Chat-Claude beats pipeline-Claude for one reason: chat runs a loop (search → read → cross-reference → verify) while pipelines run one prompt. This skill is the loop, written down. Follow it whether you are analyzing a product by hand or building the code that does.

## The loop
1. **Plan** — list which sources you will consult for THIS product: AliExpress/CJ listing data (price, orders, rating, ship time), Amazon comparables (price band, review volume/sentiment), TikTok velocity, Reddit sentiment, Google Trends (12-mo + 90-day), competitor saturation (how many stores sell it). Web search when a source tool is unavailable.
2. **Fetch per source, one at a time.** For each: record what returned, its date/freshness, and its key numbers. If a source errors, returns empty, or is unavailable, record `DATA UNAVAILABLE — <source>` and continue. Never let an empty result silently become a blank in the analysis.
3. **Per-source summary** — 2–3 lines each, numbers included.
4. **Cross-reference** — where do sources agree/disagree? Disagreement is signal (TikTok spiking while AE orders stay flat = early wave OR fake buzz; decide which and say why).
5. **Grade** using the factor rubric.
6. **Write up** using the template. Cite the specific numbers you actually retrieved.

## Honesty clause (non-negotiable)
- Every analysis opens with the **source manifest**: which sources returned data, which did not, and how fresh each is.
- Never infer a number you didn't retrieve. "Trend rising" without a retrieved trend figure is fabrication.
- If 3 or more core sources are unavailable, mark the grade `PROVISIONAL` and say what would firm it up.
- Confidence is a field, not a vibe: state it and state its cause.

## Grading factors (0–10 composite; log every factor separately)
- **Demand trend** — direction + velocity (Trends, TikTok)
- **Sales evidence** — AE/Amazon order velocity, review volume
- **Sentiment** — buyer/commenter sentiment quality, complaint themes
- **Saturation** — # of stores/ads running it; late-wave penalty
- **Margin** — landed cost vs. realistic retail (assume 10–25% true net after ads/fees, not guru math)
- **Repeat-purchase potential** — category prior; consumable-host bonus
- **App-dependency penalty** — apps/hubs/wifi required = penalty
- **Brand fit** — from the fit gate result
- **Supplier resilience** — number of healthy sources
Weights are versioned in code; when changing them, compare calibration before/after. Never tune weights to make a favorite product look better.

## Output format — ALWAYS emit
```
SOURCE MANIFEST: [source → returned? / date / key figure] …
GRADE: X.X/10 (confidence: low|med|high — because …) [PROVISIONAL if applicable]
FACTORS: demand … | sales … | sentiment … | saturation … | margin … | repeat … | app-dep … | fit … | resilience …
WHY IT WINS (or doesn't): 3–6 sentences, each anchored to a retrieved number
RISKS: top 2–3, concrete
WHAT WOULD CHANGE THIS GRADE: the specific data that would move it
```
When producing code, this same structure becomes the `factor_breakdown` and `source_manifest` JSON written to the F1 `grade_snapshots` table.
