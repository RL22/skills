# Spec schema

A board spec is JSON. Unknown `type` values fail the render with a clear error.

```jsonc
{
  "paper": "grid",        // grid | plain | white
  "seed": 12,             // different seed = different "hand"; same seed = identical image
  "title": "Signup flow", // optional, double-underlined, top-left
  "width": 1200,          // optional; omitted = fit content. Also enables auto-wrap of rows
  "height": 700,          // optional; omitted = fit content
  "margin": 44, "gap": 90,// board margin and gap between auto-placed items
  "wobble": 1,            // 0–2 ink wobble filter on strokes (never on text)
  "items": [ ... ]        // placed items, then annotations
}
```

## Placing items

Every non-annotation item is any component (usually `screen`, `stack`, `heading`, `card`). Placement, first match wins:

1. `"x": 40, "y": 120` — absolute.
2. `"at": { "rightOf": "id" | "leftOf" | "below" | "above", "gap": 60, "dx": 0, "dy": 0 }` — relative to an earlier id.
3. Auto flow — items go left→right with `gap`; `heading`, `text`, `bullets` (or `"newRow": true`) start a new row.

`w` accepts px or `"50%"` (of parent width). Board-level default widths: screen 260, heading/text/bullets 700, others 240.

## Common fields (any component)

`id` (for arrows/notes), `w`, `h`, `align` (`left|center|right` within parent), `fit` (shrink to intrinsic width),
`selected` (dashed selection box), `cursor` (draw a cursor on it).

`ink` (`note|red|green|blue|#hex`) is honoured by: `screen`, `card`, `heading`, `text`, `squiggle`/`paragraph`,
`bullets`, `button`, `image`/`video`, `badge`, `divider`, and every annotation. Other components draw in default ink.

## Components

| type | fields |
|---|---|
| `screen` | `chrome` plain\|browser\|phone\|modal\|panel, `title`, `close`, `menu`, `zigzag`, `dashed`, `clip` (hide overflow, warn), `pad`, `gap`, `children` — **give it `h`** |
| `stack` | `children`, `gap` |
| `row` | `children`, `gap`, `justify` start\|center\|end\|between, `valign` center\|top |
| `grid` | `cols`, `gap`, `children` |
| `card` | `children`, `dashed`, `pad`, `r` |
| `heading` | `text`, `size` (22), `underline` true\|false\|2 |
| `text` | `text` (`\n` ok), `size`, `font` hand\|note\|alt, `overflow: "fit"` (shrink, then truncate to `w`) |
| `squiggle` / `paragraph` | `lines`, `thick`, `align` |
| `bullets` | `items: ["a", {"text":"b","items":["c"]}]`, `size` |
| `button` | `label`, `variant` primary\|outline\|ghost\|link, `pill`, `size` sm |
| `input` / `textarea` | `label`, `placeholder`, `value`, `filled`, `rows` |
| `dropdown` | `label`, `value` |
| `slider` | `label`, `value` 0–1, `display` |
| `toggle` | `label`, `on` |
| `checkbox` / `radio` | `label`, `checked` |
| `tabs` | `items`, `active` |
| `image` / `video` | `h` or `ratio`, `label` |
| `avatar` / `logo` | `d`, `figure` |
| `add` | `label`, `h` · `plus` (circled +) |
| `icons` | `n` or `items: ["t","f"]`, `d` |
| `nav` | `items` or `n`, `logo`, `cta` true\|"Label", `menu`, `align` |
| `divider` | `label` ("OR"), `dashed` · `more` (tick marks) |
| `table` | `cells: [[...]]` or `rows`/`cols`, `header` |
| `list` | `items` or `n`, `mark` check\|dash\|dot\|num\|circle |
| `menu` / `popover` | `items`, `dividers: [i]`, `caret` top\|none, `caretX` |
| `badge` | `label` (a pill; with `target` it becomes the numbered badge annotation below) · `placeholder` (`label`, `dashed`) · `chart` (`bars`, `kind` line, `highlight`) |
| `cursor` · `spacer` (`h`) · `burger` (`d`) | |
| `page` | `template` (see pages.md), `label` (false hides it), `w`, `h` (default w×1.3), template options |
| `tree` | `root: { id, label, template?, badge?, dashed?, children }`, `nodeW` (120), `nodeH`, `gapX`, `gapY` |
| `legend` | `items: ["text", {n, text}]`, `cols` (4), `ink` (badge colour, default red) |
| `journey` | `w`, `phases: [{ title, actions, points: [{ score −2…2, touch, note, side }], opportunities }]`, `highlight`, `meta: { persona, scenario, … }`, `rows`, `labels`, `experienceH` |

Any string that is only `~` characters (`"~"`, `"~~~"`) renders as a squiggle of proportional length.

## Annotations (drawn after placement; reference ids)

Point refs: `"id"`, `"id.right"` (left\|right\|top\|bottom edge), `"id@0.3,0.8"` (relative point inside the box), or `[x, y]`.

| type | fields |
|---|---|
| `arrow` | `from`, `to`, `bend` (−0.5…0.5, default −0.18), `route: "elbow"` (right-angle, sitemap style), `label`, `dashed`, `ink` |
| `note` | `text`, `to` (leader target), `x`/`y` **or** `near` + `side` right\|left\|top\|bottom + `offset` + `fx`/`fy`, `arrow` false, `ink`, `size`, `underline` |
| `strike` | `target`, `verdict` |
| `vs` | `between: [a, b]` or `x`/`y`, `text` |
| `step` | `n`, `target` (circled number above) or `x`/`y` |
| `badge` | `n`, `target`, `corner` tr\|tl\|br\|bl, `ink` (filled numbered disc, pairs with `legend`) |

## Output

stdout: `{"out", "width", "height", "scale", "browser", "warnings": [...]}`. Warnings = screen content overflowing its
bottom padding, rows wider than their container, content past a fixed board size or at negative coordinates, duplicate ids.
`--strict` makes warnings exit 2. Output format follows the `-o` extension (`.png` `.jpg` `.svg`; SVG embeds its fonts).
Spec errors (unknown type, unknown id, `grid.cols` < 1) exit 1.
