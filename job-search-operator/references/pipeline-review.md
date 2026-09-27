# Review the Pipeline

Use the workspace contract. Set `SKILL_ROOT` to the directory containing
`SKILL.md`; use its resolved `PROFILE`, `APPLICATIONS`, `NETWORK`,
`POSITIONING`, and `PIPELINE` paths. Read the canonical profile and pipeline,
then each active application's matching record before making changes.

## Review active work

Review all applications in these active statuses: Researching, Networking,
Drafting, Ready, Applied, Interviewing, and Offer. For each one, identify a
missing or stale next action, owner, date or trigger, and any follow-up due.
After 5–7 business days without a response, draft a useful follow-up only when
there is a meaningful reason and no clear no; do not infer rejection from
silence.

When evidence changes fit, access, interest, terms, or timing, rescore with:

```sh
python3 "$SKILL_ROOT/scripts/score_opportunity.py" FIT ACCESS INTEREST TERMS TIMING
```

Preserve `U` ratings and the script's provisional range and midpoint; do not
replace unknowns with assumptions or hand-calculate a score. Treat positioning
signals as patterns, not a single response. Update the positioning record only
when an external signal changes the audience, claim, or message.

Archive an opportunity only when it has no meaningful next step. Keep silent
applications active until a confirmed terminal event or a deliberate archival
decision. For each affected opportunity, update its application log and the
pipeline only for confirmed changes, recording date, action, result or status,
and next action.

## Diagnose the funnel

For a stated review window, count qualified opportunities evaluated,
applications submitted, direct outreach touches sent, positive replies,
recruiter screens, hiring-manager interviews, later-stage interviews, and
offers. Show both numerator and denominator for conversion rates. Segment only
when the sample supports it, prioritizing source or channel, role family,
and positioning angle.

Identify the narrowest evidence-supported bottleneck and recommend one bounded
experiment for the next review window. Examples include widening discovery
within a qualified role family, changing the first outreach touch, strengthening
proof for a recurring screen objection, or revising the core CV. Do not use
an arbitrary target such as a fixed number of applications or interviews, and
do not sacrifice fit, interest, or truthful targeting merely to increase volume.
Treat simultaneous interview processes as optionality, not a bluff; never
claim competing processes that do not exist.

## Plan the next week

Name the three highest-value actions for the next week, considering deadline,
fit, access, expected leverage, the diagnosed bottleneck, and a concrete owner
and timing. Use pipeline
statuses exactly as defined by the pipeline asset:

| Situation | Status |
| --- | --- |
| Applying after evaluation | Drafting |
| Building a warm path | Networking |
| Monitoring or researching | Researching |
| Validated materials awaiting submission | Ready |
| Submitted application | Applied |
| Confirmed interview process | Interviewing |
| Confirmed offer | Offer |
| Confirmed rejection | Rejected |
| Candidate ends pursuit | Withdrawn |
| Role or process ends | Closed |
| No meaningful next step | Archived |
