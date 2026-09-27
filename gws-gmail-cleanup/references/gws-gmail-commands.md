# GWS Gmail Commands

Use these commands as known-good patterns. Keep outputs JSON where possible.

## Setup and Verification

```bash
node --version
npm --version
gcloud --version
gws --version
npm install -g @googleworkspace/cli
gws auth setup
gws auth login
gws auth status
gws gmail users getProfile --params '{"userId":"me"}'
```

## Gmail Listing and Metadata

```bash
gws gmail users messages list \
  --params '{"userId":"me","q":"older_than:5y category:promotions","maxResults":500}' \
  --page-all \
  --page-limit 200 \
  --page-delay 25 \
  --format json

gws gmail users messages get \
  --params '{"userId":"me","id":"MESSAGE_ID","format":"metadata","metadataHeaders":["From","Subject","Date","List-Unsubscribe"]}' \
  --format json
```

## Batch Actions

Move approved messages to Trash:

```bash
gws gmail users messages batchModify \
  --params '{"userId":"me"}' \
  --json '{"ids":["MESSAGE_ID"],"addLabelIds":["TRASH"]}' \
  --format json
```

Permanently delete approved messages:

```bash
gws gmail users messages batchDelete \
  --params '{"userId":"me"}' \
  --json '{"ids":["MESSAGE_ID"]}' \
  --format json
```

## Troubleshooting

- `invalid_grant` means the token is expired or revoked. Run `gws auth login`; if needed, rerun `gws auth setup`.
- `insufficient authentication scopes` means the current OAuth token does not include the required Gmail scope. Re-authenticate with the needed scope. Permanent delete may require broader Gmail access than Trash.
- If `gws auth status` shows the new scope but Gmail calls still fail, a stale local token cache may be in use. Prefer re-login first; clear only the `gws` token cache if the user approves or the local workflow requires it.
- Google storage UI may lag after deletes. Verify Gmail message counts with `gws gmail users getProfile` and storage separately in the UI.
