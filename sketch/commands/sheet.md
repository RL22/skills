# sketch sheet

A component library page: underlined section headings, each followed by a row of variants of the same
component, the way a spec sheet sits in a notebook. Template: `examples/sheet.json`.

## Gather

- The components in scope and, for each, the variants that differ in meaning (primary / outline / link;
  empty / filled / error) — the states a builder has to know about.

## Compose

1. Set `width` (about 1180) so rows wrap predictably; `gap` 50–60.
2. One `heading` per section (Buttons, Forms, Navigation, Content…).
3. Under each, one `stack` per component family, variants in `row`s, labelled with real words.
4. Where a variant needs its rules spelled out, put a `bullets` list of properties beside it.
5. A grey `note` for each convention a reader could miss (e.g. "hatch = solid / primary").

## Checks

- Each section shows at least two variants, and variants within a row differ in exactly one property.
- Sections read top-to-bottom without a component landing under the wrong heading.
