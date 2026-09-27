---
name: programmatic-brand-assets
description: Use when designing logos, favicons, PWA icons, app icons, brand marks, or brand asset packages from SVG, Canvas, p5.js, or deterministic geometric code. For Open Graph / social preview cards, use og-image instead.
metadata:
  author: Sprintz
  version: "0.1.0"
  category: brand-and-design
---

# Programmatic Brand Assets

## Overview
Create brand assets from deterministic vector or canvas code, with SVG as the source of truth and raster files as generated outputs. Prioritize reproducibility, clean geometry, and production export coverage over ad-hoc visual mockups.

## When to Use
- User asks for a logo, brand mark, icon set, favicon, app icon, or brand asset package.
- User wants code-generated, repeatable, pixel-consistent visual assets.
- User provides an existing SVG/mark and asks for web-ready derivatives.
- For Open Graph images, Twitter/X cards, and social preview cards, use the `og-image` skill instead.

Do not use this for one-off bitmap image generation unless the bitmap is only supporting research or presentation.

## Required Workflow
1. Interview briefly for brand name, audience, tone, constraints, colors, and required deliverables.
2. Explore 3-5 distinct SVG concepts. Use parallel sub-agents only when the active environment and user explicitly allow sub-agent work.
3. Refine the selected direction across required layouts: horizontal lockup, vertical lockup, square layout, isolated mark, and text-only when relevant.
4. Export raster derivatives immediately after writing SVG files.
5. Validate dimensions, transparency, contrast, and repeatability before claiming completion.

## SVG Source Rules
- The primary asset is semantic SVG with explicit `width`, `height`, `viewBox`, `role`, `title`, and `desc`.
- Use pure SVG geometry, CSS inside the SVG wrapper, or deterministic Canvas/p5.js output that is converted to SVG when possible.
- Do not embed remote fonts or external images. If typography is critical, use local/project fonts available to the export pipeline or convert final wordmarks to paths.
- Keep coordinates, spacing, stroke widths, radii, and color tokens explicit.
- Prefer reusable groups and classes over duplicated style attributes when it improves readability.

## Determinism Rules
- Never use unseeded randomness. Replace `Math.random()` with a fixed-seed PRNG.
- Record the seed in the SVG metadata or adjacent README.
- Use fixed aspect ratios, absolute viewBox coordinates, and deterministic stroke arrays.
- Re-running the generator must produce byte-identical or visually identical coordinates.

Minimal JavaScript PRNG:

```js
function mulberry32(seed) {
  return function next() {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
```

## Asset Matrix
- Favicons: `16x16`, `32x32`, `48x48`, plus `favicon.ico` when the project uses it.
- PWA/app icons: `180x180`, `192x192`, `512x512`; include maskable variants when requested.
- Logo exports: include SVG source plus PNG/WebP at useful sizes such as `512`, `1024`, and `2048`.
- Social previews / Open Graph cards: Handled by the `og-image` skill.
- Preserve transparent backgrounds for marks and logos unless a platform requires a solid background.

## Dynamic Social Cards
Dynamic social cards, Open Graph previews, Twitter/X cards, and `@vercel/og`/Satori template generation are handled exclusively by the `og-image` skill. Refer to `og-image` for layout archetypes, JSX templates, font loading, Satori constraints, and metadata generation.

## Export Commands
After creating each SVG, run local conversion immediately. Prefer the user's requested sharp command when available:

```bash
npx sharp input.svg -o output.png && npx sharp input.svg -o output.webp
```

If that CLI is unavailable, use an installed equivalent such as `sharp-cli`, `resvg`, `rsvg-convert`, Inkscape, or Python Pillow, and report the exact command used.

## Validation Checklist
- SVG opens without external network dependencies.
- Exported PNG/WebP files exist at every required size.
- Exported assets match exact pixel dimensions and aspect ratios.
- Small favicon sizes remain recognizable.
- Layout variants share consistent geometry, colors, and spacing.
- No unseeded randomness remains in generators.

## References
- https://github.com/neonwatty/logo-designer-skill
- https://github.com/alonw0/web-asset-generator
- https://github.com/rknall/claude-skills/tree/main/svg-logo-designer
