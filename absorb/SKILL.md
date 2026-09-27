---
name: absorb
description: Ingest external media (video, article, thread) to extract architectural patterns, audit a target asset, and orchestrate upgrades via map-graph. Trigger on /absorb, "absorb media", or "upgrade asset from media".
argument-hint: <media-URL> [@target-asset] [--visual]
license: MIT
compatibility: Agent-agnostic. Compatible with Antigravity, Claude Code, Cursor, Codex, OpenCode.
metadata:
  author: Sprintz
  version: "1.1.0"
  category: agent-architecture
---

# Absorb: Media-to-Asset Architectural Evolution

Transforms external media (YouTube videos, podcasts, technical blogs, and engineering threads) into concrete upgrades on an existing skill, codebase, or architectural asset.

## Scope

Execute this protocol when:
- Consuming external media containing design patterns, algorithms, or guardrails relevant to an existing project.
- Auditing a target skill or codebase against newly published technical insights.
- Generating a structured upgrade implementation plan with explicit human approval required before execution.

---

## 6-Step Execution Protocol

Execute these 6 steps in sequence:

### Step 1: Inbound Triage & Media Extraction
1. Parse `$ARGUMENTS`:
   - `$0`: Source Media URL (YouTube, Substack, blog, X thread, or local transcript).
   - `$1`: Target Asset path (OPTIONAL: `@skill-name`, file path, or directory).
   - Flags: `--visual` (triggers visual screenshot extraction of on-screen slides/diagrams).
2. Ingest the media using the designated channel per [`references/media-extractors.md`](references/media-extractors.md):
   - **Video / Audio**: `yt-dlp` subtitle extraction + `scripts/clean_transcript.py` to `/tmp/absorb-clean.txt`.
   - **Static Articles**: `defuddle parse "<URL>" > /tmp/absorb-clean.txt`.
   - **Dynamic / Gated / Visual**: `capt-chrome-agent` DOM pull and slide frame capture (`--visual`).

**Completion Criterion**: Media ingested and clean text written to `/tmp/absorb-clean.txt`.

---

### Step 2: Insight Distillation via Fabric
Process the extracted content through the technical distillation pattern in [`references/distillation-pattern.md`](references/distillation-pattern.md) (or `/fabric extract_wisdom`):
1. **Core Architectural Primitives**: Foundational topologies (Chain, Diamond, Branch, Loop) and design patterns.
2. **Failure Modes & Defensive Guardrails**: Vulnerabilities, edge cases, and concrete defenses (circuit breakers, merge gates, caps).
3. **Operational Heuristics & Keywords**: Key technical domains, frameworks, and decision rules.

**Completion Criterion**: Distilled summary generated containing explicit primitives, guardrails, and domain keywords.

---

### Step 3: Target Asset Resolution & Discovery
Determine the target asset to upgrade:

- **Case A: Target Asset Provided in Invocation (`$1`)**:
  Resolve the target asset path, inspect its codebase or `SKILL.md`, and record its baseline structure.
- **Case B: Target Asset Omitted**:
  1. Extract core domains, frameworks, technologies, and architectural concepts from the distilled media.
  2. Perform a combined semantic search across both:
     - **Global Skills**: Scan `~/.agents/skills/INDEX.md` and relevant `SKILL.md` files.
     - **Active Workspace**: Scan project directories for relevant code modules, components, or services.
  3. Rank candidates purely by semantic relevance (unbiased mix of skills and codebase files) and present the **top 3–5 candidate assets** with a 1-sentence rationale for each.
  4. Always include an explicit **"Scaffold New Asset"** option:
     - *Option [N+1]: Scaffold New Skill* (`~/.agents/skills/<suggested-name>`)
     - *Option [N+2]: Scaffold New Codebase Feature/Module* (`src/<suggested-path>`)
  5. **Prompt the user to select an option** (or specify an unlisted path). Halt until the user confirms. If a new asset is selected, Step 4 produces a **Greenfield Specification & Architecture** rather than an existing asset gap audit.

**Completion Criterion**: Target asset confirmed and verified readable (or new asset scaffold target established), with baseline state documented.

---

### Step 4: Asset Delta Audit & Gap Matrix
Audit the confirmed target asset against the distilled insights across three dimensions:

| Delta Dimension | Audit Question | Target Finding |
| :--- | :--- | :--- |
| **Missing Primitives** | What architectural primitives from the media does the target asset lack? | Structural additions to introduce. |
| **Vulnerability Gaps** | What failure modes identified in the media is the target asset currently exposed to? | Defensive guardrails to install. |
| **Anti-Patterns & Sediment** | What does the target asset currently do that the media identifies as brittle or slow? | Redundant logic or bad patterns to prune. |

**Completion Criterion**: Comparative Gap Matrix completed with high-impact recommendations categorized into Primitives, Guardrails, and Pruning.

---

### Step 5: Implementation Plan Architecture via `/map-graph`
Pass the Gap Matrix recommendations to [`map-graph`](../map-graph/SKILL.md) to **architect the implementation plan** without executing it:
1. **Topology Mapping**: Apply the **Wait Test** to identify parallelizable file domains (Diamonds).
2. **Model Tier Binding**: Bind proposed tasks to model tiers (Tier 0 deterministic tests, Tier 2 implementers, Tier 3 skeptics).
3. **Guardrails**: Apply the **Rule of 5** to router nodes and enforce **`max_iterations`** circuit breakers on review loops.
4. **Mermaid Diagram**: Render an explicit `graph TD` showing the proposed execution DAG.

**Completion Criterion**: Complete `/map-graph` architectural specification and visual diagram generated and presented.

---

### Step 6: Implementation Human Gate (Strict No Auto-Execution)
**MANDATORY RULE: `/absorb` NEVER automatically executes code changes, file mutations, or subagent dispatches.**

Present the implementation plan and execution graph to the human partner:
1. Summarize the proposed changes, files affected, and estimated subagent tiers.
2. Present 3 explicit user options:
   - **Approve & Execute**: User explicitly issues confirmation to dispatch subagents and apply changes.
   - **Refine Plan**: User requests modifications to the graph, tier allocations, or scope.
   - **Save Plan Only**: Persist the specification as an implementation plan artifact for future execution without touching code now.
3. **Halt and wait for the user's explicit instruction before executing any implementation steps.**

**Completion Criterion**: Process paused at the human gate. Subagents are dispatched ONLY after receiving explicit user approval in the subsequent turn.

---

## Supporting References

- **Media Extraction Recipes**: [`references/media-extractors.md`](references/media-extractors.md)
- **Technical Distillation Pattern**: [`references/distillation-pattern.md`](references/distillation-pattern.md)
- **Graph Engineering Protocol**: [`../map-graph/SKILL.md`](../map-graph/SKILL.md)
- **Chrome Agent (CDP) Reference**: `capt-chrome-agent` skill (separate, not bundled in this repo; only needed for dynamic or gated pages)
- **Fabric Catalog**: [`../fbrc-fabric/SKILL.md`](../fbrc-fabric/SKILL.md)
