---
name: writing-for-humans
description: Draft, revise, or review clear, specific, ethical Sprintz writing for humans. Invoke when the user says "final draft", "write for human", or "writing for human", or asks for human-sounding writing, editing, or review.
metadata:
  author: Sprintz
---

# Writing for Humans

Use this skill for Sprintz content, agent responses, sales copy, proposals,
documentation, scripts, and other writing intended for people.

## Source of truth

Read `docs/writing-rules.md` from the active Sprintz workspace.

If the channel is known, apply its profile. If sources conflict:

1. Follow the current human instruction.
2. Apply the explicitly named channel profile.
3. Apply the universal rules in `docs/writing-rules.md`.
4. Flag unresolved conflicts. Do not silently choose.

Channel rules may change formatting, rhythm, or thresholds. They may not
override truthfulness, evidence, reader dignity, or safety.

## Workflow

1. Identify the reader, problem, desired outcome, and next decision.
2. Identify the channel and apply its profile.
3. Draft for clarity, specificity, structure, and usefulness.
4. Read `references/quality-checks.md` and perform the qualitative review.
5. Run the quantitative validator:
   `python3 scripts/validate_writing.py <draft-path>`
6. Resolve findings or explicitly explain accepted findings.
7. Return the draft and a concise review summary.

Keep qualitative judgment separate from mechanical validation.

## Final-draft behavior

When invoked with "final draft":

- Treat the request as a finishing pass, not permission to change the strategy.
- Preserve the author's meaning and claims.
- Improve clarity, cadence, specificity, structure, and channel fit.
- Do not invent proof, metrics, outcomes, or experience.
- Run both quality and quantitative checks before presenting the result.
- Report unresolved issues plainly.

## Output

Return:

1. The revised draft.
2. A short quality-check summary.
3. Quantitative validator findings, if any.
4. Assumptions or unresolved conflicts.
