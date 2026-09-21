---
description: "(Theme repo) Build one storefront section per the design brief and build plan. Usage — /build-section hero-dimmer"
---
Section to build: $ARGUMENTS

1. Read CLAUDE.md (the design brief) and design/04-OUBON-THEME-BUILD.md; open the matching part of the mockups in design/ for reference.
2. Look up any Liquid object, filter, or schema shape you are not certain of via the Shopify Dev MCP / Liquid skill — do not guess Shopify API shapes.
3. Implement the section as a .liquid section with full {% schema %} settings (copy, colors, pickers) so it stays editable in the theme editor. Read metafields per the shared contract; never hardcode products.
4. Run `shopify theme check`. Fix errors.
5. Tell me exactly what to screenshot in `shopify theme dev` (desktop + 390px mobile) to compare against the mockup, and list what you expect to differ.
6. Do not touch checkout. Do not edit the live theme.
