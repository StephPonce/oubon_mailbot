---
name: ospra-listing-aeo
description: Writes store-ready, agent-ready product listings — titles, benefit lines, descriptions, spec blocks, FAQs, and structured metafields — optimized for human shoppers AND AI shopping agents (ChatGPT, Claude, Gemini storefronts). Use this whenever asked to write or rewrite a product title, description, listing, collection copy, product FAQ, or metafields for Shopify or any store, when deploying a product, or when the topic is AEO / agent-readiness — even for a simple "write a product description".
---

# Ospra Listing + AEO

AI shopping agents are now a storefront: structured, plain, complete product data converts roughly twice as well through them as scraped page text. A listing has two readers — a human skimming on a phone and an agent parsing attributes. Write for both at once.

## Rules
- **Title**: function-first, ≤ 60 characters, house pattern "The <Brand> <Function>" (e.g., "The Oubon Sketch Panel"). Never inherit supplier keyword-stuffed titles.
- **Benefit line**: one sentence = spec + outcome. "1,450 lumens. Hooks span the engine bay." Numbers do the work, not adjectives. No exclamation marks. No "premium/luxury/best".
- **Description**: 80–140 words, plain language. Lead with the situation the product solves (the scene), then how it works, then what's in the box. Specific beats evocative.
- **Spec block**: complete, machine-legible key/value pairs — lumens, color temperature (K), battery (mAh) + runtime, charge port, dimensions, weight, materials, controls, app requirement. State "No app required" explicitly when true — agents ask.
- **FAQ**: 3–5 questions a real shopper (or an agent) asks: compatibility, shipping time, returns, battery life, "does it need an app?". Full-sentence factual answers.
- **Metafields** (deploy contract): `scene`, `role`, `benefit_line`, `specs` JSON. Fill all four or flag what's missing.
- **Inherited claims**: strip medical/therapy claims and unverifiable superlatives from supplier copy.

## AEO checklist (run before calling a listing done)
- [ ] Every attribute an agent might filter on exists as structured data, not buried in prose
- [ ] Shipping window + return policy stated in the FAQ (agents surface these)
- [ ] No hype words; plain nouns and numbers (agents rank legibility)
- [ ] Title, description, and specs agree with each other (contradictions get listings dropped)
- [ ] Alt text written for every image, describing the product literally

## Output format
1. Human block: Title / Benefit line / Description / FAQ
2. Machine block:
```json
{"title": "", "benefit_line": "", "scene": "", "role": "",
 "specs": {"lumens": 0, "cct_k": "", "battery_mah": 0, "runtime_h": 0, "charge_port": "USB-C", "app_required": false, "dimensions_cm": "", "weight_g": 0, "materials": ""},
 "faq": [{"q": "", "a": ""}], "alt_text": [""]}
```
Load `oubon-brand` for voice and naming when the store is Oubon.
