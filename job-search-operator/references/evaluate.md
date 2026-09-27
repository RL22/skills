# Evaluate an Opportunity

Use the workspace contract. Set `SKILL_ROOT` to the directory containing
`SKILL.md`; use resolved `WORKSPACE`, `PROFILE`, `APPLICATIONS`, and
`APPLICATION` paths from that contract. Create or update only the single
matching application record, preserving user content.

## Extract and label

Parse the job description exactly for company, role, responsibilities,
qualifications, terms (location, arrangement, compensation, eligibility),
source, and contacts. Trust a pasted description unless verification is asked.
Verify time-sensitive decision facts and the official mission before relying on
them. Prefer official sources; write every URL, access date, and provenance in
the application’s `Sources and Evidence` table.

Label every conclusion `user-provided`, `sourced`, or `inference`. Separate
stated requirements from inferred needs. Continue with nonessential unknowns;
state them instead of inventing an answer.

## Assess fit

Map each material requirement to specific canonical-profile evidence. List every
unsupported requirement as a gap; adjacent experience is not proof. Rate each
category `1`–`5` or `U`:

| Category | Rate based on |
| --- | --- |
| Fit | requirement-to-evidence match |
| Access | warm paths and reachable decision-makers |
| Interest | candidate-stated motivation and mission match |
| Terms | acceptable location, pay, eligibility, and arrangement |
| Timing | deadline, hiring stage, and candidate availability |

Run the exact score calculation in this order:

```sh
python3 "$SKILL_ROOT/scripts/score_opportunity.py" FIT ACCESS INTEREST TERMS TIMING
```

Use its exact output and arithmetic: report the exact integer when known, or
its provisional range, midpoint, and unknown categories. Do not hand-calculate
or round a different score.

## Decide and record

Recommend exactly one: **Apply**, **Network**, **Monitor**, or **Pass**, based
on evidence, gaps, ratings, score, and deadline. Provide one concrete next
action with an owner and date or trigger. Map the decision to pipeline status:
Apply → Drafting; Network → Networking; Monitor → Researching; Pass → Archived.

Save the role snapshot, evidence map, gaps, ratings, score, decision, sources,
and next action in `APPLICATION`. Update its log and pipeline after meaningful
work; update network only after outreach and positioning only after an external
signal changes the message.
