---
name: ospra-fit-gate
description: Screens any product candidate against Oubon/Ospra's hard curation rules (power, light quality, finish, app-dependency, supplier health, photo quality, economics, safety) and assigns a scene + role. Use this whenever evaluating, screening, curating, or approving a product for a store, judging a supplier listing, deciding what enters a catalog, or writing/modifying fit-gate pipeline code — even if the user just asks "is this product good for Oubon?" or pastes an AliExpress/CJ link.
---

# Ospra Fit Gate

The gate is how twelve unrelated factories produce one coherent brand. It runs BEFORE grading: a product that fails fit is never graded, because a great product that breaks the brand is still the wrong product. Rejections are logged with reasons — they are training data too.

## Procedure
1. **Gather listing facts** — power/charging, color temperature range, finish/material, control method (app required?), supplier rating/orders/ship time/store age, photo count + backgrounds, landed cost, any hardwiring/therapy claims. If a fact is not in the listing, mark it `UNKNOWN` — never assume a pass.
2. **Run the deterministic checks** (table below). Any hard fail = FAIL.
3. **Vision check** the primary photos: finish within palette? gamer/RGB styling? clean background usable for the paper-well treatment? If you cannot view images, say so and mark `finish` and `photos` as `UNVERIFIED` rather than passing them.
4. **Economics** — compute gross margin at target retail. Retail ≥ $50 qualifies for `hero`; < $25 qualifies only for `accessory`.
5. **Assign** scene candidates + role, then emit the output block exactly.

## The rules
| Rule | Pass condition | Why it exists |
|---|---|---|
| G1 Power | USB-C rechargeable OR standard wall plug; no proprietary chargers, no disposable-battery-only | "Every light charges on USB-C" is an honest ecosystem promise needing zero factory coordination |
| G2 Light | Warm-capable (≤3000K) or CCT-adjustable; RGB only if warm white is a first-class mode | Brand is warm editorial, anti-RGB-circus |
| G3 Finish | Matte black, white, or wood-tone only | Visual coherence across suppliers |
| G4 Control | Fully usable via physical control/remote; app optional, never required; no hub/wifi mandatory | App-dependent devices carry firmware, support, and ecosystem-trust costs that punish a dropship model |
| G5 Supplier | Rating ≥ 4.6 · ≥ 500 orders · ≤ 12-day US delivery · store age ≥ 6 months | Fulfillment reliability floor — supplier failure is the #1 dropship pain |
| G6 Photos | ≥ 800px, clean/neutral background, no watermarks | The store's look depends on it |
| G7 Economics | ≥ 60% gross margin at target retail; hero ≥ $50 retail; < $25 = accessory only | One-and-done categories must profit on order #1 |
| G8 Safety | No mains hardwiring; no carrier-restricted battery formats from unknown suppliers; strip any therapy/medical claims from inherited copy | Returns, shipping holds, and claim liability |

Thresholds are per-store configuration; these are Oubon's defaults. When screening for another store, ask for (or look up) that store's brand rules before applying G2/G3.

## Scenes and roles
Scenes: `studio-desk` · `bedroom-sleep` · `living-ambience` · `garage-workshop` · `car-roadside` · `outdoor-garden`
Roles: `hero` (anchor, ≥$50) · `task` · `ambient` · `accessory` (<$25 ok) · `consumable-host` (diffuser-lamps, candle-warmer lamps — flag as PRIORITY: they unlock a repeat-purchase SKU inside a lighting brand)

## Output format — ALWAYS emit this block
```json
{
  "product": {"title": "...", "source": "ae|cj", "url": "..."},
  "checks": {
    "G1_power": "PASS|FAIL|UNKNOWN", "G2_light": "...", "G3_finish": "PASS|FAIL|UNVERIFIED",
    "G4_control": "...", "G5_supplier": "...", "G6_photos": "PASS|FAIL|UNVERIFIED",
    "G7_economics": "...", "G8_safety": "..."
  },
  "economics": {"landed_cost": 0, "target_retail": 0, "gross_margin": 0.0},
  "result": {"pass": true, "role": "task", "scene_candidates": ["studio-desk"], "fail_reasons": [], "unknowns": []}
}
```
Follow the block with a 2–3 sentence plain-English verdict. A product with any `UNKNOWN` on G4, G5, or G8 is **not a pass** — say what must be verified.
