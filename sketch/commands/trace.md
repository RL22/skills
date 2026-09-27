# sketch trace

Redraw an existing page as a sketch by **compiling** it — no judgment calls in the loop. A page is captured
once into a frozen **snapshot**, and `trace.mjs` turns the snapshot into a spec by fixed rules, so the same
snapshot always yields the same sketch. The rules (the trace grammar) are the header of `scripts/trace.mjs`.

## Steps

1. **Snapshot** (the only step that touches the network):
   ```bash
   node <skill>/scripts/snapshot.mjs <url|file.html> -o <dir>/<name>.snap.json    # --mobile for 390×844
   ```
   Writes `<name>.snap.json` plus a generation-addressed `capture-<generation>.png` (what the page looked like).
   The JSON is published last and records the screenshot filename and SHA-256 integrity hash, so it is the
   canonical commit marker. Commit both next to the image: the snapshot *is* the source; recapture only when
   you mean to update the sketch. Failed captures leave an existing snapshot JSON usable.
2. **Compile**: `node <skill>/scripts/trace.mjs <name>.snap.json -o <name>.json` (`--full` for up to four
   screens of scroll instead of the first viewport).
3. **Render** (SKILL.md loop step 4) and compare the render with the `screenshot.file` named in the snapshot.
4. **Correct with overrides, never by editing the spec.** Put every correction in `<name>.overrides.json`,
   re-run step 2 with `--overrides <name>.overrides.json`, and repeat. The spec stays a pure output.
5. To use the trace inside a `redesign` or `flow`, reference the compiled spec's frame as a starting point
   for those boards.

## Overrides

Matchers: `"text=Exact label"` · `"#id"` (element or any ancestor) · `".class"` (the element's own) ·
a node `path` from the snapshot (matches that element and everything inside it).

```jsonc
{
  "hide":     ["#onetrust-consent-sdk", "text=Chat now"],        // drop nodes
  "keep":     [".sticky-promo"],                                  // exempt from the automatic drops
  "primary":  "text=Start free",                                   // or false for no hatched button
  "label":    { "text=Start your 14-day free trial": "Start free" },
  "real":     ["text=Pricing"],     "squiggle": ["text=Customers"],  // force words / force squiggles
  "as":       { ".hero-art": "image" },                            // reclassify
  "notes":    [{ "at": "text=Start free", "text": "only CTA above the fold", "side": "right", "ink": "green" }],
  "title": "Stripe — home", "paper": "plain", "seed": 7, "width": 760, "full": false
}
```

## Checks

- Every region you can see in `<name>.png` above the fold has a counterpart in the sketch, in the same place.
- Exactly one hatched button, and it is the page's main call to action (else set `primary`).
- Anything in the screenshot that is decoration, a banner, or a widget is absent (else `hide` it).
