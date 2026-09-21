---
name: oubon-brand
description: The Oubon Shop brand system — concept, voice, naming, design tokens, imagery rules, scene taxonomy, and do/don'ts. Load this whenever writing or designing ANYTHING for Oubon (oubonshop.com) — product names, listings, emails, ads, social posts, theme/Liquid work, imagery direction, or page copy — whenever "Oubon" is mentioned, even in passing.
---

# Oubon Brand

**Concept:** "The useful kind of smart." Oubon is a smart-home essentials gallery — lighting-led at launch — not an electronics shop. The page is a dusk scene; the products are the light sources in it. Positioned against RGB gamer gadgetry (Govee/Nanoleaf) and sterile white minimalism (Aqara): warm, editorial, quietly technical. Premium everyday tools presented like furniture.

**Launch hero copy (lighting-forward):** eyebrow `SMART LIGHTING · HOME ESSENTIALS` · H1 "Good light is *a tool.*" · sub "Dimmable, rechargeable, built for the places you actually work and live. Every product spec-checked before it earns a place here."
**Umbrella copy (staged for later):** "The useful kind of *smart.*"

## Voice
Confident, warm, specific. Numbers over adjectives. One serif statement per screen, everything else quiet. No exclamation marks. Never "premium", "luxury", "best", "revolutionary". Say what the product does in the room it does it in. Buttons say what happens: "Add to cart", "Shop the collection", "Sign up".

## Naming
Pattern **"The Oubon <Function>"**, ≤ 4 words: The Oubon Sketch Panel · The Oubon Sunset Lamp. Never inherit supplier titles. Benefit line = spec + outcome ("Three brightness levels. Zero eye strain.").

## Design tokens
- Dusk palette: `#101018` page · `#14151f` surfaces · `#1c1e2c` cards · `#2e3145` lines · `#9aa0b8` body · `#f3ede1` paper (headlines, buttons, image wells) · `#ffe9c7` lit emphasis
- Glow = a light *temperature*, not a brand color: warm `rgb(255,183,104)` default ↔ cool `rgb(188,212,255)`
- Type: Instrument Serif 400 (display, italic for the emphasized word) · Albert Sans (body/UI) · IBM Plex Mono (eyebrows, prices, specs; uppercase, letterspaced)
- Shape: 14–16px card radius, 99px pills, 1px lines, glow border on hover; hover = "turn it on", lift ≤ 3px
- Signature element: the Kelvin dimmer (2700K→5000K) in the hero; never add a second gimmick

## Imagery
Supplier photos go in **paper image wells** (`#f3ede1` background, `mix-blend-mode: multiply`, square, padded) — lit vitrines in a dark gallery. Lifestyle renders: dusk-lit rooms, warm 2700K glow, consistent grade across the catalog. No RGB rainbow scenes.

## Scenes (collections) and roles
`studio-desk` · `bedroom-sleep` · `living-ambience` · `garage-workshop` · `car-roadside` · `outdoor-garden` — roles: hero (≥$50) / task / ambient / accessory (<$25) / consumable-host. Next scenes as the catalog grows: Kitchen, Bedroom, Outdoor.

## Do / Don't
✅ dusk backgrounds, paper wells, mono spec labels, warm defaults, spec-anchored claims, USB-C ecosystem promise
❌ pure black (#000), RGB accents, gradient-text headlines, carousels, countdown timers, "HOT SALE" badges, trust-badge clutter, therapy/medical claims, app-required products

For full tokens and section specs read `OUBON-DESIGN-BRIEF.md` (theme repo `CLAUDE.md`).
