---
name: skillvault
description: Establish ~/.agents/skills as the single source of truth for reusable agent skills, evaluate candidate skills with SIFT, and retrofit old agent-specific config into a portable SkillVault library.
license: MIT
compatibility: Agent-agnostic. Designed for agents that can read local files and follow project instructions. Optional Python scripts require Python 3.9+.
metadata:
  author: Sprintz
  version: "0.1.0"
  category: agent-governance
---

# SkillVault

Use this skill when the user wants to create, organize, evaluate, migrate, install, govern, or standardize agent skills across multiple AI coding agents.

SkillVault establishes:

```txt
~/.agents/skills
```

as the single source of truth for reusable agent skills.

It helps agents avoid fragmented skill folders, duplicated instructions, tool-specific rewrites, and unreviewed third-party skills.

## When to use this skill

Use this skill when the user asks to:

- Create a central agent skill library
- Evaluate an agent skill before adoption
- Compare skills for user fit
- Set up a universal skills policy
- Standardize skills across Claude Code, Antigravity, Codex, Cursor, OpenCode, or similar tools
- Decide whether a skill should be adopted, edited, trialed, forked, or rejected
- Create or update `user-profile.md` for skill assessment
- Keep skills agent-agnostic and portable
- Retrofit old agent-specific config into SkillVault-compatible skills
- Migrate reusable instructions from `AGENTS.md`, `CLAUDE.md`, Cursor rules, Copilot instructions, Antigravity config, OpenCode config, or similar files

Do not use this skill for general software package reviews unless the package is intended to act as an agent skill or reusable agent workflow.

## Core policy

All reusable agent skills should live in:

```txt
~/.agents/skills
```

Agent-specific environments may reference, symlink, copy, or index these skills, but the canonical version should remain in the central library.

## Universal Skills Policy

A skill should be:

1. **Portable** — usable across more than one agent where possible.
2. **Inspectable** — easy to read, audit, and modify.
3. **User-fit** — matched to a real user workflow.
4. **Safe** — avoids unnecessary permissions, unsafe commands, and hidden behavior.
5. **Version-aware** — has a clear source, status, and review date.
6. **Progressively disclosed** — keeps `SKILL.md` concise and moves details into references or assets.
7. **Non-fragmented** — avoids duplicating divergent copies across agents.

See `references/universal-skills-policy.md` for the full policy.

## SIFT evaluation process

SIFT means **Skill Inspection & Fit Testing**.

When evaluating a candidate skill, use the SIFT method to score and recommend an adoption decision (Adopt, Trial, Fork, Reject, etc.). 

See `references/sift-process.md` for the full step-by-step process.

## RETRO migration process

RETRO means **Reusable Extraction & Tool-agnostic Reorganization**.

Use RETRO when the user already has scattered agent-specific config (like `AGENTS.md`, `.cursor/rules/*.md`) and wants to make it SkillVault-compliant.

See `references/retrofit-process.md` for the full RETRO process.

## Use scripts when helpful

If the agent has local file access and Python is available, use:

```txt
scripts/inspect-skill.py
```

to summarize a candidate skill folder before reading every file.

Use:

```txt
scripts/score-skill.py
```

to calculate a weighted recommendation from category scores.

Use:

```txt
scripts/retrofit-config.py
```

to scan, plan, or generate a policy-compliant migration from existing agent configs.

Scripts are optional. If unavailable, perform the process manually using the references and assets.

## User profile requirement

A skill is not good in the abstract. It is only good relative to a user, workflow, agent stack, and risk profile.

Before making an adoption decision, create or infer a `user-profile.md` using `assets/user-profile.md` as the template.

## Default scoring

Score each category from 1 to 5 to reach a final decision band (Adopt, Trial, Reject, etc.).

See `references/skillfit-scorecard.md` for the full scoring rubric, decision bands, and required risk flags.

## Output formats

For skill evaluations, use `assets/evaluation-report.md`.

For retrofit migrations, produce a report with:

- Scanned path
- Agent config files found
- Reusable skill candidates
- Project-specific instructions to keep
- Risk flags
- Proposed migration
- Recommended next steps

## Agent-agnostic behavior rules

- Do not assume one agent is the source of truth.
- Do not create separate competing skill libraries for each agent.
- Prefer `~/.agents/skills` as the canonical location.
- Keep agent-specific notes as adapters, not forks, unless absolutely necessary.
- Preserve the Agent Skills open structure: `SKILL.md`, optional `scripts/`, `references/`, and `assets/`.
- Keep `SKILL.md` concise.
- Move detailed explanations into `references/`.
- Move templates into `assets/`.
- Use scripts only when they improve evaluation, reduce token spend, or improve user experience.
- Flag risky scripts, unclear permissions, missing documentation, and vendor lock-in.
- Be decisive, but state uncertainty clearly.

## Companion CLI

The **sv** command-line tool (in this repo) operationalizes this policy: manage git-backed vault topology, doctor symlink repair, per-agent skill activation, and gated install with safety snapshots. Run `python3 -m sv --help` from the repo root to explore init, snapshot, doctor, scan, list, info, outdated, migrate, enable, disable, status, install, uninstall, and sync commands.
