# sketch screen

One screen drawn large, the way a designer explains a layout: the frame in the middle, grey margin notes
with leader lines naming its parts. Template: `examples/screen.json`.

## Gather

- The screen's job in one sentence, and its regions top to bottom (nav, hero, content, form, footer…).
- The 3–6 parts worth explaining: why they exist, what they do, what's unusual.

## Compose

1. One `screen`, 420–640px wide, `chrome` matching the surface (`browser`, `phone`, `panel`, `modal`).
2. Regions as `stack`/`row`/`grid` children in reading order; give each explained part an `id`.
3. Real words only for the nav items, the headline, and the primary action; the rest squiggles.
4. One `note` per explained part, `near` the screen on the side closest to the part, `to` the part's `id`
   (use `id@x,y` to land inside large regions). Alternate sides so leader lines never cross.
5. Optional: `cursor: true` on the element the user is about to touch.

## Checks

- Every note's leader line lands on the part it names; no two leader lines cross.
- Notes sit in the margin, never over the frame.
