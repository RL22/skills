---
name: sketch
description: Sketch UI as hand-drawn, lo-fi wireframe images rendered from a JSON spec — a user flow, a single screen, a component sheet, an iteration (rejected vs refined), a redesign (current vs new), a sitemap, a customer journey map, a trace of an existing page, or its responsive breakpoints. Use for /sketch, "sketch this", "wireframe", or design assets for case studies, posts, pitches, or docs.
license: MIT
compatibility: "Agent-agnostic (Agent Skills standard). Needs Node 20+ and a headless Chromium via playwright-core — rendering runs rough.js and real font metrics in a browser, which shell/python alone cannot do. No agent-specific binaries."
argument-hint: "<flow|screen|sheet|iterate|redesign|sitemap|journey|trace|responsive|photo> [what to sketch]"
metadata:
  author: Rodney Lewis
  version: "0.4.0"
  style_source: "Inspired by the hand-drawn planning notes AJ published in The Making of Carrd (https://themakingof.carrd.co/#extras-notes). No reference images are included."
---

# sketch

Every image is a **notebook page**: black felt-tip on cream paper, drawn in one fixed **sketch grammar**
(hatch = primary, squiggle = copy, X-box = image, dashed = empty/add). You write a JSON spec; the renderer
draws it with seeded rough.js, so the same spec and seed give the same page every time.

## Commands

**Inputs:** the first word of the request is the command (table below); the rest is the subject — what to
draw, plus a URL or HTML file for `trace`/`responsive`, and optionally where to save the image.
**Output:** a spec (`<name>.json`) and its render (`.jpg`/`.png`/`.svg`) in the calling project.
Load the command file before writing a spec.

| Command | Draws | File |
|---|---|---|
| `flow` | a user journey: screens left→right, curved arrows, ①②③ | [commands/flow.md](commands/flow.md) |
| `screen` | one screen up close, every part labelled in the margin | [commands/screen.md](commands/screen.md) |
| `sheet` | a component library page: headed sections of variants | [commands/sheet.md](commands/sheet.md) |
| `iterate` | A `vs.` B, the rejected one struck out, the refined one drawn larger | [commands/iterate.md](commands/iterate.md) |
| `redesign` | CURRENT row small, NEW row large, rationale in red/green notes | [commands/redesign.md](commands/redesign.md) |
| `sitemap` | information architecture: page thumbnails in a tree, badges + legend | [commands/sitemap.md](commands/sitemap.md) |
| `journey` | customer journey map: phases, actions, emotion curve, opportunities | [commands/journey.md](commands/journey.md) |
| `trace` | an existing page compiled into a sketch from a frozen snapshot | [commands/trace.md](commands/trace.md) |
| `responsive` | one page at desktop, tablet and phone, side by side | [commands/responsive.md](commands/responsive.md) |
| `photo` | a finished render turned into a photo of a real notebook page | [commands/photo.md](commands/photo.md) |

No command given → pick it from the request with the table above and say which you picked. Nothing fits →
show the table and ask.

## Every command runs this loop

1. **Setup** — once per machine with Node 20+: `npm install` in this skill's folder.
2. **Start from the command's example**: copy `examples/<command>.json` next to where the image will live
   (the calling project, e.g. `public/case-studies/<slug>/`). This skill folder holds templates only.
   `trace` and `responsive` compile their spec from snapshots instead — their files replace steps 2–3.
3. **Write the spec.** Fields and components: [references/spec-schema.md](references/spec-schema.md).
   What each mark means and how boards compose: [references/notation.md](references/notation.md).
   Ready-made page archetypes for thumbnails (`{"type":"page","template":"pricing"}`): [references/pages.md](references/pages.md).
4. **Render**: `node <skill>/scripts/render.mjs <spec>.json -o <name>.jpg --strict` (`.png` for print,
   `.svg` for an editable file; `--help` for the rest).
5. **Look at the image** (Read it) and walk every item of
   [references/critic-checklist.md](references/critic-checklist.md) plus the command file's own checks.
6. **Loop 3–5 until clean**, at most 3 passes, then show the human what still fails.
   The page is **clean** when `--strict` exits 0 and every checklist item is YES.

For an independent second look, hand the checklist and the image to another vision-capable model or reviewer.

## House style

- **Real words carry the story**: headings, button labels, the one field that matters. Every other
  line of copy is a `"~"` squiggle.
- **Hatch the one primary action** per screen; everything else is outline, ghost, or link.
- **Ink is black; notes are grey.** Add a single red or green accent only when it means something
  (red = removed/risk, green = kept/good).
- **Screens in a row share a top edge and a height.**
- **Every note points**: give it `to:` so it draws a leader line into what it describes.
- **One idea per page**, about 1300px wide at most. A longer story becomes two pages.

## Maintaining the skill

`npm test` renders every `examples/*.json` twice (fails on any warning or pixel difference) and runs the
trace tests against `tests/fixtures/`;
`npm run previews` also refreshes `examples/*.jpg`. Look lives in `scripts/lib/tokens.js`, marks in
`scripts/lib/components.js`, placement and annotations in `scripts/lib/board.js`, the trace grammar in `scripts/trace.mjs`.
A new command = `commands/<name>.md` + `examples/<name>.json` + one row in the table above.
