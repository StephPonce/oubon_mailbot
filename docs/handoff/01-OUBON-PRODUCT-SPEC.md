# 01 — OUBON PRODUCT SPEC (The Fit Gate)
*Hard pass/fail gate every candidate passes BEFORE grading. This is how twelve unrelated factories produce one coherent brand. Implemented as pipeline stage F2 (see `02`).*

## Why a gate exists
Hue's ecosystem = radios + app. Oubon's ecosystem = **coherence**: everything looks designed by one mind, works the same way, charges the same way. Coherence is a spec, a spec is a filter, and filtering is what Ospra does.

---

## THE GATE (all must pass)

| # | Rule | Pass condition | Why |
|---|---|---|---|
| G1 | Power | USB-C rechargeable OR standard wall plug. No proprietary chargers, no non-rechargeable-battery-only. | "Every Oubon light charges on USB-C" = a real ecosystem promise, zero factory coordination. |
| G2 | Light quality | Warm-capable (≤3000K) or CCT-adjustable. RGB allowed ONLY if warm white is a first-class mode. | Brand = warm editorial, anti-RGB-circus. |
| G3 | Finish | Matte black, white, or wood-tone only. No chrome, no gamer styling, no glossy plastic hero shots. | Visual coherence across suppliers. Checked by GPT-4V (F2). |
| G4 | Control | Fully usable with physical controls/remote. App = optional enhancement, never required. No hub, no wifi-mandatory. | D3. Kills firmware/support/ecosystem liability. |
| G5 | Supplier health | Rating ≥ 4.6 · ≥ 500 orders · ≤ 12-day US delivery · store age ≥ 6 mo. | Fulfillment reliability floor. |
| G6 | Photo quality | ≥ 800px, clean background (white/neutral preferred — feeds the paper-well treatment), no watermarks. | Store look depends on it; GPT-4V checks. |
| G7 | Economics | Landed cost supports ≥ 60% gross margin at target retail. Hero candidates: retail ≥ $50 (D8). < $25 retail = accessory role only. | One-and-done category must profit on order #1. |
| G8 | Safety/ops | No mains hardwiring required (plug/rechargeable only). No lithium shapes with known carrier restrictions from that supplier. No medical/therapy claims in listing copy we'd inherit. | Returns, shipping, and claim liability. |

**Fail = logged with reason (the gate's rejections are training data too).**

## SCENE / ROLE TAXONOMY (the slot vocabulary — must match `04` metafields)
Scenes: `studio-desk` · `bedroom-sleep` · `living-ambience` · `garage-workshop` · `car-roadside` · `outdoor-garden`
Roles per scene: `hero` (≥$50, the anchor) · `task` · `ambient` · `accessory` (<$25 ok) · `consumable-host` (diffuser-lamps, candle-warmer lamps — **priority sourcing**: they unlock the oils/melts repeat SKU).

## NAMING CONVENTION
- Pattern: **"The Oubon ___"** — function-first, ≤ 4 words ("The Oubon Sketch Panel", "The Oubon Sunset Lamp").
- Never inherit supplier titles ("A3 LED Light Pad Ultra Thin USB Dimmable" ❌).
- Benefit line = one sentence, spec + outcome ("1,450 lumens. Hooks span the engine bay."). No hype adjectives, no exclamation marks.

## MACHINE-CHECKABLE SCHEMA (implement in F2)
```json
{
  "fit_check": {
    "power":        {"usb_c": true, "wall_plug": false, "proprietary": false},
    "light":        {"min_cct": 2700, "max_cct": 5000, "warm_capable": true, "rgb_only": false},
    "finish":       {"palette_match": "gpt4v", "allowed": ["matte_black","white","wood"]},
    "control":      {"app_required": false, "hub_required": false, "physical_control": true},
    "supplier":     {"rating": 4.7, "orders": 1240, "ship_days_us": 9, "store_age_months": 14},
    "photos":       {"min_px": 800, "clean_bg": "gpt4v", "watermark": false},
    "economics":    {"landed_cost": 14.20, "target_retail": 49.00, "gross_margin": 0.71, "role_eligible": ["task","ambient"]},
    "safety":       {"hardwire_required": false, "therapy_claims": false}
  },
  "result": {"pass": true, "role_assignment": "task", "scene_candidates": ["studio-desk"], "fail_reasons": []}
}
```

## LIGHTING × WELLNESS PRIORITY ZONE
Highest-heat overlap from niche research — weight discovery queries toward: sunset/ambience projectors · sunrise alarm lamps · sleep-friendly warm lighting · light-therapy-adjacent devices (**G8: strip therapy claims from copy**) · diffuser + candle-warmer lamps.
