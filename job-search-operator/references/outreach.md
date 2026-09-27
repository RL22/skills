# Outreach

Use the workspace contract. Set `SKILL_ROOT` to the resolved directory
containing `SKILL.md` and use its resolved paths; do not hard-code paths. Always
read `NETWORK`. Read `PROFILE` only when using candidate claims;
`APPLICATIONS` and `PIPELINE` only when the outreach is tied to an opportunity;
and `POSITIONING` only when an external signal or positioning work is involved.
Preserve standalone network-only work. Use only verified candidate claims and
current, attributed company facts. Draft messages only; never send, connect, or
follow up without explicit user authorization.

## Connection request

Write one concise connection note with one genuine, specific relevance: a
shared context, the recipient's public work, or a verified company fact. Do
not use links, phone numbers, a full pitch, or a referral request. The note
must be at most 200 Unicode characters, including spaces and punctuation.
Validate each final note before presenting it:

```sh
python3 "$SKILL_ROOT/scripts/count_characters.py" --limit 200 --validate "$NOTE"
```

Revise until validation passes. Present the note and its character count as a
draft awaiting authorization.

## After connection

Thank the person, briefly restore the context, and make one clear request.
Make declining optional and easy. Share a portfolio or booking link only after
connection and only when it helps the recipient act. Ask for an employee's
perspective before asking for a referral; do not assume they can or should
refer.

Keep follow-ups useful and light. Do not repeat a request after a clear no or
no response without a meaningful new reason. Reuse an existing message thread
when contacting a recruiter. Treat an old role as potentially closed; state
the candidate's current positioning and role families, then ask about the
recruiter's current employer and remit rather than presuming an opening.

## Opportunity-linked direct outreach

When an identifiable hiring manager or recruiter is appropriate and the user
wants opportunity outreach, pair the application with a concise direct message
instead of treating submission as the only action. Draft, but do not send, a
sequence of at most three touches:

1. **You:** name a specific team priority, problem, or public signal; connect it
   to two or three short, verified achievement bullets; make one easy request.
2. **Me:** after a reasonable interval, reframe one relevant piece of candidate
   value or add useful evidence rather than restating the first message.
3. **Us:** close the loop gracefully, leave a low-pressure path to reconnect,
   and stop unless the recipient replies or genuinely new context emerges.

Do not attach a resume in the first cold email unless the posting or recipient
requests it; link or attach it later when it helps them act. Personalization
must be specific and sourced, not manufactured familiarity. A three-touch
sequence is a ceiling, not a requirement: use fewer touches for a clear no, a
closed role, channel norms, or weak fit. Never duplicate the same touch across
email and LinkedIn at the same time.

## Record outcomes

After an authorized, meaningful outreach action or a reply, update the network
record with the date, channel, sequence touch, summary, status, and next action.
After an
external signal changes the audience, a claim, or a message, update the
positioning log. Do not record a draft as sent or infer interest, availability,
or a referral.
