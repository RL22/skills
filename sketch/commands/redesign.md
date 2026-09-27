# sketch redesign

Old vs new for a page or flow: a CURRENT row drawn small, a NEW row drawn large and numbered, the
rationale in margin notes. Template: `examples/redesign.json`.

## Gather

- The current screens (a `trace` of the live page is a good start) and the new ones.
- The 2–4 changes that matter and why, each tagged kept, added, or removed.

## Compose

1. `heading` "CURRENT", then the current screens small (about 150px wide) with arrows between them.
2. `heading` "NEW", then the new screens large, same size, with `step` numbers.
3. A `note` per change, pointing into the new screen: grey for explanations, `ink: "green"` for kept,
   `ink: "red"` for removed or risky. At most one accent colour per page carries meaning.
4. Where a whole section of the old page is gone, a green or red note on the CURRENT row says so.

## Checks

- The NEW row reads as the hero: larger, numbered, and carrying most of the notes.
- Every red/green note is a kept/removed claim, never decoration.
