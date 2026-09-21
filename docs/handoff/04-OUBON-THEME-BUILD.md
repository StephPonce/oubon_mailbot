# 04 — OUBON THEME BUILD PLAN (Claude Code, theme repo)
*Implements the approved design (mockups `oubon-homepage-mockup.html` v1 + `oubon-homepage-v2-smarthome.html`; system in `OUBON-DESIGN-BRIEF.md`). Copy both mockups + the brief into the repo under `/design/`; the brief becomes repo `CLAUDE.md`.*

## COPY DECISION (D2)
Design system = v2 (umbrella-ready). **Launch hero copy = lighting-forward:**
- Eyebrow `SMART LIGHTING · HOME ESSENTIALS` · H1 **"Good light is *a tool.*"** · Sub: "Dimmable, rechargeable, built for the places you actually work and live. Every product spec-checked before it earns a place here."
- v2 umbrella copy ("The useful kind of *smart.*") is staged in the brief — swap via theme settings when the catalog broadens. Build the hero section so headline/eyebrow/sub are **schema settings**, making the swap a no-code change.

## PREREQS
```bash
npm install -g @shopify/cli@latest
shopify theme pull --store rxxj7d-1i.myshopify.com --live
# NOTE: rxxj7d-1i.myshopify.com is the PERMANENT domain. oubonshop.com is the vanity
# domain and oubonshop.myshopify.com does not exist -- the CLI reports a misleading
# "not authorized to use the CLI to develop in the provided store" error if you use it.
git init && git add -A && git commit -m "baseline: stock theme"
```
- Install Shopify's official **Liquid skill** + **Shopify Dev MCP** (Liquid is under-represented in training data — don't freestyle API/schema shapes; look them up).
- Google Fonts (Instrument Serif · Albert Sans · IBM Plex Mono) via preconnect + stylesheet in `theme.liquid`; tokens from the brief into CSS custom properties in the base stylesheet + color settings in `settings_data.json`.

## CONTENT PREREQS (non-code — do before/while building)
- [ ] Rename `test-` prefixed products; set proper handles/titles per `01` naming ("The Oubon ___")
- [ ] Store meta description (currently empty)
- [ ] Create scene collections: studio-desk · bedroom-sleep · living-ambience · garage-workshop · car-roadside · outdoor-garden
- [ ] Generate lifestyle imagery via Ospra's GPT-4V+Stability pipeline — spec: products in dusk-lit rooms, warm 2700K glow, consistent grade; supplier white-bg shots are fine for cards (paper wells handle them)
- [ ] Write benefit lines + specs for the 3 live products

## METAFIELD SCHEMA (⚠️ shared contract with Ospra deploy engine — `02` F3 writes these; theme reads them)
```
product.oubon.scene          (single line: taxonomy handle)
product.oubon.role           (hero|task|ambient|accessory|consumable-host)
product.oubon.benefit_line   (single line)
product.oubon.specs          (json: {lumens, battery_mah, cct_range, charge_port, runtime_h})
```

## BUILD ORDER (section by section — never "redesign everything" in one prompt)
1. **Tokens/settings** — palette + fonts + radius wired; verify on stock sections first
2. **Header/nav** — mono wordmark, Shop/Standards/About, cart pill
3. **`hero-dimmer.liquid`** — schema: eyebrow, headline, sub, 2 CTAs, kelvin toggle on/off. Progressive enhancement: no-JS = warm static glow. Port the mockup's lerp JS.
4. **Scene tiles** — section with collection-picker blocks (mono index, serif title, one-liner, glow hover)
5. **Featured products** — paper image wells (`--paper` bg, `mix-blend-mode: multiply`, square, padded), mono tag from scene/role metafields, benefit line, mono price, Add pill; hover = glow lift ≤3px
6. **Standards strip** — Spec-checked / 30-day returns / Real support
7. **Manifesto** — serif statement section (text setting)
8. **Newsletter** — native Shopify customer form, styled to brief ("The Light Letter")
9. **Footer**
10. **Product page (PDP)** — paper-well gallery, mono spec table from `specs` metafield, benefit line as subtitle, "Complete the scene" cross-sell block (same-scene products via metafield)
11. **Collection page** — card grid reuse, scene header

## LOOP + QA (every section)
`shopify theme dev` (hot reload) → implement → `shopify theme check` → screenshot vs `/design/` mockup → iterate. Paste screenshots into Claude Code for visual critique — highest-leverage design move.
**Mobile QA gate before publish:** 390px layout · LCP (hero stays image-free) · `:focus-visible` on all interactive · `prefers-reduced-motion` honored · alt text on product imagery · Lighthouse mobile ≥ 85.
**Ship:** `shopify theme push --unpublished` → preview link → phone test → publish. Git = rollback. **Never edit the live theme. Never touch checkout.**
