# RETRO: SkillVault Retrofitting Process

## Purpose

RETRO helps users migrate scattered skills, extensions, and plugins into a SkillVault-compliant central skills library (`~/.agents/skills`).

RETRO stands for:

# **Reusable Extraction & Tool-agnostic Reorganization**

## Why RETRO exists

Many users have full agent skills scattered outside of the central vault, often located in:
- `.claude/skills/`
- `.codex/skills/`
- `.gemini/extensions/`
- `.cursor/rules/`
- `plugins/`
- `extensions/`
- `skills/`

RETRO hunts down these scattered skills and categorizes them to determine if they can be safely migrated to the central vault.

## RETRO Output Categories

When scanning a project or directory, RETRO places discovered skills into one of three buckets:

### 1. Safe to migrate
These skills are **agent-agnostic**. They do not rely on specific agent features, proprietary prompt syntax, or agent-specific binaries. They can be immediately moved or symlinked into `~/.agents/skills/` without modification.

### 2. Adaptable
These skills are **agent-specific**, meaning they mention things like "Claude", "Codex", or use specific agent XML tags/syntax (e.g., `<cursor>`, `@workspace`). However, they can be adapted to be agent-agnostic. RETRO proposes the adaptations required to make them compliant.

### 3. Stays as is
These skills are deeply tied to a specific platform, rely on complex local project configurations, or require executing agent-specific binaries that cannot be easily abstracted. It is perfectly fine for these to stay outside of the central vault.

## Core Rule: Human Approval

RETRO is a discovery and recommendation engine. 
**It must NEVER automatically move, adapt, or delete skills without explicit human approval.**
All migration actions must be manually verified and approved by the user.

## Migration Output Format

The standard output for a `retrofit-config.py plan` must look like this:

```txt
# SkillVault RETRO Migration Plan

Scanned path: `/path/to/scan`

## Safe to migrate:
- (List of skills ready to move)

## Adaptable:
- (List of skills with proposed adaptations)

## Stays as is:
- (List of skills that should remain untouched)
```

## How to execute

Use the included script:
`python scripts/retrofit-config.py plan /path/to/project`

Review the output carefully. If you agree with the adaptations, you may manually move the skills or adjust them as proposed.
