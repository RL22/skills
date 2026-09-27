# sketch flow

A user journey told left→right: one **frame** per step, curved arrows for the transitions, circled step
numbers above. Template: `examples/flow.json`.

## Gather

- The journey's start and end state, and every screen the user actually sees between them.
- For each transition, the **trigger**: the element the user acts on (a button, a menu item).

## Compose

1. List the frames in order; keep 3–5. A longer journey splits into two pages, or its middle steps
   collapse into one frame labelled with a note.
2. One `screen` per frame, all the same `h` and `w` (modals and dialogs may be smaller but share the top edge).
   `chrome`: `browser` for the first web page, `modal` for dialogs, `plain` elsewhere.
3. Inside each frame, draw only what the step needs: the trigger element with a real label and an `id`,
   everything else squiggles and X-boxes.
4. `arrow` from each trigger's `id` to the next frame; add `label` only when the trigger is not visible
   in the frame ("menu > Save").
5. `step` 1…n on the frames; one or two grey `note`s on the moment that matters (the aha, the friction).

## Checks

- Every arrow starts on the element that causes the transition.
- A reader can follow the journey from the arrows alone, without reading the notes.
