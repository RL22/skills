# {{company_name}} — {{target_role}}

Target role: {{target_role}}
Company: {{company_name}}
Status: Researching
Opportunity score: {{opportunity_score}}
Next action: {{next_action}}
Follow-up date: {{follow_up_date}}
Job URL: {{job_url}}
Location: {{location}}
Work arrangement: {{work_arrangement}}
Source: {{opportunity_source}}
Date identified: {{date_identified}}

Use `Opportunity score: 76` for an exact score, or
`Opportunity score: 48–80 provisional; midpoint 64` for a provisional score.
Set `Status: Ready` only after the application validator passes.
Keep each top-level metadata field to one line. A Ready record needs a
substantive tailored resume, a non-placeholder human-moment attestation, and an
application-log row with meaningful Date, Action, Result, and Next step values.
These checks use structural heuristics, not semantic proof: include a multiword
resume body detail, a multiword human-moment detail, and multiword log Action,
Result, and Next step values rather than short filler such as `abc` or `xx`.

## Company and Target Metadata

- Company metadata: {{company_name}}
- Role metadata: {{target_role}}

## Role Snapshot

- Needs: {{role_needs}}
- Business problem: {{business_problem}}
- Hiring signals: {{hiring_signals}}

## Fit Assessment

{{fit_score_table}}

- Fit: {{fit_summary}}
- Evidence: {{fit_evidence}}
- Gaps: {{fit_gaps}}
- Angle: {{application_angle}}
- Decision: {{application_decision}}

## Sources and Evidence

| Claim | Status (user-provided/sourced/inference) | URL | Accessed |
| --- | --- | --- | --- |
| {{claim}} | {{claim_status}} | {{source_url}} | {{access_date}} |

## People and Outreach

| Person | Role | Relationship | Outreach status | Next step |
| --- | --- | --- | --- | --- |
| {{person_name}} | {{person_role}} | {{relationship}} | {{outreach_status}} | {{next_step}} |

## Cover Letter

- {{candidate_name}}
- {{candidate_email}}
- {{candidate_phone}}
- {{candidate_location}}

For `Status: Ready`, add a confirmed record in this form:
`- Human moment: User-verified — {{non_sensitive_mission_linked_detail}}`.
This explicit user-verification record is required by validation; it does not
by itself prove the detail's authenticity.

{{cover_letter}}

## Tailored Resume

- {{candidate_name}}
- {{candidate_email}}
- {{candidate_phone}}
- {{candidate_linkedin_url}}
- {{candidate_portfolio_url}}

### Target Role

{{target_role}}

### Summary

{{resume_summary}}

### Core Skills

{{core_skills}}

### Technical Skills

{{technical_skills}}

### Professional Experience

For every role included, use a level-three heading in the format
`Held Title | Employer | Month YYYY–Month YYYY`.

{{professional_experience}}

### Education

{{education}}

## Alignment Check

{{alignment_check}}

## ATS Checklist

- [ ] {{ats_keyword_check}}
- [ ] {{ats_format_check}}
- [ ] {{ats_contact_check}}

## Application Log

| Date | Action | Owner | Result | Next step |
| --- | --- | --- | --- | --- |
| {{log_date}} | {{log_action}} | {{log_owner}} | {{log_result}} | {{log_next_step}} |

## Interview Notes

{{interview_notes}}
