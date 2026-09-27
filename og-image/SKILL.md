---
name: og-image
description: Design and generate Open Graph / social preview images (1200x630 cards) using a brand-agnostic atomic design system and @vercel/og (Satori/ImageResponse). Trigger on "OG image," "og:image," "social card," "social preview image," "Open Graph card," or when a project needs opengraph-image.tsx/twitter-image.tsx.
license: MIT
compatibility: Agent-agnostic. Implementation examples target Next.js App Router + @vercel/og, but the design system (references/design-system.md) is framework-independent.
metadata:
  author: Sprintz
  version: "0.1.0"
  category: brand-and-design
---

# OG Image

Generate Open Graph / social preview images from a real, evidence-based design system rather than ad-hoc one-off cards. "OG image" and "social image" mean the same artifact — the picture platforms (Slack, iMessage, LinkedIn, Twitter/X, Discord) pull for a link preview.

## When to use

- A project needs `og:image`, a social preview card, or a Next.js `opengraph-image.tsx`/`twitter-image.tsx`.
- The user asks for social cards, launch graphics, blog-post preview images, or changelog/documentation cards.
- Related but distinct: for logos, favicons, and non-social brand assets, use `programmatic-brand-assets` instead — that skill also has a brief `@vercel/og` section; this skill is the deeper, OG-specific companion (see its "Dynamic Social Cards" section for the pointer back here).

## Design system

`references/design-system.md` is the source of truth: 8 layout archetypes, canvas geometry/safe zones, typography scale, color/contrast strategies, and an atomic mapping (atoms → molecules → templates), derived from a structured survey of 768+ real OG cards across 17 categories on opengraphexamples.com (captured 2026-08-10).

Read it before designing a new card. Pick an archetype that matches the content shape — don't invent a ninth layout unless none of the eight fit:

1. **Dual Column Split** — title left, product visual right. Best for feature/product launches.
2. **Centered Hero** — symmetrical wordmark/tagline. Best for brand moments, major announcements.
3. **Stat Callout** — large metric numbers. Best for reports, benchmarks, milestones.
4. **App UI / Browser Frame** — product screenshot in window chrome. Best for feature docs.
5. **Code Terminal** — dev-tool/API cards with syntax-highlighted code.
6. **Full-Bleed Photo** — photography with gradient scrim. Best when a strong image exists.
7. **Quote / Testimonial** — blog posts, press quotes, podcast episodes.
8. **Badge / Pill-Header Minimal** — Vercel/Linear-style changelog and doc cards.

## Implementation: `@vercel/og`

`references/satori-constraints.md` covers the Satori-specific constraints (flex-only layout, no CSS Grid, inline styles, font loading, asset sizing, dimensions/metadata, debugging). Read it before writing template code — Satori is a constrained renderer, not a browser, and several CSS features silently no-op rather than erroring.

`assets/templates.tsx` implements all 8 archetypes as Satori-safe JSX, brand-agnostic via a `BrandTokens` prop, and verified by actually rendering every one of them (`scripts/render-check.mjs`) — not just type-checked. `TemplateCodeTerminal`'s `CodeWindow` molecule needed `whiteSpace: "pre"` on each token span after render-check caught adjacent code tokens losing their spacing (`import { client } from` rendering as `import{ client }from`) — a class of bug `tsc` cannot see. If you add a ninth archetype, follow the same pattern and re-run the render check before calling it done.

## Required workflow

1. Read `references/design-system.md`, pick the archetype matching the content.
2. Define `BrandTokens` for the calling project (colors, title font, mono font if needed, radius, padding) — never hardcode a specific brand's values into a template; `exampleTokens` in `assets/templates.tsx` is a working example, not a default. Colors must be six-digit hex (`withAlpha()` appends alpha bytes to them for motifs); other formats produce malformed CSS Satori silently ignores.
3. Implement or reuse the template from `assets/templates.tsx`, following `references/satori-constraints.md`'s Satori rules — pay special attention to the `inset`, dot-grid-vs-line-grid, and SVG `viewBox` gotchas documented there, all three found by actually rendering, not by reading Satori's docs.
4. Run `node scripts/render-check.mjs` (needs `npm install --no-save satori @resvg/resvg-js typescript @types/react react` once locally) and look at the output PNGs — render at exact target dimensions (`1200×630`) and visually confirm every motif is actually visible, not just that the process didn't crash.
5. Set the accompanying textual metadata (`og:title`, `og:description`, `twitter:card`, etc.) — file-based `opengraph-image.tsx`/`twitter-image.tsx` generates the image `<meta>` tags automatically, so don't hand-write those two.

## Determinism

Same rule as `programmatic-brand-assets`: never use unseeded `Math.random()` for motif placement, noise, or jitter. `assets/templates.tsx` exports `mulberry32`, a fixed-seed PRNG — pass a `seed` in `BrandTokens` so re-rendering the same props produces the same pixels. Record the seed when a template intentionally varies between renders.

## Font policy

Ship only the specific static font weights each template actually uses — don't bundle a whole variable font family. `assets/fonts/` currently ships `SpaceGrotesk-600.ttf`, `SpaceGrotesk-700.ttf` (the family's actual static maximum — it has no 800/ExtraBold), and `JetBrainsMono-500.ttf`. Load fonts explicitly into `ImageResponse`'s `fonts` option using the **unquoted** family name; quote family names separately in JSX `fontFamily` styles (`'"Space Grotesk"'`) — the two spellings serve different APIs and nothing keeps them in sync automatically. See `references/satori-constraints.md` for the full rule set, including how to fetch a specific static weight when upstream only ships a variable font file.

## Validation checklist

- [ ] Rendered through `scripts/render-check.mjs` (real Satori render, not just `tsc --noEmit`) at exact `1200×630` (or the declared alternate size).
- [ ] Every motif visually confirmed present in the output PNG — a layer can render with zero visible effect (`inset` collapsing to nothing, a dot-grid gradient collapsing to sub-pixel) while the process still exits 0.
- [ ] No CSS Grid, no `inset` shorthand (`top`/`right`/`bottom`/`left` instead), no unsupported CSS applied directly to elements (`backdrop-filter`, 3D transforms) — SVG-embedded `filter`/`feTurbulence` is fine but needs an explicit `viewBox`.
- [ ] Every color/font/spacing value traces back to a `BrandTokens` prop, not a hardcoded literal; colors are six-digit hex.
- [ ] No unseeded randomness; `tokens.seed` is actually threaded through every motif that varies, in every template that uses it — not just the first one built.
- [ ] Font weights loaded into `ImageResponse` match what the template actually renders, and the family name is unquoted there vs. quoted in `fontFamily`.
- [ ] Textual `og:*`/`twitter:*` metadata set via `generateMetadata`; image tags left to file-based generation, not hand-written.

## References & Assets

- `references/design-system.md` — the 8-archetype design system, typography scale, motifs, color strategies, atomic mapping. Source of truth for what to build; treat its CSS as a design reference to reinterpret through Satori-safe primitives, not as code to paste verbatim (see `satori-constraints.md`'s Satori-support caveats).
- `references/satori-constraints.md` — Satori/`ImageResponse` constraints, font handling, asset sizing, debugging, and the specific rendering gotchas (`inset`, dot-grid, `viewBox`) found by actually rendering this skill's own templates.
- `assets/templates.tsx` — Satori-safe JSX for all 8 archetypes (Centered Hero, Split Screen, Stat Grid, App Window, Code Terminal, Full Photo, Quote Card, Badge Minimal) plus shared atoms/molecules (`TitleBlock`, `StatMetricBox`, `WindowChrome`, `CodeWindow`, `PillBadge`, `AuthorByline`, motif helpers, `mulberry32`, `withAlpha`), all exported for direct reuse.
- `assets/fonts/` — the static font weights the shipped templates actually use.
- `scripts/render-check.mjs` — renders every template through real Satori + resvg and writes PNGs; run after any template change.
