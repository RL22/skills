# `@vercel/og` / `ImageResponse` Implementation Rules

Practical constraints for rendering the templates in `design-system.md` with Satori (the engine behind `next/og`'s `ImageResponse`). Source: sdorra.dev, "Social Media Cards with @vercel/og" (2022), cross-checked against current Next.js docs.

## Satori is a constrained renderer, not a browser

- Use `display: flex` and absolute positioning for layout. **No CSS Grid** — Satori doesn't support it.
- **No `inset` shorthand.** Satori does not implement it; use the four longhand properties (`top`/`right`/`bottom`/`left`: `0`) instead. Confirmed by direct render: an `inset: 0` full-bleed layer silently occupies zero space rather than erroring, so this fails quietly, not loudly.
- **The `radial-gradient(color 1px, transparent 1px)` dot-grid trick does not render in Satori.** Browsers default an unqualified radial gradient's size to the *closest-side* of its box; Satori's implementation instead reaches the *farthest corner*, so a "1px dot" stop collapses to a sub-pixel point and produces a visibly blank layer — confirmed by isolated render, not just SVG inspection (the generated SVG *looks* structurally plausible; only rendering it revealed the dot was invisible). Use the **line-grid** variant instead (two crossed `linear-gradient`s with hard 1px stops on `to right` / `to bottom`) — verified to render correctly.
- No CSS variables. `filter`/`feTurbulence`-based SVG data URIs (as used for the noise overlay motif) do render, but every SVG embedded that way **must declare an explicit `viewBox`** — Satori throws `missing "viewBox"` otherwise, even though the same markup works fine as a plain `<img>` in a browser.
- `backdrop-filter`, CSS 3D transforms (`rotateY`/`rotateX`), and most `filter` values used directly as element styles (not inside an embedded SVG) are unreliable-to-unsupported in Satori despite reading as plausible CSS — `design-system.md` documents these because real sites use them in a browser, not because they're safe to copy into a template here. Treat anything in `design-system.md` as a design reference to reinterpret through Satori-safe primitives (gradients, SVG data URIs, flex layout), not as CSS to paste verbatim.
- Inline styles only. Don't depend on a project's Tailwind config — utility classes may silently fail to apply.
- Every visual motif needs to be expressed as an inline-style gradient/SVG data URI, not an external stylesheet — and needs to be *rendered*, not just type-checked, to confirm it's actually visible (see Debugging below).

## Fonts need explicit handling

- Load only the weights actually used by a template — don't bundle a whole variable font.
- Prefer static `.ttf`/`.otf` files (faster parsing than variable fonts). Google's upstream repo often ships OFL families as a single variable-weight file (`Family[wght].ttf`) with no static cut — fetch a specific weight instance from Google Fonts' CSS2 API instead (`fonts.googleapis.com/css2?family=Family:wght@700`) rather than assuming a static file exists.
- Pass font data into `ImageResponse` via its `fonts` option using the **unquoted** family name (`name: "Space Grotesk"`) — `BrandTokens.fontTitle` is the **quoted** CSS string (`'"Space Grotesk"'`) used inside a `fontFamily` style; the two are not interchangeable and nothing enforces they stay in sync, so check both when adding a font.
- This skill ships the actual weights each template uses in `assets/fonts/`: `SpaceGrotesk-600.ttf` (eyebrow), `SpaceGrotesk-700.ttf` (title — the family's static maximum; it does not offer 800/ExtraBold), `JetBrainsMono-500.ttf` (reserved for a future code/terminal template). Don't ask the calling project to supply fonts unless it wants to override the defaults.

## Asset size matters

- Never feed a full-resolution source image into `ImageResponse` — resize/crop to the exact display dimensions first. A large remote image is a common cause of function timeouts.
- Prefer template-driven vector/gradient backgrounds (Archetypes 2, 3, 5, 8 in `design-system.md`) over photography where the content allows it — zero asset-loading risk.
- When photography is required (Archetype 6, full-bleed), resize before rendering and always pair with the scrim-overlay contrast rules from `design-system.md` §5.

## Determinism (shared with `programmatic-brand-assets`)

- Never use unseeded `Math.random()` for noise textures, gradient angle jitter, or motif placement. Use a fixed-seed PRNG (mulberry32 — see that skill's reference) so re-rendering the same props produces the same pixels.
- Record the seed alongside generated output when a template intentionally varies (e.g. picking one of N background motifs) so the choice is reproducible, not silent.

## Dimensions and metadata

- `1200×630` (`1.91:1`) for Open Graph; `1200×675` for a distinct Twitter/X card if one is needed. Export both as separate `ImageResponse` exports when the platforms need to differ, otherwise one image covers both.
- App Router convention: **`opengraph-image.tsx`** (hyphenated — `opengraphimage.tsx` is not a recognized convention) / `twitter-image.tsx` route files, exporting `alt`, `size = { width, height }`, `contentType = "image/png"`. Next generates the `og:image`/`twitter:image` `<meta>` tags **automatically** from these files — don't also hand-write those two tags at the page level, or they can conflict.
- What file-based image generation does *not* cover: `og:title`, `og:description`, `twitter:card`, `twitter:title`, `twitter:description` are text metadata, set via `generateMetadata`/the page's `metadata` export, not derived from the image file. Set `metadataBase` in the root layout so relative asset URLs resolve to absolute ones in the generated tags.

## Debugging

- Use Satori's `debug: true` while tuning a new template layout (draws element bounding boxes), then remove it before shipping.
- **`tsc --noEmit` passing is not proof a template renders.** TypeScript has no idea `inset` is unsupported by Satori, that a bare `radial-gradient(color 1px, transparent 1px)` renders invisibly, or that an SVG data URI without a `viewBox` throws at render time — all three shipped past a type-check clean in this skill's own first draft. Run `scripts/render-check.mjs` (renders every template through the real `satori` + `@resvg/resvg-js` and writes PNGs) after any template change, and actually look at the output images, not just check that the process exited 0.
- Validate every export at its exact target dimensions — a template that "looks right" in a browser preview can still clip or misalign inside Satori's actual layout engine.
