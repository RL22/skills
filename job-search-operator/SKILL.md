---
name: job-search-operator
description: "Evaluate and score job descriptions; create tailored applications, resumes, and cover letters; draft LinkedIn or recruiter outreach; discover public professional company email for supplied contacts; prepare interviews and call cheat sheets; export ATS-safe materials; manage a pipeline and weekly review; produce a daily networking and engagement brief (posts to comment on, connections to DM, daily actions); or maintain reusable workspaces and candidate state."
author: "Sprintz"
date_added: "2026-08-12"
---

# Job Search Operator

## Start

1. Set `SKILL_ROOT` to this skill directory and identify the route first.
2. Read [workspace-contract.md](references/workspace-contract.md), then resolve `~/.config/job-search-operator/config.yaml` and load only the state declared by the route. Workspace setup may run the initializer without an existing config, profile, or pipeline.
3. When a target opportunity is identifiable—including an ambiguous request such as “help me with this” accompanied by a pasted role or job description—route to Evaluate first and record the evaluation as appropriate. Before downstream application work, seek approval or clarification. An explicit request to apply, tailor a resume, or draft a cover letter is approval; after evaluation, proceed with downstream drafting when the recommendation permits it. Ask one focused clarification without creating or updating records only when no target opportunity is identifiable or the non-opportunity route itself cannot be determined. Stop only when decision or risk requires it.

## Route

| Request | Load and follow |
| --- | --- |
| Workspace setup or config recovery | [workspace-contract.md](references/workspace-contract.md) only |
| Candidate profile or career-facts update | [workspace-contract.md](references/workspace-contract.md) only; verify the user-supplied fact or source and update the canonical profile |
| Network-only relationship update | [workspace-contract.md](references/workspace-contract.md) only; load [outreach.md](references/outreach.md) only when drafting a message |
| Positioning-state update | [workspace-contract.md](references/workspace-contract.md) only; load application or pipeline state only when tied to an opportunity or external signal |
| Evaluate a role or job description | [evaluate.md](references/evaluate.md) |
| Apply, tailor a resume, or draft a cover letter | [evaluate.md](references/evaluate.md), then [apply.md](references/apply.md) |
| LinkedIn or recruiter outreach | [outreach.md](references/outreach.md) |
| Research a supplied contact or public professional company email | [outreach.md](references/outreach.md) and [contact-discovery.md](references/contact-discovery.md) |
| Interview preparation or a call cheat sheet | [interview.md](references/interview.md) |
| ATS-safe export | [export.md](references/export.md) |
| Pipeline update or weekly review | [pipeline-review.md](references/pipeline-review.md) |
| Daily networking brief: posts to comment on, connections to DM, daily actions | [networking.md](references/networking.md) |

Load only the workspace contract and the route-specific references needed for the request; do not load unrelated references.

## Shared operating rules

- Treat pasted job descriptions as the working source. Verify selectively current, consequential company or mission claims before using them.
- Label evidence as `user-provided`, `sourced`, or `inference`; include source URLs and access dates where required. Never invent facts, metrics, titles, dates, contacts, or outcomes.
- Use `U` for unknowns and ranges where precision is unsupported. State assumptions and risks plainly.
- Search existing records first; update the matching record, preserve user edits, and never create duplicates.
- Draft messages and applications only. Never send, submit, or represent that outreach occurred without explicit user action.
- Use the supplied scripts for scoring, initialization, validation, and character limits when the relevant reference directs it.
- Optimize for qualified pipeline conversion and learning, not raw application volume. Use one core CV (the canonical profile), opportunity-specific delta edits, direct outreach where appropriate, and funnel evidence to decide where deeper effort is warranted.
- On partial failure, preserve completed work, record what remains, and give the next safe action.
