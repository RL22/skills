# Networking and Engagement Brief

Use the workspace contract. Set `SKILL_ROOT` to the resolved directory
containing `SKILL.md` and use its resolved paths; do not hard-code paths. Always
read `NETWORK` and `PIPELINE`. Read `PROFILE` only when a draft makes a
candidate claim, and `POSITIONING` only when an external signal changes the
audience, a claim, or a message. Draft only; never send, post, like, comment,
connect, or follow up without explicit user authorization.

## Generate the brief

```sh
python3 "$SKILL_ROOT/scripts/daily_networking_brief.py" --today YYYY-MM-DD
```

The brief has three sections: up to ten LinkedIn posts worth a comment, the
connections to message today with a touch type and reason, and three to five
further actions. The script resolves `NETWORK` and `PIPELINE` itself and reports
a fallback path in its Data quality section. Read that section first and
carry each warning into the answer. A stale or missing source lowers
confidence; state the gap and keep the recommendation, without filling it with
assumptions.

Posts come from `linkedin-scout`, which ranks by alignment with target
companies and role themes, author fit, recency, and comment window. When the
newest post is more than two days old, or the user asks for fresh posts, refresh
with a scoped read-only pull, then rerun the brief:

```sh
python3 ../linkedin-scout/scripts/cli.py discover-feed --company SLUG
python3 ../linkedin-scout/scripts/cli.py discover-feed --person HANDLE
```

Scope every pull with `--company` or `--person`; the home feed has no reliable
extraction path.

## Turn the brief into drafts

**Posts.** Prefer people over company pages. Draft one comment per chosen post:
one to three sentences, a specific observation or question grounded in verified
candidate experience, no flattery, links, or pitch. Save each as a draft with
`linkedin-scout queue-engagement` so the user can approve or reject it; the user
posts it personally.

**DMs.** Draft by touch type, following the outreach reference.

- `first_touch`: open with the recipient's team problem or a public signal, keep
  the candidate's side to one sentence, make no job ask, and propose a
  15-minute conversation. For someone not yet connected, write a connection
  note of at most 200 characters and validate it with `count_characters.py`.
- `send_drafted`: review the existing draft against current facts.
- `nudge_1`: reference the earlier message and add one new piece of value.
- `nudge_2`: reframe one relevant piece of value in a single short message.
- `escalate`: draft a short note to the department hiring manager, or
  recommend archiving. A fourth touch is never drafted.
- `warm_follow_up`: propose two concrete 15-minute slots; share the booking link
  only after connection.

Ask for an employee's perspective before asking for a referral. Show each draft
with its reason so the user can judge the fit before sending.

**Further actions.** Present them as a checklist with the brief's `why` and
`how`. Produce an artifact, such as an audit outline, only when the user asks.

## Record outcomes

Log nothing from the brief itself. After the user reports an authorized action
or a reply, update the matching `NETWORK` record with date, channel, touch,
summary, status, and next action, and mark the queued draft with
`linkedin-scout review-engagement`. When the brief and a `NETWORK` Status
disagree, `NETWORK` wins; name the discrepancy. Automated posting, liking,
commenting, and messaging break LinkedIn's User Agreement, so every send stays a
human act in the user's own browser.
