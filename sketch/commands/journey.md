# sketch journey

A customer journey map: phases across the top, what the person does, how it feels (an emotion curve through
touchpoints with their thoughts), and the opportunities each phase opens. Template: `examples/journey.json`.

## Gather

- One persona and one scenario ("first project with a studio"). 3–5 phases.
- Per phase: 2–3 actions, 1–3 moments with a feeling score from −2 (frustrated) to +2 (delighted), the
  channel (`touch`: web, email, call, form, social…), and the thought in their words; 1–3 opportunities.

## Compose

1. One `journey` item with `w` about 1100–1200 and a `phases` array (`title`, `actions`, `points`, `opportunities`).
2. Real words for phase titles, the key actions, and every `note` (the quotes are the point); squiggles
   (`"~~"`) for filler actions and opportunities.
3. `highlight: <phase index>` hatches the phase the story is about; `meta: { persona, scenario, timeline }`
   adds an overview row on top. A key of the channels used (`touch`) is drawn automatically.
4. `points[].side: "above" | "below"` moves a thought card when two collide.

## Checks

- The curve's lowest point is the pain the case study addresses, and it carries a note.
- Every opportunity answers a low point in its own phase.
