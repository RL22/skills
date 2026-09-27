---
name: map-graph
description: Architect complex tasks into directed agent graphs (DAGs) with model tier routing, state schemas, and guardrails. Trigger on /map-graph, "graph engineering", or multi-agent workflow architecture.
license: MIT
compatibility: Agent-agnostic. Designed for Antigravity, Claude Code, Cursor, Codex, OpenCode, and custom agent harnesses.
metadata:
  author: Sprintz
  version: "2.3.0"
  category: agent-architecture
---

# Map-Graph: Agentic Graph Engineering & Model Routing

Graph engineering converts unstructured prompts into a **managed workflow of specialized nodes** connected by shared state, model tier routing, and defensive gates.

## Scope

Execute this protocol for multi-step tasks requiring:
- Parallel subagent fan-out (diamonds)
- Context-driven skill routing (branches)
- Iterative validation and refinement cycles (loops)
- Strict human-in-the-loop approval gates before production mutations

---

## 6-Step Execution Protocol

Execute these 6 steps in sequence:

### Step 1: Goal & Output Contract
1. Formulate the core objective in **one clear sentence**.
2. Define the input schema (files, user prompts, APIs) and the final output deliverable.

**Completion Criterion**: One-sentence goal, typed input description, and target output artifact format documented.

---

### Step 2: Topology Deconstruction & The Wait Test
Deconstruct the task into single-purpose nodes using the **4 Canonical Graph Primitives** (detailed in [`references/graph-patterns.md`](references/graph-patterns.md)):
- **Chain**: Sequential execution where node $N+1$ strictly requires node $N$'s output.
- **Diamond**: Parallel fan-out across independent subtasks, converging at a merge gate.
- **Branch**: Context-aware routing from a classifier to specialized handlers ($\le 5$ routes).
- **Loop**: Evaluator-optimizer cycle between generator and critic until acceptance criteria pass. Critic nodes must bind to an objective **Binary Verifier Checklist** (via [`eval-engine`](../eval-engine/SKILL.md)) to eliminate continuous score hedging.

#### The Wait Test Protocol
Audit every sequential dependency by asking:
> *"Does this step strictly require the output of the step immediately before it?"*

- **YES**: Dependency is genuine; maintain sequential link.
- **NO**: Link **fails the Wait Test**; refactor into a **Diamond (parallel fan-out)** to slash execution latency.

**Completion Criterion**: Every task phase mapped to a primitive; all sequential links verified via the Wait Test with zero unneeded waits.

---

### Step 3: Model Tier Routing & Effort Binding
Bind each node to a **tier number** and effort level per [`references/capability-tier-matrix.md`](references/capability-tier-matrix.md):
- **Tier 0**: Deterministic checks (lint, tests, AST, regex). No LLM. `Effort: N/A`
- **Tier 1**: Fast triage, summarization, extraction. `Effort: Light`
- **Tier 2**: Frontier workhorse (code implementation, copywriting). `Effort: Medium`
- **Tier 3**: Deep reasoning, adversarial review, root-cause diagnosis. `Effort: High`

Map nodes to task aliases (`delegate.sh --task <name>`) or abstract tiers. Avoid hardcoding vendor model names directly into node definitions.

#### The Pareto Model Catalog Heuristic
Continuously benchmark tasks against compact open-weights models (via `eval-engine`). Route narrow, high-volume tasks to the lowest cost/latency model tier that satisfies the binary acceptance criteria, preserving Tier 3 strictly for complex reasoning, root-cause diagnosis, or trace mining.

**Completion Criterion**: Every node assigned Tier 0–3, effort level, task alias, and Pareto cost/quality verification; no raw model names.

---

### Step 4: Shared State Payload Schema
Define a strongly-typed TypeScript interface (`GraphState`) passed across nodes (reference implementation in [`assets/graph-template.ts`](assets/graph-template.ts)).

The state must contain:
- Task identifiers and user parameters
- Node output payloads
- Loop counters (`maxIterations: 3`, `iterationCount: 0`)
- Failure reason flags and parallel branch result maps

**Completion Criterion**: Complete, valid TypeScript `GraphState` interface with iteration bounds and branch result fields.

---

### Step 5: Visual Diagram Generation
Render an explicit Mermaid flowchart (`graph TD`) representing the complete graph topology:
- Node labels annotated with tier badges (e.g. `[Node 2: Unit Tests (Tier 0)]`)
- Wait-tested parallel branches
- Loop feedback cycles with iteration bounds (`iter < max_iterations`)
- Explicit human approval gates

**Completion Criterion**: Rendered, syntactically valid Mermaid flowchart displaying all nodes, tier badges, feedback loops, and human approval gates.

---

### Step 6: Defensive Guardrail Audit
Audit the topology against the 4 failure modes before finalizing:

| Primitive | Failure Mode | Mandatory Guardrail |
| :--- | :--- | :--- |
| **Chain** | Brittleness & cascading failure | Define fallback or retry policy on critical-path nodes. |
| **Diamond** | False independence & silent drops | Enforce scoped subagent context; require a Tier 0 **Merge Validation Gate** before synthesis. |
| **Branch** | Overengineering & classification drift | **The Rule of 5**: Cap router nodes at $\le 5$ branches; decompose if $> 5$. |
| **Loop** | Runaway token burn & infinite loops, and subjective evaluator hedging | **Circuit Breaker & Binary Gate**: Enforce explicit `max_iterations` (default: 3) with an escalation fallback. Require deterministic **Binary Verifier Checklist** (per `eval-engine`) to eliminate judge hedging. |

**Completion Criterion**: Guardrail audit table complete with all 4 topological checks verified.

---

## Supporting Reference & Discovery

- **Topology Patterns & Archetypes**: [`references/graph-patterns.md`](references/graph-patterns.md)
- **Model Tier Mapping Matrix**: [`references/capability-tier-matrix.md`](references/capability-tier-matrix.md)
- **Agent Evaluation & Binary Verifiers**: [`../eval-engine/SKILL.md`](../eval-engine/SKILL.md)
- **TypeScript State Engine**: [`assets/graph-template.ts`](assets/graph-template.ts)
- **Live Model Discovery Tool**: Run `python3 scripts/fetch-models.py` to query active model catalogs.

