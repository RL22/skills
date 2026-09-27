# sketch iterate

Show a design decision: the options side by side, the rejected one struck through with its verdict, the
refined version drawn larger to the right. Template: `examples/iterate.json`.

## Gather

- The options that were really considered (2–3), the verdict on each in a few words ("Too complex",
  "Hides the CTA"), and what the chosen version changed.

## Compose

1. Options A, B… as same-size `screen`s at the left, auto-flowed, with `vs` between each pair.
2. `strike` every rejected option with its `verdict`; circle the problem area with a `"???"` note
   pointing into it when the reason is visual.
3. The refined version to the right (`at: {"rightOf": …, "gap": 110}`), larger and cleaner — it may split
   into several panels.
4. One grey `note` on the refined version naming the change that resolved the verdict.

## Checks

- Exactly one version is left un-struck, and it is the largest thing on the page.
- Each verdict is readable and sits under its own struck option.
