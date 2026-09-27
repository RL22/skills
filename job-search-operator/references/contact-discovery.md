# Contact Discovery

Use the workspace contract. Set `SKILL_ROOT` to the resolved directory
containing `SKILL.md` and use its resolved paths; do not hard-code paths. Always
read `NETWORK`. Read `PROFILE` only when using candidate claims;
`APPLICATIONS` and `PIPELINE` only when the research is tied to an opportunity;
and `POSITIONING` only when an external signal or positioning work is involved.
Preserve standalone contact discovery. Use user context, accessible public
profiles, official company pages, press releases, conference bios, and other
credible public sources. Do not depend on an authenticated LinkedIn session;
prefer an accessible LinkedIn profile when it supplies enough evidence.

Never bypass authentication barriers, scrape protected pages, use exposed
credentials, use deceptive collection, or query private databases. Use a
personal email only when its owner publicly offers it for professional contact.

## Verify the person

Confirm identity independently from email. Set `Identity status` to exactly
one of:

- `Confirmed`: current identity and role match credible public evidence.
- `User-supplied`: the user provided the identity; do not treat it as
  independently confirmed.
- `Unverified`: public evidence is insufficient or conflicting.

Check current role and company, alternate domains, initials, hyphens, duplicate
names, and job changes. A job change invalidates a prior company email unless
current evidence supports it. If `Identity status` is `User-supplied` or
`Unverified`, do not record an inferred email: set email status to `Not found`,
preserve the public profile URL if available, and make public-profile or
identity confirmation the next action.

## Find and assess email

First search for the exact public professional email on credible sources. Set
`Email status` to exactly one of:

- `Verified`: an exact email appears on a credible public source.
- `Inferred—High`: multiple current public examples establish the same-domain,
  same-format company pattern and the current person and company are verified.
- `Inferred—Medium`: limited but plausible current evidence supports the
  address; clearly retain the evidence and do not present it as verified.
- `Not found`: no responsible address can be recorded.

Record an inferred address only when `Identity status` is `Confirmed`. Infer it
only after finding at least two current public examples at the same company
domain using the same format. Check alternate company domains and the name
variations above before recording it. Never emit a low-confidence guess.

## Contact record

Create or update a network contact record with these fields:

```text
Name:
Company:
Current role:
Relationship:
Profile:
Identity status:
Professional email:
Email status:
Evidence observations:
Inference:
Last verified:
Outreach status:
Next action:
```

Use one unambiguous contact evidence record: `Evidence observations` contains
the source URL, access date, and exact observed fact or pattern examples;
`Inference` contains only derived address or pattern reasoning and confidence.
Do not duplicate contact-discovery sources in the application's `Sources and
Evidence` table. In that table, record only claims used in the application or a
decision. Set `Last verified` to the research date. Keep discovery and outreach
separate: draft outreach only and never send without explicit user
authorization. After meaningful contact research tied to an opportunity,
update the application log, pipeline, and network with the date, action,
result or status, and next action. For standalone contact research with no
application, update the network only; state that exception. After an authorized
action or a reply, update the network. Update positioning whenever an external
signal changes the audience, a claim, or a message.
