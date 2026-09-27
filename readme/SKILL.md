---
name: readme
description: Craft high-converting, visually stunning, Product Hunt-worthy README files using GitHub Flavored Markdown (GHFM). Use when writing, reviewing, redesigning, or auditing project READMEs, creating launch materials, or structuring developer-facing documentation.
argument-hint: [<repo-or-path>] [--template=cli|saas|library|agent] [--producthunt] [--audit]
license: MIT
compatibility: Agent-agnostic. Compatible with Antigravity, Claude Code, Cursor, Codex, OpenCode.
metadata:
  author: Sprintz
  version: "1.1.0"
  category: design-and-craft
---

# GHFM README Architect: Product Hunt & Developer Launch Mastery

Transform repository documentation into high-converting, designer-grade storefronts. This skill applies GitHub Flavored Markdown (GHFM) mastery, Product Hunt launch ergonomics, and visual patterns distilled from [`matiassingers/awesome-readme`](https://github.com/matiassingers/awesome-readme).

---

## The Philosophy of a Top 1% README

A world-class README is not a dump of text or technical notes; it is a **conversion landing page** rendered in the browser. Developers and Product Hunt hunters decide whether to star, install, or upvote within 5 seconds.

```
       [ 0 - 5 SECONDS ]        --> Hero Banner + Tagline + Badges + PH Widget + Live Demo (GIF)
       [ 5 - 15 SECONDS ]       --> Problem vs Solution (3-Column Card Table) + Core Architecture
       [ 15 - 30 SECONDS ]      --> Frictionless Quickstart (One Copy-Paste Command)
       [ 30+ SECONDS ]          --> Feature Deep Dives (<details>), Tech Stack, Star History & Trust
```

1. **The 5-Second Rule**: Above the fold must communicate what the product is, who it is for, why it matters, and provide immediate visual proof (GIF or high-res preview).
2. **Visual-First (Show > Tell)**: High-contrast terminal recordings (`vhs`), animated UI walkthroughs, or clean architecture diagrams beat paragraphs of text every time.
3. **Frictionless Time-to-Value**: Instant gratification. A developer should go from reading the headline to running the project in under 30 seconds.
4. **Native GHFM Craftsmanship**: Exploit the full rendering engine of GitHub—dark/light adaptive banners (`<picture>`), borderless HTML table cards, dynamic SVG icons via Iconify, collapsible `<details>` blocks, and native GitHub Alerts (`> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`).

---

## 6-Step README Crafting Workflow

Follow this sequence whenever authoring or refactoring a README:

```
  ┌─────────────────┐     ┌─────────────────────┐     ┌──────────────────────┐
  │ 1. Ingest & DNA │ ──> │ 2. Select Archetype │ ──> │ 3. Above-the-Fold    │
  └─────────────────┘     └─────────────────────┘     └──────────────────────┘
                                                                 │
  ┌─────────────────┐     ┌─────────────────────┐     ┌──────────┴───────────┐
  │ 6. Trust & Proof│ <── │ 5. Quickstart & Deep│ <── │ 4. Problem & Solution│
  └─────────────────┘     └─────────────────────┘     └──────────────────────┘
```

### Step 1: Project DNA & Positioning Triage
Extract the essential identity before writing markdown:
- **Core Value Proposition**: The punchy 1-sentence hook ("Superhuman for X", "Zero-config X for Y").
- **Target Persona**: CLI power user, frontend engineer, data scientist, or non-technical evaluator?
- **Key Metric/Differentiator**: 10x faster? 100% offline? End-to-end encrypted? Zero dependencies?
- **Launch Context**: Is this for an upcoming Product Hunt launch, GitHub Trending push, or enterprise open source?

### Step 2: Archetype Selection
Match the project to one of the 4 proven archetypes (see [`references/readme-archetypes.md`](references/readme-archetypes.md)):
1. **Developer Tool / CLI**: Focus on terminal recordings, installation matrix (`brew`, `curl`, `pipx`), command recipes, and configuration flags. *(Template: [`assets/template-cli-tool.md`](assets/template-cli-tool.md))*
2. **Full-Stack SaaS / Web App**: Focus on Product Hunt badges, problem/solution cards, interactive screenshot grids, cloud vs self-hosted guides. *(Template: [`assets/template-saas-platform.md`](assets/template-saas-platform.md))*
3. **Open Source Library / SDK**: Focus on package badges (npm/PyPI), API snippets, benchmark charts, and type safety guarantees. *(Template: [`assets/template-library-framework.md`](assets/template-library-framework.md))*
4. **AI Agent / Pipeline**: Focus on DAG architecture diagrams, model compatibility matrices, benchmark evals, and prompt examples. *(Template: [`assets/template-ai-agent.md`](assets/template-ai-agent.md))*

> [!IMPORTANT]
> **Progressive Disclosure Rule**: Load ONLY the single template corresponding to your selected archetype. Never dump all templates into active context simultaneously.

### Step 3: Above-the-Fold Engineering
Construct the high-impact header:
- **Branding Header**: Centered project banner or logo with dark/light mode switching (`<picture>` or `#gh-dark-mode-only` tags).
- **Punchy Title & Tagline**: `# Project Name` followed by bold subtitle and concise mission statement.
- **Product Hunt Launch Embed**: If launching, place the official Product Hunt badge directly under the title.
- **Unified Badge Ribbon**: 3–5 cohesive shields (`style=for-the-badge` or `flat-square`) sharing a unified color palette (version, license, build status, discord/stars). Avoid rainbow clutter.
- **Quick Links Bar**: `[Website](...) • [Documentation](...) • [Live Demo](...) • [Discord](...)`
- **Hero Asset**: Embedded demo GIF or video immediately below the badges.

### Step 4: Problem & Solution Architecture
Frame the pain point and how the project uniquely resolves it:
- **The Problem**: Use a 3-column HTML table (`<table width="100%"><tr><td width="33%">...</td></tr></table>`) with Iconify SVG icons to display 3 distinct pain cards.
- **The Solution & How It Works**: Numbered steps paired with a clean architecture diagram (Mermaid.js or high-res SVG schema).

### Step 5: Frictionless Quickstart & Feature Deep Dives
- **Zero-Friction Quickstart**: 1–2 commands max. Highlight commands in fenced codeblocks (`bash`, `python`). Show expected output.
- **Feature Highlights**: Highlight 3–6 top features. For complex features, use collapsible `<details><summary>` accordions to keep the README fast to scan.
- **Pro Tips & Warnings**: Use GitHub callouts:
  ```markdown
  > [!TIP]
  > Pro tip goes here.
  ```

### Step 6: Trust, Social Proof & Community
Close with authority and conversion:
- **Tech Stack Grid**: Skill icons or clean markdown table detailing components.
- **Star History Chart**: Dynamic interactive SVG (`https://api.star-history.com/svg?repos=owner/repo&type=Date`).
- **Community & Contributors**: Contributor avatar wall (`contrib.rocks`) and links to issue tracker, PR guidelines, and Discord.
- **License**: Clear SPDX license badge and copyright notice.

---

## Quick Reference Table: GHFM Enhancements

| Enhancement | Markdown / HTML Primitive | Reference Doc |
| :--- | :--- | :--- |
| **Dark / Light Image Theme** | `<picture><source media="(prefers-color-scheme: dark)" ...>` | [`references/ghfm-syntax-matrix.md`](references/ghfm-syntax-matrix.md) |
| **3-Column Feature Cards** | `<table width="100%"><tr><td width="33%" valign="top">` | [`references/ghfm-syntax-matrix.md`](references/ghfm-syntax-matrix.md) |
| **Dynamic Vector Icons** | `<img src="https://api.iconify.design/lucide/[name].svg?color=%23[hex]" width="20"/>` | [`references/ghfm-syntax-matrix.md`](references/ghfm-syntax-matrix.md) |
| **Product Hunt Embed** | Official Product Hunt SVG widget embed with UTM tagging | [`references/producthunt-launch-anatomy.md`](references/producthunt-launch-anatomy.md) |
| **GitHub Native Alerts** | `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]` | [`references/ghfm-syntax-matrix.md`](references/ghfm-syntax-matrix.md) |
| **Terminal Recording GIF** | `vhs` tape scripts rendered to optimized GIF | [`references/visual-assets-guide.md`](references/visual-assets-guide.md) |
| **Collapsible Accordions** | `<details><summary><b>Feature Name</b></summary>...</details>` | [`references/ghfm-syntax-matrix.md`](references/ghfm-syntax-matrix.md) |
| **Interactive Star History** | `![Star History](https://api.star-history.com/svg?repos=owner/repo&type=Date)` | [`references/visual-assets-guide.md`](references/visual-assets-guide.md) |

---

## Automated Audit Tool

Audit any README for GHFM craftsmanship. Add `--producthunt` only when the project is launching: it also
scores the Product Hunt embed and social proof (Star History, contributors, Discord). Without it those checks
are skipped and the score is rescaled, so a README is never pushed toward launch widgets it doesn't need.

```bash
# Run automated score & recommendations
python3 <skill>/scripts/audit-readme.py path/to/README.md

# Launch readiness, with verbose check details
python3 <skill>/scripts/audit-readme.py path/to/README.md --producthunt --verbose
```

Pass `--producthunt` to the audit whenever the request carries `--producthunt` or mentions a launch.

---

## Common Anti-Patterns & Red Flags

| Anti-Pattern | Why It Fails | What To Do Instead |
| :--- | :--- | :--- |
| **Wall of Prose** | Users skim; dense text is skipped entirely. | Break into bullet cards, tables, and visual schematics. |
| **Missing Hero Visual** | Abstract descriptions fail to build trust. | Embed a 10-second GIF or terminal capture (`vhs`) above the fold. |
| **Invisible Logo in Dark Mode** | Black PNGs disappear against GitHub Dark theme. | Use adaptive `<picture>` tags or transparent SVGs with light borders. |
| **Rainbow Badge Clutter** | 15 mismatched badge styles look amateurish. | Restrict to 3–5 badges with consistent style and unified palette. |
| **Delayed Quickstart** | Forcing users to scroll through history to find install. | Place install snippet immediately following the problem/solution. |
| **Static Broken Images** | Broken assets ruin credibility instantly. | Always use raw GitHub URLs or verify relative asset paths. |
