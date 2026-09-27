# Technical Media Distillation Pattern

Use this structured prompt and format when distilling ingested media in Step 3 of the `/absorb` protocol.

---

## Purpose
Extract implementation-grade primitives, defensive guardrails, and architectural heuristics from external media to prepare a comparative delta audit against an existing asset.

---

## Output Format

### 1. Core Architectural Primitives
Extract the foundational structural building blocks and design patterns introduced or emphasized by the media:
- **Name & Definition**: Clear, concise terminology for the primitive.
- **Topological Shape**: How the process or data flows (e.g., Chain, Diamond, Branch, Loop, Router).
- **Execution Mechanism**: How work is dispatched, coordinated, and terminated.

### 2. Failure Modes & Defensive Guardrails
Identify the explicit vulnerabilities, anti-patterns, or failure boundaries cited:
- **Failure Mode**: The specific breakdown (e.g., infinite loops, silent partial failures, false independence, router bloat).
- **Mandatory Guardrail**: Concrete programmatic defense (e.g., circuit breaker `max_iterations`, merge validation gates, Rule of 5).
- **Verification Criterion**: How to objectively detect or test whether the guardrail held.

### 3. Operational Heuristics & Rules of Thumb
Actionable rules for deciding *when* and *when not* to use the techniques:
- **Selection Rule**: When to transition from a simpler primitive to a more complex one (e.g., The Wait Test).
- **Thresholds & Limits**: Hard numbers mentioned (e.g., $\le 5$ routes, 2–3 iterations max).
