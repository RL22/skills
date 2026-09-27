---
name: gws-gmail-cleanup
description: Audit and clean Gmail storage using Google Workspace CLI. Use when the user wants to install or verify gws, connect Gmail, audit inbox storage, define keep/remove rules, generate JSON cleanup reports, move approved messages to Trash, or permanently delete approved Gmail messages.
compatibility: Requires Node.js/npm, Google Workspace CLI, Google Cloud CLI for setup, network access, and Gmail OAuth permissions.
metadata:
  version: "1.0.0"
  portability: "agent-skills"
author: "Sprintz"
date_added: "2026-08-12"
---

# GWS Gmail Cleanup

Use this skill to safely audit and clean Gmail with `gws`. Keep the workflow review-first: verify access, ask the user what to keep and remove, generate JSON reports, then apply only approved actions.

## Required Workflow

1. Verify setup before any audit:
   - Run `scripts/gws_doctor.mjs`.
   - If `gws` is missing, guide `npm install -g @googleworkspace/cli`.
   - If auth is missing or invalid, guide `gws auth setup`, `gws auth login`, then rerun the doctor.
   - Confirm Gmail access before listing messages.

2. Ask the user for cleanup policy:
   - What is the goal: storage reduction, clutter reduction, old mail, label cleanup, sender cleanup, category cleanup, or attachment cleanup?
   - What should always be kept: labels, senders/domains, terms, attachment types, message categories, years, or mailbox areas?
   - Which sensitive categories should be protected: medical, financial, legal, identity, jobs, account/security, receipts/orders, personal documents?
   - Whether PDFs, MP3s, Sent, Starred, Important, and custom keep labels should be protected. Recommend protecting them by default.

3. Audit before cleanup:
   - Use `scripts/gmail_audit.mjs` with the user's query or bucket choices.
   - Write JSON reports only.
   - Separate candidates from held/protected messages.
   - Present counts, estimated size, top domains, years, labels, and largest messages for review.

4. Apply actions only after approval:
   - Default destructive action is move to Trash.
   - Permanent delete requires a second explicit approval and a reviewed approved-ID file.
   - Direct permanent delete is allowed only when the user explicitly asks for it.
   - Use `scripts/gmail_bulk_apply.mjs`; never hand-roll deletion loops when the script can be used.

## Safety Rules

- Never silently delete Gmail messages.
- Never include protected or user-defined keep messages in automatic cleanup candidates.
- Treat Gmail search results as potentially sensitive until metadata is reviewed.
- Keep JSON artifacts for accountability:
  - `audit-summary.json`
  - `message-candidates.json`
  - `held-protected.json`
  - `approved-message-ids.json`
  - `action-log.jsonl`
- Prefer Trash first even when the user says "delete" unless they explicitly ask to skip Trash or permanently delete.
- If Gmail reports insufficient scopes after a new login, ask the user to re-authenticate with the required Gmail scope and retry after clearing stale token cache only if needed.

## Scripts

- `scripts/gws_doctor.mjs`: non-destructive prerequisite, auth, and Gmail profile checker.
- `scripts/gmail_audit.mjs`: non-destructive Gmail audit with JSON outputs.
- `scripts/gmail_bulk_apply.mjs`: guarded batch Trash or permanent-delete helper.
- `scripts/install-cross-agent-links.sh`: idempotent symlink installer for Claude Code and OpenCode discovery paths.

Read `references/gws-gmail-commands.md` for exact `gws` command examples and troubleshooting. Read `references/cleanup-policy.md` when designing user prompts or default protections.
