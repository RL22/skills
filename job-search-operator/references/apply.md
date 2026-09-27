# Prepare an Application

Run evaluation first. Set `SKILL_ROOT` to the directory containing `SKILL.md`;
use resolved `WORKSPACE`, `PROFILE`, `APPLICATIONS`, and `APPLICATION` paths
from the workspace contract. Work in the single matching record and use the
profile and verified assets as the sole source for candidate claims. Never
invent or upgrade scope, title, seniority, ownership, management, tools, or
outcomes.

## Resume

Start from the single core CV and the canonical profile. Default to an opportunity-specific
delta pass: set the exact `Target Role`, reorder relevant verified evidence,
adjust the summary and emphasis, and add supported job-description language.
Do not rewrite every bullet merely to make the document look newly tailored.

Reserve deeper tailoring for a priority opportunity, a materially different
scope, or a real requirement-to-evidence gap that the base does not express.
Record which base was used and the meaningful deltas so later applications can
reuse what worked. Preserve held titles and month–year dates exactly as
canonical. Emphasize truthful impact, ownership, and team enablement. Add
job-description keywords only when profile evidence supports them.

Use an ATS-safe single-column layout: no tables, sidebars, graphics, text
boxes, or multi-column sections. Before setting `Status: Ready`, run:

```sh
python3 "$SKILL_ROOT/scripts/validate_application.py" "$APPLICATION" "$PROFILE" \
  --applications-dir "$APPLICATIONS"
```

Resolve every error. Set `Status: Ready` only after validation passes and every
contact detail, title, date, tenure, management claim, tool, and outcome aligns
across the profile and application.

The Ready validator uses structural minimums rather than semantic proof: the
resume needs a multiword body or achievement detail, the human-moment record
needs a multiword detail, and each log Action, Result, and Next step needs
multiword text. These checks reject short filler (for example, `abc` or `xx`),
but do not establish that a claim is true, relevant, or supported.

For Ready records, a leading standalone `TBD`, `TODO`, or `TBC` is unresolved
in every structured field and required-content block except `Company`, even
when followed by an instruction such as `TODO revise`. `Company` permits such
a prefix only when the whole remainder has one credible company shape: a
non-generic organization noun (such as `Health`, `Bank`, `Ventures`, or
`Technologies`), a domain, a distinctive mixed-case or digit-bearing token,
or multiple title-shaped brand words. Thus `TBD General Assembly`, `TBC Acme
Labs`, `TODO Foo Bank`, `TBC Health Systems`, and `TBD OpenAI` can pass, while
sole generic labels such as `TBD Company`, `TBC Agency`, `TBD Services`, and
`TODO Consulting` cannot. Known missing-field descriptors also make a value
unresolved, so `TBC Bank Details` and `TBD General Assembly role` fail.

These are deliberately non-semantic, token-shape heuristics: they cannot prove
that a company exists or that prose is accurate. Supply a sourced or verified
company value whenever a rare legitimate name is rejected. The validator also
rejects passive workflow notes beginning with `To be` only when the next word
is in its explicit workflow/completion-verb set (including `addressed`,
`researched`, `found`, `set`, `paid`, `given`, `held`, `left`, `done`, `sent`,
and `written`), rather than rejecting arbitrary `-ed` adjectives. It detects
immediate temporal `To do` phrases with whitespace tokens, including weekdays,
`tonight`, `during August`, `within a week`, and `at the interview`; it does
not reject ordinary prose such as `To do this well`, `To do in-depth research`,
or `To do more for users next week`.

## Cover letter

Write a role-specific letter with two or three verified accomplishments and the
mandatory, authentic mission-linked human moment. A completed letter requires a
selected fact-grounded direction plus an authentic, non-sensitive personal
detail explaining why the mission connects to the candidate; that detail may describe
an observed work context. Do not invent that connection. Verify mission claims
through official sources and write their provenance in `Sources and Evidence`.
Search the profile’s verified stories first. If no authentic connection is
available, offer two or three relevant story directions grounded only in known
facts. Keep the letter incomplete while the user selects one direction. Ask
exactly one focused selection question that explicitly asks the user to choose
one of the offered directions. The invitation to share the required completion
detail is voluntary: the user may share one non-sensitive, job-relevant personal
detail tied to the selected direction, including observed work context. Do not
ask for an incident or any detail that could reveal protected or sensitive
information. If the candidate declines the detail, leave the cover letter incomplete;
a selected direction alone is not sufficient to complete it.

For `Status: Ready`, record the confirmed detail in the completed Cover Letter
as `- Human moment: User-verified — [non-sensitive mission-linked detail]`.
The validator requires this exact, non-placeholder attestation so a generic
letter or a selected direction alone cannot be marked Ready. It cannot
semantically prove authenticity; the `User-verified` record is the explicit
confirmation required before completion.

Leave the letter incomplete and clearly awaiting that detail while continuing
the resume, evaluation, and records. To preserve the pending user decision
across turns, persist in the matching application's Cover Letter section the
offered two or three fact-grounded directions, the exactly one focused selection
question, and the voluntary detail invitation; do not reduce them to a generic
missing-story marker. Use the form that matches the number of offered
directions, substituting only known facts. The selection question must enumerate
only those offered directions:

### Two directions

```markdown
## Cover Letter

- Status: Incomplete — awaiting selected story direction
- Direction 1: [fact-grounded direction]
- Direction 2: [fact-grounded direction]
- Selection question: Which direction should I use: 1 or 2?
- Voluntary detail invitation: You may share one non-sensitive, job-relevant
  personal detail tied to the selected direction, including observed work context.
```

### Three directions

```markdown
## Cover Letter

- Status: Incomplete — awaiting selected story direction
- Direction 1: [fact-grounded direction]
- Direction 2: [fact-grounded direction]
- Direction 3: [fact-grounded direction]
- Selection question: Which direction should I use: 1, 2, or 3?
- Voluntary detail invitation: You may share one non-sensitive, job-relevant
  personal detail tied to the selected direction, including observed work context.
```

Save a verified story or human moment to the canonical profile only with the
user’s explicit permission.

## Finish and record

Perform a final alignment check across all contact details, titles, dates,
tenure, management claims, tools, and outcomes. Confirm the lowercase-hyphenated
record is the existing match and no duplicate exists. Update the application log
and pipeline after meaningful work; update network after outreach and
positioning after external signals.
