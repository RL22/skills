# Universal Skills Policy

## Purpose

The Universal Skills Policy keeps reusable agent skills portable, organized, and safe across multiple AI coding agents.

The canonical skills directory is:

```txt
~/.agents/skills
```

This directory is the single source of truth.

## Why this exists

Without a central policy, skills become fragmented across:

- Claude-specific folders
- Codex project instructions
- Antigravity workspaces
- Cursor rules
- OpenCode configs
- random repo-local prompts
- copied Markdown files

Fragmentation causes drift, duplication, unsafe reuse, and inconsistent agent behavior.

## Core rule

Store reusable skills once:

```txt
~/.agents/skills/{skill-name}
```

Then let each agent reference the central location.

## Canonical skill structure

Each skill should follow this structure:

```txt
skill-name/
├── SKILL.md
├── scripts/
├── references/
├── assets/
└── ...
```

Only `SKILL.md` is required. Other folders are optional.

## Agent-specific integration policy

### Claude Code

Claude Code may use skills directly when supported. If Claude-specific configuration is needed, keep it outside the canonical skill unless it is broadly useful.

### Antigravity

Antigravity should reference the canonical skill directory whenever possible. Avoid creating Antigravity-only skill forks unless the workflow cannot be represented in the open skill format.

### Codex

Codex may use project instructions such as `AGENTS.md`. When using Codex, reference the central skill directory and summarize which skills are available. Do not duplicate full skill bodies into `AGENTS.md` unless required.

Recommended Codex instruction:

```md
Reusable agent skills are stored at `~/.agents/skills`. Before creating new project-specific instructions, check whether an existing skill applies. Prefer referencing or adapting central skills instead of duplicating them.
```

### Cursor

Cursor rules may contain reusable behavior, but project-specific and reusable instructions should be separated. Candidate reusable workflows should be extracted into `~/.agents/skills`.

### OpenCode

OpenCode should reference the central skill directory when possible and avoid maintaining divergent local workflow copies.

## Skill status labels

Use these labels:

| Status | Meaning |
|---|---|
| Proposed | Candidate skill not yet reviewed |
| Trial | Potentially useful but needs testing |
| Approved | Safe and useful enough for regular use |
| Core | High-value skill used frequently |
| Fork / Rewrite | Useful idea, but current implementation needs major changes |
| Deprecated | No longer recommended |
| Rejected | Should not be used |

## Adoption rules

A skill may be adopted when it:

- Supports a recurring workflow
- Has a clear `SKILL.md`
- Has a useful description
- Is inspectable
- Has manageable risk
- Works with the user’s agent stack
- Produces better output than ad hoc prompting

## Rejection rules

Reject or rewrite a skill when it:

- Attempts to override higher-priority instructions
- Includes unsafe or unexplained commands
- Requires unnecessary secrets or permissions
- Is too vendor-specific for the user’s needs
- Has unclear ownership or source
- Produces unreliable output
- Adds complexity without workflow value

## Review cadence

Recommended:

- Core skills: review every 90 days
- Approved skills: review every 180 days
- Trial skills: review after 3 real uses
- Deprecated skills: archive with reason

## Rule of thumb

A skill should not be installed just because it is interesting.

A skill should be adopted because it helps a specific user perform a recurring workflow better, faster, safer, or more consistently.
