# sketch responsive

One page at desktop, tablet and phone, side by side at a single scale, so the layout changes are the story.
Built from snapshots like `trace`, so it is deterministic after the first capture.
Template: `examples/responsive.json` (compiled from `tests/fixtures/landing.html`).

## Steps

1. Capture and compile:
   ```bash
   node <skill>/scripts/responsive.mjs <url|file.html> -o <dir>/<name>
   ```
   Writes generation-stamped breakpoint snapshots, `capture-<generation>.png` screenshots,
   `<name>.responsive.snap.json`, and the board spec `<name>.json`. The responsive snapshot JSON is the
   canonical bundle manifest and is atomically published only after all three captures validate, so a failed
   recapture leaves the previous complete set usable. Re-running uses that bundle only when its source identity,
   snapshot format, breakpoint viewports, and screenshot hashes match; otherwise it recaptures. Pass
   `--recapture` to refresh a valid bundle on purpose. Older generation files remain on disk so readers
   using a previous bundle can finish; remove unreferenced generations during separate maintenance.
2. Correct with an overrides file as in [trace.md](trace.md) (`--overrides <name>.overrides.json`). Top-level keys
   apply to every frame; `"breakpoints": { "phone": { "hide": [...] } }` adds to one frame only. A note lands on
   every frame unless it names one: `{ "at": "text=Menu", "text": "…", "breakpoint": "phone" }`.
3. Render (SKILL.md loop step 4) and compare each frame with the screenshot named by its snapshot JSON.

For a page that doesn't exist yet, write the three frames by hand instead: three `screen`s with `chrome`
`browser`, `browser`, `phone`, widths about 540 / 320 / 165 and the same content re-flowed.

## Checks

- Each frame matches its screenshot's structure; the differences between frames are real layout changes.
- The phone frame shows how navigation collapses (hamburger, stacked buttons).
