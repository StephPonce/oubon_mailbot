# Ospra — Design System & Build Brief

> **For Claude Design.** This is the single source of truth for how Ospra should look, feel, and be built. Build every screen in this system. It is a *new* direction — do **not** infer the design from any existing code; design fresh from this document. Read it top to bottom, then build from the prompt at the very end.

---

## 0. One-line essence

**Ospra is mission control for e-commerce.** It should feel like the cockpit of a Blue Origin capsule designed by SpaceX and finished in Apple "liquid glass": calm, precise, dark, and quietly powerful — with a single confident blue as the only real color, and an osprey watching from altitude.

---

## 1. Brand

- **Name & metaphor.** *Ospra* is a play on **osprey** — the sea-hawk that hovers at altitude, sees through the glare, and strikes once with precision. That is exactly what the product does: it watches the entire market from above, cuts through noise, and surfaces the one product worth selling. Lean into this metaphor everywhere.
- **The osprey is the unofficial mascot.** Sleek bird of prey: white crown, dark eye-stripe, hooked beak, long angular wings mid-hover. Render it **minimal and geometric** — a single-weight line mark or a low-poly/constellation silhouette in Origin Blue or white, never cartoonish, never a literal photo. It is a *precision instrument*, not a friendly blob.
- **Voice.** Confident, spare, technical-but-human. Short declaratives. No hype, no exclamation marks, no emoji in product UI. Think SpaceX mission copy ("Stage separation confirmed.") and Grok's dry precision.
- **What Ospra does (for context when designing screens):** AI-powered e-commerce automation for dropshipping — product **discovery** (AliExpress + CJ + Amazon + social-trend signals), **social-sentiment scoring**, **AI grading**, automated **Shopify deployment**, and Gmail-based **customer-support automation**. The reference store is *Oubon Shop*.

---

## 2. Design north star

Three influences, blended deliberately:

1. **Blue Origin** → the *color and confidence*. Deep space-navy canvas, one disciplined royal/azure blue as the brand signal. Aerospace seriousness. Nothing decorative.
2. **SpaceX / Grok** → the *restraint and rigor*. Near-black backgrounds, white type, generous negative space, hairline rules, uppercase micro-labels with wide tracking, monospaced numerics for anything measured. High signal-to-noise. If an element doesn't carry information, remove it.
3. **Apple Liquid Glass / frosted glass** → the *material*. Translucent, blurred, layered panels that feel like polished glass floating over a starfield — with specular edge-light, subtle refraction, and soft depth. Glass is the *surface language*; blue is the *energy*; black is the *space* it all floats in.

**Principles**
- **Dark-first, single-accent.** One blue. Resist adding a second hue. Signal colors (green/amber/red) appear only on data (grades, competition), never as decoration.
- **Calm > busy.** Whitespace is a feature. Let panels breathe.
- **Precision in numerics.** Every score, price, percentage, and metric is monospaced and right-weighted — it should read like telemetry.
- **Depth through glass and light, not borders and boxes.** Use blur, translucency, and a faint top highlight to separate layers; avoid heavy outlines.
- **Motion is physics, not flourish.** Things ease in like mass settling — smooth, weighted, brief.

---

## 3. Color system

All values are exact. Use CSS variables; never hardcode ad-hoc hexes.

### Canvas (the void)
| Token | Hex | Use |
|---|---|---|
| `--void` | `#05070E` | App background base (near-black, blue undertone) |
| `--space-900` | `#0A0F1C` | Page gradient stop / deepest panels |
| `--space-800` | `#111829` | Recessed surfaces |
| `--space-700` | `#18223A` | Raised solid surfaces (when glass isn't used) |

Page background = a very subtle radial: `--space-900` center fading to `--void` edges, optionally with a faint star/grain texture at ~3% opacity and one diffuse Origin-Blue glow orb top-right at ~8% opacity. Keep it *barely there*.

### Origin Blue (the one accent)
| Token | Hex | Use |
|---|---|---|
| `--origin-700` | `#0E3A8C` | Deep brand blue (Blue-Origin-confident), gradient base |
| `--origin-600` | `#1E5BD6` | Pressed/active states |
| `--origin-500` | `#2F6BFF` | **Primary** — brand, primary buttons, key accents |
| `--origin-400` | `#5B8DFF` | Hover, secondary accents |
| `--origin-300` | `#93B4FF` | Links, soft highlights, icons on dark |
| `--ice` | `#CFE0FF` | Specular highlight, glass edge-light, focus ring tint |

Primary gradient (buttons, the osprey mark, hero accents): `linear-gradient(135deg, #2F6BFF 0%, #1E5BD6 100%)`. A premium variant adds an ice top-sheen: overlay `linear-gradient(180deg, rgba(207,224,255,.25), transparent 40%)`.

### Text (on dark)
| Token | Value | Use |
|---|---|---|
| `--text-primary` | `#FFFFFF` | Headlines, key values |
| `--text-secondary` | `rgba(255,255,255,0.66)` | Body |
| `--text-tertiary` | `rgba(255,255,255,0.40)` | Labels, captions, meta |
| `--text-quaternary` | `rgba(255,255,255,0.24)` | Disabled, faint hints |

### Hairlines & strokes
| Token | Value | Use |
|---|---|---|
| `--line` | `rgba(255,255,255,0.08)` | Default hairline divider |
| `--line-strong` | `rgba(255,255,255,0.14)` | Emphasis divider |
| `--glass-edge` | `rgba(255,255,255,0.18)` | Top/left glass border (catches light) |

### Signal colors (data only — muted, refined, never neon)
| Token | Hex | Meaning |
|---|---|---|
| `--buy` | `#2ED3A0` | BUY grade / low competition / positive |
| `--watch` | `#F2B43D` | Medium / caution / neutral |
| `--avoid` | `#F2555A` | AVOID grade / high competition / negative |
| `--info` | `--origin-400` | Informational, "early caught" |

Each signal also has a 12%-opacity tint of itself for chip backgrounds (e.g. `rgba(46,211,160,0.12)`) and a 30%-opacity border.

---

## 4. Typography

- **Display / headings:** **Space Grotesk** (geometric, on-theme, clean). Weights 500–700.
- **UI / body:** **Inter** (or Inter Tight for tighter UI). Weights 400–600.
- **Numerics / telemetry / code:** **JetBrains Mono** (or Geist Mono) — use for *every* score, price, percentage, count, ID, and timestamp. This monospaced-data treatment is a core part of the brand feel.

**Eyebrow / micro-label idiom (SpaceX):** uppercase, `letter-spacing: 0.18em`, size 11–12px, `--text-tertiary`, weight 600. Use above section titles and on stat labels.

**Type scale (rem):**
| Role | Size | Weight | Notes |
|---|---|---|---|
| Display | 3.0–3.75rem | 600 | Marketing / hero only |
| H1 | 2.0rem | 600 | Page title |
| H2 | 1.5rem | 600 | Section |
| H3 | 1.125rem | 600 | Card title |
| Body | 0.95rem | 400 | Default |
| Small | 0.8125rem | 400 | Secondary |
| Micro/eyebrow | 0.6875–0.75rem | 600 | Uppercase, tracked |
| Numeric (stat) | 1.75–2.25rem | 600 | JetBrains Mono, tabular-nums |

Always enable `font-variant-numeric: tabular-nums` on numbers so columns align like a readout.

---

## 5. Space, grid, radii, elevation

- **Spacing scale (px):** 2, 4, 8, 12, 16, 20, 24, 32, 40, 56, 72. Default gutter 24. Page padding 24–32.
- **Radii:** `--r-sm` 10px (chips, inputs), `--r-md` 16px (buttons, small cards), `--r-lg` 22px (panels/cards), `--r-xl` 28px (hero/modals), `--r-full` 999px (pills, avatars). Lean generous and consistent — rounded but not bubbly.
- **Grid:** 12-col, max content width ~1280px, centered. Dashboard uses a fixed left rail + fluid content.
- **Elevation (shadows):**
  - `--shadow-soft`: `0 8px 32px rgba(0,0,0,0.45)`
  - `--shadow-lift`: `0 16px 48px rgba(0,0,0,0.55)` (modals, popovers)
  - `--glow-origin`: `0 0 0 1px rgba(47,107,255,0.35), 0 10px 40px rgba(47,107,255,0.22)` (active/primary)

---

## 6. The Liquid-Glass material (most important visual rule)

Panels, cards, the nav rail, modals, popovers, and toasts are **frosted glass**, not flat fills. The recipe:

```css
.glass {
  background: rgba(255, 255, 255, 0.05);                 /* faint milk over the void */
  backdrop-filter: blur(28px) saturate(140%);
  -webkit-backdrop-filter: blur(28px) saturate(140%);
  border: 1px solid var(--line);                          /* base hairline */
  border-top-color: var(--glass-edge);                   /* top edge catches light */
  border-left-color: rgba(255,255,255,0.12);
  border-radius: var(--r-lg);
  box-shadow:
    var(--shadow-soft),
    inset 0 1px 0 rgba(255,255,255,0.10);                 /* inner top specular highlight */
}
```

**Liquid touches (use tastefully):**
- A faint diagonal sheen across large glass surfaces: `linear-gradient(135deg, rgba(255,255,255,0.06), transparent 30%)` as an overlay.
- On hover of interactive glass, brighten the fill to `0.07` and the top edge toward `--ice`, and add `--glow-origin` if it's a primary/selected element.
- **Refraction accent:** a 1px gradient border that shifts from `--ice` (top-left) to transparent (bottom-right) on featured/active cards.
- Layer glass over glass sparingly — at most two glass depths; deeper nesting kills the effect.

**Do not:** stack heavy drop shadows on flat cards, use opaque gray cards, or put glass on glass on glass. If `backdrop-filter` is unsupported, fall back to `--space-800` at 92% opacity — never a hard gray.

---

## 7. The Osprey mascot

- **Logomark:** a minimal osprey in mid-hover — angular swept-back wings forming a subtle "A"/arrow, sharp beak, single eye accent. Single-weight strokes or a clean filled silhouette in the Origin gradient or white. Pairs with the wordmark **Ospra** set in Space Grotesk 600.
- **As a system motif:** a faint constellation/wireframe osprey can sit in empty backgrounds at ~4% opacity (e.g. behind the scoreboard hero, on auth screens).
- **Where it appears:** app logo (top of nav rail), favicon, loading state (osprey scanning — a slow wing-sweep or a sonar-style sweep line under it), empty states (perched osprey + "Nothing in range yet"), onboarding hero, 404 ("Off course"), and the public scoreboard hero.
- **Tone of mascot copy:** terse, aviation/hunting flavored but professional — "Scanning the market…", "Two winners in range.", "Locked on." Never cutesy.

---

## 8. Iconography & imagery

- **Icons:** thin, geometric line icons (Lucide-style, ~1.5px stroke), `--text-secondary` default, `--origin-300` when active. Consistent 20px in UI, 16px in dense rows.
- **Imagery:** product images sit inside glass tiles with a subtle inner border and a 1px `--glass-edge` top. Never let raw product photos touch the layout edge — always framed in glass.
- **Data/marketing illustration:** starfields, orbital/altitude motifs, thin grid horizons, faint topographic/sonar rings. Keep them monochrome-blue and low-opacity.

---

## 9. Motion & interaction

- **Easing:** `cubic-bezier(0.22, 1, 0.36, 1)` (settle-in). Durations: 120ms (micro/hover), 240ms (panels), 400ms (page/modal).
- Cards lift slightly and brighten on hover (`translateY(-2px)`, fill +0.02, faint glow). Buttons depress on active.
- Numbers that change should **count up** briefly. New discovery results **fade + rise** in a soft stagger (40ms apart), like contacts appearing on radar.
- Loading: a thin Origin-Blue sweep line (radar) or a shimmer across glass — never a generic spinner where a skeleton fits.
- Respect `prefers-reduced-motion` (cut transforms, keep opacity).

---

## 10. Component library (build these)

For each: dark glass surfaces, Origin Blue as the only accent, monospaced numerics, hairline separators.

- **Buttons.**
  - *Primary:* Origin gradient fill, white text, `--r-md`, `--glow-origin` on hover, depress on active. Used once per view for the main action.
  - *Secondary:* glass (transparent fill + `--glass-edge` border), white text; hover brightens fill.
  - *Ghost/tertiary:* text + icon only, `--text-secondary` → white on hover.
  - *Destructive:* `--avoid` text on transparent; filled red only for irreversible confirms.
  - Sizes sm/md/lg; loading state swaps label for the radar-sweep; disabled = `--text-quaternary`, no glow.
- **Glass card / panel.** The §6 recipe. Title (H3) + optional eyebrow; content; optional footer divider (`--line`). The default container for everything.
- **Navigation rail (left).** Fixed vertical glass rail. Top: osprey logomark + "Ospra". Then nav items (icon + label): Dashboard, Discovery, Scoreboard, Autopilot, Actions, Learning, Stores, Settings. Active item: glass pill with `--origin-500` left indicator bar + `--origin-300` icon + subtle glow. Collapsible to icon-only (84px) ↔ expanded (252px). Bottom: tier badge + account. **The rail is persistent — content changes to its right; the rail never disappears between pages.**
- **Top bar.** Slim, glass, page title (H1) left; right: search, tier chip, notifications, avatar. Subtle bottom hairline.
- **Stat tile.** Eyebrow label (uppercase, tracked) + big monospaced number + small delta (`--buy`/`--avoid` arrow). Glass.
- **Pills / badges (critical for Discovery).** Small `--r-full` chips, tinted by meaning:
  - *Grade chip:* `BUY` (green tint), `WATCH`, `AVOID` (red tint), `INSUFFICIENT DATA` (neutral). Monospaced.
  - *Opportunity / competition:* "Low competition" (green), "Medium" (amber), "High" (red).
  - *Lifecycle / early-caught:* "Just Caught" (Origin-Blue tint), "Growing" (ice), "Proven" (green) — pair with a tiny osprey/radar glyph.
  - *Days-of-proof:* "Caught 6d ago · seen 3×" (neutral glass).
  - *Supplier:* "CJ", "AliExpress", warehouse flags — minimal monochrome.
- **Score chip ("Oi Score").** A circular or rounded-square glass badge with the score (monospaced, large) and a thin radial progress ring in Origin Blue (green/amber/red by band). This is the signature data element — make it feel like an instrument gauge.
- **Product card.** Glass tile: framed product image (with AI-enhanced badge if applicable, image-count badge), title (2-line clamp), price row (cost struck through, suggested price, profit in `--buy`), the badge row (grade + competition + lifecycle + days-of-proof), and the Oi Score gauge top-right. Hover lifts + glows. Click → detail panel.
- **Product detail (slide-over or modal).** Large glass surface: image gallery (all source images, swipeable), the full score breakdown (demand / trend / sentiment / saturation as thin horizontal gauges, with honest "no data" striped bars when a signal is missing), AI analysis section, social-sentiment evidence (real posts with engagement counts), supplier comparison, and a primary "Deploy to Shopify" action.
- **Data table.** Hairline rows, no vertical borders, monospaced numeric columns right-aligned, sticky glass header, row hover = faint fill. Used in Scoreboard, Actions, Stores.
- **Modal / dialog.** Centered glass (`--r-xl`, `--shadow-lift`), dimmed starfield backdrop, single primary + ghost cancel.
- **Forms / inputs.** Glass field, `--line` border → `--origin-400` + `--ice` focus ring on focus, label as eyebrow above, helper/error below (error in `--avoid`). Toggles/switches use Origin Blue when on.
- **Toasts.** Bottom-right glass, accent left-bar by type (info/success/error), auto-dismiss, stack.
- **Empty states.** Perched-osprey illustration + terse line ("Nothing in range yet — run a scan.") + primary action.
- **Charts.** Minimal: Origin-Blue line/area on dark, faint grid, monospaced axis labels, no chartjunk. Win-rate, days-to-first-sale, etc.

---

## 11. Product context (so screens are accurate)

**Tiers — the flight ladder (Nest → Flight → Soar → Stratosphere).** Tie the names to the osprey's life: grounded nest → first flight → soaring → the stratosphere.

| Tier | Price | Tagline | Products/wk | Per-request | Stores | Support AI |
|---|---|---|---|---|---|---|
| **Nest** | Free | *See What's Possible* | 10 | 10 | 1 | preview only (drafts shown, not sent) |
| **Flight** | $29/mo ($290/yr) | *Start Selling Smarter* | 50 | 25 | 1 | 100 replies/mo |
| **Soar** ⟵ *popular* | $79/mo ($790/yr) | *Run Your Business, Not Just a Store* | 250 | 50 | 3 | 1,000 replies/mo |
| **Stratosphere** | $199/mo ($1,990/yr) | *Your AI Operations Team* | 1,500 | 100 | 10 | unlimited |

Plus: **White-glove onboarding — $499** (a 4th signup option: human store setup + hand-picked products for 30 days + weekly call + full Stratosphere access, then auto-rolls to Stratosphere). And **standalone API modules**: *Discovery API* $49/mo, *Discovery + Support API* $149/mo. Rules: annual always saves 2 months; Nest free forever; no "Enterprise — call us" (every tier has a number).

**Features built (design real screens for these):**
- **Product Discovery** — multi-source candidate sourcing (AliExpress, CJ Dropshipping, Amazon, Apify trend feeds) + a persistent **catalog** that accumulates graded products with "days of proof."
- **Social-sentiment scoring** — Amazon reviews / AliExpress reviews / supplier-quality proxy + X/Twitter, Reddit signals.
- **AI grading** — every product gets an Oi Score + BUY/WATCH/AVOID verdict with a plain-English "why we scored this" breakdown.
- **Saturation / competition + lifecycle (velocity) phase** — Just Caught → Growing → Proven, with low/medium/high competition.
- **Automated Shopify deployment** — one-click deploy of a graded product.
- **AI customer-support automation** — Gmail-based, tenant-fine-tuned reply drafts/sends.
- **Public live Scoreboard** — real graded picks + outcomes (win rate, days-to-first-sale) from the Oubon store.
- **Learning loop** — outcomes feed back to improve grading.
- **Billing/tiers** (LemonSqueezy), multi-store, onboarding checklist.

**Features planned (show as "coming" where relevant):** TikTok Shop & Pinterest trend sources, refund-risk predictor (Stratosphere first), Agency Mode (multi-client dashboard), Embed Mode (white-label discovery widget), mobile app.

**Who it's for:** the "Overloaded Operator" — a 1–3 person Shopify/Woo store doing $2k–$50k/mo, spending >4 hrs/week on sourcing or support. Design for *clarity under overload*: one obvious next action per screen.

---

## 12. Key screens to design

1. **Marketing / landing** — dark starfield hero, osprey mark, one-line value prop ("Spot winning products from altitude."), the tier ladder, a live scoreboard strip, CTA to start free (Nest).
2. **Auth (login / register)** — minimal centered glass card over starfield + faint constellation osprey.
3. **Onboarding** — 3-step checklist (Connect Shopify → Run first scan → Deploy first product) as a glass stepper.
4. **Dashboard** — mission-control overview: stat tiles (active products, weekly quota used, pending support, revenue direction), the onboarding checklist if incomplete, recent discovery, quick actions. Persistent left rail.
5. **Product Discovery** — the heart. Niche selector + scan action; a responsive grid of product cards with the full badge system and Oi Score gauges; filters (competition, lifecycle, score, niche); "Just Caught / Growing / Proven" groupings; tier-clamp upgrade nudge when results are capped.
6. **Product Detail** — slide-over with gallery, score breakdown gauges (honest "no data" bars), AI analysis, sentiment evidence with engagement counts, supplier comparison, Deploy action.
7. **Scoreboard (public + in-app)** — hero with constellation osprey, headline win-rate stat tiles, a table of graded picks with outcomes; honest small-sample note.
8. **Settings & Stores** — connected stores, brand/policy config, billing/tier, AI support settings.
9. **Upgrade / Pricing** — the 4-card tier ladder + white-glove, monthly/annual toggle ("save 2 months"), the gated-feature banner. In-app version keeps the left rail.

---

## 13. THE BUILD PROMPT (paste this into Claude Design)

> **Build the Ospra web app UI following the attached Ospra Design System exactly.**
>
> Ospra is "mission control for e-commerce" — an AI tool that discovers, grades, and deploys winning dropshipping products and automates customer support. The aesthetic is **Blue Origin meets SpaceX/Grok, finished in Apple liquid glass**: a near-black space-navy canvas (`#05070E`), **one** disciplined accent — Origin Blue (`#2F6BFF`, gradient to `#1E5BD6`) — frosted/liquid-glass panels (translucent white ~5% over a 28px backdrop blur, hairline borders with a light-catching top edge, soft shadows, a faint specular sheen), generous negative space, and **monospaced numerics (JetBrains Mono) for every score, price, and metric** so data reads like telemetry. Headlines in Space Grotesk, body in Inter, uppercase wide-tracked micro-labels. The **osprey** is the mascot — a sleek, geometric bird-of-prey logomark and a faint constellation motif; copy is terse and aviation-flavored ("Scanning the market…", "Two winners in range."). Signal colors (green `#2ED3A0` BUY / amber `#F2B43D` / red `#F2555A` AVOID) appear **only on data**, never as decoration.
>
> Build these screens, all sharing a **persistent left glass navigation rail** (Dashboard, Discovery, Scoreboard, Autopilot, Actions, Learning, Stores, Settings) that **never disappears** when navigating — only the content area to its right changes:
> 1. **Dashboard** — mission-control overview with glass stat tiles (active products, weekly-quota gauge, pending support, revenue direction), recent discovery, and quick actions.
> 2. **Product Discovery** — niche selector + "Run scan" primary action; a grid of **product cards** (framed product image, title, price row with profit in green, an instrument-style circular **Oi Score gauge**, and a badge row: BUY/WATCH/AVOID grade, Low/Medium/High competition, Just-Caught/Growing/Proven lifecycle, and "Caught Nd ago · seen N×"); filters and lifecycle groupings; an upgrade nudge when results are tier-capped.
> 3. **Product Detail** (slide-over) — image gallery, a score breakdown of demand/trend/sentiment/saturation as thin gauges with honest striped "no data" bars, an AI-analysis block, social-sentiment evidence showing real posts **with engagement counts**, supplier comparison, and a primary "Deploy to Shopify".
> 4. **Scoreboard** — hero with a faint constellation osprey, win-rate stat tiles, and a clean table of graded picks with outcomes.
> 5. **Pricing / Upgrade** — four glass tier cards on the flight ladder: **Nest** (Free — "See What's Possible"), **Flight** ($29 — "Start Selling Smarter"), **Soar** ($79, mark as *Most Popular* — "Run Your Business, Not Just a Store"), **Stratosphere** ($199 — "Your AI Operations Team"), plus a **White-glove $499** option; monthly/annual toggle that notes "save 2 months".
>
> Use the exact tokens, the glass recipe, the radii/spacing, the motion (settle-in easing, radar-sweep loaders, staggered fade-rise for results), and the component specs in the attached document. Prioritize calm, clarity, and precision over density. One obvious primary action per screen.

---

*End of brief. Build from §13; reference §1–§12 for any detail. When in doubt: darker, cleaner, fewer colors, more glass, sharper numbers, and the osprey watching.*
